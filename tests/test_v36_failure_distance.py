"""Retrospective audit tests, distinct from prospectively frozen V36 tests."""
from collections import deque
from itertools import product

import pytest

from scripts.audit_v36_recombination_failure import minimum_edits


def exhaustive_distance(start, target, fragments):
    queue, seen = deque([(tuple(start), 0)]), {tuple(start)}
    while queue:
        value, depth = queue.popleft()
        if list(value) == target:
            return depth
        children = []
        for slot in range(len(value)):
            for operator in range(3):
                children.append(value[:slot] + (operator,) + value[slot + 1:])
        for slot in range(0, len(value), 3):
            for fragment in fragments:
                children.append(value[:slot] + tuple(fragment) + value[slot + 3:])
        for child in children:
            if child not in seen:
                seen.add(child)
                queue.append((child, depth + 1))


def test_exact_distance_matches_exhaustive_point_and_splice_graph():
    fragments = [[1, 1, 1], [2, 2, 2]]
    for start in product(range(3), repeat=3):
        for target in product(range(1, 3), repeat=3):
            assert minimum_edits(list(start), list(target), fragments) == exhaustive_distance(start, list(target), fragments)


def test_near_fragment_then_point_is_shorter_than_points_without_exact_fragment():
    assert minimum_edits([], [1, 1, 2], [[1, 1, 1]]) == 2
    assert minimum_edits([], [1, 1, 2], []) == 3


def test_block_distances_sum_and_expose_fixed_depth_obstruction():
    fragments = [[1, 1, 1], [2, 2, 2]]
    assert minimum_edits([1] * 12, [2] * 12, fragments) == 4
    assert minimum_edits([1] * 12, [2] * 12, []) == 12
    with pytest.raises(ValueError):
        minimum_edits([], [1, 2], fragments)
