#!/usr/bin/env python3
"""Scientific gate for the V2 retrospective study (NOT external promotion)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.v2.gates import assess_development, validate_assessment

STUDY=ROOT/"experiment/v2/V2_RETROSPECTIVE_DISCOVERY_20261008.json"
GATE=ROOT/"experiment/v2/V2_RETROSPECTIVE_PROMOTION_GATE_20261008.json"

if __name__=="__main__":
    result=validate_assessment(assess_development(json.loads(STUDY.read_text())))
    if GATE.exists() and json.loads(GATE.read_text())!=result:
        raise RuntimeError("refusing to overwrite changed official gate")
    GATE.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("V2_DEVELOPMENT_COMPILE_GAIN",result["development_compilation_gain"])
    print("V2_REGRESSION_CASES",result["cases_with_regression"])
    print("V2_INDEPENDENT_PROMOTION",result["production_promotion_allowed"])
    print("V2_GATES",result["gate_reasons"])
