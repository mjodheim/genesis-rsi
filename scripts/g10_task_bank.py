"""Deterministic fresh-bank generator for the bounded G10 recursive-chain assay."""
from __future__ import annotations

import random
from typing import Any, Mapping

from genesis import patch_templates
from genesis.learning import distillation
from genesis.trust_root import digest_of

BANK_SCHEMA = "genesis-g10-task-bank-v1"


class G10TaskError(RuntimeError):
    pass


def select_seed_templates(specialist: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    held = distillation.validate_specialist(specialist)
    numeric = [
        item
        for item in held["templates"]
        if any(part.get("kind") == "number_delta" for part in item["after_program"])
    ]
    comparison = [
        item
        for item in held["templates"]
        if any(
            part.get("kind") == "literal" and part.get("value") == ">="
            for part in item["after_program"]
        )
    ]
    if not numeric or not comparison:
        raise G10TaskError("retained specialist lacks required independent repair families")
    left = sorted(numeric, key=lambda item: item["template_digest"])[0]
    right = sorted(comparison, key=lambda item: item["template_digest"])[0]
    if left["template_digest"] == right["template_digest"]:
        raise G10TaskError("G10 seed repair families must be distinct")
    return left, right


def _capture_value(kind: str, name: str, rng: random.Random, salt: str) -> str:
    safe_salt = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in salt)
    if kind == "ident":
        return f"{safe_salt}_{name.lower()}_{rng.randrange(1000, 9999)}"
    if kind == "number":
        return str(rng.randrange(3, 12))
    if kind == "string":
        return f'"{salt}_{name.lower()}_{rng.randrange(100, 999)}"'
    raise G10TaskError(f"unsupported capture kind: {kind}")


def instantiate_before(template: Mapping[str, Any], rng: random.Random, salt: str) -> str:
    captures: dict[str, str] = {}
    tokens: list[str] = []
    for part in template["before_pattern"]:
        if part["kind"] == "literal":
            tokens.append(str(part["value"]))
            continue
        if part["kind"] != "capture":
            raise G10TaskError("unsupported before-pattern part")
        name = str(part["name"])
        if name not in captures:
            captures[name] = _capture_value(str(part["type"]), name, rng, salt)
        tokens.append(captures[name])
    return patch_templates._join_tokens(tokens) + "\n"


def _repair(line: str, template: Mapping[str, Any]) -> str:
    repaired = patch_templates.apply_template_to_line(line, template)
    if repaired is None:
        raise G10TaskError("generated source does not match its retained template")
    return repaired


def _scope(scope_id: str, lines: list[str]) -> list[str]:
    return [f"// scope:{scope_id}\n", *lines, "// endscope\n"]


def _case(
    case_id: str,
    group: str,
    before_lines: list[str],
    after_lines: list[str],
    *,
    selected_templates: tuple[str, str],
) -> dict[str, Any]:
    before = "".join(before_lines)
    after = "".join(after_lines)
    if before == after:
        raise G10TaskError("G10 task must fail before repair")
    return {
        "id": case_id,
        "group": group,
        "files": {"case.js": before},
        "expected_files": {"case.js": after},
        "selected_template_digests": list(selected_templates),
        "evaluation": {"kind": "exact_files"},
    }


def _atom_case(
    case_id: str,
    group: str,
    template: Mapping[str, Any],
    other_digest: str,
    rng: random.Random,
) -> dict[str, Any]:
    line = instantiate_before(template, rng, case_id)
    scope_id = f"atom_{rng.randrange(10000, 99999)}"
    before = _scope(scope_id, [line])
    after = _scope(scope_id, [_repair(line, template)])
    pair = tuple(sorted((template["template_digest"], other_digest)))
    return _case(case_id, group, before, after, selected_templates=pair)


def _pair_case(
    case_id: str,
    group: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    a = instantiate_before(left, rng, case_id + "_a")
    b = instantiate_before(right, rng, case_id + "_b")
    scope_id = f"pair_{rng.randrange(10000, 99999)}"
    before = _scope(scope_id, [a, b])
    after = _scope(scope_id, [_repair(a, left), _repair(b, right)])
    pair = tuple(sorted((left["template_digest"], right["template_digest"])))
    return _case(case_id, group, before, after, selected_templates=pair)


def _scope_challenge_case(
    case_id: str,
    group: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    rng: random.Random,
    *,
    target_first: bool,
) -> dict[str, Any]:
    decoy_scope = f"decoy_{rng.randrange(10000, 99999)}"
    target_scope = f"target_{rng.randrange(10000, 99999)}"
    da = instantiate_before(left, rng, case_id + "_da")
    db = instantiate_before(right, rng, case_id + "_db")
    ta = instantiate_before(left, rng, case_id + "_ta")
    tb = instantiate_before(right, rng, case_id + "_tb")
    decoy_before = _scope(decoy_scope, [da, db])
    target_before = _scope(target_scope, [ta, tb])
    decoy_after = list(decoy_before)
    target_after = _scope(target_scope, [_repair(ta, left), _repair(tb, right)])
    if target_first:
        before = target_before + decoy_before
        after = target_after + decoy_after
    else:
        before = decoy_before + target_before
        after = decoy_after + target_after
    pair = tuple(sorted((left["template_digest"], right["template_digest"])))
    case = _case(case_id, group, before, after, selected_templates=pair)
    case["target_scope_id"] = target_scope
    case["decoy_scope_id"] = decoy_scope
    return case


def _iterate_case(
    case_id: str,
    group: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    before: list[str] = []
    after: list[str] = []
    target_scopes: list[str] = []
    scope_count = 2 + rng.randrange(0, 2)
    for index in range(scope_count):
        scope_id = f"iter_{index}_{rng.randrange(10000, 99999)}"
        target_scopes.append(scope_id)
        a = instantiate_before(left, rng, f"{case_id}_{index}_a")
        b = instantiate_before(right, rng, f"{case_id}_{index}_b")
        before.extend(_scope(scope_id, [a, b]))
        after.extend(_scope(scope_id, [_repair(a, left), _repair(b, right)]))
    pair = tuple(sorted((left["template_digest"], right["template_digest"])))
    case = _case(case_id, group, before, after, selected_templates=pair)
    case["target_scope_ids"] = target_scopes
    return case


def build_bank(
    specialist: Mapping[str, Any],
    *,
    stage: int,
    purpose: str,
    seed: int,
) -> dict[str, Any]:
    if stage not in (1, 2, 3):
        raise G10TaskError("stage must be 1, 2 or 3")
    if purpose not in {"discovery", "holdout"}:
        raise G10TaskError("purpose must be discovery or holdout")
    left, right = select_seed_templates(specialist)
    rng = random.Random(int(seed))
    cases: list[dict[str, Any]] = []

    if purpose == "discovery" and stage == 1:
        for index in range(3):
            cases.append(_atom_case(
                f"d1-a-{index}", "atom_a", left, right["template_digest"], rng
            ))
            cases.append(_atom_case(
                f"d1-b-{index}", "atom_b", right, left["template_digest"], rng
            ))
    elif purpose == "discovery" and stage == 2:
        for index in range(4):
            cases.append(_scope_challenge_case(
                f"d2-{index}",
                "pair_discovery",
                left,
                right,
                rng,
                target_first=True,
            ))
    elif purpose == "discovery" and stage == 3:
        for index in range(4):
            cases.append(_scope_challenge_case(
                f"d3-{index}",
                "scope_discovery",
                left,
                right,
                rng,
                target_first=False,
            ))
    elif purpose == "holdout" and stage == 1:
        cases.append(_atom_case("h1-ret-a", "retention_atom", left, right["template_digest"], rng))
        cases.append(_atom_case("h1-ret-b", "retention_atom", right, left["template_digest"], rng))
        for index in range(4):
            cases.append(_pair_case(f"h1-new-{index}", "new_pair", left, right, rng))
    elif purpose == "holdout" and stage == 2:
        cases.append(_atom_case("h2-ret-a", "retention_atom", left, right["template_digest"], rng))
        cases.append(_atom_case("h2-ret-b", "retention_atom", right, left["template_digest"], rng))
        for index in range(2):
            cases.append(_pair_case(f"h2-ret-pair-{index}", "retention_pair", left, right, rng))
        for index in range(4):
            cases.append(_scope_challenge_case(
                f"h2-new-{index}", "new_scope_binding", left, right, rng, target_first=False
            ))
    elif purpose == "holdout" and stage == 3:
        cases.append(_atom_case("h3-ret-a", "retention_atom", left, right["template_digest"], rng))
        cases.append(_atom_case("h3-ret-b", "retention_atom", right, left["template_digest"], rng))
        for index in range(2):
            cases.append(_pair_case(f"h3-ret-pair-{index}", "retention_pair", left, right, rng))
        for index in range(2):
            cases.append(_scope_challenge_case(
                f"h3-ret-scope-{index}", "retention_scope", left, right, rng, target_first=False
            ))
        for index in range(4):
            cases.append(_iterate_case(f"h3-new-{index}", "new_iteration", left, right, rng))

    payload = {
        "schema": BANK_SCHEMA,
        "stage": stage,
        "purpose": purpose,
        "seed": int(seed),
        "selected_template_digests": sorted(
            (left["template_digest"], right["template_digest"])
        ),
        "case_count": len(cases),
        "cases": cases,
    }
    return {**payload, "bank_digest": digest_of(payload)}
