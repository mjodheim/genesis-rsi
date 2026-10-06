from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

EXPECTED = {
    "internal/runtime/docker.go": {
        "baseline_sha256": "a8b06e93f5daa3628ec63b923bd0a74af2b18568478c33777c6fef2907c9ee5c",
        "expected_sha256": "fdabdd5d703ab87e8bab41a940b4c2445e0ca5d2fe7caffc5d8c55c3bc8a8822",
    },
    "internal/health/health.go": {
        "baseline_sha256": "ca1d017991a2f42945212dfb5410f6c68e6e1960557d6f472567b6bbc074e2d5",
        "expected_sha256": "187ac9b6036fbdf962d1d3c1303d59e553c9c3f757427d2741ec57b347e30798",
    },
}
OLD = "for i := 0; i <= retries; i++ {"
NEW = "for i := 0; i < retries; i++ {"


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_002_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    files = {}
    objective_ok = True
    for rel, expected in EXPECTED.items():
        path = root / rel
        text = path.read_text(encoding="utf-8")
        sha = digest_text(text)
        checks = {
            "old_loop_absent": OLD not in text,
            "new_loop_count": text.count(NEW),
            "exact_expected_source_digest": sha == expected["expected_sha256"],
        }
        ok = all([
            checks["old_loop_absent"],
            checks["new_loop_count"] == 1,
            checks["exact_expected_source_digest"],
        ])
        objective_ok = objective_ok and ok
        files[rel] = {
            "sha256": sha,
            "checks": checks,
            "ok": ok,
        }

    result = {
        "schema": "mira-genesis-a6b-task002-evaluator-v1",
        "objective_ok": objective_ok,
        "files": files,
        "native_go_toolchain_available": False,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
