"""Development-only tests. This is not a blind or independent experiment."""
from __future__ import annotations

import pytest

from experiment.representation_discovery.prototype import (
    MAX_INPUTS, encode, decode, encoding_bits, evolve, representation, score, tasks_for, trial, FAMILIES_TRAIN,
)


@pytest.mark.parametrize("inputs", [1, 2, 3])
def test_each_representation_is_its_own_inverse(inputs):
    for table in range(1 << (1 << inputs)):
        for mask in range(1 << inputs):
            assert representation(representation(table, inputs, mask), inputs, mask) == table


def test_bad_inputs_are_rejected():
    for args in [(1, 0, 0), (0, 7, 0), (2, 3, 8), (-1, 2, 0)]:
        with pytest.raises(ValueError):
            representation(*args)


def test_proposed_representations_cannot_worsen_training_objective():
    for n in range(2, MAX_INPUTS + 1):
        train = tasks_for(FAMILIES_TRAIN, n)
        win, history = evolve(train, n)
        assert len(history) <= (1 << n)
        assert win.training_bits <= score(train, n, 0)
        assert 0 in history
        visited = set()
        pointer = win
        while pointer.parent is not None:
            assert pointer.mask not in visited
            visited.add(pointer.mask)
            pointer = history[pointer.parent]
        assert pointer.mask == 0


def test_training_order_does_not_change_selection():
    n = 4
    train = tasks_for(FAMILIES_TRAIN, n)
    selected, _ = evolve(train, n)
    reversed_order, _ = evolve(tuple(reversed(train)), n)
    assert selected.mask == reversed_order.mask


def test_development_trial_is_deterministic_and_declares_limits():
    a = trial()
    assert a == trial()
    assert a["status"] == "DEVELOPMENT_ONLY_NOT_BLIND"
    assert len(a["rows"]) == MAX_INPUTS - 1
    assert all(row["training_evolved_bits_including_descriptor"] <= row["training_identity_bits"]
               for row in a["rows"])


def test_encoding_metrics_are_positive_and_bounded():
    for n in range(1, MAX_INPUTS + 1):
        for table in [0, 1, (1 << (1 << n)) - 1]:
            assert 0 < encoding_bits(table, n) <= 1 + (1 << n)


def test_actual_codec_roundtrip_exhaustive_small_tables():
    for n in (1, 2, 3):
        for table in range(1 << (1 << n)):
            payload = encode(table, n)
            assert decode(payload, n) == table
            assert len(payload) == encoding_bits(table, n)
            assert len(payload) <= 1 + (1 << n)


@pytest.mark.parametrize("bad", ["", "2", "0", "01", "101", "1001100"])
def test_malformed_codec_is_rejected(bad):
    with pytest.raises(ValueError):
        decode(bad, 2)


def test_real_codec_rejects_duplicate_sparse_indexes():
    # 2 input bits, 2 sparse entries at the same index 00,00.
    with pytest.raises(ValueError):
        decode("1" + "010" + "00" + "00", 2)
