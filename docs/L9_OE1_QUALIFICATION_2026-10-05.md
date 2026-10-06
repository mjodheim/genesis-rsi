# L9-OE1 prospective qualification — 2026-10-05

## Verdict

**L9_OPERATIONAL_GATE_PASSED**

The prospectively frozen L9-OE1 programme passed every acceptance predicate
committed before its first behavioral execution.

This closes the project successor-map L9 operational gate: a branching archive
maintained positive discovery while task complexity grew across four materially
different native domains under fixed external governance.

It does **not** establish a mathematical asymptotic theorem and does not satisfy
L10 independent replication.

## Freeze

- Apparatus commit before the freeze JSON: `441a079f`
- Freeze commit before first qualification behavior: `e163383b`
- Population SHA-256: `6c8e07d934e9c14cdf7f0ea52bb992addf8c752500c6cefd029e835fdadec0c9`
- Freeze SHA-256: `a7f5074d8cbce52396573c30b3307d4e9f8e2f79b6dd0e18b597504bb3061714`
- Population seed: `86753091`
- Horizon: 12 epochs, 16 tasks/epoch, 4 domains
- Per-task cap: 14 charged native executions
- Native execution: isolated
- Transfer complexity: 2 through 10 three-slot blocks, i.e. 6 through 30 slots

No threshold, seed, task order, domain, budget, mechanism or control was changed
after the freeze.


## Aggregate result

| Arm | All tasks solved | Transfer solved | Transfer evaluations |
| --- | ---: | ---: | ---: |
| coded-archive | **768 / 768** | **576 / 576** | **5,306** |
| archive-g7 ablation | 242 / 768 | 62 / 576 | 7,188 |
| greedy-g7 | 168 / 768 | 23 / 576 | 7,302 |
| cold-g7 | 148 / 768 | 0 / 576 | 7,488 |

The coded archive therefore retained a 100% transfer solve rate while the
branching G7 predecessor fell to 10.76%, greedy to 3.99% and cold to zero.

The coded transfer discovered 288 newly first-solving semantics and recorded
243 rediscoveries. Every transfer epoch in every domain retained positive
first discovery and positive rediscovery.

## Per-domain coded result

| Domain | All solved | Transfer solved | Total evaluations | Max calls/task |
| --- | ---: | ---: | ---: | ---: |
| relational-sql | **192 / 192** | **144 / 144** | 1,570 | 12 |
| regular-expressions | **192 / 192** | **144 / 144** | 1,524 | 12 |
| structured-json | **192 / 192** | **144 / 144** | 1,896 | 14 |
| binary-compression | **192 / 192** | **144 / 144** | 1,564 | 12 |

Each domain produced 72 newly first-solving transfer semantics. Rediscoveries
were respectively 62, 59, 62 and 60.
