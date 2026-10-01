"""Compute every positive predicate from preserved raw evidence, not flags."""
from __future__ import annotations

from experiment.rsi_v25.commitments import HERE, digest, digest_bytes
from experiment.rsi_v25.executable_family import (
    ROOT_PARAMS, acquired_components, neighbors, predecessor_source, render_source,
)
from experiment.rsi_v25.executable_meta import ARMS, META_CAPS, choose_successor, MetaHost
from experiment.rsi_v25.native_transfer import TASKS, TRANSFER_CAPS, NativeHost, render_native
from experiment.rsi_v25.search_engine import global_utility, run_search
from experiment.rsi_v25.l4_history_retention import check_l4, confirm_witness


def meta_utility(arm):
    chosen, search = arm["selected"], arm["search"]
    return (int(chosen["qualified_discovery"]), *chosen["utility"][:2],
            -search["represented_requests"], -search["rounds"])


def validate_search(search, *, native_task=None, calibration=None):
    caps = TRANSFER_CAPS if native_task else META_CAPS
    if (search["caps"] != caps.__dict__ or not search["isolated_policy_processes"]
            or search["represented_requests"] != len(search["nodes"]) - 1
            or search["rounds"] != len(search["observations"])
            or search["represented_requests"] > caps.requests or search["rounds"] > caps.rounds):
        raise ValueError("Search accounting, external caps or isolation disagree")
    if search["best_quality_milli"] != max(
            node["outcome"]["quality_milli"] for node in search["nodes"].values()):
        raise ValueError("Forged best-quality aggregate")
    by_source = {row["source_sha256"]: row for row in calibration["candidates"]} if calibration else {}
    seen = set()
    for node_id, node in search["nodes"].items():
        if node["source_sha256"] in seen:
            raise ValueError("Duplicate executable source charged as a new request")
        seen.add(node["source_sha256"])
        parent_id = node["parent_node_id"]
        if node_id == "root":
            if parent_id is not None or node["lineage_depth"] != 0:
                raise ValueError("Malformed root")
            continue
        parent = search["nodes"][parent_id]
        if not 0 < node["lineage_depth"] == parent["lineage_depth"] + 1 <= caps.mutation_depth:
            raise ValueError("Mutation escaped the actual parent lineage")
        receipt = node["evaluation"]
        if (not receipt["accepted"] or receipt["source_sha256"] != node["source_sha256"]
                or receipt["quality_milli"] != node["outcome"]["quality_milli"]):
            raise ValueError("Evaluator receipt or executable identity mismatch")
        if native_task:
            source = render_native(native_task, node["candidate"]["choices"])
            differences = sum(x != y for x, y in zip(
                parent["candidate"]["choices"], node["candidate"]["choices"]))
            if differences != 1:
                raise ValueError("Native repair is not a one-locus child of its selected parent")
            cases = receipt["cases"]
            if (receipt["cases_sha256"] != digest(cases) or cases["total"] <= 0
                    or cases["total"] - cases["passed"] != len(cases["failed"])
                    or receipt["quality_milli"] != cases["passed"] * 1000 // cases["total"]
                    or not receipt["native_source_executed"] or receipt["task_sha256"] != digest(native_task)
                    or receipt["harness_sha256"] != digest_bytes(
                        (HERE / "native_harnesses" / native_task["harness"]).read_bytes())):
                raise ValueError("Native quality is not derived from retained cases")
        else:
            source = render_source(node["candidate"])
            if node["candidate"] not in [x["params"] for x in neighbors(parent["candidate"])]:
                raise ValueError("Meta candidate was not generated from its selected parent")
            development = by_source[node["source_sha256"]]
            if (receipt["development_receipt_sha256"] != digest(development)
                    or receipt["public_development_utility"] != development["utility"]
                    or receipt["quality_milli"] != development["meta_quality_milli"]):
                raise ValueError("Meta quality is not bound to frozen development receipt")
        if digest_bytes(source.encode()) != node["source_sha256"]:
            raise ValueError("Candidate executable bytes do not match the receipt")
    produced = []
    for observation in search["observations"]:
        view = observation["view"]
        if (observation["view_sha256"] != digest(view)
                or len(observation["parent_node_ids"]) > observation["parallelism_cap"]
                or observation["parallelism_cap"] > caps.parallelism
                or len(observation["result_node_ids"]) > len(observation["parent_node_ids"])
                or any(parent not in view["eligible_parent_ids"] for parent in observation["parent_node_ids"])):
            raise ValueError("Decision observation exceeds revealed parent authority")
        for child_id in observation["result_node_ids"]:
            if search["nodes"][child_id]["parent_node_id"] not in observation["parent_node_ids"]:
                raise ValueError("Evaluated child lacks a selected parent")
            produced.append(child_id)
    if len(set(produced)) != len(produced) or set(produced) != set(search["nodes"]) - {"root"}:
        raise ValueError("Raw observations omit, duplicate or invent an evaluated child")
    return True


def pre_gates(meta, retention, witness, calibration):
    for arm in ARMS:
        validate_search(meta[arm]["search"], calibration=calibration)
        chosen = meta[arm]["selected"]
        if digest(chosen) != digest(choose_successor(meta[arm]["search"], calibration)):
            raise ValueError("Successor selection differs from the frozen rule or receipt")
        if chosen["source_sha256"] not in {x["source_sha256"] for x in meta[arm]["search"]["nodes"].values()}:
            raise ValueError("Selected successor was never discovered by this arm")
    chosen = meta["g2_meta"]["selected"]
    source = render_source(chosen["params"])
    if digest(retention) != digest(check_l4(source)):
        raise ValueError("Retention flags do not match isolated represented-history replay")
    if digest(witness) != digest(confirm_witness(source, chosen["parent_choice_witness"])):
        raise ValueError("Parent-choice witness flags do not match isolated replay")
    reference = next(row for row in calibration["candidates"] if row["params"] == ROOT_PARAMS)
    lineage = [node for node in meta["g2_meta"]["search"]["nodes"].values()
               if node["source_sha256"] == chosen["source_sha256"]]
    return {"qualified_executable_descent": bool(chosen["qualified_discovery"] and lineage
                                                and lineage[0]["lineage_depth"] > 0),
            "development_strict_gain": tuple(chosen["utility"]) > tuple(reference["utility"]),
            "strict_every_development_ablation": bool(chosen["component_ablations"]
                and all(tuple(chosen["utility"]) > tuple(row["utility"]) for row in chosen["component_ablations"])),
            "acquired_exploration": bool(set(acquired_components(chosen["params"]))
                                       & {"strategy", "depth_weight", "novelty_weight"}),
            "isolated_parent_choice_witness": bool(witness["accepted"]),
            "l4_zero_loss": bool(retention["tasks"] and all(
                row["initial"].get("accepted") and row["terminal"].get("accepted")
                and row["initial"]["selected_parent_ids"] == ["root"]
                and row["terminal"]["selected_parent_ids"] == []
                for row in retention["tasks"])),
            "meta_advantage_over_acquired_g2_ablation":
                meta_utility(meta["g2_meta"]) > meta_utility(meta["g2_ablation"])}


def replay_native_evidence(search, task, source, seeded):
    receipts = {node["source_sha256"]: node["evaluation"] for node_id, node in search["nodes"].items()
                if node_id != "root"}

    class ReceiptHost(NativeHost):
        def evaluate(self, row):
            if row["source_sha256"] not in receipts:
                raise ValueError("Policy replay requests an unobserved native candidate")
            return receipts[row["source_sha256"]]

    replay = run_search(source, ReceiptHost(task, seeded), caps=TRANSFER_CAPS, isolated=True)
    if digest(replay) != digest({key: value for key, value in search.items() if key != "task_id"}):
        raise ValueError("Native evidence differs from deterministic policy/receipt replay")


def adjudicate(attempt, freeze, calibration):
    meta, retention, witness = attempt["meta"], attempt["retention"], attempt["witness"]
    gates = pre_gates(meta, retention, witness, calibration)
    # Meta replay uses only the frozen public development evaluator, never the
    # native bank. Native replay below uses only already retained receipts.
    from experiment.rsi_v25.executable_family import baseline_source, predecessor_ablation_source
    controls = {"g2_meta": predecessor_source(), "g1_meta": baseline_source(),
                "g2_ablation": predecessor_ablation_source(), "no_meta": None}
    for arm in ARMS:
        replay = run_search(controls[arm], MetaHost(calibration), caps=META_CAPS, isolated=True)
        if digest(replay) != digest(meta[arm]["search"]):
            raise ValueError("Meta evidence differs from deterministic frozen-evaluator replay")
    identities = (attempt["freeze_sha256"] == freeze["freeze_sha256"]
                  and retention["policy_sha256"] == meta["g2_meta"]["selected"]["source_sha256"]
                  and attempt["track"] == "A" and attempt["scientific_external_model_calls"] == 0)
    predicates = {**gates, "frozen_identities_and_track": identities,
                  "fresh_transfer_completed": bool(attempt.get("transfer"))}
    utilities = {}
    if attempt.get("transfer"):
        if not all(gates.values()):
            raise ValueError("Transfer was consumed without every pre-gate")
        expected = {"g3", "g2", "g1_meta_successor"} | {
            "ablation_" + axis for axis in acquired_components(meta["g2_meta"]["selected"]["params"])}
        if set(attempt["transfer"]) != expected:
            raise ValueError("Fresh comparator or component ablation omitted")
        for arm, rows in attempt["transfer"].items():
            if [row["task_id"] for row in rows] != [task["task_id"] for task in TASKS]:
                raise ValueError("Native bank task identities or order changed")
            for row, task in zip(rows, TASKS):
                validate_search(row, native_task=task)
                if arm == "g2":
                    source = predecessor_source()
                elif arm == "g1_meta_successor":
                    source = render_source(meta["g1_meta"]["selected"]["params"])
                else:
                    params = dict(meta["g2_meta"]["selected"]["params"])
                    if arm.startswith("ablation_"):
                        axis = arm[len("ablation_"):]
                        params[axis] = ROOT_PARAMS[axis]
                    source = render_source(params)
                if row["policy_sha256"] != digest_bytes(source.encode()):
                    raise ValueError("A native arm ran the wrong comparator or ablation")
                replay_native_evidence(row, task, source, attempt["native_seeded"][task["task_id"]])
            utilities[arm] = global_utility(rows)
        predicates.update(
            strict_fresh_gain_over_g2=utilities["g3"] > utilities["g2"],
            strict_fresh_gain_over_g1_meta=utilities["g3"] > utilities["g1_meta_successor"],
            strict_every_fresh_component_ablation=all(
                utilities["g3"] > utility for arm, utility in utilities.items() if arm.startswith("ablation_")),
        )
    else:
        predicates.update(strict_fresh_gain_over_g2=False, strict_fresh_gain_over_g1_meta=False,
                          strict_every_fresh_component_ablation=False)
    positive = all(predicates.values())
    return {"schema": "mira-genesis-rsi-v25-executable-l5-adjudication-v1",
            "v25_l5_positive": positive,
            "verdict": "POSITIVE_BOUNDED_L5" if positive else
                       "VALID_NEGATIVE_FRESH_TRANSFER" if attempt.get("transfer") else "NEGATIVE_PRE_TRANSFER",
            "predicates": predicates, "fresh_global_utilities": utilities,
            "meta_utilities": {arm: meta_utility(meta[arm]) for arm in ARMS},
            "freeze_sha256": freeze["freeze_sha256"],
            "holdout_consumed": bool(attempt.get("transfer")),
            "scope": "BOUNDED_NATIVE_REPAIR_TRANSFER_ON_FOUR_PROJECT_AUTHORED_TASKS"}
