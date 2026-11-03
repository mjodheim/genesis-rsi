"""Tests hors réseau de scripts/summarize_circuit2_campaign.py."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "summarize_circuit2_campaign.py"
FULL = ROOT / "results" / "circuit2_campaign_full.json"
FORBIDDEN = ("gain", "success", "succes", "succès", "yield")

_spec = importlib.util.spec_from_file_location("summarize_circuit2_campaign", SCRIPT)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


def _rec(lib, proc, digest, tdigest, tlib=None, tproc=None):
    transmission = {}
    if tdigest is not None:
        transmission["digest"] = tdigest
    if tlib is not None:
        transmission["library_digest"] = tlib
    if tproc is not None:
        transmission["procedure_digest"] = tproc
    record = {"library_digest": lib, "procedure_digest": proc, "transmission": transmission}
    if digest is not None:
        record["digest"] = digest
    return record


def _run(records):
    return {"generations": records, "generations_run": len(records), "stop_reason": "fixture"}


@pytest.fixture
def synthetic_fixture():
    return {
        "arms": {
            "bibliotheque_changeante": {"seeds": {"0": _run([
                _rec("L0", "P0", "d0", "d0"),
                _rec("L0", "P0", "d1", "t1"),
                _rec("L1", "P0", "d2", "d2", tlib="L2", tproc="P0"),
            ])}},
            "bibliotheque_inchangee": {"seeds": {"0": _run([
                _rec("L0", "P0", "d0", "d0"),
                _rec("L0", "P1", "d1", "d1", tlib="L0", tproc="P1"),
            ])}},
            "digest_manquant": {"seeds": {"0": _run([
                _rec("L0", "P0", "d0", None),
                _rec("L0", "P0", "d1", "d1", tlib="L0", tproc="P0"),
            ])}},
        }
    }


def _keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


def test_synthetic_fixture_summary(synthetic_fixture):
    arms = module.summarize(synthetic_fixture)["arms"]
    changing = arms["bibliotheque_changeante"]
    seed = changing["seeds"]["0"]
    assert seed["library_digests"] == ["L0", "L0", "L1", "L2"]
    assert seed["library_changed"] is True
    assert seed["procedure_changed"] is False
    assert seed["adoption"] == [1]
    assert seed["generations_run"] == 3
    assert seed["stop_reason"] == "fixture"
    assert changing["summary"]["seeds_library_changed"] == 1
    assert changing["summary"]["seeds_adoption"] == 1
    static = arms["bibliotheque_inchangee"]["seeds"]["0"]
    assert static["library_changed"] is False
    assert static["procedure_changed"] is True
    assert static["adoption"] == []
    missing = arms["digest_manquant"]
    assert missing["seeds"]["0"]["adoption"] == "non_deductible"
    assert missing["summary"]["seeds_adoption"] == 0
    assert missing["summary"]["seeds_adoption_non_deductible"] == 1


def test_output_refused_outside_results(tmp_path, synthetic_fixture):
    results = tmp_path / "results"
    results.mkdir()
    summary = module.summarize(synthetic_fixture)
    with pytest.raises(ValueError):
        module.write_summary(summary, tmp_path / "autre.json", results)
    with pytest.raises(ValueError):
        module.write_summary(summary, results / ".." / "autre.json", results)
    assert not (tmp_path / "autre.json").exists()


def test_output_refused_through_symlink(tmp_path, synthetic_fixture):
    results = tmp_path / "results"
    results.mkdir()
    (tmp_path / "ailleurs").mkdir()
    try:
        os.symlink(tmp_path / "ailleurs", results / "lien")
    except (OSError, NotImplementedError):
        pytest.skip("liens symboliques indisponibles")
    with pytest.raises(ValueError):
        module.write_summary(module.summarize(synthetic_fixture), results / "lien" / "s.json", results)
    assert not (tmp_path / "ailleurs" / "s.json").exists()


def test_existing_output_refused(tmp_path, synthetic_fixture):
    results = tmp_path / "results"
    results.mkdir()
    summary = module.summarize(synthetic_fixture)
    target = module.write_summary(summary, results / "s.json", results)
    assert json.loads(target.read_text(encoding="utf-8")) == summary
    with pytest.raises(FileExistsError):
        module.write_summary(summary, results / "s.json", results)


def test_no_forbidden_keys(synthetic_fixture):
    for key in _keys(module.summarize(synthetic_fixture)):
        assert not any(word in key.lower() for word in FORBIDDEN), key


@pytest.mark.skipif(not FULL.exists(), reason="campagne complète absente")
def test_full_campaign_coverage():
    data = json.loads(FULL.read_text(encoding="utf-8"))
    arms = module.summarize(data)["arms"]
    assert len(arms) == 4
    for arm in arms.values():
        assert len(arm["seeds"]) == 20
    for seed in range(6):
        assert arms["inherited_lineage"]["seeds"][str(seed)]["library_changed"] is False
    for key in _keys(arms):
        assert not any(word in key.lower() for word in FORBIDDEN), key
