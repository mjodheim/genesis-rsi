# A6b prospective campaign — final result

**Date:** 2026-10-06  
**Status:** **DEVELOPMENT FAIL**  
**Claim boundary:** A6b is a frozen development campaign. It does not establish A7 or general autonomous software engineering.

## Result

A6b completed all **12 preregistered runnable tasks** across three waves without changing the frozen search apparatus during evaluated runs.

| Metric | Result |
| --- | ---: |
| Runnable tasks | 12 |
| Autonomous successes | **3 / 12** |
| Tasks requiring fallback | **9 / 12 (75%)** |
| Pipeline solved | **9 / 12 (75%)** |
| External model calls | **9** |
| External model calls / solved task | **1.0** |
| Causal reuse successes | **1** |
| Within-A6b prior-task reuse | **0** |
| Language families observed | **6** |

Wave behavior:

| Wave | Autonomous | Fallback rate | Model calls | Solved | Calls / solved |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 / 4 | 0.75 | 3 | 3 | 1.00 |
| 2 | 0 / 4 | 1.00 | 4 | 3 | 1.33 |
| 3 | 2 / 4 | 0.50 | 2 | 3 | 0.67 |

Wave 3 improved substantially relative to wave 1, but the **overall fallback rate remained 0.75**, equal to A6 rather than strictly lower.

## Preregistered gate

Passed:

- wave 3 fallback rate is lower than wave 1;
- wave 3 model calls per solved task are lower than wave 1;
- at least three language families were observed.

Failed:

- overall fallback rate is **not lower than A6** (0.75 == 0.75);
- autonomous successes are **3**, below the required **5**;
- causal reuse successes are **1**, below the required **2**;
- no winner reused experience acquired during an earlier A6b task.

Therefore **A6b fails** and **A7 remains blocked**.

## What the negative result taught us

The dominant failure is no longer adequately described as “needs more search”.

Several prospective tasks exposed an **expressivity boundary** in the transformation system:

- a C multi-line control-flow repair produced **zero autonomous candidates**;
- a YAML/config default change produced **zero autonomous candidates**;
- Python range(1, n) -> range(1, n + 1) was outside the then-current candidate vocabulary until a passing outcome was distilled;
- a Rust retry-range correction required a transformation the autonomous generator did not express;
- coordinated Python dictionary-key changes exhausted the budget without a passing composition;
- a TypeScript array-index correction exhausted 256 candidates even though the repair was a one-token numeric change;
- the final JavaScript timezone bug required changing the interpretation of a calendar string, not merely tuning a scalar already present in the code.

This matters because the one-call fallback frequently found a valid repair. The prospective failures therefore do **not** show that these tasks are intrinsically beyond contemporary model reasoning. They show that Genesis's current autonomous **transformation language and acquisition machinery are too narrow**.

## A6c boundary

A6b is now immutable negative evidence.

The next apparatus revision, **A6c**, is allowed to address the observed failure mechanism, but no retrospective repair of A6b can count as A6b evidence.

A6c targets the following loop:

observe failure -> diagnose the missing expressive capability -> synthesize a new operator -> replay/verify it -> retain it with provenance -> causally reuse it later

The new apparatus must learn generic transformation capability from evaluated outcomes rather than adding host-authored bug-specific repair recipes.
