#!/usr/bin/env python3
"""Attribute the failures of sealed trials to components, without any model.

Reads the paired repair trial DEV_LOCALIZED_REPAIR1 and the improvement trial IMPROVE1, both
already sealed, and writes ``experiment/g12/FAILURE_ATTRIBUTION1.json``. Nothing is run and no
sealed file changes.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from genesis import failure_attribution as attribution  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

REPAIR = ROOT / "experiment/localizer/LOCALIZER1/DEV_LOCALIZED_REPAIR1_RESULT.json"
IMPROVEMENT = ROOT / "experiment/improvement/IMPROVE1/RESULT.json"
OUT = ROOT / "experiment/g12/FAILURE_ATTRIBUTION1.json"


def main() -> None:
    repair = json.loads(REPAIR.read_text(encoding="utf-8"))
    improvement = json.loads(IMPROVEMENT.read_text(encoding="utf-8"))
    arms = {arm: attribution.repair_attribution(repair, arm) for arm in ("stack_trace", "localizer")}
    before, after = arms["stack_trace"]["conditions"][0], arms["localizer"]["conditions"][0]
    check = {
        "condition": before["condition"],
        "met_before": before["met"], "met_after": after["met"],
        "predicted_gain_from_the_stack_trace_arm": attribution.predicted_gain(before, after["met"] - before["met"]),
        "observed_gain": arms["localizer"]["succeeded"] - arms["stack_trace"]["succeeded"],
        "note": "the prediction uses only the arm without the rewritten localizer; the observation is the paired trial",
    }
    body = {
        "schema": "genesis-failure-attribution-report-v1",
        "sources": {"repair": repair["result_digest"], "improvement": improvement["result_digest"]},
        "development_records_only": True,
        "repair": arms, "repair_prediction_check": check,
        "improvement": attribution.improvement_attribution(improvement["records"]["isolated"]),
    }
    OUT.write_text(json.dumps({**body, "report_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"repair_limiting": {arm: item["limiting_component"] for arm, item in arms.items()},
                      "repair_gain": {arm: item["estimated_gain_by_component"] for arm, item in arms.items()},
                      "check": check, "improvement_first_unmet": body["improvement"]["failures_by_first_unmet_condition"],
                      "improvement_limiting": body["improvement"]["limiting_component"]}, indent=1))


if __name__ == "__main__":
    main()
