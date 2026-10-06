# Genesis G1-G5 foundation — 6 October 2026

**Status: DEVELOPMENT FOUNDATION IMPLEMENTED.**

This record documents working apparatus. It does **not** claim that the scientific exit criterion of every G1-G5 roadmap stage has been met, and it makes no general RSI claim.

## Composition

The first Genesis v2 implementation wave now composes:

`G1 language substrate -> G2 universal operators -> G3 failure model -> G4 self model -> G5 experiment design`

All five layers operate without requiring Genesis itself to become a larger Transformer.

## G1 — language substrate

Implemented in `genesis/languages/substrate.py`.

Current capabilities:
- one canonical document schema across Python, Java, C#, Rust, Go and TypeScript/JavaScript;
- stable tokens with source spans;
- structural nodes for declarations, calls, control flow, operators and subscripts;
- CPython AST-backed structure and symbols for Python;
- conservative lexical/structural parsing for the other initial families;
- explicit parser-backend and structural-fidelity fields;
- dependency/version facts for later documentation retrieval from PyPI, npm, Cargo, Go modules, NuGet and Maven;
- integration with the existing native toolchain registry;
- zero external model calls.

**Boundary:** compiler-grade AST, symbol resolution and type information are not yet implemented for all six families. G1 has a common working substrate, while the strongest semantic-adapter target remains open.

## G2 — universal operator IR

Implemented in `genesis/operators/universal.py`.

The first universal family learns a validated one-token structural replacement from a passing before/after pair and retains semantic role, token transition, language-neutral anchors, exact source-result provenance and content-addressed identity.

Current development transfer learns `subscript_index: 1 -> 0` from Python and materializes it into Java, TypeScript and C#. Source identifiers differ, so this is not literal patch replay. External model calls: 0.

**Boundary:** this is a synthetic development transfer, not yet the prospectively frozen external causal campaign required for strong G2 exit evidence.

## G3 — failure model

Implemented in `genesis/learning/failure_model.py` and integrated into `genesis/learning/capability_gaps.py`.

Current classes: knowledge, representation, operator, search, retrieval, toolchain, planner, evaluation, unknown and underdetermined.

Important rules:
- invalid/ambiguous evaluator is a hard blocker;
- applicable retained capability that fails to reach emission is retrieval/planner, not automatically missing operator;
- unsupported/unparsable target code points toward representation;
- exhausted representable candidate space before budget points toward operator expressivity;
- budget exhaustion with remaining candidates points toward search;
- ambiguous evidence may remain underdetermined.

No hidden solution is inspected.

**Boundary:** attribution accuracy still needs a prospective labelled failure campaign and evidence that using G3 improves intervention choice over static controls.

## G4 — self model

Implemented in `genesis/core/self_model.py`.

Genesis can build a content-addressed map of active machinery including component identity, source SHA-256, role, inputs/outputs, resource axes, associated failure classes and mutable-lineage versus trust-root status.

Initial mapped components include language substrate, language toolchains, universal operator IR, structural operator engine, strategy memory, candidate scheduler, failure model and trust root.

G4 preserves ambiguity. For example, an operator failure can point to both structural and universal operator machinery rather than choosing arbitrarily.

The trust root is represented as immutable. Evaluation failure never grants mutable Genesis permission to modify it.

**Boundary:** prospective comparison against static/random component controls is still required for strong G4 exit evidence.

## G5 — autonomous experiment design

Implemented in `genesis/evolution/experiment_design.py`.

Given G3 + G4 evidence, Genesis generates a content-addressed prospective experiment containing a causal hypothesis, unchanged parent control, candidate intervention arms, equal budgets, target components, evaluator identity, fresh case-set identity, hidden-case boundary, efficiency metrics and external promotion authority.

When several components are plausible, G5 creates discriminating arms instead of silently choosing one.

G5 refuses self-modification experiments when attribution is unknown/underdetermined, the failure is in the evaluator/trust boundary, no mutable component matches, or no intervention exists.

**Boundary:** G5 can now design an experiment. It has not yet independently discovered and validated a useful internal improvement through one of those generated experiments.

## End-to-end development demo

Runner: `python scripts/run_g1_g5_foundation_demo.py --repository-root .`

Tracked result: `experiment/g1_g5_foundation/DEVELOPMENT_RESULT.json`

Current result:
- external model calls: 0;
- G2 transfer targets: Java, TypeScript, C#;
- G3 primary class: operator;
- G4 candidates: structural_operator_engine and universal_operator_ir;
- G4 selected component: none because evidence is insufficient;
- G5 arm count: 5;
- hidden case contents visible to mutable lineage: false;
- mutable lineage owns verdict: false.

The demo is a composition/regression artifact, not a frozen scientific qualification.

## Immediate next scientific work

1. Strengthen G1 with compiler-grade semantic adapters.
2. Freeze a real G2 external cross-language campaign with literal-patch controls.
3. Build a labelled prospective G3 failure-attribution set.
4. Compare G4 intervention targeting against static/random controls.
5. Use G5 to preregister the first experiment in which Genesis attempts to improve one of its own mutable components.
6. Move a scientific gate only after fresh matched-budget evidence.