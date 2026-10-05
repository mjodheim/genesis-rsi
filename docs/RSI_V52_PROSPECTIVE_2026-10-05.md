# RSI V52 — Prospective abstraction-memory assay — 2026-10-05

## Scope

This record freezes the first prospective V52 abstraction-memory campaign after the V51 structured-memory result.

The campaign is **fresh with respect to V52 tuning**, but remains a finite, project-authored assay. It is therefore evidence about the current L9 research programme, **not** a general open-ended L9 proof.

Configuration:
- 3 prospective seeds: 520051, 520052, 520053;
- 144 tasks per seed, 432 total;
- inherited cap: 14 charged evaluations per task;
- abstraction-only transfer on top of the exact-memory apparatus;
- top-k abstraction retrieval: 1;
- negative recipe feedback enabled;
- isolated execution;
- no relaxation of L9 acceptance criteria.

## Aggregate result

| Condition | Solved | Evaluations |
|---|---:|---:|
| V52 abstraction memory | **164 / 432** | **4,815** |
| V51 structured memory | 159 / 432 | 4,870 |
| V32 archive control | 160 / 432 | — |
| Cold control | 157 / 432 | — |

V52 therefore:
- solves **+5 tasks vs V51**;
- solves **+7 tasks vs cold**;
- uses **55 fewer evaluations than V51**;
- evaluates 299 abstract candidates;
- does not regress below cold on any seed.

The abstraction layer is causally exercised and receives reuse feedback. The observed helpful-use rate is low but non-zero across all three seeds:
- seed 520051: 10 / 103 helpful uses;
- seed 520052: 15 / 98;
- seed 520053: 12 / 98.

## Per-seed result

### Seed 520051
- V52: **52 solved**, 1,648 evaluations;
- V51: 49 solved, 1,664 evaluations;
- cold: 49 solved;
- archive: 49 solved;
- distinct solved semantics: 28 vs 25 for V51.

However, V52 first discoveries are zero in windows **10 and 11**.

### Seed 520052
- V52: **56 solved**, 1,596 evaluations;
- V51: 54 solved, 1,616 evaluations;
- cold: 53 solved;
- archive: 54 solved;
- distinct solved semantics: 30 vs 28 for V51.

All V52 windows retain positive first discovery on this seed.

### Seed 520053
- V52: 56 solved, 1,571 evaluations;
- V51: 56 solved, 1,590 evaluations;
- cold: 55 solved;
- archive: 57 solved.

V52 first discoveries are zero in windows **7 and 9**.

## Adjudication

Passed predicates:
- abstraction reuse and feedback exercised;
- all committed tasks retained;
- no seed solved regression below cold;
- V52 aggregate cost <= V51;
- V52 aggregate solved > cold;
- V52 aggregate solved >= V51.

Failed predicate:
- **all_seed_windows_keep_positive_first_discovery = false**.

Therefore:

```text
scoped_sustained_abstraction_assay_passed = false
l9_general_open_ended_passed = false
verdict = VALID_NEGATIVE_SCOPED_SUSTAINED_ABSTRACTION_ASSAY
```

## Interpretation

V52 is a real improvement over V51: cross-width abstraction transfer increases solved tasks and distinct semantics while reducing evaluation cost. This supports the hypothesis that the L9 bottleneck is not only storage/retrieval; abstraction can convert prior experience into useful new candidates.

But the stronger L9 requirement is still not met. Discovery still collapses to zero in late windows for two prospective seeds. The next research question is therefore narrower:

> how can Genesis preserve positive discovery when the current abstraction vocabulary itself becomes exhausted?

The next successor should focus on **compositional or learned abstraction operators**, rather than increasing search budget or simply recalling more recipes.

Raw machine-readable evidence:
`results/rsi-v52/structured-abstraction-prospective-20261005/REPORT.json`.
