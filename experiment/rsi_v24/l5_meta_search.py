#!/usr/bin/env python3
"""Prospective V24 L5 meta-search using exact G2 over a semantic score bridge.

This module is apparatus only. Structural tests may import it, but the four
scientific arms must not be executed until a V24 freeze binds the complete
apparatus and the still-unconsumed fresh holdout.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V22 = ROOT / "experiment" / "rsi_v22"
V23 = ROOT / "experiment" / "rsi_v23"
FAMILY_PATH = V23 / "l5_policy_family.py"
SANDBOX_PATH = V23 / "sandbox_policy.py"
BRIDGE_PATH = HERE / "semantic_quality_bridge.py"
FREEZE_PATH = HERE / "V24_FREEZE.json"
V23_FREEZE_PATH = V23 / "V23_FREEZE.json"
V23_NEGATIVE_PATH = ROOT / "results" / "rsi-v23" / "l5-20260924" / "V23_L5_PRE_HOLDOUT_ADJUDICATION.json"

META_REQUEST_BUDGET = 9
META_ROUND_BUDGET = 8
META_MAX_PARALLELISM = 2
META_MUTATION_DEPTH = 2


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


family = _load("v24_l5_family_search", FAMILY_PATH)
sandbox = _load("v24_l5_sandbox_search", SANDBOX_PATH)
bridge = _load("v24_l5_semantic_bridge", BRIDGE_PATH)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require_freeze(*, verify_semantic_map: bool = True) -> dict[str, Any]:
    """Fail closed unless the committed V24 freeze matches this apparatus."""
    if not FREEZE_PATH.is_file():
        raise RuntimeError(
            "V24 scientific meta-search is forbidden before V24_FREEZE.json exists"
        )

    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze.get("schema") != "mira-genesis-rsi-v24-l5-freeze-v1":
        raise RuntimeError("invalid V24 freeze schema")
    if freeze.get("status") != "FROZEN_BEFORE_ANY_V24_META_SEARCH":
        raise RuntimeError("V24 freeze status does not authorize meta-search")

    if freeze.get("g1_source_sha256") != _sha(controller_source("g1_meta")):
        raise RuntimeError("frozen G1 identity does not match current G1")
    if freeze.get("g2_source_sha256") != _sha(controller_source("g2_meta")):
        raise RuntimeError("frozen G2 identity does not match current G2")
    if freeze.get("g2_ablation_source_sha256") != _sha(g2_ablation_source()):
        raise RuntimeError("frozen G2 ablation identity does not match current ablation")

    predecessor = freeze.get("v23_predecessor", {})
    if predecessor.get("fresh_holdout_consumed") is not False:
        raise RuntimeError("V23 predecessor no longer certifies a fresh holdout")
    if predecessor.get("eligible_for_fresh_holdout") is not False:
        raise RuntimeError("V23 predecessor eligibility changed")

    files = dict(freeze.get("files", {}))
    critical = (
        "experiment/rsi_v24/V24_L5_PREREGISTRATION.md",
        "experiment/rsi_v24/build_l5_freeze.py",
        "experiment/rsi_v24/l5_meta_search.py",
        "experiment/rsi_v24/semantic_quality_bridge.py",
        "experiment/rsi_v23/V23_FREEZE.json",
        "results/rsi-v23/l5-20260924/V23_L5_PRE_HOLDOUT_ADJUDICATION.json",
    )
    for rel in critical:
        expected = files.get(rel)
        path = ROOT / rel
        if not expected or not path.is_file():
            raise RuntimeError(f"frozen critical file missing from V24 freeze: {rel}")
        got = _file_sha256(path)
        if got != expected:
            raise RuntimeError(f"frozen critical file changed after V24 freeze: {rel}")

    if _file_sha256(V23_NEGATIVE_PATH) != predecessor.get(
        "negative_adjudication_sha256"
    ):
        raise RuntimeError("preserved V23 negative adjudication identity changed")

    if verify_semantic_map:
        rows = bridge.bridged_universe()
        utility_to_quality: dict[tuple[int, ...], int] = {}
        candidate_rows = []
        for row in rows:
            utility = tuple(int(x) for x in row["development_utility"])
            quality = int(row["quality_milli"])
            prior = utility_to_quality.get(utility)
            if prior is not None and prior != quality:
                raise RuntimeError("semantic bridge is not a function of utility")
            utility_to_quality[utility] = quality
            candidate_rows.append(
                {
                    "params_digest": str(row["params_digest"]),
                    "source_sha256": str(row["source_sha256"]),
                    "mutation_depth": int(row["mutation_depth"]),
                    "development_utility": list(utility),
                    "quality_milli": quality,
                }
            )

        map_rows = [
            {
                "development_utility": list(utility),
                "quality_milli": quality,
            }
            for utility, quality in sorted(utility_to_quality.items())
        ]
        bridge_record = dict(freeze.get("bridge", {}))
        if _canonical_sha256(map_rows) != bridge_record.get(
            "semantic_quality_map_sha256"
        ):
            raise RuntimeError("semantic quality map differs from V24 freeze")
        candidate_rows.sort(key=lambda row: row["params_digest"])
        if _canonical_sha256(candidate_rows) != bridge_record.get(
            "bridged_candidate_manifest_sha256"
        ):
            raise RuntimeError("bridged candidate manifest differs from V24 freeze")

    return freeze


def g2_ablation_source() -> str:
    src = family.root_source()
    block = "    if best >= 780:\n        return []\n\n"
    if src.count(block) != 1:
        raise RuntimeError("G2 early-stop block changed")
    return src.replace(block, "")


def controller_source(arm: str) -> str | None:
    if arm == "g2_meta":
        return (V22 / "policies" / "g2_search_policy.py").read_text(encoding="utf-8")
    if arm == "g1_meta":
        return (V22 / "policies" / "g1_search_policy.py").read_text(encoding="utf-8")
    if arm == "g2_ablation":
        return g2_ablation_source()
    if arm == "no_meta":
        return None
    raise ValueError("unknown L5 meta-search arm")


def _node(
    node_id: str,
    parent_id: str | None,
    *,
    candidate: Mapping[str, Any],
    lineage_depth: int,
    mutation_axis: str,
    ever_champion: bool,
    root_branch: str,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "parent_node_id": parent_id,
        "candidate": dict(candidate),
        "lineage_depth": int(lineage_depth),
        "action": {
            "family": "search-policy-descendant",
            "target_axes": ["meta-development-process-utility"],
            "mechanisms": [mutation_axis],
            "changed_regions": ["search_policy"],
        },
        "outcome": {
            "quality_milli": int(candidate["quality_milli"]),
            "evolver_profile_generation": int(candidate["mutation_depth"]),
            "ever_champion": bool(ever_champion),
            "root_branch_node_id": root_branch,
        },
    }


def _candidate_index() -> dict[str, dict[str, Any]]:
    return {row["params_digest"]: row for row in bridge.bridged_universe()}


def _children_for(
    node: Mapping[str, Any],
    index: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    depth = int(node["candidate"]["mutation_depth"])
    if depth >= META_MUTATION_DEPTH:
        return ()
    rows = []
    for mutation in family.neighbors(node["candidate"]["params"]):
        child = index.get(mutation["params_digest"])
        if child is None:
            continue
        if int(child["mutation_depth"]) != depth + 1:
            continue
        rows.append({**mutation, "candidate": child})
    rows.sort(key=lambda row: (row["axis"], row["to"], row["candidate"]["params_digest"]))
    return tuple(rows)


def _has_unseen_child(
    node: Mapping[str, Any],
    cursor: int,
    index: Mapping[str, dict[str, Any]],
    seen_candidate_digests: set[str],
) -> bool:
    children = _children_for(node, index)
    return any(
        row["candidate"]["params_digest"] not in seen_candidate_digests
        for row in children[cursor:]
    )


def _view(
    nodes: Mapping[str, dict[str, Any]],
    revealed: list[str],
    cursors: Mapping[str, int],
    index: Mapping[str, dict[str, Any]],
    seen_candidate_digests: set[str],
) -> dict[str, Any]:
    eligible = []
    for node_id in revealed:
        if _has_unseen_child(
            nodes[node_id],
            cursors.get(node_id, 0),
            index,
            seen_candidate_digests,
        ):
            eligible.append(node_id)
    return {
        "root_node_id": "g2-root",
        "revealed_nodes": [
            {
                "node_id": node_id,
                "lineage_depth": nodes[node_id]["lineage_depth"],
                "action": nodes[node_id]["action"],
                "outcome": nodes[node_id]["outcome"],
            }
            for node_id in revealed
        ],
        "eligible_parent_ids": sorted(eligible),
    }


def _selected_successor(nodes: Mapping[str, dict[str, Any]], revealed: list[str]) -> dict[str, Any]:
    candidates = []
    for node_id in revealed:
        row = nodes[node_id]
        candidates.append(
            (
                tuple(row["candidate"]["development_utility"]),
                str(row["candidate"]["source_sha256"]),
                node_id,
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, node_id = candidates[-1]
    return {
        "node_id": node_id,
        "candidate": dict(nodes[node_id]["candidate"]),
    }


def run_arm(arm: str) -> dict[str, Any]:
    index = _candidate_index()
    root_candidate = index[family.params_digest(family.ROOT_PARAMS)]
    root = _node(
        "g2-root",
        None,
        candidate=root_candidate,
        lineage_depth=0,
        mutation_axis="seed-g2",
        ever_champion=True,
        root_branch="g2-root",
    )
    nodes: dict[str, dict[str, Any]] = {"g2-root": root}
    revealed = ["g2-root"]
    seen_candidate_digests = {str(root_candidate["params_digest"])}
    cursors: dict[str, int] = {}
    requests = 0
    rounds = 0
    stalls = 0
    best_quality = int(root_candidate["quality_milli"])
    stop_reason = None

    source = controller_source(arm)
    with tempfile.TemporaryDirectory(prefix="v24-l5-meta-controller-") as td:
        policy_path = None
        metadata = None
        if source is not None:
            policy_path = Path(td) / f"{arm}.py"
            policy_path.write_text(source, encoding="utf-8")
            meta = sandbox.metadata(policy_path, [])
            if not meta.get("accepted"):
                raise RuntimeError(f"{arm} controller rejected: {meta}")
            metadata = list(meta["metadata"])

        while requests < META_REQUEST_BUDGET and rounds < META_ROUND_BUDGET:
            view = _view(nodes, revealed, cursors, index, seen_candidate_digests)
            eligible = list(view["eligible_parent_ids"])
            if not eligible:
                stop_reason = "candidate_family_exhausted"
                break

            if arm == "no_meta":
                parents = [eligible[0]]
            else:
                assert policy_path is not None and metadata is not None
                policy_max_rounds = int(metadata[8])
                policy_stall_rounds = int(metadata[9])
                policy_parallelism = int(metadata[7])
                if rounds >= policy_max_rounds:
                    stop_reason = "policy_max_rounds"
                    break
                if rounds > 0 and stalls >= policy_stall_rounds:
                    stop_reason = "policy_stall_rounds"
                    break
                cap = min(
                    META_MAX_PARALLELISM,
                    policy_parallelism,
                    META_REQUEST_BUDGET - requests,
                )
                selected = sandbox.execute(policy_path, view, cap, [])
                if not selected.get("accepted"):
                    raise RuntimeError(f"{arm} controller failed: {selected}")
                parents = list(selected["selected_parent_ids"])
                if not parents:
                    stop_reason = "policy_empty_batch"
                    break

            before = best_quality
            for parent_id in parents:
                parent = nodes[parent_id]
                children = _children_for(parent, index)
                child_index = cursors.get(parent_id, 0)
                expansion = None
                while child_index < len(children):
                    probe = children[child_index]
                    child_index += 1
                    if probe["candidate"]["params_digest"] in seen_candidate_digests:
                        continue
                    expansion = probe
                    break
                cursors[parent_id] = child_index
                if expansion is None:
                    raise RuntimeError("controller selected parent without unseen child")

                candidate = expansion["candidate"]
                seen_candidate_digests.add(str(candidate["params_digest"]))
                node_id = "m-" + hashlib.sha256(
                    f"{parent_id}|{expansion['params_digest']}|{child_index}".encode()
                ).hexdigest()[:16]
                prior_best = max(int(nodes[x]["outcome"]["quality_milli"]) for x in revealed)
                root_branch = (
                    node_id
                    if parent_id == "g2-root"
                    else parent["outcome"]["root_branch_node_id"]
                )
                nodes[node_id] = _node(
                    node_id,
                    parent_id,
                    candidate=candidate,
                    lineage_depth=int(parent["lineage_depth"]) + 1,
                    mutation_axis=str(expansion["axis"]),
                    ever_champion=int(candidate["quality_milli"]) > prior_best,
                    root_branch=root_branch,
                )
                revealed.append(node_id)
                best_quality = max(best_quality, int(candidate["quality_milli"]))
                requests += 1

            rounds += 1
            stalls = 0 if best_quality > before else stalls + 1

        if stop_reason is None:
            if requests >= META_REQUEST_BUDGET:
                stop_reason = "external_request_budget"
            elif rounds >= META_ROUND_BUDGET:
                stop_reason = "external_round_budget"
            else:
                stop_reason = "stopped"

    selected = _selected_successor(nodes, revealed)
    root_utility = tuple(root_candidate["development_utility"])
    selected_utility = tuple(selected["candidate"]["development_utility"])
    return {
        "schema": "mira-genesis-rsi-v24-l5-meta-arm-v1",
        "arm": arm,
        "controller_sha256": None if source is None else _sha(source),
        "represented_requests": requests,
        "rounds": rounds,
        "stop_reason": stop_reason,
        "revealed_node_ids": revealed,
        "selected_successor": selected,
        "root_g2_development_utility": root_utility,
        "successor_development_utility": selected_utility,
        "successor_strictly_better_than_g2_on_development": selected_utility > root_utility,
        "meta_process_utility": (*selected_utility, -requests, -rounds),
    }


def run_all() -> dict[str, Any]:
    require_freeze(verify_semantic_map=True)
    arms = {arm: run_arm(arm) for arm in ("g2_meta", "g1_meta", "g2_ablation", "no_meta")}
    a = arms["g2_meta"]
    b = arms["g1_meta"]
    c = arms["g2_ablation"]
    return {
        "schema": "mira-genesis-rsi-v24-l5-meta-search-v1",
        "quality_bridge": {
            "worse_than_root_max": bridge.PROMISING_MAX,
            "root_equivalent": bridge.NEUTRAL_QUALITY,
            "strict_successor_min": bridge.STRONG_THRESHOLD,
            "max_quality": bridge.MAX_QUALITY,
        },
        "budgets": {
            "represented_requests_per_arm": META_REQUEST_BUDGET,
            "rounds_per_arm": META_ROUND_BUDGET,
            "max_parallelism": META_MAX_PARALLELISM,
            "mutation_depth": META_MUTATION_DEPTH,
        },
        "arms": arms,
        "pre_holdout_facts": {
            "g2_meta_found_development_improvement": bool(
                a["successor_strictly_better_than_g2_on_development"]
            ),
            "g2_meta_process_beats_g1_meta": tuple(a["meta_process_utility"]) > tuple(b["meta_process_utility"]),
            "g2_meta_process_beats_g2_ablation": tuple(a["meta_process_utility"]) > tuple(c["meta_process_utility"]),
            "g2_ablation_selects_same_successor": (
                a["selected_successor"]["candidate"]["source_sha256"]
                == c["selected_successor"]["candidate"]["source_sha256"]
            ),
        },
    }


def main() -> None:
    print(json.dumps(run_all(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
