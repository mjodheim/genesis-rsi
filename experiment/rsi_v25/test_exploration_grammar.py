from exploration_grammar import (
    ROOT, ExplorationMechanism, V25GrammarError, behaviorally_distinct,
    decision_trace, universe,
)

ROUNDS = (
    (
        {"quality_milli": 700, "lineage_depth": 1, "novelty": 2},
        {"quality_milli": 900, "lineage_depth": 2, "novelty": 0},
    ),
    (
        {"quality_milli": 800, "lineage_depth": 1, "novelty": 0},
        {"quality_milli": 750, "lineage_depth": 3, "novelty": 2},
    ),
)

def test_universe_is_finite_unique_and_contains_root():
    rows=universe()
    assert len(rows)==27
    assert ROOT in rows
    assert len({row.digest() for row in rows})==len(rows)

def test_decision_trace_is_deterministic():
    mechanism=ExplorationMechanism("quality_first",1,1)
    assert decision_trace(mechanism, ROUNDS)==decision_trace(mechanism, ROUNDS)

def test_behavioral_diversity_is_observable_before_holdout():
    assert behaviorally_distinct(ROOT, ExplorationMechanism("quality_first",0,0), ROUNDS)

def test_invalid_mechanism_fails_closed():
    try:
        ExplorationMechanism("unbounded",0,0).validate()
    except V25GrammarError:
        pass
    else:
        raise AssertionError("invalid strategy accepted")
