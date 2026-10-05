"""Post-pilot read-only V36 grammar distance audit; never repairs frozen evidence."""
import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v32 import storage
from experiment.rsi_v36 import bank, campaign


def minimum_edits(current, target, fragments):
    """Exact distance in the admitted point/aligned-splice grammar, ignoring caps.

    Block edits commute. If a block is spliced, only its last splice and the
    following point edits can matter; earlier edits are overwritten. Therefore
    the optimum is direct point distance or one splice plus its point residual.
    No two splices of the same aligned block improve this optimum. Sum independent
    block minima. This uses hidden targets only in the external retrospective audit.
    """
    padded = current + [0] * (len(target) - len(current))
    if len(current) > len(target) or len(target) % bank.BLOCK:
        raise ValueError("Distance audit requires a complete recombination interface")
    result = 0
    for start in range(0, len(target), bank.BLOCK):
        wanted = target[start:start + bank.BLOCK]
        before = padded[start:start + bank.BLOCK]
        options = [sum(a != b for a, b in zip(before, wanted))]
        options.extend(1 + sum(a != b for a, b in zip(fragment, wanted)) for fragment in fragments)
        result += min(options)
    return result


def inspect(root, *, full_replay=True):
    root = Path(root)
    report = campaign.check(root) if full_replay else storage.read_json(root / "REPORT.json")
    manifest = storage.read_json(root / "MANIFEST.json")
    cohort_counts, counts, examples = {}, Counter(), {}
    for label, tasks in campaign.population(manifest["mode"]).items():
        local = Counter()
        for epoch in sorted({t["epoch"] for t in tasks if t["epoch"] >= bank.BLOCK}):
            subset = [t for t in tasks if t["epoch"] == epoch]
            raw = storage.read_regular(root / label / "archive" / f"epoch-{epoch:03}" / "EVIDENCE.json.gz")
            rows = json.loads(gzip.decompress(raw))
            for task, row in zip(subset, rows):
                local["transfer_tasks"] += 1
                if row["solved"]:
                    local["solved"] += 1
                    continue
                fragments = [f["ops"] for f in row["learned_fragments"]]
                paid_roots = [call for call in row["calls"] if call["kind"] in ("root", "screen")]
                selected = next(call["genome"] for call in paid_roots
                                if call["evaluation"]["source_sha256"] == row["selected_root_sha256"])
                distance = minimum_edits(selected["ops"], task["target"], fragments)
                best_paid = min(minimum_edits(call["genome"]["ops"], task["target"], fragments)
                                for call in paid_roots)
                depth = row["search"]["caps"]["mutation_depth"]
                category = ("all_paid_roots_beyond_depth" if best_paid > depth else
                            "selected_root_beyond_depth" if distance > depth else
                            "selected_root_reachable_but_not_found")
                local[category] += 1
                local["tasks_missing_a_target_fragment"] += int(any(
                    task["target"][start:start + bank.BLOCK] not in fragments
                    for start in range(0, task["slots"], bank.BLOCK)))
                examples.setdefault(category, {"label": label, "epoch": epoch,
                    "position": row["global_position"], "task_sha256": digest(task),
                    "selected_root": selected, "target": task["target"],
                    "learned_fragments": fragments, "selected_minimum_edits": distance,
                    "best_paid_root_minimum_edits": best_paid, "depth_cap": depth})
        cohort_counts[label] = dict(local)
        counts.update(local)
    return {"schema": "mira-genesis-v36-post-pilot-failure-distance-audit-v1",
            "manifest_sha256": digest(manifest), "report_sha256": digest(report),
            "full_original_replay_performed": full_replay, "counts": dict(counts),
            "cohorts": cohort_counts, "examples": examples,
            "posthoc_diagnostic": True, "new_evaluations": 0,
            "frozen_predicates_unchanged": True, "independent_replication": False,
            "l9_general_open_ended_passed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.output_dir), sort_keys=True))
