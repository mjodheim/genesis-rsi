"""Where does the repair search miss? Compare the full candidate space with the human fix.

For each ALREADY EXPOSED Defects4J case this regenerates every candidate the strategist can produce
(no top-k cut), then reads the human fix and answers three separate questions:

* localisation -- is the fixed file in the focus set, and at what rank?
* reach        -- how many candidates edit the lines the fix edits?
* expression   -- is any candidate the fix itself (whitespace-insensitive)?

It reads the fixed revision, so every case it is run on is spent as blind evidence. It refuses any
case not listed in EXPOSED_CASES. All Defects4J commands go through the container boundary.

    python scripts/audit_repair_search_space.py --workspace /srv/genesis/audit --out report.json
"""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist  # noqa: E402
from genesis.defects4j_sandbox import Defects4JSandbox  # noqa: E402
from genesis.failure_localization import prioritize  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SCHEMA = "genesis-repair-search-space-audit-v1"

# Cases whose buggy code was already opened by a recorded study. Value: whether an operator was
# later written by hand for that case (so its row says nothing about unseen bugs).
EXPOSED_CASES: dict[tuple[str, int], bool] = {
    ("Codec", 15): False, ("Compress", 6): True, ("Math", 53): True, ("Csv", 16): True,
    ("Collections", 24): False, ("Gson", 2): False, ("Jsoup", 68): False, ("JacksonCore", 11): False,
    ("Cli", 34): False, ("Time", 22): False, ("JxPath", 12): False, ("Chart", 23): False,
    ("JacksonXml", 4): False, ("Mockito", 22): False,
}


def _edits(before: list[str], after: list[str]) -> list[tuple[int, int, str, int, int]]:
    """Changed ranges in ``before`` coordinates: (first, last, kind, lines removed, lines added)."""
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    return [
        (i1 + 1, max(i2, i1 + 1), tag, i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
    ]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _metadata(sandbox: Defects4JSandbox, project: str, bug_id: int, kind: str) -> str:
    """One Defects4J metadata file, read from the image (never from the host)."""
    path = f"/defects4j/framework/projects/{project}/{kind}"
    run = sandbox.execute(["cat", path.format(bug=bug_id)])
    if not run.ok:
        raise RuntimeError(f"cannot read {path} for {project}-{bug_id}")
    return run.output


def audit_case(sandbox: Defects4JSandbox, project: str, bug_id: int) -> dict:
    name = f"{project}-{bug_id}"
    buggy, fixed = f"{name}-b", f"{name}-f"
    for directory, version in ((buggy, "b"), (fixed, "f")):
        if not (sandbox.workspace / directory).is_dir():
            if not sandbox.checkout(project, bug_id, version, directory).ok:
                raise RuntimeError(f"checkout of {directory} failed")
    prefix = sandbox.export(buggy, "dir.src.classes").output.strip()
    root, reference = sandbox.workspace / buggy, sandbox.workspace / fixed

    def source_of(classname: str) -> str:
        return f"{prefix}/{classname.strip().split('$', 1)[0].replace('.', '/')}.java"

    loaded = sorted({
        source_of(line) for line in _metadata(sandbox, project, bug_id, f"loaded_classes/{bug_id}.src").splitlines()
        if line.strip() and (root / source_of(line)).is_file()
    })
    modified = [source_of(line) for line in _metadata(sandbox, project, bug_id, f"modified_classes/{bug_id}.src").split()]
    trigger = _metadata(sandbox, project, bug_id, f"trigger_tests/{bug_id}")

    # Same file-level policy as the recorded studies: exact test-class match, then package overlap.
    exact = set(prioritize(trigger, loaded)["matched_source_paths"])
    packages = [
        line[4:].split("::")[0].rsplit(".", 1)[0].replace(".", "/") + "/"
        for line in trigger.splitlines() if line.startswith("--- ") and "." in line
    ]

    def rank(path: str) -> tuple[int, int, str]:
        overlap = max((len(package.split("/")) for package in packages if package in path), default=0)
        return (0 if path in exact else 1, -overlap, path)

    order = sorted(loaded, key=rank)
    focus = sorted(order[:32])

    fix = {
        path: _edits((root / path).read_text(errors="replace").splitlines(),
                     (reference / path).read_text(errors="replace").splitlines())
        for path in modified
    }
    generated = repair_strategist.generate(
        root, include_prefixes=[prefix], focus_paths=focus, max_candidates=10_000,
        per_family_budget=10_000, composition_fraction=0.4, source_balance_experimental=True,
        atomic_first_experimental=True, sibling_guard_experimental=True,
        stream_iterator_experimental=True, v21_semantic_hypotheses_experimental=True,
        priority_focus_paths=tuple(sorted(exact))[:8],
    )
    candidates = generated["candidates"]
    reference_text = {path: _squash((reference / path).read_text(errors="replace")) for path in modified}
    originals: dict[str, list[str]] = {}
    in_file = on_lines = 0
    first_on_lines = exact_rank = None
    for position, candidate in enumerate(candidates, 1):
        path = candidate["path"]
        if path not in fix:
            continue
        in_file += 1
        before = originals.setdefault(path, (root / path).read_text(errors="replace").splitlines())
        touched = _edits(before, candidate["content_utf8"].splitlines())
        if any(a1 <= b2 and b1 <= a2 for a1, a2, *_ in touched for b1, b2, *_ in fix[path]):
            on_lines += 1
            first_on_lines = first_on_lines or position
        if exact_rank is None and len(modified) == 1 and _squash(candidate["content_utf8"]) == reference_text[path]:
            exact_rank = position
    return {
        "case": name,
        "operator_written_for_this_case": EXPOSED_CASES[(project, bug_id)],
        "loaded_source_files": len(loaded),
        "fixed_files": modified,
        "fixed_file_rank": [order.index(path) + 1 if path in order else None for path in modified],
        "fixed_file_in_focus": all(path in focus for path in modified),
        "fix_edits": {path: [[kind, removed, added] for _, _, kind, removed, added in edits] for path, edits in fix.items()},
        "candidates": len(candidates),
        "candidates_per_family": {
            family: record["accepted"] for family, record in generated["family_activation"].items() if record["accepted"]
        },
        "candidates_in_fixed_file": in_file,
        "candidates_on_fix_lines": on_lines,
        "first_rank_on_fix_lines": first_on_lines,
        "exact_fix_rank": exact_rank,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.workspace.mkdir(parents=True, exist_ok=True)
    sandbox = Defects4JSandbox(arguments.workspace)
    probe = sandbox.probe()
    if not probe["isolated"]:
        raise SystemExit("the Defects4J boundary does not hold; refusing to run")
    cases = [audit_case(sandbox, project, bug_id) for project, bug_id in EXPOSED_CASES]
    unseen = [case for case in cases if not case["operator_written_for_this_case"]]
    body = {
        "schema": SCHEMA,
        "human_fix_read": True,
        "cases_remain_development_only": True,
        "sandbox_probe_digest": probe["probe_digest"],
        "cases": cases,
        "summary_without_hand_written_operator": {
            "cases": len(unseen),
            "fixed_file_in_focus": sum(case["fixed_file_in_focus"] for case in unseen),
            "fixed_file_ranked_first": sum(case["fixed_file_rank"][0] == 1 for case in unseen),
            "candidates_generated": sum(case["candidates"] for case in unseen),
            "cases_with_a_candidate_on_fix_lines": sum(case["candidates_on_fix_lines"] > 0 for case in unseen),
            "cases_with_the_exact_fix": sum(case["exact_fix_rank"] is not None for case in unseen),
        },
    }
    arguments.out.write_text(json.dumps({**body, "audit_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(body["summary_without_hand_written_operator"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
