# L10-C fresh-carrier structured-edit pilot — prospective protocol

Date: 2026-10-06
Status: **FROZEN BEFORE L10-C ISSUE ENUMERATION OR TASK INSPECTION**

## Motivation

L10-A was a valid baseline-only calibration: selected historical issues were already
fixed at current upstream revisions. L10-B found a real failing external bug in
Sherlock #2970, but the single external proposer returned a semantically plausible
yet syntactically malformed unified diff. That candidate was rejected before
evaluation and is preserved; it is not repaired or retried.

L10-C is a fresh-task successor. It changes two design choices prospectively:
- fresh independently maintained carriers;
- a deterministic structured edit transport rather than unified-diff text.

No L10-A or L10-B task may be reused in L10-C.

## Frozen carriers

| language | upstream | frozen upstream commit |
| --- | --- | --- |
| Python | `encode/httpx` | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` |
| Java | `mockito/mockito` | `116a4d6231dc35f90543060af41dcde00fe4e2ae` |
| C# | `FluentValidation/FluentValidation` | `fa3c160b17796ff67d6aa5ae6c4b05b471f1a791` |
| TypeScript | `colinhacks/zod` | `0b216ef674e297ebe41d8bf902262e56f8755822` |
| Rust | `sharkdp/bat` | `4608fc959aa8abf80d32198836511a570b7ae9ea` |

The carrier set was chosen before L10-C issue enumeration for language diversity,
active maintenance and ordinary local test/build workflows.

## Metadata-only task selection

After this protocol commit, enumerate only GitHub issue metadata.

For each carrier:
1. consider open issues, never pull requests, created before this protocol commit;
2. accept an issue when any label name, case-insensitive, either:
   - contains the substring `bug`; or
   - is exactly `defect` or `regression`;
3. require `updated_at` within 180 days before this protocol commit;
4. sort by `updated_at` descending, then issue number descending;
5. select exactly the first issue;
6. if none exists, record `NO_ELIGIBLE_ACTIVE_BUG`.

Issue bodies may not be fetched until the metadata selection is committed.
No selected issue may be skipped or replaced after inspection.

## Runability and evaluator freeze

For each selected issue, after its exact public payload is committed:
- define one task-specific objective and one regression command;
- freeze toolchain/image identities and evaluator bytes;
- only then execute the baseline;
- if the baseline already satisfies the objective, preserve
  `BASELINE_ALREADY_SATISFIES_OBJECTIVE`;
- if the objective cannot be evaluated without unavailable hardware, credentials,
  destructive side effects or paid/private services, preserve
  `UNRUNNABLE_UNDER_FROZEN_BOUNDARY`.

No replacement issue is allowed within this pilot.

## External proposer

The proposer is frozen as:
- Claude Code 2.1.289;
- canonical model `claude-sonnet-5-5`;
- one invocation per runnable failing carrier;
- no session persistence;
- tools restricted to `Read`, `Glob`, `Grep`;
- no evaluator, baseline output or prior candidate outcome visible;
- no retry after a candidate result.

Model-authored code is external variation and is not attributed as endogenous Genesis
construction.

## Structured edit contract

The proposer returns exactly:

```json
{
  "edits": [
    {"path": "relative/file", "old": "exact existing text", "new": "replacement text"}
  ],
  "rationale": "..."
}
```

The deterministic importer:
1. rejects empty edit lists, absolute paths, path traversal and duplicate paths unless
   each later edit targets the result of an earlier edit in the declared order;
2. for each edit in output order, requires `old` to be non-empty and to occur exactly
   once in the current candidate file bytes decoded as UTF-8;
3. replaces that exact occurrence with `new`;
4. permits no file creation/deletion/rename and no path outside the frozen carrier;
5. computes and freezes the resulting candidate tree before any evaluator runs.

There is no fuzzy matching, hunk recount, manual correction or post-result normalization.

## Claim boundary

L10-C can provide public external-transfer evidence for the composed
proposer + Genesis governance/evaluation pipeline. It still cannot set strict
`l10_independent_passed=true`; strict L10 requires separately governed external
task authorship/maintenance, independent reproduction and adversarial audit.
