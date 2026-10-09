# Compiler-grounded quality and expression learning — 9 October 2026

Anthony authorised end-to-end development and separate new trials. OpenAI Codex
provides substantial implementation assistance. This is an authored substrate;
external teacher repairs and derived capabilities retain model provenance.

## Changes

The strategist adapter now offers explicit provenance preservation. A Candidate
can carry component operators, composition depth and component identities without
changing its content/path digest. Legacy proposer defaults remain unchanged.
A new quality controller distinguishes compilation, behaviour and regression
outcomes, ranks operators using released past evidence and revises the next
choice from its own outcomes. Past failures are not deleted or relabelled.

Verified lexical rules can produce smaller expression templates: comparisons
outside an `if`, and a call wrapper outside its original return statement. API
names and repeated variable bindings remain fixed. The existing trusted Java
analyser runs inside the Docker boundary, providing AST nodes and partial type
information for original buggy production source. Proposed transformations require
resolved compiler-node evidence over their changed spans. Unknown types remain
unknown. A zero-compiler-cost lexical guard rejects invalid statement modifiers,
without treating comments or string literals as code.

Every attempted repair still receives project compilation, trigger tests and the
full suite. Its compilation counts against the candidate budget. The filter does
not run extra uncounted candidate compiles. Shared original-source analysis,
trusted-helper compilation, evidence preparation and successful-repair replay are
separately recorded. Compilation and tests do not prove semantic correctness.
Negative outcomes guide ranking; semantic applicability conditions are not yet
inferred merely from these observations.

## Prospective protocol

[PLAN](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/PLAN.json) is committed
before execution. Teacher development uses the already exposed Jsoup-59, Math-41
and Compress-44: Haiku/Luna only, at most $0.05 API cost per bug, eight candidate
validations, two models and two rounds per model. All requests, failed attempts,
known/unknown charges and durable replay outcomes are retained. Unknown charges
stop further attempts on that bug. Historical unknown charges remain unknown.

Three further cases are selected before their sources are opened: the first
remaining development case for each Jsoup/Math/Compress in the immutable split,
excluding the previous public development exposure census. They are public Java
DEVELOPMENT, not independent blind evidence. No fixed revision is consulted.
Teacher-acquired exact memory is identical in both transfer arms. The parent
uses existing fixed-order candidates. The child additionally uses expression
refinements, compiler-node/lexical filtering and attributed operator ranking.
Both have the same 64-candidate local generation ceiling and at most eight
attempted project compilations per bug. Transfer invokes no LLM. This combined
comparison does not isolate each component's contribution.

Promotion requires a strict solved-case gain, no solved-case regression and no
increase in aggregate candidate compilations. All failures and the decision enter
append-only development experience separately from policy promotion. General
RSI, autonomous primitive invention, multilingual transfer and recursive
acceleration cannot be established by three public cases.

## Execution

```sh
.venv/bin/python scripts/run_repair_quality_trial.py run \
  --output experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1
.venv/bin/python scripts/audit_repair_quality_trial.py \
  experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1
```

The run is one-shot and preserves interruptions. Audit verifies stored evidence
and its snapshots; it is not independent execution replication. Results will be
appended after execution, including any negative or abort verdict.
