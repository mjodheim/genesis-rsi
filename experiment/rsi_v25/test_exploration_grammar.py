from exploration_grammar import (
    ROOT, ExplorationMechanism, V25GrammarError, behaviorally_distinct,
    decision_record, decision_trace, universe,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
ROUNDS = (
    (
        {"candidate_id": "a", "source_sha256": SHA_A, "quality_milli": 700, "lineage_depth": 1, "novelty": 2},
        {"candidate_id": "b", "source_sha256": SHA_B, "quality_milli": 900, "lineage_depth": 2, "novelty": 0},
    ),
    (
        {"candidate_id": "a", "source_sha256": SHA_A, "quality_milli": 800, "lineage_depth": 1, "novelty": 0},
        {"candidate_id": "b", "source_sha256": SHA_B, "quality_milli": 750, "lineage_depth": 3, "novelty": 2},
    ),
)


def test_universe_is_finite_unique_and_contains_root():
    rows = universe()
    assert len(rows) == 27
    assert ROOT in rows
    assert len({row.digest() for row in rows}) == len(rows)


def test_decision_trace_is_deterministic_and_content_addressed():
    mechanism = ExplorationMechanism("quality_first", 1, 1)
    first = decision_trace(mechanism, ROUNDS)
    assert first == decision_trace(mechanism, ROUNDS)
    assert [row["round_index"] for row in first] == [0, 1]
    assert all(row["mechanism_sha256"] == mechanism.digest() for row in first)
    assert all(len(row["candidate_set_sha256"]) == 64 for row in first)
    assert all(row["observable_features"] == [
        "candidate_id", "source_sha256", "quality_milli", "lineage_depth", "novelty"
    ] for row in first)


def test_behavioral_diversity_is_observable_before_holdout():
    assert behaviorally_distinct(ROOT, ExplorationMechanism("quality_first", 0, 0), ROUNDS)


def test_tie_break_is_stable_input_order():
    tied = (
        {"candidate_id": "first", "source_sha256": SHA_A, "quality_milli": 800, "lineage_depth": 2, "novelty": 1},
        {"candidate_id": "second", "source_sha256": SHA_B, "quality_milli": 800, "lineage_depth": 2, "novelty": 1},
    )
    row = decision_record(ExplorationMechanism("quality_first", 1, 1), tied, round_index=3)
    assert row["selected_candidate_id"] == "first"
    assert row["tie_break"] == "stable-input-order-last-key=-index"


def test_hidden_or_authority_features_fail_closed():
    bad = dict(ROUNDS[0][0])
    bad["evaluator_score"] = 999
    try:
        decision_record(ROOT, (bad,), round_index=0)
    except V25GrammarError:
        pass
    else:
        raise AssertionError("unfrozen observable feature accepted")


def test_duplicate_candidate_identity_fails_closed():
    duplicate = (ROUNDS[0][0], {**ROUNDS[0][1], "candidate_id": "a"})
    try:
        decision_record(ROOT, duplicate, round_index=0)
    except V25GrammarError:
        pass
    else:
        raise AssertionError("duplicate candidate identity accepted")


def test_invalid_mechanism_fails_closed():
    try:
        ExplorationMechanism("unbounded", 0, 0).validate()
    except V25GrammarError:
        pass
    else:
        raise AssertionError("invalid strategy accepted")
