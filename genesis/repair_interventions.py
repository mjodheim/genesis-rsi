"""The repair agent's components, each changed alone, and how its attempts end.

Two things a repair domain gives ``intervention_diagnosis``:

``ended`` reads one recorded attempt and says where it stopped: nothing was ever tested (the
model submitted no candidate, none could be applied, or it never submitted), or candidates were
tested and failed. It also says how much of the envelope was left. No model is involved.

``VARIANTS`` are single changes to the seed agent. Each names the component it changes:

    reading       inspection tools   a read with a malformed line number is answered, and a
                                     refusal says why
    persistence   stopping rule      a round that brings nothing does not end the case
    depth         budget split       one round of seven inspections instead of two of three
    budget        envelope           twice the requests, validations and rounds
    model         model              a stronger model, same everything else
    oracle        localizer          the developers' own edit sites as the places to look

The variants are written by hand; the diagnosis chooses among them. ``oracle`` reads the fixed
revision: it bounds what any localizer could bring and can never be part of the agent.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Mapping, Sequence

from genesis.openrouter_repair import inspect_tool
from genesis.repair_lineage import SEED_GENOME, Envelope

CONTROL = "control"
STRONGER_MODEL = "anthropic/claude-sonnet-5.5"
STRONGER_MODEL_MAX_PRICE = (("completion", 12.0), ("prompt", 2.5), ("request", 0.0))
REFUSAL = "Inspection refused: "
# The standard inspector answers a refused read with these few characters and nothing else; records keep
# only the length of an answer, and no successful read of a source file is that short.
REFUSED_LENGTHS = frozenset(len(REFUSAL + name) for name in ("ValueError", "OSError", "KeyError", "TypeError"))
READ_USAGE = ("read_file takes `path` (as shown in the evidence or by search_files) and an optional integer "
              "`start` line; it returns 200 numbered lines from there.")

VARIANTS = {
    "reading": {"component": "inspection tools"},
    "persistence": {"component": "stopping rule"},
    "depth": {"component": "budget split"},
    "budget": {"component": "envelope"},
    "model": {"component": "model"},
    "oracle": {"component": "localizer"},
}


def tolerant_inspect(root: Path, evidence: Mapping, name: str, arguments: dict) -> str:
    """``inspect_tool`` that takes the first number of whatever was given as a start line and explains refusals."""
    if name == "read_file" and isinstance(arguments, dict):
        given = arguments.get("start", arguments.get("search_start", arguments.get("line", 1)))
        if isinstance(given, (list, tuple)) and given:
            given = given[0]
        found = re.search(r"\d+", str(given))
        arguments = {"path": arguments.get("path"), "start": int(found.group()) if found else 1}
    try:
        return inspect_tool(root, evidence, name, arguments)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return REFUSAL + (str(error) or type(error).__name__)[:120] + ". " + READ_USAGE


def configuration(variant: str, model: str) -> dict:
    """Everything that defines one arm, as plain data: it is what the preregistration records."""
    if variant != CONTROL and variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    search = dict(SEED_GENOME["search"])
    envelope = Envelope(model=model)
    if variant == "depth":
        search = {"inspection_requests": 7, "candidates_per_round": 4, "rounds": 1}
    if variant == "budget":
        search["rounds"] = 4
        envelope = Envelope(model=model, requests=16, validations=12)
    if variant == "model":
        envelope = Envelope(model=STRONGER_MODEL, max_price=STRONGER_MODEL_MAX_PRICE)
    return {
        "component": None if variant == CONTROL else VARIANTS[variant]["component"],
        "search": search, "envelope": envelope.record(),
        "persist": variant == "persistence",
        "tolerant_reading": variant == "reading",
        "locations": "developers' edit sites" if variant == "oracle" else "collected evidence",
    }


def oracle_locations(sites: Sequence[Mapping], limit: int = 6) -> list[list]:
    """The first line of each edit site, at most ``limit`` of them."""
    return [[site["path"], int(site["first"])] for site in sites][:limit]


def ended(attempt: Mapping, *, requests: int, validations: int) -> dict:
    """Where one recorded attempt stopped and what it left unused. Refused reads are counted for the
    standard inspector only: the tolerant one answers at length."""
    calls = attempt.get("calls") or []
    verdicts = attempt.get("verdicts") or []
    reads = [item for call in calls for item in call.get("inspections") or [] if item["tool"] == "read_file"]
    refused = sum(item["characters"] in REFUSED_LENGTHS for item in reads)
    if attempt.get("solved"):
        how = "repaired"
    elif not verdicts:
        submitted = [call for call in calls if call.get("submitted") is not None]
        if any(call.get("malformed") for call in calls) and not submitted:
            how = "nothing tested: no usable answer"
        elif not submitted:
            how = "nothing tested: never submitted"
        elif not sum(call["submitted"] for call in submitted):
            how = "nothing tested: empty submission"
        else:
            how = "nothing tested: edits could not be applied"
    else:
        stops = Counter(verdict.get("stopped_at") for verdict in verdicts)
        how = ("tested: other tests break" if stops.get("full_suite")
               else "tested: the failing tests still fail" if stops.get("failing_tests")
               else "tested: does not compile")
    return {"how": how, "requests_left": max(0, requests - len(calls)),
            "validations_left": max(0, validations - len(verdicts)), "reads": len(reads), "refused_reads": refused}


def stops(attempts: Sequence[Mapping], *, requests: int, validations: int) -> dict:
    """How a set of attempts ended, and how much envelope the failed ones left."""
    rows = [ended(attempt, requests=requests, validations=validations) for attempt in attempts]
    failed = [row for row in rows if row["how"] != "repaired"]
    untested = [row for row in failed if row["how"].startswith("nothing tested")]
    return {
        "attempts": len(rows), "repaired": len(rows) - len(failed),
        "how_failed_attempts_ended": dict(sorted(Counter(row["how"] for row in failed).items())),
        "failed_with_nothing_tested": len(untested),
        "of_which_with_a_refused_read": sum(row["refused_reads"] > 0 for row in untested),
        "failed_with_requests_left": sum(row["requests_left"] > 0 for row in failed),
        "failed_with_validations_left": sum(row["validations_left"] > 0 for row in failed),
        "refused_reads": {"repaired": sum(row["refused_reads"] for row in rows if row["how"] == "repaired"),
                          "failed": sum(row["refused_reads"] for row in failed)},
    }
