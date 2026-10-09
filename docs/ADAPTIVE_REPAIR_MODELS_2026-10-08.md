# Economical repair models and retained experience — 8 October 2026

Anthony requested MiMo V2.6 Pro/Flash, Claude Sonnet/Haiku 5.5 and GPT-6 Luna, plus economical routing and reduced reliance on external LLMs. All five were tested on the same exposed development cases: Codec-15, Csv-16 and Collections-24.

| Model | Full developer-suite passes | Total API spend | Spend / suite pass |
|---|---:|---:|---:|
| MiMo V2.6 Flash | 0/3 | $0.006989 | undefined (zero passes) |
| MiMo V2.6 Pro | 0/3 | $0.017611 | undefined (zero passes) |
| Claude Haiku 5.5 | 3/3 | $0.013029 | $0.004343 |
| GPT-6 Luna | 1/3 | $0.003091 | $0.003091 |
| Claude Sonnet 5.5 | 2/3 | $0.123708 | $0.061854 |
| Qwen3 Coder | 0/3 | $0.012620 | undefined (zero passes) |
| GLM-5.3 Flash | 1/3 | $0.005049 | $0.005049 |
| DeepSeek V4.1 Flash | 0/3 | $0.013393 | undefined (zero passes) |
| DeepSeek V4 Pro | 0/3 | $0.007127 | undefined (zero passes) |

GPT-6 Luna had the lowest observed spend per suite-passing repair ($0.003091), but succeeded on only one of three cases. Haiku 5.5 succeeded on all three, at $0.004343 per suite pass, and is the provisional default when reliability matters. Sonnet cost about 14 times more per suite pass than Haiku and did not succeed on Csv-16. No claim of global superiority follows from three public, exposed cases.

New five-model API spend: $0.164429. Both comparison cohorts together: $0.202618. Costs include unsuccessful calls, reasoning tokens, cache pricing and truncated responses. Reasoning tokens are a subset of output tokens, never added twice. All recorded charges are known. Historical pilot/tuning costs and infrastructure are excluded.

The protocols permit two candidate validations per case, 4,096 output tokens per response, four requests per proposal round and four rounds. Dollar reservation ceilings were raised for MiMo Pro and Sonnet to admit their tariffs; they are not identical to cheaper-model dollar ceilings. Routes that reject temperature receive no temperature parameter. These differences limit comparison with the earlier cohort. MiMo outcomes include output truncation and conservative reservation stops; they are configuration failures, not evidence of maximum model capability. Original negative/aborted records remain intact and unsealed trials are explicitly labeled.

Exact evidence: [new comparison](../experiment/bench/DEV_MODEL_COST_COMPARISON2_RESULT.json), [previous comparison](../experiment/bench/DEV_MODEL_COST_COMPARISON1_RESULT.json), and the individual preregistrations.

## Development router and experience reuse

Implemented in `genesis/adaptive_repair.py`, exposed through `scripts/run_adaptive_repair.py`. This is an opt-in development service, not a silent change to frozen evaluation policies or a general RSI result.

The router classifies observable task size using suspect source-file count, source excerpt length and failing-test count. It estimates cost per suite-passing proposal from released outcomes with explicit smoothing. Context-specific observations take precedence; released comparison averages serve as a fallback. As a provisional reliability filter, models with at least three observations and less than 50% suite passes are excluded; callers can adjust `--minimum-success-rate`. This threshold and the complexity proxies are authored heuristics, not calibrated probability estimates. Budget limits may exclude a more expensive fallback.

Before a model call, Genesis tries retained repair patterns with matching exception/language families and unique source contexts. Every reused proposal must pass compilation, triggering tests and the full developer suite again. Passing proposals retain local search/replace patterns, provenance, explanation and validator digest in a persistent SQLite event chain. Different file paths and unrelated source regions can reuse a matching local pattern. Failed proposals cannot create recipes. Unknown costs stop escalation and remain visible.

The complete focused repair checks passed (66 tests); an additional online-learning/next-invocation reuse test then passed, giving 67 distinct passing tests, including nine controller tests. Tests cover transfer to another filename, revalidation failures, complexity-dependent routing, the reliability filter, unknown costs, corruption rejection, exact archived-patch context and learning a model proposal for reuse on the next invocation.

## Live reuse demonstration

A sealed Haiku Csv-16 patch was independently revalidated by the sandboxed developer-test harness before admission into development memory. Genesis then proposed the retained transformation and passed the full suite with zero external LLM calls. A second invocation with an unrelated source comment changed also passed the full suite with zero model calls, showing that this reuse does not require the entire file to be identical. This remains the same exposed public bug with a superficial source variation, not a fresh-task or semantic-generalization result.

Artifacts: [initial reuse](../experiment/bench/DEV_ADAPTIVE_REUSE1_RESULT.json) and [source-variation reuse](../experiment/bench/DEV_ADAPTIVE_REUSE1_TRANSFER_RESULT.json). The local experience database lives outside the public repository; exported result artifacts contain provenance and validation evidence.

This memory is useful retained experience. It does not establish broad comprehension, automatic algorithm invention or that arbitrary future tasks of a similar kind will require no LLM. The next meaningful research test would freeze a learned policy and evaluate transfer on genuinely new tasks without contaminating held-out benchmarks.
