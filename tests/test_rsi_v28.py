"""Containment and provenance tests; never query the V27 fresh bank."""
import copy
import gzip
import json
import sys
from pathlib import Path

import pytest

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps, GUARD
from experiment.rsi_v28 import campaign, family, fresh_bank, freeze, meta
from experiment.rsi_v28.calibration_archive import HISTORY, load
from experiment.rsi_v28.development import Host, population
from experiment.rsi_v27.engine import run_search


def test_exact_qualified_parent_and_all_sources_obey_the_existing_guard():
    assert digest_bytes(family.render(family.ROOT_PARAMS).encode()) == family.PARENT_SHA256
    assert len(family.universe()) == 81
    assert len(family.effective_universe()) == 324
    for row in family.effective_universe():
        source = family.render_genotype(row["genotype"])
        assert row["source_sha256"] == digest_bytes(source.encode())
        assert GUARD.guard_source(source) == []


def test_layouts_have_different_bytes_but_exactly_the_same_ast():
    for row in family.universe():
        sources = [family.render_genotype(family.genotype(row["params"], layout)) for layout in family.LAYOUTS]
        assert len({digest_bytes(s.encode()) for s in sources}) == 4
        assert len({family.structure(s) for s in sources}) == 1
        assert all(family.syntax_changes(s, sources[0]) == [] for s in sources)


@pytest.mark.parametrize("params", [dict(family.ROOT_PARAMS, ordering=True), {"plateau": 0}, dict(family.ROOT_PARAMS, persistence=3)])
def test_invalid_genes_are_rejected(params):
    with pytest.raises(ValueError):
        family.render(params)


def test_original_public_archives_are_lossless_and_not_fresh():
    name = "PUBLIC_001"
    manifest = json.loads((HISTORY / (name + "_MANIFEST.json")).read_text())
    archive = HISTORY / (name + "_CALIBRATION.json.gz")
    raw = gzip.decompress(archive.read_bytes())
    assert digest_bytes(archive.read_bytes()) == manifest["gzip_sha256"]
    assert digest_bytes(raw) == manifest["raw_calibration_sha256"]
    assert not json.loads(raw)["holdout_consumed"]
    assert json.loads(raw)["scope"] == "PUBLIC_DEVELOPMENT_WITH_DISCLOSED_CONSUMED_V27_TASKS"
    assert load()["candidate_count"] == 81


def test_acquired_genes_and_one_component_transition_type_are_external_constraints():
    calibration = load()
    base = dict(family.ROOT_PARAMS, persistence=1)
    host = meta.Host(calibration, base, 1)
    for row in host.children(family.genotype(base), 0):
        for child in host.children(row["candidate"], 1):
            assert child["candidate"]["params"]["persistence"] == 1
            assert len(family.components(child["candidate"]["params"], base)) <= 1
    assert host.children(family.genotype(base), 3) == ()


def test_fresh_parameter_vectors_are_unique_and_disjoint_without_evaluation():
    assert fresh_bank.validate()
    assert [len(bank) for bank in fresh_bank.BANKS] == [24, 12, 12]
    assert len(fresh_bank.cumulative(2)) == 48
    with pytest.raises(ValueError):
        fresh_bank.cumulative(True)


def test_isolated_decisions_match_development_decisions_on_a_public_fixture():
    spec = population(1)[0]
    params = dict(family.ROOT_PARAMS, ordering=2, persistence=1)
    source = family.render(params)
    isolated = run_search(source, Host(spec), caps=Caps(requests=3, rounds=2, parallelism=2, mutation_depth=3))
    development = run_search(source, Host(spec), caps=Caps(requests=3, rounds=2, parallelism=2, mutation_depth=3), isolated=False)
    assert isolated["isolated_policy_processes"]
    assert {k: v for k, v in isolated.items() if k != "isolated_policy_processes"} == {
        k: v for k, v in development.items() if k != "isolated_policy_processes"}
    assert isolated["represented_requests"] <= 3 and isolated["rounds"] <= 2


@pytest.mark.parametrize("code,match", [
    ('import os\n', "guard"),
    ('\ndef order_candidates(view, parent_id, candidates):\n    return []\n', "permutation"),
    ('\ndef select_parent_batch(view, max_parallelism):\n    return ["root", "root"]\n', "authority"),
])
def test_source_and_decision_authority_fail_closed(code, match):
    with pytest.raises(ValueError, match=match):
        run_search(family.render(family.ROOT_PARAMS) + code, Host(population(0)[0]), isolated=True)


def test_invalid_root_quality_is_rejected():
    class BadRoot(Host):
        def root(self):
            return dict(super().root(), quality_milli=True)
    with pytest.raises(ValueError, match="root quality"):
        run_search(family.render(family.ROOT_PARAMS), BadRoot(population(0)[0]), isolated=True)


def test_forged_freezes_and_missing_canonical_evidence_cannot_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(campaign, "ATTEMPT", tmp_path / "attempt.json")
    assert campaign.check()["v28_l6_positive"] is False
    with pytest.raises(ValueError):
        campaign.check(require_result=True)
    with pytest.raises(ValueError):
        freeze.verify({"schema": "mira-genesis-v28-full-freeze-v1", "freeze_sha256": "0" * 64})


def test_exclusive_marker_preserves_an_existing_attempt(tmp_path, monkeypatch):
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps({"python_version": sys.version.split()[0], "freeze_sha256": "fixture"}))
    marker = tmp_path / "attempt.json"
    marker.write_text("consumed")
    monkeypatch.setattr(freeze, "PATH", path)
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    monkeypatch.setattr(campaign, "ATTEMPT", marker)
    with pytest.raises(FileExistsError):
        campaign.run()
    assert marker.read_text() == "consumed"


def test_fresh_receipt_replay_rejects_modified_quality_on_a_public_fixture():
    spec = population(0)[0]
    source = family.render(family.ROOT_PARAMS)
    search = run_search(source, Host(spec), caps=fresh_bank.CAPS)
    campaign.verify_graph(search, source, spec)
    modified = copy.deepcopy(search)
    node = next(row for key, row in modified["nodes"].items() if key != "root")
    node["evaluation"]["quality_milli"] = 1000 - node["evaluation"]["quality_milli"]
    with pytest.raises(ValueError, match="receipt"):
        campaign.verify_graph(modified, source, spec)


def test_consumed_native_pilot_is_retention_and_preserves_all_four_capabilities():
    path = HISTORY / "PUBLIC_001_NATIVE_RETENTION.json"
    value = json.loads(path.read_text())
    assert value["scope"] == "CONSUMED_V26_RETENTION_ONLY_NOT_FRESH" and not value["new_holdout_consumed"]
    assert len(value["generations"]) == 3
    assert all(len(r["episodes"]) == 4 and all(e["best_quality_milli"] == 1000 for e in r["episodes"])
               for r in value["generations"])


def test_persistence_ablation_removes_both_stall_and_plateau_operations():
    source = family.render(dict(family.ROOT_PARAMS, persistence=1))
    assert "penalty = 400" in source and "memory_penalty = 150" in source
    assert "8, 2, 8, 7)" in source
    assert family.render(family.ROOT_PARAMS) == family.PARENT.read_text()
