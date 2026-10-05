"""V54 recursive scaffold-lineage tests."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import bank as v53_bank
from experiment.rsi_v54 import benchmark, engine
from experiment.rsi_v54.lineage import LineageMemory


def test_lineage_memory_reuses_affine_descendant_and_increases_generation_depth(tmp_path):
    lineage = LineageMemory(tmp_path / "lineage.db")

    scaffold = {"width": 10, "rotation": 2, "mask": 0}
    child = {"width": 10, "rotation": 2, "mask": 1}
    scaffold_sha = digest(scaffold)
    child_sha = digest(child)
    row = {
        "position": 10,
        "task_sha256": "task-1",
        "routing": {
            "scaffold_lineage": {
                scaffold_sha: {
                    "kind": "rotation",
                    "provenance_key": "rotation:7",
                    "recursive_successes": 0,
                    "max_depth": 0,
                    "lineage_score": 0.0,
                }
            },
        },
        "programs": [
            {
                "source_sha256": scaffold_sha,
                "semantic_sha256": scaffold_sha,
                "genome": scaffold,
                "quality_milli": 700,
                "search_parent_source_sha256": None,
            },
            {
                "source_sha256": child_sha,
                "semantic_sha256": child_sha,
                "genome": child,
                "quality_milli": 1000,
                "search_parent_source_sha256": scaffold_sha,
            },
        ],
    }
    assert lineage.remember_episode(row) > 0
    hits = lineage.retrieve(width=14, position=20, top_k=1)
    assert hits
    hit = hits[0]
    assert hit.genome["rotation"] == 2
    assert hit.genome["mask"] != 0
    assert hit.max_depth == 1

    # A success descended from the lineaged affine scaffold creates generation 2.
    scaffold2_sha = digest(hit.genome)
    child2 = {
        "width": 14,
        "rotation": hit.genome["rotation"],
        "mask": hit.genome["mask"] | (1 << 2),
    }
    child2_sha = digest(child2)
    row2 = {
        "position": 20,
        "task_sha256": "task-2",
        "routing": {
            "scaffold_lineage": {
                scaffold2_sha: {
                    "kind": "lineage",
                    "provenance_key": hit.recipe_sha256,
                    "recursive_successes": hit.recursive_successes,
                    "max_depth": hit.max_depth,
                    "lineage_score": hit.score,
                }
            },
        },
        "programs": [
            {
                "source_sha256": scaffold2_sha,
                "semantic_sha256": scaffold2_sha,
                "genome": hit.genome,
                "quality_milli": 800,
                "search_parent_source_sha256": None,
            },
            {
                "source_sha256": child2_sha,
                "semantic_sha256": child2_sha,
                "genome": child2,
                "quality_milli": 1000,
                "search_parent_source_sha256": scaffold2_sha,
            },
        ],
    }
    assert lineage.remember_episode(row2) > 0
    assert lineage.counts()["max_depth"] >= 2
    lineage.close()


def test_v54_engine_keeps_inherited_cap(tmp_path):
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    lineage = LineageMemory(tmp_path / "lineage.db")
    task = v53_bank.stream(v53_bank.FRESH_SEEDS[0])[0]
    row = engine.episode(task, 0, exact, abstract, lineage, isolated=False)
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert row["routing"]["lineage_top_k"] == engine.LINEAGE_TOP_K
    engine.remember(exact, abstract, lineage, row)
    exact.close()
    abstract.close()
    lineage.close()


def test_v54_matched_benchmark_runs_against_v53(tmp_path):
    tasks = v53_bank.stream(v53_bank.FRESH_SEEDS[0])[:24]
    result = benchmark.run(
        v53_bank.FRESH_SEEDS[0],
        tmp_path,
        tasks=tasks,
        isolated=False,
    )
    assert result["tasks"] == 24
    assert set(result) >= {
        "v54", "v53", "v52", "v51", "archive", "cold",
        "lineage_counts", "lineage_events_recorded", "deltas",
    }
    assert result["v54"]["evaluations"] <= 24 * engine.MAX_EVALUATIONS
    assert result["l9_general_open_ended_passed"] is False
