from __future__ import annotations

import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
path = root / "contracts/tariff-shield/src/lib.rs"
text = path.read_text(encoding="utf-8", errors="replace")


def function_block(name: str) -> str:
    marker = f"    pub fn {name}"
    start = text.find(marker)
    if start < 0:
        return ""
    brace = text.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


approve = function_block("approve_upgrade")
cancel = function_block("cancel_upgrade")

match = re.search(
    r"if\s+env\.ledger\(\)\.sequence\(\)\s*(>=|>|<=|<|==|!=)\s*proposal\.expiry_ledger",
    approve,
)
operator = None if match is None else match.group(1)


def expired(sequence: int, expiry: int) -> bool:
    if operator == ">=":
        return sequence >= expiry
    if operator == ">":
        return sequence > expiry
    if operator == "<=":
        return sequence <= expiry
    if operator == "<":
        return sequence < expiry
    if operator == "==":
        return sequence == expiry
    if operator == "!=":
        return sequence != expiry
    return False


expiry = 100
semantics = {
    "before_expiry_valid": not expired(expiry - 1, expiry),
    "at_expiry_rejected": expired(expiry, expiry),
    "past_expiry_rejected": expired(expiry + 1, expiry),
}

cancel_checks = {
    "function_present": bool(cancel),
    "requires_admin": "require_admin(&env, &caller);" in cancel,
    "requires_auth": "caller.require_auth();" in cancel,
    "not_found_guard": "Error::ProposalNotFound" in cancel,
    "removes_proposal": "env.storage().persistent().remove(&key);" in cancel,
    "no_expiry_boundary_added": "expiry_ledger" not in cancel,
}

proposal_horizon_ok = (
    "let expiry_ledger = env.ledger().sequence() + 17280;" in text
)

payload = {
    "schema": "mira-genesis-a6b-task001-evaluator-v1",
    "operator": operator,
    "semantics": semantics,
    "cancel_checks": cancel_checks,
    "proposal_horizon_ok": proposal_horizon_ok,
    "objective_ok": (
        operator == ">="
        and all(semantics.values())
        and all(cancel_checks.values())
        and proposal_horizon_ok
    ),
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
