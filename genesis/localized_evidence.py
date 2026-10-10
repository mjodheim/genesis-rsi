"""Evidence whose suspect locations come from a localizer module instead of the stack trace.

A localization score says where a module points, not whether pointing there helps repair. This
is the bridge to the repair bench: the same evidence, with the production excerpts taken around
the locations a lineage module returns. Everything else in the evidence is left as collected, so
that two repair arms differ only by where they are told to look.

The module runs behind the same container boundary as during the lineage; it reads a copy of the
Java sources, never the checkout the validator compiles.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
from typing import Callable, Mapping

from genesis import localizer_lineage as lineage
from genesis.repair_bench import _excerpts
from genesis.trust_root import digest_of

_HEADER = re.compile(r"^--- (\S+)\s*$", re.MULTILINE)


def copy_java(source: Path, target: Path) -> int:
    """Copy the regular ``.java`` files under ``source``; links are not followed."""
    count = 0
    for directory, folders, files in os.walk(source, followlinks=False):
        folders[:] = [name for name in folders if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if name.endswith(".java") and path.is_file() and not path.is_symlink():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                count += 1
    return count


def trigger_report(root: Path, failing_tests) -> str:
    """The stack traces of ``failing_tests`` from the checkout's last test run."""
    path = root / "failing_tests"
    if path.is_symlink() or not path.is_file():
        return ""
    pieces = _HEADER.split(path.read_text(encoding="utf-8", errors="replace")[:2_000_000])
    wanted = set(failing_tests)
    return "".join(f"--- {pieces[index]}\n{pieces[index + 1].strip()}\n"
                   for index in range(1, len(pieces) - 1, 2) if pieces[index] in wanted)[:400_000]


def relocalize(evidence: Mapping, root: Path, module_source: str, *, image: str, scratch: Path,
               report: str | None = None, source_budget: int = 48_000, runner: Callable | None = None) -> dict:
    """``evidence`` with suspect locations and production excerpts taken from ``module_source``.

    When the module returns no location inside an existing production file, the collected evidence
    is kept and the fallback is recorded: an arm is never left without anything to read.
    """
    root, scratch = Path(root), Path(scratch)
    source_dir, test_dir = evidence["source_directory"], evidence["test_directory"]
    report = trigger_report(root, evidence["failing_tests"]) if report is None else report
    stage = scratch / f"stage-{os.getpid()}-{digest_of([str(root), evidence['evidence_digest']])[:12]}"
    shutil.rmtree(stage, ignore_errors=True)
    try:
        copy_java(root / source_dir, stage / "case" / "tree" / source_dir)
        if (root / test_dir).is_dir():
            copy_java(root / test_dir, stage / "case" / "tree" / test_dir)
        (stage / "case" / "case.json").write_text(json.dumps({
            "source_directory": source_dir, "test_directory": test_dir,
            "failing_tests": list(evidence["failing_tests"]), "report": report}), encoding="utf-8")
        outputs = lineage.run_module(module_source, ["case"], image=image, cases_directory=stage,
                                     scratch=scratch, runner=runner)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    answer = outputs.get("case") if isinstance(outputs.get("case"), Mapping) else {}
    prefix = source_dir.strip("/") + "/"
    locations = [item for item in lineage.clean_locations(answer.get("locations"))
                 if item[0].startswith(prefix) and item[0].endswith(".java") and (root / item[0]).is_file()]
    note = {"module_sha256": lineage.source_digest(module_source), "locations": len(locations),
            "error": str(answer.get("error") or "")[:120] or None, "fallback": not locations}
    body = {name: value for name, value in evidence.items() if name != "evidence_digest"}
    if locations:
        body.update(suspect_locations=locations, suspects_from_stack_trace=True,
                    production_source=_excerpts(root, [tuple(item) for item in locations], lineage.WINDOW, source_budget))
    body["localization"] = note
    return {**body, "evidence_digest": digest_of(body)}
