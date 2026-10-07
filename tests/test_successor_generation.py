from __future__ import annotations

import json
from pathlib import Path

from genesis.core import self_model
from genesis.evolution import successor_generation
from genesis.runtime import profile_executor


ROOT = Path(__file__).resolve().parents[1]


def _evidence() -> tuple[dict, dict, dict, dict]:
    g6_result = json.loads((ROOT / "experiment/g6_qualification/RESULT.json").read_text())
    g6_descendant = json.loads((ROOT / "experiment/g6_qualification/DESCENDANT.json").read_text())
    g8_result = json.loads((ROOT / "experiment/g8_qualification/RESULT.json").read_text())
    g8_freeze = json.loads((ROOT / "experiment/g8_qualification/SPECIALIST.json").read_text())
    return g6_result, g6_descendant, g8_result, g8_freeze


def _proposal() -> dict:
    parent = successor_generation.build_parent_profile(ROOT)
    g6_result, g6_descendant, g8_result, g8_freeze = _evidence()
    return successor_generation.generate_successor(
        parent,
        g6_result=g6_result,
        g6_descendant=g6_descendant,
        g8_result=g8_result,
        g8_specialist_freeze=g8_freeze,
    )


def _universal_operator() -> dict:
    g5 = json.loads((ROOT / "experiment/g5_qualification/PREREGISTRATION.json").read_text())
    return g5["source_capability"]["universal_operator"]


def test_g9_self_model_contains_specialization_and_successor_generation() -> None:
    model = self_model.build_self_model(ROOT)
    ids = {item["component_id"] for item in model["components"]}

    assert "local_specialist_distillation" in ids
    assert "successor_generator" in ids
    assert self_model.validate_self_model(model) == model


def test_g9_generates_whole_successor_from_passed_evidence() -> None:
    proposal = _proposal()
    held = successor_generation.validate_proposal(proposal)
    parent = held["parent_profile"]
    child = held["successor_profile"]

    assert child["generation"] == parent["generation"] + 1
    assert child["parent_profile_digest"] == parent["profile_digest"]
    assert child["component_inventory"] == parent["component_inventory"]
    assert held["material_change_count"] == 3
    assert held["lineage_produced"] is True
    assert held["prospective_holdout_visible"] is False
    assert held["mutable_lineage_owns_verdict"] is False

    assert (
        child["active_overrides"]["universal_operator_ir"]["source_sha256"]
        == "3451b476a319846df00ffe3984da8fb760a6a4c9f68313ebf4f4fb464f5954be"
    )
    assert (
        child["active_overrides"]["local_repair_specialist"]["specialist_digest"]
        == "94afbbfbe908f9c76c6abdf19f39f24e12f14c7c5a680feceeca0283b7424edb"
    )
    assert child["routing_program"]["order"] == [
        "local_repair_specialist",
        "universal_operator_ir",
    ]
    assert parent["routing_program"]["order"] == ["universal_operator_ir"]


def test_g9_parent_profile_uses_current_universal_parent() -> None:
    parent = successor_generation.build_parent_profile(ROOT)

    assert (
        parent["active_overrides"]["universal_operator_ir"]["source_sha256"]
        == "a294e8fb47ff3a138667463610df25121c33aa2190308231b2116492e8eb4309"
    )
    assert parent["active_overrides"]["local_repair_specialist"] is None
    assert parent["hidden_holdout_visible"] is False


def test_g9_successor_routes_fresh_python_range_to_local_specialist(tmp_path: Path) -> None:
    proposal = _proposal()
    profile = proposal["successor_profile"]
    target = tmp_path / "logic.py"
    target.write_text(
        "def product(limit):\n"
        "    out = 1\n"
        "    for item in range(1, limit):\n"
        "        out *= item\n"
        "    return out\n",
        encoding="utf-8",
    )

    generated = profile_executor.generate_candidates(
        tmp_path,
        profile,
        repository_root=ROOT,
        universal_operator=_universal_operator(),
        max_candidates=4,
    )

    assert generated["external_model_calls"] == 0
    assert generated["candidate_count"] >= 1
    assert generated["candidates"][0]["route"] == "local_repair_specialist"
    assert "range(1, limit + 1)" in generated["candidates"][0]["mutations"][0]["content_utf8"]


def test_g9_successor_falls_through_to_evolved_universal_operator(tmp_path: Path) -> None:
    proposal = _proposal()
    profile = proposal["successor_profile"]
    target = tmp_path / "Program.cs"
    target.write_text(
        "using System;\n"
        "class Program { static int[] Make() => new[]{13,77}; "
        "static int Pick() => Make()[1]; }\n",
        encoding="utf-8",
    )

    generated = profile_executor.generate_candidates(
        tmp_path,
        profile,
        repository_root=ROOT,
        universal_operator=_universal_operator(),
        max_candidates=4,
    )

    universal = [c for c in generated["candidates"] if c["route"] == "universal_operator_ir"]
    assert universal
    assert "Make()[0]" in universal[0]["mutations"][0]["content_utf8"]


def test_g9_parent_does_not_have_local_specialist_route(tmp_path: Path) -> None:
    parent = successor_generation.build_parent_profile(ROOT)
    target = tmp_path / "logic.py"
    target.write_text(
        "def product(limit):\n"
        "    out = 1\n"
        "    for item in range(1, limit):\n"
        "        out *= item\n"
        "    return out\n",
        encoding="utf-8",
    )

    generated = profile_executor.generate_candidates(
        tmp_path,
        parent,
        repository_root=ROOT,
        universal_operator=_universal_operator(),
        max_candidates=4,
    )

    assert all(c["route"] != "local_repair_specialist" for c in generated["candidates"])
