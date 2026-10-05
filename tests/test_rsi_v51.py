"""V51 structured-memory engineering tests on project-authored development tasks."""
import sqlite3

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import bank, benchmark, engine
from experiment.rsi_v51.memory import ExperimentalMemory


def _first_row():
    task = bank.stream(bank.DEVELOPMENT_SEEDS[0])[0]
    return task, v32.episode(task, 0, {}, "cold", 25, isolated=False)


def test_memory_persists_and_deduplicates_semantics(tmp_path):
    task, row = _first_row()
    db = ExperimentalMemory(tmp_path / "memory.db")
    row = dict(row)
    row["position"] = 0
    db.remember_episode(row)
    before = db.counts()
    assert before["strategies"] > 0
    assert before["experiences"] == before["evaluations"]

    # Same behavioral programs on the same task do not inflate strategy/experience counts.
    db.remember_episode(row)
    assert db.counts()["strategies"] == before["strategies"]
    assert db.counts()["experiences"] == before["experiences"]
    db.close()

    reopened = ExperimentalMemory(tmp_path / "memory.db")
    assert reopened.counts()["strategies"] == before["strategies"]
    reopened.close()


def test_retrieval_is_deterministic_and_uses_observed_signature_only(tmp_path):
    task, row = _first_row()
    db = ExperimentalMemory(tmp_path / "memory.db")
    row = dict(row)
    row["position"] = 0
    db.remember_episode(row)
    signature = db.observed_signature(row["root_evaluation"]["quality_milli"])
    a = db.retrieve(signature, position=1, top_k=2)
    b = db.retrieve(signature, position=1, top_k=2)
    assert a == b and a
    assert all(hit.score > 0 for hit in a)
    assert len(signature) == 1
    db.close()


def test_usage_feedback_changes_utility_without_mutating_evidence(tmp_path):
    _, row = _first_row()
    db = ExperimentalMemory(tmp_path / "memory.db")
    row = dict(row)
    row["position"] = 0
    db.remember_episode(row)
    signature = db.observed_signature(row["root_evaluation"]["quality_milli"])
    hit = db.retrieve(signature, position=1, top_k=1)[0]
    old = hit.utility
    db.record_usage(
        task_sha256="1" * 64,
        hit=hit,
        position=1,
        rank=0,
        impact_quality_milli=100,
        impact_evaluations=2,
    )
    new = db.retrieve(signature, position=1, top_k=1)[0]
    assert new.utility > old
    contribution = db.contribution()
    assert contribution["uses"] == 1
    assert contribution["helpful_uses"] == 1
    db.close()


def test_v51_engine_reuses_db_under_inherited_cap(tmp_path):
    tasks = bank.stream(bank.DEVELOPMENT_SEEDS[0])[:2]
    db = ExperimentalMemory(tmp_path / "memory.db")
    first = engine.episode(tasks[0], 0, db, isolated=False)
    engine.remember(db, first)
    second = engine.episode(tasks[1], 1, db, isolated=False)
    assert second["routing"]["retrieved_sources"]
    assert second["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert second["routing"]["controller_calls"] == 1
    assert second["routing"]["context_signature"] == [
        second["root_evaluation"]["quality_milli"] / 1000.0
    ]
    db.close()


def test_matched_benchmark_compares_db_archive_and_cold(tmp_path):
    result = benchmark.run(
        bank.DEVELOPMENT_SEEDS[0],
        tmp_path / "memory.db",
        isolated=False,
        limit=12,
    )
    assert result["tasks"] == 12
    assert set(result) >= {
        "db", "archive", "cold", "memory_contribution",
        "memory_counts", "predicates", "l9_general_open_ended_passed",
    }
    assert result["db"]["memory_routes"] > 0
    assert result["memory_contribution"]["uses"] > 0
    assert result["memory_counts"]["strategies"] > 0
    assert result["l9_general_open_ended_passed"] is False
    assert result["population_scope"] == "PROJECT_AUTHORED_FINITE_DEVELOPMENT"


def test_population_is_committed_and_distinct_from_v32_fresh():
    assert len(bank.DEVELOPMENT_SEEDS) == 3
    assert len({digest(task) for seed in bank.DEVELOPMENT_SEEDS for task in bank.stream(seed)}) == 288
    assert bank.WINDOWS == 8
