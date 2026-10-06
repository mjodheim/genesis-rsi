from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import re
import sys
import tempfile

WORKSPACE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORKSPACE))

from docutils.core import publish_doctree
from myst_parser.parsers.docutils_ import Parser


def role_warning_line(files: dict[str, str], *, target: str) -> tuple[int | None, str]:
    with tempfile.TemporaryDirectory(prefix="genesis-a6-task006-") as temp:
        root = Path(temp)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        stream = StringIO()
        publish_doctree(
            (root / "main.md").read_text(encoding="utf-8"),
            source_path=str(root / "main.md"),
            parser=Parser(),
            settings_overrides={"halt_level": 6, "warning_stream": stream},
        )
        text = stream.getvalue()
        pattern = re.compile(
            rf"{re.escape(target)}:(\d+): .*\[myst\.role_unknown\]"
        )
        match = pattern.search(text)
        return (None if match is None else int(match.group(1))), text


CASES = [
    {
        "name": "plain-include",
        "target": "sub.md",
        "expected_line": 3,
        "files": {
            "main.md": "~~~{include} sub.md\n~~~\n",
            "sub.md": "line one\n\n{unknownrole}`x`\n",
        },
    },
    {
        "name": "start-line",
        "target": "sub.md",
        "expected_line": 5,
        "files": {
            "main.md": "~~~{include} sub.md\n:start-line: 2\n~~~\n",
            "sub.md": "skip0\nskip1\nline three\n\n{unknownrole}`x`\n",
        },
    },
    {
        "name": "nested-include",
        "target": "inner.md",
        "expected_line": 3,
        "files": {
            "main.md": "~~~{include} outer.md\n~~~\n",
            "outer.md": "outer\n\n~~~{include} inner.md\n~~~\n",
            "inner.md": "inner one\n\n{unknownrole}`x`\n",
        },
    },
    {
        "name": "heading-offset",
        "target": "sub.md",
        "expected_line": 3,
        "files": {
            "main.md": "~~~{include} sub.md\n:heading-offset: 1\n~~~\n",
            "sub.md": "# Head\n\n{unknownrole}`x`\n",
        },
    },
    {
        "name": "front-matter",
        "target": "sub.md",
        "expected_line": 5,
        "files": {
            "main.md": "~~~{include} sub.md\n~~~\n",
            "sub.md": "---\ntitle: X\n---\n\n{unknownrole}`x`\n",
        },
    },
]

results = []
for case in CASES:
    actual, raw = role_warning_line(case["files"], target=case["target"])
    results.append(
        {
            "name": case["name"],
            "expected_line": case["expected_line"],
            "actual_line": actual,
            "ok": actual == case["expected_line"],
            "warning_sha256_input": raw,
        }
    )

# Keep the report compact while retaining exact observed line facts.
for item in results:
    item.pop("warning_sha256_input", None)

payload = {
    "schema": "mira-genesis-a6-task006-evaluator-v1",
    "objective_ok": all(item["ok"] for item in results),
    "case_count": len(results),
    "results": results,
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
