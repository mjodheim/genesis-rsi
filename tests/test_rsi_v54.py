"""V54 recursive scaffold-refinement tests."""
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v54 import benchmark, engine
from experiment.rsi_v54.refinements import (
    RefinementMemory,
    apply_refinement,
    derive_refinements,
)


def _synthetic_lineage_row():
    base = {"width": 10, "rotation": 2, "mask": 0}
    solved = {"width": 10, "rotation": 2, "mask": 0b1000}
    return base, {
        "position": 7,
        "task_sha256": "synthetic-task",
        "root_evaluation": {"quality_milli": 550},
        "programs": [{
            "source_sha256": "synthetic-descendant",
            "quality_milli": 1000,
            "genome": solved,
            "descended_from_scaffold": True,
            "scaffold_generation": 1,
            "scaffold_base_genome": base,
            "scaffold_base_source_sha256": "synthetic-base",
            "scaffold_ancestor_refinement_id": None,
        }],
    }


def test_refinement_operator_transfers_delta():
    base = {"width": 8, "rotation": 2, "mask": 0}
    solved = {"width": 8, "rotation": 3, "mask": 0b1000}
    operators = derive_refinements(base, solved)
    assert operators
    transferred = apply_refinement(
        next(op for op in operators if op["mode"] == "low"),
        {"width": 10, "rotation": 4, "mask": 0},
    )
    assert transferred["rotation"] == 5
    assert transferred["mask"] == 0b1000


def test_refinement_memory_learns_generation_two(tmp_path):
    base, row = _synthetic_lineage_row()
    memory = RefinementMemory(tmp_path / "refinements.db")
    inserted = memory.remember_episode(row)
    counts = memory.counts()
    assert inserted > 0
    assert counts["refinements"] > 0
    assert counts["max_lineage_depth"] == 2
    hit = memory.retrieve(
        root_quality_milli=550,
        width=11,
        position=8,
        top_k=1,
    )[0]
    refined = apply_refinement(
        hit.operator,
        {"width": 11, "rotation": 2, "mask": 0},
    )
    assert refined != {"width": 11, "rotation": 2, "mask": 0}
    assert hit.lineage_depth == 2
    memory.close()


def test_v54_refined_scaffold_keeps_v53_root_budget(tmp_path):
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    refinements = RefinementMemory(tmp_path / "refinements.db")

    abstract.remember_episode({
        "position": 0,
        "root_evaluation": {"quality_milli": 550},
        "programs": [{
            "quality_milli": 1000,
            "genome": {"width": 9, "rotation": 2, "mask": 0},
        }],
    })
    _, lineage = _synthetic_lineage_row()
    refinements.remember_episode(lineage)

    task = {
        "task_id": "v54-unit",
        "window": 7,
        "family": "affine",
        "width": 10,
        "inputs": [0, 1, 2, 4, 8, 16, 32, 63, 127, 255, 511, 1023],
        "target": {"width": 10, "rotation": 2, "mask": 0b1000},
    }
    row = engine.episode(
        task, 84, exact, abstract, refinements,
        isolated=False,
    )
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert len(row["routing"]["scaffold_sources"]) <= engine.SCAFFOLD_TOP_K
    assert len(row["routing"]["refined_scaffold_sources"]) <= engine.REFINEMENT_TOP_K

    exact.close()
    abstract.close()
    refinements.close()


def test_v54_matched_benchmark_runs(tmp_path):
    tasks = []
    # A deterministic miniature stream with early and late widths.
    for window, width in enumerate((3, 4, 10, 11)):
        for index in range(3):
            tasks.append({
                "task_id": f"mini-{window}-{index}",
                "window": window,
                "family": "affine",
                "width": width,
                "inputs": list(range(min(1 << width, 16))),
                "target": {
                    "width": width,
                    "rotation": 1 % width,
                    "mask": 1 << (index % width),
                },
            })
    result = benchmark.run(
        999999,
        tmp_path,
        tasks=tasks,
        isolated=False,
        scope="TEST",
    )
    assert result["tasks"] == len(tasks)
    assert result["v54"]["evaluations"] <= (
        len(tasks) * engine.MAX_EVALUATIONS
    )
    assert result["l9_general_open_ended_passed"] is False
