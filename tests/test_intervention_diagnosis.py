import pytest

from genesis import intervention_diagnosis as interventions
from genesis import repair_interventions as repair
from genesis.repair_bench import Candidate, run_arm


def test_a_variant_is_named_only_when_it_recovers_cases_the_control_does_not():
    outcomes = {f"c{index}": {"control": index >= 8, "wide": True, "same": index >= 8, "worse": False}
                for index in range(10)}
    result = interventions.diagnosis(outcomes, "control", {"wide": "envelope", "same": "tools", "worse": "model"})
    assert result["variants"]["wide"]["net"] == 8 and result["variants"]["wide"]["established"]
    assert result["variants"]["same"]["net"] == 0 and not result["variants"]["same"]["established"]
    assert result["variants"]["worse"]["lost"] == ["c8", "c9"]
    assert result["named"] == "envelope" and result["limiting_components"] == ["envelope"]
    assert result["ranking"][0] == "wide" and result["succeed_under_no_arm"] == []


def test_a_gain_the_control_matches_by_chance_is_not_credited():
    outcomes = {f"c{index}": {"control": index % 2 == 0, "variant": index % 2 == 1} for index in range(12)}
    row = interventions.diagnosis(outcomes, "control", {"variant": "x"})["variants"]["variant"]
    assert len(row["gained"]) == 6 and len(row["lost"]) == 6 and not row["established"]


def test_cases_no_arm_recovers_are_reported_and_partial_arms_compare_on_shared_cases():
    outcomes = {"a": {"control": False, "v": False, "w": True}, "b": {"control": False, "v": True},
                "c": {"control": False, "v": False, "w": False}}
    result = interventions.diagnosis(outcomes, "control", {"v": "one", "w": "two"}, margin=1, level=0.6)
    assert result["variants"]["w"]["cases"] == 2 and result["variants"]["v"]["cases"] == 3
    assert result["cases_run_under_every_arm"] == 2 and result["succeed_under_no_arm"] == ["c"]
    with pytest.raises(ValueError):
        interventions.diagnosis(outcomes, "control", {"control": "x"})


def test_the_order_of_arms_is_a_rotation_fixed_by_the_case():
    arms = ["control", "a", "b", "c"]
    first = interventions.order("Lang-1", arms)
    assert sorted(first) == sorted(arms) and first == interventions.order("Lang-1", arms)
    assert len({tuple(interventions.order(f"case-{index}", arms)) for index in range(40)}) == 4
    assert interventions.sign_test(0, 5) == 1 / 32 and interventions.sign_test(0, 0) == 1.0


def test_a_malformed_start_line_is_read_and_a_refusal_is_explained(tmp_path):
    source = tmp_path / "src" / "A.java"
    source.parent.mkdir()
    (tmp_path / "test").mkdir()
    source.write_text("\n".join(f"line {index}" for index in range(1, 301)), encoding="utf-8")
    evidence = {"source_directory": "src", "test_directory": "test"}
    text = repair.tolerant_inspect(tmp_path, evidence, "read_file", {"path": "src/A.java", "start": "[120, 180]"})
    assert text.startswith("120| line 120")
    assert repair.tolerant_inspect(tmp_path, evidence, "read_file", {"path": "src/A.java", "search_start": "50"}).startswith("50| ")
    refused = repair.tolerant_inspect(tmp_path, evidence, "read_file", {"path": "../etc/passwd"})
    assert refused.startswith(repair.REFUSAL) and "read_file takes" in refused
    assert len(refused) not in repair.REFUSED_LENGTHS


def test_recorded_attempts_are_sorted_by_how_they_ended():
    read = {"tool": "read_file", "characters": 30, "arguments": {}}
    attempts = [
        {"solved": True, "calls": [{"submitted": 1}], "verdicts": [{"stopped_at": "passed"}]},
        {"solved": False, "calls": [{"inspections": [read]}, {"submitted": 0}], "verdicts": []},
        {"solved": False, "calls": [{"submitted": 2, "inapplicable": 2}], "verdicts": []},
        {"solved": False, "calls": [{"submitted": None}], "verdicts": []},
        {"solved": False, "calls": [{"submitted": 1}] * 8, "verdicts": [{"stopped_at": "failing_tests"}, {"stopped_at": "full_suite"}]},
    ]
    summary = repair.stops(attempts, requests=8, validations=6)
    assert summary["repaired"] == 1 and summary["failed_with_nothing_tested"] == 3
    assert summary["how_failed_attempts_ended"] == {
        "nothing tested: edits could not be applied": 1, "nothing tested: empty submission": 1,
        "nothing tested: never submitted": 1, "tested: other tests break": 1}
    assert summary["of_which_with_a_refused_read"] == 1 and summary["failed_with_requests_left"] == 3
    assert summary["failed_with_validations_left"] == 4


def test_each_variant_changes_one_thing_and_stays_inside_its_envelope():
    control = repair.configuration(repair.CONTROL, "m")
    for name in repair.VARIANTS:
        given = repair.configuration(name, "m")
        changed = [key for key in control if key != "component" and given[key] != control[key]]
        assert len(changed) == (2 if name == "budget" else 1), name
        search, envelope = given["search"], given["envelope"]
        assert search["rounds"] * (search["inspection_requests"] + 1) <= envelope["model_requests_per_case"]
    assert repair.oracle_locations([{"path": "src/A.java", "first": 7, "last": 9}] * 9) == [["src/A.java", 7]] * 6
    with pytest.raises(ValueError):
        repair.configuration("unknown", "m")


def test_with_persistence_an_empty_round_does_not_end_the_case(tmp_path, monkeypatch):
    import genesis.repair_bench as bench
    asked = []

    def proposer(root, evidence, history, remaining):
        asked.append(len(history))
        return [] if len(asked) == 1 else [Candidate("src/A.java", "x", "test", "h")]

    monkeypatch.setattr(bench, "validate", lambda *a, **k: {"plausible": True})
    monkeypatch.setattr(bench, "squashed_sha256", lambda text: "0")
    (tmp_path / "case" / "src").mkdir(parents=True)
    (tmp_path / "case" / "src" / "A.java").write_text("y", encoding="utf-8")
    sandbox = type("S", (), {"workspace": tmp_path})()
    evidence = {"failing_tests": ["T::t"]}
    assert not run_arm(sandbox, "case", evidence, proposer, 6, max_rounds=2)["solved"] and asked == [0]
    asked.clear()
    assert run_arm(sandbox, "case", evidence, proposer, 6, max_rounds=2, persist=True)["solved"] and asked == [0, 0]
