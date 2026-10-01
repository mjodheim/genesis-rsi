"""Internal worker: bounded pure policy calls, never evaluator execution."""
import importlib.util
import json
import sys
from pathlib import Path

def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)


def main():
    limits()
    payload = json.loads(sys.stdin.read())
    spec = importlib.util.spec_from_file_location("bounded_lineage_policy", Path(sys.argv[1]).resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metadata = tuple(module.policy_metadata())
    if len(metadata) != 10 or any(type(x) is not int for x in metadata):
        raise ValueError("Invalid policy ABI metadata")
    mode = payload["mode"]
    result = {"metadata": metadata}
    if mode == "decide":
        order = getattr(module, "order_candidates", None)
        result["ordered_candidates"] = {
            key: list(order(payload["view"], key, rows)) if order else [r["source_sha256"] for r in rows]
            for key, rows in payload["choices"].items()}
        result["selected_parent_ids"] = list(module.select_parent_batch(
            payload["view"], payload["max_parallelism"]))
    elif mode == "target":
        selector = getattr(module, "select_target", None)
        result["target"] = (selector(payload["diagnostics"], payload["targets"])
                            if selector else payload["targets"][0])
    elif mode != "metadata":
        raise ValueError("Unknown isolated worker mode")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
