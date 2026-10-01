"""Frozen cross-domain transfer of the byte-exact qualified L6 terminal policy."""
import argparse
import json
import os

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v25.search_engine import global_utility
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v28 import campaign as v28, family
from experiment.rsi_v29 import freeze, native_bank

ATTEMPT = ROOT / "results/rsi-v29/transfer-20261001/V29_ATTEMPT.json"
VERDICT = ATTEMPT.with_name("V29_FINAL_ADJUDICATION.json")


def policies():
    record = json.loads(v28.ATTEMPT.read_text())
    phases = record["chain"]["phases"]
    selected = phases[-1]
    result = {"g3": family.render(family.ROOT_PARAMS)}
    for i, phase in enumerate(phases):
        result["g" + str(i + 4)] = family.render_genotype(phase["selected_genotype"])
    for axis in family.components(selected["selected_params"]):
        result["ablation_" + axis] = family.render_genotype(family.genotype(
            {**selected["selected_params"], axis: 0}, selected["selected_genotype"]["layout"]))
    if result["g6"] != (v28.ATTEMPT.parent / "G6_SELECTED_POLICY.py").read_text():
        raise ValueError("Terminal L6 source identity changed")
    return result


def passed_results(task, observed):
    if len(observed) != len(task["cases"]):
        raise ValueError("Incomplete case results")
    import zlib
    rows = []
    for case, output in zip(task["cases"], observed):
        if type(output) is not dict or type(output.get("ok")) is not bool or set(output) != (
                {"ok", "value"} if output["ok"] else {"ok", "error"}):
            raise ValueError("Malformed native output")
        value = output.get("value")
        if task["domain"] == "binary-compression" and case["operation"] == "c" and output.get("ok"):
            try:
                value = zlib.decompress(bytes.fromhex(value)).hex()
            except (ValueError, zlib.error):
                value = None
        rows.append(bool(output.get("ok")) and value == case["expected"])
    return rows


def verify_receipt(receipt, task, choices):
    passed = passed_results(task, receipt["observed"])
    if (receipt["receipt_sha256"] != digest({k: v for k, v in receipt.items() if k != "receipt_sha256"})
            or receipt["source_sha256"] != digest_bytes(native_bank.render(task["domain"], choices).encode())
            or receipt["task_sha256"] != digest(task) or receipt["runtime_kernel"] != task["domain"]
            or receipt["native_source_executed"] is not True or receipt["accepted"] is not True
            or receipt["passed"] != passed or type(receipt["quality_milli"]) is not int
            or receipt["quality_milli"] != sum(passed) * 1000 // len(passed)):
        raise ValueError("Altered native evaluator receipt")


def verify_search(search, task, source, seeded):
    receipts = {}
    for key, node in search["nodes"].items():
        if key == "root":
            continue
        verify_receipt(node["evaluation"], task, node["candidate"]["choices"])
        if node["source_sha256"] in receipts:
            raise ValueError("Duplicate native proposal")
        receipts[node["source_sha256"]] = node["evaluation"]
    class ReceiptHost(native_bank.Host):
        def evaluate(self, row):
            if row["source_sha256"] not in receipts:
                raise ValueError("Replay requests an unobserved native proposal")
            return receipts[row["source_sha256"]]
    replay = run_search(source, ReceiptHost(task, seeded), caps=native_bank.CAPS, isolated=True)
    if digest(replay) != digest(search):
        raise ValueError("Native choices, source, lineage, or budgets changed")


def adjudicate(record, frozen, *, replay=True):
    if record["status"] != "COMPLETED":
        raise ValueError("Incomplete V29 attempt")
    expected = policies()
    if set(record["arms"]) != set(expected):
        raise ValueError("Omitted cross-domain control")
    native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
    roots = {r["domain"]: r["seeded"] for r in native["tasks"]}
    if native["population_sha256"] != digest(native_bank.TASKS) or native["controller_executed"]:
        raise ValueError("Native bank was changed or used for selection")
    for task, prepared in zip(native_bank.TASKS, native["tasks"]):
        verify_receipt(prepared["reference"], task, (0, 0, 0))
        verify_receipt(prepared["seeded"], task, (1, 1, 1))
    utilities = {}
    for arm, source in expected.items():
        rows = record["arms"][arm]
        if [r["domain"] for r in rows] != list(native_bank.DOMAINS):
            raise ValueError("Omitted or reordered native domain")
        for task, row in zip(native_bank.TASKS, rows):
            if replay:
                verify_search(row["search"], task, source, roots[task["domain"]])
        utilities[arm] = [global_utility([row["search"]]) for row in rows]
    predicates = {"qualified_l6_lineage_preserved": frozen["previous_l6"]["v28_l6_positive"],
        "four_actual_external_algorithmic_domains": len(native_bank.DOMAINS) == 4 and set(native_bank.DOMAINS) == set(frozen["domains"]),
        "unchanged_terminal_policy": frozen["terminal_policy_sha256"] == digest_bytes(expected["g6"].encode()),
        "strict_transfer_above_g3_in_every_domain": all(a > b for a, b in zip(utilities["g6"], utilities["g3"])),
        "strict_ordering_ablation_in_every_domain": all(a > b for a, b in zip(utilities["g6"], utilities["ablation_ordering"])),
        "exact_freeze_and_single_attempt": record["freeze_sha256"] == frozen["freeze_sha256"]
            and record["canonical_attempts"] == 1 and record["track"] == "A"
            and record["scientific_external_model_calls"] == 0 and record["runtime_versions"] == frozen["runtime_versions"]}
    positive = all(predicates.values())
    return {"schema": "mira-genesis-v29-cross-domain-adjudication-v1", "v29_l7_positive": positive,
        "verdict": "POSITIVE_BOUNDED_L7" if positive else "VALID_NEGATIVE_FRESH_TRANSFER",
        "predicates": predicates, "domain_utilities": utilities, "domains": native_bank.DOMAINS,
        "freeze_sha256": frozen["freeze_sha256"], "new_holdout_consumed": True,
        "scope": "UNCHANGED_L6_PIPELINE_ON_FOUR_PROJECT_AUTHORED_NATIVE_ALGORITHMIC_TASKS",
        "independent_environment_maintenance": True, "independent_task_authorship": False,
        "descriptive_ablation_ties_preserved": True}


def run():
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if frozen["runtime_versions"] != native_bank.runtime_versions():
        raise ValueError("Canonical native runtime differs from freeze")
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    record = {"status": "STARTED", "canonical_attempts": 1, "track": "A", "scientific_external_model_calls": 0,
              "freeze_sha256": frozen["freeze_sha256"], "runtime_versions": frozen["runtime_versions"], "arms": {}}
    with os.fdopen(descriptor, "w") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
        roots, cache = {r["domain"]: r["seeded"] for r in native["tasks"]}, {}
        class CachedHost(native_bank.Host):
            def evaluate(self, row):
                key = digest([self.task, row["candidate"]])
                if key not in cache:
                    cache[key] = super().evaluate(row)
                return cache[key]
        for arm, source in policies().items():
            record["arms"][arm] = []
            for task in native_bank.TASKS:
                search = run_search(source, CachedHost(task, roots[task["domain"]]), caps=native_bank.CAPS, isolated=True)
                record["arms"][arm].append({"domain": task["domain"], "search": search})
                write_json(ATTEMPT, record)
            print("Preserved native arm: " + arm, flush=True)
        record["status"] = "COMPLETED"
        write_json(ATTEMPT, record)
        result = adjudicate(record, frozen, replay=False)
        write_json(VERDICT, result)
        print(json.dumps(result, indent=2), flush=True)
        return result
    except BaseException as error:
        record["status"] = "INSTRUMENT_ABORTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        write_json(ATTEMPT, record)
        write_json(VERDICT, {"v29_l7_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT", "freeze_sha256": frozen["freeze_sha256"]})
        raise


def check(require_result=False):
    if not freeze.PATH.exists():
        if ATTEMPT.exists() or require_result:
            raise ValueError("V29 evidence has no freeze")
        return {"v29_l7_positive": False, "status": "APPARATUS_PREPARATION"}
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if not ATTEMPT.exists():
        if require_result:
            raise ValueError("Missing canonical V29 evidence")
        return {"v29_l7_positive": False, "status": "PREREGISTERED_UNCONSUMED"}
    for path in (ATTEMPT, VERDICT):
        if freeze.git("show", "HEAD:" + path.relative_to(ROOT).as_posix()) != path.read_bytes():
            raise ValueError("V29 evidence is not committed exactly")
    record, verdict = json.loads(ATTEMPT.read_text()), json.loads(VERDICT.read_text())
    expected = ({"v29_l7_positive": False, "verdict": "PRESERVED_INSTRUMENT_ABORT", "freeze_sha256": frozen["freeze_sha256"]}
                if record["status"] == "INSTRUMENT_ABORTED" else adjudicate(record, frozen))
    if digest(verdict) != digest(expected):
        raise ValueError("V29 verdict disagrees with raw replay")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-result", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.require_result), indent=2)) if args.check else run()
