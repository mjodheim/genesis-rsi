"""Generic Java constructor/superclass shadow-field consistency candidates.

Pattern:
- subclass declares nullable String field that shadows a value held by parent
- getter falls back to super.getX() while local field is null
- equals compares local field
- constructor passes String argument to super(arg) without initializing field

The repair hypothesis is to initialize the local field in this constructor.
No benchmark IDs, class names, expected outputs, tests, or reference fixes
are encoded. This is a *candidate*, not a guaranteed correct repair.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-inherited-field-consistency-mutator-v1"
IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
CLASS = re.compile(r"\bclass\s+(?P<name>"+IDENT+r")\s+extends\s+"+IDENT+r"(?:\."+IDENT+r")*\b")
FIELD = re.compile(r"\bprivate\s+(?:transient\s+)?(?:final\s+)?String\s+(?P<name>"+IDENT+r")\s*=\s*null\s*;")
EQUALS = re.compile(r"\bboolean\s+equals\s*\(\s*(?:final\s+)?Object\s+"+IDENT+r"\s*\)\s*\{")
# A constructor's first statement must forward the named argument to parent.
# Avoid interpreting arbitrary occurrences of super() inside comments or literals.
CTOR = re.compile(
    r"(?P<full>(?:public|protected)\s+(?P<class>"+IDENT+r")\s*\("
    r"\s*(?:final\s+)?String\s+(?P<name>"+IDENT+r")\s*\)"
    r"\s*(?:throws\s+[^{]+)?\{\s*super\s*\(\s*(?P<forward>"+IDENT+r")\s*\)\s*;)",
    re.MULTILINE,
)


def _files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    selections = [str(p).strip("/") for p in prefixes if str(p).strip("/")]
    found = []
    for file in root.rglob("*.java"):
        if not file.is_file() or file.stat().st_size > 512_000:
            continue
        rel = file.relative_to(root)
        if any(part.lower() in ("build", "target", "test", "tests", ".git")
               for part in rel.parts[:-1]):
            continue
        path = rel.as_posix()
        if selections and not any(path == x or path.startswith(x + "/") for x in selections):
            continue
        found.append(file)
    return sorted(found, key=lambda p: p.as_posix())


def _fixes(text: str) -> list[tuple[str, str, str, int]]:
    if not EQUALS.search(text):
        return []
    classes = {match.group("name") for match in CLASS.finditer(text)}
    fields = {match.group("name") for match in FIELD.finditer(text)}
    if not classes or not fields:
        return []
    repairs = []
    for match in CTOR.finditer(text):
        name = match.group("name")
        if (match.group("class") not in classes
                or name != match.group("forward")
                or name not in fields):
            continue
        # Getter uses local field when set, otherwise parent value.
        getter = "get" + name[0].upper() + name[1:]
        fallback = re.compile(
            r"\b"+re.escape(name)+r"\s*==\s*null\s*\?\s*"
            r"super\."+re.escape(getter)+r"\s*\(\s*\)\s*:\s*"
            r"(?:this\.)?"+re.escape(name)+r"\s*;"
        )
        if not fallback.search(text):
            continue
        # equals() currently compares the local field (rather than the getter).
        comparison = re.compile(
            r"\b"+re.escape(name)+r"\s*==\s*null\b"
            r"|\b"+re.escape(name)+r"\s*\.equals\s*\("
            r"|\bother\s*\.\s*"+re.escape(name)+r"\b"
        )
        if not comparison.search(text[EQUALS.search(text).end():]):
            continue
        # Prevent candidates with an explicit already-initialized field.
        ctor_end = text.find("}", match.end())
        ctor_content = text[match.end():ctor_end if ctor_end >= 0 else len(text)]
        if re.search(r"\bthis\s*\.\s*"+re.escape(name)+r"\s*=", ctor_content):
            continue
        # Keep original surrounding whitespace; only insert a statement after
        # super(arg), leaving project source and strings untouched otherwise.
        at = match.end()
        suffix = "\n        this." + name + " = " + name + ";"
        after = text[:at] + suffix + text[at:]
        if after != text:
            repairs.append((name, text, after, text.count("\n", 0, at) + 1))
    return repairs


def generate(root: str | Path, *,
             include_prefixes: Sequence[str] = (),
             max_candidates: int = 64) -> dict[str, Any]:
    if not (1 <= max_candidates <= 500):
        raise ValueError("max_candidates outside [1,500]")
    base = Path(root).resolve(strict=True)
    candidates = []
    for path in _files(base, include_prefixes):
        before = path.read_text(encoding="utf-8")
        relative = path.relative_to(base).as_posix()
        for field, original, after, line in _fixes(before):
            core = {
                "schema": SCHEMA,
                "path": relative,
                "expected_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "new_sha256": hashlib.sha256(after.encode()).hexdigest(),
                "operator": "initialize_shadowed_inherited_state",
                "field": field,
                "line": line,
            }
            digest = digest_of(core)
            candidates.append({
                "id": "java-state-"+digest[:18],
                "candidate_digest": digest,
                "path": relative,
                "operator": "initialize_shadowed_inherited_state",
                "expected_sha256": core["expected_sha256"],
                "content_utf8": after,
                "detail": {
                    "mode": "constructor_super_forwarding_inconsistent_with_local_equality",
                    "site_count": 1,
                    "line": line,
                    "strategy_origin": "source_local_inherited_state_consistency",
                },
                "external_model_calls": 0,
            })
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break
    payload = {"schema": SCHEMA, "candidate_count": len(candidates),
               "candidates": candidates, "external_model_calls": 0}
    return {**payload, "result_digest": digest_of(payload)}
