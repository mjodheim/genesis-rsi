import pytest

from genesis import localizer_recombination as recombination

A = [["a.java", 10], ["a.java", 200], ["b.java", 5], ["b.java", 300], ["c.java", 1], ["c.java", 400]]
B = [["a.java", 15], ["z.java", 50], ["y.java", 7]]


def test_a_merge_keeps_the_lead_then_takes_what_adds_a_new_place():
    merged = recombination.merge(A, B, 2)
    assert merged[:2] == A[:2]
    assert merged[2:4] == [["z.java", 50], ["y.java", 7]]      # a.java:15 stands next to a.java:10
    assert merged[4:] == [["b.java", 5], ["b.java", 300]] and len(merged) == 6


def test_a_merge_of_short_answers_falls_back_on_everything_distinct():
    assert recombination.merge([["a.java", 10]], [["a.java", 15]], 1) == [["a.java", 10], ["a.java", 15]]
    assert recombination.merge([], B, 3) == B


def test_composites_are_named_by_content_and_bounded():
    assert recombination.composite("x", "y", 2) == recombination.composite("x", "y", 2)
    assert recombination.composite("x", "y", 2)["name"] != recombination.composite("y", "x", 2)["name"]
    with pytest.raises(ValueError):
        recombination.composite("x", "y", 6)


def _truth(cases, path, line):
    return {case: [{"path": path, "first": line, "last": line}] for case in cases}


def test_recombination_promotes_only_on_unseen_cases_and_can_chain():
    training = [f"t{index}" for index in range(6)]
    selection = [f"s{index}" for index in range(12)]
    truth = {}
    answers = {"champion": {}, "rejected": {}}
    for index, case in enumerate(training + selection):
        if index % 2:
            truth[case] = [{"path": "a.java", "first": 10, "last": 10}]
        else:
            truth[case] = [{"path": "z.java", "first": 50, "last": 50}]
        answers["champion"][case] = [["a.java", 10]]
        answers["rejected"][case] = [["z.java", 50]]
    outcome = recombination.evolve("champion", answers, truth, training, selection)
    assert outcome["attempts"][0]["outcome"] == "promoted"
    assert outcome["attempts"][0]["selection"]["gained"] == 6 and outcome["attempts"][0]["selection"]["lost"] == 0
    assert len(outcome["chain"]) == 2 and outcome["chain"][1] in answers
    assert outcome["attempts"][-1]["outcome"] == "no composite better on training"


def test_a_training_gain_that_does_not_hold_on_selection_is_rejected():
    training, selection = ["t0", "t1"], [f"s{index}" for index in range(8)]
    truth = {case: [{"path": "z.java", "first": 50, "last": 50}] for case in training}
    truth.update({case: [{"path": "a.java", "first": 10, "last": 10}] for case in selection})
    answers = {"champion": {case: [["a.java", 10]] for case in training + selection},
               "rejected": {case: [["z.java", 50]] for case in training + selection}}
    outcome = recombination.evolve("champion", answers, truth, training, selection)
    assert outcome["chain"] == ["champion"]
    assert outcome["attempts"][0]["outcome"] == "rejected on unseen cases"
