# Three further development bugs — 8 October 2026

Prospectively selected Compress-6, Gson-2 and Jsoup-68, from three public development projects, before inspecting the outcomes of this trial. They differ from Codec-15/Csv-16/Collections-24 in the preceding model comparison. They remain exposed development cases, not a fresh held-out sample.

The sealed plan permits memory proposals first, up to four deterministic local operator candidates, then only Haiku 5.5/Luna if necessary. Up to eight candidate validations, two models, two feedback rounds per model and $0.05 API budget per case. The router relaxes its observed-success threshold only when no eligible primary model remains. No developer-authored repair or fixed revision was consulted during the trial.

| Case | Local result | Model assistance | Full-suite success | Durable recipe / memory-only replay |
|---|---|---|---|---|
| Compress-6 | First local operator candidate passed | None | Yes | Verified / passed |
| Gson-2 | Four candidates failed | Haiku inspections, then HTTP 404 | No | No failed repair was learned |
| Jsoup-68 | Four candidates failed | Luna; proposed repair still failed tests | No | No failed repair was learned |

Compress-6 is a genuine no-LLM success under the developer-suite acceptance criterion. The local operator initializes `ZipArchiveEntry.name` in the string constructor. The candidate passed compilation, the triggering tests and the complete developer test suite. Genesis recorded its local-operator provenance, contextual edits and sealed verdict. A freshly opened SQLite reader loaded the retained recipe; the memory-only replay reproduced the same candidate digest and passed the full suite with zero model calls. This is one validated development repair and durable reuse, not general semantic correctness or general RSI.

The prior experience database was copied using SQLite backup before the trial and bound into the plan by a digest. Learning after each case was permitted explicitly. The initial event history remains an exact prefix of the final digest-checked history. Failed validations, model inspections and the API failure are preserved alongside the successful recipe.

## Costs and failure interpretation

Twelve requests were sent. Known API spend is $0.006470695, all from failed assisted cases; Compress-6 and its replay cost $0 in API calls. One Haiku HTTP 404 has no returned usage/cost, so total spend is unknown and the reported known amount is a lower bound, not a zero-filled total. The controller stopped escalation on Gson-2 after that unknown charge. Its conservative router then excluded Haiku for Jsoup-68 and used the configured Luna fallback. This is an API/availability limitation and must not be interpreted as evidence of Haiku reasoning failure. The unknown-cost exclusion remains active until reviewed; no successful trial or missing charge was fabricated.

## Persistent memory and artifacts

The verified final database was copied to the stable development path `/home/anthony/genesis-bench/adaptive-repair/experience.sqlite`, retaining all 56 events, including the original CSV experience and the new Compress repair. [Active memory pointer](../experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json) records the source trial and memory digest. Subsequent development trials should use this memory rather than starting from the older CSV-only database. Frozen scientific evaluations must not ingest this adaptive memory.

[Sealed plan](../experiment/bench/DEV_ADAPTIVE_THREE_BUGS1_PLAN.json), [sealed result and exported memory events](../experiment/bench/DEV_ADAPTIVE_THREE_BUGS1_RESULT.json), and the three per-case result files preserve the exact observations. The source snapshot is retained in the trial workspace.

Implementation added an optional local-operator stage to the development controller, durable learning of local successes and bounded feedback rounds with updated remaining dollar budgets. The standalone trial runner verifies recipe persistence and memory-only replay before classifying a successful observation as verified learning. Local success is distinguished from reuse of a previously retained recipe.

Validation: 69 focused controller, OpenRouter, cost-accounting, repair-benchmark and sandbox tests passed. Repository orphan, dependency and commit-citation checks passed. Additional result audits verified the sealed artifacts, initial/final memory prefix, candidate/recipe digest equality, source snapshot and zero model calls in replay.
