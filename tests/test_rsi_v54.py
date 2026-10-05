"""V54 recursive scaffold-lineage tests."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory, derive_recipes
from experiment.rsi_v53 import bank as v53_bank
from experiment.rsi_v54 import benchmark, engine
from experiment.rsi_v54.lineage import LineageMemory


def test_lineage_memory_credits_successful_scaffold_descendant(tmp_path):
    lineage = LineageMemory(tmp_path / "lineage.db")
    scaffold = {"width": 10, "rotation": 2, "mask": 0}
    child = {"width": 10, "rotation": 2, "mask": 1}
    scaffold_sha = digest(scaffold)
    child_sha = digest(child)
    row = {
        "position": 10,
        "task_sha256": "task",
        "routing": {
            "scaffold_sources": [scaffold_sha],
            "scaffold_recipe_ids": [7],
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
    rotation = [r for r in derive_recipes(child) if r["mode"] == "rotation"][0]
    credit = lineage.credit_for(rotation)
    assert credit.recursive_successes == 1
    assert credit.max_depth >= 1
    lineage.close()


def test_v54_engine_keeps_inherited_cap(tmp_path):
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    lineage = LineageMemory(tmp_path / "lineage.db")
    task = v53_bank.stream(v53_bank.FRESH_SEEDS[0])[0]
    row = engine.episode(task, 0, exact, abstract, lineage, isolated=False)
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert row["routing"]["scaffold_pool"] == engine.SCAFFOLD_POOL
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
