# ER2 v2 — Default-before-use dataflow normalization

ER2 v1 successfully routed J10 to the sole causal source file but could not express
the repair. Post-reveal diagnosis showed a dataflow-order gap: a nullable value was
used to construct cache state before its default was resolved.

ER2 v2 adds a generic source-mined primitive that detects an earlier conditional use
and a later guarded default assignment for the same value. It proposes moving default
resolution before the use, making the use unconditional, deleting the redundant late
guard, and coordinating bounded subsets of analogous sibling methods.

The primitive encodes no Lang-50, FastDateFormat, Locale, cache, method, test, issue,
commit, or line identity.

## Qualification

- 6/6 focused unit checks passed.
- J10 is consumed training evidence, not a holdout.
- On frozen J10 triggers, the v2 planner found a passing plan at logical index 0.
- Evaluator errors: 0.
- External model calls: 0.

## Claim boundary

This validates the new mechanism only. Fresh transfer begins at J11 after the v2
freeze. J10 remains a negative fresh-transfer result for ER2 v1.
