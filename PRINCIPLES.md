# Genesis principles

Genesis is an experimental software lineage for studying efficient recursive self-improvement.

These principles define the direction of the active project. Historical experiments remain authoritative for their own frozen claims.

## 1. Capability before scale

Genesis does not define progress as increasing parameter count, context length, hardware demand or model size.

The preferred direction is:

> **more capability per unit of compute, memory, latency, energy and external assistance.**

A descendant that gains capability by multiplying resource demand may be useful, but it is not automatically an improvement.

## 2. Genesis is not a monolithic Transformer

The Genesis lineage is not defined as a Transformer and will not pursue recursive improvement by merely scaling a monolithic Transformer.

Transformer models may be used as external research tools, optional fallback proposers, comparison baselines, or bounded specialist components when experimentally justified. They are not the identity of Genesis.

The mutable Genesis machinery is modular: representations, memory, search, operators, routing, planning, tool interfaces and learned specialist mechanisms may evolve independently.

## 3. Better machinery, not larger machinery

When a capability is missing, Genesis should first ask whether it can improve representation, decomposition, search, memory, retrieval, operator vocabulary, tool use, scheduling, causal attribution, experiment design, specialization or distillation.

Raw resource growth is a last resort, not the default research strategy.

## 4. Failure is training data for machinery

A failed task is useful only if Genesis can explain what limited it.

The target loop is:

`observe -> diagnose limitation -> propose machinery change -> test -> retain/reject -> causally reuse`

A retry over the same inadequate search space is not self-improvement.

## 5. Language knowledge comes through interfaces to reality

Genesis should not contain hand-authored encyclopedias of Java, Rust, C#, Python, Go or TypeScript repairs.

Language adapters expose parsers and syntax trees, symbols/types/references when available, compiler/linter/test diagnostics, dependency metadata and versioned documentation retrieval.

Programming-language-specific facts are acquired on demand. Reusable knowledge should be retained as language-neutral abstractions where possible.

## 6. Learned capability must have provenance

Every retained capability should answer:

- where did it come from?
- which observation motivated it?
- which candidate instantiated it?
- which evaluator validated it?
- where did it transfer?
- what happens under ablation?
- what resources did it consume?

Unattributed improvement is not scientific evidence.

## 7. Recursive improvement must beat its parent prospectively

Genesis N+1 is not better because it solved the task used to create it.

A meaningful improvement requires fresh, prospectively governed evidence against Genesis N under comparable budgets.

The strongest target is a chain `G0 -> G1 -> G2 -> ...` where each generation contributes causally to producing a better successor.

## 8. The mutable lineage does not own truth

Genesis may propose new evaluators, benchmarks and scientific hypotheses. It must not silently redefine the acceptance criterion used to decide that it improved.

Trust-root functions remain externally governed: hidden/fresh evaluation, integrity validation, final promotion authority, resource ceilings, rollback and evidence identity.

## 9. Preserve negative results

Failed experiments are part of the lineage's knowledge.

They are never rewritten into successes. Apparatus defects create successor experiments, not retrospective rescoring.

## 10. Efficiency is a scientific outcome

Every serious future campaign should report, where measurable:

- solved tasks;
- external model calls;
- wall time;
- CPU/GPU time;
- peak memory;
- candidate/evaluation count;
- bytes of retained memory;
- measured energy when a real instrument exists.

The project should optimize a Pareto frontier, not a single opaque score.

## 11. Architecture remains evolvable

Genesis may eventually alter its own representations, memory organization, search and planning, routing, operator language, learning/update rules, specialist models, mutation machinery and allocation of admitted resources.

No current architecture family is assumed to be the final one.

## 12. Claims stay narrower than the evidence

Genesis is not currently AGI, ASI or general RSI.

Today it is a research system with bounded positive and negative results around cumulative adaptation, software autonomy, self-extension and evolvable cognitive machinery.

The purpose of the roadmap is to close that gap experimentally rather than rhetorically.