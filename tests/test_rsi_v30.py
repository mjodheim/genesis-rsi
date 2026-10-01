"""Bottleneck selection and evidence-boundary tests, using public contexts only."""
import copy
import gzip
import json
import sys

import pytest

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.development import Host
from experiment.rsi_v30 import campaign, family, freeze, fresh_bank, meta, pipeline_contexts as contexts


@pytest.fixture(scope="module")
def public():
    return json.loads((meta.HERE / "PUBLIC_CONTEXTS.json").read_text())


def test_disjoint_prospective_population_is_unfiltered():
    assert len(fresh_bank.CONTEXTS) == 58 and fresh_bank.validate()
    assert [sum(row["fault"] == part for row in fresh_bank.CONTEXTS) for part in contexts.PARTS] == [16, 24, 18]


def test_parent_prefix_and_closed_eight_program_universe():
    assert family.render((0, 0, 0)) == family.parent()
    assert digest_bytes(family.parent().encode()) == family.PARENT_SHA256
    rows = family.universe()
    assert len(rows) == len({row["source_sha256"] for row in rows}) == 8
    assert all(family.render(row["flags"]).startswith(family.parent()) for row in rows)
    assert all(not meta.GUARD.guard_source(family.render(row["flags"]), []) for row in rows)
    with pytest.raises(ValueError):
        family.render((True, 0, 0))
    with pytest.raises(ValueError):
        family.fixed("unbounded-authority")


def test_all_examined_public_traces_and_negatives_are_retained(public):
    with gzip.open(meta.HERE / "PUBLIC_CONTEXTS_ALL.json.gz", "rt") as stream:
        rows = json.load(stream)
    assert len(rows) == 324 and digest(rows) == public["all_examined_public_contexts_sha256"]
    assert any(not row["eligible_public_diagnostic_example"] for row in rows)
    assert public["scope"] == "OUTCOME_CONDITIONED_PUBLIC_DEVELOPMENT_NOT_FRESH"
    assert not public["new_holdout_consumed"]


def test_isolated_selector_sees_only_diagnostics_and_allowed_targets(public, monkeypatch):
    expected = public["contexts"][0]["diagnostics"]
    metadata = list(meta.development_functions(family.parent(), ())["policy_metadata"]())
    def observe(path, payload):
        assert set(payload) == {"mode", "diagnostics", "targets"}
        assert payload["diagnostics"] == expected and payload["targets"] == list(contexts.TARGETS)
        assert set(expected) == {*contexts.PARTS, "revealed_best_quality_milli", "basis"}
        assert not any(key in expected for key in ("fault", "spec", "expected", "context_sha256"))
        return {"target": "exploration", "metadata": metadata}
    monkeypatch.setattr(meta, "call", observe)
    assert meta.select(family.render((1, 1, 1)), expected) == "exploration"


def test_unrevealed_quality_and_fault_do_not_change_diagnostics(public):
    row = public["contexts"][0]
    host = Host(row["context"]["spec"])
    revealed = {node["candidate"]["token"] for node in row["baseline"]["nodes"].values()}
    for token, proposal in host.rows.items():
        if token not in revealed:
            proposal["quality_milli"] = -987654
    assert contexts.diagnostics(row["baseline"], host) == row["diagnostics"]


def test_repair_operator_is_equal_and_wrong_part_is_noop(public):
    context = public["contexts"][0]["context"]
    intact = contexts.qualified_genotype()["params"]
    assert contexts.repaired_params(context, context["fault"]) == intact
    for part in contexts.PARTS:
        if part != context["fault"]:
            assert contexts.repaired_params(context, part) == contexts.baseline_params(context)


def test_probe_post_and_decision_costs_are_charged_equally(public):
    row = public["contexts"][0]
    baseline = row["baseline"]
    result = meta.context_utility([{"baseline": baseline, "post": baseline}])
    assert result[2:] == (-2 * baseline["represented_requests"] - 1, -2 * baseline["rounds"] - 1)


def test_public_discovery_and_previous_acquisition_ablation(public):
    measured = meta.calibration(public)
    pilot = meta.pilot(measured)
    inherited, ablated = (pilot["arms"][key] for key in ("inherited_g6", "g6_scheduling_ablation"))
    assert inherited["selected"]["qualified_discovery"]
    assert inherited["utility"] > ablated["utility"]
    assert inherited["selected"]["source_sha256"] == ablated["selected"]["source_sha256"]


def test_real_isolated_selector_and_parent_default(public):
    diagnostics = public["contexts"][0]["diagnostics"]
    assert meta.select(family.parent(), diagnostics) == "identity"
    assert meta.select(family.render((1, 1, 1)), diagnostics) == "exploration"


def test_graph_replay_refuses_forged_receipt(public):
    row = public["contexts"][0]
    search = copy.deepcopy(row["baseline"])
    node = next(node for key, node in search["nodes"].items() if key != "root")
    node["evaluation"]["quality_milli"] += 1
    with pytest.raises(ValueError, match="receipt"):
        campaign.verify_graph(search, row["context"], "identity")


def test_lossless_archive_refuses_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ATTEMPT", tmp_path / "index.json")
    monkeypatch.setattr(campaign, "RAW", tmp_path / "raw.json.gz")
    record = {"status": "COMPLETED", "canonical_attempts": 1, "freeze_sha256": "fixture", "every_negative": [0, 1, 0]}
    campaign.preserve(record)
    assert campaign.read_attempt() == record
    campaign.RAW.write_bytes(gzip.compress(json.dumps({**record, "every_negative": []}).encode()))
    with pytest.raises(ValueError, match="altered"):
        campaign.read_attempt()


def test_missing_freeze_and_corrupt_identity_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(campaign, "ATTEMPT", tmp_path / "attempt.json")
    assert campaign.check()["v30_l8_positive"] is False
    with pytest.raises(ValueError):
        campaign.check(require_result=True)
    with pytest.raises(ValueError):
        freeze.verify({"schema": "mira-genesis-v30-full-freeze-v1", "freeze_sha256": "0" * 64})


def test_exclusive_attempt_marker_refuses_retry(tmp_path, monkeypatch):
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
