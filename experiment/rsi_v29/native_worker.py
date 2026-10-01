"""Trusted external native harness; source never receives expected answers."""
import importlib.util
import json
import resource
import sys
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    spec = importlib.util.spec_from_file_location("bounded_native_proposal", Path(sys.argv[1]).resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for case in json.loads(sys.stdin.read())["operations"]:
        try:
            rows.append({"ok": True, "value": module.run(case["operation"], case["data"])})
        except Exception as error:
            rows.append({"ok": False, "error": type(error).__name__})
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
