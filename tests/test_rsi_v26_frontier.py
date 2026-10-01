"""V26 tests never select canonical scientific successors or consume fresh transfer."""
import copy
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from experiment.rsi_v25.commitments import digest,digest_bytes
from experiment.rsi_v25.executable_family import G2_SHA256
from experiment.rsi_v25.search_engine import GUARD,global_utility
from experiment.rsi_v26.family import ROOT_PARAMS,universe,render,neighbors,components
from experiment.rsi_v26.development import population
from experiment.rsi_v26 import native_bank,campaign,freeze


def test_v26_preserves_the_qualified_predecessor_and_has_a_complete_finite_family():
    assert digest_bytes(render(ROOT_PARAMS).encode())==G2_SHA256
    assert len(universe())==len({row["source_sha256"]for row in universe()})==19
    assert len(population())==len({digest(row)for row in population()})==108


@pytest.mark.parametrize("row",universe())
def test_all_declared_sources_are_guarded_and_can_choose_a_fixture_root(row):
    source=render(row["params"]);assert GUARD.guard_source(source)==[]
    functions={};exec(compile(source,"<bounded-v26-fixture>","exec"),functions)
    view={"root_node_id":"root","eligible_parent_ids":["root"],"revealed_nodes":[{
        "node_id":"root","lineage_depth":0,"action":{"family":"fixture","mechanisms":[],"target_axes":[],"changed_regions":[]},
        "outcome":{"quality_milli":0,"evolver_profile_generation":0,"ever_champion":True,"root_branch_node_id":"root"}}]}
    assert functions["select_parent_batch"](view,2)==["root"]
    assert functions["policy_metadata"]()[7]==(2 if row["params"]["strategy"]=="frontier_mix"else 1)


def test_frontier_mix_explores_a_continuation_and_an_available_sibling_under_the_cap():
    functions={};exec(render({**ROOT_PARAMS,"strategy":"frontier_mix","stop_quality":1000}),functions)
    def row(node,depth,quality):
        return {"node_id":node,"lineage_depth":depth,"action":{"family":"fixture","mechanisms":[],"target_axes":[],"changed_regions":[]},
                "outcome":{"quality_milli":quality,"evolver_profile_generation":0,"ever_champion":False,"root_branch_node_id":node}}
    view={"root_node_id":"root","eligible_parent_ids":["root","first","second"],
          "revealed_nodes":[row("root",0,0),row("first",1,500),row("second",1,600)]}
    assert functions["select_parent_batch"](view,2)==["second","root"]
    assert functions["select_parent_batch"](view,1)==["second"]
    view["revealed_nodes"][-1]["outcome"]["quality_milli"]=1000
    assert functions["select_parent_batch"](view,2)==[]


def test_mutations_follow_one_actual_parent_axis_and_fixed_prospective_order():
    first=neighbors(ROOT_PARAMS)[0]
    assert first["params"]["strategy"]=="frontier_mix"
    assert neighbors(first["params"])[0]["params"]["stop_quality"]==1000
    assert all(sum(row["params"][axis]!=ROOT_PARAMS[axis]for axis in ROOT_PARAMS)==1 for row in neighbors(ROOT_PARAMS))
    with pytest.raises(ValueError):render({**ROOT_PARAMS,"unknown":1})
    with pytest.raises(ValueError):render({**ROOT_PARAMS,"stop_quality":True})


def test_frozen_public_calibration_has_no_native_outcomes_or_silent_acquisitions():
    r=json.loads((native_bank.HERE/"PUBLIC_CALIBRATION.json").read_text())
    assert not r["holdout_consumed"]
    assert r["candidate_count"]==19 and r["population_count"]==108
    assert r["population_sha256"]==digest(population())
    root=next(x for x in r["candidates"]if x["params"]==ROOT_PARAMS)
    for row in r["candidates"]:
        assert tuple(row["utility"])==global_utility(row["episodes"])
        assert row["source_sha256"]==digest_bytes(render(row["params"]).encode())
        if row["eligible_successor"]:
            assert row["params"]["stop_quality"]==1000 and row["params"]["strategy"]!="inherited"
            assert tuple(row["utility"])>tuple(root["utility"])
            assert all(tuple(row["utility"])>tuple(control["utility"])for control in row["component_ablations"])
            assert row["parent_choice_witness"]["control_parent_ids"]!=row["parent_choice_witness"]["successor_parent_ids"]


def test_native_target_files_are_new_and_dependencies_are_explicit():
    manifest=json.loads((native_bank.HERE/"native_sources/SOURCE_MANIFEST.json").read_text())
    targets={row["file"]for row in manifest["sources"]if row["role"]=="target"}
    assert targets=={"Product.java","Order.java","pigeon.js","stack.js"}
    assert not targets&{"Batch.java","OrderLine.java","fruit.js","goose.js"}
    for row in manifest["sources"]:
        raw=(native_bank.HERE/"native_sources"/row["file"]).read_bytes()
        assert digest_bytes(raw)==row["source_sha256"]
        assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==row["git_blob_sha1"]
    for task in native_bank.TASKS:
        assert native_bank.render(task,(0,0)).encode()==(native_bank.HERE/"native_sources"/task["source"]).read_bytes()
        assert len({digest_bytes(native_bank.render(task,choice).encode())for choice in itertools.product(range(4),repeat=2)})==16


def test_native_preparation_only_calibrated_reference_and_seed():
    r=json.loads((native_bank.HERE/"NATIVE_CALIBRATION.json").read_text())
    assert not r["successor_executed"] and r["population_sha256"]==digest(native_bank.TASKS)
    assert all(x["reference"]["quality_milli"]==1000 and x["seeded"]["quality_milli"]<1000 for x in r["tasks"])


def test_canonical_marker_refuses_a_second_attempt_without_changing_evidence(tmp_path,monkeypatch):
    frozen=tmp_path/"freeze.json";frozen.write_text('{"runtime_versions":{},"freeze_sha256":"fixture"}')
    marker=tmp_path/"attempt.json";marker.write_text("consumed")
    monkeypatch.setattr(freeze,"PATH",frozen)
    monkeypatch.setattr(freeze,"verify",lambda value:True)
    monkeypatch.setattr(campaign,"runtime_versions",lambda:{})
    monkeypatch.setattr(campaign,"ATTEMPT",marker)
    with pytest.raises(FileExistsError):campaign.run()
    assert marker.read_text()=="consumed"


def test_missing_and_forged_scientific_evidence_cannot_pass(tmp_path,monkeypatch):
    monkeypatch.setattr(freeze,"PATH",tmp_path/"freeze.json")
    monkeypatch.setattr(campaign,"ATTEMPT",tmp_path/"attempt.json")
    assert campaign.check()["v26_l5_positive"]is False
    with pytest.raises(ValueError):campaign.check(require_result=True)
    with pytest.raises(ValueError):freeze.verify({"schema":"mira-genesis-rsi-v26-full-scientific-freeze-v1","freeze_sha256":"0"*64})


def test_recorded_v26_evidence_replays_and_rejects_forged_verdicts():
    if not campaign.ATTEMPT.exists():pytest.skip("Prospective: canonical V26 has not executed")
    result=campaign.check(require_result=True)
    assert result["verdict"]in ("POSITIVE_BOUNDED_L5","VALID_NEGATIVE_FRESH_TRANSFER","NEGATIVE_PRE_TRANSFER","PRESERVED_INSTRUMENT_ABORT")
    if result["verdict"]=="PRESERVED_INSTRUMENT_ABORT":return
    record=json.loads(campaign.ATTEMPT.read_text());frozen=json.loads(freeze.PATH.read_text())
    calibration=json.loads((native_bank.HERE/"PUBLIC_CALIBRATION.json").read_text())
    native=json.loads((native_bank.HERE/"NATIVE_CALIBRATION.json").read_text())
    if record["transfer"]:
        changed=copy.deepcopy(record);del changed["transfer"]["g2"]
        with pytest.raises(ValueError,match="omitted comparator"):
            campaign.adjudicate(changed,frozen,calibration,native)
