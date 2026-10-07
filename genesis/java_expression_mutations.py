"""Generic coordinated Java builder-capacity expression rewrites.

ER1-J9 showed that a repair may require the same expression rewrite in
multiple sibling methods.  This primitive recognizes a broader structural
pattern: a method computes an item count from an index range, but sizes a
builder from only the first element (possibly plus separator overhead).

The candidate replaces that first-item-dependent estimate by a count-scaled
fallback estimate.  It emits both single-site variants and coordinated
same-file variants across structurally compatible sibling methods.

No repository, class, method, issue, test, commit, line, identifier, or
literal value is hard-coded.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-coordinated-builder-capacity-v1"

_METHOD = re.compile(
    r"(?P<head>(?:public|protected|private|static|final|synchronized|native|abstract|\s)+"
    r"[A-Za-z_$][A-Za-z0-9_$<>\[\]., ?]*\s+[A-Za-z_$][A-Za-z0-9_$]*\s*"
    r"\([^)]*\)\s*(?:throws\s+[^\{]+)?\{)",
    re.MULTILINE,
)
_COUNT = re.compile(
    r"(?m)^[ \t]*(?:final\s+)?int\s+(?P<count>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(?\s*"
    r"(?P<end>[A-Za-z_$][A-Za-z0-9_$]*)\s*-\s*(?P<start>[A-Za-z_$][A-Za-z0-9_$]*)\s*\)?\s*;"
)
_BUILDER = re.compile(
    r"new\s+(?P<type>StringBuilder|StringBuffer)\s*\((?P<expr>[^;]+?)\)\s*;"
)
_TERNARY_FALLBACK = re.compile(r"\?\s*(?P<const>[1-9][0-9]{0,4})\s*:")
_INDEXED = re.compile(
    r"\b(?P<array>[A-Za-z_$][A-Za-z0-9_$]*)\s*\[\s*(?P<index>[A-Za-z_$][A-Za-z0-9_$]*)\s*\]"
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


def _site_candidates(text: str) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    for method_index, mm in enumerate(_METHOD.finditer(text)):
        brace = text.find("{", mm.start("head"), mm.end("head"))
        span = _block_span(text, brace)
        if not span:
            continue
        body_start, body_end = span
        body = text[body_start:body_end]
        counts = list(_COUNT.finditer(body))
        if not counts:
            continue

        for count_match in counts:
            count = count_match.group("count")
            start = count_match.group("start")
            end = count_match.group("end")

            # A count must participate in the usual empty-range guard; this
            # keeps the rewrite tied to sequence-size semantics.
            if not re.search(rf"\b{re.escape(count)}\s*(?:<=|==|<)\s*0\b", body):
                continue

            for builder in _BUILDER.finditer(body):
                expr = builder.group("expr")
                indexed = list(_INDEXED.finditer(expr))
                if not indexed:
                    continue
                # The old estimate must depend on the first selected element.
                if not any(m.group("index") == start for m in indexed):
                    continue
                fallback = _TERNARY_FALLBACK.search(expr)
                if not fallback:
                    continue
                default_width = int(fallback.group("const"))
                if default_width < 1:
                    continue

                expr_abs_start = body_start + builder.start("expr")
                expr_abs_end = body_start + builder.end("expr")

                # Candidate A is deliberately simple and safe: scale the
                # source-local fallback estimate by the already-computed count.
                replacements = [f"{count} * {default_width}"]

                # Candidate B preserves source-local separator-size evidence if
                # the original estimate contains one.  It is an alternative,
                # never a privileged benchmark-specific form.
                sep = re.search(
                    r"\+\s*(?P<sep>[A-Za-z_$][A-Za-z0-9_$]*)\.length\(\)",
                    expr,
                )
                if sep:
                    replacements.append(
                        f"{count} * ({default_width} + {sep.group('sep')}.length())"
                    )

                for replacement in replacements:
                    if replacement == expr.strip():
                        continue
                    sites.append(
                        {
                            "method_index": method_index,
                            "count": count,
                            "start_var": start,
                            "end_var": end,
                            "builder_type": builder.group("type"),
                            "default_width": default_width,
                            "start": expr_abs_start,
                            "end": expr_abs_end,
                            "before": expr,
                            "after": replacement,
                        }
                    )
    return sites


def _candidate(relative: str, before: str, after: str, *, sites: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    descriptor = [
        {
            "method_index": s["method_index"],
            "builder_type": s["builder_type"],
            "default_width": s["default_width"],
            "count": s["count"],
            "start_var": s["start_var"],
            "end_var": s["end_var"],
            "replacement": s["after"],
        }
        for s in sites
    ]
    payload = {
        "path": relative,
        "operator": "java_builder_capacity_count_scale",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "mode": mode,
        "sites": descriptor,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-expr-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_builder_capacity_count_scale",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "mode": mode,
            "site_count": len(sites),
            "sites": descriptor,
            "strategy_origin": "source_local_count_range_plus_first_element_capacity_estimate",
        },
        "external_model_calls": 0,
    }


def _apply_sites(text: str, sites: Sequence[dict[str, Any]]) -> str:
    out = text
    for site in sorted(sites, key=lambda s: (s["start"], s["end"]), reverse=True):
        out = out[: site["start"]] + site["after"] + out[site["end"] :]
    return out


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    sites = _site_candidates(text)
    if not sites:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Single-site variants remain useful when only one overload is defective.
    for site in sites:
        mutated = _apply_sites(text, [site])
        key = _sha(mutated)
        if key in seen:
            continue
        seen.add(key)
        out.append(_candidate(relative, text, mutated, sites=[site], mode="single_site"))

    # Coordinate the same structural rewrite across sibling methods.  Group by
    # builder kind, source-local fallback width and replacement shape while
    # allowing method-local count variable names to differ.
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for site in sites:
        replacement_shape = re.sub(rf"\b{re.escape(site['count'])}\b", "$COUNT", site["after"])
        key = (site["builder_type"], site["default_width"], replacement_shape)
        groups.setdefault(key, []).append(site)

    for grouped in groups.values():
        # At most one structurally equivalent site per method.
        by_method: dict[int, dict[str, Any]] = {}
        for site in grouped:
            by_method.setdefault(site["method_index"], site)
        coordinated = list(by_method.values())
        if len(coordinated) < 2:
            continue
        mutated = _apply_sites(text, coordinated)
        key = _sha(mutated)
        if key in seen:
            continue
        seen.add(key)
        out.insert(
            0,
            _candidate(
                relative,
                text,
                mutated,
                sites=coordinated,
                mode="coordinated_sibling_methods",
            ),
        )

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
        raise ValueError(f"project root does not exist or is not a directory: {base}")

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
        "scheduling": "round_robin_by_source_file_with_coordinated_sibling_variant_first",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
