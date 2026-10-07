# Genesis G10 qualification

This directory contains the preserved evidence for the strengthened Genesis v2
G10 recursive-successor qualification executed on 7 October 2026.

## Canonical chain

- `G0_PROFILE.json` — campaign seed built from the qualified G9 successor.
- `G1_PROFILE.json` — stage-1 successor.
- `G2_PROFILE.json` — stage-2 successor.
- `G3_PROFILE.json` — stage-3 successor.
- `CHAIN_RESULT.json` — final frozen-chain adjudication.

Profile chain:

`G0 -> G1 -> G2 -> G3`

Final verdict:

`G10_SCIENTIFIC_GATE_PASSED`

## Stage layout

Each `stageN/` directory contains:

- `DISCOVERY_BANK.json` — visible discovery material used by the current generation;
- `DISCOVERY_RESULT.json` — current-generation evidence and, for stages 2/3, the matched direct-ancestor comparison;
- `SUCCESSOR.json` — content-addressed successor freeze created before the qualification holdout;
- `PREREGISTRATION.json` — frozen holdout SHA-256, apparatus identities, budgets and decision predicates;
- `HOLDOUT_REVEALED.json` — fresh qualification material revealed only after preregistration;
- `RESULT.json` — preserved stage result.

## Scientific chronology

The apparatus and final adjudicator were frozen first in `c6a231b2`.

Stage 1:
- successor freeze: `a136d784`
- preregistration: `2aed97f8`
- result: `610038b7`

Stage 2:
- successor freeze: `9bf326f7`
- preregistration: `e40285c7`
- result: `123386a6`

Stage 3:
- successor freeze: `03477d6f`
- preregistration: `cebf06dc`
- result: `b062230a`

Final chain result:
- `c5b6fb44`

All of these commits are additionally retained by dedicated
`provenance/g10-*` tags.

## Boundary

This is project-authored, bounded software-repair evidence. It supports the
narrow claim documented in `docs/G10_QUALIFICATION_2026-10-07.md`: domain-
bounded recursive self-improvement under this exact frozen assay, not general
RSI, AGI, ASI or independent third-party validation. The successor mechanism
families in the level-0→1→2→3 ladder remain host-authored; the result does not
claim open-ended invention of arbitrary new improvement machinery.
