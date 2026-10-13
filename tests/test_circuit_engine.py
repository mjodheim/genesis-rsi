import random

from genesis import circuit_engine as engine
from genesis import circuit_tasks as tasks
from genesis.circuit_engine import Component, Engine, Task


def _value(tree, inputs, library, mask):
    if tree[0] == "in":
        return inputs[tree[1]]
    return library[tree[0]].apply([_value(child, inputs, library, mask) for child in tree[1]], mask)


def test_a_found_circuit_computes_its_target_and_the_search_is_reproducible():
    xor = Task("xor", "parity", 2, 0b0110)
    found = engine.solve(Engine(), xor, 5000)
    assert found.solved and found.cost == 5      # counted as a tree: a shared signal counts each time
    assert _value(found.tree, engine.variables(2), {"nand": engine.NAND}, 0b1111) == 0b0110
    assert engine.solve(Engine(), xor, 5000).evaluations == found.evaluations
    assert not engine.solve(Engine(), xor, 10).solved and engine.solve(Engine(), xor, 10).evaluations == 10


def test_components_are_recognised_whatever_the_order_of_their_inputs():
    implies = Component("a", 2, ((1, 1), (0, 2)))
    reversed_implies = Component("b", 2, ((0, 0), (1, 2)))
    assert implies.table != reversed_implies.table and implies.key == reversed_implies.key
    assert engine.NAND.symmetric and not implies.symmetric


def test_a_step_proposes_what_solutions_share_and_keeps_only_what_helps():
    learn = [task for task in tasks.suite(("and", "or", "parity")) if task.inputs <= 4]
    first = Engine()
    solutions = engine.attempt(first, learn, 2000)
    found = engine.proposals(first, solutions)
    assert found and all(component.key != engine.NAND.key and support >= 1 for component, support in found)
    assert [support for _, support in found] == sorted((support for _, support in found), reverse=True)
    successor, after, step = engine.improved(first, learn, 2000, solutions, generation=1)
    if successor is not first:
        assert engine.measure(after)[0] >= engine.measure(solutions)[0] and step["added"]
        library = {item.name: item for item in successor.components}
        for task, solution in zip(learn, after):
            if solution.solved:
                assert _value(solution.tree, engine.variables(task.inputs), library, (1 << (1 << task.inputs)) - 1) == task.target
    else:
        assert step["added"] is None


def test_a_step_that_cannot_help_hands_back_the_same_engine():
    task = [Task("x", "and", 2, 0b1010)]
    first = Engine()
    solutions = engine.attempt(first, task, 100)
    assert engine.improved(first, task, 100, solutions, generation=1)[0] is first


def test_families_do_not_overlap_and_tables_are_right():
    names = [task.name for family in (*tasks.LEARN, *tasks.HELD_OUT) for task in tasks.tasks(family)]
    assert len(names) == len(set(names)) and not set(tasks.LEARN) & set(tasks.HELD_OUT)
    by_name = {task.name: task for task in tasks.suite((*tasks.LEARN, *tasks.HELD_OUT))}
    assert by_name["and2"].target == 0b1000 and by_name["parity2"].target == 0b0110
    assert by_name["add1bit1"].target == 0b1000 and by_name["less1"].target == 0b0100
    assert tasks.tasks("random", 1) == tasks.tasks("random", 1) != tasks.tasks("random", 2)


def test_random_ranking_is_reproducible():
    learn = [task for task in tasks.suite(("and", "or")) if task.inputs <= 3]
    first = Engine()
    solutions = engine.attempt(first, learn, 1000)
    procedure = {**engine.SEED_PROCEDURE, "ranking": "random"}
    one = engine.improved(first, learn, 1000, solutions, generation=1, procedure=procedure, rng=random.Random(3))[2]
    two = engine.improved(first, learn, 1000, solutions, generation=1, procedure=procedure, rng=random.Random(3))[2]
    assert one == two


def test_deeper_patterns_contain_the_shallow_ones_and_a_ranker_orders_the_trials():
    learn = [task for task in tasks.suite(("and", "or", "parity")) if task.inputs <= 3]
    first = Engine()
    solutions = engine.attempt(first, learn, 3000)
    shallow = {component.key for component, _ in engine.proposals(first, solutions)}
    deep = {component.key for component, _ in engine.proposals(first, solutions, layers=3, arity=4)}
    assert shallow <= deep and len(deep) > len(shallow)
    assert len(engine.features(2, 0b0110, 4, 2, 1, 1)) == 13 and engine.features(2, 0b0110, 4, 2, 1, 1)[8] == 1.0
    procedure = {**engine.SEED_PROCEDURE, "ranking": "learned", "min_support": 1, "tried": 2}
    prefers_small = [0.0] * 5 + [-1.0] + [0.0] * 7
    step = engine.improved(first, learn, 3000, solutions, generation=1, procedure=procedure, ranker=prefers_small)[2]
    assert [trial["nands"] for trial in step["trials"]] == sorted(trial["nands"] for trial in step["trials"])
    assert step["trials"][0]["nands"] == min(len(component.steps) for component, _ in engine.proposals(first, solutions))
