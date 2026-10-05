# V51 — structured experimental memory development

V51 is a development successor to the retained negative V32 memory assay. It does not alter V32, V49 or V50 evidence. Its purpose is to test issue #374: whether a persistent, scored and deduplicated database can make memory reuse measurable and less harmful without changing L9's definition.

## Authority boundary

The database is evaluator/host-owned. The actor never receives hidden targets, task identifiers, inputs, expected outputs, family names or future quality. The retrieval context exposed to memory selection is the already-observed root quality plus structural compatibility already enforced by V31/V32 (candidate width). Evaluator, budget, acceptance rule and trust root remain external.

## Memory model

The executable reference backend is SQLite so repository tests require no service. `schema_postgres.sql` defines the production-equivalent PostgreSQL layout.

Persistent concepts:

- `strategies`: behavior-deduplicated executable strategies and adaptive metadata;
- `experiences`: task/context observations for a strategy;
- `lineages`: retained parent relationships;
- `evaluations`: exact quality/cost outcome;
- `memory_usage`: each recall and its measured quality/cost impact.

A semantic strategy is stored once. All successful observed contexts remain queryable. Retrieval first enforces structural compatibility, then uses nearest observed context. Utility, confidence, empirical success, novelty and age are recorded and scored; memories with sufficiently negative measured utility are excluded.

## Matched development comparison

The committed development population uses seeds 510051, 510052 and 510053, eight windows, twelve tasks per window, 288 tasks total. Each task is evaluated by:

1. V51 structured DB memory;
2. the retained V32 adaptive archive;
3. cold start.

The same inherited candidate cap applies. Every DB recall is compared with the matched cold result. `memory_usage` records quality delta and evaluation savings, then revises the recalled strategy utility/confidence.

This population is project-authored and finite. It is engineering development, not a fresh L9 qualification population.

## L9 boundary

A positive V51 development benchmark can establish that structured memory is useful under this finite comparison. It cannot establish general open-ended L9. In particular, a finite run cannot prove an asymptotically positive discovery rate and exhausted windows must remain visible. `l9_general_open_ended_passed` therefore remains false in V51 development by construction.
