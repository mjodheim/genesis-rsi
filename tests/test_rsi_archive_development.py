"""Reject fabricated discovery and verify that inverse proposals stay target-blind."""
import copy
import importlib

import pytest

from experiment.rsi_v47 import bank, engine


@pytest.mark.parametrize("version", range(43, 48))
def test_receipt_replay_rejects_fabricated_novelty(version):
    module = importlib.import_module(f"experiment.rsi_v{version}.engine")
    task = bank.stream(503, 0)[0]
    row = module.episode(task, 0, [], "adaptive", isolated=False, variant=module.VARIANTS[0])
    assert module.verify_stream([task], "adaptive", [], [row], isolated=False)
    changed = copy.deepcopy(row)
    changed["new_solving_behaviors"].append("f" * 64)
    with pytest.raises(ValueError, match="Altered archive"):
        module.verify_stream([task], "adaptive", [], [changed], isolated=False)


@pytest.mark.parametrize("variant", engine.VARIANTS)
def test_inverse_proposals_work_without_hidden_target(variant):
    task = bank.stream(503, 0)[0]
    host = engine.Host(task, {}, "adaptive", isolated=False, variant=variant)
    candidates = host.children(host.root_genome, 0)
    charges = len(host.revealed)
    host.task = {"domain": task["domain"], "inputs": task["inputs"]}
    assert host.children(host.root_genome, 0) == candidates
    assert len(host.revealed) == charges
    assert host.inference_output_calls > 0


def test_inverse_replay_checks_inference_work_and_g7_identity():
    task = bank.stream(503, 0)[0]
    row = engine.episode(task, 0, [], "adaptive", isolated=False, variant="inverse4_successors")
    assert row["search"]["policy_sha256"] == engine.programs.PARENT_SHA256
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert engine.verify_stream([task], "adaptive", [], [row], isolated=False)
    changed = copy.deepcopy(row)
    changed["inference_output_calls"] += 1
    with pytest.raises(ValueError, match="Altered archive"):
        engine.verify_stream([task], "adaptive", [], [changed], isolated=False)
