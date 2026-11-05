"""Tests de scripts/derive_compact_json.py (hors réseau, sous tmp_path)."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "derive_compact_json.py"
_SPEC = importlib.util.spec_from_file_location("derive_compact_json", _SCRIPT)
dcj = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dcj)

# Valeur factice réservée aux tests ; ce n'est le hash d'aucun vrai commit.
COMMIT = "0123456789abcdef0123456789abcdef01234567"
DATA = {"b": 1, "a": {"d": [1, 2.5, True, None], "c": "é"}}


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "results"
    path.mkdir()
    return path


def derive(root, raw, name="a", commit=COMMIT, compact=None, manifest=None):
    source = root.parent / f"source_{name}.json"
    source.write_bytes(raw)
    return dcj.derive(
        source,
        compact or root / f"{name}.compact.json",
        manifest or root / f"{name}.manifest.json",
        "owner/repo",
        commit,
        "results/original.json",
        results_root=root,
    )


def test_cles_dupliquees_refusees(root):
    for raw in (b'{"a":1,"a":2}', b'{"x":{"b":1,"b":1}}', b'[{"k":1,"k":1}]'):
        with pytest.raises(dcj.DerivationError, match="dupliqu"):
            derive(root, raw)
    assert list(root.iterdir()) == []


def test_json_non_fini_ou_invalide_refuse(root):
    for raw in (b'{"a":NaN}', b'{"a":Infinity}', b"{", b"\xff"):
        with pytest.raises(dcj.DerivationError):
            derive(root, raw)
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    "a, b",
    [
        (1, True),
        (1, 1.0),
        (True, 1.0),
        (0, False),
        (0, 0.0),
        (0.0, -0.0),
        ({"a": 1}, {"a": True}),
        ([1], [1.0]),
        ({"a": [1, {"b": 0}]}, {"a": [1, {"b": False}]}),
        ({"a": 1}, {"a": 1, "b": 2}),
    ],
)
def test_difference_de_type_detectee(a, b):
    assert not dcj.strict_equal(a, b)
    assert not dcj.strict_equal(b, a)


def test_egalite_stricte_positive():
    value = {"a": [1, 1.0, True, None, "x", {"b": [False]}]}
    assert dcj.strict_equal(value, json.loads(json.dumps(value)))


def test_derive_detecte_une_alteration_de_type(root, monkeypatch):
    monkeypatch.setattr(dcj, "compact_bytes", lambda value: b'{"a":true}\n')
    with pytest.raises(dcj.DerivationError, match="diffère"):
        derive(root, b'{"a":1}')
    assert list(root.iterdir()) == []


def test_sha256_sur_octets_reels_crlf_et_indentation(root):
    lf = json.dumps(DATA, indent=4, ensure_ascii=False).encode("utf-8")
    variants = {
        "lf": lf,
        "crlf": lf.replace(b"\n", b"\r\n"),
        "tab": json.dumps(DATA, indent="\t", ensure_ascii=False).encode("utf-8"),
        "plat": json.dumps(DATA, ensure_ascii=True).encode("utf-8"),
    }
    compacts = set()
    for name, raw in variants.items():
        manifest = derive(root, raw, name=name)
        compact_bytes = (root / f"{name}.compact.json").read_bytes()
        on_disk = json.loads((root / f"{name}.manifest.json").read_text("utf-8"))
        assert on_disk == manifest
        assert manifest["sha256_octets_originaux"] == hashlib.sha256(raw).hexdigest()
        assert manifest["sha256_fichier_compact"] == hashlib.sha256(compact_bytes).hexdigest()
        assert (root.parent / f"source_{name}.json").read_bytes() == raw
        compacts.add(compact_bytes)
    assert len(compacts) == 1
    assert len({hashlib.sha256(v).hexdigest() for v in variants.values()}) == len(variants)


def test_manifeste_champs(root):
    manifest = derive(root, b'{"a":1}', commit=COMMIT.upper())
    assert manifest["depot"] == "owner/repo"
    assert manifest["commit_source"] == COMMIT
    assert manifest["chemin_original"] == "results/original.json"
    assert manifest["mention"] == (
        "dérivé de présentation, aucune preuve expérimentale ajoutée"
    )


def test_sortie_deterministe(root):
    raw = json.dumps(DATA).encode("utf-8")
    derive(root, raw, name="un")
    derive(root, raw, name="deux")
    first = (root / "un.compact.json").read_bytes()
    assert first == (root / "deux.compact.json").read_bytes()
    assert first == '{"a":{"c":"é","d":[1,2.5,true,null]},"b":1}\n'.encode("utf-8")
    assert first.count(b"\n") == 1 and first.endswith(b"\n")


def test_refus_d_ecraser(root):
    derive(root, b'{"a":1}')
    before = (root / "a.compact.json").read_bytes()
    with pytest.raises(dcj.DerivationError, match="écraser"):
        derive(root, b'{"a":2}')
    assert (root / "a.compact.json").read_bytes() == before


def test_refus_si_le_manifeste_existe_deja(root):
    (root / "a.manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(dcj.DerivationError, match="écraser"):
        derive(root, b'{"a":1}')
    assert not (root / "a.compact.json").exists()


def test_refus_hors_de_results(root, tmp_path):
    autre = tmp_path / "autre"
    autre.mkdir()
    cas = [
        {"compact": autre / "c.json"},
        {"manifest": autre / "m.json"},
        {"compact": root / ".." / "c.json"},
        {"manifest": root / ".." / "m.json"},
    ]
    for kwargs in cas:
        with pytest.raises(dcj.DerivationError, match="hors de"):
            derive(root, b'{"a":1}', **kwargs)
    assert list(autre.iterdir()) == []
    assert list(root.iterdir()) == []
    assert not (tmp_path / "c.json").exists()
    assert not (tmp_path / "m.json").exists()


@pytest.mark.parametrize(
    "commit",
    ["", "abc", "0" * 39, "0" * 41, "g" * 40, COMMIT + "\n", "0x" + "0" * 38],
)
def test_commit_invalide_refuse(root, commit):
    with pytest.raises(dcj.DerivationError, match="commit"):
        derive(root, b'{"a":1}', commit=commit)
    assert list(root.iterdir()) == []


def test_cli(root):
    source = root.parent / "src.json"
    source.write_bytes(b'{"a": 1}\r\n')
    argv = [
        str(source),
        str(root / "c.json"),
        str(root / "m.json"),
        "owner/repo",
        COMMIT,
        "results/original.json",
        "--results-root",
        str(root),
    ]
    assert dcj.main(argv) == 0
    assert (root / "c.json").read_bytes() == b'{"a":1}\n'
    assert dcj.main(argv) == 1


def test_aide_sous_processus(tmp_path):
    resultat = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert resultat.returncode == 0
    assert resultat.stdout.strip()
    assert "usage" in resultat.stdout.lower()
    assert "source" in resultat.stdout.lower()
    assert resultat.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_sans_argument_sous_processus(tmp_path):
    resultat = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert resultat.returncode == 2
    assert resultat.stderr.strip()
    assert list(tmp_path.iterdir()) == []
