import ast
import importlib.util
from pathlib import Path

CHEMIN = Path(__file__).resolve().parent.parent / "scripts" / "circuit2_learn_scale_readiness.py"
CLES = {"point", "constat", "source", "extrait", "statut"}
STATUTS = {"lu", "non vérifié"}
INTERDITS = {"run_circuit2_campaign", "freeze_circuit2_plan", "socket", "urllib", "requests", "http"}


def _charger():
    spec = importlib.util.spec_from_file_location("circuit2_learn_scale_readiness", CHEMIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VERDICT


def _modules_importes():
    arbre = ast.parse(CHEMIN.read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                noms.add(alias.name)
                noms.add(alias.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            noms.add(module)
            noms.add(module.split(".")[0])
            for alias in noeud.names:
                noms.add(alias.name)
    return noms


def test_cles_et_statuts():
    for entree in _charger():
        assert set(entree) == CLES
        assert isinstance(entree["point"], int)
        assert entree["statut"] in STATUTS


def test_entrees_lues_documentees():
    for entree in _charger():
        if entree["statut"] == "lu":
            assert entree["source"].strip()
            assert entree["extrait"].strip()


def test_points_presents():
    points = {entree["point"] for entree in _charger()}
    assert {1, 2, 3} <= points


def test_aucun_import_interdit():
    assert not (_modules_importes() & INTERDITS)


def test_aucune_mention_held_out():
    assert "HELD_OUT" not in CHEMIN.read_text(encoding="utf-8")
