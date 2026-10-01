"""Fixed fault/repair operators and oracle-free diagnostics from real execution."""
import json

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v25.search_engine import global_utility
from experiment.rsi_v27.development import Host, PUBLIC_CAPS
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v28 import campaign as v28, family

PARTS = ("exploration", "generation", "scheduling")
TARGETS = ("identity", *PARTS)
GENES = {"exploration": "persistence", "generation": "ordering", "scheduling": "scheduling"}


def qualified_genotype():
    return json.loads(v28.ATTEMPT.read_text())["chain"]["phases"][-1]["selected_genotype"]


def baseline_params(context):
    params = dict(qualified_genotype()["params"])
    params[GENES[context["fault"]]] = 0
    return params


def repaired_params(context, target):
    if target not in TARGETS:
        raise ValueError("Unknown optimization target")
    params = baseline_params(context)
    if target != "identity":
        gene = GENES[target]
        params[gene] = qualified_genotype()["params"][gene]
    return params


def source(context, target="identity"):
    return family.render_genotype(family.genotype(repaired_params(context, target), qualified_genotype()["layout"]))


def diagnostics(search, host):
    """Never evaluate a proposal or read an unrevealed quality or fault label."""
    nodes, seen = search["nodes"], {search["nodes"]["root"]["source_sha256"]}
    plateau, skipped_new_regions, redundant_roots = 0, 0, 0
    for observation in search["observations"]:
        view = {row["node_id"]: row for row in observation["view"]["revealed_nodes"]}
        root = observation["view"]["root_node_id"]
        parents = observation["parent_node_ids"]
        if root in parents and len(parents) > 1:
            for key in parents:
                if key == root:
                    continue
                row = view[key]
                previous = view[row["parent_node_id"]]
                if (row["lineage_depth"] >= 2 and row["outcome"]["quality_milli"] >= 900
                        and row["outcome"]["quality_milli"] > previous["outcome"]["quality_milli"]):
                    redundant_roots += 1
        for key in observation["result_node_ids"]:
            row = nodes[key]
            parent = nodes[row["parent_node_id"]]
            axes = set(parent["action"]["target_axes"])
            static = [{"source_sha256": child["source_sha256"], "action": host.action(child)}
                      for child in host.children(parent["candidate"], parent["lineage_depth"])
                      if child["source_sha256"] not in seen]
            new_possible = any(set(child["action"]["target_axes"]) - axes for child in static)
            new_actual = set(row["action"]["target_axes"]) - axes
            if new_possible and not new_actual:
                skipped_new_regions += 1
            if (row["lineage_depth"] >= 2 and row["outcome"]["quality_milli"] > 0
                    and row["outcome"]["quality_milli"] == parent["outcome"]["quality_milli"]
                    and not new_possible):
                plateau += 1
        seen.update(nodes[key]["source_sha256"] for key in observation["result_node_ids"])
    failed = search["best_quality_milli"] < 1000
    return {"exploration": plateau if failed and not skipped_new_regions else 0,
            "generation": skipped_new_regions if failed else 0,
            "scheduling": redundant_roots if not failed else 0,
            "revealed_best_quality_milli": search["best_quality_milli"],
            "basis": "REVEALED_EXECUTION_AND_STATIC_PROPOSALS_ONLY"}


def episode(context, target="identity", *, isolated=False):
    return run_search(source(context, target), Host(context["spec"]), caps=PUBLIC_CAPS, isolated=isolated)


def public_preparation():
    """Disclosed outcome-conditioned public curriculum, never fresh selection."""
    from experiment.rsi_v28.development import population
    chosen, all_rows = [], []
    for stage, (part, required) in enumerate(zip(PARTS, (16, 3, 1))):
        count = 0
        for spec in sorted(population(stage), key=digest):
            context = {"fault": part, "spec": spec}
            baseline = episode(context)
            measured = diagnostics(baseline, Host(spec))
            variants = {target: episode(context, target) if target != "identity" else baseline for target in TARGETS}
            utilities = {target: global_utility([search]) for target, search in variants.items()}
            best = max(utilities.values())
            eligible = (measured[part] > 0 and utilities[part] == best and best > utilities["identity"]
                        and all(measured[other] == 0 for other in PARTS if other != part))
            row = {"context": context, "context_sha256": digest(context), "baseline": baseline,
                   "diagnostics": measured, "variants": variants, "utilities": utilities,
                   "eligible_public_diagnostic_example": eligible}
            all_rows.append(row)
            if eligible and count < required:
                chosen.append(row)
                count += 1
        if count != required:
            raise ValueError("Insufficient declared public diagnostic examples: " + part)
    return {"scope": "OUTCOME_CONDITIONED_PUBLIC_DEVELOPMENT_NOT_FRESH", "new_holdout_consumed": False,
            "curriculum_counts": [16, 3, 1], "contexts": chosen,
            "all_examined_public_contexts_sha256": digest(all_rows), "all_examined_context_count": len(all_rows),
            "all_examined_contexts": all_rows}
