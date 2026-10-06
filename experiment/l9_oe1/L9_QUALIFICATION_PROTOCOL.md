# L9-OE1 prospective qualification protocol

Status: prospective and frozen before first behavioral execution.

This protocol operationalizes the project L9 criterion from
docs/RSI_GENERAL_SUCCESSOR_MAP_2026-09-23.md for a finite prospective
qualification programme. A positive result is evidence for the project L9 gate,
not a mathematical proof of a positive asymptotic discovery rate and not L10.

## Fixed observation programme

- Population seed: 86753091.
- Domains: relational SQLite, regular expressions, structured JSON and binary compression.
- Horizon: 12 epochs per domain.
- Tasks: 16 tasks per epoch and domain.
- Acquisition epochs: 0-2.
- Transfer epochs: 3-11, growing from 2 to 10 motif blocks.
- Transfer diversity: 8 distinct target compositions per epoch, repeated twice.
- Every paid native execution is isolated.
- Maximum charged executions per task: 14.


All epochs run to completion unless the external instrument itself fails.
Behavioral failure never changes task order, thresholds or the stopping rule.

## Arms

1. coded-archive: OE1 target-blind coded constructor with a branching motif archive.
2. archive-g7: V36 branching archive under the same fourteen-call cap, without coding.
3. greedy-g7: V36 latest/greedy history under the same cap.
4. cold-g7: V36 search without acquired history under the same cap.

Expected answers, target bodies and future task identities remain outside actor
selection. A codebook may inspect acquired motif bodies and declared task size;
it may not inspect the current hidden target or expected outputs.

## Recovery and archive accounting

After every epoch the coded arm persists its motif archive, semantic discovery
ledger and codebook manifest, then reloads them through a fresh process boundary.
The regenerated codebook hash must match the committed state. The archive must
retain all four acquired motif branches; transfer codebooks are descendants of
all four motif parents rather than a single greedy parent.


## Frozen acceptance predicates

The finite L9-OE1 operational gate is positive only if every predicate below holds.

1. All 768 committed tasks are retained in each arm: 12 epochs x 16 tasks x 4 domains.
2. No arm exceeds 14 charged native executions on any task.
3. coded-archive solves at least 95 percent of transfer tasks in aggregate.
4. coded-archive solves at least 90 percent in every domain and every transfer epoch.
5. Every domain and every transfer epoch records at least four newly first-solving
   semantic behaviours in coded-archive; zero-discovery windows fail the gate.
6. coded-archive exceeds archive-g7 transfer solve rate by at least 15 percentage
   points in aggregate and by at least 5 points in every domain.
7. coded-archive exceeds both greedy-g7 and cold-g7 transfer solve rate by at least
   20 percentage points in aggregate.
8. coded-archive uses no more charged evaluations in aggregate than archive-g7.
9. Each domain retains four distinct acquired motif parents and distinct codebook
   descendants for every block count 2 through 10.
10. Every epoch-boundary state round-trip reproduces the exact state digest and
    every regenerated codebook reproduces its recorded source digest.
11. Every transfer epoch and domain records at least one rediscovery of a previously
    solved semantic behaviour, demonstrating archive reuse rather than only novelty.
12. All control failures, negative candidates and zero windows are retained in the
    final report; no aggregate may hide a failing domain or epoch.

A single false predicate yields a retained negative result. Thresholds, horizon,
seed, domains, task order, codebook budget and controls may not be changed after
the first qualification behavior.

## Claim boundary

A positive result may be recorded as L9_OPERATIONAL_GATE_PASSED for the Genesis
successor map: a branching archive sustaining positive discovery as archive size,
task complexity and domain diversity increase under fixed external governance.
It remains finite empirical evidence, not an asymptotic theorem and not L10
independent replication. L10 therefore remains open even after a positive L9 result.
