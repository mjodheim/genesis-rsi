"""Transform execution only, with the inherited pure-source and resource boundary."""
import importlib.util
import json
import sys
from pathlib import Path


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    payload = json.loads(sys.stdin.read())
    spec = importlib.util.spec_from_file_location("bounded_program", Path(sys.argv[1]).resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(json.dumps([module.transform(value) for value in payload["inputs"]]))


if __name__ == "__main__":
    main()
