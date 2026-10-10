"""Which component limits a system? Change one at a time on the cases it fails, and count.

``failure_attribution`` compares success rates where a condition holds and where it does not. It
cannot tell a component that loses cases from a component that merely fails on hard ones. Here
nothing is inferred from rates. The system is run again on cases it failed, once unchanged (the
*control*) and once per *variant*, each variant changing a single component. A variant is
compared with the control on the same cases: cases only the variant succeeds on against cases
only the control succeeds on, with an exact one-sided sign test. The control arm is what keeps a
case that failed by chance from being read as recovered by a change.

A component is named as limiting when its variant gains at least ``margin`` cases net and the
test passes ``level``. Cases that succeed under no arm are reported as such: no component that
was changed explains them.

Nothing here is specific to repair or to a language. A domain supplies the variants and runs them.
"""
from __future__ import annotations

import hashlib
from math import comb
from typing import Mapping, Sequence

SCHEMA = "genesis-intervention-diagnosis-v1"
ORDER_DOMAIN = "genesis-intervention-order-v1|"


def order(case: str, arms: Sequence[str]) -> list[str]:
    """The arms of one case, rotated by the case's name so that no arm always runs first."""
    arms = list(arms)
    shift = int(hashlib.sha256((ORDER_DOMAIN + case).encode()).hexdigest(), 16) % len(arms)
    return arms[shift:] + arms[:shift]


def sign_test(lost: int, gained: int) -> float:
    """One-sided exact probability of at least ``gained`` wins among discordant pairs under equality."""
    total = lost + gained
    if total == 0:
        return 1.0
    return sum(comb(total, k) for k in range(gained, total + 1)) / 2 ** total


def compared(outcomes: Mapping[str, Mapping[str, bool]], control: str, variant: str) -> dict:
    """``variant`` against ``control`` over the cases that have both."""
    cases = sorted(case for case, arms in outcomes.items() if control in arms and variant in arms)
    gained = [case for case in cases if outcomes[case][variant] and not outcomes[case][control]]
    lost = [case for case in cases if outcomes[case][control] and not outcomes[case][variant]]
    return {
        "cases": len(cases),
        "control_succeeds": sum(bool(outcomes[case][control]) for case in cases),
        "variant_succeeds": sum(bool(outcomes[case][variant]) for case in cases),
        "gained": gained, "lost": lost, "net": len(gained) - len(lost),
        "one_sided_exact_sign_test_p": round(sign_test(len(lost), len(gained)), 6),
    }


def diagnosis(outcomes: Mapping[str, Mapping[str, bool]], control: str, variants: Mapping[str, str], *,
              margin: int = 3, level: float = 0.05) -> dict:
    """``variants`` maps each variant to the component it changes. Returns what the run establishes."""
    if control in variants:
        raise ValueError("the control is not a variant")
    if margin < 1 or not 0 < level < 1:
        raise ValueError("a positive margin and a level between 0 and 1 are required")
    rows = {}
    for variant, component in variants.items():
        row = compared(outcomes, control, variant)
        row["component"] = component
        row["established"] = row["net"] >= margin and row["one_sided_exact_sign_test_p"] <= level
        rows[variant] = row
    established = sorted((name for name, row in rows.items() if row["established"]),
                         key=lambda name: (-rows[name]["net"], name))
    ranking = sorted(rows, key=lambda name: (-rows[name]["net"], rows[name]["one_sided_exact_sign_test_p"], name))
    arms = [control, *variants]
    complete = sorted(case for case, seen in outcomes.items() if all(arm in seen for arm in arms))
    return {
        "schema": SCHEMA, "control": control, "margin": margin, "level": level,
        "variants": rows, "ranking": ranking,
        "limiting_components": [rows[name]["component"] for name in established],
        "named": rows[established[0]]["component"] if established else None,
        "cases_run_under_every_arm": len(complete),
        "succeed_under_no_arm": [case for case in complete if not any(outcomes[case][arm] for arm in arms)],
        "succeed_under_every_arm": [case for case in complete if all(outcomes[case][arm] for arm in arms)],
    }
