"""Tests de scripts/shard_circuit2_result.py.

TOUTES les données ci-dessous sont SYNTHÉTIQUES : ce ne sont pas des résultats de
CIRCUIT2, elles servent uniquement à tester le découpage et le réassemblage.
Aucun fichier réel de results/ n'est lu ni écrit ; tout se passe sous tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_circuit2_result.py"
_spec = importlib.util.spec_from_file_location("shard_circuit2_result", _SCRIPT)
shard = importlib.util.module_from_spec(_spec)
sys.modules["shard_circuit2_result"] = shard
_spec.loader.exec_module(shard)

REFUS = (shard.ShardError, FileExistsError)
ARMS = ("SYNTHETIC_ARM_A", "SYNTHETIC_ARM_B")


def synthetic_object(runs_per_arm=12, arms=ARMS):
    """Objet SYNTHÉTIQUE imitant la structure (pas les valeurs) du résultat."""
    return {
        "plan_digest": "SYNTHETIC-plan-digest",
        "machinery_commit": "SYNTHETIC-commit",
        "seeds": list(range(runs_per_arm)),
        "generations": 3,
        "scale": "SYNTHETIC-scale",
        "arms": {
            arm: [
                {
                    "synthetic": True,
                    "seed": s,
                    "payload": "synthétique é",
                    "filler": 0.1 * s,
                    "nested": {"k": [1, 2, {"z": None}]},
                }
                for s in range(runs_per_arm)
            ]
            for arm in arms
        },
    }


def write_source(path, obj):
    data = (json.dumps(obj, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return data


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    source = root / "synthetic_source.json"
    raw = write_source(source, synthetic_object())
    return tmp_path, root, source, raw


def do_split(env, name="shards", **kwargs):
    _, root, source, _ = env
    return shard.split(source, root / name, results_root=root, **kwargs)


def edit_manifest(path, change):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    change(manifest)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def read_manifest(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_reconstruction_identique_octet_pour_octet(env):
    _, _, source, raw = env
    mtime = source.stat().st_mtime_ns
    manifest_path = do_split(env)
    assert shard.reassemble(manifest_path) == raw
    manifest = read_manifest(manifest_path)
    assert manifest["source_sha256"] == shard._sha256(raw)
    assert manifest["fragment_count"] == 6
    assert source.read_bytes() == raw
    assert source.stat().st_mtime_ns == mtime


def test_fragments_en_tete_commun_bras_et_plage(env):
    manifest_path = do_split(env)
    manifest = read_manifest(manifest_path)
    ranges = [e["seed_index_range"] for e in manifest["fragments"] if e["arm"] == ARMS[0]]
    assert ranges == [[0, 5], [5, 10], [10, 12]]
    first = manifest["fragments"][0]
    text = (manifest_path.parent / first["file"]).read_text(encoding="utf-8")
    assert text.startswith('{\n  "plan_digest": "SYNTHETIC-plan-digest",')
    assert text.endswith("}\n")
    fragment = json.loads(text)
    assert fragment["arm"] == ARMS[0]
    assert fragment["seed_index_range"] == [0, 5]
    assert [r["seed"] for r in fragment["runs"]] == [0, 1, 2, 3, 4]
    for key in ("plan_digest", "machinery_commit", "seeds", "generations", "scale"):
        assert key in fragment
    assert manifest["reassembly_order"] == [e["file"] for e in manifest["fragments"]]


def test_taille_de_groupe_parametrable(env):
    manifest_path = do_split(env, seeds_per_shard=4)
    manifest = read_manifest(manifest_path)
    ranges = [e["seed_index_range"] for e in manifest["fragments"] if e["arm"] == ARMS[1]]
    assert ranges == [[0, 4], [4, 8], [8, 12]]
    assert shard.reassemble(manifest_path) == env[3]


def test_parametres_invalides_refuses(env):
    for bad in (0, -1, True, "5"):
        with pytest.raises(shard.ShardError):
            do_split(env, name="invalide", seeds_per_shard=bad)
    assert not (env[1] / "invalide").exists()


def test_bras_vide_conserve(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    obj = synthetic_object(runs_per_arm=3)
    obj["arms"]["SYNTHETIC_EMPTY"] = []
    source = root / "s.json"
    raw = write_source(source, obj)
    manifest_path = shard.split(source, root / "out", results_root=root)
    assert shard.reassemble(manifest_path) == raw


def test_source_non_canonique_refusee(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    source = root / "s.json"
    source.write_text(json.dumps(synthetic_object(3), indent=4) + "\n", encoding="utf-8")
    with pytest.raises(shard.ShardError, match="exactement"):
        shard.split(source, root / "out", results_root=root)
    assert not (root / "out").exists()


def test_fragment_altere_refuse(env):
    manifest_path = do_split(env)
    manifest = read_manifest(manifest_path)
    target = manifest_path.parent / manifest["fragments"][2]["file"]
    original = target.read_bytes()
    target.write_bytes(original.replace(b"SYNTHETIC", b"SYNTHETIX", 1))
    assert len(target.read_bytes()) == len(original)
    with pytest.raises(shard.ShardError, match="empreinte"):
        shard.reassemble(manifest_path)


def test_fragment_tronque_ou_absent_refuse(env):
    manifest_path = do_split(env)
    manifest = read_manifest(manifest_path)
    target = manifest_path.parent / manifest["fragments"][1]["file"]
    target.write_bytes(target.read_bytes()[:-10])
    with pytest.raises(shard.ShardError, match="empreinte"):
        shard.reassemble(manifest_path)
    target.unlink()
    with pytest.raises(shard.ShardError, match="illisible"):
        shard.reassemble(manifest_path)


def test_manifeste_ordre_modifie_refuse(env):
    manifest_path = do_split(env)

    def swap(m):
        f = m["fragments"]
        f[0], f[1] = f[1], f[0]

    edit_manifest(manifest_path, swap)
    with pytest.raises(shard.ShardError, match="ordre"):
        shard.reassemble(manifest_path)


def test_manifeste_ordre_modifie_et_renumerote_refuse(env):
    manifest_path = do_split(env)

    def swap(m):
        f = m["fragments"]
        f[0], f[1] = f[1], f[0]
        for position, entry in enumerate(f):
            entry["order"] = position
        m["reassembly_order"] = [e["file"] for e in f]

    edit_manifest(manifest_path, swap)
    with pytest.raises(shard.ShardError):
        shard.reassemble(manifest_path)


def test_manifeste_nombre_modifie_refuse(env):
    manifest_path = do_split(env)
    edit_manifest(manifest_path, lambda m: m["fragments"].pop())
    with pytest.raises(shard.ShardError, match="nombre"):
        shard.reassemble(manifest_path)


def test_manifeste_fragment_retire_de_facon_coherente_refuse(env):
    manifest_path = do_split(env)

    def drop(m):
        m["fragments"].pop()
        m["fragment_count"] -= 1
        m["reassembly_order"].pop()

    edit_manifest(manifest_path, drop)
    with pytest.raises(shard.ShardError):
        shard.reassemble(manifest_path)


def test_manifeste_nom_de_fragment_hors_dossier_refuse(env):
    manifest_path = do_split(env)

    def evil(m):
        m["fragments"][0]["file"] = "../synthetic_source.json"
        m["reassembly_order"][0] = "../synthetic_source.json"

    edit_manifest(manifest_path, evil)
    with pytest.raises(shard.ShardError, match="nom de fragment"):
        shard.reassemble(manifest_path)


def test_refus_ecrasement(env):
    manifest_path = do_split(env)
    before = {p.name: p.read_bytes() for p in manifest_path.parent.iterdir()}
    with pytest.raises(REFUS):
        do_split(env)
    after = {p.name: p.read_bytes() for p in manifest_path.parent.iterdir()}
    assert before == after


def test_refus_ecrasement_sans_ecriture_partielle(env):
    _, root, _, _ = env
    out = root / "shards"
    out.mkdir()
    (out / shard.MANIFEST_NAME).write_text("existant", encoding="utf-8")
    with pytest.raises(REFUS):
        do_split(env)
    assert [p.name for p in out.iterdir()] == [shard.MANIFEST_NAME]
    assert (out / shard.MANIFEST_NAME).read_text(encoding="utf-8") == "existant"


def test_refus_sortie_hors_results(env):
    tmp_path, root, source, _ = env
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "lien").symlink_to(outside, target_is_directory=True)
    for candidate in (tmp_path / "elsewhere", root / ".." / "escape", root / "lien" / "sub"):
        with pytest.raises(shard.ShardError, match="hors de"):
            shard.split(source, candidate, results_root=root)
    assert not (tmp_path / "elsewhere").exists()
    assert not (tmp_path / "escape").exists()
    assert list(outside.iterdir()) == []


def test_taille_maximale_parametrable(env):
    _, root, _, _ = env
    measured = read_manifest(do_split(env, name="mesure"))
    largest = max(e["bytes"] for e in measured["fragments"])
    ok_path = do_split(env, name="ok", max_fragment_chars=largest)
    for entry in read_manifest(ok_path)["fragments"]:
        text = (ok_path.parent / entry["file"]).read_text(encoding="utf-8")
        assert len(text) <= largest
    with pytest.raises(shard.ShardError, match="trop grand"):
        do_split(env, name="trop_petit", max_fragment_chars=largest - 1)
    assert not (root / "trop_petit").exists()


def test_fragments_sous_la_limite_par_defaut(env):
    manifest = read_manifest(do_split(env))
    assert all(e["bytes"] < shard.DEFAULT_MAX_FRAGMENT_CHARS for e in manifest["fragments"])


def test_cli_split_puis_verify(env, monkeypatch, capsys):
    tmp_path, _, source, raw = env
    monkeypatch.chdir(tmp_path)
    assert shard.main(["split", str(source), "results/cli_shards"]) == 0
    manifest = "results/cli_shards/MANIFEST.json"
    assert shard.main(["verify", manifest]) == 0
    assert "OK" in capsys.readouterr().out
    victim = next((tmp_path / "results" / "cli_shards").glob("0000_*.json"))
    victim.write_bytes(victim.read_bytes() + b" ")
    assert shard.main(["verify", manifest]) == 2
    assert "REFUS" in capsys.readouterr().err
    assert shard.main(["split", str(source), "elsewhere"]) == 2
    assert not (tmp_path / "elsewhere").exists()
    assert source.read_bytes() == raw
