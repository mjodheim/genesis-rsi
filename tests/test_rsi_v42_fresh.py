"""Prospective V42 freeze and continuation boundaries."""
import json
import sys

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import bank as v35_bank
from experiment.rsi_v42 import bank, campaign, freeze


def test_fresh_population_is_disjoint_and_fixed():
    assert not set(bank.FRESH_SEEDS) & set(bank.DEV_SEEDS)
    assert not set(bank.FRESH_SEEDS) & set(v35_bank.FRESH_SEEDS)
    assert sum(len(bank.stream(seed, epoch)) for seed in bank.FRESH_SEEDS
               for epoch in range(bank.INITIAL_EPOCHS)) == 468
    assert bank.population_sha256() == digest({
        str(seed): [bank.stream(seed, epoch) for epoch in range(bank.INITIAL_EPOCHS)]
        for seed in bank.FRESH_SEEDS
    })


def test_freeze_constants_never_predeclare_l9_or_l10():
    constants = freeze.constants()
    assert constants["fresh_consumed_before_freeze"] is False
    assert constants["l9_open_ended_passed"] is False
    assert constants["l10_independent_passed"] is False
    assert constants["finite_prefix_cannot_establish_open_endedness"] is True
    assert constants["memory_policy"] == "last_chance_stagnation5_frontier_v1"
    assert constants["max_charged_evaluations_per_task"] == 14


def test_missing_freeze_never_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "missing")
    result = campaign.check()
    assert result["l9_open_ended_passed"] is False
    assert result["l10_independent_passed"] is False
    with pytest.raises(ValueError):
        campaign.check(require_prefix=True)
