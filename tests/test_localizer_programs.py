import pytest

from genesis import localizer_programs as programs

A = [["a.java", 10], ["a.java", 200], ["b.java", 5], ["b.java", 300]]
B = [["a.java", 15], ["z.java", 50], ["b.java", 5]]
KNOWN = {"a": A, "b": B}


def run(program):
    return programs.run(programs.checked(program, ["a", "b"]), KNOWN.__getitem__)


def test_each_operation_does_what_its_name_says():
    assert run(["head", 2, ["member", "a"]]) == A[:2]
    assert run(["tail", 3, ["member", "a"]]) == A[3:]
    assert run(["shift", -15, ["member", "b"]]) == [["a.java", 1], ["z.java", 35], ["b.java", 1]]
    assert run(["apart", 20, ["join", ["member", "a"], ["member", "b"]]]) == A + [["z.java", 50]]
    assert run(["join", ["member", "b"], ["member", "a"]]) == B + [A[0], A[1], A[3]]
    assert run(["weave", ["member", "a"], ["member", "b"]])[:4] == [A[0], B[0], A[1], B[1]]
    assert run(["agree", ["member", "a"], ["member", "b"]]) == [A[0], A[2]]
    assert run(["files", ["member", "b"], ["head", 2, ["member", "a"]]]) == [B[0]]


def test_a_program_outside_the_language_is_refused():
    for bad in (["member", "c"], ["head", 9, ["member", "a"]], ["exec", ["member", "a"]], "a", [],
                ["join", ["member", "a"]], ["head", 2, ["member", "a"]] + [1]):
        with pytest.raises(ValueError):
            programs.checked(bad, ["a", "b"])
    with pytest.raises(ValueError):
        programs.checked(["tail", 1, ["member", "a"]], ["a"], allowed=("head",))
    deep = ["member", "a"]
    for _ in range(programs.MAX_NODES):
        deep = ["head", 1, deep]
    with pytest.raises(ValueError):
        programs.checked(deep, ["a"])


def test_a_program_is_named_by_its_content():
    one = programs.checked(["join", ["member", "a"], ["member", "b"]], ["a", "b"])
    other = programs.checked(["join", ["member", "b"], ["member", "a"]], ["a", "b"])
    assert programs.named(one) == programs.named(one) != programs.named(other)
    assert programs.size(one) == 3 and programs.leaves(other) == ["b", "a"] and programs.operations(one) == ["join"]


def _world():
    """Member x is right on even cases, member y on odd ones, each ranks its guess first."""
    cases = [f"c{index}" for index in range(60)]
    truth = {case: [{"path": "a.java", "first": 100, "last": 100}] for case in cases}
    right, wrong = [["a.java", 100]], [["w.java", 1], ["w.java", 500], ["v.java", 1], ["v.java", 500],
                                       ["u.java", 1], ["u.java", 500]]
    known = {"x": {case: (right + wrong[:5] if index % 2 == 0 else wrong) for index, case in enumerate(cases)},
             "y": {case: (right + wrong[:5] if index % 2 == 1 else wrong) for index, case in enumerate(cases)}}
    return cases, truth, known


def test_the_diagnosis_separates_what_the_archive_holds_from_what_it_lacks():
    cases, truth, known = _world()
    truth["c1"] = [{"path": "q.java", "first": 1, "last": 1}]
    truth["c3"] = [{"path": "a.java", "first": 100, "last": 100}, {"path": "w.java", "first": 500, "last": 500}]
    known["y"]["c3"] = [["a.java", 100]]
    reach = programs.diagnosis("x", known, truth, cases)
    assert reach == {"cases": 60, "missed": 30, "one_member": 28, "pooled": 1, "out_of_reach": 1}


def test_the_search_finds_a_program_that_uses_both_members_and_the_chain_reuses_it():
    cases, truth, known = _world()
    searching, selection = cases[:30], cases[30:]
    outcome = programs.evolve("x", known, truth, searching, selection, seed=1, generations=3, rounds=6,
                              population=40, kept=10)
    first = outcome["attempts"][0]
    assert first["outcome"] == "promoted" and first["search_localized"] == 30
    assert first["selection"] == {"parent": 15, "child": 30, "gained": 15, "lost": 0,
                                  "one_sided_sign_test": first["selection"]["one_sided_sign_test"]}
    assert set(programs.leaves(outcome["programs"][outcome["chain"][1]])) == {"x", "y"}
    assert outcome["attempts"][1]["outcome"] == "no program better on search cases"
    assert outcome["attempts"][1]["archive_size"] == 3 and outcome["chain"][1] in known
    again = programs.evolve("x", {key: dict(value) for key, value in _world()[2].items()}, truth, searching,
                            selection, seed=1, generations=3, rounds=6, population=40, kept=10)
    assert again["chain"] == outcome["chain"]


def test_a_removed_operation_never_appears_in_what_the_search_returns():
    cases, truth, known = _world()
    scorer = programs.Scorer(known, truth, cases)
    allowed = tuple(name for name in programs.OPERATIONS if name not in ("join", "weave"))
    found = programs.search("x", scorer, seed=3, rounds=4, population=30, kept=8, allowed=allowed)
    assert not {"join", "weave"} & set(programs.operations(found["program"]))
    assert found["localized"] == 30
