"""The inherited lineage discovers its selector using measured public receipts."""
import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import GUARD
from experiment.rsi_v27.engine import CAPS, call, development_functions, run_search
from experiment.rsi_v28.family import genotype, render_genotype, structure, syntax_changes
from experiment.rsi_v30 import family
from experiment.rsi_v30.pipeline_contexts import PARTS, TARGETS, qualified_genotype

HERE = Path(__file__).parent


def select(source, diagnostics, *, isolated=True):
    if GUARD.guard_source(source, []):
        raise ValueError("Target selector violates the immutable policy guard")
    payload = {"mode": "target", "diagnostics": diagnostics, "targets": list(TARGETS)}
    if isolated:
        with tempfile.TemporaryDirectory(prefix="v30-selector-") as temporary:
            path = Path(temporary) / "policy.py"
            path.write_text(source)
            response = call(path, payload)
            target = response["target"]
            if response["metadata"] != list(development_functions(family.parent(), ())["policy_metadata"]()):
                raise ValueError("Target selection changed inherited metadata")
    else:
        function = development_functions(source, ()).get("select_target")
        target = function(diagnostics, list(TARGETS)) if function else TARGETS[0]
    if type(target) is not str or target not in TARGETS:
        raise ValueError("Target selection exceeded the fixed repair authority")
    return target


def context_utility(rows):
    return (sum(row["post"]["best_quality_milli"] == 1000 for row in rows),
            sum(row["post"]["best_quality_milli"] for row in rows),
            -sum(row["baseline"]["represented_requests"] + row["post"]["represented_requests"] + 1 for row in rows),
            -sum(row["baseline"]["rounds"] + row["post"]["rounds"] + 1 for row in rows))


def calibration(public):
    result = []
    for candidate in family.universe():
        source = family.render(candidate["flags"])
        rows, successes = [], 0
        for row in public["contexts"]:
            target = select(source, row["diagnostics"], isolated=False)
            utility = tuple(row["utilities"][target])
            successes += utility > tuple(row["utilities"]["identity"]) and utility == max(
                tuple(value) for value in row["utilities"].values())
            rows.append({"context_sha256": row["context_sha256"], "target": target,
                         "baseline": row["baseline"], "post": row["variants"][target]})
        result.append({**candidate, "target_choices": [row["target"] for row in rows],
                       "correct_improvements": successes, "quality_milli": successes * 1000 // len(rows),
                       "utility": context_utility(rows), "public_receipts_sha256": digest(rows)})
    return {"scope": "OUTCOME_CONDITIONED_PUBLIC_CALIBRATION_NOT_FRESH",
            "new_holdout_consumed": False, "public_contexts_sha256": digest(public), "candidates": result}


class Host:
    forbidden_tokens = []

    def __init__(self, measured):
        self.rows = {tuple(row["flags"]): row for row in measured["candidates"]}
        self.descriptors = {flags: {"structure_sha256": structure(family.render(flags)),
                                   "target_axes": syntax_changes(family.render(flags), family.parent())}
                            for flags in self.rows}

    def qualified(self, flags):
        row = self.rows[flags]
        if row["quality_milli"] != 1000:
            return False
        return all(self.rows[tuple(0 if i == index else x for i, x in enumerate(flags))]["quality_milli"] < 1000
                   for index in range(3) if flags[index])

    def row(self, flags):
        flags = family.validate(flags)
        return {"candidate": {"flags": flags}, "source_sha256": digest_bytes(family.render(flags).encode()),
                "quality_milli": self.rows[flags]["quality_milli"]}

    def root(self):
        return self.row(family.ROOT_FLAGS)

    def children(self, candidate, depth):
        return tuple(self.row(flags) for flags in family.neighbors(candidate["flags"])) if depth < CAPS.mutation_depth else ()

    def action(self, row):
        return {"family": "executable-target-selector", **self.descriptors[tuple(row["candidate"]["flags"])]}

    def evaluate(self, row):
        flags = tuple(row["candidate"]["flags"])
        return {"accepted": True, "source_sha256": row["source_sha256"], "quality_milli": row["quality_milli"],
                "qualified": self.qualified(flags), "public_receipt_sha256": digest(self.rows[flags])}


def choose(search, host):
    candidates = [node for node in search["nodes"].values() if host.qualified(tuple(node["candidate"]["flags"]))]
    if not candidates:
        return {"qualified_discovery": False, "flags": family.ROOT_FLAGS,
                "source_sha256": digest_bytes(family.parent().encode())}
    candidates.sort(key=lambda node: (sum(node["candidate"]["flags"]), node["source_sha256"]))
    node = candidates[0]
    return {"qualified_discovery": True, "flags": node["candidate"]["flags"], "source_sha256": node["source_sha256"]}


def utility(selected, search):
    return (int(selected["qualified_discovery"]), search["best_quality_milli"],
            -search["represented_requests"], -search["rounds"])


def scheduling_ablation():
    inherited = qualified_genotype()
    return render_genotype(genotype({**inherited["params"], "scheduling": 0}, inherited["layout"]))


def pilot(measured, *, isolated=False):
    host = Host(measured)
    arms = {}
    for name, source in (("inherited_g6", family.parent()), ("g6_scheduling_ablation", scheduling_ablation())):
        search = run_search(source, host, caps=CAPS, isolated=isolated)
        selected = choose(search, host)
        arms[name] = {"search": search, "selected": selected, "utility": utility(selected, search)}
    return {"scope": "PUBLIC_DEVELOPMENT_PILOT_NOT_CANONICAL", "new_holdout_consumed": False, "arms": arms}
