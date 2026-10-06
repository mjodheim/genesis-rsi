"""Deterministic component evolution for Genesis G6.

This apparatus turns evidence about a *limiting internal component* into actual
candidate descendant source code.  It is intentionally small, replayable and
zero-model-call.

The first evolution family targets an over-specific contextual matcher in the
universal operator IR.  It does not receive hidden qualification cases.  It is
allowed to use already-revealed prior-generation evidence (G5) as training
experience, generate several generic machinery variants, run retention/safety
checks on that prior evidence, and select the smallest passing descendant.

The resulting descendant is source-addressed and can be evaluated externally
against a fresh sealed holdout.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import difflib
import hashlib
import types
from typing import Any, Mapping, Sequence

from genesis.trust_root import digest_of

EVOLUTION_SCHEMA = "genesis-component-evolution-v1"
DESCENDANT_SCHEMA = "genesis-component-descendant-v1"
SELECTION_SCHEMA = "genesis-component-descendant-selection-v1"


@dataclass(frozen=True)
class TrainingExample:
    example_id: str
    path: str
    source: str
    should_emit: bool

    def record(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "path": self.path,
            "source_sha256": hashlib.sha256(self.source.encode("utf-8")).hexdigest(),
            "should_emit": self.should_emit,
        }


def _replace_function(source: str, function_name: str, replacement: str) -> str:
    tree = ast.parse(source)
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == function_name
        ),
        None,
    )
    if node is None or node.end_lineno is None:
        raise ValueError(f"function {function_name!r} not found")
    lines = source.splitlines(keepends=True)
    start = node.lineno - 1
    end = node.end_lineno
    normalized = replacement.rstrip() + "\n"
    return "".join(lines[:start]) + normalized + "".join(lines[end:])


def _candidate_functions() -> tuple[tuple[str, str, str], ...]:
    """Return generic matcher variants, ordered only by stable id."""
    return (
        (
            "drop_wildcard_identifier_anchors",
            "Remove wildcard identifier context from anchors while preserving "
            "literal/structural delimiters.",
            '''def _anchor_matches(
    tokens: Sequence[Mapping[str, Any]],
    index: int,
    operator: Mapping[str, Any],
) -> bool:
    left = [
        item
        for item in list(operator.get("left_anchor") or [])
        if not (
            str(item.get("kind")) == "identifier"
            and str(item.get("value")) == "*"
        )
    ]
    right = [
        item
        for item in list(operator.get("right_anchor") or [])
        if not (
            str(item.get("kind")) == "identifier"
            and str(item.get("value")) == "*"
        )
    ]
    if index < len(left) or index + 1 + len(right) > len(tokens):
        return False
    left_tokens = tokens[index - len(left):index] if left else []
    right_tokens = tokens[index + 1:index + 1 + len(right)]
    return all(_token_matches(token, pattern) for token, pattern in zip(left_tokens, left)) and all(
        _token_matches(token, pattern) for token, pattern in zip(right_tokens, right)
    )
''',
        ),
        (
            "semantic_role_fallback",
            "Keep exact anchors first, then admit a token when the learned "
            "semantic role still matches.",
            '''def _anchor_matches(
    tokens: Sequence[Mapping[str, Any]],
    index: int,
    operator: Mapping[str, Any],
) -> bool:
    left = list(operator.get("left_anchor") or [])
    right = list(operator.get("right_anchor") or [])
    exact = False
    if index >= len(left) and index + 1 + len(right) <= len(tokens):
        left_tokens = tokens[index - len(left):index]
        right_tokens = tokens[index + 1:index + 1 + len(right)]
        exact = all(
            _token_matches(token, pattern)
            for token, pattern in zip(left_tokens, left)
        ) and all(
            _token_matches(token, pattern)
            for token, pattern in zip(right_tokens, right)
        )
    if exact:
        return True
    expected_role = str(operator.get("semantic_role") or "")
    return bool(expected_role) and _semantic_role(tokens, index) == expected_role
''',
        ),
        (
            "structural_delimiter_anchors",
            "Retain only punctuation delimiters from learned local anchors.",
            '''def _anchor_matches(
    tokens: Sequence[Mapping[str, Any]],
    index: int,
    operator: Mapping[str, Any],
) -> bool:
    left = [
        item for item in list(operator.get("left_anchor") or [])
        if str(item.get("kind")) == "punctuation"
    ]
    right = [
        item for item in list(operator.get("right_anchor") or [])
        if str(item.get("kind")) == "punctuation"
    ]
    if not left and not right:
        return False
    if index < len(left) or index + 1 + len(right) > len(tokens):
        return False
    left_tokens = tokens[index - len(left):index] if left else []
    right_tokens = tokens[index + 1:index + 1 + len(right)]
    return all(_token_matches(token, pattern) for token, pattern in zip(left_tokens, left)) and all(
        _token_matches(token, pattern) for token, pattern in zip(right_tokens, right)
    )
''',
        ),
    )


def _load_module(source: str, module_name: str) -> types.ModuleType:
    module = types.ModuleType(module_name)
    module.__file__ = f"<{module_name}>"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _diff_size(parent_source: str, descendant_source: str) -> int:
    diff = difflib.unified_diff(
        parent_source.splitlines(),
        descendant_source.splitlines(),
        lineterm="",
    )
    return sum(1 for line in diff if line.startswith("+") or line.startswith("-"))


def diagnose_context_overfit(
    parent_source: str,
    operator: Mapping[str, Any],
    failed_example: TrainingExample,
) -> dict[str, Any]:
    """Detect same-role/no-candidate evidence without knowing a hidden solution."""
    module = _load_module(parent_source, "genesis_parent_diagnosis")
    outputs = module.materialize_source(
        failed_example.source,
        path=failed_example.path,
        operator=operator,
    )
    document = module.substrate.inspect_source(
        failed_example.source,
        path=failed_example.path,
    )
    old = dict(operator["from_token"])
    expected_role = str(operator.get("semantic_role") or "")
    same_role_tokens = 0
    for index, token in enumerate(document["tokens"]):
        if not module._token_matches(token, old):
            continue
        if module._semantic_role(document["tokens"], index) == expected_role:
            same_role_tokens += 1

    payload = {
        "parent_source_sha256": hashlib.sha256(parent_source.encode("utf-8")).hexdigest(),
        "operator_digest": operator.get("operator_digest"),
        "failed_example": failed_example.record(),
        "parent_candidate_count": len(outputs),
        "same_semantic_role_token_count": same_role_tokens,
        "diagnosis": (
            "anchor_context_over_specific"
            if len(outputs) == 0 and same_role_tokens > 0
            else "not_established"
        ),
        "hidden_holdout_visible": False,
        "external_model_calls": 0,
    }
    return {**payload, "diagnosis_digest": digest_of(payload)}


def generate_descendants(
    parent_source: str,
    *,
    operator: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if diagnosis.get("diagnosis") != "anchor_context_over_specific":
        raise ValueError("evolution requires an established anchor-context overfit")
    descendants: list[dict[str, Any]] = []
    parent_sha = hashlib.sha256(parent_source.encode("utf-8")).hexdigest()

    for mutation_id, rationale, replacement in _candidate_functions():
        source = _replace_function(parent_source, "_anchor_matches", replacement)
        source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if source_sha == parent_sha:
            continue
        payload = {
            "schema": DESCENDANT_SCHEMA,
            "component_id": "universal_operator_ir",
            "mutation_id": mutation_id,
            "rationale": rationale,
            "parent_source_sha256": parent_sha,
            "source_sha256": source_sha,
            "source_utf8": source,
            "operator_digest": operator.get("operator_digest"),
            "diagnosis_digest": diagnosis.get("diagnosis_digest"),
            "diff_size": _diff_size(parent_source, source),
            "external_model_calls_for_generation": 0,
        }
        descendants.append({**payload, "descendant_digest": digest_of(payload)})
    return descendants


def evaluate_training_examples(
    descendant: Mapping[str, Any],
    *,
    operator: Mapping[str, Any],
    examples: Sequence[TrainingExample],
) -> dict[str, Any]:
    module = _load_module(
        str(descendant["source_utf8"]),
        f"genesis_descendant_{str(descendant['mutation_id'])}",
    )
    records: list[dict[str, Any]] = []
    passed = 0
    for example in examples:
        outputs = module.materialize_source(
            example.source,
            path=example.path,
            operator=operator,
        )
        emits = len(outputs) > 0
        correct = emits == example.should_emit
        passed += int(correct)
        records.append({
            **example.record(),
            "candidate_count": len(outputs),
            "correct": correct,
        })
    payload = {
        "descendant_digest": descendant["descendant_digest"],
        "example_count": len(examples),
        "passed": passed,
        "all_passed": passed == len(examples),
        "examples": records,
        "external_model_calls": 0,
    }
    return {**payload, "training_result_digest": digest_of(payload)}


def evolve_component(
    parent_source: str,
    *,
    operator: Mapping[str, Any],
    failed_example: TrainingExample,
    training_examples: Sequence[TrainingExample],
) -> dict[str, Any]:
    """Generate and select a material descendant using only prior evidence."""
    diagnosis = diagnose_context_overfit(
        parent_source,
        operator,
        failed_example,
    )
    descendants = generate_descendants(
        parent_source,
        operator=operator,
        diagnosis=diagnosis,
    )
    evaluations = [
        evaluate_training_examples(
            descendant,
            operator=operator,
            examples=training_examples,
        )
        for descendant in descendants
    ]
    by_digest = {
        item["descendant_digest"]: item
        for item in descendants
    }
    ranked = sorted(
        evaluations,
        key=lambda result: (
            -int(result["passed"]),
            int(by_digest[result["descendant_digest"]]["diff_size"]),
            str(by_digest[result["descendant_digest"]]["mutation_id"]),
        ),
    )
    if not ranked or not ranked[0]["all_passed"]:
        raise RuntimeError("no generated descendant preserves the required training behavior")
    winner_eval = ranked[0]
    winner = by_digest[winner_eval["descendant_digest"]]

    payload = {
        "schema": SELECTION_SCHEMA,
        "component_id": "universal_operator_ir",
        "diagnosis": diagnosis,
        "candidate_count": len(descendants),
        "candidates": [
            {
                "descendant_digest": descendant["descendant_digest"],
                "mutation_id": descendant["mutation_id"],
                "source_sha256": descendant["source_sha256"],
                "diff_size": descendant["diff_size"],
                "training": next(
                    item for item in evaluations
                    if item["descendant_digest"] == descendant["descendant_digest"]
                ),
            }
            for descendant in descendants
        ],
        "selected_descendant": winner,
        "selection_rule": "maximize_training_passes_then_minimize_source_diff_then_stable_mutation_id",
        "training_evidence_only": True,
        "hidden_holdout_visible": False,
        "external_model_calls": 0,
    }
    return {**payload, "selection_digest": digest_of(payload)}
