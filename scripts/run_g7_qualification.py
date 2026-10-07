"""Execute the prospectively frozen Genesis G7 promotion/rollback qualification.

This program is the external authority/evaluator. Mutable lineage code only
receives content-addressed decision or rollback records after this program has
measured candidates under the frozen rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
from typing import Any, Mapping

from genesis.evolution import lineage_promotion
from genesis.trust_root import digest_of

RESULT_SCHEMA = "genesis-g7-qualification-result-v1"
MEASUREMENT_SCHEMA = "genesis-g7-component-measurement-v1"


def _load_module(source: str, name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = f"<{name}>"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _case_set_digest(round_record: Mapping[str, Any]) -> str:
    payload = {
        "round_id": round_record["round_id"],
        "cases": [
            {
                "id": case["id"],
                "program_sha256": hashlib.sha256(
                    str(case["files"]["Program.py"]).encode("utf-8")
                ).hexdigest(),
            }
            for case in round_record["cases"]
        ],
    }
    return digest_of(payload)


def _run_python(root: Path) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "Program.py"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "wall_time_seconds": round(time.monotonic() - started, 6),
        "stdout_tail": completed.stdout[-800:],
        "stderr_tail": completed.stderr[-800:],
    }


def _evaluate(
    artifact: Mapping[str, Any],
    round_record: Mapping[str, Any],
    *,
    operator: Mapping[str, Any],
    evaluator_digest: str,
    candidate_budget: int,
) -> dict[str, Any]:
    held = lineage_promotion.validate_artifact(artifact)
    module = _load_module(
        str(held["source_utf8"]),
        "g7_eval_" + held["artifact_digest"][:12],
    )
    cases: list[dict[str, Any]] = []
    executions = 0
    started = time.monotonic()

    for case in round_record["cases"]:
        program = str(case["files"]["Program.py"])
        outputs = module.materialize_source(
            program,
            path="Program.py",
            operator=operator,
            max_outputs=1,
        )
        if not outputs:
            cases.append(
                {
                    "case_id": case["id"],
                    "case_digest": digest_of(
                        {
                            "round_id": round_record["round_id"],
                            "case_id": case["id"],
                            "program_sha256": hashlib.sha256(
                                program.encode("utf-8")
                            ).hexdigest(),
                        }
                    ),
                    "passed": False,
                    "status": "no_candidate",
                    "candidate_executions": 0,
                }
            )
            continue
        if executions >= candidate_budget:
            cases.append(
                {
                    "case_id": case["id"],
                    "case_digest": digest_of(
                        {
                            "round_id": round_record["round_id"],
                            "case_id": case["id"],
                            "program_sha256": hashlib.sha256(
                                program.encode("utf-8")
                            ).hexdigest(),
                        }
                    ),
                    "passed": False,
                    "status": "budget_exhausted",
                    "candidate_executions": 0,
                }
            )
            continue
        with tempfile.TemporaryDirectory(prefix="genesis-g7-case-") as tmp:
            root = Path(tmp)
            (root / "Program.py").write_text(outputs[0], encoding="utf-8")
            evaluation = _run_python(root)
        executions += 1
        cases.append(
            {
                "case_id": case["id"],
                "case_digest": digest_of(
                    {
                        "round_id": round_record["round_id"],
                        "case_id": case["id"],
                        "program_sha256": hashlib.sha256(
                            program.encode("utf-8")
                        ).hexdigest(),
                    }
                ),
                "passed": evaluation["passed"],
                "status": "evaluated",
                "candidate_executions": 1,
                "evaluation": evaluation,
            }
        )

    payload = {
        "schema": MEASUREMENT_SCHEMA,
        "artifact_digest": held["artifact_digest"],
        "source_sha256": held["source_sha256"],
        "evaluator_digest": evaluator_digest,
        "case_set_digest": _case_set_digest(round_record),
        "round_id": round_record["round_id"],
        "candidate_budget": candidate_budget,
        "candidate_executions": executions,
        "within_candidate_budget": executions <= candidate_budget,
        "passed": sum(1 for case in cases if case["passed"]),
        "evaluated": len(cases),
        "passed_case_ids": sorted(case["case_id"] for case in cases if case["passed"]),
        "external_model_calls": 0,
        "wall_time_seconds": round(time.monotonic() - started, 6),
        "cases": cases,
    }
    return {**payload, "measurement_digest": digest_of(payload)}


def _validate_measurement(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = {k: v for k, v in record.items() if k != "measurement_digest"}
    if record.get("schema") != MEASUREMENT_SCHEMA:
        raise RuntimeError("unrecognized G7 measurement schema")
    if record.get("measurement_digest") != digest_of(payload):
        raise RuntimeError("G7 measurement digest does not reproduce")
    return dict(record)


def _authority_decision(
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
) -> str:
    p = _validate_measurement(parent)
    c = _validate_measurement(candidate)
    if p["evaluator_digest"] != c["evaluator_digest"]:
        raise RuntimeError("authority comparison uses different evaluators")
    if p["case_set_digest"] != c["case_set_digest"]:
        raise RuntimeError("authority comparison uses different case sets")
    if p["candidate_budget"] != c["candidate_budget"]:
        raise RuntimeError("authority comparison uses different budgets")

    parent_pass = set(p["passed_case_ids"])
    candidate_pass = set(c["passed_case_ids"])
    adopt = (
        c["passed"] > p["passed"]
        and parent_pass <= candidate_pass
        and p["within_candidate_budget"]
        and c["within_candidate_budget"]
        and p["external_model_calls"] == 0
        and c["external_model_calls"] == 0
    )
    expected = {
        "version": 1,
        "adopt_requires_strict_capability_gain": True,
        "adopt_requires_parent_success_preservation": True,
        "adopt_requires_matched_candidate_budget": True,
        "adopt_requires_zero_external_model_calls": True,
        "ties_or_regressions": "reject",
    }
    if dict(rule) != expected:
        raise RuntimeError("runtime authority rule differs from preregistration")
    return "adopt" if adopt else "reject"


def _baseline_round(round_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = []
    for case in round_record["cases"]:
        with tempfile.TemporaryDirectory(prefix="genesis-g7-baseline-") as tmp:
            root = Path(tmp)
            (root / "Program.py").write_text(
                str(case["files"]["Program.py"]),
                encoding="utf-8",
            )
            results.append({"case_id": case["id"], **_run_python(root)})
    return results


def _tamper_probes(store_root: Path, final_decision_digest: str) -> dict[str, bool]:
    results: dict[str, bool] = {}
    probes = ("artifact", "decision", "journal", "state")
    for probe in probes:
        with tempfile.TemporaryDirectory(prefix=f"g7-tamper-{probe}-") as tmp:
            clone = Path(tmp) / "lineage"
            shutil.copytree(store_root, clone)
            store = lineage_promotion.ComponentLineageStore.load(clone)
            if probe == "artifact":
                active = store.state["active_artifact_digest"]
                path = store.artifacts_dir / f"{active}.json"
                value = json.loads(path.read_text(encoding="utf-8"))
                value["source_utf8"] += "\n# tampered\n"
                path.write_text(json.dumps(value), encoding="utf-8")
            elif probe == "decision":
                path = store.decisions_dir / f"{final_decision_digest}.json"
                value = json.loads(path.read_text(encoding="utf-8"))
                value["case_set_digest"] = "tampered-case-set"
                path.write_text(json.dumps(value), encoding="utf-8")
            elif probe == "journal":
                path = store.journal_path
                value = json.loads(path.read_text(encoding="utf-8"))
                value["entries"][0]["payload"]["artifact_digest"] = "0" * 64
                path.write_text(json.dumps(value), encoding="utf-8")
            elif probe == "state":
                path = store.state_path
                value = json.loads(path.read_text(encoding="utf-8"))
                value["generation"] = int(value["generation"]) + 100
                path.write_text(json.dumps(value), encoding="utf-8")
            try:
                lineage_promotion.ComponentLineageStore.load(clone)
            except lineage_promotion.LineagePromotionError:
                results[probe] = True
            else:
                results[probe] = False
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repository_root.resolve()
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    holdout_bytes = args.holdout.read_bytes()
    holdout_sha = hashlib.sha256(holdout_bytes).hexdigest()
    if holdout_sha != prereg["holdout"]["sha256"]:
        raise SystemExit("G7 holdout SHA-256 differs from preregistration")
    holdout = json.loads(holdout_bytes)
    rounds = {item["round_id"]: item for item in holdout["rounds"]}
    if set(rounds) != {"A", "B", "C"}:
        raise SystemExit("G7 holdout does not contain the frozen rounds")
    if sum(len(item["cases"]) for item in rounds.values()) != prereg["holdout"]["case_count"]:
        raise SystemExit("G7 holdout case count differs from preregistration")

    candidate_payload = {
        k: v for k, v in candidates.items() if k != "candidate_set_digest"
    }
    if candidates.get("candidate_set_digest") != digest_of(candidate_payload):
        raise SystemExit("G7 candidate set digest does not reproduce")
    if candidates["candidate_set_digest"] != prereg["candidate_set_digest"]:
        raise SystemExit("G7 candidate set differs from preregistration")

    runner_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if runner_sha != prereg["external_evaluator"]["source_sha256"]:
        raise SystemExit("G7 external evaluator source differs from preregistration")
    apparatus_path = repo / prereg["lineage_apparatus"]["path"]
    if hashlib.sha256(apparatus_path.read_bytes()).hexdigest() != prereg[
        "lineage_apparatus"
    ]["source_sha256"]:
        raise SystemExit("G7 lineage apparatus differs from preregistration")

    operator = json.loads(
        (repo / "experiment/g5_qualification/PREREGISTRATION.json").read_text()
    )["source_capability"]["universal_operator"]

    baselines = {
        round_id: _baseline_round(round_record)
        for round_id, round_record in rounds.items()
    }
    baseline_all_fail = all(
        not item["passed"]
        for records in baselines.values()
        for item in records
    )

    seed = candidates["seed"]
    d1 = candidates["candidate_d1"]
    reversion = candidates["candidate_reversion"]
    d2 = candidates["candidate_d2"]

    if args.store_root.exists():
        shutil.rmtree(args.store_root)
    store = lineage_promotion.ComponentLineageStore.initialize(
        args.store_root,
        seed_artifact=seed,
    )

    checkpoints: list[dict[str, Any]] = []
    isolation: dict[str, bool] = {}
    measurements: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}

    def restart(label: str) -> lineage_promotion.ComponentLineageStore:
        loaded = lineage_promotion.ComponentLineageStore.load(args.store_root)
        checkpoints.append(
            {
                "label": label,
                "state_digest": loaded.state["state_digest"],
                "active_artifact_digest": loaded.state["active_artifact_digest"],
                "generation": loaded.state["generation"],
                "journal_head": loaded.journal.head,
            }
        )
        return loaded

    # Round A: seed -> D1, expected to be decided solely by the frozen authority rule.
    store.stage_candidate(d1)
    isolation["A"] = store.state["active_artifact_digest"] == seed["artifact_digest"]
    parent_a = _evaluate(
        seed,
        rounds["A"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    candidate_a = _evaluate(
        d1,
        rounds["A"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    verdict_a = _authority_decision(
        parent_a,
        candidate_a,
        rule=prereg["decision_rule"]["rule"],
    )
    decision_a = lineage_promotion.create_external_decision(
        parent_artifact=seed,
        candidate_artifact=d1,
        decision=verdict_a,
        authority_digest=prereg["authority"]["authority_digest"],
        rule_digest=prereg["decision_rule"]["rule_digest"],
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        case_set_digest=parent_a["case_set_digest"],
        parent_measurement_digest=parent_a["measurement_digest"],
        candidate_measurement_digest=candidate_a["measurement_digest"],
        ablation_evidence_digest=digest_of(
            {
                "kind": "exact_parent_reversion",
                "candidate": d1["artifact_digest"],
                "parent": seed["artifact_digest"],
                "round": "A",
            }
        ),
    )
    store.apply_external_decision(decision_a)
    store = restart("after_A_decision")
    measurements["A"] = {"parent": parent_a, "candidate": candidate_a}
    decisions["A"] = decision_a

    # Round B: propose exact-source reversion as a normal descendant of active D1.
    before_b = dict(store.state)
    store.stage_candidate(reversion)
    isolation["B"] = store.state["active_artifact_digest"] == d1["artifact_digest"]
    parent_b = _evaluate(
        d1,
        rounds["B"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    candidate_b = _evaluate(
        reversion,
        rounds["B"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    verdict_b = _authority_decision(
        parent_b,
        candidate_b,
        rule=prereg["decision_rule"]["rule"],
    )
    decision_b = lineage_promotion.create_external_decision(
        parent_artifact=d1,
        candidate_artifact=reversion,
        decision=verdict_b,
        authority_digest=prereg["authority"]["authority_digest"],
        rule_digest=prereg["decision_rule"]["rule_digest"],
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        case_set_digest=parent_b["case_set_digest"],
        parent_measurement_digest=parent_b["measurement_digest"],
        candidate_measurement_digest=candidate_b["measurement_digest"],
        ablation_evidence_digest=digest_of(
            {
                "kind": "reversion_candidate_control",
                "candidate": reversion["artifact_digest"],
                "active": d1["artifact_digest"],
                "round": "B",
            }
        ),
    )
    store.apply_external_decision(decision_b)
    rejection_state_unchanged = store.state == before_b
    store = restart("after_B_decision")
    measurements["B"] = {"parent": parent_b, "candidate": candidate_b}
    decisions["B"] = decision_b

    # External rollback challenge: exact restoration of A's parent.
    rollback = lineage_promotion.create_external_rollback(
        adoption_decision=decision_a,
        authority_digest=prereg["authority"]["rollback_authority_digest"],
        reason_evidence_digest=prereg["rollback_challenge_digest"],
    )
    store.apply_external_rollback(rollback, adoption_decision=decision_a)
    store = restart("after_exact_rollback")
    rollback_exact = (
        store.state["active_artifact_digest"] == seed["artifact_digest"]
        and store.active_artifact()["source_sha256"] == seed["source_sha256"]
    )

    # Round C: after rollback, an independently generated D2 competes against seed.
    store.stage_candidate(d2)
    isolation["C"] = store.state["active_artifact_digest"] == seed["artifact_digest"]
    parent_c = _evaluate(
        seed,
        rounds["C"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    candidate_c = _evaluate(
        d2,
        rounds["C"],
        operator=operator,
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        candidate_budget=prereg["decision_rule"]["candidate_budget_per_round"],
    )
    verdict_c = _authority_decision(
        parent_c,
        candidate_c,
        rule=prereg["decision_rule"]["rule"],
    )
    decision_c = lineage_promotion.create_external_decision(
        parent_artifact=seed,
        candidate_artifact=d2,
        decision=verdict_c,
        authority_digest=prereg["authority"]["authority_digest"],
        rule_digest=prereg["decision_rule"]["rule_digest"],
        evaluator_digest=prereg["external_evaluator"]["evaluator_digest"],
        case_set_digest=parent_c["case_set_digest"],
        parent_measurement_digest=parent_c["measurement_digest"],
        candidate_measurement_digest=candidate_c["measurement_digest"],
        ablation_evidence_digest=digest_of(
            {
                "kind": "exact_parent_reversion",
                "candidate": d2["artifact_digest"],
                "parent": seed["artifact_digest"],
                "round": "C",
            }
        ),
    )
    store.apply_external_decision(decision_c)
    store = restart("after_C_decision")
    measurements["C"] = {"parent": parent_c, "candidate": candidate_c}
    decisions["C"] = decision_c

    tamper = _tamper_probes(args.store_root, decision_c["decision_digest"])
    replay_final = lineage_promotion.ComponentLineageStore.load(args.store_root)

    requirements = {
        "holdout_sha256_matches_preregistered_identity": holdout_sha == prereg["holdout"]["sha256"],
        "all_raw_holdout_cases_fail_before_repair": baseline_all_fail,
        "all_candidates_are_isolated_before_decision": all(isolation.values()),
        "round_A_is_adopted_by_frozen_rule": decision_a["decision"] == "adopt",
        "round_B_regression_is_rejected_by_frozen_rule": decision_b["decision"] == "reject",
        "round_B_rejection_does_not_mutate_active_state": rejection_state_unchanged,
        "external_rollback_restores_exact_A_parent": rollback_exact,
        "restart_replay_succeeds_after_each_transition": len(checkpoints) == 4,
        "round_C_is_adopted_after_rollback": decision_c["decision"] == "adopt",
        "final_active_artifact_is_D2": replay_final.state["active_artifact_digest"] == d2["artifact_digest"],
        "lineage_generation_is_monotonic_and_expected": replay_final.state["generation"] == 3,
        "artifact_tampering_is_rejected": tamper["artifact"],
        "decision_tampering_is_rejected": tamper["decision"],
        "journal_tampering_is_rejected": tamper["journal"],
        "state_tampering_is_rejected": tamper["state"],
        "all_measurements_use_zero_external_model_calls": all(
            record[side]["external_model_calls"] == 0
            for record in measurements.values()
            for side in ("parent", "candidate")
        ),
        "all_decisions_bind_frozen_authority_rule_and_evaluator": all(
            record["authority_digest"] == prereg["authority"]["authority_digest"]
            and record["rule_digest"] == prereg["decision_rule"]["rule_digest"]
            and record["evaluator_digest"] == prereg["external_evaluator"]["evaluator_digest"]
            for record in decisions.values()
        ),
    }
    gate_passed = all(requirements.values())

    result = {
        "schema": RESULT_SCHEMA,
        "preregistration_digest": prereg["preregistration_digest"],
        "candidate_set_digest": candidates["candidate_set_digest"],
        "holdout": {
            "sha256": holdout_sha,
            "round_count": len(rounds),
            "case_count": sum(len(item["cases"]) for item in rounds.values()),
            "baseline_all_fail": baseline_all_fail,
            "baseline_results": baselines,
        },
        "measurements": measurements,
        "decisions": decisions,
        "rollback": rollback,
        "isolation": isolation,
        "rejection_state_unchanged": rejection_state_unchanged,
        "rollback_exact": rollback_exact,
        "restart_checkpoints": checkpoints,
        "tamper_probes": tamper,
        "final_state": replay_final.state,
        "final_journal_head": replay_final.journal.head,
        "requirements": requirements,
        "gate_passed": gate_passed,
        "verdict": (
            prereg["qualification_rule"]["pass_label"]
            if gate_passed
            else prereg["qualification_rule"]["fail_label"]
        ),
        "external_model_calls": 0,
        "claim_boundary": prereg["claim_boundary"],
    }
    result["result_digest"] = digest_of(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
