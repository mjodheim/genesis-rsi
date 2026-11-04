"""Contrôles hors réseau du wrapper de capture budget 16 du CIRCUIT2."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHEMIN = ROOT / "scripts" / "capture_circuit2_budget16.py"
DIAGNOSTIC = ROOT / "scripts" / "circuit2_budget16_diagnostic.py"
NOM_STDOUT = "circuit2_budget16_stdout.json"
NOM_STDERR = "circuit2_budget16_stderr.txt"


def _charger():
    nom = "capture_circuit2_budget16"
    spec = importlib.util.spec_from_file_location(nom, CHEMIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


cap = _charger()


def _faux_script(racine, corps):
    dossier = racine / "scripts"
    dossier.mkdir()
    (dossier / cap.SCRIPT_NAME).write_text(corps, encoding="utf-8")


def _runner(resultat=None, appels=None):
    def faux(*args, **kwargs):
        if appels is not None:
            appels.append((args, kwargs))
        return resultat

    return faux


def _sha(chemin):
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def test_stdout_et_stderr_dans_deux_fichiers_et_code_propage(tmp_path):
    _faux_script(
        tmp_path,
        "import sys\n"
        "sys.stdout.write('{\"a\": 1}\\n')\n"
        "sys.stderr.write('avertissement\\n')\n"
        "sys.exit(3)\n",
    )
    assert cap.main([], root=tmp_path) == 3
    sortie = tmp_path / "results" / NOM_STDOUT
    erreur = tmp_path / "results" / NOM_STDERR
    assert sortie != erreur
    assert sortie.read_text(encoding="utf-8") == '{"a": 1}\n'
    assert erreur.read_text(encoding="utf-8") == "avertissement\n"


def test_appel_identique_a_celui_du_test_d_integration(tmp_path):
    appels = []
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"{}\n", stderr=b""), appels)
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert len(appels) == 1
    args, kwargs = appels[0]
    assert args == ([sys.executable, str(tmp_path / "scripts" / cap.SCRIPT_NAME)],)
    assert kwargs == {
        "cwd": str(tmp_path),
        "capture_output": True,
        "timeout": 600,
        "check": False,
    }


def test_stdout_vide_est_ecrit_tel_quel(tmp_path):
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"", stderr=b""))
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert (tmp_path / "results" / NOM_STDOUT).read_bytes() == b""
    assert (tmp_path / "results" / NOM_STDERR).read_bytes() == b""


def test_timeout_ecrit_le_partiel_sans_rien_inventer(tmp_path):
    def faux(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 600, output=b"partiel", stderr=None)

    assert cap.main([], root=tmp_path, runner=faux) == cap.TIMEOUT_CODE
    assert (tmp_path / "results" / NOM_STDOUT).read_text(encoding="utf-8") == "partiel"
    assert (tmp_path / "results" / NOM_STDERR).read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("existant", [NOM_STDOUT, NOM_STDERR])
def test_refus_d_ecraser_un_fichier_existant(tmp_path, existant, capsys):
    (tmp_path / "results").mkdir()
    ancien = tmp_path / "results" / existant
    ancien.write_text("ancien", encoding="utf-8")
    appels = []
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"neuf", stderr=b"neuf"), appels)
    assert cap.main([], root=tmp_path, runner=faux) == 2
    assert appels == []
    assert ancien.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in (tmp_path / "results").iterdir()) == [existant]
    assert "Refus" in capsys.readouterr().err


def test_aucune_ecriture_hors_results(tmp_path):
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"x", stderr=b"y"))
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["results"]
    results = (tmp_path / "results").resolve()
    for nom in ("../x", "sous/x", "/tmp/x", "", ".."):
        with pytest.raises(cap.CaptureError):
            cap._target(results, nom)


def test_results_symlink_vers_l_exterieur_est_refuse(tmp_path):
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    racine = tmp_path / "depot"
    racine.mkdir()
    (racine / "results").symlink_to(dehors, target_is_directory=True)
    appels = []
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"x", stderr=b"y"), appels)
    assert cap.main([], root=racine, runner=faux) == 2
    assert appels == []
    assert list(dehors.iterdir()) == []


def test_options_refusees():
    with pytest.raises(SystemExit):
        cap.main(["--out", "x.json"])


def test_script_de_diagnostic_inchange(tmp_path):
    avant = _sha(DIAGNOSTIC)
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"{}\n", stderr=b""))
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert _sha(DIAGNOSTIC) == avant


def test_crlf_conserve_exactement_en_stdout_et_stderr(tmp_path):
    faux = _runner(SimpleNamespace(returncode=0, stdout=b"a\r\nb\r\n", stderr=b"a\r\nb\r\n"))
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert (tmp_path / "results" / NOM_STDOUT).read_bytes() == b"a\r\nb\r\n"
    assert (tmp_path / "results" / NOM_STDERR).read_bytes() == b"a\r\nb\r\n"


def test_octets_non_utf8_conserves_sans_exception(tmp_path):
    brut = b"\xff\xfe\x80"
    faux = _runner(SimpleNamespace(returncode=0, stdout=brut, stderr=brut))
    assert cap.main([], root=tmp_path, runner=faux) == 0
    assert (tmp_path / "results" / NOM_STDOUT).read_bytes() == brut
    assert (tmp_path / "results" / NOM_STDERR).read_bytes() == brut


def test_timeout_conserve_les_octets_partiels_a_l_identique(tmp_path):
    def faux(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 600, output=b"\xe2\x82", stderr=b"\xff")

    assert cap.main([], root=tmp_path, runner=faux) == cap.TIMEOUT_CODE
    assert (tmp_path / "results" / NOM_STDOUT).read_bytes() == b"\xe2\x82"
    assert (tmp_path / "results" / NOM_STDERR).read_bytes() == b"\xff"


def test_sous_processus_reel_octets_bruts_retrouves_a_l_identique(tmp_path):
    _faux_script(
        tmp_path,
        "import sys\n"
        "sys.stdout.buffer.write(b'a\\r\\nb\\r\\n\\xff')\n"
        "sys.stderr.buffer.write(b'e\\r\\n\\x80')\n",
    )
    assert cap.main([], root=tmp_path) == 0
    assert (tmp_path / "results" / NOM_STDOUT).read_bytes() == b"a\r\nb\r\n\xff"
    assert (tmp_path / "results" / NOM_STDERR).read_bytes() == b"e\r\n\x80"
