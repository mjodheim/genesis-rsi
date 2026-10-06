# L10-A external fork pilot — prospective protocol

Date: 2026-10-06
Status: **FROZEN BEFORE TASK INVENTORY OR CANDIDATE EXECUTION**

## Scientific role

This pilot stress-tests Genesis on independently maintained public software carriers.
It is deliberately **not** sufficient to set `l10_independent_passed=true`.
The project-defined L10 ceiling still requires separately governed external task
authorship/maintenance, independent reproduction, and adversarial audit.

No candidate may be executed against any carrier until:
1. this protocol is committed;
2. a deterministic task inventory is materialized from upstream metadata;
3. the selected task, exact issue payload, evaluator commands and carrier checkout are
   committed in a second freeze record.

Failures are retained. A carrier may not be silently replaced after an inconvenient task.

## Frozen carrier set

Exactly one carrier per language family is admitted:

| language | upstream | frozen upstream commit |
| --- | --- | --- |
| Python | `pallets/click` | `2247b35ea1c47c727d7a06e51fa280e12a863ff6` |
| Java | `google/gson` | `845664ba1c307e6c1910d07cfed2f622e0ad8df1` |
| C# | `spectreconsole/spectre.console` | `0de1831405299575419a9cb17d5e7349a3ae61f5` |
| TypeScript | `sindresorhus/p-map` | `2c0934b8312b637f933b752c6054845c2d2d5533` |
| Rust | `BurntSushi/ripgrep` | `3fce3b5bb0236da2df6d99672afb8a719642eca7` |

The carrier set was chosen for language diversity, public independent maintenance,
manageable repository size and ordinary local test/build workflows. None of these five
repositories had its task issue body inspected for this pilot before this freeze.

## Deterministic task selection

After this commit, collect open GitHub issues for each frozen upstream without executing
Genesis or modifying the carrier. Selection uses metadata only.

For each carrier:
- consider open issues, not pull requests, created before this protocol commit;
- sort by numeric issue number ascending;
- select the first issue carrying at least one case-insensitive label in:
  `bug`, `type: bug`, `type/bug`, `kind/bug`, `defect`, `regression`;
- do not rank, skip or replace an issue because its implementation looks hard;
- if no issue satisfies the label rule, record `NO_ELIGIBLE_TASK` for that carrier.

Only after the issue number is selected may its body and linked reproduction material be
read. The complete selected issue payload must then be hashed and frozen before candidate
execution.

If the selected task cannot be evaluated locally without credentials, paid services,
network access during candidate evaluation, destructive side effects, or unavailable
platform hardware, record `UNRUNNABLE_UNDER_FROZEN_BOUNDARY`; do not substitute another
issue in the same pilot.

## Evaluation boundary

Use the existing `genesis.real_project` isolation discipline where applicable:
- bind the exact host tree before candidate evaluation;
- establish the unchanged baseline first;
- evaluate candidates only in disposable workspaces;
- keep evaluator commands and authority paths outside the mutable image;
- derive acceptance from host-owned process outcomes, never candidate self-report;
- preserve every attempted candidate and negative;
- leave the frozen upstream checkout and protected/default branches unchanged;
- retain a deterministic replay of any accepted patch.

Task-specific setup and evaluator commands belong to the second freeze and may not be
changed after Genesis sees a candidate outcome.

## Pilot claim

A positive carrier result may support only:

> Genesis transferred its bounded evidence-based real-project evaluation/selection
> discipline to this frozen external carrier under the prospectively frozen task and
> evaluator.

Five positive carriers would be strong multi-language external-transfer evidence, but
would still not satisfy strict L10 independence without the separately trusted external
maintainer, reproducer and adversarial auditor required by the L10 handoff.

## Stop rules

- Never tune the task, evaluator, budget or acceptance rule after observing a candidate.
- Never discard a negative carrier and replace it in this pilot.
- Never reinterpret infrastructure failure as task success.
- Never write an accepted patch upstream automatically.
- Never claim AGI, general RSI or independent L10 from this pilot.
