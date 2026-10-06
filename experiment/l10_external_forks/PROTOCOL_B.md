# L10-B active-bug external fork pilot — prospective protocol

Date: 2026-10-06
Status: **FROZEN BEFORE ISSUE-METADATA ENUMERATION, ISSUE-BODY INSPECTION, BASELINE OR CANDIDATE EXECUTION**

## Why this successor exists

L10-A was valid but non-qualifying: its deterministic oldest-bug selection chose two
public issues whose frozen current upstream revisions already satisfied the objective,
and three carriers had no eligible bug-labelled issue. No candidate was executed.

L10-B is a new prospective successor. It does not rescore or replace any L10-A task.
Its only task-selection change is designed from the disclosed L10-A calibration:
prefer recently active bug reports rather than the oldest still-open report.

## Frozen carrier set

| language | upstream | frozen upstream commit |
| --- | --- | --- |
| Python | `sherlock-project/sherlock` | `e40a45ec2a074b90703b3b4b842c8a3adbd6ada3` |
| Java | `jhy/jsoup` | `088614f4a1454232a1f03c63b7f80742f1f2a854` |
| C# | `Humanizr/Humanizer` | `e4da08c5e631975e15bb98ae020aede819d376ca` |
| TypeScript | `markedjs/marked` | `e809386482250c5c856d54e34b5930ee7a5faa4f` |
| Rust | `sharkdp/hyperfine` | `ef86c830b509fd734b9f13d2f30cbe3e8c834276` |

These repositories were selected before any L10-B issue enumeration for language
diversity, active maintenance, manageable repository size and ordinary local
test/build workflows.

## Deterministic metadata-only task selection

After this protocol commit, enumerate issue metadata only. Do not fetch issue bodies
during selection.

For each carrier independently:

1. consider open issues (never pull requests) created before this protocol commit;
2. accept an issue if at least one case-insensitive label is exactly one of:
   `bug`, `type: bug`, `type/bug`, `kind/bug`, `defect`, `regression`;
3. require `updated_at` to be within 120 days before this protocol commit;
4. sort eligible issues by `updated_at` descending, then numeric issue number descending;
5. select exactly the first issue;
6. if none exists, record `NO_ELIGIBLE_ACTIVE_BUG`.

No issue may be skipped or replaced because its content, implementation, platform,
difficulty or expected result is inconvenient.

Only after the selected issue number is committed may its body and linked reproduction
material be inspected. The exact issue payload must then be hashed and frozen before
baseline evaluation or candidate generation.

## Runability and baseline

After body freeze, define one task-specific external objective and regression command
before running either. If the task requires credentials, paid services, unavailable
hardware, destructive side effects or unsupported operating systems, record
`UNRUNNABLE_UNDER_FROZEN_BOUNDARY` and do not substitute another issue.

If the frozen upstream baseline already satisfies the objective, record
`BASELINE_ALREADY_SATISFIES_OBJECTIVE` and do not score a candidate.

## Candidate attribution

Candidate generation remains an explicit external variation source, not lineage-owned
competence. For each runnable failing baseline:

- one proposer invocation only;
- official Codex CLI, model `gpt-5.6-sol`;
- proposer may inspect frozen carrier checkout and public selected issue payload;
- proposer receives no hidden evaluator source/output and no previous candidate result;
- candidate diff is frozen before evaluation;
- no repair/retry/replacement after candidate evaluation.

Genesis owns the governed isolation, evidence retention, evaluator boundary, candidate
selection/adoption logic and learned-history handling. Any model-authored code remains
attributed to the composed system.

## Claim boundary

L10-B can supply stronger multi-language public external-transfer evidence.
It cannot set strict `l10_independent_passed=true`: the L10 handoff additionally
requires genuinely independent task governance/reproduction/adversarial audit outside
the project owner's and this assistant's control.
