# G11 — Synthetic Java repair pilot, 2026-10-08

RESULT: Negative for current experimental structural reranking.

## Pre-registered controls

Preregistration SHA256-style digest: f3f3e4b02e01eeef02f165e69b063a30ca1f2009fe5336ca0a201073aa04db40
Frozen candidate index digest: a7e4f5f021283a6f280d782e23de52d6e1c2509bf4392b185f1789dd268564ab
Preregistration commit 3002876d; runner field fix f916c6fa.
Eight synthetic Java bugs, test assertions independently defined in the runner; never supplied to the repair planner.
At most 64 candidates per arm generated, 24 top-ranked candidates tested per arm, same configuration budgets.
All candidate indexes frozen before candidate validation; original cases compiled and failed their test suites.
Full suite means all assertions for each synthetic example: NOT a Defects4J or external-project test suite.
No ER4 cases, patch reveal, runtime learning, or cross-language generalization tested.

## First passing rank, among top 24

| Case | Baseline | G11 understanding rerank | G11 plus security and performance |
|---|---:|---:|---:|
| A | 21 | 21 | 21 |
| B | 9 | none | none |
| C | 18 | 19 | 19 |
| D | 1 | 1 | 1 |
| E | 7 | 7 | 7 |
| F | 2 | 1 | 1 |
| G | none | none | none |
| H | 2 | 1 | 1 |

## Aggregate

| Arm | Cases solved of eight | Planning time, all eight |
|---|---:|---:|
| baseline | 7/8 | 0.064 s |
| understanding | 6/8 | 12.816 s |
| understanding_security_performance | 6/8 | 12.685 s |

Case B was harmed: baseline found a correct patch at rank 9; G11 placed it beyond the first 24.
Cases F and H improve from rank 2 to 1, but case C moves from rank 18 to 19.
Cases A/D/E unchanged, G not fixed in any arm.
Security/performance review modules produced identical candidate ordering to understanding-only, by design.
The original JDK analyzer recompiled its helper repeatedly; the later in-process helper cache addresses some overhead. Times shown are from the original uncached run.
Eight small synthetic bugs are not sufficient to support a general effect estimate.

## Response to negative result

Reranking is now experimental-only. Default G11 understanding operates in shadow mode: annotate and observe without changing candidate score/order.
To reproduce the two original experimental arms, the pilot script now explicitly supplies understanding_rerank=True.
Next: fresh previously unseen external test bugs, independently frozen holdouts, identical budgets, full project suites, and a real audit.
Four prior ER4 holdouts (Lang-23, 45, 53, 44) were previously exposed and are not clean.

Artifacts: G11_REPAIR_PILOT_PREREG_20261008.json, G11_REPAIR_PILOT_RESULTS_20261008.json, scripts/g11_repair_pilot.py.
