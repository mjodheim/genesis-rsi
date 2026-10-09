"""Generation zero of the fault localizer: the stack-trace rule the repair bench already uses.

This file is the starting point of a lineage whose later members are written by a model and
stored as data. It is self-contained on purpose (standard library only, one entry point) because
it runs inside a container that holds nothing else.

``localize(case)`` receives::

    {"root": "<directory holding the buggy sources>",
     "source_directory": "<production sources, relative to root>",
     "test_directory": "<test sources, relative to root>",
     "failing_tests": ["pkg.SomeTest::method", ...],
     "report": "<the failing tests' stack traces, each introduced by '--- pkg.SomeTest::method'>"}

and returns suspect locations, most suspect first, as ``[[path relative to root, line], ...]``.
Only the first six are used; each one stands for the lines within forty lines of it.
"""
import os
import re

FRAME = re.compile(r"^\s+at ([\w.$]+)\.[\w$<>]+\(([\w$]+\.java):(\d+)\)", re.MULTILINE)


def localize(case):
    root = case["root"]
    source = case["source_directory"]

    def resolve(classname):
        path = source + "/" + classname.split("$", 1)[0].replace(".", "/") + ".java"
        return path if os.path.isfile(os.path.join(root, path)) else None

    suspects = []
    for classname, _, line in FRAME.findall(case["report"]):
        path = resolve(classname)
        if path is not None and [path, int(line)] not in suspects:
            suspects.append([path, int(line)])
    if not suspects:
        # A trace that never enters production code still names the test: fall back to the
        # class the test is named after.
        for name in case["failing_tests"]:
            path = resolve(re.sub(r"Tests?$", "", name.split("::")[0]))
            if path is not None and [path, 1] not in suspects:
                suspects.append([path, 1])
    return suspects[:6]
