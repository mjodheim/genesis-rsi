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

## Completed observations

The code/protocol was committed and pushed before the teacher and transfer run.
The teacher solved all three exposed development bugs with Haiku, and all three
accepted repairs passed full-suite fresh-reader replay:

| Teacher development case | Known API cost | Durable replay |
|---|---:|---|
| Jsoup-59, empty trimmed attribute name | $0.0019091 | passed |
| Math-41, weighted variance array segment | $0.0035033 | passed |
| Compress-44, constructor null arguments | $0.0009735 | passed |

**Five API requests cost $0.0063859**, failed/read/proposal requests included;
all new charges are known. Historical unknown charges remain unknown. Runtime,
infrastructure and developer effort are excluded. This is three assisted repairs,
not three autonomous inventions. Their exact recipes entered durable memory.
The extractor retains five lexical rules and derives two smaller expression
proposals. The multiline constructor insertion is outside this acquisition
substrate; a durable recipe is not automatically a generalized capability.
The authored substrate gate still passes six positives and rejects its controls.
It does not test the two new teacher-derived rules on independent real tasks.

| Fresh public Java development case | Parent / child solved | Candidate compilation attempts per arm | Learned candidates |
|---|---|---:|---:|
| Jsoup-25 | no / no | 0 / 0 | 0 |
| Math-37 | no / no | 8 / 8 | 0 |
| Compress-18 | no / no | 8 / 8 | 0 |

There is **0/3 success in either arm** and no quality-policy promotion. The
32 attempted candidates include four compilation failures, two in each arm;
all remaining attempts fail triggering tests. The child removes 17 known-invalid
modifier proposals from Math's 64-candidate pool, but this does not improve the
observed solved-case or tested compilation result. These are different cases
from the previous 34/48-failure cohort, so comparing those rates across cohorts
would not establish a causal gain. No learned expression activated on these
causal views. Jsoup has no production trace and the legacy naming fallback
finds no class, so both arms receive empty pools. Zero attempts is a localisation
failure, not a successful reduction of repair cost.

All analysis/compiler commands are inventoried in
[DIAGNOSIS](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/DIAGNOSIS.json), including
shared original preparation, trusted helper compilation, two source analysis
queries, authored gate compilation and teacher replays. Every candidate's explicit
project compilation is counted. There is no extra candidate compiler screen.
Passing compilations alone are not sufficient to solve a bug. A cost per verified
new real transfer capability cannot be reported because no such success exists.

The verified complete 50-event suffix enters canonical development memory:
**173 → 223**, including three successful recipes, teacher calls, failed attempts,
proposals and the rejection decision. Memory admission is separate from policy
promotion. All six buggy source/test trees were checked and restored.
[RESULT](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/RESULT.json),
[VERIFICATION](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/VERIFICATION.json),
[DECISION](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/DECISION.json) and
[PROMOTION](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/PROMOTION.json)
preserve the evidence. Audit verifies stored records, not independent execution.

## Subsequent localisation engineering

The completed result is unchanged. A prospective opt-in `localize_assertions`
argument to `collect_evidence`, exposed by adaptive repair's
`--localize-assertions`, infers bounded production method hypotheses from calls
and local variable declarations in the failing test method. Expected literals,
strings and comments cannot become code templates. Ambiguous class names,
symlinks and nonproduction targets are excluded. This is static API evidence,
not runtime coverage, an executed call graph or causal proof. Default behaviour
is preserved; the rejected quality policy is not activated automatically.

A separate now-exposed Jsoup-25 engineering check yields 12 method locations in
Jsoup/Element and 64 existing-operator candidates, versus the empty original
pool. It performs no repair validation and claims no repair success or fresh
transfer. See
[ASSERTION_LOCALIZATION_DEV_CHECK](../experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1/ASSERTION_LOCALIZATION_DEV_CHECK.json).
The new helper is written after the frozen run and is not included in its earlier
machinery snapshot. Research reproduction uses that earlier snapshot.

Validation before execution: 117 focused tests, including real sandboxed Java AST
analysis. Subsequent localisation tests verify literal independence, ambiguity,
source boundaries and preservation of existing stack-derived evidence. Full
focused-suite and repository checks are repeated after this successor change.

General RSI is not demonstrated and the research objective remains incomplete.
Remaining priorities are better causal localisation beyond direct calls,
acquisition of multiline/state/algorithmic repairs, semantic applicability
conditions and separate demonstrations of real transfer across generations.
Adding a syntactic/type guard does not establish those capabilities.

Final verification: **121 focused tests pass**, with no skip on this host; the
repository import, orphan, dependency and citation checks pass. The adaptive CLI
exposes the new opt-in localisation flag. The original result and its audit are
unchanged after the post-result helper was added.
