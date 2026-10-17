"""Independent read-only integrity and arithmetic audit of frozen CIRCUIT2.

Does not run the experiment, inspect secret banks, mutate saved results,
replace an independent evaluator, or promote any scientific hypothesis.
The authenticated historical machinery bytes use the project's actual
digest_of(bytes.hex()) convention, not bare sha256(file_bytes).
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from genesis.trust_root import digest_of


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seal_valid(record: dict, field: str) -> bool:
    actual = record.get(field)
    return isinstance(actual, str) and actual == digest_of({key: val for key, val in record.items() if key != field})


def _mean(values: list) -> float:
    require(bool(values), "empty population")
    return sum(values) / len(values)


def _rounded_close(actual: float, stated: float, *, tol: float = .0011) -> bool:
    return math.isfinite(actual) and math.isfinite(stated) and abs(actual - stated) <= tol


def _one_sided_sign_p(wins: int, losses: int) -> float:
    n = wins + losses
    require(n > 0, "no non-tied pairs")
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / (2**n)


def _compare_pair(left: list, right: list, saved: dict, label: str) -> dict:
    require(len(left) == len(right) and len(left) > 0, f"{label}: mismatched pair count")
    delta = [a - b for a, b in zip(left, right)]
    wins = sum(value > 0 for value in delta)
    losses = sum(value < 0 for value in delta)
    require(saved.get("wins") == wins and saved.get("losses") == losses, f"{label}: sign tally mismatch")
    require(_rounded_close(_mean(delta), saved["mean_difference"]), f"{label}: mean delta mismatch")
    require(_rounded_close(_one_sided_sign_p(wins, losses), saved["one_sided_sign_test_p"]), f"{label}: p-value mismatch")
    return {"wins": wins, "losses": losses, "ties": len(delta) - wins - losses}


def verify(plan: dict, result: dict, *, root: Path = ROOT) -> dict:
    require(plan.get("schema") == "genesis-circuit-meta-plan-v1", "wrong plan schema")
    require(result.get("schema") == "genesis-circuit-meta-result-v1", "wrong result schema")
    require(plan.get("name") == result.get("name") == "CIRCUIT2", "wrong experiment name")
    require(_seal_valid(plan, "plan_digest"), "plan digest mismatch")
    require(_seal_valid(result, "result_digest"), "result digest mismatch")
    require(plan["plan_digest"] == result["plan_digest"], "result not linked to plan")
    commit = plan.get("machinery_commit")
    require(isinstance(commit, str) and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit),
            "invalid historical commit reference")
    files = plan.get("machinery_digests")
    require(isinstance(files, Mapping) and len(files) > 0, "missing machine provenance")
    for name, expected in files.items():
        require(isinstance(name, str) and ".." not in name and not name.startswith("/"), "invalid machinery path")
        try:
            original = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{commit}:{name}"], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:
            raise EvidenceError(f"unreachable historical code: {name}") from exc
        require(digest_of(original.hex()) == expected, f"machinery digest mismatch: {name}")
    seeds = plan.get("seeds")
    groups = plan.get("family_groups")
    require(isinstance(seeds, list) and len(seeds) > 0 and
            isinstance(groups, list) and len(groups) > 0, "empty experimental design")
    record = result["by_arm_and_group"]
    expected_arms = frozenset(("explore", "learned1", "learned2", "support"))
    require(frozenset(record) == expected_arms, "missing/unexpected experimental arms")
    flat: dict[str, dict[str, list]] = {}
    n_per_arm = len(seeds) * len(groups)
    for arm, rows in record.items():
        require(len(rows) == len(groups), f"{arm}: wrong family group count")
        flat[arm] = {}
        for metric in ("learning_gain", "held_out", "trials"):
            series = [value for row in rows for value in row[metric]]
            require(len(series) == n_per_arm, f"{arm}: wrong {metric} lineage count")
            require(all(isinstance(value, int) and not isinstance(value, bool) for value in series),
                    f"{arm}: malformed metric")
            flat[arm][metric] = series
            entry = result["H2"][{
                "learning_gain":"learning_gain_mean",
                "held_out":"held_out_mean", "trials":"trials_mean"
            }[metric]][arm]
            require(_rounded_close(_mean(series), entry), f"{arm}: {metric} mean mismatch")
    for arm in expected_arms:
        gain = _mean(flat[arm]["learning_gain"])
        trials = _mean(flat[arm]["trials"])
        require(trials > 0, f"{arm}: invalid trial denominator")
        require(_rounded_close(gain/trials, result["H2"]["gain_per_trial"][arm]),
                f"{arm}: per-trial gain mismatch")

    rankers = result.get("rankers")
    require(isinstance(rankers, dict) and len(rankers) == 6, "wrong ranker inventory")
    require(plan.get("ranker", "").startswith("ridge regression (penalty 1)"),
            "unexpected declared ranking method")
    for name, ranker in rankers.items():
        require(name in {"learned10", "learned11", "learned12",
                         "learned20", "learned21", "learned22"},
                f"unrecognized ranker {name}")
        groups_used = ranker.get("fitted_on_groups")
        require(isinstance(groups_used, list) and
                len(groups_used) == (1 if name.startswith("learned1") else 2) and
                all(isinstance(value, int) and 0 <= value < len(groups) for value in groups_used) and
                len(set(groups_used)) == len(groups_used),
                f"{name}: wrong train family groups")
        weights = ranker.get("weights")
        require(isinstance(weights, list) and len(weights) == 13 and
                all(isinstance(value, (int,float)) and math.isfinite(value)
                    for value in weights), f"{name}: wrong 13-feature coefficients")
        auc = ranker.get("auc_on_target_explore_trials")
        require(isinstance(auc, (int,float)) and 0 <= auc <= 1,
                f"{name}: invalid AUC")
        require(isinstance(ranker.get("trials"), int) and ranker["trials"] > 0,
                f"{name}: invalid training trial count")

    stats = {}
    for field, leftarm, rightarm, metric in (
        ("learned2_against_explore", "learned2", "explore", "learning_gain"),
        ("learned2_against_learned1", "learned2", "learned1", "learning_gain"),
        ("learned2_against_support", "learned2", "support", "learning_gain"),
        ("held_out_learned2_against_explore", "learned2", "explore", "held_out"),
    ):
        stats[field] = _compare_pair(
            flat[leftarm][metric], flat[rightarm][metric], result["H2"][field], field
        )
    h1 = result["H1"]
    baseline = plan["reference_circuit1"]["held_out_by_seed"]
    open_ = h1["open_held_out"]
    require(len(open_) == len(baseline), "H1 paired lengths differ")
    stats["H1"] = _compare_pair(open_, baseline, h1["paired"], "H1")
    require(len(open_) <= len(seeds), "H1 more observations than declared seeds")
    lineage_count = len(open_) + len(record) * n_per_arm
    require(lineage_count == 125, f"unexpected frozen lineage count {lineage_count}")
    return {
        "status": "REPRODUCIBLE_RECORD_AUDIT_ONLY",
        "plan_digest": plan["plan_digest"],
        "result_digest": result["result_digest"],
        "historical_machinery_files_checked": len(files),
        "H1_lineages": len(open_),
        "H2_lineages": len(record) * n_per_arm,
        "rankers_verified": len(rankers),
        "features_per_ranker": 13,
        "total_lineages": lineage_count,
        "paired_checks": stats,
        "warning": "Integrity of records and arithmetic does not validate generality, independence or causal RSI",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    plan = read_json(args.root / "experiment/engine/CIRCUIT2/PLAN.json")
    result = read_json(args.root / "experiment/engine/CIRCUIT2/RESULT.json")
    try:
        summary = verify(plan, result, root=args.root)
    except (EvidenceError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL CIRCUIT2 frozen evidence: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
