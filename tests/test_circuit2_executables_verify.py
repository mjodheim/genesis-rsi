"""Tests du vérificateur d'identité des exécutables CIRCUIT2.

Hors réseau. Les dépôts factices sont créés dans tmp_path avec des fichiers
SYNTHÉTIQUES (contenu arbitraire, sans lien avec les vrais exécutables).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

CHEMIN = Path(__file__).resolve().parent.parent / "scripts" / "verify_circuit2_executables.py"


def _charger():
    nom = "verify_circuit2_executables"
    if nom in sys.modules:
        return sys.modules[nom]
    spec = importlib.util.spec_from_file_location(nom, CHEMIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


verif = _charger()
NOMS = [f"synthetique_{i}.py" for i in range(8)]


@pytest.fixture
def depot(tmp_path, monkeypatch):
    gel = verif._charger_gel()
    monkeypatch.setattr(gel, "EXECUTABLES", tuple(NOMS))
    for i, nom in enumerate(NOMS):
        (tmp_path / nom).write_bytes(f"# fichier synthétique {i}\n".encode())
    calcule = gel.compute_manifest(tmp_path, tuple(NOMS))
    fichiers = dict(calcule["files"]) if isinstance(calcule.get("files"), dict) else dict(calcule)
    manifeste = {"digest": gel.global_digest(fichiers), "files": fichiers}
    _ecrire(tmp_path, manifeste)
    monkeypatch.setattr(verif, "RACINE_DEFAUT", tmp_path)
    return tmp_path


def _chemin(depot):
    return depot / "experiment" / "engine" / "CIRCUIT2" / "EXECUTABLES.json"


def _ecrire(depot, manifeste):
    chemin = _chemin(depot)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")


def _lire(depot):
    return json.loads(_chemin(depot).read_text(encoding="utf-8"))


def test_nominal(depot):
    assert verif.verify_manifest(root=depot) == []


def test_fichier_modifie_d_un_octet(depot):
    cible = depot / NOMS[3]
    cible.write_bytes(cible.read_bytes() + b"x")
    with pytest.raises(verif.ExecutableIdentityError, match="différente") as info:
        verif.verify_manifest(root=depot)
    assert NOMS[3] in str(info.value)


def test_fichier_absent(depot):
    (depot / NOMS[0]).unlink()
    with pytest.raises(verif.ExecutableIdentityError, match="absent") as info:
        verif.verify_manifest(root=depot)
    assert NOMS[0] in str(info.value)


def test_manifeste_absent(depot):
    _chemin(depot).unlink()
    with pytest.raises(verif.ExecutableIdentityError, match="absent") as info:
        verif.verify_manifest(root=depot)
    assert "EXECUTABLES.json" in str(info.value)


def test_manifeste_illisible(depot):
    _chemin(depot).write_text("{pas du json", encoding="utf-8")
    with pytest.raises(verif.ExecutableIdentityError, match="illisible"):
        verif.verify_manifest(root=depot)


def test_digest_altere_files_intacts(depot):
    m = _lire(depot)
    fichiers_avant = dict(m["files"])
    m["digest"] = "0" * 64
    _ecrire(depot, m)
    assert _lire(depot)["files"] == fichiers_avant
    with pytest.raises(verif.ExecutableIdentityError, match="incohérent"):
        verif.verify_manifest(root=depot)


def test_cle_en_trop(depot):
    gel = verif._charger_gel()
    m = _lire(depot)
    m["files"]["intrus.py"] = "1" * 64
    m["digest"] = gel.global_digest(m["files"])
    _ecrire(depot, m)
    with pytest.raises(verif.ExecutableIdentityError, match="en trop") as info:
        verif.verify_manifest(root=depot)
    assert "intrus.py" in str(info.value)


def test_manifeste_inchange_octet_pour_octet_apres_succes(depot):
    chemin = _chemin(depot)
    avant = chemin.read_bytes()
    assert verif.verify_manifest(root=depot) == []
    assert chemin.read_bytes() == avant


def test_manifeste_inchange_octet_pour_octet_apres_echec(depot):
    chemin = _chemin(depot)
    (depot / NOMS[2]).write_bytes(b"altere")
    avant = chemin.read_bytes()
    with pytest.raises(verif.ExecutableIdentityError):
        verif.verify_manifest(root=depot)
    assert chemin.read_bytes() == avant


def test_main_refuse_avant_tout_appel_du_lanceur(depot, monkeypatch, capsys):
    (depot / NOMS[1]).write_bytes(b"altere")
    appels = []
    monkeypatch.setattr(verif.importlib, "import_module", lambda nom: appels.append(nom))
    assert verif.main(["--x"]) == 2
    assert appels == []
    assert "Refus" in capsys.readouterr().err


def test_main_delegue_si_ok(depot, monkeypatch):
    recus = []

    class Espion:
        @staticmethod
        def main(args):
            recus.append(args)
            return 0

    monkeypatch.setattr(verif.importlib, "import_module", lambda nom: Espion)
    assert verif.main(["--a", "1"]) == 0
    assert recus == [["--a", "1"]]


def test_depot_reel_conforme_au_manifeste_publie():
    assert verif.verify_manifest() == []
