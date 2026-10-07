"""Generic guarded default-normalization hoisting.

Learns a dataflow-order repair from source structure: when an optional value
is conditionally used earlier in a method but resolved to a default only later,
move the default resolution before the earlier use, make that use unconditional,
and delete the now-redundant late default block. The same structural repair can
be coordinated across sibling methods.

No repository, class, method, type, variable, issue, test, commit, or line
identity is encoded.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-default-before-use-mutation-set-v1"

_METHOD = re.compile(
    r"(?P<head>(?:public|protected|private|static|final|synchronized|native|abstract|\s)+"
    r"[A-Za-z_$][A-Za-z0-9_$<>\[\]., ?]*\s+[A-Za-z_$][A-Za-z0-9_$]*\s*"
    r"\([^)]*\)\s*(?:throws\s+[^\{]+)?\{)",
    re.MULTILINE,
)
_NONNULL_IF = re.compile(
    r"(?m)^(?P<indent>[ \t]*)if\s*\(\s*(?P<var>[A-Za-z_$][A-Za-z0-9_$]*)\s*!=\s*null\s*\)\s*\{"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _block_span(text: str, open_brace: int) -> tuple[int, int] | None:
    depth = 0
    in_string = False
    in_char = False
    escaped = False
    for pos in range(open_brace, len(text)):
        ch = text[pos]
        if escaped:
            escaped = False
            continue
        if ch == "\\" and (in_string or in_char):
            escaped = True
            continue
        if ch == '"' and not in_char:
            in_string = not in_string
            continue
        if ch == "'" and not in_string:
            in_char = not in_char
            continue
        if in_string or in_char:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, pos
    return None


def _eligible_java_files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    wanted = tuple(str(x).strip("/") for x in prefixes if str(x).strip("/"))
    out: list[Path] = []
    for p in root.rglob("*.java"):
        if not p.is_file() or p.stat().st_size > 512_000:
            continue
        rel = p.relative_to(root)
        if any(part in {".git", "target", "build", "test", "tests"} for part in rel.parts[:-1]):
            continue
        s = rel.as_posix()
        if wanted and not any(s == x or s.startswith(x + "/") for x in wanted):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _dedent_block(body: str, outer_indent: str) -> str:
    lines = body.splitlines(keepends=True)
    nonblank = [line for line in lines if line.strip()]
    if not nonblank:
        return ""
    cut = min(len(line) - len(line.lstrip(" \t")) for line in nonblank)
    return "".join(
        line if not line.strip() else outer_indent + line[cut:]
        for line in lines
    )


def _method_repairs(text: str) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for method_index, mm in enumerate(_METHOD.finditer(text)):
        brace = text.find("{", mm.start("head"), mm.end("head"))
        span = _block_span(text, brace)
        if not span:
            continue
        body_start, body_end = span
        body = text[body_start:body_end]

        for early in _NONNULL_IF.finditer(body):
            var = early.group("var")
            early_brace = body.find("{", early.start(), early.end())
            early_span = _block_span(body, early_brace)
            if not early_span:
                continue
            early_body_start, early_body_end = early_span
            early_body = body[early_body_start:early_body_end]
            if not re.search(rf"\b{re.escape(var)}\b", early_body):
                continue
            if len([x for x in early_body.splitlines() if x.strip()]) > 4:
                continue

            null_if = re.compile(
                rf"(?m)^(?P<indent>[ \t]*)if\s*\(\s*{re.escape(var)}\s*==\s*null\s*\)\s*\{{"
            )
            for late in null_if.finditer(body, early_body_end):
                late_brace = body.find("{", late.start(), late.end())
                late_span = _block_span(body, late_brace)
                if not late_span:
                    continue
                late_body_start, late_body_end = late_span
                late_body = body[late_body_start:late_body_end]
                assign = re.fullmatch(
                    rf"\s*{re.escape(var)}\s*=\s*(?P<expr>[^;]+);\s*",
                    late_body,
                    re.DOTALL,
                )
                if not assign:
                    continue
                default_expr = assign.group("expr").strip()
                if not default_expr or re.search(rf"\b{re.escape(var)}\b", default_expr):
                    continue

                early_indent = early.group("indent")
                normalized_use = _dedent_block(early_body, early_indent)
                if not normalized_use.strip():
                    continue
                replacement = (
                    f"{early_indent}if ({var} == null) {{\n"
                    f"{early_indent}    {var} = {default_expr};\n"
                    f"{early_indent}}}\n"
                    f"{normalized_use.rstrip()}\n"
                )

                early_abs_start = body_start + early.start()
                early_abs_end = body_start + early_span[1] + 1
                late_abs_start = body_start + late.start()
                late_abs_end = body_start + late_span[1] + 1
                if late_abs_end < body_end and text[late_abs_end:late_abs_end + 1] == "\n":
                    late_abs_end += 1

                repairs.append({
                    "method_index": method_index,
                    "var": var,
                    "default_expr": default_expr,
                    "use_shape": re.sub(rf"\b{re.escape(var)}\b", "$VAR", early_body.strip()),
                    "default_shape": re.sub(rf"\b{re.escape(var)}\b", "$VAR", default_expr),
                    "edits": [
                        (early_abs_start, early_abs_end, replacement),
                        (late_abs_start, late_abs_end, ""),
                    ],
                })
                break
    return repairs


def _apply(text: str, edits: Sequence[tuple[int, int, str]]) -> str:
    out = text
    for start, end, replacement in sorted(
        edits, key=lambda x: (x[0], x[1]), reverse=True
    ):
        out = out[:start] + replacement + out[end:]
    return out


def _candidate(
    relative: str,
    before: str,
    after: str,
    repairs: Sequence[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    desc = [{
        "method_index": r["method_index"],
        "default_shape": r["default_shape"],
        "use_shape": r["use_shape"],
    } for r in repairs]
    payload = {
        "path": relative,
        "operator": "java_default_before_use_hoist",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "mode": mode,
        "repairs": desc,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-default-hoist-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_default_before_use_hoist",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "mode": mode,
            "site_count": len(repairs),
            "repairs": desc,
            "strategy_origin": "source_local_nullable_default_after_earlier_conditional_use",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    repairs = _method_repairs(text)
    if not repairs:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for repair in repairs:
        mutated = _apply(text, repair["edits"])
        key = _sha(mutated)
        if key not in seen:
            seen.add(key)
            out.append(_candidate(relative, text, mutated, [repair], "single_method"))

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for repair in repairs:
        groups.setdefault(
            (repair["default_shape"], repair["use_shape"]), []
        ).append(repair)

    coordinated_out: list[dict[str, Any]] = []
    for group in groups.values():
        by_method: dict[int, dict[str, Any]] = {}
        for repair in group:
            by_method.setdefault(repair["method_index"], repair)
        siblings = list(by_method.values())
        if len(siblings) < 2:
            continue
        # Try bounded subsets rather than assuming every analogous sibling is
        # defective. Pairwise plans come first; the full group remains an
        # available hypothesis when three or more methods match.
        max_size = min(3, len(siblings))
        for size in range(2, max_size + 1):
            for coordinated_tuple in combinations(siblings, size):
                coordinated = list(coordinated_tuple)
                edits = [edit for repair in coordinated for edit in repair["edits"]]
                mutated = _apply(text, edits)
                key = _sha(mutated)
                if key in seen:
                    continue
                seen.add(key)
                coordinated_out.append(
                    _candidate(
                        relative,
                        text,
                        mutated,
                        coordinated,
                        "coordinated_sibling_methods",
                    )
                )
    out = coordinated_out + out
    return out


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 4096,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(
            f"project root does not exist or is not a directory: {base}"
        )

    files = _eligible_java_files(base, include_prefixes)
    per_file: list[list[dict[str, Any]]] = []
    for path in files:
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        candidates = _file_candidates(rel, text)
        if candidates:
            per_file.append(candidates)

    out: list[dict[str, Any]] = []
    round_index = 0
    while len(out) < max_candidates:
        progress = False
        for items in per_file:
            if round_index >= len(items):
                continue
            progress = True
            rec = dict(items[round_index])
            rec["index"] = len(out)
            out.append(rec)
            if len(out) >= max_candidates:
                break
        if not progress:
            break
        round_index += 1

    payload = {
        "schema": SCHEMA,
        "candidate_count": len(out),
        "eligible_source_file_count": len(files),
        "scheduled_source_file_count": len(per_file),
        "scheduling": "round_robin_by_source_file_with_coordinated_default_hoist_first",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
