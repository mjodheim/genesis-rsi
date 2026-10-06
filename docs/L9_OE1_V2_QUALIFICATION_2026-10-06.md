# L9-OE1 v2 qualification — 6 October 2026

## Verdict

**L9_OPERATIONAL_GATE_PASSED**

The audited v2 successor passes every predicate frozen before its first behavioral
execution. This closes the project's finite **operational L9 gate** under the exact
prospective criterion. It is not an asymptotic theorem and it does not close L10.

## Why v2 exists

The retained v1 qualification was strongly positive, but post-run review found three
certificate weaknesses: runtime-dependent regeneration of binary-compression contexts,
candidate-level negative receipts were not retained in the final report, and a retry
path could reuse pre-existing epoch-zero state. V2 was created as a separate successor;
v1 was not edited or relabelled.

V2 fixes all three prospectively:
- the exact 768-task population is committed as immutable JSON bytes;
- epoch zero refuses prior state and is bound to the default-state digest;
- every charged candidate, including failures, is retained in the archived report.

## Frozen chronology

- apparatus/population commit: `590489e6`
- freeze commit: `8c326d83`
- new seed: `86753117`
- population file SHA-256: `c32d0c6f331e471152885c3d43f2f2e516a962974cfb54e7b15d2592d3bf4344`
- freeze SHA-256: `2e8b58aff4c99ab6f25b1a73cd9da3f92d398bcb5b8e77703314ff224459e3cc`
- raw report SHA-256: `a05b06ce54dd981e6218cdc5f3c0d21be74149e08668fbad03f877ed88bbf84c`
- deterministic gzip SHA-256: `f44f14cf4ffacff9ea2111c5c41e9576a7a7bf95f882853b95fa457fe6aa1de5`

No v2 candidate was executed before the apparatus and freeze commits.

## Prospective programme

Four materially different native domains were evaluated:
SQLite, regular expressions, structured JSON and binary compression.

Each arm saw:
- 12 epochs/domain;
- 16 tasks/epoch/domain;
- 768 total tasks;
- acquisition epochs 0–2;
- transfer epochs 3–11;
- transfer complexity growing from 2 to 10 learned three-slot blocks;
- at most 14 charged native executions/task;
- isolated native execution.

## Aggregate transfer result

| Arm | Solved | Tasks | Solve rate | Evaluations |
|---|---:|---:|---:|---:|
| coded-archive | **576** | 576 | **100%** | **5,414** |
| archive-g7 | 71 | 576 | 12.33% | 7,179 |
| greedy-g7 | 11 | 576 | 1.91% | 7,407 |
| cold-g7 | 0 | 576 | 0% | 7,488 |

The coded archive solved **768/768 tasks overall**.

Per-domain transfer:
- relational SQL: coded 144/144 vs archive-G7 20/144;
- regular expressions: coded 144/144 vs archive-G7 2/144;
- structured JSON: coded 144/144 vs archive-G7 18/144;
- binary compression: coded 144/144 vs archive-G7 31/144.

Maximum charged calls/task for coded-archive were 12, 12, 12 and 14 respectively.

## Sustained discovery and archive evidence

The coded arm recorded:
- 288 newly first-solving transfer semantics;
- 268 rediscoveries;
- four acquired motif parents/domain;
- nine persisted codebook descendants/domain, covering transfer block counts 2 through 10;
- positive discovery and rediscovery in every transfer epoch/domain.

All frozen predicates are true.

## Negative evidence retention

The archived report contains every task record and every charged candidate receipt.
It retains **31,398 negative candidate receipts** rather than inferring their existence
from aggregate counts.

The uncompressed report is 92,297,609 bytes. It is stored losslessly as deterministic
gzip to avoid a near-100 MB Git object. The audit checker verifies both compressed and
raw hashes, decompresses the full report and recalculates adjudication from all 16
streams.

## Claim boundary

This result is finite, project-authored empirical evidence for the project's operational
L9 definition: branching learned structure, increasing task complexity across multiple
domains, sustained discovery/rediscovery and fixed external evaluation/budget
governance.

It does **not** establish mathematical asymptotic open-endedness, general RSI or AGI.
**L10 remains open** and requires independent/private or externally authored
replication under its own governance.
