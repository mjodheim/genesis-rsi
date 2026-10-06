"""Prospective OE1 native multi-domain campaign."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiment.l9_oe1 import diagnostic_constructor
from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank, engine as v36

ARMS = ("diagnostic", "archive", "greedy", "cold")
EPOCHS = bank.EPOCHS
TASKS_PER_EPOCH = bank.TASKS_PER_EPOCH
FREEZE = ROOT / "experiment/l9_oe1/NATIVE_PROSPECTIVE_FREEZE.json"
RESULT = ROOT / "results/l9-oe1/native-prospective-20261005/REPORT.json"

APPARATUS_FILES = (
    "experiment/l9_oe1/diagnostic_constructor.py",
    "experiment/l9_oe1/native_prospective.py",
    "experiment/l9_oe1/NATIVE_PROSPECTIVE_PROTOCOL.md",
    "experiment/rsi_v35/native.py",
    "experiment/rsi_v36/bank.py",
    "experiment/rsi_v36/engine.py",
)


def population():
    return {
        f"{seed}-{domain}": bank.stream(
            seed,
            domain,
            epochs=EPOCHS,
            tasks_per_epoch=TASKS_PER_EPOCH,
        )
        for seed in bank.FRESH_SEEDS
        for domain in native.DOMAINS
    }


def source_hashes():
    return {
        path: digest_bytes((ROOT / path).read_bytes())
        for path in APPARATUS_FILES
    }


def freeze_value():
    tasks = population()
    base = {
        "schema": "mira-genesis-l9-oe1-native-prospective-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_PROSPECTIVE_BEHAVIOR",
        "fresh_seeds": list(bank.FRESH_SEEDS),
        "domains": list(native.DOMAINS),
        "epochs": EPOCHS,
        "tasks_per_epoch": TASKS_PER_EPOCH,
        "tasks_per_arm": sum(map(len, tasks.values())),
        "arms": list(ARMS),
        "max_evaluations_per_task": 14,
        "population_sha256": digest(tasks),
        "streams": {key: digest(value) for key, value in tasks.items()},
        "source_sha256": source_hashes(),
        "acceptance_predicates": [
            "all_committed_tasks_retained",
            "all_tasks_within_fourteen_calls",
            "diagnostic_solves_every_task",
            "complete_diagnostic_acquisition",
            "positive_each_diagnostic_transfer_epoch",
            "diagnostic_beats_all_controls_each_seed_domain",
            "diagnostic_cost_no_greater_than_cold",
            "strict_diagnostic_archive_and_solved_growth",
            "diagnostic_branching_and_rediscovery",
            "diagnostic_receipts_replay",
        ],
    }
    return {**base, "freeze_sha256": digest(base)}


def verify_freeze():
    expected = freeze_value()
    actual = json.loads(FREEZE.read_text())
    if actual != expected:
        raise ValueError("OE1 native prospective freeze differs from committed apparatus")
    return True


def _run_arm(tasks, arm, isolated):
    history = {}
    rows = []
    epochs = []

    for epoch in range(EPOCHS):
        previous = history
        epoch_rows = []
        subset = [task for task in tasks if task["epoch"] == epoch]
        start = sum(task["epoch"] < epoch for task in tasks)

        for local_index, task in enumerate(subset):
            position = start + local_index
            if arm == "diagnostic":
                row = diagnostic_constructor.episode(
                    task,
                    position,
                    history,
                    isolated=isolated,
                )
                diagnostic_constructor.verify_episode(
                    task,
                    position,
                    history,
                    row,
                    isolated=isolated,
                )
            else:
                row = v36.episode(
                    task,
                    position,
                    history,
                    arm,
                    isolated=isolated,
                )
                v36.verify_episode(
                    task,
                    position,
                    history,
                    arm,
                    row,
                    isolated=isolated,
                )

            epoch_rows.append(row)
            rows.append(row)
            history = v36.history_from([row], history)

        summary = (
            diagnostic_constructor.summary(epoch_rows, previous)
            if arm == "diagnostic"
            else v36.summary(epoch_rows, previous)
        )
        epochs.append(summary)

    total = (
        diagnostic_constructor.summary(rows)
        if arm == "diagnostic"
        else v36.summary(rows)
    )
    return {
        "arm": arm,
        "epochs": epochs,
        "total": total,
        "max_task_evaluations": max(row["charged_evaluations"] for row in rows),
        "rows": rows,
    }


def _cohort(item, isolated):
    label, tasks = item
    arms = {
        arm: _run_arm(tasks, arm, isolated)
        for arm in ARMS
    }
    return label, arms


def adjudicate(cohorts):
    predicates = {
        "all_committed_tasks_retained": True,
        "all_tasks_within_fourteen_calls": True,
        "diagnostic_solves_every_task": True,
        "complete_diagnostic_acquisition": True,
        "positive_each_diagnostic_transfer_epoch": True,
        "diagnostic_beats_all_controls_each_seed_domain": True,
        "diagnostic_cost_no_greater_than_cold": True,
        "strict_diagnostic_archive_and_solved_growth": True,
        "diagnostic_branching_and_rediscovery": True,
        "diagnostic_receipts_replay": True,
    }

    expected = EPOCHS * TASKS_PER_EPOCH
    for label, arms in cohorts.items():
        for arm in ARMS:
            predicates["all_committed_tasks_retained"] &= (
                arms[arm]["total"]["tasks"] == expected
            )
            predicates["all_tasks_within_fourteen_calls"] &= (
                arms[arm]["max_task_evaluations"] <= 14
            )

        diagnostic = arms["diagnostic"]
        predicates["diagnostic_solves_every_task"] &= (
            diagnostic["total"]["solved"] == expected
        )
        predicates["complete_diagnostic_acquisition"] &= all(
            row["solved"] == row["tasks"]
            for row in diagnostic["epochs"][:3]
        )
        predicates["positive_each_diagnostic_transfer_epoch"] &= all(
            row["first_solving_semantics"] >= 1
            for row in diagnostic["epochs"][3:]
        )

        transfer_solved = sum(
            row["solved"] for row in diagnostic["epochs"][3:]
        )
        predicates["diagnostic_beats_all_controls_each_seed_domain"] &= all(
            transfer_solved
            > sum(row["solved"] for row in arms[control]["epochs"][3:])
            for control in ("archive", "greedy", "cold")
        )
        predicates["diagnostic_cost_no_greater_than_cold"] &= (
            diagnostic["total"]["evaluations"]
            <= arms["cold"]["total"]["evaluations"]
        )

        old_archive = old_solved = 0
        for row in diagnostic["epochs"]:
            predicates["strict_diagnostic_archive_and_solved_growth"] &= (
                row["archive_size"] > old_archive
                and row["solved_semantic_size"] > old_solved
            )
            old_archive = row["archive_size"]
            old_solved = row["solved_semantic_size"]

        predicates["diagnostic_branching_and_rediscovery"] &= (
            diagnostic["epochs"][2]["branches"] == 4
            and diagnostic["total"]["rediscoveries"] > 0
        )

        # Every diagnostic row was independently replayed inside _run_arm.
        predicates["diagnostic_receipts_replay"] &= True

    totals = {
        arm: {
            key: sum(
                cohorts[label][arm]["total"].get(key, 0)
                for label in cohorts
            )
            for key in (
                "tasks",
                "solved",
                "evaluations",
                "first_solving_semantics",
                "rediscoveries",
            )
        }
        for arm in ARMS
    }

    positive = all(predicates.values())
    return {
        "schema": "mira-genesis-l9-oe1-native-prospective-adjudication-v1",
        "predicates": predicates,
        "totals": totals,
        "scoped_sustained_native_assay_passed": positive,
        "verdict": (
            "POSITIVE_SCOPED_SUSTAINED_NATIVE_ASSAY"
            if positive
            else "VALID_NEGATIVE_SCOPED_SUSTAINED_NATIVE_ASSAY"
        ),
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
    }


def run(*, isolated=True, workers=6):
    verify_freeze()
    items = list(population().items())
    cohorts = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for label, arms in pool.map(
            lambda item: _cohort(item, isolated),
            items,
        ):
            cohorts[label] = arms

    compact = {
        label: {
            arm: {
                "epochs": value["epochs"],
                "total": value["total"],
                "max_task_evaluations": value["max_task_evaluations"],
            }
            for arm, value in arms.items()
        }
        for label, arms in cohorts.items()
    }
    return {
        "schema": "mira-genesis-l9-oe1-native-prospective-report-v1",
        "freeze_sha256": freeze_value()["freeze_sha256"],
        "population_sha256": freeze_value()["population_sha256"],
        "isolated": isolated,
        "cohorts": compact,
        "adjudication": adjudicate(cohorts),
        "claim_boundary": (
            "FINITE_PROSPECTIVE_MULTI_DOMAIN_ASSAY_NOT_ASYMPTOTIC_GENERAL_L9"
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--output", type=Path, default=RESULT)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--no-isolation", action="store_true")
    args = parser.parse_args(argv)

    if args.action == "freeze":
        value = freeze_value()
        print(json.dumps(value, sort_keys=True))
        return

    report = run(
        isolated=not args.no_isolation,
        workers=args.workers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps(report["adjudication"], sort_keys=True))


if __name__ == "__main__":
    main()
