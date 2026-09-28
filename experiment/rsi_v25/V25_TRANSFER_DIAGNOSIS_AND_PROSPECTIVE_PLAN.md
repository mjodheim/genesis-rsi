# RSI V24 negative transfer diagnosis and V25 prospective direction

Status: post-holdout diagnosis. V24 evidence is immutable negative evidence. This document does not redefine V24 success.

## V24 observed result

The frozen V24 fresh holdout completed successfully under the preregistered identities and equal external caps. G3, exact G2, and the G1-meta-selected successor obtained the same aggregate global utility:

- G3: (2, 2500, -17, -17)
- G2: (2, 2500, -17, -17)
- G1-meta successor: (2, 2500, -17, -17)

They were also identical task-by-task in best quality, represented requests, and rounds:

| Fresh task | Best quality | Requests | Rounds |
|---|---:|---:|---:|
| brewstead-brew-lifecycle-thresholds | 1000 | 2 | 2 |
| brewstead-effect-rounding | 0 | 3 | 3 |
| brewtrack-brewmath-precision | 1000 | 7 | 7 |
| brewtrack-recipemath-units-water | 500 | 5 | 5 |

Therefore V24 is a valid negative L5 result: the pre-holdout causal gate passed, but G3 did not strictly beat either frozen comparator on fresh global utility.

## Diagnosis

V24 selected a G3 whose changed parameters improved meta-development utility, including a strong-result stopping mechanism, but the fresh population did not expose a behavioral distinction among G3 and its controls. The failure is therefore not evidence that G3 regressed. It is evidence that the acquired mechanism was behaviorally silent on the frozen transfer population.

This bounds the next claim. A successor experiment must not merely search more values of the same stopping thresholds and then replay the consumed V24 holdout. It must test whether evolving the *choice of what to explore next* creates causally attributable, budget-matched behavioral differences that survive on a new population.

## V25 prospective hypothesis

Under equal external request/round/parallelism budgets, a lineage that can evolve a bounded parent-selection/exploration mechanism in addition to stopping parameters will discover a successor G4 whose improvement-process behavior differs from its exact predecessor on prospective development tasks and whose frozen identity then strictly improves utility on a new, previously unconsumed cross-domain holdout. Ablating the acquired exploration mechanism must weaken the transition.

## Required gates before a V25 fresh holdout may be consumed

1. Preserve V24 final adjudication and all twelve task results with content hashes.
2. Freeze a bounded executable mutation grammar that may change exploration/parent-selection machinery but cannot change evaluator, budgets, task bank, sandbox, evidence ledger, trust root, credentials, or success rule.
3. Include exact-predecessor, mechanism-ablation, and no-meta controls under identical external budgets.
4. Require a prospective development behavioral-diversity gate: the selected successor must differ from the exact predecessor on at least one decision trace before holdout access. This gate is about behavior, not final holdout performance.
5. Require causal meta-development advantage over the mechanism ablation under the frozen utility.
6. Retain all previously required L4 capabilities with zero tolerance.
7. Freeze a genuinely new holdout population before successor selection; V24 BrewTrack/Brewstead holdout tasks are forbidden as V25 selection or final-test targets.
8. Only after gates 1-7 pass may the frozen successor and controls see the new holdout once.

## What would count as V25 L5-positive

The final claim remains conservative: the successor must strictly beat the exact predecessor and the matched predecessor-meta control on the new frozen global utility, while exact identities, causal ablation, retention, budget equality, provenance, and no-leakage predicates all pass. Any failed predicate is preserved as negative evidence; no post-observation tuning is allowed.

## Engineering next step

Implement the V25 mutation grammar and trace recorder against disposable prospective development tasks first. Do not author or inspect final holdout outcomes while iterating on that apparatus. Freeze apparatus, candidate universe/generator, controls, budgets, development tasks, retention suite, and new holdout identities before scientific execution.
