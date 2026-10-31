"""Vivacité du chemin circuit2 : aucune amélioration de score exigée."""
from dataclasses import replace
import sys
from pathlib import Path

import pytest

try:
    import circuit2_liveness as lv
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import circuit2_liveness as lv

BUDGET = dict(mutations=12, runs=8, randoms=2)


def test_terminaison_et_bilan():
    b = lv.diagnose(seed=1, **BUDGET)
    assert b["mutations_done"] == 12
    assert b["randoms_done"] == 2
    assert b["procedures"] == 1 + 12 + 2
    assert b["runs_done"] == b["procedures"] * b["cases_per_procedure"]
    assert b["cases_per_procedure"] >= 8
    assert b["gates_total"] == sum(n * b["cases_per_procedure"] for n in b["steps_per_procedure"])
    assert b["roundtrips_ok"] == b["procedures"]
    assert len(b["digests"]) == b["procedures"]


def test_contrats():
    assert lv.diagnose(seed=2, **BUDGET)["violations"] == []


def test_mutate_ne_modifie_pas_l_original():
    p = lv.cp.seed_procedure()
    avant = lv._record_json(p)
    rng = lv.random.Random("test|mutate")
    q = lv.cp.mutate(p, rng)
    assert lv._record_json(p) == avant
    assert q is not None
    lv.cp.validate(q)


def test_reproductibilite():
    a = lv.diagnose(seed=3, **BUDGET)
    assert a == lv.diagnose(seed=3, **BUDGET)
    assert a["digests"] != lv.diagnose(seed=4, **BUDGET)["digests"]


def test_taches_apprentissage():
    b = lv.diagnose(seed=0, **BUDGET)
    assert b["learn_task_count"] > 0
    learn = {str(x) for x in lv.tasks.LEARN}
    assert set(b["learn_families"]) <= learn


def test_dependance_interne_manquante_reste_visible(monkeypatch):
    def faux_import(nom, *args, **kwargs):
        raise ModuleNotFoundError("No module named 'numpy_absent'", name="numpy_absent")

    monkeypatch.setattr(lv.importlib, "import_module", faux_import)
    with pytest.raises(ModuleNotFoundError) as info:
        lv._charger("circuit_procedure")
    assert info.value.name == "numpy_absent"


def test_module_essaye_absent_passe_au_prefixe_suivant(monkeypatch):
    sentinelle = object()
    essais = []

    def faux_import(nom, *args, **kwargs):
        essais.append(nom)
        if nom == "genesis.module_x":
            return sentinelle
        raise ModuleNotFoundError(f"No module named '{nom}'", name=nom)

    monkeypatch.setattr(lv.importlib, "import_module", faux_import)
    assert lv._charger("module_x") is sentinelle
    assert essais == ["module_x", "genesis.module_x"]


def test_procedure_de_depart_est_validee_avant_les_mutations(monkeypatch):
    noms = []
    original = lv._valider

    def espion(p, nom, violations):
        noms.append(nom)
        return original(p, nom, violations)

    monkeypatch.setattr(lv, "_valider", espion)
    lv.diagnose(seed=5, mutations=2, runs=1, randoms=1)
    assert noms[0] == "départ"
    assert noms.count("départ") == 1


def test_procedure_de_depart_refusee_donne_une_violation(monkeypatch):
    depart = lv.cp.seed_procedure()
    original = lv.cp.validate

    def validate_refuse_depart(p):
        if p == depart:
            raise lv.cp.ProcedureError("départ refusé")
        return original(p)

    monkeypatch.setattr(lv.cp, "validate", validate_refuse_depart)
    recues = []
    run_original = lv.cp.run

    def run_espion(p, traits):
        recues.append(p)
        return run_original(p, traits)

    monkeypatch.setattr(lv.cp, "run", run_espion)
    b = lv.diagnose(seed=6, mutations=0, runs=1, randoms=0)
    assert any(v.startswith("validate refuse départ") for v in b["violations"])
    assert all(p != depart for p in recues)
    assert b["procedures"] == 0
    assert b["runs_done"] == 0


def test_valider_renvoie_un_booleen_explicite():
    violations = []
    assert lv._valider(lv.cp.seed_procedure(), "ok", violations) is True
    assert violations == []
    p = lv.cp.seed_procedure()
    invalide = replace(p, admit_output=p.n_inputs + len(p.steps))
    assert lv._valider(invalide, "invalide", violations) is False
    assert len(violations) == 1
    assert violations[0].startswith("validate refuse invalide")


def test_suite_vide_donne_une_violation(monkeypatch):
    monkeypatch.setattr(lv.tasks, "tasks", lambda *a, **k: [])
    b = lv.diagnose(seed=7, mutations=0, runs=1, randoms=0)
    assert "suite circuit2 vide" in b["violations"]


def test_famille_manquante_donne_une_violation(monkeypatch):
    learn = [str(x) for x in lv.tasks.LEARN]
    retiree = learn[-1]
    def faux_tasks(famille, *a, **k):
        if str(famille) == retiree:
            return []
        return [{"family": str(famille)}]
    monkeypatch.setattr(lv.tasks, "tasks", faux_tasks)
    b = lv.diagnose(seed=8, mutations=0, runs=1, randoms=0)
    assert any("absentes" in v and retiree in v for v in b["violations"])


def _refuser(monkeypatch, cible):
    original = lv.cp.validate

    def validate(p):
        if cible(p):
            raise lv.cp.ProcedureError("refus ciblé")
        return original(p)

    monkeypatch.setattr(lv.cp, "validate", validate)


def _espions(monkeypatch):
    vus = {"run": [], "replay_digest": [], "to_record": []}
    for nom in vus:
        original = getattr(lv.cp, nom)

        def espion(p, *a, _o=original, _l=vus[nom], **k):
            _l.append(p)
            return _o(p, *a, **k)

        monkeypatch.setattr(lv.cp, nom, espion)
    return vus


def _noms(familles):
    if isinstance(familles, str):
        return {familles}
    return {str(f) for f in familles}


def test_lecture_limitee_a_learn(monkeypatch):
    demandees = []
    original = lv.tasks.tasks

    def espion(famille, *a, **k):
        demandees.append(str(famille))
        return original(famille, *a, **k)

    def sentinelle(*a, **k):
        raise AssertionError("_circuit2_assignment ne doit pas être appelée")

    monkeypatch.setattr(lv.tasks, "tasks", espion)
    monkeypatch.setattr(lv.tasks, "_circuit2_assignment", sentinelle)
    b = lv.diagnose(seed=9, mutations=0, runs=1, randoms=0)
    assert b["violations"] == []
    assert sorted(demandees) == sorted(_noms(lv.tasks.LEARN))
    assert len(demandees) == len(set(demandees))
    assert not set(demandees) & _noms(lv.tasks.HELD_OUT)
    assert not set(demandees) & _noms(lv.tasks.CONTROL)


def test_depart_refuse_avec_mutations_ne_mute_pas(monkeypatch):
    depart = lv.cp.seed_procedure()

    def lever(*a, **k):
        raise AssertionError("mutate ne doit pas être appelée")

    _refuser(monkeypatch, lambda p: p == depart)
    monkeypatch.setattr(lv.cp, "mutate", lever)
    vus = _espions(monkeypatch)
    b = lv.diagnose(seed=10, mutations=5, runs=1, randoms=0)
    assert any(v.startswith("validate refuse départ") for v in b["violations"])
    assert vus["run"] == []
    assert b["procedures"] == 0
    assert b["runs_done"] == 0
    assert b["mutations_done"] == 0
    b = lv.diagnose(seed=10, mutations=5, runs=1, randoms=2)
    assert any(v.startswith("validate refuse départ") for v in b["violations"])
    assert b["randoms_done"] == 2
    assert b["procedures"] == 2
    assert b["mutations_done"] == 0
    assert b["runs_done"] == 2 * b["cases_per_procedure"]
    assert all(p != depart for p in vus["run"])
    assert all(p != depart for p in vus["replay_digest"])
    assert all(p != depart for p in vus["to_record"])


def test_mutation_refusee_est_exclue_et_la_suite_continue(monkeypatch):
    produites = []
    original = lv.cp.mutate

    def mutate_espion(p, rng):
        q = original(p, rng)
        if q is not None:
            produites.append(q)
        return q

    monkeypatch.setattr(lv.cp, "mutate", mutate_espion)
    _refuser(monkeypatch, lambda p: len(produites) >= 3 and p is produites[2])
    vus = _espions(monkeypatch)
    b = lv.diagnose(seed=11, mutations=8, runs=1, randoms=0)
    assert len(produites) >= 4
    cible = produites[2]
    refusees = [v for v in b["violations"] if v.startswith("validate refuse mutée")]
    assert len(refusees) == 1 and len(b["violations"]) == 1
    for lot in vus.values():
        assert not any(p is cible for p in lot)
    assert b["mutations_done"] == len(produites) - 1
    assert b["procedures"] == 1 + b["mutations_done"]
    assert b["runs_done"] == b["procedures"] * b["cases_per_procedure"]
    assert len(b["digests"]) == b["procedures"]
    assert b["roundtrips_ok"] == b["procedures"]


def test_aleatoire_refusee_est_exclue_et_les_autres_continuent(monkeypatch):
    produites = []
    original = lv.cp.random_procedure

    def random_espion(*a, **k):
        q = original(*a, **k)
        produites.append(q)
        return q

    monkeypatch.setattr(lv.cp, "random_procedure", random_espion)
    _refuser(monkeypatch, lambda p: len(produites) >= 2 and p is produites[1])
    vus = _espions(monkeypatch)
    b = lv.diagnose(seed=12, mutations=0, runs=1, randoms=3)
    assert len(produites) == 3
    cible = produites[1]
    refusees = [v for v in b["violations"] if v.startswith("validate refuse aléatoire 1")]
    assert len(refusees) == 1 and len(b["violations"]) == 1
    for lot in vus.values():
        assert not any(p is cible for p in lot)
    assert b["randoms_done"] == 2
    assert b["procedures"] == 1 + 2
    assert b["runs_done"] == b["procedures"] * b["cases_per_procedure"]
    assert len(b["digests"]) == b["procedures"]
    assert b["roundtrips_ok"] == b["procedures"]


SCRIPT = Path(lv.__file__).resolve()


def _lancer_script(cwd):
    import subprocess

    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def test_script_sous_processus_chemin_positif(tmp_path):
    import json

    r = _lancer_script(tmp_path)
    assert r.returncode == 0, r.stderr
    b = json.loads(r.stdout)
    assert b["violations"] == []
    assert b["procedures"] > 0
    learn = {str(x) for x in lv.tasks.LEARN}
    assert b["learn_families"]
    assert set(b["learn_families"]) <= learn


def test_script_sous_processus_silencieux_et_stable(tmp_path):
    import json

    a = _lancer_script(tmp_path)
    c = _lancer_script(tmp_path)
    assert a.returncode == 0 and c.returncode == 0
    assert list(tmp_path.iterdir()) == []
    assert json.loads(a.stdout) == json.loads(c.stdout)
