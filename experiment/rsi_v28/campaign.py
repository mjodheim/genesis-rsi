"""Single V28 attempt, automatic lineage, and independent receipt replay."""
import argparse
import json
import os
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v25.executable_family import predecessor_source
from experiment.rsi_v25.search_engine import global_utility
from experiment.rsi_v26 import native_bank
from experiment.rsi_v28 import family, freeze, fresh_bank, meta
from experiment.rsi_v28.calibration_archive import load
from experiment.rsi_v27.engine import run_search

ATTEMPT = ROOT / "results/rsi-v28/chain-20261001/V28_ATTEMPT.json"
VERDICT = ATTEMPT.with_name("V28_FINAL_ADJUDICATION.json")


def bootstrap(calibration):
    host = meta.Host(calibration, family.ROOT_PARAMS, 0)
    search = run_search(predecessor_source(), host, isolated=True)
    selected = meta.choose(search, host)
    return {"source_sha256": digest_bytes(predecessor_source().encode()),
            "utility": meta.utility(selected, search, 0), "search": search}


def causal_gates(chain, comparison):
    phases = chain["phases"]
    gates = {"three_automatic_discoveries": len(phases) == 3 and all(
        p["qualified_discovery"] for p in phases),
        "strict_bootstrap_causality": bool(phases) and tuple(phases[0]["utility"]) > tuple(comparison["utility"])}
    for stage in (1, 2):
        passed = False
        if len(phases) > stage:
            previous, current = phases[stage - 1], phases[stage]
            axes = family.components(previous["selected_params"], previous["parent_params"])
            controls = {row["component"]: row for row in current["controls"]}
            passed = len(axes) == 1 and axes[0] in controls and tuple(current["utility"]) > tuple(
                controls[axes[0]]["utility"])
        gates["strict_causal_transition_" + str(stage + 1)] = passed
    return gates


def policies(phase):
    candidate = phase["selected_genotype"]
    selected = family.render_genotype(candidate)
    result = {"successor": selected, "parent": family.render(phase["parent_params"])}
    result.update({"ablation_" + axis: family.render_genotype(
        family.genotype({**phase["selected_params"], axis: 0}, candidate["layout"]))
        for axis in family.components(phase["selected_params"])})
    return result


def transfer_key(source, spec):
    return digest([digest_bytes(source.encode()), digest(spec)])


def verify_graph(search, source, spec):
    host = fresh_bank.Host(spec)
    receipts = {}
    for key, node in search["nodes"].items():
        if key == "root":
            continue
        expected = host.evaluate(host.rows[node["candidate"]["token"]])
        if node["evaluation"] != expected or node["source_sha256"] in receipts:
            raise ValueError("Altered graph evaluator receipt")
        receipts[node["source_sha256"]] = expected

    class ReceiptHost(fresh_bank.Host):
        def evaluate(self, row):
            if row["source_sha256"] not in receipts:
                raise ValueError("Graph replay requests an unobserved proposal")
            return receipts[row["source_sha256"]]

    replay = run_search(source, ReceiptHost(spec), caps=fresh_bank.CAPS, isolated=True)
    if digest(replay) != digest(search):
        raise ValueError("Altered graph trace, choice, source, or budget")


def native_roots():
    return {r["task_id"]: r["seeded"] for r in json.loads(
        (native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())["tasks"]}


def verify_native(search, source, task, seeded):
    receipts = {}
    for key, node in search["nodes"].items():
        if key == "root":
            continue
        receipt, choices = node["evaluation"], node["candidate"]["choices"]
        cases = receipt["cases"]
        if (receipt["source_sha256"] != digest_bytes(native_bank.render(task, choices).encode())
                or receipt["task_sha256"] != digest(task)
                or receipt["harness_sha256"] != digest_bytes((native_bank.HERE / "native_harnesses" / task["harness"]).read_bytes())
                or not receipt["native_source_executed"] or receipt["cases_sha256"] != digest(cases)
                or type(cases["passed"]) is not int or type(cases["total"]) is not int
                or not 0 <= cases["passed"] <= cases["total"] or cases["total"] <= 0
                or len(cases["failed"]) != cases["total"] - cases["passed"]
                or receipt["quality_milli"] != cases["passed"] * 1000 // cases["total"]
                or node["source_sha256"] in receipts):
            raise ValueError("Altered consumed native retention receipt")
        receipts[node["source_sha256"]] = receipt

    class ReceiptHost(native_bank.Host):
        def evaluate(self, row):
            if row["source_sha256"] not in receipts:
                raise ValueError("Native replay requests an unobserved proposal")
            return receipts[row["source_sha256"]]

    replay = run_search(source, ReceiptHost(task, seeded), caps=native_bank.CAPS, isolated=True)
    if digest(replay) != digest(search):
        raise ValueError("Altered native retention trace, choice, source, or budget")


def adjudicate(record, frozen, *, replay=True):
    if record["status"] != "COMPLETED":
        raise ValueError("An incomplete attempt cannot be adjudicated")
    calibration = load()
    if replay:
        if digest(record["chain"]) != digest(meta.pilot(calibration, isolated=True)):
            raise ValueError("Canonical lineage differs from automatic public replay")
        if digest(record["bootstrap"]) != digest(bootstrap(calibration)):
            raise ValueError("Canonical bootstrap differs from matched replay")
    gates = causal_gates(record["chain"], record["bootstrap"])
    phases, roots = record["chain"]["phases"], native_roots()
    expected_native = {"G" + str(i + 4) for i in range(len(phases))}
    if set(record["native_retention"]) != expected_native:
        raise ValueError("Native retention omitted a generation")
    native_ok = True
    for i, phase in enumerate(phases):
        rows = record["native_retention"]["G" + str(i + 4)]
        if [r["task_id"] for r in rows] != [t["task_id"] for t in native_bank.TASKS]:
            raise ValueError("Native retention task set changed")
        for task, row in zip(native_bank.TASKS, rows):
            search = row["search"]
            if replay:
                verify_native(search, family.render_genotype(phase["selected_genotype"]), task, roots[task["task_id"]])
            native_ok &= search["best_quality_milli"] == 1000
    gates["all_prior_native_capabilities_retained"] = native_ok
    gates["exact_frozen_identity_and_single_attempt"] = (
        record["freeze_sha256"] == frozen["freeze_sha256"] and record["track"] == "A"
        and record["scientific_external_model_calls"] == 0 and record["canonical_attempts"] == 1
        and record["python_version"] == frozen["python_version"])
    utilities, expected_keys = [], set()
    pre_gates = all(gates.values())
    if record["transfer"] and not pre_gates:
        raise ValueError("Fresh bank consumed with failed pre-gates")
    for stage, phase in enumerate(phases):
        if not record["transfer"]:
            gates["strict_fresh_transition_" + str(stage + 1)] = False
            continue
        arms = {}
        for arm, source in policies(phase).items():
            episodes = []
            for spec in fresh_bank.cumulative(stage):
                key = transfer_key(source, spec)
                expected_keys.add(key)
                if key not in record["transfer"]:
                    raise ValueError("Omitted fresh comparator or task")
                row = record["transfer"][key]
                if row["policy_sha256"] != digest_bytes(source.encode()) or row["task_sha256"] != digest(spec):
                    raise ValueError("Altered fresh source/task identity")
                if replay:
                    verify_graph(row["search"], source, spec)
                episodes.append(row["search"])
            arms[arm] = episodes
        values = {arm: global_utility(rows) for arm, rows in arms.items()}
        active = {arm: global_utility(rows[-len(fresh_bank.BANKS[stage]):]) for arm, rows in arms.items()}
        retention = all(old["best_quality_milli"] != 1000 or new["best_quality_milli"] == 1000
                        for old, new in zip(arms["parent"], arms["successor"]))
        gates["strict_fresh_transition_" + str(stage + 1)] = (
            values["successor"] > values["parent"] and active["successor"] > active["parent"]
            and all(values["successor"] > value for arm, value in values.items() if arm.startswith("ablation_"))
            and retention)
        utilities.append({"stage": stage, "cumulative": values, "active_partition": active,
                          "previous_solved_capabilities_retained": retention})
    if set(record["transfer"]) != expected_keys:
        raise ValueError("Unexpected or duplicated fresh source/task evaluation")
    positive = all(gates.values())
    return {"schema": "mira-genesis-v28-repeated-descent-adjudication-v1", "v28_l6_positive": positive,
            "verdict": "POSITIVE_BOUNDED_L6" if positive else "VALID_NEGATIVE_FRESH_TRANSFER" if record["transfer"] else "NEGATIVE_PRE_TRANSFER",
            "predicates": gates, "fresh_utilities": utilities,
            "meta_utilities": [p["utility"] for p in phases], "bootstrap_utility": record["bootstrap"]["utility"],
            "freeze_sha256": frozen["freeze_sha256"], "new_holdout_consumed": bool(record["transfer"]),
            "scope": "THREE_AUTOMATIC_CAUSAL_TRANSITIONS_ON_FINITE_PROJECT_AUTHORED_REPRESENTED_TASKS",
            "older_ablation_ties_are_preserved": True, "fresh_native_transfer": False}


def run():
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if frozen["python_version"] != sys.version.split()[0]:
        raise ValueError("Canonical Python version differs from freeze")
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    record = {"status": "STARTED", "canonical_attempts": 1, "track": "A", "scientific_external_model_calls": 0,
              "python_version": frozen["python_version"], "freeze_sha256": frozen["freeze_sha256"],
              "native_retention": {}, "transfer": {}}
    with os.fdopen(descriptor, "w") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    def save():
        write_json(ATTEMPT, record)
    try:
        def checkpoint(phases):
            record["partial_chain"] = phases
            save()
        calibration = load()
        record["chain"] = meta.pilot(calibration, isolated=True, checkpoint=checkpoint)
        record.pop("partial_chain", None)
        record["bootstrap"] = bootstrap(calibration)
        save()
        roots, cache = native_roots(), {}
        class ConsumedHost(native_bank.Host):
            def evaluate(self, row):
                key = digest([self.task, row["candidate"]])
                if key not in cache:
                    cache[key] = super().evaluate(row)
                return cache[key]
        for stage, phase in enumerate(record["chain"]["phases"]):
            name = "G" + str(stage + 4)
            record["native_retention"][name] = []
            for task in native_bank.TASKS:
                search = run_search(family.render_genotype(phase["selected_genotype"]),
                    ConsumedHost(task, roots[task["task_id"]]), caps=native_bank.CAPS, isolated=True)
                record["native_retention"][name].append({"task_id": task["task_id"], "search": search})
                save()
            print("Preserved consumed native retention: " + name, flush=True)
        gates = causal_gates(record["chain"], record["bootstrap"])
        native_ok = all(row["search"]["best_quality_milli"] == 1000 for rows in record["native_retention"].values() for row in rows)
        if all(gates.values()) and native_ok:
            record["status"] = "TRANSFER_STARTED"
            save()
            for stage, phase in enumerate(record["chain"]["phases"]):
                for source in policies(phase).values():
                    for spec in fresh_bank.cumulative(stage):
                        key = transfer_key(source, spec)
                        if key in record["transfer"]:
                            continue
                        search = run_search(source, fresh_bank.Host(spec), caps=fresh_bank.CAPS, isolated=True)
                        record["transfer"][key] = {"policy_sha256": digest_bytes(source.encode()),
                                                   "task_sha256": digest(spec), "search": search}
                        save()
                print("Preserved new represented partition: " + str(stage + 1), flush=True)
        record["status"] = "COMPLETED"
        save()
        result = adjudicate(record, frozen, replay=False)
        write_json(VERDICT, result)
        for stage, phase in enumerate(record["chain"]["phases"]):
            (ATTEMPT.parent / ("G" + str(stage + 4) + "_SELECTED_POLICY.py")).write_text(
                family.render_genotype(phase["selected_genotype"]))
        print(json.dumps(result, indent=2), flush=True)
        return result
    except BaseException as error:
        record["status"] = "INSTRUMENT_ABORTED"
        record["instrument_error"] = {"type": type(error).__name__, "message": str(error)}
        save()
        write_json(VERDICT, {"v28_l6_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT",
                             "freeze_sha256": frozen["freeze_sha256"]})
        raise


def check(require_result=False):
    if not freeze.PATH.exists():
        if ATTEMPT.exists() or require_result:
            raise ValueError("Scientific evidence has no freeze")
        return {"v28_l6_positive": False, "status": "APPARATUS_PREPARATION"}
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if not ATTEMPT.exists():
        if require_result:
            raise ValueError("Missing canonical V28 evidence")
        return {"v28_l6_positive": False, "status": "PREREGISTERED_UNCONSUMED"}
    for path in (ATTEMPT, VERDICT):
        if freeze.git("show", "HEAD:" + path.relative_to(ROOT).as_posix()) != path.read_bytes():
            raise ValueError("Canonical evidence is not committed exactly")
    record, verdict = json.loads(ATTEMPT.read_text()), json.loads(VERDICT.read_text())
    if record["status"] == "COMPLETED":
        for stage, phase in enumerate(record["chain"]["phases"]):
            path = ATTEMPT.parent / ("G" + str(stage + 4) + "_SELECTED_POLICY.py")
            if path.read_text() != family.render_genotype(phase["selected_genotype"]) or freeze.git(
                    "show", "HEAD:" + path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise ValueError("Selected source or its committed identity changed")
    if record["status"] == "INSTRUMENT_ABORTED":
        expected = {"v28_l6_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT", "freeze_sha256": frozen["freeze_sha256"]}
    else:
        expected = adjudicate(record, frozen)
    if digest(verdict) != digest(expected):
        raise ValueError("Verdict disagrees with retained evidence")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-result", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.require_result), indent=2))
    else:
        run()
