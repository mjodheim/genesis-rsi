# A2 zero-LLM external bug result — 2026-10-06

**Development verdict: PASS**

Genesis repaired a real, public, externally authored bug with **zero external
LLM calls** using the generic scalar mutation grammar frozen before source
inspection.

## Carrier

- Repository: `drishtiaggarwal-ugsot/Os_Club_portal`
- Frozen upstream commit: `a4a8a4173aaf4afd77da5f748b5be5a25353faab`
- Public issue: #5, “Seats left is off by one”
- Candidate generator freeze: `d5ef0781`
- A2 v2 apparatus freeze: `2b470021`

The public bug says that a session with 30 free seats is displayed as 29 of 30.

## Baseline

The frozen objective reproduced the bug:

- 30 free seats → **29 of 30 seats left**
- 1 free seat → **0 of 30 seats left**
- full and unlimited-seat controls remained correct
- objective exit code: **1**

## Search

The frozen generic generator enumerated the complete finite image under
`frontend/src`:

- **2,030** single-site scalar candidates
- **2,030** charged candidate evaluations
- no candidate truncation
- no external-model call
- no manual candidate repair
- exactly **one** passing candidate

Winner:

- id: `scalar-1fea14f388f31db8`
- digest: `1fea14f388f31db8bedd38870f147953449882133fbe1b477533275fcef10c4a`
- path: `frontend/src/utils/format.js`
- generated edit: `session.seats_left - 1` → `session.seats_left - 0`

The form is mechanically minimal rather than pretty. It is kept verbatim:
rewriting it by hand to `session.seats_left` would violate the no-manual-repair
rule.

## Result

The unique candidate produced:

- 30 free seats → **30 of 30 seats left**
- 1 free seat → **1 of 30 seats left**
- full → **Full**
- unlimited → **4 going**

Winner objective exit: **0**.

Independent replay of the exact generated winner: **0**.

Result digest:
`f36ca5c56023e5cabbe1b23ef489a18a949438ea50268eb3edd08ce3b4eaf6aa`

## Repository validation

The exact generated candidate was then validated against the repository's
frontend tooling:

- `npm ci --ignore-scripts`: pass
- `npm run lint`: **0 warnings, 0 errors**
- `npm run check:contributors`: pass
- `npm run build`: pass

No external model participated in candidate generation or validation.

## Preserved failure

The first execution completed the candidate loop but aborted while serialising
its final report because the Python runner contained the literal `false`
instead of `False`. That run is preserved as
`ABORTED_RUN_1.json`; it is not counted as a result. V2 changed only that
apparatus literal. The task, generator, candidate order, candidate budget,
objective and winner rule were unchanged.

## Claim boundary

This establishes **A2 DEVELOPMENT PASS**: Genesis can generate and select a
working mutation for at least one real external software bug without using an
LLM.

It does **not** establish general autonomous software engineering. The repair
grammar is still host-written and the evaluator is project-controlled. A3 must
show causal retention and reuse on a fresh external task; A4 must move beyond
host-authored repair operators toward strategy acquisition from outcomes.
