# Economical OpenRouter repair integration — 8 October 2026

Status: development integration, no fresh repair result or RSI qualification.

At the owner's request, new repair-bench preregistrations default to OpenRouter
with `qwen/qwen3-coder-next`. Claude remains only an explicitly selected legacy
route; T1's original preregistration is unchanged. The owner subsequently
required economical model selection. The GPT comparison was stopped, and no
automatic upgrade to an expensive model is configured.

The agent can propose exact-text repairs and optionally read/search only buggy
production/test sources. Genesis retains isolated compilation, test-suite
validation and verdict authority. Credentials are supplied by environment and
never copied into the repository.

## Retained development chronology

All cases below use the already-exposed Codec-15 development case. These are
not held-out qualifications. Each local development protocol bound source
digests before invocation; the uncommitted implementation is not represented
as a prospectively committed scientific apparatus.

| Protocol | Model | Outcome |
| --- | --- | --- |
| DEV_OPENROUTER1 | Qwen3 Coder | Interrupted by upstream Google shared-pool 429 errors; no sealed result. Original source and attempt journals retained. |
| DEV_OPENROUTER2 | Qwen3 Coder | Sealed development negative: both arms 0/1 with two validations per arm. Exploration reached the full suite, which rejected a regression. Declared sealed-case cost: $0.0113, excluding earlier attempts. |
| DEV_OPENROUTER3 | GPT-6.1 Sol | No compatible endpoint with the initially required temperature parameter; no sealed result. |
| DEV_OPENROUTER4 | GPT-6.1 Sol | Operator-stopped after the owner's economical-model instruction; no sealed result. At least one retained call reports $0.0153585; this is not a complete execution cost or repair verdict. |
| DEV_OPENROUTER5_ECONOMY | Qwen3 Coder Next | Four retained billable responses report $0.00368256 in total. The next request was refused locally by the conservative cost check. No sealed result. |

The economical test proves that live source inspection, repair generation and
cost refusal operate. It does not prove a correct repair. Its original budget
refusal was classified as an aborted case and remains so. The successor
implementation instead treats a local refusal as a proposal-budget stop with
zero request cost, distinct from a failed API call. This is a prospective
apparatus change, not a relabeling of that execution.

Protocol files and the DEV_OPENROUTER2 result are retained under
`experiment/bench/`. Attempt journals, aborted outcomes and verified source
snapshots are retained under `/home/anthony/genesis-bench/<protocol>/`.
Original interrupted attempts must accompany any later campaign accounting;
unknown API costs must not be treated as zero. A separate synthetic smoke call
reported $0.00035824; an additional diagnostic response reported $0.00128996.

## Current economical controls

- Provider price ceilings: $0.20/million input tokens, $1.00/million output
  tokens, no per-request surcharge, with cheapest providers preferred.
- One model identity per trial; provider failover stays within the price caps.
- At most four requests per exploratory proposal round, one for the plain arm.
- At most 2,048 output tokens per request.
- Conservative reservations refuse above $0.01/request or $0.03/round.
- Reservations use serialized request bytes plus a framing allowance, rather
  than an independently verified tokenizer. They are not a guaranteed invoice
  cap. Repeated trial attempts consume additional resources and remain recorded.
- A refusal before sending costs zero. Missing costs after an API attempt stay
  unknown. Actual reported cost above the request budget stops continuation.

Changing models, machinery or budgets requires a new prospective protocol.
No fresh cases have been consumed by these development rehearsals, and no
model repair competence is attributed to endogenous Genesis machinery.

## Verification and provenance

The final focused suite covers transport failures, source boundaries, symlink
refusal, tool loops, immutable checkout contents, durable call records, provider
price limits and refusal before network access, alongside existing repair-bench
and Docker-boundary tests. Substantial code, test and documentation assistance:
OpenAI Codex. This is external-provider tooling, not a new core RSI mechanism.
