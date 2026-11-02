"""Tests hors réseau de improvement_rate (validation technique seulement).

Enregistrements synthétiques ; valeurs attendues calculées à la main.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import circuit2_improvement_rate as cir  # noqa: E402


def _recs(scores, exhausted=None):
    """Enregistrements SYNTHÉTIQUES : seuls 'score' et 'exhausted'."""
    exhausted = exhausted or [False] * len(scores)
    return [{"score": s, "exhausted": e} for s, e in zip(scores, exhausted)]


def test_increasing_series():
    out = cir.improvement_rate(_recs([[1, -10], [3, -10], [4, -10]]))
    assert out["rate"] == 1.5  # (2 + 1) / 2
    assert out["n_deltas"] == 2
    assert out["n_none"] == 0
    assert out["incomplete"] is False


def test_flat_series():
    out = cir.improvement_rate(_recs([[2, -5], [2, -5], [2, -5]]))
    assert out["rate"] == 0
    assert out["n_deltas"] == 2


def test_decreasing_series():
    out = cir.improvement_rate(_recs([[5, -1], [3, -1], [2, -1]]))
    assert out["rate"] < 0
    assert out["rate"] == -1.5  # (-2 + -1) / 2


def test_none_in_middle_no_pair_crosses():
    records = _recs([[1, -10], None, [3, -8], [6, -5]], [False, True, False, True])
    out = cir.improvement_rate(records)
    assert out["n_none"] == 1
    assert out["skipped_pairs"] == [(0, 1), (1, 2)]
    assert out["incomplete"] is True
    assert out["exhausted_generations"] == [1, 3]
    assert out["n_deltas"] == 1
    assert out["rate"] == 3  # seule la paire (2, 3) : 6 - 3
    assert out["mean_neg_evaluations_delta"] == 3  # -5 - (-8)


@pytest.mark.parametrize("scores", [[None, None, None], [[2, -4]], []])
def test_no_delta(scores):
    out = cir.improvement_rate(_recs(scores))
    assert out["rate"] is None
    assert out["n_deltas"] == 0
    assert out["mean_neg_evaluations_delta"] is None
    assert out["n_none"] == sum(1 for s in scores if s is None)
    assert out["incomplete"] is (None in scores)


def test_neg_evaluations_reported_apart():
    varied = cir.improvement_rate(_recs([[2, -10], [4, -30], [5, -20]]))
    constant = cir.improvement_rate(_recs([[2, -10], [4, -10], [5, -10]]))
    assert varied["rate"] == 1.5 == constant["rate"]  # (2 + 1) / 2
    assert varied["mean_neg_evaluations_delta"] == -5  # (-20 + 10) / 2
    assert constant["mean_neg_evaluations_delta"] == 0


_INVALID = [
    [3],
    ["x"],
    [None],
    [[1, 2]],
    [{"score": [1, 2, 3], "exhausted": False}],
    [{"score": [True, 1], "exhausted": False}],
    [{"score": [1, False], "exhausted": False}],
    [{"score": True, "exhausted": False}],
    [{"score": "ab", "exhausted": False}],
    [{"score": [1, float("nan")], "exhausted": False}],
    [{"exhausted": False}],
    [{"score": [1, -1], "exhausted": False}, 7],
]


@pytest.mark.parametrize("records", _INVALID)
def test_invalid_inputs_raise(records):
    with pytest.raises(ValueError):
        cir.improvement_rate(records)


def test_module_does_not_import_genesis_ast():
    tree = ast.parse((SCRIPTS / "circuit2_improvement_rate.py").read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert names
    assert not [n for n in names if n.split(".")[0] == "genesis"]


def test_module_does_not_load_genesis_in_subprocess():
    snippet = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import circuit2_improvement_rate\n"
        "bad = [m for m in sys.modules if m.split('.')[0] == 'genesis']\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", snippet, str(SCRIPTS)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_result_keys_are_descriptive_only():
    out = cir.improvement_rate([])
    assert set(out) == {
        "rate", "n_deltas", "n_none", "skipped_pairs",
        "exhausted_generations", "incomplete", "mean_neg_evaluations_delta",
    }
