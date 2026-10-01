"""One declared recovery replication of an already consumed negative V25 bank.

Never invokes the canonical one-shot runner. Original terminal output is committed
before replication. Raw traces here are replication evidence, explicitly labeled,
not falsely attributed to the unavailable original workspace. A disagreement or
any positive result fails closed; it cannot replace the original negative.
"""
from __future__ import annotations

import json
import os
import subprocess

from experiment.rsi_v25.commitments import HERE, ROOT, digest, write_json
from experiment.rsi_v25.executable_family import (
    ablations, acquired_components, predecessor_source, render_source,
)
from experiment.rsi_v25.executable_meta import run_meta
from experiment.rsi_v25.l4_history_retention import check_l4, confirm_witness
from experiment.rsi_v25.native_transfer import run_native_policy
from experiment.rsi_v25.scientific_freeze import committed_freeze, runtime_versions
from experiment.rsi_v25.campaign_adjudication import adjudicate, pre_gates
from experiment.rsi_v25.run_executable_campaign import ATTEMPT, ADJUDICATION

DIRECTORY = ATTEMPT.parent
OBSERVED = DIRECTORY / "V25_ORIGINAL_OBSERVED_OUTPUT.json"
REPLICATION = DIRECTORY / "V25_RECOVERY_REPLICATION.json"


def require_committed(path):
    relative = path.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    if committed != path.read_bytes():
        raise ValueError("Recovery protocol and original observation must be committed before replication")


def require_same_negative(observed, replicated):
    original = observed["original_adjudication"]
    if (not observed["holdout_consumed"] or not observed["original_run_completed"]
            or original["v25_l5_positive"] or replicated["v25_l5_positive"]
            or digest(original) != digest(replicated)):
        raise ValueError("Recovery replication diverges; never rescore or upgrade the original negative")


def run():
    require_committed(ROOT / "scripts/replicate_v25_consumed_result.py")
    require_committed(OBSERVED)
    require_committed(ATTEMPT)
    freeze = committed_freeze()
    observed = json.loads(OBSERVED.read_text())
    tombstone = json.loads(ATTEMPT.read_text())
    if (tombstone["status"] != "EVIDENCE_RECOVERY_REQUIRED" or tombstone["canonical_attempts"] != 1
            or observed["original_adjudication"]["freeze_sha256"] != freeze["freeze_sha256"]):
        raise ValueError("Recovery is restricted to the recorded completed original negative")
    # A separately named permanent marker distinguishes replication from the
    # original attempt and refuses a second recovery execution on any checkout.
    descriptor = os.open(REPLICATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    record = {"schema": "mira-genesis-rsi-v25-explicit-recovery-replication-v1",
              "status": "RECOVERY_STARTED", "freeze_sha256": freeze["freeze_sha256"],
              "canonical_attempts": 1, "recovery_replication_runs": 1,
              "track": "A", "scientific_external_model_calls": 0,
              "runtime_versions": freeze["runtime_versions"],
              "replication_runtime_versions": runtime_versions(),
              "evidence_provenance": "RAW_TRACES_FROM_DECLARED_REPLICATION_OF_ALREADY_CONSUMED_BANK",
              "original_raw_traces_unavailable": True,
              "original_observed_output_sha256": digest(observed),
              "new_fresh_scientific_attempt": False, "transfer": {},
              "negative_preservation_required": True}
    with os.fdopen(descriptor, "w") as output:
        json.dump(record, output, indent=2, sort_keys=True)
        output.write("\n")
    try:
        calibration = json.loads((HERE / "PUBLIC_DEVELOPMENT_CALIBRATION.json").read_text())
        native = json.loads((HERE / "NATIVE_HOST_CALIBRATION.json").read_text())
        record["native_seeded"] = {row["task_id"]: row["seeded"] for row in native["tasks"]}
        def save_meta(rows):
            record["meta"] = rows
            write_json(REPLICATION, record)
        record["meta"] = run_meta(calibration, checkpoint=save_meta)
        selected = record["meta"]["g2_meta"]["selected"]
        expected = {"depth_weight": 0, "novelty_weight": 0, "stall_rounds": 3,
                    "stop_quality": 900, "strategy": "depth_first"}
        if selected["params"] != expected:
            raise ValueError("Recovered source selection differs from the original frozen discovery")
        source = render_source(selected["params"])
        record["retention"] = check_l4(source)
        record["witness"] = confirm_witness(source, selected["parent_choice_witness"])
        record["pre_gates"] = pre_gates(record["meta"], record["retention"], record["witness"], calibration)
        if not all(record["pre_gates"].values()):
            raise ValueError("Recovered pre-gates diverge from the recorded original output")
        policies = {"g3": source, "g2": predecessor_source(),
                    "g1_meta_successor": render_source(record["meta"]["g1_meta"]["selected"]["params"])}
        policies.update({"ablation_" + axis: render_source(params)
                         for axis, params in zip(acquired_components(selected["params"]), ablations(selected["params"]))})
        for arm, policy in policies.items():
            def save_native(rows):
                record["transfer"][arm] = rows
                write_json(REPLICATION, record)
            record["transfer"][arm] = run_native_policy(policy, native, checkpoint=save_native)
            print("Preserved recovery replication arm: " + arm, flush=True)
        record["status"] = "COMPLETED"
        reproduced = adjudicate(record, freeze, calibration)
        require_same_negative(observed, reproduced)
        record["recovery_matches_observed_negative"] = True
        write_json(REPLICATION, record)
        # This committed evidence envelope references the original run while
        # explicitly attributing all reconstructed traces to this replication.
        # It remains distinguishable from original raw canonical evidence.
        write_json(ATTEMPT, record)
        write_json(ADJUDICATION, observed["original_adjudication"])
        for arm in ("g2_meta", "g1_meta"):
            (DIRECTORY / (arm.upper() + "_SELECTED_POLICY.py")).write_text(
                render_source(record["meta"][arm]["selected"]["params"]))
        print(json.dumps({"original_negative_preserved": True, "recovery_matches_observed_negative": True,
                          "new_fresh_attempt": False, "v25_l5_positive": False}, indent=2), flush=True)
    except BaseException as error:
        record["status"] = "RECOVERY_ABORTED"
        record["recovery_error"] = {"type": type(error).__name__, "message": str(error)}
        write_json(REPLICATION, record)
        raise


if __name__ == "__main__":
    run()
