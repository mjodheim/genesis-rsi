# L10-D multi-language causal-retention campaign — prospective protocol

Date: 2026-10-06
Status: **FROZEN BEFORE L10-D ISSUE ENUMERATION OR ISSUE-BODY INSPECTION**

## Why L10-D exists

L10-C established a real public external-transfer pass on a frozen upstream Rust bug,
but its solution proposal came from an external frontier LLM. That is useful evidence
for the composed proposer + Genesis governance/evaluation pipeline, yet it does not
show that Genesis adds capability beyond the same LLM used alone.

L10-D is therefore a causal comparison, not a relabelled strict-L10 attempt.

Primary question:

> Does a fixed external proposer perform measurably better after Genesis is allowed
> to retain and retrieve prior task experience than the same proposer used statelessly?

Secondary question:

> Does the fraction of tasks needing an external proposer begin to decrease as
> reusable experience accumulates?

Strict `l10_independent_passed` remains false throughout this campaign. Independent
task governance, reproduction and adversarial audit remain separate requirements.

## Frozen carrier set

Carrier choice was made before L10-D issue enumeration. Exact upstream HEADs were
queried without inspecting issue metadata or bodies.

| language | upstream | frozen upstream commit |
| --- | --- | --- |
| Python | `pallets/click` | `2247b35ea1c47c727d7a06e51fa280e12a863ff6` |
| Java | `junit-team/junit5` | `47bbcd1f19ec23fc9b357bd4893fd9d40ef8df89` |
| C# | `spectreconsole/spectre.console` | `0de1831405299575419a9cb17d5e7349a3ae61f5` |
| Go | `spf13/cobra` | `adbc8813901bba65827259daa8e22ff94ec1f30e` |
| Rust | `BurntSushi/ripgrep` | `3fce3b5bb0236da2df6d99672afb8a719642eca7` |
| TypeScript | `vitest-dev/vitest` | `7d9f512c09de1478b40ab3d9743702f4cae7247d` |

## Frozen proposer

Both experimental arms use exactly the same proposer identity and budget:

- Claude Code `2.1.289`;
- canonical model `claude-sonnet-5-5`;
- no session persistence;
- one proposer invocation per arm per runnable task;
- tools restricted to `Read`, `Glob`, `Grep`;
- no network/web tools;
- no evaluator code, baseline output, hidden tests or candidate outcome visible;
- structured-edit JSON output only;
- no retry, repair or second proposer call after candidate freeze.

The proposer is external variation. Model-authored code is never attributed as
endogenous Genesis construction.

## Metadata-only task enumeration

Only after the commit freezing this protocol may issue metadata be enumerated.

For each frozen carrier:

1. consider open GitHub issues only, never pull requests;
2. issue creation must predate this protocol freeze commit;
3. accept an issue when any label name, case-insensitive:
   - contains `bug`; or
   - is exactly `defect` or `regression`;
4. require `updated_at` within 365 days before the protocol freeze;
5. sort by `updated_at` descending, then issue number descending;
6. freeze exactly the first **three** matching issue numbers, or every matching issue
   if fewer than three exist.

The selected issue-number matrix must be committed before any selected issue body,
comments, linked pull requests or code-specific task content are fetched.

All selected tasks remain in the campaign. A later unusable or already-fixed task is
preserved with its classification; it is not silently replaced.

## Task preparation and runability

After the issue-number matrix is frozen, fetch the exact public issue payload for
every selected task and commit it unchanged.

For each task, in the frozen order:

1. clone/check out the exact carrier commit above;
2. define one task-specific objective and one ordinary regression command;
3. freeze evaluator bytes, toolchain/container identity and resource limits;
4. execute the unmodified baseline;
5. classify it as one of:
   - `RUNNABLE_FAILING_BASELINE`;
   - `BASELINE_ALREADY_SATISFIES_OBJECTIVE`;
   - `UNRUNNABLE_UNDER_FROZEN_BOUNDARY`.

Only `RUNNABLE_FAILING_BASELINE` tasks enter the two-arm comparison.

No candidate may influence runability classification or evaluator design.

## Two-arm causal comparison

Every runnable failing task receives two isolated candidate runs.

### Arm A — stateless proposer control

The proposer receives:

- the current issue payload;
- read-only access to the frozen carrier source;
- the common structured-edit output contract.

It receives **no L10-D prior-task experience**.

Each task starts a fresh proposer session.

### Arm B — Genesis cumulative-memory arm

The proposer identity, model, tool restrictions, budget and current-task information
are identical to Arm A.

The only added input is a Genesis-generated **experience context** retrieved from
tasks completed *before* the current task.

The current task's Arm-A output/result, baseline output, evaluator bytes and hidden
objective details may not enter Arm B before both candidate trees are frozen.

## Experience store

L10-D starts with a new empty campaign memory namespace. It does not preload hand-written
software advice.

After both candidates for task N are evaluated, Genesis stores a deterministic record
containing only campaign-observed data:

- carrier/language;
- public issue title, labels and body;
- candidate structured edits from each arm;
- touched paths and changed symbols/tokens derivable from the edit;
- evaluator verdict and regression result;
- failure signature when applicable;
- proposer usage metadata (turns, latency, token/cost data when available).

Before Arm B of task N+1, Genesis retrieves at most five previous records using a
frozen deterministic lexical ranking over public task text plus changed paths/tokens.
No extra LLM call may be used to create, rank or rewrite the retrieved memories.

The exact retrieved record IDs and bytes are frozen with the proposer input.

This makes persistence/retrieval — not a different model or a larger inference budget —
the intended causal difference between the two arms.

## Arm ordering and isolation

To reduce order bias, arm execution order is deterministic from:

`sha256("<carrier>/<issue-number>")`

- even low bit: A then B;
- odd low bit: B then A.

Both candidate outputs are frozen before either candidate is evaluated.

Neither arm sees the other arm's current-task candidate.

## Structured-edit contract

Both arms return exactly:

```json
{
  "edits": [
    {"path": "relative/file", "old": "exact existing text", "new": "replacement text"}
  ],
  "rationale": "..."
}
```

The importer is identical for both arms and follows the L10-C deterministic contract:
no fuzzy matching, no manual repair, no path escape, no post-result normalization.

## Metrics frozen in advance

Per task and arm record:

- objective pass/fail;
- regression pass/fail;
- candidate import success/failure;
- proposer wall time;
- turns;
- input/output tokens when exposed;
- monetary cost when exposed;
- files/edits touched;
- retrieved-memory count and IDs for Arm B.

Campaign summaries must include:

- runnable task count and language coverage;
- solved-task count A vs B;
- regressions A vs B;
- tasks solved by B while A fails;
- tasks solved by A while B fails;
- cumulative success curves by task index;
- cumulative proposer cost/tokens by arm;
- whether the A→B gap grows, shrinks or stays flat as experience accumulates.

No task may be omitted from aggregate tables because its result is inconvenient.

## Internal-only probe

Before invoking any external proposer on a runnable task, Genesis may attempt a
deterministic internal-only transformation **only** if its frozen experience engine
finds an exact supported structural transformation from previous records.

Rules:

- no LLM/model/API call;
- one internal attempt maximum;
- candidate frozen before evaluation;
- failure is retained;
- an internal-only success does not remove the task from the A/B comparison; A and B
  still run so the causal baseline remains measurable.

This probe establishes the first quantitative curve for external-model dependence.
A zero-success result is valid evidence and must be preserved.

## Predeclared interpretation

L10-D is considered to show a **causal retention signal** when all are true:

1. at least six runnable failing tasks span at least three languages;
2. Arm B solves at least one task that Arm A fails;
3. Arm B does not have a higher regression count than Arm A;
4. the B-only success used at least one previously frozen Genesis experience record;
5. no model/budget/tool asymmetry exists between A and B.

This is deliberately a modest signal, not a proof of general superiority.

A stronger result is recorded if B has a positive net solved-task delta over A and the
delta increases in the later half of the campaign.

Any internal-only success on a previously unseen task is reported separately as
evidence of reduced proposer dependence.

## Claim boundary

L10-D can test whether Genesis adds measurable value to a fixed LLM through persistent
experience and can begin measuring declining LLM dependence.

It cannot by itself establish AGI, open-ended RSI, general software autonomy, or strict
L10 independent replication.

Strict L10 remains a later external-governance/reproduction/audit event.
