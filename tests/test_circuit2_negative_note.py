"""Tests hors réseau de scripts/circuit2_negative_note.py."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "circuit2_negative_note.py"
NOTE = ROOT / "docs" / "CIRCUIT2_RESULTAT_NUL_2026-11-04.md"
SOURCE = ROOT / "results" / "circuit2_adjudication_full.json"
PLAN = ROOT / "experiment" / "engine" / "CIRCUIT2" / "PROCEDURE_PREREG_PLAN.json"
PROVENANCE = ROOT / "results" / "circuit2_provenance.json"
FORBIDDEN = ("amélioration démontrée", "succès")
YIELD_LINE = "- held_out_yield (ordre du fichier, null si absent) : "
ARMS = ("A", "B", "C", "D")
SEEDS = [0, 1, 2]

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
                    "seed": SEEDS[index],
                    "generations": 2,
                    "held_out_yield": value,
                    "stop_reason": "budget" if index % 2 == 0 else "converged",
                    "library_fingerprint": fingerprint,
                }
            )
    base = {
        "plan_digest": "d" * 64,
        "seeds": list(SEEDS),
        "task_budget": 7,
        "per_generation_limit": 5,
    }
    return {"rows": rows, **{**base, **meta}}


def _plan():
    return {
        "digest": "d" * 64,
        "seeds": list(SEEDS),
        "arms": [{"name": arm} for arm in ARMS],
        "budgets": {"task_budget": 7, "generations": 2, "per_generation_limit": 5},
        "machinery_commit": "m" * 40,
        "criterion": {
            "thresholds": {"min_points": 11, "min_seeds": 3},
            "text": "Texte de critère synthétique du plan.",
        },
    }


def _prov():
    return {
        "files": {
            "results/circuit2_campaign_full.json": {
                "resolved_commit": "aaaaaaaa" + "0" * 32,
                "verdict": "verdict-campagne",
            },
            "results/circuit2_adjudication_s0-1_g6.json": {
                "resolved_commit": "bbbbbbbb" + "0" * 32,
                "verdict": "verdict-pilote",
            },
        }
    }


def _check_policy(text):
    lowered = text.lower()
    assert "résultat négatif" in lowered
    assert "non vérifié" in lowered
    for word in FORBIDDEN:
        assert word not in lowered


def test_render_all_zero_counts():
    text = note.render(_data(), _plan(), _prov())
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
    text = note.render(_data({"B": [0, 0.25, 0]}, scale="full", task_budget=7), _plan(), _prov())
    assert "Aucun gain" not in text
    assert "- Bras B : valeurs non nulles [0.25]" in text
    assert YIELD_LINE + "[0, 0.25, 0]" in text
    assert 'scale : "full"' in text
    assert "task_budget : 7" in text
    assert 'plan_digest : "' + "d" * 64 + '"' in text
    _check_policy(text)


def _write_input(tmp_path, data=None, plan=None):
    src = tmp_path / "entree.json"
    src.write_text(json.dumps(_data() if data is None else data), encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_plan() if plan is None else plan), encoding="utf-8")
    prov_file = tmp_path / "provenance.json"
    prov_file.write_text(json.dumps(_prov()), encoding="utf-8")
    return src, plan_file, prov_file


def test_run_refuses_overwrite(tmp_path):
    src, plan_file, prov_file = _write_input(tmp_path)
    dst = tmp_path / "sortie.md"
    dst.write_text("existant", encoding="utf-8")
    with pytest.raises(FileExistsError):
        note.run(src, dst, plan_file, prov_file)
    assert dst.read_text(encoding="utf-8") == "existant"


def test_output_is_deterministic(tmp_path):
    src, plan_file, prov_file = _write_input(tmp_path)
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    note.run(src, first, plan_file, prov_file)
    note.run(src, second, plan_file, prov_file)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == note.render(_data(), _plan(), _prov()).encode("utf-8")


def test_missing_input_raises_and_writes_nothing(tmp_path):
    dst = tmp_path / "sous_dossier" / "sortie.md"
    with pytest.raises(FileNotFoundError, match="absent"):
        note.run(tmp_path / "inexistant.json", dst)
    assert not dst.exists()
    assert not dst.parent.exists()


def _without_arm(data):
    data["rows"] = [row for row in data["rows"] if row["arm"] != "D"]
    return data


def _with_bad_seed(data):
    data["rows"][0]["seed"] = 99
    return data


def _plan_with(**changes):
    plan = _plan()
    plan.update(changes)
    return plan


INCONSISTENT = {
    "digest": (_data(plan_digest="autre"), _plan()),
    "graines du plan": (_data(), _plan_with(seeds=[0, 1, 2, 3])),
    "ensemble de bras": (_without_arm(_data()), _plan()),
    "graines par bras": (_with_bad_seed(_data()), _plan()),
    "generations": (_data(generations=3), _plan()),
    "per_generation_limit": (_data(per_generation_limit=6), _plan()),
}


@pytest.mark.parametrize("data, plan", list(INCONSISTENT.values()), ids=list(INCONSISTENT))
def test_inconsistency_refused_without_output(tmp_path, data, plan):
    src, plan_file, prov_file = _write_input(tmp_path, data, plan)
    dst = tmp_path / "sous_dossier" / "sortie.md"
    with pytest.raises(ValueError):
        note.run(src, dst, plan_file, prov_file)
    assert not dst.exists()
    assert not dst.parent.exists()


@pytest.mark.parametrize(
    "target",
    [
        "task_budget",
        "per_generation_limit",
        "global_generations",
        "local_generations",
        "plan_task_budget",
        "plan_generations",
        "plan_per_generation_limit",
    ],
)
@pytest.mark.parametrize(
    "case",
    ["different", "missing", "true", "false", "float", "string", "null"],
)
def test_required_integer_budgets_refused_without_output(tmp_path, target, case):
    data = _data()
    plan = _plan()
    if target.startswith("plan_"):
        container = plan["budgets"]
        key = target.removeprefix("plan_")
    elif target == "local_generations":
        # Une seule ligne invalide doit être refusée malgré les métadonnées.
        data["generations"] = plan["budgets"]["generations"]
        container = data["rows"][-1]
        key = "generations"
    elif target == "global_generations":
        data["generations"] = plan["budgets"]["generations"]
        container = data
        key = "generations"
    else:
        container = data
        key = target
    expected = plan["budgets"][key]
    if case == "missing":
        if target == "global_generations":
            # Sans métadonnée globale, chaque ligne reste obligatoire.
            for row in data["rows"]:
                del row["generations"]
        del container[key]
    else:
        container[key] = {
            "different": expected + 1,
            "true": True,
            "false": False,
            "float": float(expected),
            "string": str(expected),
            "null": None,
        }[case]
    src, plan_file, prov_file = _write_input(tmp_path, data, plan)
    dst = tmp_path / "sous_dossier" / "sortie.md"
    with pytest.raises(ValueError):
        note.run(src, dst, plan_file, prov_file)
    assert not dst.exists()
    assert not dst.parent.exists()

def test_local_generations_without_global_metadata_accepted():
    data = _data()
    assert "generations" not in data
    note.validate_against_plan(data, _plan())

def test_displayed_threshold_comes_from_plan():
    base = note.render(_data(), _plan(), _prov())
    assert '{"min_points": 11, "min_seeds": 3}' in base
    assert "n'est pas atteint" in base
    changed = _plan()
    changed["criterion"]["thresholds"] = {"min_points": 77, "min_seeds": 5}
    changed["criterion"]["text"] = "Autre texte."
    text = note.render(_data(), changed, _prov())
    assert '{"min_points": 77, "min_seeds": 5}' in text
    assert "Autre texte." in text
    assert '"min_points": 11' not in text
    assert "Texte de critère synthétique du plan." not in text
    assert ">=10 points" not in text
    assert "16 graines" not in text


def test_provenance_section_from_provenance_file():
    text = note.render(_data(), _plan(), _prov())
    campaign = 'commit résolu "aaaaaaaa' + "0" * 32 + '", verdict "verdict-campagne"'
    pilot = 'commit résolu "bbbbbbbb' + "0" * 32 + '", verdict "verdict-pilote"'
    assert campaign in text
    assert pilot in text
    assert "contenu non relu ici" in text
    assert "statut dans la provenance : non vérifié" in text
    assert 'machinery_commit du plan (lu dans le plan) : "' + "m" * 40 + '"' in text
    assert "recalcul du digest : non vérifié" in text
    _check_policy(text)


def test_committed_adjudication_valid_against_frozen_plan():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    note.validate_against_plan(data, plan)


@pytest.mark.skipif(
    not NOTE.exists(),
    reason="note non générée : elle sera produite ensuite par l'action run, puis comparée ici à render(JSON committé)",
)
def test_committed_note_matches_render():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    expected = note.render(data, plan, provenance).encode("utf-8")
    assert NOTE.read_bytes() == expected
