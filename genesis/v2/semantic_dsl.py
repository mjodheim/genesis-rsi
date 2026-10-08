"""Genesis V2.1 — typed, source-derived Java semantic hypotheses.

The *language* is a deliberately narrow declarative grammar:
    GuardReturn(predicate=Flag(field) OP Flag(argument.field), result=ClassConstant)
    -> InsertAfter(MethodEntry | PublicNullCheck)

Programs are proposed from repeated contracts among sibling methods in the
*buggy* source, BEFORE seeing a passing patch or running a validator. This
does not execute user strings, fabricate labels, change the trust root, or
claim that peer agreement proves semantic correctness.

The grammar is an explicit human-engineered research substrate, not yet
autonomous invention of completely new semantic operator families.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from genesis.java_sibling_guard_mutations import (
    _mask_literals_and_comments, _methods, NULL_CHECK, ID,
)
from genesis.trust_root import digest_of

SCHEMA = "genesis-v2-typed-java-guard-hypothesis-v1"
COMPILED_SCHEMA = "genesis-v2-compiled-hypothesis-v1"
MAX_FILE_BYTES = 512_000
MAX_HYPOTHESES = 32

GUARD = re.compile(
    rf"\bif\s*\(\s*(?P<receiver>{ID})\s*(?P<connector>\|\||&&)\s*"
    rf"(?P<arg>{ID})\.(?P<field>{ID})\s*\)\s*"
    rf"\{{\s*return\s+(?P<const>{ID})\s*;\s*\}}",
)
IDENTIFIER = re.compile(rf"^{ID}$")
BOOL_DECLARATION = re.compile(
    rf"\b(?:(?:public|protected|private|static|final|transient|volatile)\s+)*"
    rf"boolean\s+(?P<field>{ID})\s*(?:[;=,])"
)
CONSTANT_DECLARATION = re.compile(
    rf"\b(?:(?:public|protected|private|final|static)\s+)*"
    rf"(?P<type>{ID})\s+(?P<name>{ID})\s*="
)


class SemanticHypothesisError(ValueError):
    """Invalid, stale or unsupported declarative transformation."""


def _read_project_source(root: Path, relative: str) -> str:
    if (not isinstance(relative, str) or not relative.endswith(".java")
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise SemanticHypothesisError("invalid Java source path")
    base = root.resolve(strict=True)
    path = (base / relative).resolve(strict=True)
    if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise SemanticHypothesisError("source outside approved workspace/size")
    if any(part in {".git", "target", "build", "tests", "test"} for part in Path(relative).parts):
        raise SemanticHypothesisError("source in forbidden artifact/test folder")
    return path.read_text(encoding="utf-8")


def _discover_in_text(relative: str, source: str) -> list[dict[str, Any]]:
    masked = _mask_literals_and_comments(source)
    methods = _methods(masked)
    known_boolean_fields = {m["field"] for m in BOOL_DECLARATION.finditer(masked)}
    fields_or_constants = {
        (m["type"], m["name"]) for m in CONSTANT_DECLARATION.finditer(masked)
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for method in methods:
        grouped[method["rtype"], method["argtype"]].append(method)

    proposed: list[dict[str, Any]] = []
    for (rtype, argtype), siblings in sorted(grouped.items()):
        if rtype != argtype or len(siblings) < 3:
            continue  # return type and argument class must agree
        donor_patterns: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
        for method in siblings:
            for m in GUARD.finditer(method["body"]):
                if m["arg"] != method["arg"]:
                    continue
                if {m["receiver"], m["field"]}.difference(known_boolean_fields):
                    continue
                if (rtype, m["const"]) not in fields_or_constants:
                    continue
                donor_patterns[(m["receiver"], m["connector"], m["field"], m["const"])].add(
                    method["method"]
                )

        for pattern, donors in sorted(donor_patterns.items()):
            if len(donors) < 2:
                continue
            left, connector, right, constant = pattern
            for target in siblings:
                body = target["body"]
                if target["method"] in donors:
                    continue
                # Requires an existing source-local computation using the
                # same argument. A missing guard alone is not sufficient.
                if not re.search(r"\b" + re.escape(target["arg"]) + r"\s*\.", body):
                    continue
                if not re.search(r"\breturn\b", body):
                    continue
                if re.search(r"\bif\s*\(\s*" + re.escape(left) + r"\b", body):
                    continue
                null_check = NULL_CHECK.match(body)
                anchor = (
                    "after_existing_null_check" if null_check
                    and null_check["arg"] == target["arg"] else "method_entry"
                )
                core = {
                    "schema": SCHEMA,
                    "source_path": relative,
                    "source_sha256": sha256(source.encode()).hexdigest(),
                    "language": "java",
                    "hypothesis": "sibling_boolean_guard_contract",
                    "target_method": target["method"],
                    "target_return_type": target["rtype"],
                    "parameter_type": target["argtype"],
                    "parameter_name": target["arg"],
                    "predicate": {
                        "left_boolean_field": left,
                        "connector": connector,
                        "argument_boolean_field": right,
                    },
                    "return_constant": constant,
                    "placement": anchor,
                    "donor_methods": sorted(donors),
                    "donor_quorum": len(donors),
                    "derived_only_from_buggy_source": True,
                    "human_patch_seen": False,
                    "validator_result_seen": False,
                }
                proposed.append({**core, "hypothesis_digest": digest_of(core)})
    proposed.sort(key=lambda h: (h["source_path"], h["target_method"],
                                 h["predicate"]["connector"],
                                 h["return_constant"]))
    return proposed[:MAX_HYPOTHESES]


def propose(
    root: str | Path, relative: str, *, max_hypotheses: int = 16
) -> dict[str, Any]:
    if (type(max_hypotheses) is not int or not 1 <= max_hypotheses <= MAX_HYPOTHESES):
        raise SemanticHypothesisError("hypothesis budget must be 1..32")
    source = _read_project_source(Path(root), relative)
    generated = _discover_in_text(relative, source)[:max_hypotheses]
    data = {
        "schema": "genesis-v2-semantic-proposals-v1",
        "proposals": generated,
        "hypothesis_count": len(generated),
        "source_path": relative,
        "source_sha256": sha256(source.encode()).hexdigest(),
        "external_model_calls": 0,
        "no_evaluator_feedback_seen": True,
        "independent_repair_proven": False,
    }
    return {**data, "proposal_digest": digest_of(data)}


def compile_hypothesis(
    root: str | Path, hypothesis: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate by *re-inferring source facts*, then compile safe source edit.

    Never executes the generated Java; the untrusted candidate must go through
    a separate, isolated compiler/full-suite validator before promotion.
    """
    if not isinstance(hypothesis, Mapping):
        raise SemanticHypothesisError("hypothesis must be a typed mapping")
    if hypothesis.get("schema") != SCHEMA:
        raise SemanticHypothesisError("unsupported hypothesis language")
    core = {k: v for k, v in hypothesis.items() if k != "hypothesis_digest"}
    if hypothesis.get("hypothesis_digest") != digest_of(core):
        raise SemanticHypothesisError("hypothesis checksum mismatch")
    relative = hypothesis.get("source_path")
    source = _read_project_source(Path(root), relative)
    if hypothesis.get("source_sha256") != sha256(source.encode()).hexdigest():
        raise SemanticHypothesisError("source changed after the hypothesis was emitted")
    if dict(hypothesis) not in _discover_in_text(relative, source):
        raise SemanticHypothesisError("hypothesis not grounded in current source contracts")

    masked = _mask_literals_and_comments(source)
    targets = [
        m for m in _methods(masked)
        if m["method"] == hypothesis["target_method"]
        and m["rtype"] == hypothesis["target_return_type"]
        and m["argtype"] == hypothesis["parameter_type"]
        and m["arg"] == hypothesis["parameter_name"]
    ]
    if len(targets) != 1:
        raise SemanticHypothesisError("ambiguous/nonexistent target method")
    target = targets[0]
    start = target["body_start"]
    body = target["body"]
    if hypothesis["placement"] == "after_existing_null_check":
        match = NULL_CHECK.match(body)
        if not match or match["arg"] != target["arg"]:
            raise SemanticHypothesisError("expected null-check anchor missing")
        start += match.end()
    elif hypothesis["placement"] != "method_entry":
        raise SemanticHypothesisError("unsupported insertion point")

    pred = hypothesis["predicate"]
    statement = (
        f"\n        if ({pred['left_boolean_field']} {pred['connector']} "
        f"{target['arg']}.{pred['argument_boolean_field']}) {{\n"
        f"            return {hypothesis['return_constant']};\n"
        f"        }}\n"
    )
    content = source[:start] + statement + source[start:]
    if content == source or len(content.encode()) > MAX_FILE_BYTES:
        raise SemanticHypothesisError("unbounded or empty source transformation")
    body = {
        "schema": COMPILED_SCHEMA,
        "source_path": relative,
        "source_sha256": hypothesis["source_sha256"],
        "candidate_sha256": sha256(content.encode()).hexdigest(),
        "hypothesis_digest": hypothesis["hypothesis_digest"],
        "candidate_validated": False,
        "compiler_ran": False,
        "source_edited_on_disk": False,
    }
    return {
        **body,
        "compiled_candidate_digest": digest_of(body),
        "content_utf8": content,
    }
