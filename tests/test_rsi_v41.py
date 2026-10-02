from experiment.rsi_v35 import bank as v35_bank
from experiment.rsi_v41 import bank, engine

def test_same_consumed_tasks():
    assert bank.stream(503,3)==v35_bank.stream(503,3)

def test_policy_and_budget():
    prefix=[]
    for position,task in enumerate(bank.stream(503,0)[:5]):
        row=engine.episode(task,position,prefix,"adaptive",isolated=False)
        assert row["charged_evaluations"]<=14
        assert row["routing"]["memory_policy"]=="conditional_stagnation4_frontier_v1"
        prefix.append(row)
