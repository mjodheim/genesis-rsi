# ER2 — Capability-Routed Compositional Repair Planner

ER1 J1–J9 exposed a structural limitation in the previous loop: Genesis kept adding one
specialist after each failure, while fresh defects frequently required a different
capability. ER2 changes the search machinery itself.

The planner introduces a repair-plan IR, dynamic causal routing to trigger-loaded source
files, deterministic capability ranking, bounded same-file composition, and a generic
coordinated sibling-expression primitive distilled from J9. Existing atomic candidates
remain available as ablations and the historical broad search remains a fallback.

## Qualification before fresh use

- 5/5 focused unit checks passed.
- Deterministic ordering/digests passed.
- J9 consumed replay: planner produced 419 candidates (219 atomic, 200 composed).
- The first evaluated planner candidate passed both frozen J9 hidden triggers.
- Evaluator errors: 0.
- External model calls: 0.

This replay is deliberately **not** counted as external transfer because J9 is consumed
training evidence. J10+ remain unseen until the machinery freeze is committed and tagged.

## Claim boundary

ER2 v1 composes edits only within one source file and to depth two. It does not yet prove
multi-file planning, open-ended program synthesis, or fresh real-repository success.
Those claims require J10+ evidence.
