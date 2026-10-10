"""Descendants of the fault localizer built without a model, from what the archive already holds.

A lineage keeps every module a model wrote, promoted or not. A rejected module is not useless:
it localizes cases its parent misses and misses others. A *composite* merges the answers of two
members of the archive: the first ``lead`` locations of one, then the locations of the other
that add a new place, then what remains. Composites are data, they nest, and choosing one costs
arithmetic only, because each member's answers are computed once.

The choice is made on training cases. A composite replaces the champion only under the rule of
the lineage, on selection cases. Validation cases are scored once at the end.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from genesis.localizer_lineage import MAX_LOCATIONS, WINDOW, compare, evaluate, promotes
from genesis.trust_root import digest_of

COMPOSITE_SCHEMA = "genesis-localizer-composite-v1"


def composite(first: str, second: str, lead: int) -> dict:
    if not 1 <= lead < MAX_LOCATIONS:
        raise ValueError("lead must leave room for the second member")
    body = {"schema": COMPOSITE_SCHEMA, "first": first, "second": second, "lead": lead}
    return {**body, "name": "c-" + digest_of(body)[:12]}


def adds_a_place(location: Sequence, kept: Sequence[Sequence]) -> bool:
    """False when a kept location in the same file already stands within half a window."""
    return all(path != location[0] or abs(line - location[1]) > WINDOW // 2 for path, line in kept)


def merge(first: Sequence[Sequence], second: Sequence[Sequence], lead: int) -> list[list]:
    kept = [list(item) for item in first[:lead]]
    for source in (second, first[lead:]):
        for item in source:
            if len(kept) < MAX_LOCATIONS and adds_a_place(item, kept):
                kept.append(list(item))
    for item in list(first[lead:]) + list(second):
        if len(kept) < MAX_LOCATIONS and list(item) not in kept:
            kept.append(list(item))
    return kept[:MAX_LOCATIONS]


def answers_of(member: Mapping, answers: Mapping[str, Mapping[str, list]]) -> dict[str, list]:
    """Locations of a composite on every case, from the stored answers of its two members."""
    first, second = answers[member["first"]], answers[member["second"]]
    return {case: merge(first.get(case, []), second.get(case, []), member["lead"]) for case in first}


def scored(locations: Mapping[str, list], truth: Mapping, cases: Sequence[str]) -> dict:
    return evaluate({case: {"locations": locations.get(case, [])} for case in cases}, truth, cases)


def proposals(champion: str, archive: Sequence[str]) -> list[dict]:
    """Every composite that pairs the champion with another member, in either order."""
    found = []
    for other in archive:
        if other == champion:
            continue
        for lead in range(1, MAX_LOCATIONS):
            found.append(composite(champion, other, lead))
            found.append(composite(other, champion, lead))
    return found


def best_proposal(champion: str, answers: Mapping[str, Mapping[str, list]], truth: Mapping,
                  training: Sequence[str]) -> tuple[dict, dict] | None:
    """The composite that localizes the most training cases, if it beats the champion there."""
    base = scored(answers[champion], truth, training)["localized"]
    ranked = []
    for member in proposals(champion, sorted(answers)):
        evaluation = scored(answers_of(member, answers), truth, training)
        if evaluation["localized"] > base:
            ranked.append((-evaluation["localized"], -evaluation["any_site"], member["name"], member, evaluation))
    if not ranked:
        return None
    _, _, _, member, evaluation = min(ranked, key=lambda row: row[:3])
    return member, evaluation


def evolve(champion: str, answers: dict, truth: Mapping, training: Sequence[str], selection: Sequence[str], *,
           generations: int = 5, margin: int = 5, alpha: float = 0.05) -> dict:
    """Recombine until a generation yields no promoted composite. ``answers`` gains the promoted ones."""
    chain, attempts, members = [champion], [], {}
    for generation in range(1, generations + 1):
        found = best_proposal(champion, answers, truth, training)
        if found is None:
            attempts.append({"generation": generation, "outcome": "no composite better on training"})
            break
        member, training_evaluation = found
        locations = answers_of(member, answers)
        comparison = compare(scored(locations, truth, selection), scored(answers[champion], truth, selection))
        promoted = promotes(comparison, margin, alpha)
        attempts.append({"generation": generation, "member": member, "parent": champion,
                         "archive_size": len(answers), "training_localized": training_evaluation["localized"],
                         "selection": {key: comparison[key] for key in
                                       ("parent", "child", "gained", "lost", "one_sided_sign_test")},
                         "outcome": "promoted" if promoted else "rejected on unseen cases"})
        if not promoted:
            break
        members[member["name"]] = member
        answers[member["name"]] = locations
        champion = member["name"]
        chain.append(champion)
    return {"chain": chain, "attempts": attempts, "members": members}
