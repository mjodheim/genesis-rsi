"""G12 controlled candidate -> real validator -> learned structural operator.

Uses existing A6c memory and structural-operator synthesis. This is a
DEVELOPMENT/TRAINING loop only; fresh holdout evaluation must be physically
separate and frozen before any learning is permitted.

Trust boundary: calling validator has to be an independent, audited,
full-project evaluator. This module checks its signed-by-content receipt but
cannot prove the evaluator is honest or sandboxed. Do not promote to RSI
without independent replication and self-discovered semantic capability.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from genesis.learning import self_extension
from genesis.trust_root import digest_of

FREEZE_SCHEMA = "genesis-g12-learning-candidate-freeze-v1"
RECEIPT_SCHEMA = "genesis-g12-controlled-learning-result-v1"
SHA = re.compile(r"^[0-9a-f]{64}$")


class G12GateError(RuntimeError):
    """Violation of a G12 learning/evidence phase boundary."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validated_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise G12GateError("candidate path must be relative")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise G12GateError("candidate path escapes buggy workspace")
    if any(part in {".git", "test", "tests", "target", "build"} for part in Path(relative).parts):
        raise G12GateError("candidate must mutate project source only")
    if path.stat().st_size > 512_000:
        raise G12GateError("candidate source exceeds size limit")
    return path


def _checked_proposal(root: Path, candidate: Mapping[str, Any]) -> dict[str, Any]:
    relative = candidate.get("path")
    source = _validated_path(root, relative)
    original = source.read_text(encoding="utf-8")
    proposed = candidate.get("content_utf8")
    if not isinstance(proposed, str) or len(proposed.encode()) > 512_000 or original == proposed:
        raise G12GateError("candidate must be bounded and change source")
    preimage = _hash(original)
    if candidate.get("expected_sha256") != preimage:
        raise G12GateError("candidate is not based on the current buggy source")
    digest = candidate.get("candidate_digest")
    if not isinstance(digest, str) or not SHA.fullmatch(digest):
        raise G12GateError("candidate digest missing")
    return {
        "path": relative, "expected_sha256": preimage,
        "new_sha256": _hash(proposed),
        "candidate_digest": digest,
        "operators": list((candidate.get("plan") or {}).get("component_operators", [])),
        "depth": int((candidate.get("plan") or {}).get("depth", 1)),
    }


def _write_new(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A complete, synced staging file is linked into place atomically.
    # A power loss cannot leave a half-written *official* freeze/memory.
    stage = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=".g12-stage-", delete=False,
        ) as handle:
            stage = Path(handle.name)
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(stage, path)
        except FileExistsError:
            current = json.loads(path.read_text(encoding="utf-8"))
            if current != dict(document):
                raise G12GateError("immutable freeze/result conflicts with existing file")
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def freeze_training_search(
    *,
    root: Path,
    candidates: Sequence[Mapping[str, Any]],
    previous_failure: Mapping[str, Any],
    freeze_path: Path,
    role: str,
    max_candidates: int = 8,
) -> dict[str, Any]:
    """Seal all candidates before validation or operator learning."""
    if role != "released_training":
        raise G12GateError("never train on a fresh or held-out evaluation")
    if previous_failure.get("winner") is not None or previous_failure.get("autonomous_passed"):
        raise G12GateError("G12 extension requires a verified previous miss")
    if not 1 <= max_candidates <= 32 or not 1 <= len(candidates) <= max_candidates:
        raise G12GateError("bounded candidate set required")
    original_report = previous_failure.get("report_digest")
    if not isinstance(original_report, str) or not SHA.fullmatch(original_report):
        raise G12GateError("previous failure report must have a reproducible digest")
    content = {
        "schema": FREEZE_SCHEMA,
        "previous_failure_digest": original_report,
        "candidate_order": [_checked_proposal(root, c) for c in candidates],
        "phase": "training_candidates_frozen_before_validation",
        "source_role": "released_training",
        "human_patch_seen": False,
        "future_holdout_seen": False,
        "independent_evaluator_not_yet_run": True,
    }
    frozen = {**content, "freeze_digest": digest_of(content)}
    _write_new(freeze_path, frozen)
    return frozen


def _validated_outcome(outcome: Mapping[str, Any]) -> bool:
    """Full suite must be explicitly run and pass, not just trigger/compile."""
    return (
        outcome.get("compiled") is True
        and outcome.get("full_suite_ran") is True
        and outcome.get("full_suite_pass") is True
        and outcome.get("full_suite_failures") == 0
        and outcome.get("test_exit") == 0
    )


def validate_and_learn(
    *,
    root: Path,
    candidates: Sequence[Mapping[str, Any]],
    frozen: Mapping[str, Any],
    freeze_path: Path,
    previous_failure: Mapping[str, Any],
    evaluator: Callable[[str, str, str], Mapping[str, Any]],
    memory_path: Path,
    result_path: Path,
    role: str,
    context_lines: int = 1,
) -> dict[str, Any]:
    """Only an independently full-suite validated candidate may be distilled."""
    if role != "released_training" or frozen.get("source_role") != "released_training":
        raise G12GateError("cannot learn from an unreleased holdout")
    if frozen.get("schema") != FREEZE_SCHEMA:
        raise G12GateError("invalid freeze schema")
    unsigned = {k: v for k, v in frozen.items() if k != "freeze_digest"}
    if frozen.get("freeze_digest") != digest_of(unsigned):
        raise G12GateError("freeze checksum mismatch")
    if json.loads(freeze_path.read_text()) != dict(frozen):
        raise G12GateError("freeze on disk differs from signed candidate list")
    if frozen.get("previous_failure_digest") != previous_failure.get("report_digest"):
        raise G12GateError("previous failure provenance mismatch")
    if frozen.get("candidate_order") != [_checked_proposal(root, c) for c in candidates]:
        raise G12GateError("candidate changed after freeze")
    if result_path.exists() or memory_path.exists():
        raise G12GateError("do not overwrite a completed learning round")
    if not callable(evaluator):
        raise G12GateError("independent evaluator required")

    # The gap is diagnosed from the previous failure *before* any candidate
    # outcome is observed. This causal ordering is part of A6c memory.
    diagnosis = self_extension.diagnose_failure(
        root, previous_failure,
        target_prefixes=tuple(dict.fromkeys(c["path"] for c in candidates)),
    )
    if not diagnosis["operator_acquisition_recommended"]:
        raise G12GateError("failure report does not justify new capability")
    memory = self_extension.retain_gap(self_extension.empty_memory(), diagnosis)
    attempts: list[dict[str, Any]] = []
    promoted = None
    learned = None
    for record, candidate in zip(frozen["candidate_order"], candidates):
        try:
            feedback = dict(evaluator(
                record["path"], candidate["content_utf8"],
                record["expected_sha256"],
            ))
        except Exception as exc:
            # Failure of an evaluator is never evidence that a patch is wrong.
            feedback = {"error": "evaluator_exception:" + type(exc).__name__}
        # A validator must work on isolated copies. Never accept a result
        # from an evaluator that silently rewrote the training source.
        if _hash(_validated_path(root, record["path"]).read_text(encoding="utf-8")) != record["expected_sha256"]:
            raise G12GateError("evaluator mutated the original buggy source")
        passed = _validated_outcome(feedback)
        attempt = {
            "candidate_sha256": record["new_sha256"],
            "outcome": feedback,
            "validated_full_suite": passed,
        }
        attempts.append({**attempt, "attempt_digest": digest_of(attempt)})
        if passed:
            # The candidate source originates from Genesis planning, not a
            # revealed benchmark fix. The evaluator has seen only buggy source
            # plus proposed candidate, not a fixed-version checkout.
            one_file = {
                "mutations": [{
                    "path": record["path"], "expected_absent": False,
                    "content_utf8": candidate["content_utf8"],
                }]
            }
            receipt_body = {
                "candidate": record, "evaluator_outcome": feedback,
                "freeze_digest": frozen["freeze_digest"],
            }
            receipt_digest = digest_of(receipt_body)
            learned = self_extension.acquire_from_passing_candidate(
                memory, root, one_file, diagnosis=diagnosis,
                passing_result_digest=receipt_digest,
                context_lines=context_lines,
            )
            memory = learned["memory"]
            promoted = {
                "passed_candidate_sha256": record["new_sha256"],
                "evaluator_receipt_digest": receipt_digest,
                "operator_digests": learned["added_operator_digests"],
                "acquisition_digest": learned["acquisition"]["acquisition_digest"],
            }
            break

    if promoted is not None:
        # Verify the retained operation can generate the same change on the
        # source it learned from, with no further model calls.
        reuse = self_extension.generate_candidates(
            memory, root, include_prefixes=[promoted_path :=
                next(r["path"] for r in frozen["candidate_order"]
                     if r["new_sha256"] == promoted["passed_candidate_sha256"])],
            max_candidates=32,
        )
        generated = {
            _hash(m["content_utf8"])
            for c in reuse["candidate_set"]["candidates"]
            for m in c.get("mutations", [])
            if m.get("path") == promoted_path
        }
        if promoted["passed_candidate_sha256"] not in generated:
            raise G12GateError("learned operator did not replay validated patch")
        promoted["replay_verified_on_training_source"] = True
        promoted["reused_without_model_calls"] = reuse["external_model_calls"] == 0

    payload = {
        "schema": RECEIPT_SCHEMA,
        "frozen_candidates_digest": frozen["freeze_digest"],
        "original_failure_digest": previous_failure["report_digest"],
        "diagnosis_digest": diagnosis["diagnosis_digest"],
        "attempt_count": len(attempts),
        "attempts": attempts,
        "validated_operator_acquisition": promoted,
        "memory_generation": memory["generation"],
        "memory_digest": memory["memory_digest"],
        "source_role": "released_training",
        "independent_new_bug_successes": 0,
        "novel_semantic_operator_autonomously_invented": False,
        "learning_only_from_validated_candidate": promoted is not None,
        "operator_learning_external_model_calls": 0,
        "human_patch_accessed": False,
    }
    result = {**payload, "receipt_digest": digest_of(payload)}
    _write_new(result_path, result)
    _write_new(memory_path, memory)
    return result
