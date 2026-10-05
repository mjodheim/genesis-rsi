# RSI V51 — structured memory development, 5 October 2026

## Why this successor exists

Issue #374 proposed replacing the passive archive with a persistent experimental memory that can be queried, scored, deduplicated and evaluated by its actual reuse impact. V51 implements that proposal without modifying any frozen predecessor.

The first implementation was intentionally benchmarked before publication. It failed badly: cross-width memories were eligible and the DB solved only 127/288 against 141/288 cold. Adding a relevance threshold alone did not repair it. The root cause was then isolated: V31/V32 first restrict candidate history to the current structural width, whereas the initial DB retrieval did not.

That negative development path is retained in this report because it directly demonstrates the harmful-memory failure mode #374 was intended to expose.

## Corrected development result

After restoring structural compatibility and retaining all successful observed contexts per strategy, the three matched development seeds produced:

| arm | solved / 288 | charged evaluations |
| --- | ---: | ---: |
| structured DB | **145** | **2,961** |
| V32 adaptive archive | **149** | 2,989 |
| cold start | 141 | 3,267 |

The structured DB therefore exceeds cold on solved tasks while using 306 fewer charged evaluations. It is four solves below the existing V32 archive but uses 28 fewer evaluations. Memory contribution is positive on average for every seed after structural filtering.

Per-seed DB results were 51/96, 55/96 and 39/96. The matched cold results were 49/96, 54/96 and 38/96. Thus the corrected DB did not regress below cold on any development seed.

## What changed technically

- persistent relational storage for strategies, experiences, lineages, evaluations and memory-use events;
- exact behavior/semantic deduplication;
- top-k retrieval over every prior successful observed context;
- compatibility filtering before ranking;
- adaptive utility, confidence, novelty, reuse and success/failure counts;
- time/position aging;
- explicit `memory_contribution` from paired quality and evaluation-cost deltas;
- PostgreSQL deployment schema plus dependency-free SQLite reference backend;
- matched DB / archive / cold benchmark.

## L9 test

**L9 remains open.** V51 is a finite, project-authored development population. It cannot prove an open-ended positive discovery rate. In addition, at least one late window reaches zero first discoveries on individual seeds, so the evidence must not be aggregated into a claim that hides exhaustion.

The useful conclusion is narrower: structured memory is now measurable and, after compatibility correction, provides a positive finite advantage over cold while reducing evaluation cost. That makes it a viable component for the next sustained L9 programme, not a substitute for that programme.
