# G12 — Validated operator learning, development audit (2026-10-08)

## Results

Genesis now has a bounded learning controller connected to the existing A6c
structural operator synthesis engine. It diagnoses a prior failure, freezes
candidate edits before running an independent project evaluator, requires a
full-suite clean verdict, distills successful edits into declarative operators,
persists their lineage, and reuses the resulting operators without model calls.

| Released development project | Full project suite | Operator acquired | Memory generation | New holdout pass |
|---|---|---|---:|---:|
| Compress-6: inherited state | 0 failing tests | 1 | 2 | 0 |
| Math-53: sibling guards | 0 failing tests | 1 | 2 | 0 |

The G12 candidate generators used existing G11 assistant-authored operators
designed after studying the respective bugs. What Genesis acquired on its own
was a structural replay rule from a validated patch, NOT a new semantic
repair idea discovered without assistance.

Results and provenance:
- G12_COMPRESS6_DEVELOPMENT_MANIFEST_20261008.json
- G12_COMPRESS6_DEVELOPMENT_RESULT_20261008.json
- G12_MATH53_DEVELOPMENT_MANIFEST_20261008.json
- G12_MATH53_DEVELOPMENT_RESULT_20261008.json

## Persistent memory and application

The merged, hash-checked, provenance-linked training-only bank is stored at:
G12_TRAINING_OPERATOR_BANK_20261008.json

This contains two learned structural operators and references to two
independently validated training receipts. Its memory generation=0 is a
fresh combined SEED, not a second lineage generation. Original memory
files remain intact on the VPS.

Repair planning can now opt in to reserve up to four exploration slots
for retained learned operators, including when an otherwise identical
human-authored candidate would win the deduplication score. With one
reserved slot, both known development projects placed an operator recovered
from the training bank at rank 1. Default mode allocates zero such slots
and remains unchanged.

Synthetic tests show an acquired Java edit can transfer to a renamed class
and field in another project fixture and pass fresh assertions. This is
limited structural adaptation, not general semantic understanding.

## Safety and evidence constraints

- Only explicit released-training cases may be used; unexposed holdouts are refused.
- Candidate identities, source hashes and prior failure records are frozen
  before any candidate test. Changes after freeze are rejected.
- Only compilation plus executed full-suite exit 0 and zero failures can
  trigger operator acquisition.
- Source-path traversal, duplicate/mutated evidence and project mutation
  by the evaluator are rejected. Evidence files are created atomically.
- The G12 runtime exploration option is OFF by default. No ER3 service
  changes have been made.
- G11 independent evidence remains at 0 out of 9 held-out repairs.
- Two separate development memory generations of 2 do not demonstrate
  recursive self-improvement or independently validated novel operators.

Next challenge: Genesis must invent new semantic transformations from its
own program analyses and public failed-test observations BEFORE a passing
candidate exists, then validate these ideas on genuinely untouched projects
against an equal-budget baseline. Its general RSI readiness is NOT proven.
