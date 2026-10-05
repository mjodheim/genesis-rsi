"""Target-blind sparse-mask diagnosis from scalar evaluator feedback."""
from __future__ import annotations

import itertools
import math


def quality_for_distance(width, distance):
    return (width - distance) * 1000 // width


def infer_distance(width, quality_milli):
    matches = [
        distance for distance in range(width + 1)
        if quality_for_distance(width, distance) == quality_milli
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return min(matches)
    return min(
        range(width + 1),
        key=lambda distance: abs(
            quality_for_distance(width, distance) - quality_milli
        ),
    )


def infer_sparse_mask_size(width, root_quality_milli, max_bits=2):
    distance = infer_distance(width, root_quality_milli)
    if 1 <= distance <= max_bits:
        expected = quality_for_distance(width, distance)
        if expected == root_quality_milli:
            return distance
    return None


def hypotheses(width, mask_size):
    return tuple(
        sum(1 << bit for bit in bits)
        for bits in itertools.combinations(range(width), mask_size)
    )


def observed_intersection(width, mask_size, probe_mask, quality_milli):
    distance = infer_distance(width, quality_milli)
    numerator = probe_mask.bit_count() + mask_size - distance
    if numerator < 0 or numerator % 2:
        return None
    intersection = numerator // 2
    if not 0 <= intersection <= mask_size:
        return None
    return intersection


def filter_hypotheses(rows, probe_mask, intersection):
    return tuple(
        mask for mask in rows
        if (mask & probe_mask).bit_count() == intersection
    )


def _query_pool(width):
    masks = set()
    full = (1 << width) - 1

    # Binary-code partitions.
    dimensions = max(1, math.ceil(math.log2(width)))
    for axis in range(dimensions):
        mask = 0
        for bit in range(width):
            if (bit >> axis) & 1:
                mask |= 1 << bit
        masks.add(mask)

    # Contiguous balanced intervals at several scales.
    for size in {
        max(1, width // 2),
        max(1, width // 3),
        max(1, width // 4),
    }:
        for start in range(width):
            mask = 0
            for offset in range(size):
                mask |= 1 << ((start + offset) % width)
            masks.add(mask)

    # Deterministic affine half-partitions over bit indices.
    half = max(1, width // 2)
    for multiplier in range(1, width, 2):
        for offset in range(min(width, 8)):
            mask = 0
            for bit in range(width):
                if ((multiplier * bit + offset) % width) < half:
                    mask |= 1 << bit
            masks.add(mask)

    # Singleton fallbacks are useful once uncertainty is already small.
    for bit in range(width):
        masks.add(1 << bit)

    return tuple(sorted(
        mask for mask in masks
        if mask not in (0, full)
    ))


def choose_probe(width, rows, used_masks=()):
    used = set(used_masks)
    if len(rows) <= 1:
        return None
    best = None
    for probe in _query_pool(width):
        if probe in used:
            continue
        buckets = {}
        for hypothesis in rows:
            key = (hypothesis & probe).bit_count()
            buckets[key] = buckets.get(key, 0) + 1
        if len(buckets) <= 1:
            continue
        sizes = tuple(sorted(buckets.values(), reverse=True))
        score = (
            sizes[0],
            sum(size * size for size in sizes),
            abs(probe.bit_count() * 2 - width),
            probe,
        )
        if best is None or score < best[0]:
            best = (score, probe)
    return None if best is None else best[1]


def diagnose(width, root_quality_milli, observations, max_bits=2):
    """Return current hypotheses and the next target-blind probe.

    observations is an iterable of (probe_mask, quality_milli) pairs. No target
    value, expected output, task family or hidden task identifier is consumed.
    """
    mask_size = infer_sparse_mask_size(
        width, root_quality_milli, max_bits=max_bits
    )
    if mask_size is None:
        return {
            "active": False,
            "mask_size": None,
            "hypotheses": (),
            "next_probe": None,
        }

    rows = hypotheses(width, mask_size)
    used = []
    for probe_mask, quality in observations:
        intersection = observed_intersection(
            width, mask_size, probe_mask, quality
        )
        if intersection is None:
            return {
                "active": False,
                "mask_size": mask_size,
                "hypotheses": (),
                "next_probe": None,
            }
        rows = filter_hypotheses(
            rows, probe_mask, intersection
        )
        used.append(probe_mask)
        if not rows:
            return {
                "active": False,
                "mask_size": mask_size,
                "hypotheses": (),
                "next_probe": None,
            }

    return {
        "active": True,
        "mask_size": mask_size,
        "hypotheses": rows,
        "next_probe": choose_probe(width, rows, used),
    }
