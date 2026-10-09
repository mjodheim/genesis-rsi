import pytest

from genesis.repair_lineage import Envelope, Ledger, descendant_report, lineage_proposer, training_report
from test_repair_lineage import answer, evaluation, genome, repair, scripted, setup


def test_rejected_edit_is_corrected_with_feedback_and_no_checkout_mutation(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(answer("submit_repairs", repair("return 7;")),
                          answer("read_file", {"path": "src/A.java"}),
                          answer("submit_repairs", repair()))
    calls, ledger = [], Ledger(1)
    proposer = lineage_proposer(genome(inspection_requests=2, rounds=1), Envelope(model="test/model"),
                               ledger, calls, transport=send, application_feedback=True)
    candidates = proposer(tmp_path, evidence, (), 6)
    assert len(candidates) == 1 and "return 0;" in candidates[0].content
    assert "return 1;" in (tmp_path / "src/A.java").read_text()
    assert len(seen) == 3 and ledger.spent == pytest.approx(.003)
    feedback = [m["content"] for m in seen[1]["messages"] if m["role"] == "tool"]
    assert '"inapplicable": 1' in feedback[0]
    assert "search matches=0" in feedback[0]
    assert calls[0]["submission_results"][0]["applicable"] is False
    assert calls[2]["submission_results"][0]["applicable"] is True


def test_recovery_never_adds_requests_after_final_step(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(*[answer("submit_repairs", repair("absent")) for _ in range(2)])
    calls = []
    proposer = lineage_proposer(genome(inspection_requests=1, rounds=1),
                               Envelope(model="test/model", requests=2), Ledger(1), calls,
                               transport=send, application_feedback=True)
    assert proposer(tmp_path, evidence, (), 6) == []
    assert len(seen) == 2
    assert proposer(tmp_path, evidence, (), 6) == []
    assert len(seen) == 2


def test_explicit_empty_submission_does_not_force_more_spending(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(answer("submit_repairs", {"candidates": []}))
    proposer = lineage_proposer(genome(), Envelope(model="test/model"), Ledger(1), [],
                               transport=send, application_feedback=True)
    assert proposer(tmp_path, evidence, (), 6) == [] and len(seen) == 1


def test_history_includes_rejected_training_attempts_but_not_selection():
    measured = evaluation({"training": False, "selection": True})
    measured["cases"]["selection"]["verdicts"][0]["feedback"] = "RESERVED_SELECTION_DETAIL"
    measured["cases"]["training"]["calls"][0]["submission_results"] = [
        {"path": "src/A.java", "edits": [{"search": "old", "replace": "new"}], "applicable": False}]
    report = training_report(measured, ["training"], detailed=True)
    history = descendant_report("parent", [{"generation": 1, "status": "evaluated",
                                            "training_report": report, "rationale": "try another edit"}])
    assert "RESERVED_SELECTION_DETAIL" not in history
    assert '"search": "old"' in history and "try another edit" in history
    long = descendant_report("P" * 50_000, [
        {"generation": i, "status": "evaluated", "training_report": str(i) * 50_000}
        for i in range(20)], limit=2400)
    assert len(long) <= 2400 and '"generation": 19' in long and '"generation": 0,' not in long


def test_evolution_reuses_rejected_training_evidence_without_selection_feedback(tmp_path, monkeypatch):
    from argparse import Namespace
    import scripts.run_repair_lineage as runner
    from genesis.repair_lineage import SEED_GENOME, checked_genome

    seed = checked_genome(SEED_GENOME)
    recorded = {"training_cases": ["train"], "selection_cases": ["select"],
                "seed_genome": seed, "generations": 2, "name": "offline",
                "plan_digest": "plan", "seed_genome_digest": "seed", "cumulative_feedback": True}
    monkeypatch.setattr(runner, "_context", lambda _: (
        tmp_path, recorded, Envelope(model="test/model"), Ledger(1), ["train", "select"]))
    outcomes = []
    for marker in ("SEED_FAILURE", "REJECTED_CHILD_FAILURE", "NEXT_FAILURE"):
        outcome = evaluation({"train": False, "select": False})
        outcome.update(solved=0, evaluation_digest=marker)
        outcome["cases"]["train"]["verdicts"][0]["feedback"] = marker
        outcome["cases"]["select"]["verdicts"][0]["feedback"] = "SELECTION_SECRET"
        outcomes.append(outcome)
    def measured(*args, **kwargs):
        assert kwargs["application_feedback"] is True
        return outcomes.pop(0)
    monkeypatch.setattr(runner, "evaluate_runs", measured)
    reports = []
    def written(workspace, tag, parent, report, envelope, ledger):
        reports.append(report)
        return {"genome": {**seed, "playbook": tag}, "rationale": tag, "calls": []}
    monkeypatch.setattr(runner, "successor", written)
    assert runner.evolve(Namespace(workspace=tmp_path, parallel=1)) == 0
    assert "REJECTED_CHILD_FAILURE" in reports[1] and "gen1" in reports[1]
    assert all("SELECTION_SECRET" not in report for report in reports)
    import json
    lineage = json.loads((tmp_path / "LINEAGE.json").read_text())
    assert lineage["final_generation"] == 0
    assert len(lineage["training_attempts"]) == 2
