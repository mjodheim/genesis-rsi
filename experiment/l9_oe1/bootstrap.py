"""Bootstrap the persistent OE1 experience graph from the consumed V53 population."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.store import ExperienceStore
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import bank, engine as v53
from experiment.rsi_v53.benchmark import _record_abstract, _record_exact


def import_v53(store, *, code_sha, isolated=False):
    improver = ImproverGenome(
        exact_top_k=2,
        abstract_top_k=1,
        scaffold_top_k=v53.SCAFFOLD_TOP_K,
        scaffold_pool=8,
        scaffold_min_width=v53.SCAFFOLD_MIN_WIDTH,
        scaffold_root_quality_max=v53.SCAFFOLD_ROOT_QUALITY_MAX,
    )
    improver_sha = store.upsert_improver(improver, generation=0)
    run_id = store.create_run(
        code_sha=code_sha,
        scope="CONSUMED_V53_BOOTSTRAP_FOR_OE1_REPLAY",
        metadata={
            "source": "V53 consumed prospective population",
            "seeds": list(bank.FRESH_SEEDS),
            "fresh_evidence": False,
            "tuning_allowed": True,
        },
    )

    totals = {"tasks": 0, "solved": 0, "evaluations": 0}
    with tempfile.TemporaryDirectory(prefix="oe1-v53-bootstrap-") as td:
        root = Path(td)
        for seed in bank.FRESH_SEEDS:
            exact = ExperimentalMemory(root / f"{seed}-exact.db")
            abstract = AbstractionMemory(root / f"{seed}-abstract.db")
            baseline = ExperimentalMemory(root / f"{seed}-v51.db")
            try:
                for position, task in enumerate(bank.stream(seed)):
                    cold = v32.episode(
                        task, position, {}, "cold", 25, isolated=isolated
                    )

                    x51 = v51.episode(
                        task, position, baseline, isolated=isolated
                    )
                    x51.update(
                        window=task["window"],
                        width=task["width"],
                        task_family=task["family"],
                    )
                    _record_exact(
                        baseline,
                        x51,
                        cold,
                        task,
                        x51["routing"]["retrieved_strategy_ids"],
                    )
                    v51.remember(baseline, x51)

                    row = v53.episode(
                        task,
                        position,
                        exact,
                        abstract,
                        isolated=isolated,
                    )
                    row.update(
                        window=task["window"],
                        width=task["width"],
                        task_family=task["family"],
                    )
                    _record_exact(
                        exact,
                        row,
                        cold,
                        task,
                        row["routing"]["exact_strategy_ids"],
                    )
                    _record_abstract(abstract, row, x51, task)
                    v53.remember(exact, abstract, row)

                    store.record_episode(
                        run_id=run_id,
                        improver_sha256=improver_sha,
                        task=task,
                        row=row,
                    )
                    totals["tasks"] += 1
                    totals["solved"] += int(row["solved"])
                    totals["evaluations"] += row["charged_evaluations"]
            finally:
                exact.close()
                abstract.close()
                baseline.close()
    return {
        "run_id": run_id,
        "improver_sha256": improver_sha,
        **totals,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args(argv)
    store = ExperienceStore(args.dsn)
    try:
        result = import_v53(
            store, code_sha=args.code_sha, isolated=args.isolated
        )
        print(result)
    finally:
        store.close()


if __name__ == "__main__":
    main()
