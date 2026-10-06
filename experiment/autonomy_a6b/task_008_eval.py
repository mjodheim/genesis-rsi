from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

REST_SHA256 = "eb3eb76cbba2f7bc870a879b8453fa4400597a75b5f02e7b1e338d66de69ff3c"
OLD = '  extra_pip_packages: ""'
EXPECTED = '  extra_pip_packages: "skill-ovos-date-time"'
PLACEHOLDER = "  extra_pip_packages: <DEFAULT>"


def normalize_config(text: str) -> str:
    if EXPECTED in text:
        return text.replace(EXPECTED, PLACEHOLDER, 1)
    if OLD in text:
        return text.replace(OLD, PLACEHOLDER, 1)
    return text


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_008_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    config = (root / "ovos-core/config.yaml").read_text(encoding="utf-8")
    skills_api = (root / "ovos-skills/api.py").read_text(encoding="utf-8")
    extra_api = (root / "ovos-skills-extra/api.py").read_text(encoding="utf-8")

    default_ok = config.count(EXPECTED) == 1 and OLD not in config
    unrelated_config_preserved = hashlib.sha256(normalize_config(config).encode("utf-8")).hexdigest() == REST_SHA256
    readiness_broadcasts_present = (
        'bus.emit(Message("mycroft.ready"))' in skills_api
        and 'bus.emit(Message("mycroft.ready"))' in extra_api
    )

    result = {
        "schema": "mira-genesis-a6b-task008-evaluator-v2",
        "objective_ok": default_ok and unrelated_config_preserved and readiness_broadcasts_present,
        "core_default_skill_present": default_ok,
        "unrelated_config_preserved": unrelated_config_preserved,
        "external_skill_ready_broadcasts_present": readiness_broadcasts_present,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
