from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

import joblib
import numpy as np

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

    spec = importlib.util.spec_from_file_location("a6b_task007_validate", source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    mapping = module.JOINT_LIMITS_29
    mapping_ok = (
        set(mapping.keys()) == {16, 23}
        and mapping[16] == ("left_shoulder_roll", -0.75, 2.2515)
        and mapping[23] == ("right_shoulder_roll", -2.2515, 0.75)
    )

    def warnings_for(index: int, value: float):
        data = {
            "fps": 30,
            "dof_pos": np.zeros((3, 29), dtype=np.float32),
        }
        data["dof_pos"][:, index] = value
        with tempfile.NamedTemporaryFile(suffix=".pkl") as tmp:
            joblib.dump(data, tmp.name)
            errors, warnings = module.validate_retarget(tmp.name)
        return errors, warnings

    e16, w16 = warnings_for(16, 3.0)
    e23, w23 = warnings_for(23, -3.0)
    e15, w15 = warnings_for(15, 3.0)
    e22, w22 = warnings_for(22, -3.0)

    behavior_ok = (
        e16 == [] and any("left_shoulder_roll" in w and "DOF 16" in w for w in w16)
        and e23 == [] and any("right_shoulder_roll" in w and "DOF 23" in w for w in w23)
        and e15 == [] and not any("shoulder_roll" in w for w in w15)
        and e22 == [] and not any("shoulder_roll" in w for w in w22)
    )

    result = {
        "schema": "mira-genesis-a6b-task007-evaluator-v1",
        "objective_ok": mapping_ok and behavior_ok and unrelated_preserved,
        "mapping_ok": mapping_ok,
        "behavior_ok": behavior_ok,
        "unrelated_source_preserved": unrelated_preserved,
        "keys": sorted(mapping.keys()),
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
