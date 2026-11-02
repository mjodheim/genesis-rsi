"""Diagnostic relationnel de improved_by selon task_budget (16 et 64).

Départage les hypothèses possibles pour un rendement nul de improved_by :
« aucun_candidat » (candidates == 0, quel que soit le nombre de tâches
résolues), « admission » (candidats proposés mais aucun admis/essayé) et
« acceptation_refusee » (essais sans ajout) ; « adopte » si un composant
est ajouté. Aucun nombre n'est codé : seules des relations sont affirmées.
Le test d'affichage écrit la classification observée de chaque budget.

Provenance : ce test n'est pas lu à partir des JSON gelés. Il exécute
improved_by et ce.measure sur six tâches synthétiques, à task_budget 16
et 64. Le diagnostic a été motivé par les adjudications réduites de la
graine 0, dont les champs machinery_commit lus dans les JSON sont :
results/circuit2_adjudication_s0_g1.json (1 génération) porte
machinery_commit 0247f6cd4409aa2d86d6b0d1db532179aebc908f ;
results/circuit2_adjudication_s0_g2.json (2 générations) porte
machinery_commit afb02ecaf37ddee6f02f2065cd2822330bc7fe85. Ces deux
commits de machinerie diffèrent : les deux JSON ne forment donc pas une
série strictement comparable. Le résultat observé dans les deux JSON est
négatif : held_out_yield 0 et même library_fingerprint (03922f7a…) pour
les quatre bras.

Ce fichier est exécuté. Il utilise _metered_attempt, ce.measure et
improved_by tels qu'ils sont, sans les modifier ni les contourner. Si la
classification affichée à budget 16 n'est pas 'aucun_candidat' ou
'admission', le cas ne reproduit pas un rendement nul ; il ne doit pas être
retouché (ni task_budget) pour autant.
"""

from __future__ import annotations

import pytest

import genesis.circuit_engine as ce
import genesis.circuit_procedure as cp
from genesis.trust_root import digest_of

BUDGETS = (16, 64)
LIMITS = (0, 5, 50, 500)
TARGETS = (
    ("AND", 8),
    ("OR", 14),
    ("XOR", 6),
    ("XNOR", 9),
    ("NAND", 7),
    ("NOR", 1),
)


def _tasks():
    return [ce.Task(name=n, family="synthetic", inputs=2, target=t) for n, t in TARGETS]


def _measure(base):
    s, e = ce.measure(base)
    return s, -e


def _run(tb, limit=10**6):
    tasks = _tasks()
    base = ce._metered_attempt(ce.Engine(), tasks, tb, ce.Meter(10**6), {"procedure": 0, "synthesis": 0, "evaluations": 0})
    assert base is not None
    eng0 = ce.Engine()
    before = digest_of(eng0.record())
    meter = ce.Meter(limit)
    engine, _solutions, info = ce.improved_by(eng0, tasks, tb, base, cp.seed_procedure(), meter, generation=0)
    assert engine is not None, "improved_by ne renvoie aucun objet moteur identifiable"
    solved, neg_eval = _measure(base)
    summary = {
        "resolues_avant": solved,
        "evaluations_avant": -neg_eval,
        "candidates": info["candidates"],
        "admitted": info["admitted"],
        "trials": len(info["trials"]),
        "added": info["added"],
        "exhausted": info["exhausted"],
        "spent": dict(info["spent"]),
        "empreinte_avant": before,
        "empreinte_apres": digest_of(engine.record()),
    }
    raw = {"tasks": tasks, "base": base, "eng0": eng0, "engine": engine, "meter": meter}
    return summary, raw


def classify(s):
    if s["candidates"] == 0:
        return "aucun_candidat"
    if s["trials"] == 0:
        return "admission"
    if s["added"] is None:
        return "acceptation_refusee"
    return "adopte"


def test_api_circuit_procedure():
    seed = cp.seed_procedure()
    traits = cp.traits_of(3, 3, 2, True)
    priority, admit, gates = cp.run(seed, traits)
    assert isinstance(priority, int) and isinstance(admit, bool) and isinstance(gates, int) and gates >= 0, (
        "API run : (priorité entière, admission booléenne, nombre de portes) attendu"
    )
    assert cp.run(seed, traits) == (priority, admit, gates), "run doit être déterministe"


@pytest.mark.parametrize("tb", BUDGETS)
def test_relations(tb):
    s, raw = _run(tb)
    assert s["admitted"] <= s["candidates"], "hypothèse 'admission' : les admis ne peuvent excéder les candidats proposés"
    assert s["trials"] <= min(s["admitted"], 6), "hypothèse 'admission' : essais bornés par les admis et par tried=6"
    assert sum(s["spent"].values()) == raw["meter"].spent, "comptabilité : la somme des postes de info['spent'] doit égaler meter.spent"
    if s["added"] is not None:
        assert s["trials"] >= 1, "un ajout suppose au moins un essai"
    if s["trials"] > 0:
        assert s["candidates"] > 0, "des essais supposent des candidats proposés"
    if s["candidates"] == 0:
        assert s["added"] is None, "sans candidat, aucun ajout"
        assert s["empreinte_avant"] == s["empreinte_apres"], "sans candidat, l'empreinte doit rester inchangée"
    if s["added"] is not None:
        assert s["empreinte_avant"] != s["empreinte_apres"], "hypothèse 'accepté mais bibliothèque inchangée' : l'empreinte doit changer"
        after = ce._metered_attempt(raw["engine"], raw["tasks"], tb, ce.Meter(10**6), {"procedure": 0, "synthesis": 0, "evaluations": 0})
        assert _measure(after) > _measure(raw["base"]), "hypothèse 'acceptation' : (résolues, -évaluations) doit être strictement meilleur"
    else:
        assert raw["engine"] is raw["eng0"], "hypothèse 'acceptation refusée' : sans ajout, le moteur renvoyé doit être le même objet"


@pytest.mark.parametrize("limit", LIMITS)
@pytest.mark.parametrize("tb", BUDGETS)
def test_plafonds(tb, limit):
    s, raw = _run(tb, limit)
    assert raw["meter"].spent <= limit, "hypothèse 'facturation' : meter.spent ne doit pas dépasser le plafond"
    assert isinstance(s["exhausted"], bool), "info['exhausted'] doit être un booléen"
    assert sum(s["spent"].values()) == raw["meter"].spent, "comptabilité : postes de info['spent'] et meter.spent doivent coïncider"
    if limit == 0:
        assert raw["meter"].spent == 0, "plafond exact à zéro : rien ne doit être dépensé"
        assert s["added"] is None, "plafond à zéro : aucun ajout sans budget"


@pytest.mark.parametrize("tb", BUDGETS)
def test_determinisme(tb):
    assert _run(tb)[0] == _run(tb)[0], "hypothèse 'non-déterminisme' : deux exécutions doivent donner le même dict"


def test_affiche_classification(capsys):
    with capsys.disabled():
        for tb in BUDGETS:
            s, _ = _run(tb)
            print(f"\n[improved_by] task_budget={tb} classification={classify(s)} candidates={s['candidates']} admitted={s['admitted']} trials={s['trials']} resolues_avant={s['resolues_avant']}")
