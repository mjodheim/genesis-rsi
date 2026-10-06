"""Run the Genesis G1->G5 development foundation demonstration.

This is a DEVELOPMENT demonstration, not a scientific qualification. It proves
that the current apparatus composes end to end without an external model:

G1 language substrate
 -> G2 universal operator transfer
 -> G3 failure attribution
 -> G4 self model
 -> G5 prospective matched-budget experiment design
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from genesis.core import self_model
from genesis.evolution import experiment_design
from genesis.languages import substrate
from genesis.learning import failure_model
from genesis.operators import universal
from genesis.trust_root import digest_of

DEMO_SCHEMA = "genesis-g1-g5-foundation-demo-v1"


def build_demo(repository_root: str | Path) -> dict[str, object]:
    repo = Path(repository_root).resolve()

    source_before = "def f(items):\n    return items[1]\n"
    source_after = "def f(items):\n    return items[0]\n"
    source_document = substrate.inspect_source(source_before, path="source.py")
    operator = universal.learn_from_validated_pair(
        source_before,
        source_after,
        source_path="source.py",
        source_result_digest="development-validated-python-pass",
    )

    targets = {
        "A.java": "class A { int f(int[] values) { return values[1]; } }\n",
        "a.ts": "function f(data: number[]) { return data[1]; }\n",
        "A.cs": "class A { int F(int[] values) { return values[1]; } }\n",
    }
    transfers: list[dict[str, object]] = []
    for path, source in targets.items():
        outputs = universal.materialize_source(
            source,
            path=path,
            operator=operator,
        )
        transfers.append({
            "path": path,
            "language": substrate.language_for_path(path),
            "candidate_count": len(outputs),
            "output_digest": digest_of({"outputs": list(outputs)}),
        })

    with tempfile.TemporaryDirectory(prefix="genesis-g3-demo-") as temporary:
        task_root = Path(temporary)
        (task_root / "logic.py").write_text(
            "def identity(value):\n    return value\n",
            encoding="utf-8",
        )
        miss = {
            "report_digest": "development-autonomous-miss",
            "candidate_budget": 64,
            "charged_candidate_executions": 0,
            "winner": None,
            "schedule": {
                "scheduled_count": 0,
                "family_input_counts": {"learned": 0, "retained": 0},
                "family_scheduled_counts": {},
            },
        }
        failure = failure_model.diagnose(
            task_root,
            miss,
            target_prefixes=["logic.py"],
        )

    model = self_model.build_self_model(repo)
    target = self_model.choose_intervention_target(model, failure)
    plan = experiment_design.design_experiment(
        model,
        failure,
        evaluator_id="development-external-evaluator-v1",
        fresh_case_set_id="development-hidden-holdout-v1",
        budget={
            "candidate_executions": 64,
            "wall_time_seconds": 120,
            "external_model_calls": 0,
        },
    )

    payload = {
        "schema": DEMO_SCHEMA,
        "g1": {
            "document_digest": source_document["document_digest"],
            "language": source_document["language"],
            "parser_backend": source_document["parser_backend"],
        },
        "g2": {
            "operator_digest": operator["operator_digest"],
            "source_language": operator["source_language"],
            "semantic_role": operator["semantic_role"],
            "transfers": transfers,
        },
        "g3": {
            "failure_model_digest": failure["failure_model_digest"],
            "primary_failure_class": failure["primary_failure_class"],
        },
        "g4": {
            "self_model_digest": model["self_model_digest"],
            "candidate_component_ids": target["candidate_component_ids"],
            "selected_component_id": target["selected_component_id"],
            "reason": target["reason"],
        },
        "g5": {
            "plan_digest": plan["plan_digest"],
            "target_component_ids": plan["target_component_ids"],
            "arm_count": len(plan["arms"]),
            "fresh_case_contents_visible_to_lineage": plan[
                "fresh_case_contents_visible_to_lineage"
            ],
            "mutable_lineage_owns_verdict": plan["mutable_lineage_owns_verdict"],
        },
        "external_model_calls": 0,
        "claim_boundary": (
            "development apparatus composition only; no G1-G5 scientific exit "
            "criterion or general RSI claim"
        ),
    }
    return {**payload, "demo_digest": digest_of(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = build_demo(arguments.repository_root)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
