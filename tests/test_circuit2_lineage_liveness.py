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
KEYS = {"index", "solved", "solved_source", "spend", "spend_total", "n_evaluated", "adopted", "exhausted", "library_size", "library_digest", "procedure_digest"}


@pytest.fixture(scope="module")
def result():
    return liveness.run(**SMALL)


def test_budget_16_synthesises_nothing_and_the_output_has_its_keys(result):
    assert result["schema"] == "circuit2-lineage-liveness-v1"
    assert result["held_out_families_in_input"] == 0
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


def _state(index, score, parent_score, synthesis, adopted, size):
    return {
        "index": index,
        "score": score,
        "parent_score": parent_score,
        "spent": {"synthesis": synthesis, "search": 1},
        "evaluated": ["t1", "t2"],
        "adopted": adopted,
        "exhausted": False,
        "library": [f"l{i}" for i in range(size)],
        "procedure": {"procedure_digest": f"digest-{index}"},
    }


def _run_with_states(monkeypatch, states):
    monkeypatch.setattr(liveness.circuit_meta_lineage, "run_lineage", lambda *args, **kwargs: states)
    family = list(tasks.LEARN)[0]
    learn_task = engine.Task("learn", family, 2, 0b0110)
    result = liveness.run(budgets=((16, 1096),), seeds=(0,), generations=len(states) - 1, tasks=[learn_task])
    (entry,) = result["runs"]
    return result, entry


def test_synthetic_states_give_the_expected_aggregates(monkeypatch):
    """États synthétiques construits à la main : aucun résultat réel n'est utilisé."""
    states = [
        _state(0, (9, 9), None, 99, True, 9),
        _state(1, (4, 9), (7, 9), 2, True, 1),
        _state(2, None, (3, 9), 5, False, 1),
        _state(3, None, None, 0, True, 2),
    ]
    result, entry = _run_with_states(monkeypatch, states)
    records = entry["generations"]
    assert [r["index"] for r in records] == [1, 2, 3]
    assert [r["solved"] for r in records] == [4, 3, None]
    assert [r["solved_source"] for r in records] == ["own", "parent", None]
    assert [r["spend_total"] for r in records] == [3, 6, 1]
    assert entry["adoptions_total"] == 2
    assert entry["synthesis_total"] == 7
    assert entry["synthesis_total"] != 0
    assert entry["library_sizes"] == [1, 1, 2]
    assert entry["grows_after_generation_1"] is True
    assert result["held_out_families_in_input"] == 0


@pytest.mark.parametrize(
    "sizes, grows",
    [([2, 2, 2], False), ([3, 2, 1], False), ([1, 1, 2], True), ([1, 3, 2], True)],
)
def test_synthetic_library_growth_flag(monkeypatch, sizes, grows):
    """États synthétiques construits à la main : aucun résultat réel n'est utilisé."""
    states = [_state(0, (0, 1), None, 0, False, 0)]
    states += [_state(i, (1, 1), None, 1, False, size) for i, size in enumerate(sizes, start=1)]
    _, entry = _run_with_states(monkeypatch, states)
    assert entry["library_sizes"] == sizes
    assert entry["grows_after_generation_1"] is grows


def _record_lineage(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(liveness.circuit_meta_lineage, "run_lineage", fake)
    return calls


def test_main_refuses_zero_generations_before_any_lineage_call(tmp_path, monkeypatch):
    monkeypatch.setattr(liveness, "RESULTS_DIR", tmp_path / "results")
    calls = _record_lineage(monkeypatch)
    assert liveness.main(["--generations", "0"]) == 1
    assert calls == []
    assert not (tmp_path / "results").exists()


def test_main_refuses_an_existing_output_before_any_lineage_call(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(liveness, "RESULTS_DIR", results)
    calls = _record_lineage(monkeypatch)
    existing = results / "already.json"
    existing.write_text("{}\n", encoding="utf-8")
    assert liveness.main(["--out", str(existing)]) == 1
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "{}\n"
