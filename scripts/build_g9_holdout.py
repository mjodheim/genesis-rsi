"""Generate a fresh three-block holdout for Genesis v2 G9."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from genesis.trust_root import digest_of

SCHEMA = "genesis-g9-holdout-v1"
CSPROJ = '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>disable</ImplicitUsings><Nullable>disable</Nullable></PropertyGroup></Project>\n'


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))


def _name(rng: random.Random, prefix: str) -> str:
    return f"{prefix}{rng.randrange(100, 999)}"


def _csharp_retained(rng: random.Random, index: int) -> dict:
    method = _name(rng, "Pick")
    good = rng.randrange(10, 60)
    bad = good + rng.randrange(10, 60)
    if index % 2:
        source = (
            "using System;\n"
            f"class Program {{ static int {method}(int[] values) => values[1]; "
            f"static int Main() => {method}(new[]{{{good},{bad}}}) == {good} ? 0 : 21; }}\n"
        )
    else:
        a = chr(rng.randrange(ord("a"), ord("m")))
        b = chr(rng.randrange(ord("n"), ord("z")))
        source = (
            "using System;\n"
            f'class Program {{ static char {method}(string text) => text[1]; '
            f'static int Main() => {method}("{a}{b}") == \'{a}\' ? 0 : 22; }}\n'
        )
    return {
        "id": f"retained-{index}",
        "group": "parent_retention",
        "files": {"Case.csproj": CSPROJ, "Program.cs": source},
        "evaluation": {"kind": "dotnet_exit_zero"},
    }


def _csharp_g6_gain(rng: random.Random, index: int) -> dict:
    maker = _name(rng, "Make")
    picker = _name(rng, "Pick")
    if index % 2:
        good = rng.randrange(61, 110)
        bad = good + rng.randrange(10, 60)
        source = (
            "using System;\n"
            f"class Program {{ static int[] {maker}() => new[]{{{good},{bad}}}; "
            f"static int {picker}() => {maker}()[1]; "
            f"static int Main() => {picker}() == {good} ? 0 : 31; }}\n"
        )
    else:
        a = chr(rng.randrange(ord("a"), ord("m")))
        b = chr(rng.randrange(ord("n"), ord("z")))
        source = (
            "using System;\n"
            f'class Program {{ static string {maker}() => "{a}{b}"; '
            f"static char {picker}() => {maker}()[1]; "
            f"static int Main() => {picker}() == '{a}' ? 0 : 32; }}\n"
        )
    return {
        "id": f"g6-gain-{index}",
        "group": "g6_component_gain",
        "files": {"Case.csproj": CSPROJ, "Program.cs": source},
        "evaluation": {"kind": "dotnet_exit_zero"},
    }


def _python_specialist(rng: random.Random, index: int) -> dict:
    fn = _name(rng, "product_to_")
    limit = _name(rng, "limit_")
    item = _name(rng, "item_")
    old = f"    for {item} in range(1, {limit}):"
    new = f"    for {item} in range(1, {limit} + 1):"
    source = (
        f"def {fn}({limit}):\n"
        "    result = 1\n"
        f"{old}\n"
        f"        result *= {item}\n"
        "    return result\n\n"
        f"raise SystemExit(0 if {fn}(4) == 24 and {fn}(1) == 1 else 1)\n"
    )
    return {
        "id": f"g8-python-{index}",
        "group": "g8_specialist_gain",
        "files": {"program.py": source},
        "evaluation": {"kind": "python_exit_zero"},
        "expected_replacement": {"path": "program.py", "old": old, "new": new},
    }


def _rust_retry_specialist(rng: random.Random) -> dict:
    var = _name(rng, "attempt_")
    const = _name(rng, "MAX_TRIES_").upper()
    count = rng.randrange(4, 8)
    old = f"    for {var} in 1..{const} {{"
    new = f"    for {var} in 0..{const} {{"
    source = (
        f"const {const}: usize = {count};\n"
        "fn run() {\n"
        f"{old}\n"
        f'        println!("{{}}", {var});\n'
        "    }\n"
        "}\n"
    )
    return {
        "id": "g8-rust-retry",
        "group": "g8_specialist_gain",
        "files": {"program.rs": source},
        "evaluation": {
            "kind": "static_single_line",
            "protected_substring": f"const {const}: usize = {count};",
        },
        "expected_replacement": {"path": "program.rs", "old": old, "new": new},
    }


def _rust_boundary_specialist(rng: random.Random) -> dict:
    ctx = _name(rng, "ctx_")
    clock = _name(rng, "clock_")
    tick = _name(rng, "tick_")
    lease = _name(rng, "lease_")
    deadline = _name(rng, "deadline_")
    old = f"    if {ctx}.{clock}().{tick}() > {lease}.{deadline} {{"
    new = f"    if {ctx}.{clock}().{tick}() >= {lease}.{deadline} {{"
    source = (
        "fn expired() -> bool {\n"
        f"{old}\n"
        "        return true;\n"
        "    }\n"
        "    false\n"
        "}\n"
    )
    return {
        "id": "g8-rust-boundary",
        "group": "g8_specialist_gain",
        "files": {"program.rs": source},
        "evaluation": {"kind": "static_single_line"},
        "expected_replacement": {"path": "program.rs", "old": old, "new": new},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rng = _rng(args.seed)
    cases = []
    for index in range(1, 5):
        cases.append(_csharp_retained(rng, index))
    for index in range(1, 5):
        cases.append(_csharp_g6_gain(rng, index))
    cases.append(_python_specialist(rng, 1))
    cases.append(_python_specialist(rng, 2))
    cases.append(_rust_retry_specialist(rng))
    cases.append(_rust_boundary_specialist(rng))

    payload = {
        "schema": SCHEMA,
        "seed_commitment": hashlib.sha256(args.seed.encode()).hexdigest(),
        "case_count": len(cases),
        "group_counts": {
            group: sum(1 for case in cases if case["group"] == group)
            for group in sorted({case["group"] for case in cases})
        },
        "cases": cases,
    }
    payload["holdout_content_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
