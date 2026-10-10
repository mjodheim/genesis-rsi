"""Where does a system lose its cases, and which of its components should change first?

A trial leaves one record per case: what each stage produced and whether the case succeeded.
This module reads such records without any model. A *condition* is something a component is
responsible for ("the evidence covers the place of the fix"). For each condition it reports how
often success follows when the condition holds and when it does not, and from the difference an
estimate of the cases that would be gained if the component always met it.

The estimate is observational: cases where a condition fails may simply be harder. It ranks
components for the next experiment; only an experiment that changes a component shows that it
limits the system. ``predicted_gain`` states what the estimate expects from a given change, so
that a paired trial can contradict it.

Nothing here is specific to a language or to repair: a domain supplies conditions over its own
records.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

SCHEMA = "genesis-failure-attribution-v1"


@dataclass(frozen=True)
class Condition:
    name: str
    component: str
    holds: Callable[[Mapping], bool]


def attribute(cases: Sequence[Mapping], conditions: Sequence[Condition],
              succeeded: Callable[[Mapping], bool]) -> dict:
    """Per condition, in pipeline order: success with and without it, and the estimated gain of always meeting it."""
    rows = []
    first_unmet: dict[str, int] = {}
    outcomes = [bool(succeeded(case)) for case in cases]
    held = [[bool(condition.holds(case)) for condition in conditions] for case in cases]
    for flags, won in zip(held, outcomes):
        if not won:
            name = next((condition.name for condition, flag in zip(conditions, flags) if not flag), "every condition met")
            first_unmet[name] = first_unmet.get(name, 0) + 1
    for index, condition in enumerate(conditions):
        # A later condition is judged only where the earlier ones hold: otherwise the stage
        # nearest to the outcome would always look like the one that limits everything.
        reached = [(flags, won) for flags, won in zip(held, outcomes) if all(flags[:index])]
        met = [won for flags, won in reached if flags[index]]
        unmet = [won for flags, won in reached if not flags[index]]
        row = {"condition": condition.name, "component": condition.component,
               "cases_where_earlier_conditions_hold": len(reached),
               "met": len(met), "succeeded_when_met": sum(met),
               "unmet": len(unmet), "succeeded_when_unmet": sum(unmet),
               "failures_when_unmet": len(unmet) - sum(unmet)}
        if met and unmet:
            difference = sum(met) / len(met) - sum(unmet) / len(unmet)
            row["estimated_gain_if_always_met"] = round(max(0.0, difference) * len(unmet), 2)
        else:
            row["estimated_gain_if_always_met"] = None if unmet else 0.0
        rows.append(row)
    by_component: dict[str, float] = {}
    for row in rows:
        if row["estimated_gain_if_always_met"] is not None:
            by_component[row["component"]] = round(by_component.get(row["component"], 0.0)
                                                   + row["estimated_gain_if_always_met"], 2)
    limiting = max(by_component, key=lambda name: by_component[name]) if by_component and max(by_component.values()) > 0 else None
    return {"schema": SCHEMA, "cases": len(cases), "succeeded": sum(outcomes), "conditions": rows,
            "failures_by_first_unmet_condition": dict(sorted(first_unmet.items(), key=lambda item: -item[1])),
            "estimated_gain_by_component": dict(sorted(by_component.items(), key=lambda item: -item[1])),
            "limiting_component": limiting,
            "estimate_is_observational": True}


def predicted_gain(row: Mapping, newly_met: int) -> float | None:
    """Cases the estimate expects to gain when ``newly_met`` more cases meet the condition of ``row``."""
    if not row["met"] or not row["unmet"]:
        return None
    difference = row["succeeded_when_met"] / row["met"] - row["succeeded_when_unmet"] / row["unmet"]
    return round(max(0.0, difference) * newly_met, 2)


# -- the repair bench ---------------------------------------------------------------------------


def repair_views(result: Mapping, arm: str) -> list[dict]:
    """One flat record per usable case of a paired repair trial, for one arm."""
    return [{"case": case["case"], "covered": bool(case["fix_covered"][arm]), **case["arms"][arm]}
            for case in result["cases"] if case.get("usable", True)]


def _stops(view: Mapping) -> set[str]:
    return {verdict.get("stopped_at") for verdict in view.get("verdicts") or []}


REPAIR_CONDITIONS = (
    Condition("the evidence covers the place of the fix", "localizer", lambda view: view["covered"]),
    Condition("a candidate reached validation", "proposer", lambda view: bool(view.get("verdicts"))),
    Condition("a candidate compiles", "proposer", lambda view: bool(_stops(view) - {"compile"})),
    Condition("a candidate passes the failing tests", "proposer",
              lambda view: bool(_stops(view) & {"full_suite", "passed"})),
)


def repair_attribution(result: Mapping, arm: str) -> dict:
    return attribute(repair_views(result, arm), REPAIR_CONDITIONS, lambda view: bool(view["solved"]))


# -- chained program improvement ----------------------------------------------------------------


def _reasons(record: Mapping) -> set[str]:
    return {attempt.get("reason") for attempt in record.get("attempts") or [] if attempt.get("step") == 1}


IMPROVEMENT_CONDITIONS = (
    Condition("a rewrite could be run", "writer: form", lambda record: bool(_reasons(record) - {"unusable"})),
    Condition("a rewrite behaves like the original on the recorded calls", "writer: behaviour",
              lambda record: bool(_reasons(record) - {"unusable", "behaviour differs", "did not finish"})),
    Condition("a rewrite is cheaper", "writer: cost", lambda record: bool(_reasons(record) & {"accepted", "breaks tests"})),
)


def improvement_attribution(records: Sequence[Mapping]) -> dict:
    return attribute(records, IMPROVEMENT_CONDITIONS, lambda record: record["chain_length"] > 0)
