"""Case-local virtual branches; partial candidates never acquire deployment authority."""
from pathlib import Path
from typing import Mapping

from genesis.openrouter_repair import _allowed, inspect_tool
from genesis.repair_bench import Candidate, History, RepairBenchError, _production_target


def find_parent(history: History, identity: str) -> Candidate | None:
    """Only candidates already graded in this case may be used as parents."""
    for candidate, verdict in history:
        if candidate.digest == identity and verdict.get("candidate_digest") == identity:
            return candidate
    return None


def archive_prompt(history: History) -> str:
    lines = ["## Case-local candidate branches (partial repairs are not successes)"]
    for number, (candidate, verdict) in enumerate(history[-6:], max(1, len(history) - 5)):
        lines.append(f"Attempt {number}, {candidate.digest}: {verdict['stopped_at']}; files " +
                     ", ".join(path for path, _ in candidate.files)[:180])
    return "\n".join(lines)


def read_branch(root: Path, evidence: Mapping, history: History, arguments: Mapping) -> str:
    identity = arguments.get("branch", "")
    if not identity:
        return inspect_tool(root, evidence, "read_file", dict(arguments))
    parent = find_parent(history, identity)
    if parent is None:
        raise ValueError("unknown case-local branch")
    target = _allowed(root, arguments["path"], evidence)
    path = target.relative_to(root).as_posix()
    virtual = {Path(name).as_posix(): text for name, text in parent.files}
    if path not in virtual:
        return inspect_tool(root, evidence, "read_file", dict(arguments))
    _production_target(root, path, evidence["source_directory"], evidence["test_directory"])
    start = max(1, int(arguments.get("start", 1)))
    return "\n".join(f"{i + 1}| {line}" for i, line in enumerate(virtual[path].splitlines())
                     if start <= i + 1 < start + 200)[:16000]


def extend_branch(root: Path, evidence: Mapping, parent: Candidate, files,
                  origin: str, description: str) -> Candidate | None:
    """Edit a virtual parent, retaining its other changes; never write to the checkout."""
    if not isinstance(files, list) or not 1 <= len(files) <= 3:
        return None
    virtual, originals, edited = {}, {}, set()
    try:
        def allowed(path):
            target = _production_target(root, path, evidence["source_directory"], evidence["test_directory"])
            return target, target.relative_to(root).as_posix()

        for path, content in parent.files:
            target, canonical = allowed(path)
            if canonical in virtual:
                return None
            originals[canonical] = target.read_text(encoding="utf-8", errors="replace")
            virtual[canonical] = content
        for item in files:
            target, path = allowed(item["path"])
            if path in edited or not isinstance(item["edits"], list) or not item["edits"]:
                return None
            edited.add(path)
            if path not in originals:
                originals[path] = target.read_text(encoding="utf-8", errors="replace")
            text = virtual.get(path, originals[path])
            before = text
            for edit in item["edits"]:
                old, new = edit["search"], edit["replace"]
                if not isinstance(old, str) or not isinstance(new, str) or not old or old == new or text.count(old) != 1:
                    return None
                text = text.replace(old, new)
            if text == before:
                return None
            virtual[path] = text
    except (RepairBenchError, ValueError, OSError, KeyError, TypeError):
        return None
    changed = sorted((path, content) for path, content in virtual.items() if content != originals[path])
    if not changed or len(changed) > 3:
        return None
    depth = (parent.provenance or {}).get("branch_depth", 0) + 1
    provenance = {"branch_parent_digest": parent.digest, "branch_depth": depth}
    return Candidate(*changed[0], origin, description, provenance=provenance, extra_files=tuple(changed[1:]))
