# Autonomous RSI software track

**Status: DEVELOPMENT. This document defines a target and records engineering
milestones; it claims no general autonomous software-engineering result.**

## Objective

The long-term target is **100% operational independence from external LLMs** for
the Genesis software-work loop.

"100% autonomous" means that a frozen campaign can run with **zero external model
calls**. It does **not** mean Genesis must solve 100% of arbitrary software bugs.
Success rate, cost and autonomy are separate measurements.

The target system must be able to:

1. inspect a previously unseen repository;
2. identify and use its native language toolchain;
3. diagnose a failing objective from observable evidence;
4. construct candidate transformations without an external LLM;
5. isolate, compile/test and rank those candidates;
6. retain successful strategies and useful failures;
7. reuse retained strategies on later repositories;
8. extend its own transformation repertoire under the existing trust root;
9. progressively reduce external-model dependence until it reaches zero.

## Architectural rule

Language support supplies **interfaces to reality, not answers**.

A Rust pack may expose Cargo, rustc, rustfmt, compiler diagnostics and tests. A
Java pack may expose Maven/Gradle, javac and tests. The packs must not contain a
catalogue of bug-specific fixes that merely moves human intelligence into host
code.

The first supported families are:

- Python
- Rust
- Java
- C#/.NET
- Go
- TypeScript/JavaScript

The initial toolchain implementation lives in
`genesis/language_toolchains.py`.

## Autonomy ladder

| Level | Requirement | Status |
| --- | --- | --- |
| A0 | Detect languages and available toolchains without an LLM. | **DEVELOPMENT PASS** |
| A1 | Execute bounded diagnosis/verification loops using native tools. | **DEVELOPMENT PASS** |
| A2 | Generate useful candidate mutations without an external LLM for at least one real bug family. | **DEVELOPMENT PASS** |
| A3 | Retain a successful strategy and causally reuse it on a fresh external task. | **DEVELOPMENT PASS** |
| A4 | Acquire new transformation strategies from failures/results rather than host-authored recipes. | **DEVELOPMENT PASS** |
| A5 | Transfer retained strategies across at least three language families. | **DEVELOPMENT PASS** |
| A6 | Frozen multi-repository campaign with an LLM fallback arm shows decreasing fallback demand. | **DEVELOPMENT FAIL — A6 and A6b failed; A6c apparatus in development** |
| A7 | Frozen multi-language campaign completes with **0 external model calls** while retaining useful repair performance. | **blocked pending A6c** |

A6b completed on 2026-10-06 as a preserved negative result: 3/12 autonomous successes, 75% fallback demand, and no within-A6b causal reuse. See docs/A6B_CAMPAIGN_2026-10-06.md. A6c is a new apparatus revision focused on self-extension of the transformation repertoire; it cannot retroactively alter A6b.

A7 is the operational "100% autonomous" target. It is intentionally independent
of L10: L10 measures external validation; this track measures who actually
generates the software solution.

## A0 — language/toolchain sensors

`genesis.language_toolchains` detects the six initial language families and
reports native compiler/test tooling without invoking repository code or an
external model. Language packs declare diagnostic and verification argv arrays;
they contain no issue-specific repair rules.

## A1 — bounded native diagnosis

`genesis.native_diagnosis` now executes a zero-LLM diagnosis pass with these
constraints:

- fixed argv probes from the detected language packs;
- no shell execution;
- a hard probe budget and timeout;
- no automatic retry;
- offline-oriented environment defaults;
- execution in a disposable repository copy, never the source tree;
- normalized diagnostic classes plus exact stdout/stderr hashes;
- explicit `external_model_calls: 0` in every report.

The first DEVELOPMENT validation uses a clean Python fixture and an independently
failing Python syntax fixture. The clean fixture is classified `clean`; the
broken fixture is observed as a nonzero native-tool failure and classified
`python_syntax_error`. Source-tree non-mutation, hard budget and no-retry
properties are separately tested.

This closes only the A1 **apparatus milestone**. It does not yet show that Genesis
can create a repair; A2 is deliberately separate.

## Measurement

Every external task must record at least:

- external model call count;
- external-model tokens/cost when non-zero;
- candidate count and charged executions;
- compiler/test/linter diagnostics consumed;
- whether the winning transformation was newly generated or retrieved;
- retained strategy/operator identities;
- causal ablation of the claimed retained acquisition;
- wall time and task success;
- comparison against the same base LLM working without Genesis when an LLM arm
  exists.

The critical curve is not merely task success. It is:

`external_model_calls_per_solved_task -> 0`

while held-out task performance stays useful.

## Scientific boundary

Until A7 is prospectively frozen and passed, Genesis must not be described as a
general autonomous software engineer. Language packs, compilers and tests are
tools; they do not by themselves supply programming intelligence.

The autonomy track inherits the existing Genesis rules: preserve negative
results, no silent retries, immutable frozen evidence, candidate isolation and a
trust root outside mutable lineage machinery.
