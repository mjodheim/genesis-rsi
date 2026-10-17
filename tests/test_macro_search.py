"""Tests for larger-granularity representation search; development-only."""
from __future__ import annotations
import pytest
from experiment.representation_discovery import macro_search as m
from experiment.representation_discovery import adaptive_basis as a
from experiment.representation_discovery import prototype as p

def test_axis_program_reconstructs_mask_transform():
    for n in (2, 3, 4, 5):
        for mask in range(1 << n):
            for value in (0, 1, (1 << (1 << n)) - 1):
                assert a.apply_program(value, n, m.axis_program(n, mask)) == p.representation(value, n, mask)

@pytest.mark.parametrize("arity", (3, 4, 5, 6))
def test_search_never_worse_on_training_and_evaluations_are_matched(arity):
    train = p.tasks_for(p.FAMILIES_TRAIN, arity)
    guided = m.discover(train, arity)
    rand = m.discover(train, arity, shear_mode="random")
    assert guided.train_bits <= a.training_score(train, arity, ())
    assert guided.evaluated_candidates == rand.evaluated_candidates
    assert guided.prescreen_probes > 0
    assert rand.prescreen_probes == 0

def test_full_mobius_can_emerge_without_rewarding_individual_axis_steps():
    n = 6
    train = p.tasks_for(p.FAMILIES_TRAIN, n)
    result = m.discover(train, n)
    assert result.baseline_mask == 63
    assert a.training_score(train, n, m.axis_program(n, 63)) < a.training_score(train, n, ())
    assert all(a.training_score(train, n, m.axis_program(n, 1 << k))
               > a.training_score(train, n, ()) for k in range(n))

def test_development_results_reproducible():
    assert m.trial((0,)) == m.trial((0,))



def test_evaluation_descriptor_accounting_is_explicit():
    report = m.trial((0,))
    for row in report["rows"]:
        n = row["arity"]
        guided = tuple(a.Op(*op) for op in row["guided_program"])
        full = m.axis_program(n, (1 << n) - 1)
        assert row["evaluation_guided_including_descriptor"] == (
            row["evaluation_guided_bits"] + a.program_descriptor_bits(guided, n)
        )
        assert row["evaluation_full_mobius_including_descriptor"] == (
            row["evaluation_full_mobius_bits"] + a.program_descriptor_bits(full, n)
        )
        assert row["control_random_family_bits"]["identity"] > 0
