import json
from pathlib import Path

from genesis import circuit_procedure as cproc

JSON_PATH = (
    Path(__file__).resolve().parent.parent
    / "results"
    / "circuit2_budget16_traits_s0_g1.json"
)

# Règle de seed_procedure : priorité = (support>=3, low), avec
# low = (support>=2 ET NON support>=3) OU support>=4.
# Quand seul support>=2 vaut 1, les bits sont (0, 1), donc priorité 1,
# et l'admission vaut support>=2 ET NON arity>=4.
PRIORITE_APRES_MUTATION = 1


def _candidates():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))["candidats"]


def _traits(candidate):
    t = candidate["traits"]
    return cproc.traits_of(t["support"], t["arity"], t["nands"], t["composed"])


def _index(name):
    return cproc.TRAIT_NAMES.index(name)


def test_json_contains_two_candidates():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert data["nombre_candidats"] == 2
    assert len(data["candidats"]) == 2


def test_raw_diagnostic_is_frozen():
    candidates = _candidates()
    assert [c["traits"]["support"] for c in candidates] == [1, 1]
    assert [c["traits"]["arity"] for c in candidates] == [1, 2]
    assert [c["traits"]["composed"] for c in candidates] == [False, False]


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
        assert traits[i_arity] == 0
        priority, admitted, _ = cproc.run(seed, tuple(traits))
        assert priority == 0
        assert admitted is False
        traits[i_support] = 1
        priority, admitted, _ = cproc.run(seed, tuple(traits))
        assert admitted is True
        assert priority == PRIORITE_APRES_MUTATION
