from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys

REST_SHA256 = "d0fd681c9db8539557f5e77e686ddb7883cb2982be9e258dc5232093542f4c86"
ENTRY_RE = re.compile(r'^\s*(?:15|16|22|23): \(("(?:left|right)_shoulder_roll"), ([^\n]+)\),$', re.M)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_007_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    source = root / "robotica/validate.py"
    text = source.read_text(encoding="utf-8")

    rest = ENTRY_RE.sub("    <JOINT_LIMIT_ENTRY>", text)
    unrelated_preserved = hashlib.sha256(rest.encode("utf-8")).hexdigest() == REST_SHA256

    tree = ast.parse(text)
    mapping = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "JOINT_LIMITS_29" for target in node.targets):
                mapping = ast.literal_eval(node.value)
                break

    expected = {
        16: ("left_shoulder_roll", -0.75, 2.2515),
        23: ("right_shoulder_roll", -2.2515, 0.75),
    }
    mapping_ok = mapping == expected
    objective_ok = mapping_ok and unrelated_preserved

    result = {
        "schema": "mira-genesis-a6b-task007-evaluator-v2",
        "objective_ok": objective_ok,
        "mapping_ok": mapping_ok,
        "unrelated_source_preserved": unrelated_preserved,
        "mapping": mapping,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
