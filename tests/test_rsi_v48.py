"""Interpreter fidelity, proposer isolation, paid accounting and donor provenance."""
import copy
import random

import pytest

from experiment.rsi_v48 import bank, engine, proposer


@pytest.mark.parametrize("domain", engine.programs.DOMAINS)
def test_metered_interpreter_matches_real_program(domain):
    rng = random.Random("v48-public-interpreter-" + domain)
    inputs = engine.programs.WITNESSES[domain]
    for length in (0, 1, 2, 5, 12, 32):
        genome = {"domain": domain, "steps": [rng.randrange(4) for _ in range(length)]}
        before = copy.deepcopy(inputs)
        meter = proposer.Meter()
        assert meter.outputs(genome, inputs) == engine.execute(genome, inputs, isolated=False)
        assert inputs == before
        assert meter.output_calls == 1
        assert meter.primitive_visits >= len(inputs) * length


def test_proposal_interface_never_receives_hidden_target():
    task = bank.stream(503, 0)[2]
    host = engine.Host(task, {}, "adaptive", isolated=False)
    expected = host.children(host.root_genome, 0)
    host.task = {"inputs": task["inputs"], "domain": task["domain"]}
    before = len(host.revealed)
    assert host.children(host.root_genome, 0) == expected
    assert len(host.revealed) == before


def test_inference_cap_is_external_and_fails_closed(monkeypatch):
    monkeypatch.setattr(proposer, "MAX_OUTPUT_CALLS", 0)
    with pytest.raises(ValueError, match="output cap"):
        proposer.Meter().outputs(engine.programs.identity("arithmetic"), [1])
    monkeypatch.setattr(proposer, "MAX_OUTPUT_CALLS", 1)
    monkeypatch.setattr(proposer, "MAX_PRIMITIVE_VISITS", 0)
    with pytest.raises(ValueError, match="primitive cap"):
        proposer.Meter().outputs({"domain": "arithmetic", "steps": [0]}, [1])


def test_isolated_g7_and_candidate_evaluation_preserve_paid_outcome():
    task = bank.stream(503, 0)[2]
    development = engine.episode(task, 0, [], "adaptive", isolated=False)
    isolated = engine.episode(task, 0, [], "adaptive", isolated=True)
    for key in ("solved", "charged_evaluations", "new_solving_behaviors", "inference_output_calls", "inference_primitive_visits"):
        assert isolated[key] == development[key]
    assert isolated["search"]["isolated_policy_processes"] is True
    assert isolated["search"]["policy_sha256"] == engine.programs.PARENT_SHA256
    assert isolated["charged_evaluations"] <= 14


def test_donor_ancestry_and_work_are_replayed():
    prefix = []
    for epoch in range(2):
        for position, task in enumerate(bank.stream(503, epoch)):
            row = engine.episode(task, position, prefix, "adaptive", isolated=False)
            history = engine.history_from(prefix)
            for program in row["programs"]:
                donor = program["archive_donor_sha256"]
                if donor:
                    assert donor in history
                    if not program["previously_observed"]:
                        assert program["parent_source_sha256"] == donor
            assert engine.verify_stream([task], "adaptive", prefix, [{**row, "position": 0}], isolated=False)
            prefix.append(row)
    changed = copy.deepcopy(prefix[-1])
    changed["position"] = 0
    changed["inference_primitive_visits"] += 1
    with pytest.raises(ValueError, match="Altered archive"):
        engine.verify_stream([task], "adaptive", prefix[:-1], [changed], isolated=False)
