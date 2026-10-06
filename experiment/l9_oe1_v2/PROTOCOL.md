# L9-OE1 v2 prospective qualification protocol

Status: **must be frozen before first v2 behavioral execution**.

This is a clean successor to the retained L9-OE1 v1 qualification. V1 produced a strong positive operational result, but post-run review found three certificate weaknesses: runtime-dependent population regeneration, incomplete candidate-level negative retention, and a retry path that could reuse pre-existing epoch-zero state. V2 fixes those instrument weaknesses prospectively. V1 artefacts remain unchanged.

## Materialized observation programme

- Population seed: 86753117.
- The exact 768-task population is materialized in POPULATION.json before freeze.
- The campaign reads those committed bytes; it never regenerates contexts/tasks.
- Domains: relational SQLite, regular expressions, structured JSON, binary compression.
- Horizon: 12 epochs/domain.
- Tasks: 16 tasks/epoch/domain.
- Acquisition epochs: 0-2.
- Transfer epochs: 3-11, growing from 2 through 10 three-slot motif blocks.
- Four arms: coded-archive, archive-g7, greedy-g7, cold-g7.
- Maximum charged native executions per task: 14.
- Native execution is isolated.

## Fail-closed execution

Every stream must start in a newly-created directory. Epoch zero refuses any pre-existing state or epoch receipt. The epoch-zero state_before_sha256 must equal the digest of the externally fixed default state. Later epochs require exactly the previous state and the campaign verifies every state digest boundary.

## Candidate retention

Every task record retains every charged call with call kind, candidate genome and source hash, full evaluator receipt, and construction metadata. The final report therefore contains positive and negative candidate receipts. The retention predicate is computed from charged-call totals and task records, not from summary counts alone.

## Frozen acceptance predicates

V2 is positive only if all are true:

1. all 768 materialized tasks are retained in every arm;
2. every stream begins from the exact default state and all recovery links match;
3. no task exceeds 14 charged executions;
4. every charged execution has a retained candidate receipt and retained evaluator result;
5. coded-archive solves at least 95% of transfer tasks in aggregate;
6. coded-archive solves at least 90% in every domain/transfer epoch and records at least four newly first-solving semantics there;
7. coded-archive beats archive-g7 by at least 15 points aggregate and 5 points/domain;
8. coded-archive beats greedy-g7 and cold-g7 by at least 20 points aggregate;
9. coded-archive uses no more charged executions than archive-g7;
10. each domain retains four acquired motif parents and codebook descendants for block counts 2 through 10;
11. every transfer epoch/domain contains at least one rediscovery;
12. all task failures, zero-discovery windows, and negative candidate evaluations are retained explicitly in the report.

A single false predicate is a retained negative result. Seed, population bytes, domains, order, thresholds, budgets, arms and mechanisms may not change after freeze.

## Claim boundary

A positive v2 result may close the project-defined **operational L9 gate**: a branching archive sustaining positive discovery while archive size, complexity and domain diversity grow under fixed external governance. It remains finite empirical evidence, not a mathematical asymptotic theorem. L10 remains separately open and requires independent/private or externally authored replication.
