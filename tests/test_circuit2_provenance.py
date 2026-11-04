"""Tests de verify_circuit2_provenance : hors réseau, dépôt git temporaire.

Les fichiers JSON créés ici sont des fixtures synthétiques de test ; ils ne
représentent aucun résultat réel du projet.
"""

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_SCRIPT = RACINE / "scripts" / "verify_circuit2_provenance.py"

_spec = importlib.util.spec_from_file_location(
    "verify_circuit2_provenance", CHEMIN_SCRIPT
)
verif = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verif)


def git(depot, *args):
    res = subprocess.run(
        ["git", *args], cwd=str(depot), capture_output=True, text=True, check=True
    )
    return res.stdout.strip()


@pytest.fixture
def depot(tmp_path):
    d = tmp_path / "depot"
    d.mkdir()
    git(d, "init", "-q")
    git(d, "config", "user.email", "test@example.invalid")
    git(d, "config", "user.name", "Test")
    git(d, "config", "commit.gpgsign", "false")
    (d / "results").mkdir()

    def commit(nom):
        (d / f"{nom}.txt").write_text(nom, encoding="utf-8")
        git(d, "add", f"{nom}.txt")
        git(d, "commit", "-q", "-m", f"commit {nom}")
        return git(d, "rev-parse", "HEAD")

    c1 = commit("a")
    c2 = commit("b")
    principale = git(d, "rev-parse", "--abbrev-ref", "HEAD")
    git(d, "checkout", "-q", "-b", "autre", c1)
    c3 = commit("c")
    git(d, "checkout", "-q", principale)
    return SimpleNamespace(chemin=d, c1=c1, c2=c2, c3=c3)


def ecrire(depot, nom, contenu):
    f = depot.chemin / "results" / nom
    f.write_text(json.dumps(contenu), encoding="utf-8")
    return f


def verdict(depot, contenu):
    f = ecrire(depot, "fixture.json", contenu)
    return verif.verifier_fichier(f, depot.chemin)


def test_ancetre_de_head(depot):
    r = verdict(depot, {"machinery_commit": depot.c1})
    assert r["verdict"] == "ancetre_de_head"
    r = verdict(depot, {"machinery_commit": depot.c2})
    assert r["verdict"] == "ancetre_de_head"


def test_non_ancetre_autre_branche(depot):
    r = verdict(depot, {"machinery_commit": depot.c3})
    assert r["verdict"] == "non_ancetre"
    assert r["valeurs"][0]["commit_resolu"] == depot.c3


def test_commit_inconnu(depot):
    r = verdict(depot, {"machinery_commit": "deadbeef" * 5})
    assert r["verdict"] == "commit_inconnu"


def test_cle_absente(depot):
    r = verdict(depot, {"autre_cle": depot.c1})
    assert r["verdict"] == "cle_absente"
    assert r["valeurs"] == []


def test_prefixe_court_indetermine(depot, monkeypatch):
    appels = []
    monkeypatch.setattr(
        verif, "_git", lambda *a, **k: appels.append(a) or (0, "", "")
    )
    r = verdict(depot, {"machinery_commit": depot.c1[:12]})
    assert r["verdict"] == "indetermine"
    assert r["raison"] == "oid_complet_requis"
    assert r["valeurs"][0]["raison"] == "oid_complet_requis"
    assert r["valeurs"][0]["code_retour"] is None
    assert appels == []


def test_majuscules_indeterminees(depot):
    r = verdict(depot, {"machinery_commit": depot.c1.upper()})
    assert r["verdict"] == "indetermine"
    assert r["valeurs"][0]["raison"] == "oid_complet_requis"


def test_cle_trouvee_en_profondeur(depot):
    imbrique = {"a": [{"b": {"c": [{"machinery_commit": depot.c2}]}}]}
    assert verif.trouver_valeurs(imbrique) == [depot.c2]
    r = verdict(depot, imbrique)
    assert r["verdict"] == "ancetre_de_head"


def test_valeur_non_hexadecimale_indeterminee(depot):
    r = verdict(depot, {"machinery_commit": "--help"})
    assert r["verdict"] == "indetermine"
    assert r["valeurs"][0]["code_retour"] is None


def test_refus_chemin_hors_results(depot):
    hors = depot.chemin / "hors.json"
    hors.write_text("{}", encoding="utf-8")
    with pytest.raises(verif.CheminRefuse):
        verif.verifier_fichier(hors, depot.chemin)
    with pytest.raises(verif.CheminRefuse):
        verif.verifier_fichier("results/../hors.json", depot.chemin)


def test_refus_lien_symbolique(depot):
    cible = depot.chemin / "hors.json"
    cible.write_text("{}", encoding="utf-8")
    lien = depot.chemin / "results" / "lien.json"
    try:
        os.symlink(cible, lien)
    except (OSError, NotImplementedError):
        pytest.skip("liens symboliques indisponibles")
    with pytest.raises(verif.CheminRefuse):
        verif.verifier_fichier(lien, depot.chemin)


def test_sortie_ecrite_puis_refus_d_ecraser(depot, capsys):
    f = ecrire(depot, "entree.json", {"machinery_commit": depot.c1})
    assert verif.main([str(f)], depot=depot.chemin) == 0
    sortie = depot.chemin / "results" / "circuit2_provenance.json"
    contenu = json.loads(sortie.read_text(encoding="utf-8"))
    assert contenu["head"] == depot.c2
    assert contenu["fichiers_lus"] == ["results/entree.json"]
    assert contenu["verdicts"][0]["verdict"] == "ancetre_de_head"
    avant = sortie.read_text(encoding="utf-8")
    assert verif.main([str(f)], depot=depot.chemin) == 2
    assert sortie.read_text(encoding="utf-8") == avant
    assert "écriture refusée" in capsys.readouterr().err


def test_sortie_sans_cle_de_performance(depot):
    f = ecrire(depot, "entree.json", {"machinery_commit": depot.c1})
    assert verif.main([str(f)], depot=depot.chemin) == 0
    sortie = depot.chemin / "results" / "circuit2_provenance.json"
    contenu = json.loads(sortie.read_text(encoding="utf-8"))

    def cles(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from cles(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from cles(v)

    for k in cles(contenu):
        assert not any(m in k.lower() for m in ("gain", "success", "yield"))


def test_erreur_git_indeterminee(depot, monkeypatch):
    monkeypatch.setattr(verif, "_git", lambda *a, **k: (128, "", "fatal"))
    r = verdict(depot, {"machinery_commit": depot.c1})
    assert r["verdict"] == "indetermine"
    assert r["code_retour"] == 128
    assert r["valeurs"][0]["code_retour"] == 128


def test_git_inexecutable_indetermine(depot, monkeypatch):
    monkeypatch.setattr(verif, "_git", lambda *a, **k: (None, "", "OSError"))
    r = verdict(depot, {"machinery_commit": depot.c1})
    assert r["verdict"] == "indetermine"
    assert r["raison"] == "git_inexecutable"
    assert r["valeurs"][0]["raison"] == "git_inexecutable"
    assert r["code_retour"] is None


def test_resolution_differente_indeterminee(depot, monkeypatch):
    monkeypatch.setattr(
        verif, "_git", lambda *a, **k: (0, depot.c2 + "\n", "")
    )
    r = verdict(depot, {"machinery_commit": depot.c1})
    assert r["verdict"] == "indetermine"
    assert r["raison"] == "resolution_differente"
    assert r["valeurs"][0]["commit_resolu"] == depot.c2


def test_fichier_vide_indetermine(depot):
    f = depot.chemin / "results" / "vide.json"
    f.write_text("", encoding="utf-8")
    assert f.stat().st_size == 0
    r = verif.verifier_fichier(f, depot.chemin)
    assert r["verdict"] == "indetermine"
    assert r["raison"] == "fichier_vide"
    assert r["code_retour"] is None
    assert r["valeurs"] == []


def test_script_commite_non_vide():
    assert CHEMIN_SCRIPT.stat().st_size > 0
    assert "def main" in CHEMIN_SCRIPT.read_text(encoding="utf-8")


def test_clone_superficiel_ancetre_absent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.email", "test@example.invalid")
    git(source, "config", "user.name", "Test")
    git(source, "config", "commit.gpgsign", "false")
    oids = []
    for nom in ("a", "b", "c"):
        (source / f"{nom}.txt").write_text(nom, encoding="utf-8")
        git(source, "add", f"{nom}.txt")
        git(source, "commit", "-q", "-m", f"commit {nom}")
        oids.append(git(source, "rev-parse", "HEAD"))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "--depth", "1", source.as_uri(), str(clone))
    assert git(clone, "rev-parse", "--is-shallow-repository") == "true"
    assert git(clone, "rev-parse", "HEAD") == oids[2]
    (clone / "results").mkdir()
    f = clone / "results" / "fixture.json"
    f.write_text(json.dumps({"machinery_commit": oids[0]}), encoding="utf-8")
    r = verif.verifier_fichier(f, clone)
    assert r["verdict"] != "ancetre_de_head"
    assert r["verdict"] in ("commit_inconnu", "indetermine")
    f.write_text(json.dumps({"machinery_commit": oids[2]}), encoding="utf-8")
    assert verif.verifier_fichier(f, clone)["verdict"] == "ancetre_de_head"
