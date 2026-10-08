#!/usr/bin/env python3
"""Genesis V2 research prototype: retrospective nine-case discovery.

Research-only. Both partitions come from previously released, exposed G11
cases. This script DOES NOT repair a new bug, run arbitrary generated code,
read human patches, modify V1, or promote a descendant.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.v2.discovery import retrospective_study, validate_study
from genesis.v2.traces import create_catalogue, validate_catalogue
from genesis.trust_root import digest_of

HISTORIC = Path("/home/anthony/benchmarks")
BATCHES = (
    ("g11-fresh-three-20261008/FROZEN_3REPO_CANDIDATES.json",
     "G11_3REPO_RESULTS_20261008.json"),
    ("g11-second-batch-20261008/FROZEN_SECOND_BATCH_CANDIDATES.json",
     "G11_SECOND_BATCH_RESULTS_20261008.json"),
    ("g11-third-batch-20261008/FROZEN_THIRD_BATCH_CANDIDATES.json",
     "G11_THIRD_BATCH_RESULTS_20261008.json"),
)
DATA = ROOT / "experiment/v2/V2_RELEASED_DEVELOPMENT_CATALOGUE_20261008.json"
STUDY = ROOT / "experiment/v2/V2_RETROSPECTIVE_DISCOVERY_20261008.json"


def run() -> dict:
    batches = []
    for frozen_rel, result_rel in BATCHES:
        frozen = json.loads((HISTORIC / frozen_rel).read_text(encoding="utf-8"))
        result = json.loads(
            (ROOT / "experiment/g11" / result_rel).read_text(encoding="utf-8")
        )
        batches.append((frozen, result))
    catalogue = validate_catalogue(create_catalogue(batches))
    expected = (
        "Math-53", "Csv-16", "Collections-24",
        "Gson-2", "Jsoup-68", "JacksonCore-11",
        "Cli-34", "Time-22", "JxPath-12",
    )
    actual = tuple(item["case_id"] for item in catalogue["cases"])
    if actual != expected:
        raise RuntimeError("unexpected G11 corpus; refuse accidental new holdout")
    result = validate_study(retrospective_study(
        catalogue, training_case_ids=expected[:6],
        development_check_case_ids=expected[6:],
        top_k=8, max_generations=2,
    ))
    DATA.parent.mkdir(parents=True, exist_ok=True)
    for path, value in ((DATA, catalogue), (STUDY, result)):
        if path.exists() and json.loads(path.read_text()) != value:
            raise RuntimeError(f"existing immutable V2 evidence changed: {path}")
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    study = run()
    print("GENESIS_V2_RETROSPECTIVE_DEVELOPMENT")
    print("EXPOSED_PROJECTS", len(study["training_cases"]) + len(study["development_check_cases"]))
    print("GENOME_GENERATION", study["training_search"]["learned_genome"]["generation"])
    print("MUTANTS_EVALUATED", study["training_search"]["total_mutants_considered"])
    print("BASELINE_DEV_CHECK_COMPILED", study["baseline_check"]["compile_valid_candidates"])
    print("DESCENDANT_DEV_CHECK_COMPILED", study["descendant_check"]["compile_valid_candidates"])
    print("DIFFERENCE", study["development_compilation_gain"])
    print("FULL_SUITE_IMPROVEMENT", study["development_full_suite_gain"])
    print("SCIENTIFIC_DECISION", study["decision"])
    print("RESULT_DIGEST", study["study_digest"])
