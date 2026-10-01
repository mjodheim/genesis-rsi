"""One canonical frozen V25 attempt. Preserve every partial record and failure."""
from __future__ import annotations

import json
import os

from experiment.rsi_v25.commitments import HERE, ROOT, write_json
from experiment.rsi_v25.executable_family import ablations, acquired_components, predecessor_source, render_source
from experiment.rsi_v25.executable_meta import run_meta
from experiment.rsi_v25.l4_history_retention import check_l4, confirm_witness
from experiment.rsi_v25.native_transfer import run_native_policy
from experiment.rsi_v25.scientific_freeze import committed_freeze, runtime_versions
from experiment.rsi_v25.campaign_adjudication import adjudicate, pre_gates

ATTEMPT = ROOT / "results/rsi-v25/executable-20261001/V25_ATTEMPT.json"
ADJUDICATION = ATTEMPT.parent / "V25_FINAL_ADJUDICATION.json"


def run():
    freeze = committed_freeze()
    if freeze["runtime_versions"] != runtime_versions():
        raise ValueError("Canonical runtime differs from the committed freeze")
    calibration = json.loads((HERE / "PUBLIC_DEVELOPMENT_CALIBRATION.json").read_text())
    native = json.loads((HERE / "NATIVE_HOST_CALIBRATION.json").read_text())
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    # The marker is the canonical record itself, not a deletable transient lock.
    descriptor = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    attempt = {"schema": "mira-genesis-rsi-v25-canonical-attempt-v1",
               "freeze_sha256": freeze["freeze_sha256"], "status": "STARTED",
               "track": "A", "scientific_external_model_calls": 0,
               "runtime_versions": freeze["runtime_versions"], "transfer": {},
               "native_seeded": {row["task_id"]: row["seeded"] for row in native["tasks"]},
               "canonical_attempts": 1, "negative_preservation_required": True}
    with os.fdopen(descriptor, "w") as output:
        json.dump(attempt, output, sort_keys=True, indent=2)
        output.write("\n")
    try:
        def preserve_meta(rows):
            attempt["meta"] = rows
            write_json(ATTEMPT, attempt)
        attempt["meta"] = run_meta(calibration, checkpoint=preserve_meta)
        write_json(ATTEMPT, attempt)
        selected = attempt["meta"]["g2_meta"]["selected"]
        source = render_source(selected["params"])
        attempt["retention"] = check_l4(source)
        attempt["witness"] = confirm_witness(source, selected["parent_choice_witness"])
        attempt["pre_gates"] = pre_gates(attempt["meta"], attempt["retention"], attempt["witness"], calibration)
        write_json(ATTEMPT, attempt)
        if all(attempt["pre_gates"].values()):
            policies = {"g3": source, "g2": predecessor_source(),
                        "g1_meta_successor": render_source(attempt["meta"]["g1_meta"]["selected"]["params"])}
            policies.update({"ablation_" + axis: render_source(params)
                             for axis, params in zip(acquired_components(selected["params"]),
                                                     ablations(selected["params"]))})
            attempt["status"] = "TRANSFER_STARTED"
            write_json(ATTEMPT, attempt)
            for arm, policy in policies.items():
                def preserve_native(rows):
                    attempt["transfer"][arm] = rows
                    write_json(ATTEMPT, attempt)
                attempt["transfer"][arm] = run_native_policy(policy, native, checkpoint=preserve_native)
                write_json(ATTEMPT, attempt)
                print(f"Preserved native arm {arm}", flush=True)
        attempt["status"] = "COMPLETED"
        verdict = adjudicate(attempt, freeze, calibration)
        write_json(ATTEMPT, attempt)
        write_json(ADJUDICATION, verdict)
        print(json.dumps(verdict, indent=2), flush=True)
        return verdict
    except BaseException as error:
        attempt["status"] = "INSTRUMENT_ABORTED"
        attempt["instrument_error"] = {"type": type(error).__name__, "message": str(error)}
        write_json(ATTEMPT, attempt)
        write_json(ADJUDICATION, {"verdict": "PRESERVED_INSTRUMENT_ABORT",
                                "v25_l5_positive": False, "freeze_sha256": freeze["freeze_sha256"],
                                "partial_evidence_preserved": True})
        raise


if __name__ == "__main__":
    run()
