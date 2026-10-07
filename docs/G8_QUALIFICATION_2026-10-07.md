# Genesis G8 qualification — 7 October 2026

**Verdict: `G8_SCIENTIFIC_GATE_PASSED` under the preregistered project-defined criterion.**

This result qualifies the Genesis v2 G8 distillation/local-specialization gate in one bounded software-repair setting. It does **not** establish G9, G10, general RSI, AGI, ASI, universal replacement of external models, or independent third-party validation.

## Question

Can Genesis convert previously expensive validated reasoning into a cheaper retained local mechanism, then preserve or improve useful performance on fresh related tasks?

## Source experience

The G8 specialist was built only from frozen A6b fallback results selected by a generic rule:

- fallback evaluation passed;
- at least one external model invocation was used;
- at least one reusable deterministic template was learned;
- fallback report and learned-template digests reproduce;
- no manual task-id selection.

Five historical A6b traces satisfied the rule: tasks 1, 4, 6, 7 and 11. Together they represented:

- **5 external-model calls** under the A6b project accounting convention;
- **$0.474032** recorded external reasoning cost;
- **6 reusable learned templates**;
- zero model calls for the deterministic distillation step itself.

The resulting specialist is content-addressed as:

`94afbbfbe908f9c76c6abdf19f39f24e12f14c7c5a680feceeca0283b7424edb`

## Prospective chronology

1. G8 distillation, specialist construction, holdout generation, preregistration and evaluation machinery were frozen in `2afad013`.
2. The specialist was distilled from prior frozen A6b evidence and frozen in `83655749` before the fresh G8 holdout existed.
3. Only after the specialist commit, a new random seed was drawn and the frozen holdout generator created eight fresh tasks across four families.
4. The holdout was sealed as SHA-256 `ab7408a9bbc7cfbd12e8f4238422af190ee20d3df757d4c9f4ed42063db66df9`.
5. The complete 17-predicate G8 qualification was preregistered in `e018a588` before holdout reveal.
6. The frozen evaluator ran the external baseline, local specialist and empty-specialist ablation.
7. The positive result and revealed seed/holdout were frozen in `01fd7f60`.

## Fresh holdout

The eight fresh cases contained two independently generated instances from each family:

- Python inclusive upper-bound range;
- TypeScript zero-based first-entry selection;
- Rust retry-range lower-bound correction;
- Rust exact-boundary comparator correction.

The seed was unavailable to the specialist before its freeze. After qualification it was revealed; its SHA-256 reproduces the `seed_commitment` embedded in the frozen holdout.

## External baseline

Baseline environment:

- Claude Code **2.1.289**;
- model **`claude-sonnet-5-5`**;
- one non-interactive fallback session per case;
- read-only tools: `Read`, `Glob`, `Grep`;
- no shell/test execution;
- no web;
- no evaluator visibility;
- maximum budget `$0.50` per case.

The project uses the same call accounting convention as A6b: one fallback session counts as one `external_model_call`, even if the provider performs multiple internal turns.

Result:

- solved: **7/8**;
- external-model calls: **8**;
- calls per solved task: **1.142857...**;
- recorded cost: **$0.2300264**;
- cost per solved task: **$0.0328609...**;
- wall time per solved task: **~7.8365 s**.

## Distilled local specialist

The specialist uses the existing deterministic learned-line-rewrite engine plus the six retained rules distilled from prior validated outcomes. Runtime model access is disabled by construction.

Result:

- solved: **8/8**;
- external-model calls: **0**;
- calls per solved task: **0.0**;
- runtime external cost: **$0**;
- candidate executions: **1 per case**;
- wall time per solved task: **~0.03183 s**.

On this run, that is roughly a **246x reduction in wall time per solved task**, in addition to eliminating runtime model calls and dollar cost for these families.

## Empty-specialist ablation

The exact same local mechanism with its retained rule set removed solved:

- **0/8**.

This shows that the fresh local success depends on the distilled retained machinery rather than on the surrounding evaluator or task harness.

## Baseline formatting miss

The external baseline's single miss does not reflect a semantic reasoning failure. On `rust-boundary-1`, Claude proposed the correct `>` to `>=` repair, but returned an absolute temporary-workspace path. The prospectively frozen safety boundary accepted only the target-relative path and therefore rejected the proposal.

The frozen result is preserved exactly as 7/8. No post-hoc retry or parser relaxation was performed.

A conservative robustness check does not affect the G8 conclusion: even if that semantically correct proposal were credited, the external baseline would be 8/8 with 8 external calls and positive dollar cost, versus local 8/8 with zero external calls and zero dollar cost.

## Frozen qualification predicates

All **17/17** preregistered predicates returned true:

- holdout identity matches the preregistration;
- all raw tasks fail before repair;
- four families and eight cases are present;
- specialist identity validates;
- source experience contains repeated expensive reasoning;
- external baseline attempts exactly one model call per case;
- local specialist uses zero model calls;
- local specialist solves at least 7/8;
- local success retains or improves external-baseline success;
- model calls per solved task strictly decrease;
- runtime dollar cost per solved task strictly decreases;
- local wall time per solved task is lower;
- empty-specialist ablation loses capability;
- empty-specialist ablation solves zero tasks;
- specialist had no holdout visibility at freeze;
- distillation used zero model calls;
- mutable specialist owns neither evaluator nor verdict.

Therefore:

> **`G8_SCIENTIFIC_GATE_PASSED`**

## What this establishes

In this bounded domain, Genesis demonstrated the intended efficiency-first loop:

`validated expensive reasoning -> generic retained templates -> compact local specialist -> fresh tasks -> equal-or-better useful performance at lower runtime cost`

This is directly aligned with the Genesis v2 principle that capability growth should preferentially come from **better machinery rather than larger machinery**.

## What this does not establish

- The specialist covers related repair families; it is not a universal software engineer.
- External models remain useful for novel problems outside retained machinery.
- G9 is not passed: G8 does not yet show Genesis N producing a whole successor Genesis N+1 satisfying the complete successor criterion.
- G10 is not passed: there is no repeated recursive successor chain.
- The evaluator and holdout are project-created, not independently governed third-party evidence.
- This is not general RSI, AGI or ASI.

## Frozen identities

- apparatus commit: `2afad013`
- specialist commit: `83655749`
- preregistration commit: `e018a588`
- result commit: `01fd7f60`
- specialist freeze digest: `d74b2561c48e22b1c4eb9195ea49f89c4d051a26dd4f9dcdd52ed17015320485`
- specialist digest: `94afbbfbe908f9c76c6abdf19f39f24e12f14c7c5a680feceeca0283b7424edb`
- preregistration digest: `e1bd0ed55001d9788c24ca0522f0323fdd79019541fcca2e10a3600d989372e5`
- result digest: `e5471f661a337d81ec6fa1996d766d0baee67a0cf354d20d833fb6bc97389641`
- holdout SHA-256: `ab7408a9bbc7cfbd12e8f4238422af190ee20d3df757d4c9f4ed42063db66df9`

## Evidence

- `experiment/g8_qualification/SPECIALIST.json`
- `experiment/g8_qualification/PREREGISTRATION.json`
- `experiment/g8_qualification/HOLDOUT_REVEALED.json`
- `experiment/g8_qualification/SEED_REVEALED.txt`
- `experiment/g8_qualification/RESULT.json`
- `genesis/learning/distillation.py`
- `scripts/build_g8_specialist.py`
- `scripts/build_g8_holdout.py`
- `scripts/build_g8_qualification_preregistration.py`
- `scripts/run_g8_qualification.py`
- `tests/test_distillation.py`
- `tests/test_g8_qualification_record.py`