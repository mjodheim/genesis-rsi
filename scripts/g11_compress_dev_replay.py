#!/usr/bin/env python3
"""Reproducible POSTHOC repair replay on previously examined Compress-6.

This is NOT an unseen independent test. No human fix is inspected.
Program source is untouched; validators use fresh buggy-only copies.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist
from genesis.failure_localization import prioritize
from genesis.trust_root import digest_of
from scripts.g11_compress_real_pilot import BUGGY, evaluate_unique, focus_files
from scripts.run_autonomous_defects4j_lang import _d4j_export

OUTPUT = Path(__file__).resolve().parents[1] / "experiment/g11/G11_COMPRESS6_POSTHOC_REPAIR_20261008.json"


def run() -> dict:
    source_prefix = _d4j_export(BUGGY, "dir.src.classes")[-1]
    focus = focus_files(BUGGY, source_prefix)
    hints = prioritize((BUGGY / "failing_tests").read_text(encoding="utf-8"), focus)
    opts = {
        "include_prefixes": [source_prefix],
        "focus_paths": focus,
        "max_candidates": 80,
        "per_family_budget": 80,
        "composition_fraction": 0.4,
        "source_balance_experimental": True,
        "priority_focus_paths": hints["matched_source_paths"],
    }
    without_atomic = repair_strategist.generate(BUGGY, **opts)
    with_atomic = repair_strategist.generate(
        BUGGY, **opts, atomic_first_experimental=True,
    )
    pure = "initialize_shadowed_inherited_state"
    def rank_of(data):
        return next((
            i for i, c in enumerate(data["candidates"], 1)
            if c["plan"]["component_operators"] == [pure]
        ), None)
    old_rank = rank_of(without_atomic)
    new_rank = rank_of(with_atomic)
    if new_rank is None:
        raise RuntimeError("new operator was not selected")
    selected = with_atomic["candidates"][new_rank - 1]
    preimage = (BUGGY / selected["path"]).read_text(encoding="utf-8")
    if hashlib.sha256(preimage.encode()).hexdigest() != selected["expected_sha256"]:
        raise RuntimeError("buggy source changed before replay")
    # Freeze the candidate before executing independent validation.
    freeze = {
        "schema": "genesis-g11-development-repair-freeze-v1",
        "candidate_sha256": hashlib.sha256(selected["content_utf8"].encode()).hexdigest(),
        "candidate_digest": selected["candidate_digest"],
        "source_path": selected["path"],
        "source_sha256": selected["expected_sha256"],
        "selected_operator": pure,
        "prioritized_sources": hints["matched_source_paths"],
        "atomic_disabled_rank": old_rank,
        "atomic_enabled_rank": new_rank,
        "old_search_digest": without_atomic["strategy_digest"],
        "new_search_digest": with_atomic["strategy_digest"],
        "no_fixed_checkout_or_human_solution": True,
    }
    freeze_digest = digest_of(freeze)
    if new_rank > 8:
        raise RuntimeError("posthoc correct fix still outside evaluation budget")
    outcome = evaluate_unique(
        Path(selected["path"]), selected["content_utf8"],
        selected["candidate_digest"], selected["expected_sha256"],
    )
    payload = {
        "schema": "genesis-g11-posthoc-development-repair-v1",
        "project": "Compress",
        "bug_id": 6,
        "case_was_already_exposed": True,
        "claim": "training_development_case_repair_not_unseen_autonomous_discovery",
        "freeze_digest": freeze_digest,
        "freeze": freeze,
        "original_reference_test_failure_count": 1,
        "full_project_validation": outcome,
        "validated_full_project_suite": bool(outcome.get("validated_full_suite")),
        "human_reference_patch_seen": False,
        "independent_holdout_success_count": 0,
    }
    result = {**payload, "result_digest": digest_of(payload)}
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    value = run()
    print("DEVELOPMENT_RANK_OLD", value["freeze"]["atomic_disabled_rank"])
    print("DEVELOPMENT_RANK_NEW", value["freeze"]["atomic_enabled_rank"])
    print("FULL_PROJECT_PASS", value["validated_full_project_suite"])
    print("REPORT", OUTPUT)
