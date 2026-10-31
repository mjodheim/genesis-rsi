"""Approbation du wrapper non scellé, hors réseau, sans génération réelle.

Seul le point d'entrée hôte (wrapper non scellé + fichier d'approbation hors dépôt,
variable GENESIS_HOST_APPROVALS) est protégé. L'appel direct du lanceur historique
gelé n'est PAS protégé par le wrapper, et cette limite subsiste : le refuser
exigerait un nouveau lanceur re-scellé, décision à prendre séparément.
Le dépôt ne prouve pas l'indépendance de l'approbation : elle dépend de la
configuration de l'hôte (fichier hors dépôt, non inscriptible par le candidat).
La règle de propriété (fichier appartenant à root ou à un autre uid que l'uid courant)
dépend de la configuration de l'hôte ; sous root, un fichier créé par le test appartient
à root, d'où les tests skipped. Les autres modules importés par le lanceur ne sont pas
couverts par les empreintes du lanceur, du vérificateur et du sceau.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import run_circuit2_campaign as campaign

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_circuit2_anchored.py"
LAUNCHER = ROOT / "scripts" / "run_circuit2_campaign.py"
OPTION = "--approved-seal-sha256"
ENV = "GENESIS_HOST_APPROVALS"
KEY = "circuit2_launcher_seal_sha256"
LAUNCHER_KEY = "circuit2_launcher_sha256"
VERIFIER_KEY = "circuit2_verifier_sha256"
SEAL_PATH_KEY = "circuit2_launcher_seal_path"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _anchored(tmp_path, extra, approvals=None):
    out = tmp_path / "OUT.json"
    env = {k: v for k, v in os.environ.items() if k != ENV}
    if approvals is not None:
        env[ENV] = str(approvals)
    return subprocess.run(
        [
            sys.executable, "-I", "-B", str(SCRIPT),
            "--seeds", "0", "--generations", "1",
            "--out", str(out), *extra,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def test_anchored_subprocess_requires_approval(tmp_path):
    done = _anchored(tmp_path, [])
    assert done.returncode == 2
    assert done.stdout == ""
    assert done.stderr.startswith("refus")
    assert list(tmp_path.iterdir()) == []


def _host_file(tmp_path_factory, content):
    """Fichier d'approbation hôte hors dépôt et hors du répertoire de travail, mode 0o600."""
    path = tmp_path_factory.mktemp("host") / "approvals.json"
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    assert not path.resolve().is_relative_to(ROOT.resolve())
    return path


@pytest.mark.parametrize("value", ["", "abc", "F" * 64, "0" * 63, "0" * 64])
def test_anchored_subprocess_refuses_a_command_line_anchor(tmp_path, tmp_path_factory, value):
    """Empreinte hôte volontairement différente du sceau : aucune génération possible, même en cas de régression."""
    approvals = _host_file(tmp_path_factory, json.dumps({KEY: "0" * 64}))
    done = _anchored(tmp_path, [OPTION, value], approvals)
    assert done.returncode == 2
    assert done.stdout == ""
    assert OPTION in done.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("content", ["", "{", "[]", "{}", json.dumps({KEY: "F" * 64}), json.dumps({KEY: "0" * 64})])
def test_anchored_subprocess_refuses_an_invalid_or_different_host_approval(tmp_path, tmp_path_factory, content):
    approvals = _host_file(tmp_path_factory, content)
    done = _anchored(tmp_path, [], approvals)
    assert done.returncode == 2
    assert done.stdout == ""
    assert done.stderr.startswith("refus")
    assert list(tmp_path.iterdir()) == []


def test_historical_launcher_matches_the_versioned_seal():
    seal = json.loads(Path(campaign.SEAL_PATH).read_bytes())
    assert _sha(LAUNCHER) == seal["launcher_sha256"]

def test_direct_historical_entry_point_bypasses_the_wrapper():
    """Limite connue, qui subsiste : l'appel direct du lanceur gelé n'est PAS protégé par le wrapper.

    Seul le point d'entrée hôte (wrapper + fichier d'approbation hors dépôt) est protégé.
    Fermer l'appel direct exigerait un nouveau lanceur re-scellé, décision à prendre
    séparément. L'indépendance de l'approbation n'est pas prouvée par le dépôt : elle
    dépend de la configuration de l'hôte (fichier hors dépôt, non inscriptible par le candidat).
    """
    source = LAUNCHER.read_text(encoding="utf-8")
    module = ast.parse(source)
    expected = ast.parse(
        'if __name__ == "__main__":\n'
        '    raise SystemExit(main())\n'
    ).body[0]
    assert ast.dump(module.body[-1]) == ast.dump(expected)
    assert OPTION not in source
    assert "run_circuit2_anchored" not in source


IMPORT_SNIPPET = """
import sys
sys.path.insert(0, sys.argv[1])
import run_circuit2_anchored
sys.exit(3 if "run_circuit2_campaign" in sys.modules else 0)
"""
WRAPPER = """
import runpy
import sys
from pathlib import Path
script, flag = sys.argv[1], sys.argv[2]
sys.argv = [script, *sys.argv[3:]]
try:
    runpy.run_path(script, run_name="__main__")
finally:
    imported = "run_circuit2_campaign" in sys.modules
    Path(flag).write_text("importe" if imported else "non importe", encoding="utf-8")
"""


def test_the_anchored_script_has_no_module_level_import_of_the_campaign():
    """Le module de campagne est importé par importlib dans main, après les contrôles, jamais au niveau du module."""
    module = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = []
    for node in module.body:
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert "run_circuit2_campaign" not in names


def test_importing_the_anchored_script_does_not_import_the_campaign(tmp_path):
    command = [sys.executable, "-I", "-B", "-c", IMPORT_SNIPPET, str(SCRIPT.parent)]
    done = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout == ""


def _launch(entry, tmp_path, tmp_path_factory, approvals):
    """Lance le vrai script en processus séparé (python -I), directement ou via un wrapper qui note l'import."""
    helper = tmp_path_factory.mktemp("helper")
    flag = helper / "modules.txt"
    wrapper = helper / "wrapper.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != ENV}
    env[ENV] = str(approvals)
    tail = ["--seeds", "0", "--generations", "1", "--out", str(tmp_path / "OUT.json")]
    if entry == "direct":
        command = [sys.executable, "-I", "-B", str(SCRIPT), *tail]
    else:
        command = [sys.executable, "-I", "-B", str(wrapper), str(SCRIPT), str(flag), *tail]
    done = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=120, env=env)
    return done, flag


@pytest.mark.parametrize("entry", ["direct", "wrapper"])
def test_the_real_script_refuses_a_wrong_approval_before_importing_the_campaign(entry, tmp_path, tmp_path_factory):
    """Fixture synthétique : empreintes volontairement fausses ; aucune campagne ne peut démarrer."""
    wrong = {KEY: "0" * 64, LAUNCHER_KEY: "0" * 64, VERIFIER_KEY: "0" * 64, SEAL_PATH_KEY: str(Path(campaign.SEAL_PATH))}
    approvals = _host_file(tmp_path_factory, json.dumps(wrong))
    done, flag = _launch(entry, tmp_path, tmp_path_factory, approvals)
    assert done.returncode == 2, done.stderr
    assert done.stdout == ""
    assert "ne correspond pas" in done.stderr
    assert list(tmp_path.iterdir()) == []
    if entry == "wrapper":
        assert flag.read_text(encoding="utf-8") == "non importe"


def test_the_wrapper_flag_detects_an_import(tmp_path_factory):
    """Témoin de contrôle : le wrapper signale un import de run_circuit2_campaign (module factice, aucune campagne)."""
    helper = tmp_path_factory.mktemp("control")
    script = helper / "importer.py"
    script.write_text("import sys\nsys.modules['run_circuit2_campaign'] = sys\n", encoding="utf-8")
    wrapper = helper / "wrapper.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    flag = helper / "modules.txt"
    done = subprocess.run([sys.executable, "-I", "-B", str(wrapper), str(script), str(flag)], cwd=helper, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert flag.read_text(encoding="utf-8") == "importe"
