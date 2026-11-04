"""Tests des comptages descriptifs circuit2 (données synthétiques uniquement).

Aucune valeur de résultat réel n'est figée ici. Les valeurs issues du run réel
seront figées dans le test de contrôle séparé, avec ce principe : un résultat
constant est un résultat négatif conservé, pas une anomalie à corriger.
"""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "circuit2_full_descriptive_counts.py"
)
spec = importlib.util.spec_from_file_location("circuit2_full_descriptive_counts", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def gen(index, score, digest):
    return {"index": index, "score": list(score), "transmission": {"digest": digest}, "spend": 0}


def entry(seed, gens):
    return {"seed": seed, "generations": gens}


def synthetic():
    return {
        "arms": {
            "inherited_lineage": [
                entry(0, [gen(0, (1, 2), "a"), gen(1, (1, 2), "a"), gen(2, (3, 4), "b")]),
                entry(1, [gen(0, (1, 2), "a"), gen(1, (1, 2), "a"), gen(2, (1, 2), "a")]),
                entry(2, [gen(2, (1, 2), "c"), gen(0, (1, 2), "a"), gen(1, (3, 4), "b")]),
            ],
            "frozen_engine": [entry(0, [gen(0, (0, 0), "x"), gen(1, (0, 0), "x")])],
            "fixed_procedure": [entry(0, [gen(0, (5, 5), "p"), gen(1, (6, 5), "q")])],
            "random_procedure": [
                entry(0, [gen(0, (7, 7), "r")]),
                entry(1, [gen(0, (7, 7), "r")]),
            ],
        }
    }


def arm(n, last, changes, hist, scores):
    return {
        "n_seeds": n,
        "seeds_last_differs_from_gen0": last,
        "seeds_score_changes_at_least_once": changes,
        "distinct_transmission_digests_per_seed_histogram": hist,
        "distinct_scores": scores,
    }


EXPECTED = {
    "arms": {
        "inherited_lineage": arm(3, 1, 2, {"1": 1, "2": 1, "3": 1}, [[1, 2], [3, 4]]),
        "frozen_engine": arm(1, 0, 0, {"1": 1}, [[0, 0]]),
        "fixed_procedure": arm(1, 1, 1, {"2": 1}, [[5, 5], [6, 5]]),
        "random_procedure": arm(2, 0, 0, {"1": 2}, [[7, 7]]),
    }
}


def write_input(tmp_path):
    path = tmp_path / "full.json"
    path.write_text(json.dumps(synthetic()), encoding="utf-8")
    return path


def test_exact_counts(tmp_path):
    out = tmp_path / "counts.json"
    result = mod.run(write_input(tmp_path), out)
    assert result == EXPECTED
    assert json.loads(out.read_text(encoding="utf-8")) == EXPECTED


def test_refuses_overwrite(tmp_path):
    out = tmp_path / "counts.json"
    out.write_text("existant", encoding="utf-8")
    with pytest.raises(FileExistsError):
        mod.run(write_input(tmp_path), out)
    assert out.read_text(encoding="utf-8") == "existant"


def test_deterministic_sorted_output(tmp_path):
    src = write_input(tmp_path)
    out1 = tmp_path / "c1.json"
    out2 = tmp_path / "c2.json"
    mod.run(src, out1)
    mod.run(src, out2)
    assert out1.read_bytes() == out2.read_bytes()
    expected_text = json.dumps(EXPECTED, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert out1.read_text(encoding="utf-8") == expected_text


def test_missing_input_fails_explicitly(tmp_path):
    out = tmp_path / "counts.json"
    with pytest.raises(FileNotFoundError):
        mod.run(tmp_path / "absent.json", out)
    assert not out.exists()
    assert mod.main(["--input", str(tmp_path / "absent.json"), "--output", str(out)]) == 1
    assert not out.exists()


def test_missing_arm_fails(tmp_path):
    src = tmp_path / "partial.json"
    src.write_text(json.dumps({"arms": {"frozen_engine": []}}), encoding="utf-8")
    out = tmp_path / "counts.json"
    with pytest.raises(KeyError):
        mod.run(src, out)
    assert not out.exists()
