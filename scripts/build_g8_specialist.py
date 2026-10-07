"""Freeze a G8 local specialist from already-evaluated A6b fallback evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from genesis.learning import distillation
from genesis.trust_root import digest_of

SCHEMA = "genesis-g8-specialist-freeze-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()

    candidates = sorted(
        (root / "experiment" / "autonomy_a6b").glob("task_*_fallback_result.json")
    )
    selected = []
    skipped = []
    for path in candidates:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if (
            raw.get("schema") != distillation.SOURCE_SCHEMA
            or raw.get("fallback_passed") is not True
            or int(raw.get("model_calls", 0)) < 1
            or int(raw.get("learned_template_count", 0)) < 1
        ):
            skipped.append(path.relative_to(root).as_posix())
            continue
        try:
            validated = distillation.validate_source_record(raw)
        except distillation.DistillationError:
            skipped.append(path.relative_to(root).as_posix())
            continue
        selected.append((path, validated))

    if len(selected) < 4:
        raise SystemExit("G8 requires at least four validated expensive distillation sources")

    specialist = distillation.distill_local_specialist(
        [record for _path, record in selected],
        specialist_id="g8-a6b-local-repair-specialist",
    )
    payload = {
        "schema": SCHEMA,
        "selection_rule": {
            "source_family": "A6b frozen fallback results",
            "requires_fallback_passed": True,
            "requires_model_calls_at_least": 1,
            "requires_learned_template_count_at_least": 1,
            "requires_reproducible_report_and_template_digests": True,
            "manual_task_id_selection": False,
        },
        "selected_paths": [path.relative_to(root).as_posix() for path, _ in selected],
        "skipped_paths": skipped,
        "specialist": specialist,
        "hidden_g8_holdout_visible": False,
        "external_model_calls_for_distillation": 0,
    }
    payload["freeze_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
