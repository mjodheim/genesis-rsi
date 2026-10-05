"""V52 cross-width abstraction-memory tests."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import bank
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52 import benchmark, engine
from experiment.rsi_v52.abstractions import AbstractionMemory, derive_recipes, instantiate


def test_recipe_derivation_and_cross_width_instantiation():
    genome = {"width": 4, "rotation": 1, "mask": 0b1001}
    recipes = derive_recipes(genome)
    assert {row["mode"] for row in recipes} >= {
        "low", "high", "scaled", "rotation", "mask_low", "mask_high", "mask_scaled"
    }
    instantiated = [instantiate(row, 8) for row in recipes]
    assert all(row["width"] == 8 for row in instantiated)
    assert len({digest(row) for row in instantiated}) >= 4


def test_abstraction_memory_persists_success_recipes(tmp_path):
    task = bank.stream(bank.DEVELOPMENT_SEEDS[0])[0]
    row = v32.episode(task, 0, {}, "cold", 25, isolated=False)
    memory = AbstractionMemory(tmp_path / "abstract.db")
    memory.remember_episode(row)
    counts = memory.counts()
    assert counts["recipes"] > 0 and counts["contexts"] > 0
    hits = memory.retrieve(
        root_quality_milli=row["root_evaluation"]["quality_milli"],
        width=task["width"] + 1, position=1, top_k=4,
    )
    assert hits
    assert all(instantiate(hit.recipe, task["width"] + 1)["width"] == task["width"] + 1 for hit in hits)
    memory.close()


def test_v52_engine_keeps_inherited_cap_and_exercises_abstraction(tmp_path):
    tasks = bank.stream(bank.DEVELOPMENT_SEEDS[0])[:13]
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    rows = []
    for position, task in enumerate(tasks):
        row = engine.episode(task, position, exact, abstract, isolated=False)
        assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
        engine.remember(exact, abstract, row)
        rows.append(row)
    assert any(row["routing"]["abstract_sources"] for row in rows[1:])
    exact.close()
    abstract.close()


def test_matched_benchmark_compares_v52_v51_archive_and_cold(tmp_path):
    result = benchmark.run(
        bank.DEVELOPMENT_SEEDS[0], tmp_path, isolated=False, limit=16, abstract_top_k=4
    )
    assert result["tasks"] == 16
    assert set(result) >= {
        "v52", "v51", "archive", "cold", "abstraction_counts",
        "abstraction_contribution", "deltas", "l9_general_open_ended_passed",
    }
    assert result["v52"]["abstract_routes"] > 0
    assert result["abstraction_counts"]["recipes"] > 0
    assert result["l9_general_open_ended_passed"] is False


from experiment.rsi_v52 import bank as fresh_bank, campaign


def test_prospective_population_is_committed_and_wider_than_v51():
    assert not set(fresh_bank.FRESH_SEEDS) & set(bank.DEVELOPMENT_SEEDS)
    tasks = [task for seed in fresh_bank.FRESH_SEEDS for task in fresh_bank.stream(seed)]
    assert len(tasks) == 432
    assert len({digest(task) for task in tasks}) == 432
    assert {task["width"] for task in tasks} == set(range(3, 15))
    assert fresh_bank.WINDOWS == 12


def test_scoped_adjudication_requires_every_seed_window_positive():
    def row(seed):
        return {
            "seed": seed,
            "tasks": 144,
            "v52": {
                "solved": 80, "evaluations": 1200,
                "abstract_candidates_evaluated": 10,
            },
            "v51": {"solved": 78, "evaluations": 1220},
            "archive": {"solved": 82},
            "cold": {"solved": 70},
            "v52_first_discoveries_by_window": {str(i): 1 for i in range(12)},
            "abstraction_contribution": {"uses": 10},
        }
    rows = [row(seed) for seed in fresh_bank.FRESH_SEEDS]
    result = campaign.adjudicate(rows)
    assert result["scoped_sustained_abstraction_assay_passed"]
    rows[0]["v52_first_discoveries_by_window"]["11"] = 0
    negative = campaign.adjudicate(rows)
    assert not negative["scoped_sustained_abstraction_assay_passed"]
    assert not negative["l9_general_open_ended_passed"]
