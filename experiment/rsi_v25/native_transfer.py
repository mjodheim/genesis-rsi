"""Project-authored fresh tasks on byte-exact native public host snapshots.

Candidate generation changes only two declared production expressions. Evaluator
code, cases, source reference, quality rule and caps remain external. This is
bounded repair transfer, not an independent external-maintainer/general AGI gate.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import HERE, digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps, run_search

TRANSFER_CAPS = Caps()
TASKS = (
    {"task_id": "cellar-batch-stock-ship", "source": "Batch.java",
     "harness": "BatchHarness.java", "runtime": "java",
     "loci": (
         ("availableQuantity", ("quantityOnHand - quantityReserved;", "quantityOnHand + quantityReserved;", "quantityOnHand;")),
         ("shipReserved", ("quantityReserved -= quantity; quantityOnHand -= quantity;",
                           "quantityReserved += quantity; quantityOnHand -= quantity;",
                           "quantityReserved -= quantity; quantityOnHand += quantity;")),
     )},
    {"task_id": "cellar-order-line-total-snapshot", "source": "OrderLine.java",
     "harness": "OrderLineHarness.java", "runtime": "java",
     "loci": (
         ("lineTotal", ("unitPrice.multiply(BigDecimal.valueOf(quantity))", "unitPrice.add(BigDecimal.valueOf(quantity))",
                        "unitPrice.subtract(BigDecimal.valueOf(quantity))")),
         ("nameSnapshot", ("this.productName=productName.trim()", "this.productName=productName",
                           "this.productName=productName.toUpperCase()")),
     )},
    {"task_id": "arcade-fruit-occupancy-path", "source": "fruit.js",
     "harness": "fruit_harness.js", "runtime": "node",
     "loci": (
         ("tailVacancy", ("sn === mover && !sn.grow ? 1 : 0", "!sn.grow ? 1 : 0", "0")),
         ("blockedPath", ("(blocked.has(nk) && nk !== goal)", "blocked.has(nk)", "false")),
     )},
    {"task_id": "arcade-goose-collision-honk", "source": "goose.js",
     "harness": "goose_harness.js", "runtime": "node",
     "loci": (
         ("carBounds", ("car.horizontal ? 30 : 15, hh = car.horizontal ? 15 : 30",
                        "car.horizontal ? 15 : 30, hh = car.horizontal ? 30 : 15",
                        "30, hh = 30")),
         ("honkWindow", ("s.time - g.honkAt < HONK_COOLDOWN", "s.time - g.honkAt <= HONK_COOLDOWN",
                         "s.time - g.honkAt > HONK_COOLDOWN")),
     )},
)


def render_native(task, choices):
    if len(choices) != 2 or any(type(x) is not int or x not in (0, 1, 2) for x in choices):
        raise ValueError("Native mutation outside the frozen grammar")
    raw = (HERE / "native_sources" / task["source"]).read_text()
    for (_, variants), choice in zip(task["loci"], choices):
        if raw.count(variants[0]) != 1:
            raise ValueError("Native mutation anchor is ambiguous or changed")
        raw = raw.replace(variants[0], variants[choice])
    return raw


def evaluate_native(task, choices):
    source = render_native(task, choices)
    source_hash = digest_bytes(source.encode())
    harness = HERE / "native_harnesses" / task["harness"]
    with tempfile.TemporaryDirectory(prefix="v25-native-evaluator-") as temporary:
        directory = Path(temporary)
        native = directory / task["source"]
        native.write_text(source)
        if task["runtime"] == "java":
            compile_command = ["java", "com.sun.tools.javac.Main", "-d", str(directory / "classes"),
                               str(native), str(harness)]
            built = subprocess.run(compile_command, capture_output=True, text=True, timeout=20, check=False)
            if built.returncode:
                raise RuntimeError(f"Native Java instrument failed: {built.stderr[:2000]}")
            command = ["java", "-cp", str(directory / "classes"), harness.stem]
        else:
            command = ["node", str(harness), str(native)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if completed.returncode:
            raise RuntimeError(f"Native evaluator instrument failed: {completed.stderr[:2000]}")
        cases = json.loads(completed.stdout)
    if (set(cases) != {"passed", "total", "failed"} or type(cases["passed"]) is not int
            or type(cases["total"]) is not int or cases["total"] <= 0
            or not 0 <= cases["passed"] <= cases["total"]
            or cases["total"] - cases["passed"] != len(cases["failed"])):
        raise ValueError("Invalid native evaluator receipt")
    return {"accepted": True, "source_sha256": source_hash,
            "quality_milli": cases["passed"] * 1000 // cases["total"],
            "cases": cases, "cases_sha256": digest(cases),
            "task_sha256": digest(task), "harness_sha256": digest_bytes(harness.read_bytes()),
            "runtime": task["runtime"], "native_source_executed": True}


def host_calibration():
    """Reference and seeded roots only: never execute a successor on transfer."""
    rows = []
    for task in TASKS:
        reference, seeded = evaluate_native(task, (0, 0)), evaluate_native(task, (1, 1))
        if reference["quality_milli"] != 1000 or seeded["quality_milli"] == 1000:
            raise ValueError("Native task is not calibrated to a real seeded defect")
        rows.append({"task_id": task["task_id"], "reference": reference, "seeded": seeded})
    return {"scope": "REFERENCE_AND_SEEDED_ROOT_CALIBRATION_ONLY", "tasks": rows,
            "population_sha256": digest(TASKS), "successor_executed": False}


class NativeHost:
    def __init__(self, task, seeded):
        self.task, self.seeded = task, seeded
        self.forbidden_tokens = [task["task_id"], task["source"], task["harness"]]

    def _row(self, choices):
        return {"candidate": {"choices": list(choices)},
                "source_sha256": digest_bytes(render_native(self.task, choices).encode())}

    def root(self):
        return {**self._row((1, 1)), "quality_milli": self.seeded["quality_milli"]}

    def children(self, candidate, depth):
        if depth >= TRANSFER_CAPS.mutation_depth:
            return ()
        parent, rows = candidate["choices"], []
        for axis in range(2):
            for value in (0, 1, 2):
                if value != parent[axis]:
                    child = list(parent)
                    child[axis] = value
                    rows.append(self._row(child))
        # Source identity is outcome-independent; no quality-based child order.
        return tuple(sorted(rows, key=lambda row: row["source_sha256"]))

    def evaluate(self, row):
        return evaluate_native(self.task, row["candidate"]["choices"])

    def action(self, row):
        choices = row["candidate"]["choices"]
        changed = [name for (name, _), choice in zip(self.task["loci"], choices) if choice != 1]
        return {"family": "native-production-repair", "target_axes": changed,
                "mechanisms": [f"expression-{i}-{v}" for i, v in enumerate(choices) if v != 1] or ["seeded-root"],
                "changed_regions": changed}

    def generation(self, row, depth):
        return 0


def run_native_policy(source, calibration, checkpoint=None):
    seeded = {row["task_id"]: row["seeded"] for row in calibration["tasks"]}
    results = []
    for task in TASKS:
        results.append({"task_id": task["task_id"], **run_search(
            source, NativeHost(task, seeded[task["task_id"]]), caps=TRANSFER_CAPS, isolated=True)})
        if checkpoint:
            checkpoint(results)
    return results
