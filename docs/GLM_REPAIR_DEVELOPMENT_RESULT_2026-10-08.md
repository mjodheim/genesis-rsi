# GLM repair development result — 8 October 2026

GLM-5.3 Flash produced a test-suite-passing repair of the already-exposed
Defects4J Codec-15 case on its second validated candidate. DeepSeek was not
invoked, following the owner's instruction to try it only if GLM did not
produce a validated repair.

This is development on a public, consumed case. It is not fresh blind evidence,
independent validation, a correctness proof or a new Genesis RSI gate.

## Frozen development protocol

`experiment/bench/TRIAL_DEV_OPENROUTER8_GLM_LOW_PREREG.json` fixed before execution:

- model: `z-ai/glm-5.3-flash`, through OpenRouter;
- one read-only exploration arm on Codec-15;
- two candidate validations, one candidate requested per proposal round;
- at most four requests per proposal round and 4,096 total output tokens/request;
- reasoning effort: `low`;
- provider price caps: $0.35/million input, $1.30/million output, no request surcharge;
- conservative reservation caps: $0.03/request and $0.06/proposal round;
- source identities bound by digest and preserved in the local machinery snapshot.

The mutable proposer never controlled compilation, tests or the verdict.
All candidate compilation/test execution used the network-disabled Defects4J
container boundary. Source/test inspection excluded fixed revisions and VCS
history. The checkout was restored after each candidate validation.

## Result and developer-fix audit

The sealed result reports **1/1 solved** under the bench's full-suite predicate,
with two validated candidates over two proposal rounds and first passing rank 2.
The accepted patch modifies `Soundex.java` to traverse a preceding run of H/W
characters before comparing phonetic codes.

Exact recorded model cost for the successful execution: **$0.00142348**.

Only after result sealing, the audit opened the fixed revision. The accepted
file is **not identical to the developer's file**, even ignoring whitespace.
This does not establish that the alternative is wrong or equivalent; correctness
beyond the developer test suite remains unestablished. The accepted patch and
validation receipts remain in the original result file.

## Preceding interrupted attempt

`DEV_OPENROUTER6_GLM` used default reasoning. Its single request cost
**$0.00222820**, consuming 4,096 completion tokens including 3,973 reasoning
tokens. The OpenRouter generation diagnostic confirms both finish reason and
native finish reason `length`. No usable repair was validated and no result was
sealed. That interruption remains preserved; it is not rescored as a scientific
negative. A newly numbered protocol explicitly selected low reasoning before
the successful successor execution.

Combined recorded cost of the two GLM executions: **$0.00365168**.

`DEV_OPENROUTER7_DEEPSEEK` and its low-effort successor
`DEV_OPENROUTER9_DEEPSEEK_LOW` were prepared but never executed. They have no
model calls or repair verdict. The earlier protocol is superseded apparatus;
the latter is a contingent development comparison, not an observed result.

## Evidence and verification

- `experiment/bench/TRIAL_DEV_OPENROUTER8_GLM_LOW_PREREG.json`
- `experiment/bench/TRIAL_DEV_OPENROUTER8_GLM_LOW_RESULT.json`
- `experiment/bench/TRIAL_DEV_OPENROUTER8_GLM_LOW_REVEAL.json`
- Original attempted-call journals and source snapshots:
  `/home/anthony/genesis-bench/DEV_OPENROUTER6_GLM/` and
  `/home/anthony/genesis-bench/DEV_OPENROUTER8_GLM_LOW/`.
- Successful result digest independently recomputed before the reveal audit.
- Focused repair-proposer, bench and sandbox suite: **52 passed**.
- Repository integrity script: passed.

Provider competence is attributed to GLM. Genesis supplied evidence collection,
the repair loop and external-to-proposer validation. Configuration, test and
documentation assistance: OpenAI Codex. No claim of endogenous acquisition or
recursive improvement follows from this model repair.
