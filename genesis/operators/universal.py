"""Language-neutral learned operators for Genesis G2.

The first universal operator family is intentionally small: a validated one-token
structural change is learned once, expressed without source-language identifiers,
and then materialized against compatible structural contexts in other languages.

This is not a repair cookbook.  The operation is derived from a previously
validated before/after pair and retains exact provenance to that outcome.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis.languages import substrate
from genesis.trust_root import digest_of

OPERATOR_SCHEMA = "genesis-universal-operator-v1"
CANDIDATE_SET_SCHEMA = "genesis-universal-operator-candidates-v1"

_IGNORED_PARTS = {
    ".git", ".gradle", ".idea", ".pytest_cache", ".venv", "__pycache__",
    "bin", "build", "coverage", "dist", "node_modules", "obj", "target", "venv",
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _descriptor(token: Mapping[str, Any]) -> dict[str, str]:
    kind = str(token["kind"])
    value = str(token["value"])
    if kind == "identifier":
        return {"kind": "identifier", "value": "*"}
    return {"kind": kind, "value": value}


def _token_matches(token: Mapping[str, Any], descriptor: Mapping[str, Any]) -> bool:
    if str(token.get("kind")) != str(descriptor.get("kind")):
        return False
    expected = str(descriptor.get("value"))
    return expected == "*" or str(token.get("value")) == expected


def _semantic_role(tokens: Sequence[Mapping[str, Any]], index: int) -> str:
    left = str(tokens[index - 1]["value"]) if index > 0 else ""
    right = str(tokens[index + 1]["value"]) if index + 1 < len(tokens) else ""
    if left == "[" and right == "]":
        return "subscript_index"
    if str(tokens[index]["kind"]) == "operator":
        return "operator"
    depth = 0
    for token in reversed(tokens[:index]):
        value = str(token["value"])
        if value == ")":
            depth += 1
        elif value == "(":
            if depth == 0:
                return "call_argument"
            depth -= 1
    return "literal_or_token"


def validate_operator(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != OPERATOR_SCHEMA:
        raise ValueError("unsupported universal operator schema")
    value = dict(record)
    recorded = str(value.pop("operator_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise ValueError("universal operator does not reproduce its digest")
    return dict(record)


def learn_from_validated_pair(
    before_source: str,
    after_source: str,
    *,
    source_path: str,
    source_result_digest: str,
    anchor_width: int = 2,
) -> dict[str, Any]:
    """Learn one language-neutral token replacement from a passing outcome."""
    if not source_result_digest:
        raise ValueError("source_result_digest is required")
    if anchor_width < 1 or anchor_width > 4:
        raise ValueError("anchor_width must be in [1, 4]")

    before_doc = substrate.inspect_source(before_source, path=source_path)
    after_doc = substrate.inspect_source(after_source, path=source_path)
    if not before_doc["parse_ok"] or not after_doc["parse_ok"]:
        raise ValueError("universal operator learning requires structurally valid source")

    before_tokens = list(before_doc["tokens"])
    after_tokens = list(after_doc["tokens"])
    matcher = SequenceMatcher(
        a=[(item["kind"], item["value"]) for item in before_tokens],
        b=[(item["kind"], item["value"]) for item in after_tokens],
        autojunk=False,
    )
    changed = [item for item in matcher.get_opcodes() if item[0] != "equal"]
    if len(changed) != 1:
        raise ValueError("first universal operator family requires exactly one token change")
    tag, i1, i2, j1, j2 = changed[0]
    if tag != "replace" or i2 - i1 != 1 or j2 - j1 != 1:
        raise ValueError("first universal operator family requires one-token replacement")

    old = before_tokens[i1]
    new = after_tokens[j1]
    compatible_kinds = {"number", "string", "operator", "keyword", "identifier"}
    if str(old["kind"]) not in compatible_kinds or str(new["kind"]) not in compatible_kinds:
        raise ValueError("unsupported universal token kind")
    if str(old["kind"]) != str(new["kind"]) and not {
        str(old["kind"]), str(new["kind"])
    } <= {"keyword", "identifier"}:
        raise ValueError("token replacement changes incompatible semantic kinds")

    payload = {
        "schema": OPERATOR_SCHEMA,
        "operation": "replace_token",
        "semantic_role": _semantic_role(before_tokens, i1),
        "from_token": {"kind": str(old["kind"]), "value": str(old["value"])},
        "to_token": {"kind": str(new["kind"]), "value": str(new["value"])},
        "left_anchor": [
            _descriptor(item)
            for item in before_tokens[max(0, i1 - anchor_width):i1]
        ],
        "right_anchor": [
            _descriptor(item)
            for item in before_tokens[i2:i2 + anchor_width]
        ],
        "source_language": before_doc["language"],
        "source_path": source_path,
        "source_document_digest": before_doc["document_digest"],
        "source_result_digest": str(source_result_digest),
        "anchor_width": anchor_width,
        "external_model_calls_for_learning": 0,
    }
    return {**payload, "operator_digest": digest_of(payload)}


def _anchor_matches(
    tokens: Sequence[Mapping[str, Any]],
    index: int,
    operator: Mapping[str, Any],
) -> bool:
    left = list(operator.get("left_anchor") or [])
    right = list(operator.get("right_anchor") or [])
    if index < len(left) or index + 1 + len(right) > len(tokens):
        return False
    left_tokens = tokens[index - len(left):index]
    right_tokens = tokens[index + 1:index + 1 + len(right)]
    return all(_token_matches(token, pattern) for token, pattern in zip(left_tokens, left)) and all(
        _token_matches(token, pattern) for token, pattern in zip(right_tokens, right)
    )


def materialize_source(
    source: str,
    *,
    path: str,
    operator: Mapping[str, Any],
    max_outputs: int = 32,
) -> tuple[str, ...]:
    """Materialize a learned operation in any supported language context."""
    held = validate_operator(operator)
    document = substrate.inspect_source(source, path=path)
    if not document["parse_ok"]:
        return ()
    tokens = list(document["tokens"])
    old = dict(held["from_token"])
    new = dict(held["to_token"])
    outputs: list[str] = []
    for index, token in enumerate(tokens):
        if not _token_matches(token, old) or not _anchor_matches(tokens, index, held):
            continue
        start = int(token["start"])
        end = int(token["end"])
        mutated = source[:start] + str(new["value"]) + source[end:]
        try:
            parsed = substrate.inspect_source(mutated, path=path)
        except ValueError:
            continue
        if parsed["parse_ok"] and mutated != source and mutated not in outputs:
            outputs.append(mutated)
        if len(outputs) >= max_outputs:
            break
    return tuple(outputs)


def _in_scope(relative: str, prefixes: Sequence[str]) -> bool:
    wanted = tuple(str(item).strip("/") for item in prefixes if str(item).strip("/"))
    if not wanted:
        return True
    return any(relative == prefix or relative.startswith(prefix + "/") for prefix in wanted)


def generate(
    root: str | Path,
    operators: Sequence[Mapping[str, Any]],
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 256,
) -> dict[str, Any]:
    """Generate cross-language candidates from retained universal operators."""
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    candidates: list[dict[str, Any]] = []

    for path in sorted(base.rglob("*")):
        if not path.is_file() or substrate.language_for_path(path) is None:
            continue
        relative_path = path.relative_to(base)
        if any(part in _IGNORED_PARTS for part in relative_path.parts[:-1]):
            continue
        relative = relative_path.as_posix()
        if not _in_scope(relative, include_prefixes) or path.stat().st_size > 512_000:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        expected = _sha256_text(original)
        target_language = substrate.language_for_path(relative)

        for raw_operator in operators:
            operator = validate_operator(raw_operator)
            for mutated in materialize_source(original, path=relative, operator=operator):
                payload = {
                    "path": relative,
                    "operator_digest": operator["operator_digest"],
                    "expected_sha256": expected,
                    "content_sha256": _sha256_text(mutated),
                    "target_language": target_language,
                }
                candidate_digest = digest_of(payload)
                candidates.append({
                    "id": f"universal-{candidate_digest[:16]}",
                    "label": f"universal_operator:{relative}",
                    "provenance": {
                        "generator": "universal_operator_ir",
                        "operator": operator["semantic_role"],
                        "operator_digest": operator["operator_digest"],
                        "source_language": operator["source_language"],
                        "source_result_digest": operator["source_result_digest"],
                        "target_language": target_language,
                        "strategy_origin": "prior_passing_evaluated_cross_language_abstraction",
                        "external_model_calls": 0,
                    },
                    "mutations": [{
                        "path": relative,
                        "expected_sha256": expected,
                        "expected_absent": False,
                        "content_utf8": mutated,
                    }],
                    "candidate_digest": candidate_digest,
                })
                if len(candidates) >= max_candidates:
                    return {
                        "schema": CANDIDATE_SET_SCHEMA,
                        "candidate_count": len(candidates),
                        "truncated": True,
                        "external_model_calls": 0,
                        "candidates": candidates,
                    }

    return {
        "schema": CANDIDATE_SET_SCHEMA,
        "candidate_count": len(candidates),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": candidates,
    }
