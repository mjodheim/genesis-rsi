from experiment.rsi_v35 import bank as v35_bank
from experiment.rsi_v42 import bank, engine

def test_same_tasks():
    assert bank.stream(887,3)==v35_bank.stream(887,3)

def test_last_chance_policy_is_bounded():
    prefix=[]
    for position,task in enumerate(bank.stream(503,0)):
        row=engine.episode(task,position,prefix,"adaptive",isolated=False)
        assert row["charged_evaluations"]<=14
        assert row["routing"]["memory_policy"]=="last_chance_stagnation5_frontier_v1"
        prefix.append(row)
