from __future__ import annotations
import json
from pathlib import Path
import sys

import pytest

from genesis.evolution import recursive_chain

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import g10_evaluator  # noqa: E402
import g10_task_bank  # noqa: E402

G9=json.loads((ROOT/"experiment/g9_qualification/SUCCESSOR.json").read_text())
SPECIALIST=json.loads((ROOT/"experiment/g8_qualification/SPECIALIST.json").read_text())["specialist"]


def _chain():
    g0=recursive_chain.build_seed_profile(G9)
    profiles=[g0]
    comparisons=[]
    for stage,seed in ((1,11001),(2,12001),(3,13001)):
        bank=g10_task_bank.build_bank(SPECIALIST,stage=stage,purpose="discovery",seed=seed)
        parent=profiles[-1]
        pm=g10_evaluator.evaluate_profile(ROOT,parent,bank,max_candidates_per_case=6)
        ancestor=None
        if len(profiles)>=2:
            ancestor=g10_evaluator.evaluate_profile(ROOT,profiles[-2],bank,max_candidates_per_case=6)
        evidence=g10_evaluator.build_discovery_evidence(pm)
        proposal=recursive_chain.induce_successor(parent,evidence)
        profiles.append(proposal["successor_profile"])
        comparisons.append((pm,ancestor,proposal))
    return profiles,comparisons


def test_seed_is_exactly_the_qualified_g9_successor():
    seed=recursive_chain.build_seed_profile(G9)
    assert seed["campaign_generation"]==0
    assert seed["base_system_profile"]["profile_digest"]==G9["successor_profile_digest"]
    assert seed["recursive_capability"]["level"]==0
    assert seed["external_model_calls_for_generation"]==0


def test_development_chain_has_recursive_production_advantage():
    profiles,comparisons=_chain()
    assert [p["campaign_generation"] for p in profiles]==[0,1,2,3]
    assert [p["recursive_capability"]["level"] for p in profiles]==[0,1,2,3]
    assert comparisons[0][0]["solved"]==6
    assert comparisons[1][0]["solved"]==4
    assert comparisons[1][1]["solved"]==0
    assert comparisons[2][0]["solved"]==4
    assert comparisons[2][1]["solved"]==0
    assert comparisons[1][0]["candidate_executions"]<comparisons[1][1]["candidate_executions"]
    assert comparisons[2][0]["candidate_executions"]<comparisons[2][1]["candidate_executions"]


def test_development_holdouts_show_monotonic_capability_extension():
    profiles,_=_chain()
    expected=((1,2,6),(2,4,8),(3,6,10))
    for stage,parent_solved,child_solved in expected:
        bank=g10_task_bank.build_bank(
            SPECIALIST,stage=stage,purpose="holdout",seed=20000+stage*1001
        )
        parent=g10_evaluator.evaluate_profile(ROOT,profiles[stage-1],bank,max_candidates_per_case=6)
        child=g10_evaluator.evaluate_profile(ROOT,profiles[stage],bank,max_candidates_per_case=6)
        assert parent["solved"]==parent_solved
        assert child["solved"]==child_solved
        assert g10_evaluator.pass_ids(parent)<=g10_evaluator.pass_ids(child)
        assert parent["external_model_calls"]==child["external_model_calls"]==0


def test_induction_refuses_insufficient_discovery_evidence():
    seed=recursive_chain.build_seed_profile(G9)
    bank=g10_task_bank.build_bank(SPECIALIST,stage=2,purpose="discovery",seed=991)
    measurement=g10_evaluator.evaluate_profile(ROOT,seed,bank,max_candidates_per_case=6)
    evidence=g10_evaluator.build_discovery_evidence(measurement)
    assert measurement["solved"]==0
    with pytest.raises(recursive_chain.RecursiveChainError):
        recursive_chain.induce_successor(seed,evidence)


def test_profile_and_discovery_tampering_fail_closed():
    seed=recursive_chain.build_seed_profile(G9)
    damaged=json.loads(json.dumps(seed))
    damaged["campaign_generation"]=99
    with pytest.raises(recursive_chain.RecursiveChainError):
        recursive_chain.validate_profile(damaged)

    bank=g10_task_bank.build_bank(SPECIALIST,stage=1,purpose="discovery",seed=100)
    measurement=g10_evaluator.evaluate_profile(ROOT,seed,bank,max_candidates_per_case=6)
    evidence=g10_evaluator.build_discovery_evidence(measurement)
    evidence["solved"]+=1
    with pytest.raises(recursive_chain.RecursiveChainError):
        recursive_chain.validate_discovery(evidence,parent_profile_digest=seed["profile_digest"])
