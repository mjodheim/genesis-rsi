"""Lanceur de campagne CIRCUIT2 : hors réseau, sans modèle, plan scellé dans tmp_path."""
from __future__ import annotations

import copy
import json

import pytest

import freeze_circuit2_plan as freeze
import run_circuit2_campaign as campaign
import seal_circuit2_launcher as sealing
from genesis import circuit_tasks as tasks

COMMIT = "a" * 40
ARMS = ("inherited_lineage", "frozen_engine", "fixed_procedure", "random_procedure")
FORBIDDEN = ("gain", "yield", "rendement", "succ")


@pytest.fixture(scope="module")
def sealed():
    return freeze.build_plan(measure=lambda: {str(s): 100 for s in freeze.SEEDS}, machinery_commit=COMMIT)


@pytest.fixture
def plan_path(tmp_path, sealed):
    path = tmp_path / "PLAN.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def canonical(tmp_path, sealed, monkeypatch):
    path = tmp_path / "CANONICAL.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    monkeypatch.setattr(campaign, "CANONICAL_PLAN_PATH", path)
    return path


@pytest.fixture(autouse=True)
def launcher_seal(tmp_path, sealed, monkeypatch):
    """Fixture synthétique : sceau écrit dans tmp_path pour le vrai lanceur et le plan factice (coûts 100)."""
    path = tmp_path / "LAUNCHER_SEAL.json"
    path.write_text(json.dumps(sealing.build_seal(sealed["digest"])), encoding="utf-8")
    monkeypatch.setattr(campaign, "SEAL_PATH", path)
    return path


def _record(exhausted=False, adopted=False, label="d", spent=10):
    return {"exhausted": exhausted, "digest": label, "spent": spent, "transmission": {"digest": (label + "+") if adopted else label}}


class _FakeRun:
    """Fixture unitaire : faux ArmRun ; step() enregistre (arm, seed, index) et rend les enregistrements scriptés."""

    def __init__(self, calls, script, arm, seed, learn, limit, budget):
        self.calls, self.make = calls, script or (lambda a, s, g: _record())
        self.arm, self.seed, self.learn, self.limit, self.budget = arm, seed, learn, limit, budget
        self.index = 0

    def step(self):
        index, self.index = self.index, self.index + 1
        record = self.make(self.arm, self.seed, index + 1)
        self.calls.append({"arm": self.arm, "seed": self.seed, "index": index, "generations": index + 1, "learn": self.learn, "limit": self.limit, "budget": self.budget, "spent": record.get("spent", 0)})
        return record


def _fake_new_run(calls, script=None):
    """Faux new_run instrumenté (fixtures unitaires, aucune mesure)."""

    def new_run(arm, seed, learn, limit, budget):
        return _FakeRun(calls, script, arm, seed, learn, limit, budget)

    return new_run


def _no_run_all(*args, **kwargs):
    raise AssertionError("run_all ne doit plus être appelé par le lanceur")


def _no_run_arm(*args, **kwargs):
    raise AssertionError("run_arm ne doit plus être appelé par le lanceur")


def _patch(monkeypatch, calls, script=None):
    monkeypatch.setattr(campaign.arms, "run_all", _no_run_all)
    monkeypatch.setattr(campaign.arms, "run_arm", _no_run_arm)
    monkeypatch.setattr(campaign, "new_run", _fake_new_run(calls, script))


def _seal_body(sealed):
    """Fixture synthétique : corps de sceau valide (sans digest) pour le vrai lanceur et le plan factice."""
    return {k: v for k, v in sealing.build_seal(sealed["digest"]).items() if k != "digest"}


def _write_seal(path, body, digest=None):
    """Fixture synthétique : écrit un sceau ; le digest est recalculé sauf s'il est imposé."""
    seal = dict(body)
    seal["digest"] = sealing.digest_of(body) if digest is None else digest
    path.write_text(json.dumps(seal), encoding="utf-8")


def _alter_launcher(tmp_path, monkeypatch):
    """Fixture synthétique : copie du lanceur avec un octet de plus, substituée à campaign.LAUNCHER_FILE."""
    altered = tmp_path / "run_circuit2_campaign_altered.py"
    altered.write_bytes(campaign.LAUNCHER_FILE.read_bytes() + b"\n")
    monkeypatch.setattr(campaign, "LAUNCHER_FILE", altered)
    return altered


def test_a_valid_launcher_seal_lets_the_campaign_run(sealed, launcher_seal, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    sealing.verify_launcher(sealed["digest"], launcher_seal, campaign.LAUNCHER_FILE)
    result = campaign.run_campaign(sealed, seeds=[0], generations=1)
    assert result["plan_digest"] == sealed["digest"]
    assert calls


def test_a_missing_launcher_seal_is_refused_before_any_generation(sealed, launcher_seal, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    launcher_seal.unlink()
    with pytest.raises(campaign.PlanError):
        campaign.run_campaign(sealed, seeds=[0], generations=1)
    with pytest.raises(campaign.PlanError):
        campaign.run_campaign(sealed, seeds=[999])
    assert calls == []


def test_an_altered_launcher_is_refused_before_any_generation(sealed, tmp_path, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    _alter_launcher(tmp_path, monkeypatch)
    with pytest.raises(campaign.PlanError):
        campaign.run_campaign(sealed, seeds=[0], generations=1)
    assert calls == []


@pytest.mark.parametrize(
    "variant",
    ["other_plan_digest", "tampered_content", "other_launcher_sha", "other_verifier_sha", "wrong_schema", "unreadable"],
)
def test_invalid_launcher_seals_are_refused_before_any_generation(sealed, launcher_seal, monkeypatch, variant):
    calls = []
    _patch(monkeypatch, calls)
    body = _seal_body(sealed)
    if variant == "other_plan_digest":
        _write_seal(launcher_seal, {**body, "plan_digest": "f" * 64})
    elif variant == "tampered_content":
        _write_seal(launcher_seal, {**body, "launcher_sha256": "0" * 64}, digest=sealing.digest_of(body))
    elif variant == "other_launcher_sha":
        _write_seal(launcher_seal, {**body, "launcher_sha256": "0" * 64})
    elif variant == "other_verifier_sha":
        _write_seal(launcher_seal, {**body, "verifier_sha256": "0" * 64})
    elif variant == "wrong_schema":
        _write_seal(launcher_seal, {**body, "schema": "circuit2-launcher-seal-v0"})
    else:
        launcher_seal.write_text("{", encoding="utf-8")
    with pytest.raises(sealing.SealError):
        sealing.verify_launcher(sealed["digest"], launcher_seal, campaign.LAUNCHER_FILE)
    with pytest.raises(campaign.PlanError):
        campaign.run_campaign(sealed, seeds=[0], generations=1)
    assert calls == []


def test_main_returns_2_with_an_altered_launcher_and_writes_no_output(plan_path, tmp_path, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    _alter_launcher(tmp_path, monkeypatch)
    out = tmp_path / "OUT.json"
    assert campaign.main(["--plan", str(plan_path), "--seeds", "0", "--generations", "1", "--out", str(out)]) == 2
    assert not out.exists()
    assert calls == []


def test_the_seal_script_refuses_to_overwrite_an_existing_seal(tmp_path):
    out = tmp_path / "EXISTING_SEAL.json"
    out.write_text("{}", encoding="utf-8")
    assert sealing.main(["--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "{}"


def _check_executed(calls, result, count, plan):
    """Chaque (arm, seed, index) une fois, index consécutifs, arrêt immédiat, dépense exécutée == publiée, plafond du plan."""
    keys = [(c["arm"], c["seed"], c["index"]) for c in calls]
    assert len(keys) == len(set(keys))
    total_runs = 0
    for arm in ARMS:
        for run in result["arms"][arm]:
            total_runs += 1
            mine = [c for c in calls if c["arm"] == arm and c["seed"] == run["seed"]]
            assert [c["index"] for c in mine] == list(range(len(mine)))
            assert len(mine) == run["generations_run"] == len(run["generations"])
            assert sum(c.get("spent", 0) for c in mine) == sum(r.get("spent", 0) for r in run["generations"])
            assert not any(campaign._stops(r) for r in run["generations"][:-1])
            if run["stopped_early"]:
                assert campaign._stops(run["generations"][-1])
    assert len(calls) == sum(len(r["generations"]) for rs in result["arms"].values() for r in rs)
    assert sum(c["spent"] for c in calls) <= total_runs * count * plan["budgets"]["per_generation_limit"]


def _gens_for(calls, arm, seed):
    return [c["generations"] for c in calls if c["arm"] == arm and c["seed"] == seed]


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_a_valid_plan_loads(plan_path, sealed):
    assert campaign.load_plan(plan_path)["digest"] == sealed["digest"]


def test_a_missing_plan_is_refused(tmp_path):
    with pytest.raises(freeze.PlanError):
        campaign.load_plan(tmp_path / "absent.json")


def test_an_altered_plan_is_refused(tmp_path, sealed):
    altered = copy.deepcopy(sealed)
    altered["criterion"]["text"] = altered["criterion"]["text"].replace("10 points", "5 points")
    path = tmp_path / "ALTERED.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(freeze.PlanError):
        campaign.load_plan(path)


def test_a_plan_with_other_machinery_fingerprints_is_refused(tmp_path, sealed):
    other = copy.deepcopy(sealed)
    other["machinery_digests"]["genesis/circuit_engine.py"] = "0" * 64
    resealed = freeze.seal({k: v for k, v in other.items() if k != "digest"})
    path = tmp_path / "OTHER.json"
    path.write_text(json.dumps(resealed), encoding="utf-8")
    with pytest.raises(freeze.PlanError):
        campaign.load_plan(path)


def test_run_arm_receives_exactly_the_plan_budgets_learn_tasks_and_seeds(sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    campaign.run_campaign(sealed)
    count = sealed["budgets"]["generations"]
    assert list(dict.fromkeys(c["arm"] for c in calls)) == list(campaign.arms.ARMS)
    assert {c["seed"] for c in calls} == set(sealed["seeds"])
    for call in calls:
        assert call["limit"] == sealed["budgets"]["per_generation_limit"]
        assert call["budget"] == sealed["budgets"]["task_budget"]
        assert list(call["learn"]) == freeze.learn_tasks()
    for arm in campaign.arms.ARMS:
        for seed in sealed["seeds"]:
            assert _gens_for(calls, arm, seed) == list(range(1, count + 1))
    given = calls[0]["learn"]
    assert given and {t.family for t in given} <= set(tasks.LEARN)


def test_seeds_outside_the_plan_or_too_many_generations_are_refused(sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    too_many = sealed["budgets"]["generations"] + 1
    for kwargs in ({"seeds": [999]}, {"seeds": [0, 999]}, {"seeds": []}, {"generations": too_many}, {"generations": 0}):
        with pytest.raises(ValueError):
            campaign.run_campaign(sealed, **kwargs)
    assert calls == []


def test_scale_is_reduced_for_a_sub_campaign_and_full_otherwise(sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    small = campaign.run_campaign(sealed, seeds=[1, 0], generations=1)
    assert small["scale"] == "reduced" and small["seeds"] == [1, 0] and small["generations"] == 1
    fewer = campaign.run_campaign(sealed, generations=1)
    assert fewer["scale"] == "reduced"
    full = campaign.run_campaign(sealed, seeds=list(sealed["seeds"]), generations=sealed["budgets"]["generations"])
    assert full["scale"] == "full" and full["seeds"] == sealed["seeds"]
    assert full["plan_digest"] == sealed["digest"] and full["machinery_commit"] == COMMIT
    assert set(full["arms"]) == set(ARMS)


def test_a_second_write_to_the_same_output_is_refused(plan_path, tmp_path, monkeypatch):
    _patch(monkeypatch, [])
    out = tmp_path / "OUT.json"
    argv = ["--plan", str(plan_path), "--seeds", "0", "--generations", "1", "--out", str(out)]
    assert campaign.main(argv) == 0
    written = out.read_text(encoding="utf-8")
    assert campaign.main(argv) != 0
    assert out.read_text(encoding="utf-8") == written
    assert json.loads(written)["scale"] == "reduced"


def test_the_output_has_no_gain_or_success_key(sealed, monkeypatch):
    _patch(monkeypatch, [])
    result = campaign.run_campaign(sealed, seeds=[0], generations=1)
    keys = [k.lower() for k in _keys(result)]
    assert keys and not [k for k in keys if any(word in k for word in FORBIDDEN)]


def _bump_costs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if "cost" in str(key) and isinstance(value, dict) and value and all(
                isinstance(v, int) and not isinstance(v, bool) for v in value.values()
            ):
                for name in value:
                    value[name] += 1
                return True
            if _bump_costs(value):
                return True
    elif isinstance(node, list):
        return any(_bump_costs(item) for item in node)
    return False


def _resealed_other_costs(sealed):
    other = copy.deepcopy(sealed)
    assert _bump_costs(other), "coûts de référence introuvables dans le plan"
    return freeze.seal({k: v for k, v in other.items() if k != "digest"})


def _total(value):
    if isinstance(value, dict):
        return sum(_total(v) for v in value.values())
    if isinstance(value, list):
        return sum(_total(v) for v in value)
    return value


def test_a_plan_with_modified_reference_costs_resealed_is_refused(tmp_path, sealed):
    path = tmp_path / "COSTS.json"
    path.write_text(json.dumps(_resealed_other_costs(sealed)), encoding="utf-8")
    with pytest.raises(freeze.PlanError):
        campaign.load_plan(path)


def test_an_altered_dict_passed_to_run_campaign_is_refused_without_running(sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    altered = copy.deepcopy(sealed)
    altered["criterion"]["text"] = altered["criterion"]["text"].replace("10 points", "5 points")
    assert altered["criterion"]["text"] != sealed["criterion"]["text"]
    for candidate in (altered, _resealed_other_costs(sealed)):
        with pytest.raises(freeze.PlanError):
            campaign.run_campaign(candidate, seeds=[0], generations=1)
    assert calls == []


def test_a_valid_plan_with_another_digest_is_refused(tmp_path, sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    other = freeze.build_plan(measure=lambda: {str(s): 101 for s in freeze.SEEDS}, machinery_commit=COMMIT)
    freeze.verify_plan(other)
    assert other["digest"] != sealed["digest"]
    with pytest.raises(freeze.PlanError):
        campaign.check_plan(other)
    with pytest.raises(freeze.PlanError):
        campaign.run_campaign(other)
    path = tmp_path / "OTHER_VALID.json"
    path.write_text(json.dumps(other), encoding="utf-8")
    assert campaign.main(["--plan", str(path), "--seeds", "0", "--generations", "1"]) == 2
    assert calls == []


def test_a_missing_or_invalid_canonical_plan_is_refused_without_fallback(tmp_path, sealed, monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    monkeypatch.setattr(campaign, "CANONICAL_PLAN_PATH", tmp_path / "absent.json")
    with pytest.raises(freeze.PlanError):
        campaign.canonical_digest()
    with pytest.raises(freeze.PlanError):
        campaign.run_campaign(sealed)
    broken = tmp_path / "BROKEN.json"
    broken.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(campaign, "CANONICAL_PLAN_PATH", broken)
    with pytest.raises(freeze.PlanError):
        campaign.canonical_digest()
    assert calls == []


def test_canonical_digest_is_read_from_the_published_file(canonical, sealed):
    assert campaign.canonical_digest() == sealed["digest"]
    assert campaign.canonical_digest(canonical) == sealed["digest"]


def _script(stops=None, adopted=(), bare=False):
    """Fixture unitaire : épuisement à la génération stops[(bras, graine)], avec adoption si la clé est dans adopted."""
    stops = stops or {}

    def make(arm, seed, g):
        if bare:
            return {"exhausted": True}
        key = (arm, seed)
        hit = stops.get(key) == g
        return _record(exhausted=hit, adopted=hit and key in adopted, label=f"{arm}-{seed}-{g}")

    return make


def test_stop_at_the_second_generation_is_effective_and_the_third_is_never_called(sealed, monkeypatch):
    """Fixture unitaire : enregistrements contrôlés par le faux run_arm, aucune mesure."""
    calls, arm, seed = [], ARMS[0], sealed["seeds"][0]
    count = sealed["budgets"]["generations"]
    assert count >= 3
    _patch(monkeypatch, calls, _script({(arm, seed): 2}))
    result = campaign.run_campaign(sealed, seeds=[seed], generations=count)
    assert _gens_for(calls, arm, seed) == [1, 2]
    assert not [c for c in calls if c["arm"] == arm and c["generations"] >= 3]
    run = result["arms"][arm][0]
    assert run["generations_run"] == len(run["generations"]) == 2
    assert run["stopped_early"] is True and run["stop_reason"] == "exhausted_without_adoption"
    assert sum(record["spent"] for record in run["generations"]) == 2 * 10
    _check_executed(calls, result, count, sealed)


def test_exhaustion_with_adoption_continues_until_the_generation_limit(sealed, monkeypatch):
    """Fixture unitaire : épuisée mais digests différents (adoption) => poursuite jusqu'à count."""
    calls, arm, seed = [], ARMS[0], sealed["seeds"][0]
    count = sealed["budgets"]["generations"]
    _patch(monkeypatch, calls, _script({(arm, seed): 2}, adopted={(arm, seed)}))
    result = campaign.run_campaign(sealed, seeds=[seed], generations=count)
    run = result["arms"][arm][0]
    assert _gens_for(calls, arm, seed) == list(range(1, count + 1))
    assert run["generations_run"] == len(run["generations"]) == count
    assert run["stopped_early"] is False and run["stop_reason"] == "generation_limit"
    _check_executed(calls, result, count, sealed)


def test_missing_digests_never_truncate(sealed, monkeypatch):
    """Fixture unitaire : sans les deux digests, l'adoption n'est pas déductible ; rien n'est tronqué."""
    calls, seed = [], sealed["seeds"][0]
    count = sealed["budgets"]["generations"]
    _patch(monkeypatch, calls, _script(bare=True))
    result = campaign.run_campaign(sealed, seeds=[seed], generations=count)
    for name in ARMS:
        run = result["arms"][name][0]
        assert _gens_for(calls, name, seed) == list(range(1, count + 1))
        assert run["generations_run"] == len(run["generations"]) == count
        assert run["stopped_early"] is False and run["stop_reason"] == "generation_limit"
    _check_executed(calls, result, count, sealed)


def test_a_stop_does_not_influence_other_arms_or_seeds(sealed, monkeypatch):
    """Fixture unitaire : arrêt à la 2e pour (bras A, graine 0) ; (bras B, graine 1) va à count."""
    calls, first, second = [], sealed["seeds"][0], sealed["seeds"][1]
    count = sealed["budgets"]["generations"]
    _patch(monkeypatch, calls, _script({(ARMS[0], first): 2}))
    result = campaign.run_campaign(sealed, seeds=[first, second], generations=count)
    assert _gens_for(calls, ARMS[0], first) == [1, 2]
    for arm, seed in ((ARMS[1], second), (ARMS[0], second), (ARMS[1], first)):
        assert _gens_for(calls, arm, seed) == list(range(1, count + 1))
    stopped, other = result["arms"][ARMS[0]][0], result["arms"][ARMS[1]][1]
    assert stopped["generations_run"] == 2 and stopped["stopped_early"] is True
    assert other["seed"] == second and other["generations_run"] == count
    assert other["stopped_early"] is False and other["stop_reason"] == "generation_limit"
    _check_executed(calls, result, count, sealed)


def test_reduced_real_run_of_the_four_arms_applies_the_stop_rule(sealed):
    """Exécution réelle réduite : 1 graine, 1 génération, coûts factices 100 (plafond 800)."""
    seed = sealed["seeds"][0]
    result = campaign.run_campaign(sealed, seeds=[seed], generations=1)
    assert result["scale"] == "reduced" and result["seeds"] == [seed]
    assert set(result["arms"]) == set(ARMS)
    for name in ARMS:
        runs = result["arms"][name]
        assert len(runs) == 1
        run = runs[0]
        assert run["generations_run"] == len(run["generations"]) == 1
        for record in run["generations"]:
            assert record["spent"] <= record["limit"]
            assert _total(record["spend"]) == record["spent"]
        fired = any(campaign._stops(r) for r in run["generations"])
        assert run["stopped_early"] is fired
        assert run["stop_reason"] == ("exhausted_without_adoption" if fired else "generation_limit")


REAL_GENERATIONS = 3


def _instrumented(monkeypatch):
    """Compte les steps réels de ArmRun et additionne le spent des Meter créés pendant chacun."""
    real_meter, real_step = campaign.arms.ce.Meter, campaign.ArmRun.step
    meters, steps = [], []

    class SpyMeter(real_meter):
        def __init__(self, limit):
            super().__init__(limit)
            meters.append(self)

    def step(self):
        before = len(meters)
        index = self.index
        record = real_step(self)
        steps.append((self.arm, self.seed, index, sum(m.spent for m in meters[before:])))
        return record

    monkeypatch.setattr(campaign.arms.ce, "Meter", SpyMeter)
    monkeypatch.setattr(campaign.ArmRun, "step", step)
    return steps


def _real_args(plan):
    budgets = plan["budgets"]
    return plan["seeds"][0], freeze.learn_tasks(), budgets["per_generation_limit"], budgets["task_budget"]


@pytest.mark.parametrize("arm", ARMS)
def test_real_runs_execute_each_generation_once_and_publish_the_executed_spend(sealed, monkeypatch, arm):
    """Exécution réelle hors réseau : 1 graine, 3 générations par bras (durée non mesurée)."""
    steps = _instrumented(monkeypatch)
    seed, learn, limit, budget = _real_args(sealed)
    run = campaign.run_until_stop(arm, seed, learn, REAL_GENERATIONS, limit, budget)
    assert [(a, s, i) for a, s, i, _ in steps] == [(arm, seed, i) for i in range(run["generations_run"])]
    assert len(steps) == run["generations_run"] == len(run["generations"])
    assert sum(spent for *_, spent in steps) == sum(r["spent"] for r in run["generations"])
    assert 1 <= len(steps) <= REAL_GENERATIONS
    assert not any(campaign._stops(r) for r in run["generations"][:-1])


@pytest.mark.parametrize("arm", ARMS)
def test_persistent_run_equals_the_run_arm_trajectory(sealed, arm):
    """Même trajectoire que arms.run_arm sur generations_run générations, sans rejeu."""
    seed, learn, limit, budget = _real_args(sealed)
    run = campaign.run_until_stop(arm, seed, learn, REAL_GENERATIONS, limit, budget)
    reference = campaign.arms.run_arm(arm, seed, learn, run["generations_run"], limit, budget)
    assert run["generations"] == reference["generations"]


@pytest.mark.parametrize("parent_score, candidate_score", [([3, -50], [5, -40]), (None, [5, -40]), ([3, -50], None), (None, None)])
def test_inherited_lineage_publishes_the_parent_score_and_the_candidate_selection_score(sealed, monkeypatch, parent_score, candidate_score):
    """Fixture contrôlée, sans prétention de mesure : lineage.step est factice, parent_score != score."""
    def fake_step(state, learn, budget, meter, rng):
        body = {key: copy.deepcopy(value) for key, value in state.items() if key != "digest"}
        body["index"] += 1
        body["spent"] = {"procedure": 1, "synthesis": 2, "evaluations": 3}
        body["exhausted"] = False
        body["parent_score"] = parent_score
        body["score"] = candidate_score
        meter.charge(6)
        return campaign.arms.lineage._seal(body, state.engine)

    monkeypatch.setattr(campaign.arms.lineage, "step", fake_step)
    seed, learn, limit, budget = _real_args(sealed)
    run = campaign.new_run("inherited_lineage", seed, learn, 100, budget)
    record = run.step()
    assert record["score"] == parent_score
    assert record["selection_score"] == candidate_score
    if parent_score is not None:
        assert record["score"] is not run.state["parent_score"]
    if candidate_score is not None:
        assert record["selection_score"] is not run.state["score"]
    assert record["spend"] == {"procedure": 1, "synthesis": 2, "evaluations": 3}
    assert record["exhausted"] is False
    assert record["spent"] == sum(record["spend"].values()) == 6
