"""Contrôles hors réseau du diagnostic de vivacité de la lignée CIRCUIT2."""
from __future__ import annotations

import json

import pytest

try:
    import circuit2_lineage_liveness as liveness
except ImportError:
    from scripts import circuit2_lineage_liveness as liveness

from genesis import circuit_engine as engine
from genesis import circuit_tasks as tasks

SMALL = dict(budgets=((16, 1096),), seeds=(0,), generations=2)
KEYS = {"index", "solved", "spend", "spend_total", "n_evaluated", "adopted", "exhausted", "library_size", "library_digest", "procedure_digest"}


@pytest.fixture(scope="module")
def result():
    return liveness.run(**SMALL)


def test_budget_16_synthesises_nothing_and_the_output_has_its_keys(result):
    assert result["schema"] == "circuit2-lineage-liveness-v1"
    assert result["held_out_reads"] == 0
    assert result["learn_task_count"] > 0
    (entry,) = result["runs"]
    assert len(entry["generations"]) == 2
    for key in ("synthesis_total", "adoptions_total", "library_sizes", "grows_after_generation_1"):
        assert key in entry
    assert entry["synthesis_total"] == 0
    for index, record in enumerate(entry["generations"], start=1):
        assert set(record) == KEYS
        assert record["index"] == index
        assert record["spend"]["synthesis"] == 0
        size = record["library_size"]
        assert isinstance(size, int) and not isinstance(size, bool) and size >= 0


def test_a_held_out_family_is_refused_before_any_lineage_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("run_lineage ne doit pas être appelé")

    monkeypatch.setattr(liveness.circuit_meta_lineage, "run_lineage", forbidden)
    for family in tasks.HELD_OUT:
        bad = engine.Task("held", family, 2, 0b0110)
        with pytest.raises(liveness.LivenessError):
            liveness.run(tasks=[bad], **SMALL)


def test_the_families_read_are_learn_only(result):
    families = set(result["families"])
    assert families and families <= set(tasks.LEARN)
    assert not families & set(tasks.HELD_OUT)
    assert not families & set(getattr(tasks, "CONTROL", ()))
    assert result["families"] == sorted(result["families"])


def test_writing_refuses_outside_results_and_overwrite(tmp_path, monkeypatch):
    allowed = tmp_path / "results"
    monkeypatch.setattr(liveness, "RESULTS_DIR", allowed)
    with pytest.raises(liveness.LivenessError):
        liveness.write_result({"a": 1}, tmp_path / "elsewhere.json")
    with pytest.raises(liveness.LivenessError):
        liveness.write_result({"a": 1}, allowed / ".." / "escape.json")
    assert not (tmp_path / "elsewhere.json").exists()
    assert not (tmp_path / "escape.json").exists()
    target = allowed / "out.json"
    liveness.write_result({"a": 1}, target)
    before = target.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        liveness.write_result({"a": 2}, target)
    assert target.read_text(encoding="utf-8") == before
    assert json.loads(before) == {"a": 1}


def test_main_returns_one_for_a_refused_path(tmp_path, monkeypatch):
    monkeypatch.setattr(liveness, "RESULTS_DIR", tmp_path / "results")
    assert liveness.main(["--out", str(tmp_path / "x.json")]) == 1


def test_two_identical_runs_give_the_same_json(result):
    again = liveness.run(**SMALL)
    assert json.dumps(again, sort_keys=True) == json.dumps(result, sort_keys=True)
