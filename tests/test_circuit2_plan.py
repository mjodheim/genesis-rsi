"""Offline checks of the CIRCUIT2 freeze script: build, seal, tamper, refuse a second freeze."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import freeze_circuit2_plan as freeze
from genesis import circuit_tasks as tasks

COMMIT = "a" * 40
LITERAL = (
    "succès seulement si la procédure finale gagne au moins 10 points de rendement "
    "contre la procédure fixe et contre l'aléatoire ; si deux transitions successives "
    "de procédure gagnent chacune au moins 5 points à bibliothèque initiale identique ; "
    "si chacune de ces comparaisons gagne dans au moins 16 graines sur 20 ; et si le gain "
    "disparaît sous ablation (procédure initiale restaurée). Sinon échec publié. "
    "Aucun critère n'est modifiable après gel."
)


@pytest.fixture(scope="module")
def plan():
    return freeze.build_plan(machinery_commit=COMMIT)


MUTATIONS = {
    "field": lambda p: p["metric"].update(name="other"),
    "seed removed": lambda p: p["seeds"].pop(),
    "criterion softened": lambda p: p["criterion"].update(text=p["criterion"]["text"].replace("10 points", "5 points")),
    "budget changed": lambda p: p["budgets"].update(per_generation_limit=p["budgets"]["per_generation_limit"] + 1),
    "justification emptied": lambda p: p["budget_justification"].update(measured_base_cost_by_seed={}),
    "machinery digest": lambda p: p["machinery_digests"].update({"genesis/circuit_engine.py": "0" * 64}),
}


def test_build_plan_has_seeds_arms_and_the_criterion_word_for_word(plan):
    assert plan["seeds"] == list(range(20))
    assert [a["name"] for a in plan["arms"]] == ["inherited_lineage", "frozen_engine", "fixed_procedure", "random_procedure"]
    assert all(label.startswith("circuit2|") for label in plan["seed_labels"])
    assert plan["criterion"]["text"] == LITERAL
    assert plan["machinery_commit"] == COMMIT
    assert sorted(plan["machinery_digests"]) == sorted(freeze.MACHINERY_FILES)


def test_budgets_come_from_the_measurement(plan):
    just = plan["budget_justification"]
    costs = just["measured_base_cost_by_seed"]
    assert len(costs) == 20 and all(c > 0 for c in costs.values())
    assert just["max_measured_base_cost"] == max(costs.values())
    assert plan["budgets"]["per_generation_limit"] == freeze.LIMIT_MULTIPLIER * max(costs.values())
    assert plan["budgets"]["per_generation_limit"] != 16 and plan["budgets"]["task_budget"] != 32
    assert plan["budgets"]["per_generation_limit"] >= 2 * just["max_measured_base_cost"]
    assert all(just[key] for key in ("measured_on", "measured_base_cost_by_seed", "max_measured_base_cost", "rule"))


def test_selection_never_reads_the_held_out_families(plan):
    selection = plan["selection"]
    assert selection["held_out_reads"] == 0
    assert set(selection["families"]) == set(tasks.LEARN)
    assert not set(selection["families"]) & set(tasks.HELD_OUT)
    assert {t.family for t in freeze.learn_tasks()} <= set(tasks.LEARN)


def test_the_digest_verifies(plan):
    freeze.verify_plan(plan)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
@pytest.mark.parametrize("resealed", [False, True])
def test_an_altered_plan_is_refused(plan, name, resealed):
    altered = copy.deepcopy(plan)
    MUTATIONS[name](altered)
    if resealed:
        altered = freeze.seal({k: v for k, v in altered.items() if k != "digest"})
    with pytest.raises(freeze.PlanError):
        freeze.verify_plan(altered)


def test_a_different_machinery_fingerprint_is_refused(plan):
    other = {**plan["machinery_digests"], "genesis/circuit_engine.py": "0" * 64}
    with pytest.raises(freeze.PlanError):
        freeze.verify_plan(plan, current_digests=other)


def test_a_base_evaluation_that_does_not_fit_is_an_explicit_error(monkeypatch):
    monkeypatch.setattr(freeze, "MEASURE_CEILING", 1)
    with pytest.raises(freeze.PlanError, match="does not fit"):
        freeze.measure_base_costs()
    with pytest.raises(freeze.PlanError):
        freeze.build_plan(measure=lambda: {str(s): 0 for s in freeze.SEEDS}, machinery_commit=COMMIT)


def test_a_positive_base_cost_is_measured_under_a_capped_meter(monkeypatch):
    real = freeze.engine.Meter
    made = []

    class SpyMeter(real):
        def __init__(self, limit):
            super().__init__(limit)
            made.append((limit, self))

    monkeypatch.setattr(freeze.engine, "Meter", SpyMeter)
    costs = freeze.measure_base_costs(seeds=(0, 1))
    assert set(costs) == {"0", "1"}
    assert all(isinstance(c, int) and not isinstance(c, bool) and c > 0 for c in costs.values())
    assert [limit for limit, _ in made] == [freeze.MEASURE_CEILING] * 2
    for (limit, meter), seed in zip(made, ("0", "1")):
        assert meter.spent == costs[seed] and meter.spent <= limit


def test_a_second_freeze_is_refused(tmp_path):
    path = tmp_path / "PLAN.json"
    fake = lambda: {str(s): 100 for s in freeze.SEEDS}
    first = freeze.freeze(path, measure=fake, machinery_commit=COMMIT)
    written = path.read_text(encoding="utf-8")
    with pytest.raises(freeze.PlanError, match="already exists"):
        freeze.freeze(path, measure=fake, machinery_commit=COMMIT)
    assert path.read_text(encoding="utf-8") == written and first["digest"] in written


def test_the_plan_path_is_under_experiment_engine_next_to_circuit1():
    expected = Path("experiment/engine/CIRCUIT2/PLAN.json")
    assert freeze.PLAN_PATH.relative_to(freeze.ROOT) == expected
    circuit1 = freeze.ROOT / "experiment" / "engine" / "CIRCUIT1"
    assert freeze.PLAN_PATH.parent != circuit1
    assert freeze.PLAN_PATH.parent.parent == circuit1.parent
    assert not freeze.PLAN_PATH.exists()


# Digest of the default suite(LEARN + HELD_OUT), pinned from the CIRCUIT1 base suite;
# it must never be recomputed from the modified code.
CIRCUIT1_SUITE_DIGEST = "fd8167e8b55a514dc6439c674e0c503d5a757052500d76f23b27f3889598c4fe"
LEGACY_CIRCUIT2_SEED0_DIGEST = "790bc82194e7dbc5f04f2f3553eae88bf69f96014122ecadcd93b13c1a8bf15c"
FAMILIES = (*tasks.LEARN, *tasks.HELD_OUT)


def _digest(items):
    rows = [[t.name, t.family, t.inputs, t.target] for t in items]
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()


def _keys(items):
    return {(t.inputs, t.target) for t in items}


@pytest.mark.parametrize("family", FAMILIES)
def test_circuit2_shares_no_table_with_circuit1(family):
    old, new = tasks.tasks(family), tasks.circuit2_tasks(family)
    assert new and not _keys(old) & _keys(new)
    assert all(t.family == family and t.inputs <= tasks.CIRCUIT2_MAX_INPUTS for t in new)
    assert len({t.name for t in new}) == len(new) and len(_keys(new)) == len(new)


def test_circuit2_generation_is_reproducible():
    baseline = {family: tasks.circuit2_tasks(family) for family in FAMILIES}
    tasks._circuit2_assignment.cache_clear()
    assert baseline == {family: tasks.circuit2_tasks(family) for family in FAMILIES}
    assert tasks.circuit2_suite(FAMILIES) == [
        t for family in FAMILIES for t in baseline[family]
    ]


def test_circuit2_heldout_seed_variation_is_real():
    heldout = [
        [(t.name, t.inputs, t.target) for t in tasks.circuit2_suite(tasks.HELD_OUT, seed)]
        for seed in (0, 1, 2, 3, 7, 11)
    ]
    assert all(heldout), "each heldout suite must be nonempty"
    assert len({tuple(one) for one in heldout}) >= 4, (
        "different seeds must not silently reuse an identical heldout suite"
    )


def test_legacy_circuit2_seed_zero_is_unchanged():
    # Pinned from PR #428 original HEAD, NOT regenerated from modified code.
    sequence = tasks.circuit2_suite((*tasks.LEARN, *tasks.HELD_OUT, *tasks.CONTROL), seed=0)
    assert _digest(sequence) == LEGACY_CIRCUIT2_SEED0_DIGEST


def test_measure_base_costs_actually_evaluates_seed_specific_tasks(monkeypatch):
    recorded = []
    real_attempt = freeze.engine._metered_attempt

    def track_attempt(engine, given_tasks, *args):
        recorded.append(_digest(given_tasks))
        return real_attempt(engine, given_tasks, *args)

    monkeypatch.setattr(freeze.engine, "_metered_attempt", track_attempt)
    seeds = (0, 1, 2, 3, 7, 11)
    measured = freeze.measure_base_costs(seeds=seeds)
    assert set(measured) == {str(s) for s in seeds}
    assert len(recorded) == len(seeds)
    assert len(set(recorded)) >= 4, (
        "cost measurement silently reused the same seed-zero task set"
    )


def test_circuit1_default_suite_is_unchanged():
    assert _digest(tasks.suite(FAMILIES)) == CIRCUIT1_SUITE_DIGEST


def test_the_plan_is_built_on_circuit2_instances_and_not_written(plan, monkeypatch):
    expected = [t for t in tasks.circuit2_suite(tuple(tasks.LEARN)) if t.inputs <= freeze.MAX_INPUTS]
    assert expected and freeze.learn_tasks() == expected
    assert all(t.name.startswith("c2_") for t in expected)
    assert plan["budget_justification"]["learn_task_count"] == len(expected)
    assert plan["metric"]["held_out_families"] == sorted(tasks.HELD_OUT)
    assert plan["selection"]["families"] == sorted(tasks.LEARN)
    seen = []
    real = freeze.engine._metered_attempt

    def spy(machine, learn, *args):
        seen.append(list(learn))
        return real(machine, learn, *args)

    monkeypatch.setattr(freeze.engine, "_metered_attempt", spy)
    freeze.measure_base_costs(seeds=(0,))
    assert seen == [expected]
    assert not freeze.PLAN_PATH.exists()
