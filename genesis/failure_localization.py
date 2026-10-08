"""Bounded failing-test-to-source *hints*, without hidden reference fixes.

Input: raw failing_tests text from the already-tested buggy checkout, and
candidate source paths selected by project-level dynamic loaded classes.
Test class basename similarity is weak evidence, not ground truth.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Sequence
from genesis.trust_root import digest_of

_HEADER = re.compile(
    r"^---\s+(?P<test>[A-Za-z_][\w.$]*)::(?P<method>[A-Za-z_][\w$]*)\s*$",
    re.MULTILINE,
)


def prioritize(
    failing_tests_text: str,
    source_paths: Sequence[str],
) -> dict:
    """Return ranked filenames and fully explicit evidence provenance.

    Never reads the human fix. A name match is a hint and should be guarded
    against unrepresentative or renamed tests; no method is asserted faulty.
    """
    raw = [match.group("test").rsplit(".", 1)[-1].split("$", 1)[0]
           for match in _HEADER.finditer(failing_tests_text[:200_000])]
    classes = []
    for name in raw:
        normalized = name
        for suffix in ("TestCase", "Tests", "Test"):
            if normalized.endswith(suffix) and len(normalized) > len(suffix):
                normalized = normalized[:-len(suffix)]
                break
        if normalized:
            classes.append(normalized)
    unique = sorted(set(str(p) for p in source_paths
                        if str(p).endswith(".java") and ".." not in Path(str(p)).parts))
    matched = []
    for path in unique:
        stem = Path(path).stem
        # Match only exact class/simple basename, not arbitrary substring.
        if stem in classes:
            matched.append(path)
    ranked = sorted(unique, key=lambda path: (path not in matched, path))
    payload = {
        "schema": "genesis-failing-test-source-hints-v1",
        "source_paths": ranked,
        "matched_source_paths": sorted(matched),
        "source_count": len(unique),
        "test_header_count": len(raw),
        "evidence_kind": "failing_test_classname_basename_heuristic",
        "fault_location_proven": False,
        "human_patch_seen": False,
    }
    return {**payload, "hint_digest": digest_of(payload)}
