"""Recompute a repair lineage's decisions and totals from its stored records.

    python scripts/audit_repair_lineage.py --name LINEAGE1 [--trial L1]

This checks the stored evidence against itself: seals, the chain of genome digests, every
promotion decision, the envelope on every case and the held-out summary. It reruns nothing, so
it is not an independent replication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.repair_lineage import checked_genome, exact_sign_test, genome_digest, promotes  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

BENCH = ROOT / "experiment/bench"


def sealed(path: Path, key: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    body = {name: value for name, value in record.items() if name != key}
    if record.get(key) != digest_of(body):
        raise AssertionError(f"{path.name}: {key} does not match its content")
    return record


def within_envelope(case: dict, envelope: dict) -> bool:
    return (case["validated"] <= envelope["validations_per_case"]
            and len(case["calls"]) <= envelope["model_requests_per_case"])


def audit_lineage(folder: Path) -> dict:
    plan = sealed(folder / "PLAN.json", "plan_digest")
    lineage = sealed(folder / "LINEAGE.json", "lineage_digest")
    replicates, margin = plan.get("replicates", 1), plan.get("promotion_margin", 1)

    def runs(names: list[str]) -> list[str]:
        return list(names) if replicates == 1 else [f"{n}#{r}" for r in range(1, replicates + 1) for n in names]

    cases, selection = runs(plan["training_cases"] + plan["selection_cases"]), runs(plan["selection_cases"])
    assert lineage["plan_digest"] == plan["plan_digest"]
    assert genome_digest(plan["seed_genome"]) == plan["seed_genome_digest"] == lineage["seed_genome_digest"]
    assert not set(plan["training_cases"]) & set(plan["selection_cases"])
    current, current_generation = plan["seed_genome"], 0
    evaluations = {0: sealed(folder / "GEN0_EVALUATION.json", "evaluation_digest")}
    assert evaluations[0]["genome_digest"] == plan["seed_genome_digest"]
    decisions = []
    for entry in lineage["generations"]:
        assert entry["parent_generation"] == current_generation
        assert entry["parent_digest"] == genome_digest(current)
        if entry["decision"] in ("promoted", "rejected"):
            child = checked_genome(entry["genome"])
            evaluation = sealed(folder / f"GEN{entry['generation']}_EVALUATION.json", "evaluation_digest")
            assert evaluation["genome_digest"] == genome_digest(child) == entry["genome_digest"]
            assert sorted(evaluation["cases"]) == sorted(cases)
            assert all(within_envelope(case, plan["envelope"]) for case in evaluation["cases"].values())
            assert evaluation["solved"] == sum(case["solved"] for case in evaluation["cases"].values())
            expected = promotes(evaluation, evaluations[current_generation], selection, margin)
            assert (entry["decision"] == "promoted") == expected
            evaluations[entry["generation"]] = evaluation
            if expected:
                current, current_generation = child, entry["generation"]
        decisions.append((entry["generation"], entry["decision"]))
    assert current_generation == lineage["final_generation"]
    assert genome_digest(current) == lineage["final_genome_digest"] == genome_digest(lineage["final_genome"])
    return {
        "development_case_runs": len(cases), "decisions": decisions, "final_generation": current_generation,
        "solved_per_evaluated_generation": {number: record["solved"] for number, record in evaluations.items()},
        "development_cost_usd": round(sum(record["cost_usd"] for record in evaluations.values()), 6),
    }


def audit_trial(folder: Path, trial: str) -> dict:
    plan = sealed(folder / "PLAN.json", "plan_digest")
    lineage = sealed(folder / "LINEAGE.json", "lineage_digest")
    prereg = sealed(BENCH / f"TRIAL_{trial}_PREREG.json", "preregistration_digest")
    result = sealed(BENCH / f"TRIAL_{trial}_RESULT.json", "result_digest")
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert prereg["arms"] == {"seed": plan["seed_genome_digest"], "final": lineage["final_genome_digest"]}
    assert [case["case"] for case in result["cases"]] == prereg["cases"]
    development = set(plan["training_cases"] + plan["selection_cases"])
    assert not development & set(prereg["cases"])
    usable = [case for case in result["cases"] if case["usable"]]
    table = {"both": 0, "seed_only": 0, "final_only": 0, "neither": 0}
    for case in usable:
        assert all(within_envelope(arm, prereg["envelope"]) for arm in case["arms"].values())
        seed, final = case["arms"]["seed"]["solved"], case["arms"]["final"]["solved"]
        table["both" if seed and final else "seed_only" if seed else "final_only" if final else "neither"] += 1
    summary = result["summary"]
    assert summary["paired"] == table and summary["usable_cases"] == len(usable)
    assert summary["solved"] == {"seed": table["both"] + table["seed_only"], "final": table["both"] + table["final_only"]}
    assert summary["one_sided_exact_sign_test_p"] == round(exact_sign_test(table["seed_only"], table["final_only"]), 6)
    return {"usable_cases": len(usable), "paired": table, "solved": summary["solved"],
            "one_sided_exact_sign_test_p": summary["one_sided_exact_sign_test_p"], "cost_usd": summary["cost_usd"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True)
    parser.add_argument("--trial")
    arguments = parser.parse_args()
    folder = BENCH / arguments.name
    report = {"lineage": audit_lineage(folder)}
    if arguments.trial:
        report["trial"] = audit_trial(folder, arguments.trial)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
