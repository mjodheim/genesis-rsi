# Haiku 404 diagnosis, corrected retries and dependency memory replay — 8 October 2026

The owner explicitly requested investigation of the interruption and retries of Gson-2 and Jsoup-68. Earlier plans and negative results are preserved. These are exposed development retries, not a new held-out sample.

## Confirmed 404 cause

The fourth exploratory request changed `tool_choice` from `auto` to a forced named `submit_repairs` function. All returned Haiku 5.5 endpoints advertised `function: false` and `auto: true`. A separate small controlled API check reproduced HTTP 404 with the named function and HTTP 200 with `auto`. The server message was: “No endpoints found that support the provided tool_choice value” (punctuation normalized). This is a client/provider compatibility failure, not model reasoning failure.

The proposer now uses `auto`. On its last request it advertises only `submit_repairs` and explicitly requests a final proposal; inspection remains unavailable. This retains request/validation limits without forcing an unsupported API mode. HTTP failures retain bounded, credential-redacted diagnostic messages.

The old failed attempt and unknown cost remain in memory. A separate append-only review, bound to the live diagnostic and that fourth-call Haiku attempt, excludes this proven incompatible request from routing statistics. Unreviewed unknown costs still prevent escalation; no old charge was replaced by zero.

[Controlled diagnostic and endpoint metadata](../experiment/bench/HAIKU_404_DIAGNOSTIC_20261008.json).

## Retry results

| Case | Successful proposer | Developer suite | Durable memory replay | Retry API spend |
|---|---|---|---|
| Gson-2 | GPT-6 Luna | Passed | Passed after dependency-path correction | $0.004250505 |
| Jsoup-68 | Claude Haiku 5.5 | Passed | Passed | $0.004480800 |

Nine retry requests, no new HTTP 404, all returned usage costs known: **$0.008731305**. The synthetic successful diagnostic request cost $0.0000639 separately. Rejected 404 requests have no usage record, so historical/diagnostic rejected-request charges remain unknown; no combined invoice total is claimed. Local candidates were attempted first and failed on these two cases; the successful retry proposals used external LLMs.

Each positive repair passed compilation, the triggering tests and the full developer test suite. Both recipes were admitted with candidate and verdict digests. No human-authored benchmark repair or fixed revision was consulted. Passing the developer suite remains plausible repair evidence, not proof of semantic correctness or general RSI.

## Additional memory bug found and fixed

The first Gson retry repaired `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`, while the initial stack trace only supplied `gson/src/main/java/com/google/gson/Gson.java`. Recipe lookup originally searched only the initial suspect paths, so the repair was durably stored but the initial memory replay failed. The original retry records this verification failure (`aborted_cases: 1`); it was not overwritten or relabeled.

Recipes now retain the repaired path. Lookup first tries the current suspect paths and then the remembered production path; legacy records recover it from their sealed validator verdict. Paths remain constrained to the current production roots, with symlinks and parent traversal refused. Invalid paths from another project are skipped. A separate, prospectively sealed followup replayed both learned candidates through the full suite, with zero LLM calls and identical candidate digests.

[Preserved retry result](../experiment/bench/DEV_ADAPTIVE_RETRY404_1_RESULT.json), [replay followup plan](../experiment/bench/DEV_ADAPTIVE_RETRY404_1_REPLAY_FIXED_PLAN.json), [successful memory-only followup](../experiment/bench/DEV_ADAPTIVE_RETRY404_1_REPLAY_FIXED_RESULT.json), and [post-run verified summary](../experiment/bench/DEV_ADAPTIVE_RETRY404_1_VERIFIED_RESULT.json).

## Active memory and checks

The successful followup history was appended transactionally to the stable database `/home/anthony/genesis-bench/adaptive-repair/experience.sqlite`. All previous events remain an exact prefix. The database now has 84 digest-checked events, preserving the CSV and Compress experience, old failed attempts, the transport review and both new validated repairs. Previous active-memory pointers were archived before updating the current pointer.

74 focused controller, OpenRouter, cost, benchmark and sandbox tests passed. Regression tests cover the fourth Haiku request, error-message redaction, review without erasing an unknown bill, a learned dependency outside the trace and legacy/path-boundary handling. Repository orphan, dependency and citation checks passed. The original trial and corrected replay each retain their source snapshots.
