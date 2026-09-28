import pytest

from controls import (
    ARMS, ExternalBudget, ControlArm, consume_budget, prospective_arms,
)
from exploration_grammar import ExplorationMechanism, ROOT


def test_all_prospective_control_arms_are_present_and_valid():
    arms = prospective_arms()
    assert tuple(arm.name for arm in arms) == ARMS
    assert all(arm.validate() is arm for arm in arms)


def test_controls_cannot_gain_mechanism_evolution_authority():
    for name in ("exact_predecessor", "mechanism_ablation", "no_meta"):
        mechanism = None if name == "no_meta" else ROOT
        with pytest.raises(ValueError, match="may not evolve"):
            ControlArm(name, mechanism, True).validate()


def test_predecessor_controls_are_root_exact():
    changed = ExplorationMechanism("quality_first", 0, 0)
    with pytest.raises(ValueError, match="exact V25 root"):
        ControlArm("mechanism_ablation", changed, False).validate()


def test_external_budget_is_equal_and_fail_closed():
    assert ExternalBudget().validate() == ExternalBudget()
    consume_budget(requests=9, rounds=8, parallelism=2, depth=2)
    with pytest.raises(RuntimeError, match="request budget"):
        consume_budget(requests=10, rounds=8, parallelism=2, depth=2)
    with pytest.raises(RuntimeError, match="round budget"):
        consume_budget(requests=9, rounds=9, parallelism=2, depth=2)
    with pytest.raises(RuntimeError, match="parallelism"):
        consume_budget(requests=9, rounds=8, parallelism=3, depth=2)
    with pytest.raises(RuntimeError, match="mutation-depth"):
        consume_budget(requests=9, rounds=8, parallelism=2, depth=3)


def test_budget_definition_cannot_be_silently_changed():
    with pytest.raises(ValueError, match="differs"):
        ExternalBudget(represented_requests=8).validate()
