# Real-project transfer and retained learning — 9 October 2026

Anthony authorised moving from exercises to real bugs and publishing the work.
The code and exact protocol were committed and pushed before the comparison
completed. Cases were selected before opening their code: the first case for
each of Jsoup, Math and Compress in the frozen development split, excluding the
split's original exposure list. They remain public DEVELOPMENT cases, not
independent blind evidence or protected held-out cases.

## Observed results

| Java development bug | Parent / adapted autonomous repair | Subsequent training | New API cost | Durable model-free replay |
|---|---|---|---:|---|
| Jsoup-29, document title whitespace | failed / failed | passed with GPT-6 Luna | $0.002398255 | passed |
| Math-66, numerical minimization | failed / failed | failed with Haiku and Luna | $0.011491545 | no successful recipe |
| Compress-19, ZIP64 extra metadata | failed / failed | passed with Haiku | $0.003388400 | passed |

Both arms had four candidate validations per case, 24 validations in total,
with zero external model calls. No gain was observed and the adapted search
policy was not promoted. Source-observed subscript candidates were absent on
all three causal source views. Retained offset rules produced no candidate on
Jsoup/Math and nine on Compress. Consequently the parent and child tried the
same ordered candidates: this run does not isolate a positive or negative
effect of changing their order. The narrow exercise-derived capability does
not solve these real bugs within the tested budget.

Only after all three comparisons and the rejection decision, a separate
training phase ran existing local operators and, when needed, the economical
router with Haiku 5.5 and GPT-6 Luna. Its ceiling was $0.05 per case, eight
candidate validations, two models and two proposal rounds per model. The
16 actual API requests cost $0.0172782 including failed Math attempts; every
new recorded charge is known. Older unknown charges remain unknown. API cost
excludes the image rebuild, runtime infrastructure and development effort.

Both accepted patches passed compilation, triggering tests and the full
developer test suite. They entered persistent memory and were independently
loaded by a new database reader; the same candidates passed full-suite replay
with zero model calls. Passing tests establishes plausibility, not proven
semantic correctness. Assisted proposals remain attributed to their external
models; neither repair is counted as an autonomous invention by Genesis.

The canonical development memory now contains 124 events, preserving its
original 84-event prefix and adding the complete 40-event training history,
including failures. Its prior pointer and database are archived. Promoting
validated experience is separate from promoting a search policy: the latter
remains rejected. The source and test trees of all three buggy checkouts were
checked and contain no remaining tracked changes.

## Evidence and validation

- [Frozen protocol](../experiment/bench/DEV_REAL_REPAIR_TRANSFER1/PLAN.json),
  [result](../experiment/bench/DEV_REAL_REPAIR_TRANSFER1/RESULT.json),
  [recorded-evidence verification](../experiment/bench/DEV_REAL_REPAIR_TRANSFER1/VERIFICATION.json),
  and [experience promotion receipt](../experiment/bench/DEV_REAL_REPAIR_TRANSFER1/PROMOTION.json).
- Candidate-pool/order digests were written before validation. Per-candidate
  outcomes, negative comparisons and assisted-training histories are preserved.
  All Genesis Python sources and the runner were snapshotted and hash-frozen.
- The dedicated Defects4J image was rebuilt and pinned to its actual local image
  ID. The observed isolation probe passed all required checks; executions were
  nonroot, network-disabled, resource-limited and used a read-only image. No
  fixed project revision was inspected.
- 99 focused repair tests passed before the result commit (96 before execution).
  Three further tests cover
  memory promotion, preservation of unknown charges, concurrent-write refusal
  and pointer-write recovery. Repository import checks passed. The evidence
  auditor recomputes decisions, verifies verdict digests, costs, historical
  memory continuity and replay identities; it is not independent replication.

## Consequence for RSI research

The exercise result cannot be promoted into a real-world RSI claim. The concrete
limitation is insufficient coverage in the bounded candidate pools: neither
accepted assisted patch occurred in those pools. This does not establish that
every larger generator configuration lacks the corresponding operation.
Reordering an inactive observation family cannot address this gap. Next work
should test acquisition/generalization of additional repair operations and
compiler-aware candidate selection, with separate real-project selection and
transfer tasks. Replaying these two exact corrections alone would measure
memory, not improved problem-solving on unseen bugs. Math-66 remains an explicit
negative result; its protocol and budgets are not retroactively enlarged.
