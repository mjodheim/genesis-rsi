"""Single frozen experiment of lineage-owned measured pipeline target selection."""
import argparse
import gzip
import json
import os
import sys
from collections import Counter

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v27.development import Host as GraphHost
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v29 import campaign as v29, native_bank
from experiment.rsi_v30 import family, freeze, fresh_bank, meta
from experiment.rsi_v30.pipeline_contexts import PARTS, TARGETS, PUBLIC_CAPS, diagnostics, episode, source

ATTEMPT = ROOT / "results/rsi-v30/target-20261001/V30_ATTEMPT.json"
VERDICT = ATTEMPT.with_name("V30_FINAL_ADJUDICATION.json")
SELECTED = ATTEMPT.with_name("G7_SELECTED_POLICY.py")
RAW = ATTEMPT.with_name("V30_ATTEMPT_RAW.json.gz")


def preserve(record):
    """Lossless deterministic archive; the exclusive attempt marker stays present."""
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with RAW.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(encoded)
    write_json(ATTEMPT, {"schema": "mira-genesis-v30-lossless-attempt-index-v1", "status": record["status"],
                        "canonical_attempts": record["canonical_attempts"], "freeze_sha256": record["freeze_sha256"],
                        "raw_filename": RAW.name, "raw_bytes_sha256": digest_bytes(RAW.read_bytes()),
                        "uncompressed_bytes_sha256": digest_bytes(encoded), "record_sha256": digest(record)})


def read_attempt():
    index = json.loads(ATTEMPT.read_text())
    if index["schema"] != "mira-genesis-v30-lossless-attempt-index-v1" or index["raw_filename"] != RAW.name:
        raise ValueError("Incomplete or unknown canonical attempt archive")
    encoded = gzip.decompress(RAW.read_bytes())
    record = json.loads(encoded)
    if (index["raw_bytes_sha256"] != digest_bytes(RAW.read_bytes())
            or index["uncompressed_bytes_sha256"] != digest_bytes(encoded) or index["record_sha256"] != digest(record)
            or any(index[key] != record[key] for key in ("status", "canonical_attempts", "freeze_sha256"))):
        raise ValueError("Lossless attempt archive or index was altered")
    return record


def public_calibration(*, replay=False):
    public = json.loads((meta.HERE / "PUBLIC_CONTEXTS.json").read_text())
    with gzip.open(meta.HERE / "PUBLIC_CONTEXTS_ALL.json.gz", "rt") as stream:
        all_rows = json.load(stream)
    if digest(all_rows) != public["all_examined_public_contexts_sha256"] or len(all_rows) != public["all_examined_context_count"]:
        raise ValueError("The complete public population, including negatives, was changed")
    indexed = {row["context_sha256"]: row for row in all_rows}
    if (len(indexed) != len(all_rows) or len(public["contexts"]) != sum(public["curriculum_counts"])
            or public["new_holdout_consumed"] or public["scope"] != "OUTCOME_CONDITIONED_PUBLIC_DEVELOPMENT_NOT_FRESH"):
        raise ValueError("Invalid public development scope or population")
    for row in public["contexts"]:
        if digest(row) != digest(indexed[row["context_sha256"]]) or not row["eligible_public_diagnostic_example"]:
            raise ValueError("Undisclosed public curriculum selection")
        if replay:
            for target in TARGETS:
                if digest(episode(row["context"], target)) != digest(row["variants"][target]):
                    raise ValueError("Altered public execution receipt")
            if row["diagnostics"] != diagnostics(row["baseline"], GraphHost(row["context"]["spec"])):
                raise ValueError("Public diagnostic cannot be reproduced")
    measured = meta.calibration(public)
    if digest(measured) != digest(json.loads((meta.HERE / "PUBLIC_CALIBRATION.json").read_text())):
        raise ValueError("Public selector calibration changed")
    return measured


def policies(flags):
    flags = family.validate(flags)
    result = {"adaptive_g7": family.render(flags), "parent_g6": family.parent()}
    result.update({"fixed_" + target: family.fixed(target) for target in PARTS})
    result.update({"ablation_" + part: family.render(tuple(0 if i == index else x for i, x in enumerate(flags)))
                   for index, part in enumerate(PARTS)})
    return result


def verify_graph(search, context, target):
    host = GraphHost(context["spec"])
    receipts = {}
    for key, node in search["nodes"].items():
        if key == "root":
            continue
        original = host.rows[node["candidate"]["token"]]
        expected = host.evaluate(original)
        if (original["source_sha256"] != node["source_sha256"] or digest(expected) != digest(node["evaluation"])
                or node["source_sha256"] in receipts):
            raise ValueError("Altered or duplicate revealed graph receipt")
        receipts[node["source_sha256"]] = node["evaluation"]
    class ReceiptHost(GraphHost):
        def evaluate(self, row):
            if row["source_sha256"] not in receipts:
                raise ValueError("Graph replay requests an unobserved proposal")
            return receipts[row["source_sha256"]]
    replay = run_search(source(context, target), ReceiptHost(context["spec"]), caps=PUBLIC_CAPS, isolated=True)
    if digest(replay) != digest(search):
        raise ValueError("Graph policy, choice, source, lineage, or budget changed")


def retention(successor, *, replay=False):
    if not successor.startswith(family.parent()):
        raise ValueError("G7 did not inherit the byte-exact qualified core")
    previous = json.loads(v29.ATTEMPT.read_text())
    native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
    rows = []
    for task, row, prepared in zip(native_bank.TASKS, previous["arms"]["g6"], native["tasks"]):
        search = {**row["search"], "policy_sha256": digest_bytes(successor.encode())}
        if replay:
            v29.verify_search(search, task, successor, prepared["seeded"])
        rows.append({"domain": task["domain"], "unchanged_core_receipt_replay": True,
                     "retained_search_sha256": digest(search), "best_quality_milli": search["best_quality_milli"]})
    return {"scope": "CONSUMED_L7_NATIVE_RECEIPT_RETENTION_NOT_FRESH_NATIVE_EXECUTION", "rows": rows,
            "no_loss": len(rows) == 4 and all(row["best_quality_milli"] == 1000 for row in rows)}


def adjudicate(record, frozen, *, replay=True):
    if record["status"] != "COMPLETED":
        raise ValueError("Incomplete V30 attempt")
    measured = public_calibration(replay=replay)
    if replay and digest(record["meta"]) != digest(meta.pilot(measured, isolated=True)):
        raise ValueError("Meta discovery or matched prior-acquisition ablation changed")
    arms = record["meta"]["arms"]
    selected = arms["inherited_g6"]["selected"]
    successor = family.render(selected["flags"])
    if (record["selected_source_sha256"] != selected["source_sha256"]
            or record["selected_source_sha256"] != digest_bytes(successor.encode())):
        raise ValueError("Selected source was substituted")
    meta_gain = (selected["qualified_discovery"] and tuple(arms["inherited_g6"]["utility"]) >
                 tuple(arms["g6_scheduling_ablation"]["utility"]))
    keep = retention(successor, replay=replay)
    if digest(keep) != digest(record["retention"]):
        raise ValueError("Prior capability retention changed")
    expected = policies(selected["flags"])
    utilities, selections = {}, {}
    if record["fresh_consumed"]:
        if set(record["arms"]) != set(expected):
            raise ValueError("Omitted adaptive, fixed-target, or selector-term control")
        for arm, controller in expected.items():
            rows = record["arms"][arm]
            if [row["context_sha256"] for row in rows] != [digest(context) for context in fresh_bank.CONTEXTS]:
                raise ValueError("Fresh contexts were omitted, filtered, or reordered")
            for context, row in zip(fresh_bank.CONTEXTS, rows):
                if row["context"] != context or row["diagnostics"] != diagnostics(row["baseline"], GraphHost(context["spec"])):
                    raise ValueError("Diagnostic was altered or includes future answers")
                if (row["target_call"] != {"controller_sha256": digest_bytes(controller.encode()),
                                          "payload_sha256": digest({"diagnostics": row["diagnostics"], "targets": TARGETS}),
                                          "represented_calls": 1, "isolated_policy_process": True}
                        or row["target"] not in TARGETS):
                    raise ValueError("Target choice or represented cost changed")
                if replay:
                    verify_graph(row["baseline"], context, "identity")
                    if row["target"] != meta.select(controller, row["diagnostics"], isolated=True):
                        raise ValueError("Lineage did not make the recorded target choice")
                    verify_graph(row["post"], context, row["target"])
            utilities[arm] = meta.context_utility(rows)
            selections[arm] = dict(Counter(row["target"] for row in rows))
        # The probe is equal for every arm, including the fixed targets.
        first = record["arms"]["adaptive_g7"]
        if digest(record["probes"]) != digest([row["baseline"] for row in first]):
            raise ValueError("Shared measured probes were substituted")
        if any(digest([r["baseline"] for r in rows]) != digest([r["baseline"] for r in first])
               for rows in record["arms"].values()):
            raise ValueError("Controls received unequal initial observations")
    predicates = {"qualified_l7_predecessor": frozen["previous_l7"]["v29_l7_positive"],
        "lineage_discovered_selector": selected["qualified_discovery"],
        "previous_acquisition_causally_reduces_next_discovery_cost": meta_gain,
        "unchanged_core_retains_prior_capabilities": keep["no_loss"],
        "fresh_adaptive_beats_parent_and_every_fixed_target": bool(utilities) and all(
            utilities["adaptive_g7"] > utilities[name] for name in ("parent_g6", *("fixed_" + part for part in PARTS))),
        "every_selector_term_causal_on_fresh_population": bool(utilities) and all(
            utilities["adaptive_g7"] > utilities["ablation_" + part] for part in PARTS),
        "multiple_pipeline_parts_selected_from_measured_evidence": bool(selections) and all(
            selections["adaptive_g7"].get(part, 0) > 0 for part in PARTS),
        "exact_freeze_single_attempt_equal_caps_zero_external_models": record["freeze_sha256"] == frozen["freeze_sha256"]
            and record["canonical_attempts"] == 1 and record["track"] == "A"
            and record["scientific_external_model_calls"] == 0 and record["python_version"] == frozen["python_version"]}
    positive = all(predicates.values())
    return {"schema": "mira-genesis-v30-bottleneck-adjudication-v1", "v30_l8_positive": positive,
        "verdict": "POSITIVE_BOUNDED_L8" if positive else "VALID_NEGATIVE_TARGET_SELECTION",
        "predicates": predicates, "arm_utilities": utilities, "target_counts": selections,
        "meta_utilities": {name: arm["utility"] for name, arm in arms.items()},
        "selected_flags": selected["flags"], "selected_source_sha256": record["selected_source_sha256"],
        "freeze_sha256": frozen["freeze_sha256"], "new_holdout_consumed": record["fresh_consumed"],
        "fresh_context_count": len(fresh_bank.CONTEXTS) if record["fresh_consumed"] else 0,
        "scope": "FINITE_MEASURED_BOTTLENECK_SELECTION_ON_FAULTED_DISPOSABLE_PIPELINE_COPIES",
        "independent_task_authorship": False, "open_ended_self_modification": False,
        "retention": keep}


def run():
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if frozen["python_version"] != sys.version.split()[0]:
        raise ValueError("Canonical Python version differs from freeze")
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    record = {"status": "STARTED", "canonical_attempts": 1, "track": "A", "scientific_external_model_calls": 0,
              "freeze_sha256": frozen["freeze_sha256"], "python_version": frozen["python_version"],
              "fresh_consumed": False, "arms": {}}
    with os.fdopen(descriptor, "w") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        measured = public_calibration(replay=True)
        record["meta"] = meta.pilot(measured, isolated=True)
        selected = record["meta"]["arms"]["inherited_g6"]["selected"]
        successor = family.render(selected["flags"])
        record["selected_source_sha256"] = digest_bytes(successor.encode())
        SELECTED.write_text(successor)
        record["retention"] = retention(successor, replay=True)
        write_json(ATTEMPT, record)
        if selected["qualified_discovery"] and tuple(record["meta"]["arms"]["inherited_g6"]["utility"]) > tuple(
                record["meta"]["arms"]["g6_scheduling_ablation"]["utility"]) and record["retention"]["no_loss"]:
            record["fresh_consumed"] = True
            write_json(ATTEMPT, record)
            cache = {}
            def evaluated(context, target):
                key = digest([context, source(context, target)])
                if key not in cache:
                    cache[key] = episode(context, target, isolated=True)
                return cache[key]
            # All arms share this measured probe. Its complete cost is charged to each arm.
            probes = [evaluated(context, "identity") for context in fresh_bank.CONTEXTS]
            record["probes"] = probes
            write_json(ATTEMPT, record)
            for arm, controller in policies(selected["flags"]).items():
                record["arms"][arm] = []
                for context, baseline in zip(fresh_bank.CONTEXTS, probes):
                    observed = diagnostics(baseline, GraphHost(context["spec"]))
                    target = meta.select(controller, observed, isolated=True)
                    record["arms"][arm].append({"context": context, "context_sha256": digest(context),
                        "baseline": baseline, "diagnostics": observed, "target": target,
                        "target_call": {"controller_sha256": digest_bytes(controller.encode()),
                                        "payload_sha256": digest({"diagnostics": observed, "targets": TARGETS}),
                                        "represented_calls": 1, "isolated_policy_process": True},
                        "post": evaluated(context, target)})
                    write_json(ATTEMPT, record)
                print("Preserved target arm: " + arm, flush=True)
        record["status"] = "COMPLETED"
        preserve(record)
        result = adjudicate(record, frozen, replay=False)
        write_json(VERDICT, result)
        print(json.dumps(result, indent=2), flush=True)
        return result
    except BaseException as error:
        record["status"] = "INSTRUMENT_ABORTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        preserve(record)
        write_json(VERDICT, {"v30_l8_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT", "freeze_sha256": frozen["freeze_sha256"]})
        raise


def check(require_result=False):
    if not freeze.PATH.exists():
        if ATTEMPT.exists() or require_result:
            raise ValueError("V30 evidence has no freeze")
        return {"v30_l8_positive": False, "status": "APPARATUS_PREPARATION"}
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if not ATTEMPT.exists():
        if require_result:
            raise ValueError("Missing canonical V30 evidence")
        return {"v30_l8_positive": False, "status": "PREREGISTERED_UNCONSUMED"}
    for path in (ATTEMPT, RAW, VERDICT):
        if freeze.git("show", "HEAD:" + path.relative_to(ROOT).as_posix()) != path.read_bytes():
            raise ValueError("V30 evidence is not committed exactly")
    record, verdict = read_attempt(), json.loads(VERDICT.read_text())
    expected = ({"v30_l8_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT", "freeze_sha256": frozen["freeze_sha256"]}
                if record["status"] == "INSTRUMENT_ABORTED" else adjudicate(record, frozen))
    if record["status"] == "COMPLETED" and (SELECTED.read_text() != family.render(record["meta"]["arms"]["inherited_g6"]["selected"]["flags"])
            or freeze.git("show", "HEAD:" + SELECTED.relative_to(ROOT).as_posix()) != SELECTED.read_bytes()):
        raise ValueError("Selected G7 source differs from the lineage's committed choice")
    if digest(verdict) != digest(expected):
        raise ValueError("V30 verdict disagrees with raw replay")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-result", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.require_result), indent=2)) if args.check else run()
