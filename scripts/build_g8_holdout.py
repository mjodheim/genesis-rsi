"""Generate a fresh G8 holdout after the specialist is frozen.

The generator is deterministic from a supplied seed, but the seed is chosen only
after the specialist commit.  It emits two fresh instances for each of four
families distilled from prior A6b evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from genesis.trust_root import digest_of

SCHEMA = "genesis-g8-sealed-holdout-v1"


def _rng(seed: str) -> random.Random:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))


def _pick(rng: random.Random, prefix: str, used: set[str]) -> str:
    while True:
        value = f"{prefix}{rng.randrange(100, 999)}"
        if value not in used:
            used.add(value)
            return value


def _python_range_case(rng: random.Random, index: int) -> dict:
    used: set[str] = set()
    fn = _pick(rng, "productTo", used)
    limit = _pick(rng, "limit", used)
    value = _pick(rng, "item", used)
    old = f"    for {value} in range(1, {limit}):"
    new = f"    for {value} in range(1, {limit} + 1):"
    source = (
        f"def {fn}({limit}):\n"
        "    out = 1\n"
        f"{old}\n"
        f"        out *= {value}\n"
        "    return out\n\n"
        f"raise SystemExit(0 if {fn}(4) == 24 and {fn}(1) == 1 else 1)\n"
    )
    return {
        "id": f"python-inclusive-{index}",
        "family": "python_inclusive_range",
        "path": "program.py",
        "source_utf8": source,
        "allowed_replacement": {"old": old, "new": new},
        "public_contract": (
            "The function must multiply every positive integer from 1 through the supplied "
            "limit inclusively. The current loop stops one early. Keep the zero/one behavior "
            "and all unrelated source unchanged."
        ),
        "runtime": {"kind": "python_exit_zero"},
    }


def _typescript_index_case(rng: random.Random, index: int) -> dict:
    used: set[str] = set()
    array = _pick(rng, "PHASES", used).upper()
    selected = _pick(rng, "firstPhase", used)
    old = f"const {selected} = {array}[1];"
    new = f"const {selected} = {array}[0];"
    first = _pick(rng, "alpha", used)
    second = _pick(rng, "beta", used)
    source = (
        f'const {array} = [{{name: "{first}"}}, {{name: "{second}"}}];\n'
        f"{old}\n"
        f'if ({selected}.name !== "{first}") process.exit(1);\n'
    )
    return {
        "id": f"typescript-zero-index-{index}",
        "family": "typescript_zero_index",
        "path": "program.ts",
        "source_utf8": source,
        "allowed_replacement": {"old": old, "new": new},
        "public_contract": (
            "The array is zero-indexed and the variable named as the first phase must refer to "
            "the first entry, not the second. Preserve the array contents and unrelated source."
        ),
        "runtime": {"kind": "node_exit_zero"},
    }


def _rust_retry_case(rng: random.Random, index: int) -> dict:
    used: set[str] = set()
    loop_var = _pick(rng, "attempt", used)
    constant = _pick(rng, "MAX_TRIES_", used).upper()
    count = rng.randrange(4, 8)
    old = f"    for {loop_var} in 1..{constant} {{"
    new = f"    for {loop_var} in 0..{constant} {{"
    source = (
        f"const {constant}: usize = {count};\n"
        "fn run() {\n"
        f"{old}\n"
        f'        println!("{{}}", {loop_var});\n'
        "    }\n"
        "}\n"
    )
    return {
        "id": f"rust-retry-range-{index}",
        "family": "rust_retry_range",
        "path": "program.rs",
        "source_utf8": source,
        "allowed_replacement": {"old": old, "new": new},
        "public_contract": (
            f"The retry loop must perform exactly {count} configured attempts. Keep {constant} "
            "unchanged and preserve all unrelated source. The current exclusive range starts at 1 "
            "and therefore performs one attempt too few."
        ),
        "runtime": {
            "kind": "static_exact_replacement",
            "protected_substring": f"const {constant}: usize = {count};",
        },
    }


def _rust_boundary_case(rng: random.Random, index: int) -> dict:
    used: set[str] = set()
    env = _pick(rng, "ctx", used)
    ledger = _pick(rng, "clock", used)
    seq = _pick(rng, "tick", used)
    proposal = _pick(rng, "lease", used)
    expiry = _pick(rng, "deadline", used)
    old = f"    if {env}.{ledger}().{seq}() > {proposal}.{expiry} {{"
    new = f"    if {env}.{ledger}().{seq}() >= {proposal}.{expiry} {{"
    source = (
        "fn expired() -> bool {\n"
        f"{old}\n"
        "        return true;\n"
        "    }\n"
        "    false\n"
        "}\n"
    )
    return {
        "id": f"rust-boundary-{index}",
        "family": "rust_boundary_inclusive",
        "path": "program.rs",
        "source_utf8": source,
        "allowed_replacement": {"old": old, "new": new},
        "public_contract": (
            "The exact expiry boundary must count as expired: equality is expired, one unit "
            "before is still valid, and one unit after is expired. Preserve all unrelated source."
        ),
        "runtime": {"kind": "static_exact_replacement"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rng = _rng(args.seed)
    cases = []
    for index in (1, 2):
        cases.append(_python_range_case(rng, index))
        cases.append(_typescript_index_case(rng, index))
        cases.append(_rust_retry_case(rng, index))
        cases.append(_rust_boundary_case(rng, index))

    payload = {
        "schema": SCHEMA,
        "seed_commitment": hashlib.sha256(args.seed.encode("utf-8")).hexdigest(),
        "case_count": len(cases),
        "families": sorted({case["family"] for case in cases}),
        "cases": cases,
    }
    payload["holdout_content_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
