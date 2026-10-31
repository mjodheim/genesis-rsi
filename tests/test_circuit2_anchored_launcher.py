"""Approbation hôte du sceau CIRCUIT2 : hors réseau, fixtures synthétiques (plan factice, coûts 100)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import freeze_circuit2_plan as freeze
import run_circuit2_anchored as anchored
import run_circuit2_campaign as campaign
import seal_circuit2_launcher as sealing

COMMIT = "a" * 40
REAL_SEAL = Path(campaign.SEAL_PATH)
ROOT = Path(__file__).resolve().parents[1]
REAL_SCRIPTS = ROOT / "scripts"
REAL_LAUNCHER = REAL_SCRIPTS / "run_circuit2_campaign.py"
REAL_VERIFIER = REAL_SCRIPTS / "seal_circuit2_launcher.py"
ANCHOR = "--approved-seal-sha256"
ENV = "GENESIS_HOST_APPROVALS"
KEY = "circuit2_launcher_seal_sha256"
LAUNCHER_KEY = "circuit2_launcher_sha256"
VERIFIER_KEY = "circuit2_verifier_sha256"
SEAL_PATH_KEY = "circuit2_launcher_seal_path"


@pytest.fixture(scope="module")
def sealed():
    """Fixture synthétique : plan factice aux coûts de référence 100."""
    return freeze.build_plan(measure=lambda: {str(s): 100 for s in freeze.SEEDS}, machinery_commit=COMMIT)


@pytest.fixture(autouse=True)
def canonical(tmp_path, sealed, monkeypatch):
    path = tmp_path / "CANONICAL.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    monkeypatch.setattr(campaign, "CANONICAL_PLAN_PATH", path)
    return path


@pytest.fixture(autouse=True)
def launcher_seal(tmp_path, sealed, monkeypatch):
    """Fixture synthétique : sceau valide écrit dans tmp_path pour le vrai lanceur et le plan factice."""
    path = tmp_path / "LAUNCHER_SEAL.json"
    path.write_text(json.dumps(sealing.build_seal(sealed["digest"])), encoding="utf-8")
    monkeypatch.setattr(campaign, "SEAL_PATH", path)
    return path


@pytest.fixture
def calls(monkeypatch):
    """Fixture synthétique : new_run factice, aucune génération réelle ; enregistre les appels."""
    recorded = []

    class _FakeRun:
        def step(self):
            return {"exhausted": False, "digest": "d", "spent": 0, "transmission": {"digest": "d"}}

    def new_run(arm, seed, learn, limit, budget):
        recorded.append((arm, seed))
        return _FakeRun()

    monkeypatch.setattr(campaign, "new_run", new_run)
    return recorded


@pytest.fixture
def plan_path(tmp_path, sealed):
    path = tmp_path / "PLAN.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    return path


def _approved(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _args(plan):
    return ["--plan", str(plan), "--seeds", "0", "--generations", "1"]


def _write_approval(path, content, mode=0o600):
    """Fixture synthétique : écrit un fichier d'approbation hôte au format JSON attendu."""
    path.write_text(json.dumps(content), encoding="utf-8")
    os.chmod(path, mode)
    return path


def _content(launcher, verifier, seal, seal_path):
    """Fixture synthétique : contenu d'approbation hôte calculé sur les octets des fichiers donnés."""
    return {
        KEY: _approved(seal),
        LAUNCHER_KEY: _approved(launcher),
        VERIFIER_KEY: _approved(verifier),
        SEAL_PATH_KEY: str(seal_path),
    }


@pytest.fixture
def host_approval(tmp_path, launcher_seal, monkeypatch):
    """Fixture synthétique : approbation hôte hors dépôt (tmp_path), mode 0o600, empreintes des fichiers courants.

    Le propriétaire réel est le processus de test ; _current_uid est simulé pour que le fichier
    soit vu comme appartenant à un autre uid. La règle de propriété n'est exercée pour de bon
    qu'en processus séparé. La chaîne des répertoires de tmp_path (même propriétaire réel) est
    vue comme appartenant à un autre uid par la même simulation ; les règles d'inscriptibilité
    des répertoires ne sont pas assouplies.
    """
    path = _write_approval(tmp_path / "host_approvals.json", _content(REAL_LAUNCHER, REAL_VERIFIER, launcher_seal, launcher_seal))
    assert not path.resolve().is_relative_to(anchored.REPO_ROOT.resolve())
    monkeypatch.setattr(anchored, "_current_uid", lambda: os.geteuid() + 1)
    monkeypatch.setenv(ENV, str(path))
    return path


REAL_LOAD_VERIFIED = anchored._load_verified


@pytest.fixture(autouse=True)
def inprocess_modules(monkeypatch):
    """Fixture synthétique : les tests en processus réutilisent les modules déjà importés (patchés par les fixtures).

    Le chargement réel par octets est exercé par les tests de cache et par les tests en processus séparé.
    """
    known = {anchored.LAUNCHER_MODULE: campaign, anchored.VERIFIER_MODULE: sealing}
    monkeypatch.setattr(anchored, "_load_verified", lambda name, path, source: known[name])


def test_accepts_the_approved_seal(plan_path, tmp_path, sealed, launcher_seal, host_approval, calls):
    approved = _approved(launcher_seal)
    out = tmp_path / "OUT.json"
    argv = [*_args(plan_path), "--out", str(out)]
    assert anchored.main(argv) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["approved_seal_sha256"] == approved
    assert written["host_approval_file"] == str(host_approval.resolve())
    assert written["command"] == argv
    assert written["launcher_provenance"]["plan_digest"] == sealed["digest"]
    assert calls


def _refused(plan_path, tmp_path, calls, capsys, extra=(), fragment=None):
    """Refus : code 2, aucune sortie standard, aucun fichier --out, aucune génération."""
    out = tmp_path / "OUT.json"
    assert anchored.main([*_args(plan_path), "--out", str(out), *extra]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    if fragment is not None:
        assert fragment in captured.err
    assert not out.exists()
    assert calls == []


def _verified_tree(tmp_path, host_approval, monkeypatch):
    """Fixture synthétique : copie de scripts/ (lanceur et vérificateur intacts) avec le sceau réel copié et une approbation hôte sur cette copie.

    SCRIPTS_DIR pointe sur la copie ; le chargement réel par octets est rétabli. Retourne le dossier scripts
    de la copie et l'approbation validée par load_host_approval puis check_approved.
    """
    tree = tmp_path / "verified_tree"
    shutil.copytree(REAL_SCRIPTS, tree / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    seal = tree / REAL_SEAL.resolve().relative_to(ROOT)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_bytes(REAL_SEAL.read_bytes())
    scripts = tree / "scripts"
    _write_approval(host_approval, _content(scripts / "run_circuit2_campaign.py", scripts / "seal_circuit2_launcher.py", seal, seal))
    monkeypatch.setattr(anchored, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(anchored, "_load_verified", REAL_LOAD_VERIFIED)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "run_circuit2_campaign", raising=False)
    monkeypatch.delitem(sys.modules, "seal_circuit2_launcher", raising=False)
    approval = anchored.load_host_approval()
    anchored.check_approved(approval)
    return scripts, approval


def _plant_cache(scripts, witness, tmp_path):
    """Fixture synthétique : .pyc malveillant (UNCHECKED_HASH) du lanceur et du vérificateur ; son code crée le fichier témoin."""
    source = tmp_path / "malicious_source.py"
    source.write_text("from pathlib import Path\nPath(" + repr(str(witness)) + ").write_text('execute', encoding='utf-8')\n", encoding="utf-8")
    for name in ("run_circuit2_campaign.py", "seal_circuit2_launcher.py"):
        target = scripts / name
        cache = Path(importlib.util.cache_from_source(str(target)))
        cache.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(str(source), cfile=str(cache), dfile=str(target), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        assert cache.is_file()


def test_a_malicious_bytecode_cache_is_never_executed(tmp_path, host_approval, monkeypatch):
    """Régression : un .pyc UNCHECKED_HASH planté dans __pycache__ n'est pas exécuté ; le module vient des octets hachés."""
    witness = tmp_path / "CACHE_WITNESS.txt"
    scripts, approval = _verified_tree(tmp_path, host_approval, monkeypatch)
    _plant_cache(scripts, witness, tmp_path)
    module = anchored._import_campaign(approval)
    assert not witness.exists()
    assert sys.dont_write_bytecode is True
    assert Path(module.__file__) == scripts / "run_circuit2_campaign.py"
    assert approval["launcher_source"] == (scripts / "run_circuit2_campaign.py").read_bytes()
    assert callable(module.main)
    assert sys.modules["run_circuit2_campaign"] is module
    verifier = sys.modules["seal_circuit2_launcher"]
    assert Path(verifier.__file__) == scripts / "seal_circuit2_launcher.py"
    assert callable(verifier.build_seal)


def test_without_a_cache_the_verified_modules_load(tmp_path, host_approval, monkeypatch):
    """Témoin positif : sans __pycache__ planté, le chargement par octets fonctionne."""
    scripts, approval = _verified_tree(tmp_path, host_approval, monkeypatch)
    assert not list(scripts.rglob("*.pyc"))
    module = anchored._import_campaign(approval)
    assert Path(module.__file__) == scripts / "run_circuit2_campaign.py"
    assert callable(module.main)
    assert not list(scripts.rglob("*.pyc"))


@pytest.mark.parametrize("mode", [0o777, 0o770])
def test_refusal_when_the_approval_is_in_a_replaceable_directory(mode, host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    imported = []
    monkeypatch.setattr(anchored, "_import_campaign", lambda approval: imported.append(approval))
    parent = tmp_path / "replaceable"
    parent.mkdir()
    moved = parent / "host_approvals.json"
    shutil.copy2(host_approval, moved)
    os.chmod(parent, mode)
    monkeypatch.setenv(ENV, str(moved))
    _refused(plan_path, tmp_path, calls, capsys, fragment="répertoire")
    assert imported == []


def test_refusal_when_a_parent_directory_belongs_to_the_current_uid(host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    owner = host_approval.parent.stat().st_uid
    if owner == 0:
        pytest.skip("répertoire appartenant à root : accepté par la règle (autre uid ou root)")
    imported = []
    real_load = anchored.load_host_approval

    def approval_of_another_uid():
        approval = real_load()
        approval["owner"] = owner + 1
        return approval

    monkeypatch.setattr(anchored, "load_host_approval", approval_of_another_uid)
    monkeypatch.setattr(anchored, "_current_uid", lambda: owner)
    monkeypatch.setattr(anchored, "_import_campaign", lambda approval: imported.append(approval))
    _refused(plan_path, tmp_path, calls, capsys, fragment="propriétaire du répertoire")
    assert imported == []


def test_refusal_without_the_environment_variable(host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    monkeypatch.delenv(ENV)
    _refused(plan_path, tmp_path, calls, capsys, fragment=ENV)


def test_refusal_with_a_missing_approval_file(plan_path, tmp_path, calls, capsys, monkeypatch):
    monkeypatch.setenv(ENV, str(tmp_path / "absent.json"))
    _refused(plan_path, tmp_path, calls, capsys, fragment="illisible")


@pytest.mark.parametrize(
    "content",
    ["", "{", "[]", "{}", json.dumps({KEY: 5}), json.dumps({KEY: ""}), json.dumps({KEY: "abc"}), json.dumps({KEY: "F" * 64}), json.dumps({KEY: "g" * 64}), json.dumps({KEY: "0" * 63}), json.dumps({KEY: "f" * 64})],
)
def test_refusal_with_an_invalid_or_different_approval(content, host_approval, plan_path, tmp_path, calls, capsys):
    host_approval.write_text(content, encoding="utf-8")
    _refused(plan_path, tmp_path, calls, capsys)


@pytest.mark.parametrize("mode", [0o620, 0o602, 0o660, 0o606, 0o666])
def test_refusal_when_the_approval_is_writable_by_group_or_others(mode, host_approval, plan_path, tmp_path, calls, capsys):
    os.chmod(host_approval, mode)
    _refused(plan_path, tmp_path, calls, capsys, fragment="inscriptible")


def test_refusal_when_the_approval_is_inside_the_repository(host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    monkeypatch.setattr(anchored, "REPO_ROOT", tmp_path)
    _refused(plan_path, tmp_path, calls, capsys, fragment="dépôt")


def test_refusal_for_a_file_of_the_real_repository(plan_path, tmp_path, calls, capsys, monkeypatch):
    monkeypatch.setenv(ENV, str(Path(__file__).resolve()))
    _refused(plan_path, tmp_path, calls, capsys, fragment="dépôt")


@pytest.mark.parametrize("form", ["separate", "equals"])
def test_command_line_anchor_is_refused_even_with_a_valid_host_approval(form, host_approval, launcher_seal, plan_path, tmp_path, calls, capsys):
    approved = _approved(launcher_seal)
    extra = [ANCHOR, approved] if form == "separate" else [f"{ANCHOR}={approved}"]
    _refused(plan_path, tmp_path, calls, capsys, extra=extra, fragment=ANCHOR)


def test_existing_output_is_refused(plan_path, tmp_path, launcher_seal, host_approval, calls, capsys):
    out = tmp_path / "OUT.json"
    out.write_text("existant", encoding="utf-8")
    argv = [*_args(plan_path), "--out", str(out)]
    assert anchored.main(argv) == 2
    assert out.read_text(encoding="utf-8") == "existant"
    assert capsys.readouterr().out == ""
    assert calls == []


@pytest.mark.parametrize("key", [KEY, LAUNCHER_KEY, VERIFIER_KEY])
def test_refusal_when_one_approved_fingerprint_differs_and_the_campaign_is_not_imported(key, host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    imported = []
    monkeypatch.setattr(anchored, "_import_campaign", lambda approval: imported.append(approval))
    data = json.loads(host_approval.read_text(encoding="utf-8"))
    data[key] = "0" * 64
    host_approval.write_text(json.dumps(data), encoding="utf-8")
    _refused(plan_path, tmp_path, calls, capsys, fragment="ne correspond pas")
    assert imported == []


def test_refusal_when_the_approval_belongs_to_the_current_uid(host_approval, plan_path, tmp_path, calls, capsys, monkeypatch):
    owner = host_approval.stat().st_uid
    if owner == 0:
        pytest.skip("fichier appartenant à root : accepté par la règle (autre uid ou root)")
    imported = []
    monkeypatch.setattr(anchored, "_current_uid", lambda: owner)
    monkeypatch.setattr(anchored, "_import_campaign", lambda approval: imported.append(approval))
    _refused(plan_path, tmp_path, calls, capsys, fragment="propriétaire")
    assert imported == []


def test_refusal_when_the_campaign_module_uses_another_seal(host_approval, launcher_seal, plan_path, tmp_path, calls, capsys):
    other = tmp_path / "OTHER_SEAL.json"
    other.write_bytes(launcher_seal.read_bytes())
    data = json.loads(host_approval.read_text(encoding="utf-8"))
    data[SEAL_PATH_KEY] = str(other)
    host_approval.write_text(json.dumps(data), encoding="utf-8")
    _refused(plan_path, tmp_path, calls, capsys, fragment="autre sceau")


def test_existing_output_is_refused_before_the_campaign_import(host_approval, plan_path, tmp_path, capsys, monkeypatch):
    imported = []
    monkeypatch.setattr(anchored, "_import_campaign", lambda approval: imported.append(approval))
    out = tmp_path / "OUT.json"
    out.write_text("existant", encoding="utf-8")
    assert anchored.main([*_args(plan_path), "--out", str(out)]) == 2
    assert capsys.readouterr().out == ""
    assert imported == []


ENTRIES = ["direct", "wrapper"]
SCENARIOS = {
    "altered_launcher_recomputed_seal": "ne correspond pas",
    "approval_inside_repository": "dépôt",
    "approval_group_writable": "inscriptible",
}
WRAPPER = """
import runpy
import sys
script = sys.argv[1]
sys.argv = [script, *sys.argv[2:]]
runpy.run_path(script, run_name="__main__")
"""
STUB = """

def main(argv=None):
    print('{"launcher_provenance": {}}')
    return 0
"""


def _candidate_tree(base, witness, stub=False):
    """Fixture synthétique : copie du dépôt candidat (scripts, sceau recalculé), lanceur copié avec code témoin.

    Le code ajouté crée le fichier témoin dès l'import du module de campagne ; avec stub, main est
    remplacé pour qu'aucune campagne réelle ne puisse être lancée, même en cas de régression.
    """
    tree = base / "candidate"
    shutil.copytree(REAL_SCRIPTS, tree / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    if (ROOT / "src").is_dir():
        os.symlink(ROOT / "src", tree / "src")
    for package in ("genesis", "mira_core", "metamorphosis"):
        if (ROOT / package).is_dir():
            os.symlink(ROOT / package, tree / package)
    launcher = tree / "scripts" / "run_circuit2_campaign.py"
    added = "\n\n# candidat synthétique (test)\nfrom pathlib import Path as _Witness\n\n_Witness(" + repr(str(witness)) + ").write_text('importe', encoding='utf-8')\n"
    launcher.write_bytes(REAL_LAUNCHER.read_bytes() + (added + (STUB if stub else "")).encode("utf-8"))
    seal = tree / REAL_SEAL.resolve().relative_to(ROOT)
    seal.parent.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in json.loads(REAL_SEAL.read_text(encoding="utf-8")).items() if k != "digest"}
    body["launcher_sha256"] = _approved(launcher)
    seal.write_text(json.dumps({**body, "digest": sealing.digest_of(body)}), encoding="utf-8")
    return tree, launcher, seal


def _run(entry, tree, approval, out, tmp_path):
    """Lance le vrai run_circuit2_anchored.py de la copie en processus séparé (python -I), directement ou via un wrapper."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    script = tree / "scripts" / "run_circuit2_anchored.py"
    head = [sys.executable, "-I", str(script)] if entry == "direct" else [sys.executable, "-I", str(wrapper), str(script)]
    env = {k: v for k, v in os.environ.items() if k != ENV}
    env[ENV] = str(approval)
    command = [*head, "--seeds", "0", "--generations", "1", "--out", str(out)]
    return subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=120, env=env)


def _scenario(name, tmp_path, witness):
    """Fixture synthétique : arbre candidat et fichier d'approbation hôte du scénario de refus (main remplacé par un stub)."""
    tree, launcher, seal = _candidate_tree(tmp_path, witness, stub=True)
    verifier = tree / "scripts" / "seal_circuit2_launcher.py"
    host = tmp_path / "host"
    host.mkdir()
    os.chmod(host, 0o755)
    if name == "altered_launcher_recomputed_seal":
        assert _approved(launcher) != _approved(REAL_LAUNCHER)
        assert _approved(seal) != _approved(REAL_SEAL)
        assert json.loads(seal.read_text(encoding="utf-8"))["launcher_sha256"] == _approved(launcher)
        return tree, _write_approval(host / "approvals.json", _content(REAL_LAUNCHER, REAL_VERIFIER, REAL_SEAL, seal))
    content = _content(launcher, verifier, seal, seal)
    if name == "approval_inside_repository":
        return tree, _write_approval(tree / "approvals.json", content)
    return tree, _write_approval(host / "approvals.json", content, 0o660)


def _assert_refused(done, out, witness, fragment):
    assert done.returncode == 2, done.stderr
    assert done.stdout == ""
    assert fragment in done.stderr
    assert not out.exists()
    assert not witness.exists()


def test_the_witness_is_created_when_the_candidate_module_is_imported(tmp_path):
    """Témoin de contrôle : sans approbation, importer la copie du lanceur crée bien le fichier témoin."""
    witness = tmp_path / "WITNESS.txt"
    tree, _, _ = _candidate_tree(tmp_path, witness, stub=True)
    snippet = "import sys\nfor entry in sys.argv[1:]:\n    sys.path.insert(0, entry)\nimport run_circuit2_campaign\n"
    done = subprocess.run([sys.executable, "-I", "-c", snippet, str(tree / "src"), str(tree / "scripts")], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert witness.read_text(encoding="utf-8") == "importe"


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_candidate_scenarios_are_refused_in_a_separate_process_before_the_import(scenario, entry, tmp_path):
    witness = tmp_path / "WITNESS.txt"
    out = tmp_path / "OUT.json"
    tree, approval = _scenario(scenario, tmp_path, witness)
    _assert_refused(_run(entry, tree, approval, out, tmp_path), out, witness, SCENARIOS[scenario])


@pytest.mark.skipif(os.geteuid() == 0, reason="sous root, un fichier créé par le test appartient à root et est accepté par la règle")
@pytest.mark.parametrize("entry", ENTRIES)
def test_a_fake_approval_created_by_the_candidate_is_refused(entry, tmp_path):
    """Même uid que le candidat, mode 0600, hors dépôt, empreintes cohérentes avec la copie : refus par propriétaire."""
    witness = tmp_path / "WITNESS.txt"
    out = tmp_path / "OUT.json"
    tree, launcher, seal = _candidate_tree(tmp_path, witness, stub=True)
    host = tmp_path / "host"
    host.mkdir()
    os.chmod(host, 0o755)
    verifier = tree / "scripts" / "seal_circuit2_launcher.py"
    approval = _write_approval(host / "approvals.json", _content(launcher, verifier, seal, seal))
    assert approval.stat().st_uid == os.geteuid()
    _assert_refused(_run(entry, tree, approval, out, tmp_path), out, witness, "propriétaire")


@pytest.mark.skipif(os.geteuid() != 0, reason="témoin positif : une approbation valide exige un fichier appartenant à root ou à un autre uid")
@pytest.mark.parametrize("entry", ENTRIES)
def test_positive_witness_with_a_valid_approval(entry, tmp_path):
    """Candidat synthétique (main remplacé, aucune campagne réelle) : l'import n'a lieu qu'avec une approbation valide."""
    witness = tmp_path / "WITNESS.txt"
    out = tmp_path / "OUT.json"
    tree, launcher, seal = _candidate_tree(tmp_path, witness, stub=True)
    host = tmp_path / "host"
    host.mkdir()
    verifier = tree / "scripts" / "seal_circuit2_launcher.py"
    approval = _write_approval(host / "approvals.json", _content(launcher, verifier, seal, seal))
    assert approval.stat().st_uid == 0
    done = _run(entry, tree, approval, out, tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
    assert witness.read_text(encoding="utf-8") == "importe"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["host_approval_file"] == str(approval.resolve())
    assert written["approved_seal_sha256"] == _approved(seal)


def test_canonical_launcher_matches_the_versioned_seal():
    seal = json.loads(REAL_SEAL.read_text(encoding="utf-8"))
    body = {k: v for k, v in seal.items() if k != "digest"}
    assert seal["digest"] == sealing.digest_of(body)
    assert seal["launcher_sha256"] == sealing.file_sha256(campaign.LAUNCHER_FILE)
    assert seal["verifier_sha256"] == sealing.file_sha256(Path(sealing.__file__))


@pytest.fixture
def received(monkeypatch):
    """Fixture synthétique : campaign.main factice, enregistre son argv et imprime un JSON valide."""
    argvs = []

    def fake_main(argv=None):
        argvs.append(list(argv))
        print(json.dumps({"launcher_provenance": {}}))
        return 0

    monkeypatch.setattr(campaign, "main", fake_main)
    return argvs


def test_campaign_receives_no_anchor_and_seal_is_untouched(received, plan_path, tmp_path, launcher_seal, host_approval):
    approved = _approved(launcher_seal)
    before = _approved(campaign.SEAL_PATH)
    out = tmp_path / "OUT.json"
    assert anchored.main([*_args(plan_path), "--out", str(out)]) == 0
    assert received == [_args(plan_path)]
    assert ANCHOR not in received[0] and approved not in received[0]
    for flag in ("--plan", "--seeds", "--generations"):
        assert flag in received[0]
    assert _approved(campaign.SEAL_PATH) == before == approved
    assert json.loads(out.read_text(encoding="utf-8"))["approved_seal_sha256"] == approved


def test_received_argv_does_not_depend_on_the_option_order(received, plan_path, tmp_path, host_approval):
    base = _args(plan_path)
    assert anchored.main([*base, "--out", str(tmp_path / "A.json")]) == 0
    assert anchored.main(["--out", str(tmp_path / "B.json"), *base]) == 0
    assert campaign.main(base) == 0
    assert received[0] == received[1] == received[2] == base
