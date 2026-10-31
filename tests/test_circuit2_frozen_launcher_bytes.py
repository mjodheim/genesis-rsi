"""Authentification des octets extraits du lanceur gelé du Circuit 2.

Hors réseau, sans modèle. Le test lit en octets le manifeste
EXECUTABLES.json, prend files['scripts/run_circuit2_campaign.py'] comme
référence et exige que le sha256 des octets de
results/circuit2_launcher_frozen_9fbd0c46.py lui soit égal.

Un échec est un résultat négatif conservé tel quel : aucune restauration.
Le sceau LAUNCHER_SEAL.json est seulement vérifié, sans l'imposer à scripts/.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROZEN_PATH = ROOT / "results" / "circuit2_launcher_frozen_9fbd0c46.py"
MANIFEST_PATH = ROOT / "experiment" / "engine" / "CIRCUIT2" / "EXECUTABLES.json"
LAUNCHER_KEY = "scripts/run_circuit2_campaign.py"
SEAL_LAUNCHER_SHA256 = "62ee8b290d70e03ea5654a2512b21bb1b69f36bdd9f422f29c1c6aa9f5d96f3d"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reference_frozen_sha256() -> str:
    manifest = json.loads(MANIFEST_PATH.read_bytes())
    entry = manifest["files"][LAUNCHER_KEY]
    if isinstance(entry, dict):
        entry = entry["sha256"]
    return entry


def _find_seal() -> Path:
    candidate = MANIFEST_PATH.parent / "LAUNCHER_SEAL.json"
    if candidate.is_file():
        return candidate
    found = sorted(p for p in ROOT.rglob("LAUNCHER_SEAL.json") if ".git" not in p.parts)
    assert found, "LAUNCHER_SEAL.json introuvable"
    return found[0]


def test_frozen_launcher_bytes_match_frozen_fingerprint():
    data = FROZEN_PATH.read_bytes()
    assert _sha256(data) == _reference_frozen_sha256(), (
        "les octets extraits ne portent pas l'empreinte gelée du manifeste"
    )


def test_seal_still_records_sealed_launcher_fingerprint():
    seal = json.loads(_find_seal().read_bytes())
    assert seal["launcher_sha256"] == SEAL_LAUNCHER_SHA256
