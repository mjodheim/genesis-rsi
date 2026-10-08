# Repair bench

The bench scores a repair mechanism on bugs nobody involved has looked at. See
`genesis/repair_bench.py`, `genesis/repair_proposers.py` and `docs/DEFECTS4J_SANDBOX.md`.

## Split

`experiment/bench/REPAIR_BENCH_SPLIT_V1.json` assigns each active case of the pinned Defects4J
revision to `held_out` when `sha256("genesis-repair-bench-v1|" + case) mod 5 == 0` and the case was
never exposed; everything else is `development`. The whole Lang project and every case a recorded
study, audit or smoke test opened are exposed. The file is written once and sealed by digest.

Held-out cases are listed in hash order and trials take them from the front. A case is consumed
when a preregistration names it. It is never used twice.

Benchmark-wide statistics were computed before the split existed
(`experiment/g12/REPAIR_SEARCH_SPACE_DIAGNOSIS_20261008.md`). They are aggregates and did not
inform any mechanism here, but the split is not pristine in the strictest sense.

## What a case shows a proposer

Only what running the buggy revision's relevant tests shows: failing test names, stack traces,
source around the test frames, and numbered source around the production frames. When no trace
enters production code, the class the failing test is named after is shown instead. The fixed
revision is never checked out during a trial.

## Arms

| Arm | Proposer |
|---|---|
| `strategist` | the existing operator families, no model call (control) |
| `model` | a language model given the evidence in one prompt |
| `model_explore` | the same, with read and search access to a copy of the buggy sources and tests |

Every arm gets the same number of validations per case. An arm works in at most four rounds; each
round it is shown its own earlier candidates with what the validator observed (compiler errors, the
test that still fails, the tests it broke), and it stops at the first candidate that passes the full
suite. Model proposals that touch anything outside the production source directory are dropped.

## Verdict and its limits

A candidate is `plausible` when it compiles, the failing tests pass and the full developer suite
passes. That is not correctness. After a trial is sealed, `scripts/audit_repair_bench_trial.py`
reads the fixed revisions of the solved cases and counts the accepted patches identical to the
developer's, which is a lower bound on correct.

Defects4J is public. A model may have seen these fixes in training, so a model arm's score measures
the loop end to end, not unaided reasoning. Bugs published after a model's training cutoff are the
way to separate the two.

## Running a trial

```
python scripts/run_repair_bench_trial.py preregister --name T1 --held-out 24 --budget 10 \
    --arms strategist model model_explore --provider claude --model claude-sonnet-5-5
git add experiment/bench/TRIAL_T1_PREREG.json && git commit && git push   # before running
python scripts/run_repair_bench_trial.py run --name T1 --workspace /srv/genesis/bench
python scripts/audit_repair_bench_trial.py --name T1 --workspace /srv/genesis/bench
```

A rehearsal names development cases with `--cases` instead of `--held-out`.

## OpenRouter repair agent

New preregistrations use OpenRouter by default, without the Claude CLI.
Existing records without a provider field retain their original Claude route:

```sh
export OPENROUTER_API_KEY=...  # supply privately; never commit the key
python scripts/run_repair_bench_trial.py preregister --name DEV_OPENROUTER_NEXT \
    --cases Codec-15 --budget 2 --per-call 2 --arms model model_explore \
    --provider openrouter --model qwen/qwen3-coder-next
python scripts/run_repair_bench_trial.py run --name DEV_OPENROUTER_NEXT \
    --workspace /home/anthony/genesis-bench/DEV_OPENROUTER_NEXT --parallel 1
```

`qwen/qwen3-coder-next` is the default economical OpenRouter model for this Java repair task.
It is a coding model with tool-call support; this selection is a working
choice, not evidence that it is the best model. The model identity is frozen
per trial, with no model fallback. OpenRouter may route to another provider
serving that same model when an upstream provider is unavailable; the actual
provider is recorded for each response. Other OpenRouter models can be
selected with `--model` before preregistration.

The plain `model` arm receives the same buggy-side excerpts as the existing
proposer and submits exact-text edits. The `model_explore` arm additionally
has bounded `read_file` and literal `search_files` tools over production/test
roots. Neither arm has a shell, network tool, VCS history, fixed revisions,
write access or verdict authority. Candidate execution remains in the
Defects4J sandbox. Inspection refuses traversal, hidden paths and symlinks.

Each proposal round permits at most four OpenRouter requests (one in the
plain arm), each with at most 2,048 output tokens and a 180-second request
timeout. Providers are sorted by price, capped at $0.20/million input tokens,
$1.00/million output tokens, and no per-request surcharge. Before sending,
the agent reserves a conservative input-byte estimate plus 8,192 framing
tokens and the full output allowance. It refuses a reservation over $0.01
per request or $0.03 per proposal round. These estimates are not an
independently verified tokenizer or billing cap. Actual response model,
routed provider, usage and reported cost are
retained. Unknown costs remain unknown. A locally refused budget reservation
sends no request, costs zero, and ends the arm's proposal round without being
classified as a provider failure. A provider error stops further cases
from starting; calls and aborted case outcomes are retained separately and
flushed to disk. A sealed-case cost summary excludes earlier interrupted
attempts; their call journals must also be included in campaign accounting.

OpenRouter preregistrations bind the relevant source files by digest and
refuse execution after a machinery change. **T1 still names Claude** and is
unchanged. An OpenRouter experiment needs its own preregistration; T1's 24
reserved cases cannot become fresh cases for another held-out trial.

For a model-specific comparison, preregister `--input-price`, `--output-price`,
`--call-cost`, `--round-cost`, `--output-tokens` and `--reasoning-effort` explicitly.
Execution reads these values from the frozen record, without runtime overrides.
The economical default limits remain unchanged. GLM's default reasoning exhausted
the output allowance on Codec-15; an explicitly frozen `low` effort successor
produced a full-suite-passing alternative repair at $0.00142348. See the
[complete development result and correctness boundary](GLM_REPAIR_DEVELOPMENT_RESULT_2026-10-08.md).

Implementation: `genesis/openrouter_repair.py`. Substantial implementation
and test assistance: OpenAI Codex. No new self-improvement mechanism or
scientific gate is introduced by this provider adapter.

References: [OpenRouter tool calling](https://openrouter.ai/docs/guides/features/tool-calling),
[Qwen3 Coder Next model](https://openrouter.ai/qwen/qwen3-coder-next),
[provider price limits](https://openrouter.ai/docs/guides/routing/provider-selection).
