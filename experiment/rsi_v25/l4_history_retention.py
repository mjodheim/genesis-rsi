"""Zero-loss executable policy replay of represented positive V22R histories."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest_bytes, load_module
from experiment.rsi_v25.search_engine import SANDBOX
from experiment.rsi_v25.executable_family import render_source

OLD = load_module("v25_l4_history_schema", ROOT / "experiment/rsi_v23/l4_retention_gate.py")
REFERENCE = ROOT / "results/rsi-v22r/V22R_FINAL_ADJUDICATION.json"
TRANSCRIPTS = tuple(ROOT / f"results/rsi-v22r/r1-20260924/{part}/transcript.json"
                    for part in ("catalog", "game-state", "progression"))


def check_l4(source):
    reference = json.loads(REFERENCE.read_text())
    if not reference["v22_positive"]:
        raise ValueError("The qualified L4 reference is not positive")
    tasks = []
    with tempfile.TemporaryDirectory(prefix="v25-l4-retention-") as temporary:
        policy = Path(temporary) / "policy.py"
        policy.write_text(source)
        metadata = SANDBOX.metadata(policy, [])
        if not metadata.get("accepted"):
            raise ValueError("Retention policy rejected by preserved sandbox")
        parallelism = min(2, metadata["metadata"][7])
        for (task_id, path), transcript in zip(OLD.L4_TASKS, TRANSCRIPTS):
            terminal = OLD.view(task_id, path)
            initial = {**terminal, "revealed_nodes": terminal["revealed_nodes"][:1],
                       "eligible_parent_ids": ["root"]}
            first = SANDBOX.execute(policy, initial, parallelism, [])
            last = SANDBOX.execute(policy, terminal, parallelism, [])
            retained = (first.get("accepted") and last.get("accepted")
                        and first["selected_parent_ids"] == ["root"]
                        and last["selected_parent_ids"] == [])
            tasks.append({"task_id": task_id, "initial": first, "terminal": last,
                          "represented_best_quality_milli": 1000,
                          "represented_requests": 1, "represented_rounds": 1,
                          "transcript_sha256": digest_bytes(transcript.read_bytes()),
                          "retained": bool(retained)})
    return {"schema": "mira-genesis-rsi-v25-l4-history-retention-v1",
            "scope": "EXECUTABLE_REPLAY_OF_REPRESENTED_POSITIVE_DISCOVERY_HISTORIES",
            "private_native_host_or_external_model_rerun": False,
            "reference_sha256": digest_bytes(REFERENCE.read_bytes()),
            "policy_sha256": digest_bytes(source.encode()), "tasks": tasks,
            "zero_tolerance_retention": all(row["retained"] for row in tasks)}


def confirm_witness(source, witness):
    if not witness:
        return {"accepted": False, "reason": "no-nonempty-parent-choice-witness"}
    with tempfile.TemporaryDirectory(prefix="v25-behavior-witness-") as temporary:
        policy = Path(temporary) / "policy.py"
        policy.write_text(source)
        control = Path(temporary) / "control.py"
        control.write_text(render_source(witness["control_params"]))
        if digest_bytes(control.read_bytes()) != witness["control_source_sha256"]:
            raise ValueError("Behavior witness control identity mismatch")
        first = SANDBOX.execute(control, witness["view"], 1, [])
        second = SANDBOX.execute(policy, witness["view"], 1, [])
    accepted = bool(first.get("accepted") and second.get("accepted")
                    and first["selected_parent_ids"] == witness["control_parent_ids"]
                    and second["selected_parent_ids"] == witness["successor_parent_ids"]
                    and first["selected_parent_ids"] and second["selected_parent_ids"]
                    and first["selected_parent_ids"] != second["selected_parent_ids"])
    return {"accepted": accepted, "matched_exploration_ablation": first, "successor": second,
            "view_sha256": witness["view_sha256"]}
