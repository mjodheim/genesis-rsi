"""Scientific report must not mistake seed variation for independent NPN classes."""
from __future__ import annotations

import pytest
from tools.audit_circuit2_seed_diversity import audit, npn_class, require_npn_isolation
from genesis import circuit_tasks as tasks


def test_equivalent_tables_have_same_canonical_class():
    for inputs, table in ((2, 7), (3, 23), (3, 105)):
        baseline = npn_class(inputs, table)
        for mask in range(1 << inputs):
            alternate = tasks._transform(
                inputs, table, tuple(reversed(range(inputs))), False, mask
            )
            assert npn_class(inputs, alternate) == baseline


def test_audit_is_deterministic_after_clearing_generation_cache():
    first = audit(tuple(range(20)))
    tasks._circuit2_assignment.cache_clear()
    assert first == audit(tuple(range(20)))


def test_npn_overlap_is_truthfully_reported_and_not_hidden_by_different_digests():
    report = audit(tuple(range(20)))
    assert report["status"] == "DESCRIPTIVE_DEVELOPMENT_AUDIT_NOT_BLIND_OR_PROSPECTIVE"
    assert report["within_seed_exact_collisions"] == []
    assert report["train"]["distinct_full_suite_digests"] == 20
    assert report["evaluation"]["distinct_full_suite_digests"] == 20
    assert report["npn_independent_holdout"] == (report["shared_npn_count"] == 0)
    assert report["seed_independence_established"] is False
    for name in ("train", "evaluation"):
        group = report[name]
        assert group["total_task_slots"] >= group["distinct_exact_tables"]
        assert group["distinct_exact_tables"] >= group["distinct_npn_classes"]
        assert group["repeat_slots"] == group["total_task_slots"] - group["distinct_exact_tables"]
    # This is a protective NEGATIVE test of the current design; new task-grammar
    # releases must replace this test with a new frozen prospective protocol.
    assert report["shared_npn_count"] > 0
    with pytest.raises(ValueError, match="reuse NPN-equivalent"):
        require_npn_isolation(report)


def test_strict_guard_permits_genuinely_isolated_synthetic_report():
    report = {
        "within_seed_exact_collisions": [],
        "shared_npn_count": 0,
    }
    require_npn_isolation(report)
    report["within_seed_exact_collisions"] = [1]
    with pytest.raises(ValueError, match="exact table"):
        require_npn_isolation(report)
