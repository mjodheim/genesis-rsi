# Genesis V2.1 — Typed semantic hypotheses

**Implementation status: opt-in Java research adapter with source-only
hypothesis generation and external validation. NOT general RSI.**

## Why this exists

V2.0 only learned candidate *order* from already measured results. It cannot
discover a mutation when none of the old Java operators can express the
repair. V2.1 introduces a first, restricted program hypothesis language
which can propose source changes **before a passing patch exists**.

## Hypothesis grammar (version 1)

The only supported construct is a peer-derived method contract:

- Observation: at least two sibling methods, in the same Java class, with
  matching return/argument types, include an identical Boolean guard and
  class-typed static-final fallback constant.
- Suspicion: another same-type method uses its argument but omits the shared
  guard.
- Hypothesis: insert the same early guard and fallback return, respecting
  an existing public argument null check.

The predicate is a typed expression with an instance Boolean field, the
same field on the method's argument, and either || or &&. Names and return
constant come from observed source, not a preselected benchmark repair.
Methods, field declarations and class scopes are extracted from masked Java
text (comments and strings excluded). This is NOT yet a complete Java AST
or resolved type engine; compilation plus tests are mandatory downstream.

A hypothesis is an immutable, content-addressed document containing source
hash, target method, donor quorum, typed predicate, placement and evidence
scope. The compiler re-derives every source witness before emitting the edit;
it rejects stale source, paths outside the buggy tree, unsupported grammar,
non-static or non-final fallback constants, cross-class witnesses and
unjustified declarations. It never executes the emitted Java itself.

## Language modules

A bounded, explicitly populated registry handles routing, rather than a
hardwired code path in the core. The only supported plugin today is
v21.java.contract-inference, handling .java files.

Modules can be attached and detached. Immutable signed hypothesis records
survive a module's removal; compilation is unavailable until the proper
versioned module returns. The registry does not dynamically import arbitrary
plugin code or grant languages access to the evaluator or promotion gate.

A broader system needs native adapters for Python, C#, TypeScript and other
languages. The current Java implementation is a prototype, not support
for all programming languages.

## Tests and evidence

Two independent synthetic Java contracts were written with arbitrary class
and Boolean-field names not recognized by the older G11 sibling operator.
V2.1 automatically proposed a Boolean || guard in Signal/corrupt and a
Boolean && guard in Parcel/flagged, before the separate test oracle ran.
For both fixtures, the original version failed the new assertions; the
transformed version compiled and passed.

On an **already exposed** real bug, Math-53, V2.1 proposed a guard in
Complex.add from three sibling methods (subtract, multiply, divide).
The hypothesis was frozen in
V21_MATH53_PROPOSAL_FREEZE_20261008.json, committed as d115b574
**before** the independent Defects4J evaluator ran. Full project tests
passed with zero failures. The complete result, which records zero unseen
successes, is saved in
V21_MATH53_DEVELOPMENT_VALIDATION_20261008.json.

This reproduces an existing development repair through the new typed
hypothesis DSL, not a first blind external repair: Math-53 has already been
examined and the guard-contract grammar was designed by a human assistant.

The default V1 and V2.0 behavior remains unchanged. The repair strategist
can opt in with v21_semantic_hypotheses_experimental=True, and the typed
family can coexist with a V2 policy genome. Proposals from the DSL are
**hypotheses**, not trusted fixes; only an independent compiler and
full-suite tester can validate them.

## What G12 / RSI requires next

The *grammar itself* is currently human-engineered, and the proposed
hypotheses are derived from one predetermined pattern. True semantic
self-extension requires Genesis to propose revisions to this grammar or
entirely new operation schemas, verify their safety and semantics in a
trusted typed interpreter, and show on preregistered untouched tasks that
those proposals solve bugs unavailable to the frozen parent.

No claims of unrestricted code synthesis, automatic general RSI, or
production promotion are supported by this stage.
