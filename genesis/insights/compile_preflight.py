"""Experimental, opt-in, read-only Java candidate compilation screening.

Compile candidates against the *buggy* project's own compiled classpath.
No tests, reference fixes, public issues or expected answers are loaded.
The reference source is compiled with the identical options first; if
that fails, no candidate is demoted (outcome is inconclusive).

This is a source-validity filter, NOT a test of behavioral correctness.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-g11-java-compile-preflight-v1"


def _compile(
    source_path: str,
    text: str,
    *,
    javac: Path,
    classpath: Sequence[str],
    timeout_seconds: int,
) -> tuple[str, str]:
    safe_relative = Path(source_path)
    if safe_relative.is_absolute() or ".." in safe_relative.parts or not safe_relative.parts:
        raise ValueError("compiler preflight requires a safe relative source path")
    with tempfile.TemporaryDirectory(prefix="g11-javac-screen-") as tmp:
        base = Path(tmp)
        path = base / "source" / safe_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        classes = base / "classes"
        classes.mkdir()
        command = [
            str(javac), "-proc:none", "-implicit:none",
            "-encoding", "UTF-8", "-d", str(classes),
        ]
        if classpath:
            command.extend(("-classpath", os.pathsep.join(classpath)))
        command.append(str(path))
        try:
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=timeout_seconds,
            )
            status = "valid" if result.returncode == 0 else "invalid"
            # Compiler diagnostics include the random TemporaryDirectory
            # path. Normalize it before hashing for deterministic provenance.
            diagnostics = (result.stderr + result.stdout).replace(str(base), "$TMP")
            diagnostic_digest = hashlib.sha256(diagnostics.encode()).hexdigest()
            return status, diagnostic_digest
        except (subprocess.TimeoutExpired, OSError) as exc:
            return "inconclusive", hashlib.sha256(type(exc).__name__.encode()).hexdigest()


def screen_candidates(
    root: Path,
    candidates: Sequence[Mapping[str, Any]],
    *,
    javac: Path,
    classpath: Sequence[str],
    max_candidates: int = 80,
    timeout_seconds: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Partition stable candidate order by valid/unknown/invalid compilation.

    Fail-closed for missing originals, unsupported Java files, stale source
    hashes and unresolved original source. A negative status is *reliable*
    only when compiling the original under identical options succeeded.
    """
    if max_candidates < 1 or max_candidates > 250:
        raise ValueError("max_candidates must be [1,250]")
    if timeout_seconds < 1 or timeout_seconds > 120:
        raise ValueError("timeout_seconds must be [1,120]")
    base = Path(root).resolve(strict=True)
    if not str(javac):
        raise ValueError("javac path is required")
    baseline_cache: dict[str, str] = {}
    outcomes: list[dict[str, Any]] = []
    sorted_candidates = [dict(c) for c in candidates]
    for index, rec in enumerate(sorted_candidates[:max_candidates]):
        relative = str(rec.get("path") or "")
        target = (base / relative).resolve()
        mutated = rec.get("content_utf8")
        status = "inconclusive"
        reason = "unsupported_or_missing_candidate"
        digest = ""
        if (relative and not Path(relative).is_absolute()
                and ".." not in Path(relative).parts
                and target.is_relative_to(base) and target.is_file()
                and target.suffix == ".java"
                and isinstance(mutated, str)
                and len(mutated.encode("utf-8")) <= 512_000):
            original = target.read_text(encoding="utf-8")
            preimage = hashlib.sha256(original.encode()).hexdigest()
            expected = rec.get("expected_sha256")
            if expected in ("", None, preimage):
                if relative not in baseline_cache:
                    baseline_cache[relative] = _compile(
                        relative, original, javac=javac,
                        classpath=classpath, timeout_seconds=timeout_seconds,
                    )[0]
                if baseline_cache[relative] == "valid":
                    status, digest = _compile(
                        relative, mutated, javac=javac,
                        classpath=classpath, timeout_seconds=timeout_seconds,
                    )
                    reason = "source_preflight"
                else:
                    reason = "original_compilation_unavailable"
            else:
                reason = "preimage_digest_mismatch"
        outcomes.append({
            "input_rank": index + 1,
            "source_path": relative,
            "candidate_sha256": hashlib.sha256(str(mutated).encode()).hexdigest(),
            "status": status,
            "reason": reason,
            "diagnostic_digest": digest,
        })
    # Stable partition changes only the ordering, not candidate contents.
    # Candidates not screened remain in their existing relative order
    # and are marked inconclusive rather than assumed invalid.
    statuses = {row["input_rank"]: row["status"] for row in outcomes}
    priority = {"valid": 0, "inconclusive": 1, "invalid": 2}
    reordered = [
        record for i, record in sorted(
            enumerate(sorted_candidates, 1),
            key=lambda pair: (
                priority[statuses.get(pair[0], "inconclusive")], pair[0]
            ),
        )
    ]
    for index, rec in enumerate(reordered):
        rec["logical_index"] = index
    counts = Counter(row["status"] for row in outcomes)
    payload = {
        "schema": SCHEMA,
        "screened_candidate_count": len(outcomes),
        "candidate_count": len(sorted_candidates),
        "valid_count": counts["valid"],
        "invalid_count": counts["invalid"],
        "inconclusive_count": counts["inconclusive"],
        "source_original_compilations": baseline_cache,
        "outcomes": outcomes,
        "source_code_executed": False,
        "behavioral_correctness_proven": False,
        "selection_is_experimental": True,
        "candidate_content_unchanged": True,
        "compiler_classpath_present": bool(classpath),
        "external_model_calls": 0,
    }
    return reordered, {**payload, "preflight_digest": digest_of(payload)}
