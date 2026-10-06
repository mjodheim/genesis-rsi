from __future__ import annotations

import json
from pathlib import Path
import re
import sys

POST_START = "app.post('/api/transactions'"
NEXT_ROUTE = "app.put('/api/transactions"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_003_eval.py <workspace>")

    root = Path(sys.argv[1]).resolve()
    path = root / "_worker.ts"
    text = path.read_text(encoding="utf-8")

    start = text.find(POST_START)
    end = text.find(NEXT_ROUTE, start + 1)
    if start < 0 or end < 0:
        raise SystemExit("transaction POST route not found")
    route = text[start:end]

    utc_default = "transaction_date ?? new Date().toISOString().split('T')[0]" in route
    direct_client_date = bool(
        re.search(r"\b(?:const|let)\s+finalDate\s*=\s*transaction_date\s*;?", route)
    )
    required_guard = bool(
        re.search(
            r"if\s*\([^)]*(?:!\s*transaction_date|transaction_date\s*={2,3}\s*(?:undefined|null)|transaction_date\s*==\s*null)[^)]*\)"
            r"\s*return\s+c\.json\([\s\S]{0,180}?400\)",
            route,
        )
    )

    timezone_aware_default = (
        ("Intl.DateTimeFormat" in route or "toLocaleDateString" in route)
        and "timeZone" in route
        and "toISOString().split('T')[0]" not in route
    )

    source_strategy_ok = (
        (direct_client_date and required_guard)
        or timezone_aware_default
    )

    invariants = {
        "insert_sql_preserved": (
            "INSERT INTO transactions (user_id, amount, transaction_date, category_id, notes, payment_method_id)"
            in route
        ),
        "amount_validation_preserved": "amount is required" in route,
        "default_category_lookup_preserved": "SELECT id FROM categories WHERE is_default = 1" in route,
        "transaction_date_binding_preserved": (
            ".bind(userId, amount, finalDate, finalCategory" in route
        ),
    }

    objective_ok = (
        not utc_default
        and source_strategy_ok
        and all(invariants.values())
    )

    result = {
        "schema": "mira-genesis-a6b-task003-evaluator-v1",
        "objective_ok": objective_ok,
        "utc_default_present": utc_default,
        "direct_client_date": direct_client_date,
        "required_client_date_guard": required_guard,
        "timezone_aware_default": timezone_aware_default,
        "invariants": invariants,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
