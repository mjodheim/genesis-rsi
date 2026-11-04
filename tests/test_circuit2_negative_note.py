"""Tests hors réseau de scripts/circuit2_negative_note.py."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "circuit2_negative_note.py"
NOTE = ROOT / "docs" / "CIRCUIT2_RESULTAT_NUL_2026-11-04.md"
SOURCE = ROOT / "results" / "circuit2_adjudication_full.json"
FORBIDDEN = ("amélioration démontrée", "succès")
YIELD_LINE = "- held_out_yield (ordre du fichier, null si absent) : "

_spec = importlib.util.spec_from_file_location("circuit2_negative_note", SCRIPT)
note = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(note)


def _data(yields_by_arm=None, **meta):
    yields_by_arm = yields_by_arm or {}
    rows = []
    for arm in ("A", "B", "C", "D"):
        values = yields_by_arm.get(arm, [0, 0, 0])
        for index, value in enumerate(values):
            fingerprint = "abcdef0123456789" if index < 2 else "1234567890abcdef"
            rows.append(
                {
                    "arm": arm,
                    "held_out_yield": value,
                    "stop_reason": "budget" if index % 2 == 0 else "converged",
                    "library_fingerprint": fingerprint,
                }
            )
    return {"rows": rows, **meta}


def _check_policy(text):
    lowered = text.lower()
    assert "résultat négatif" in lowered
    assert "non vérifié" in lowered
    for word in FORBIDDEN:
        assert word not in lowered


def test_render_all_zero_counts():
    text = note.render(_data())
    assert text.count("- Nombre de lignes : 3") == 4
    assert text.count(YIELD_LINE + "[0, 0, 0]") == 4
    assert text.count("- stop_reason (ensemble) : budget, converged") == 4
    assert text.count("distinctes : 2 (préfixes : 12345678, abcdef01)") == 4
    for arm in "ABCD":
        assert f"### Bras {arm}" in text
    assert "Aucun gain" in text
    assert "scale : absent du fichier" in text
    assert "machinery_commit : absent du fichier" in text
    _check_policy(text)


def test_render_nonzero_value_without_conclusion():
    text = note.render(_data({"B": [0, 0.25, 0]}, scale="full", task_budget=7))
    assert "Aucun gain" not in text
    assert "- Bras B : valeurs non nulles [0.25]" in text
    assert YIELD_LINE + "[0, 0.25, 0]" in text
    assert 'scale : "full"' in text
    assert "task_budget : 7" in text
    assert "plan_digest : absent du fichier" in text
    _check_policy(text)


def _write_input(tmp_path):
    src = tmp_path / "entree.json"
    src.write_text(json.dumps(_data()), encoding="utf-8")
    return src


def test_run_refuses_overwrite(tmp_path):
    src = _write_input(tmp_path)
    dst = tmp_path / "sortie.md"
    dst.write_text("existant", encoding="utf-8")
    with pytest.raises(FileExistsError):
        note.run(src, dst)
    assert dst.read_text(encoding="utf-8") == "existant"


def test_output_is_deterministic(tmp_path):
    src = _write_input(tmp_path)
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    note.run(src, first)
    note.run(src, second)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == note.render(_data()).encode("utf-8")


def test_missing_input_raises_and_writes_nothing(tmp_path):
    dst = tmp_path / "sous_dossier" / "sortie.md"
    with pytest.raises(FileNotFoundError, match="absent"):
        note.run(tmp_path / "inexistant.json", dst)
    assert not dst.exists()
    assert not dst.parent.exists()


@pytest.mark.skipif(
    not NOTE.exists(),
    reason="note non générée : elle sera produite ensuite par l'action run, puis comparée ici à render(JSON committé)",
)
def test_committed_note_matches_render():
    expected = note.render(json.loads(SOURCE.read_text(encoding="utf-8"))).encode("utf-8")
    assert NOTE.read_bytes() == expected
