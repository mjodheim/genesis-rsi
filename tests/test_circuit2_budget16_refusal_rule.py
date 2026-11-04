import json
from pathlib import Path

from genesis import circuit_procedure as cproc

JSON_PATH = (
    Path(__file__).resolve().parent.parent
    / "results"
    / "circuit2_budget16_traits_s0_g1.json"
)


def _candidates():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        lists = [
            v
            for v in data.values()
            if isinstance(v, list)
            and v
            and all(isinstance(x, dict) and "priorite" in x for x in v)
        ]
        assert len(lists) == 1
        data = lists[0]
    assert isinstance(data, list)
    return data


def _traits(candidate):
    src = candidate["traits"] if isinstance(candidate.get("traits"), dict) else candidate
    return cproc.traits_of(
        src["support"], src["arity"], src["nands"], src["composed"]
    )


def _index(name):
    return cproc.TRAIT_NAMES.index(name)


def test_json_contains_two_candidates():
    assert len(_candidates()) == 2


def test_seed_refuses_both_candidates_like_the_json():
    seed = cproc.seed_procedure()
    for candidate in _candidates():
        priority, admitted, _ = cproc.run(seed, _traits(candidate))
        assert (priority, admitted) == (candidate["priorite"], candidate["admis"])
        assert (priority, admitted) == (0, False)


def test_support_traits_are_all_zero():
    indices = [_index(f"support>={k}") for k in (2, 3, 4)]
    for candidate in _candidates():
        traits = _traits(candidate)
        assert [traits[i] for i in indices] == [0, 0, 0]


def test_support_at_least_2_is_the_cause_of_the_refusal():
    seed = cproc.seed_procedure()
    i_support = _index("support>=2")
    i_arity = _index("arity>=4")
    for candidate in _candidates():
        traits = list(_traits(candidate))
        assert traits[i_support] == 0
        traits[i_support] = 1
        traits[i_arity] = 0
        _, admitted, _ = cproc.run(seed, tuple(traits))
        assert admitted is True
