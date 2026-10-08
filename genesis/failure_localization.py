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


def prioritize_from_public_test_source(
    *,
    project_root: str | Path,
    test_source_dir: str,
    failing_tests_text: str,
    source_paths: Sequence[str],
    max_focus_files: int = 32,
) -> dict:
    """Prioritize touched Java *types* referenced by failing public test code.

    Read only the original buggy checkout's public tests. No patches, future
    evaluation outcomes or reference fixes. Unlike sorting loaded classes by
    file path, this can prioritize helper types used by a test whose own class
    has no direct equivalent in production.

    Lexical source mentions are WEAK, not statement coverage or causal proof.
    """
    from genesis.java_sibling_guard_mutations import _mask_literals_and_comments
    from pathlib import Path
    import re
    from collections import defaultdict

    if not 1 <= max_focus_files <= 32:
        raise ValueError("focus budget must be 1..32")
    root = Path(project_root).resolve(strict=True)
    base_tests = (root / test_source_dir).resolve()
    if not base_tests.is_relative_to(root):
        raise ValueError("invalid test directory")
    paths = tuple(sorted(set(str(x) for x in source_paths)))
    scores: dict[str, int] = {p: 0 for p in paths}
    evidence: dict[str, list[str]] = defaultdict(list)
    loaded_source_names = {p: Path(p).stem for p in paths}
    parsed_tests = []
    for match in _HEADER.finditer(failing_tests_text[:200_000]):
        test_class = match["test"]
        method = match["method"]
        relative = Path(test_class.replace(".", "/") + ".java")
        file = (base_tests / relative).resolve()
        if not file.is_relative_to(base_tests) or not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        if len(text) > 512_000:
            continue
        masked = _mask_literals_and_comments(text)
        # Only the declared failing method, not all unrelated test methods.
        signature = re.compile(
            r"\b(?:void|boolean|int|long|String|[A-Z][A-Za-z0-9_$<>]*)\s+"
            + re.escape(method)
            + r"\s*\([^)]*\)\s*(?:throws\s+[A-Za-z0-9_$.,\s]+)?\{"
        )
        declaration = signature.search(masked)
        if declaration is None:
            continue
        depth = 1
        end = declaration.end()
        while end < len(masked) and depth:
            if masked[end] == "{":
                depth += 1
            elif masked[end] == "}":
                depth -= 1
            end += 1
        if depth != 0:
            continue
        body = masked[declaration.end():end - 1]
        test_pkg = test_class.rsplit(".", 1)[0] if "." in test_class else ""
        package_path = test_pkg.replace(".", "/") + "/" if test_pkg else ""
        parsed_tests.append({"test_class":test_class,"test_method":method})
        for path, stem in loaded_source_names.items():
            # Direct class reference in failing test method: the most
            # reliable *lexical* clue. This is not dynamic coverage.
            direct = len(re.findall(r"\b"+re.escape(stem)+r"\b", body))
            if direct:
                scores[path] += min(24, direct * 8)
                evidence[path].append("declared_java_type_used_in_failing_test")
            # References to a typed field in the enclosing test class.
            for field in re.findall(
                r"\b"+re.escape(stem)+r"\s+([A-Za-z_$][A-Za-z0-9_$]*)"
                + r"\s*(?:=|;|,)",
                masked[:declaration.start()],
            )[:12]:
                if re.search(r"\b"+re.escape(field)+r"\s*\.",body):
                    scores[path] += 7
                    evidence[path].append("typed_test_fixture_invoked")
                    break
            if package_path and package_path in path:
                scores[path] += min(4, len(package_path.split("/")))
                evidence[path].append("public_test_package_match")
            base_name = test_class.rsplit(".",1)[-1]
            for suffix in ("Tests", "TestCase", "Test"):
                if base_name.endswith(suffix):
                    base_name=base_name[:-len(suffix)]
                    break
            if stem == base_name:
                scores[path] += 40
                evidence[path].append("test_class_base_name_match")
    ordered = sorted(paths, key=lambda x: (-scores[x], x))
    best = ordered[:max_focus_files]
    statement = {
        "schema": "genesis-g11-public-test-source-priority-v1",
        "scope": "buggy-side public failing Java test method only",
        "tested_method_count": len(parsed_tests),
        "input_loaded_source_count": len(paths),
        "selected_focus_count": len(best),
        "selected_source_paths": best,
        "positive_evidence_source_count": sum(scores[x] > 0 for x in paths),
        "ranked_evidence": [
            {"path":path, "score":scores[path], "reasons":sorted(set(evidence[path]))}
            for path in ordered[:max_focus_files]
        ],
        "source_of_ground_truth": "none",
        "fault_location_proven": False,
        "human_patch_consulted": False,
        "machine_code_executed": False,
        "repair_proven": False,
    }
    return {**statement,"priority_digest":digest_of(statement)}
