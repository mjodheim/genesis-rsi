"""Generalize a missing early guard from two sibling Java methods.

A family of methods that share a return type and parameter type can share
semantic precondition handling. If two siblings use the *same* simple guard
and return an in-class constant, but another sibling omits that guard, propose
inserting it after the method's existing argument-null check.

The candidate remains a hypothesis, not a validated patch. No defect IDs,
test cases, class names, exact constants or human solutions are embedded.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from collections import defaultdict
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-sibling-guard-transfer-v1"
ID = r"[A-Za-z_$][A-Za-z0-9_$]*"
METHOD = re.compile(
    r"\b(?:public|protected|private)\s+(?:(?:static|final|synchronized)\s+)*"
    r"(?P<rtype>"+ID+r")\s+(?P<method>"+ID+r")\s*"
    r"\(\s*(?:final\s+)?(?P<argtype>"+ID+r")\s+(?P<arg>"+ID+r")\s*\)"
    r"\s*(?:throws\s+"+ID+r"(?:\s*,\s*"+ID+r")*)?\s*\{",
)
GUARD = re.compile(
    r"\bif\s*\(\s*(?P<receiver>"+ID+r")\s*(?P<logic>\|\||&&)\s*"
    r"(?P<arg>"+ID+r")\.(?P<flag>"+ID+r")\s*\)\s*"
    r"\{\s*return\s+(?P<const>"+ID+r")\s*;\s*\}",
)
NULL_CHECK = re.compile(
    r"^\s*(?:(?:"+ID+r")\.)?"+ID+r"\.checkNotNull\s*\(\s*(?P<arg>"+ID+r")\s*\)\s*;",
)
SCOPED = re.compile(r"\b(?:return|new)\s+(?P<token>"+ID+r")\s*;")


def _mask_literals_and_comments(source: str) -> str:
    chars = list(source)
    state = "code"
    index = 0
    while index < len(chars):
        ch = chars[index]
        next_ch = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if ch == "/" and next_ch == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line"
                continue
            if ch == "/" and next_ch == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block"
                continue
            if ch in ('"', "'"):
                state = "string" if ch == '"' else "char"
                chars[index] = " "
                index += 1
                continue
        elif state == "line":
            if ch == "\n":
                state = "code"
            else:
                chars[index] = " "
            index += 1
            continue
        elif state == "block":
            if ch == "*" and next_ch == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if ch != "\n":
                chars[index] = " "
            index += 1
            continue
        else:
            if ch == "\\" and next_ch:
                if ch != "\n":
                    chars[index] = " "
                if next_ch != "\n":
                    chars[index + 1] = " "
                index += 2
                continue
            if ch == ('"' if state == "string" else "'"):
                state = "code"
            if ch != "\n":
                chars[index] = " "
            index += 1
            continue
        index += 1
    return "".join(chars)


def _closing_brace(masked: str, open_brace: int) -> int | None:
    depth = 0
    for index in range(open_brace, len(masked)):
        c = masked[index]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _methods(masked: str) -> list[dict[str, Any]]:
    result = []
    for match in METHOD.finditer(masked):
        end = _closing_brace(masked, match.end() - 1)
        if end is None:
            continue
        result.append({
            **match.groupdict(),
            "body_start": match.end(),
            "body_end": end,
            "body": masked[match.end():end],
        })
    return result


def _variants(relative: str, source: str) -> list[dict[str, Any]]:
    masked = _mask_literals_and_comments(source)
    methods = _methods(masked)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for method in methods:
        groups[(method["rtype"], method["argtype"])].append(method)
    variants = []
    seen = set()
    for (rtype, argtype), siblings in sorted(groups.items()):
        if len(siblings) < 3:
            continue
        donors: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for method in siblings:
            if (re.search(r"\b"+re.escape(method["arg"])+r"\s*\.", method["body"]) is None
                    or re.search(r"\breturn\b", method["body"]) is None):
                continue
            for match in GUARD.finditer(method["body"]):
                if match["arg"] != method["arg"]:
                    continue
                if (not match["receiver"].startswith("is")
                        or not match["flag"].startswith("is")):
                    continue
                # Distill a portable pattern, independent of the source
                # parameter variable's spelling (rhs, other, value, ...).
                key = (match["receiver"], match["flag"], match["const"])
                donors[key].add(method["method"])
        patterns = sorted(
            key for key, names in donors.items() if len(names) >= 2
        )
        for method in siblings:
            body = method["body"]
            for state_field, flag, constant in patterns:
                if method["method"] in donors[(state_field, flag, constant)]:
                    continue
                # The target must use the same argument and have the expected
                # source-local computation form. This avoids completely
                # unrelated "return NaN" edits.
                if (re.search(r"\b"+re.escape(method["arg"])+r"\.", body) is None
                        or "return" not in body):
                    continue
                if re.search(r"\bif\s*\(\s*"+re.escape(state_field)+r"\b", body):
                    continue
                insertion = method["body_start"]
                first = NULL_CHECK.match(body)
                if first and first["arg"] == method["arg"]:
                    insertion += first.end()
                original = source
                indent = "        "
                new_statement = (
                    f"\n{indent}if ({state_field} || {method['arg']}.{flag}) {{\n"
                    f"{indent}    return {constant};\n{indent}}}\n"
                )
                changed = original[:insertion] + new_statement + original[insertion:]
                key_sha = hashlib.sha256(changed.encode()).hexdigest()
                if key_sha in seen:
                    continue
                seen.add(key_sha)
                content = {
                    "schema": SCHEMA,
                    "path": relative,
                    "operator": "java_transfer_sibling_invalid_state_guard",
                    "expected_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "content_sha256": key_sha,
                    "donor_method_count": len(donors[(state_field, flag, constant)]),
                    "target_method": method["method"],
                    "source_line": original.count("\n", 0, insertion) + 1,
                }
                cd = digest_of(content)
                variants.append({
                    "id": "java-guard-"+cd[:16],
                    "candidate_digest": cd,
                    "path": relative,
                    "operator": "java_transfer_sibling_invalid_state_guard",
                    "expected_sha256": content["expected_sha256"],
                    "content_utf8": changed,
                    "detail": {
                        "mode": "transfer_sibling_early_state_guard",
                        "donor_method_count": content["donor_method_count"],
                        "site_count": 1,
                        "operator_source": "sibling_methods_in_buggy_source",
                        "source_line": content["source_line"],
                    },
                    "external_model_calls": 0,
                })
    return variants


def generate(
    root: str | Path, *, include_prefixes: Sequence[str] = (), max_candidates: int = 64
) -> dict[str, Any]:
    if not (1 <= max_candidates <= 500):
        raise ValueError("max_candidates outside [1,500]")
    base = Path(root).resolve(strict=True)
    wanted = tuple(str(p).strip("/") for p in include_prefixes if str(p).strip("/"))
    variants = []
    for file in sorted(base.rglob("*.java")):
        rel = file.relative_to(base).as_posix()
        if (not file.is_file() or file.stat().st_size > 512_000
                or any(part in (".git", "target", "build", "test", "tests")
                       for part in file.relative_to(base).parts[:-1])):
            continue
        if wanted and not any(rel == key or rel.startswith(key + "/") for key in wanted):
            continue
        variants.extend(_variants(rel, file.read_text(encoding="utf-8")))
        if len(variants) >= max_candidates:
            variants = variants[:max_candidates]
            break
    payload = {
        "schema": SCHEMA,
        "candidate_count": len(variants),
        "candidates": variants,
        "external_model_calls": 0,
    }
    return {**payload, "result_digest": digest_of(payload)}
