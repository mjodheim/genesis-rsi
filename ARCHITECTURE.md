# Genesis architecture

**Status:** active architecture direction, 6 October 2026.

Genesis is being reorganized around one question:

> Can a persistent software lineage improve the machinery that produces its capabilities while keeping the improvement causal, replayable, resource-aware and externally verifiable?

The active architecture is intentionally modular and non-Transformer-centric.

## Logical architecture

```text
                         +-----------------------+
                         |  External trust root  |
                         | eval / limits / gate  |
                         +-----------+-----------+
                                     |
                                     v
+-------------+     +----------------+----------------+     +-------------+
| Environment | --> |          Genesis runtime        | --> |  Evidence   |
| repo / task |     |                                 |     |  journal    |
+-------------+     +----------------+----------------+     +-------------+
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
        v                            v                            v
+-------+-------+            +-------+-------+            +-------+-------+
| Language      |            | Self / failure |            | Memory        |
| substrate     |            | model          |            | systems       |
| AST/types/etc |            | attribution    |            | causal/etc    |
+-------+-------+            +-------+-------+            +-------+-------+
        |                            |                            |
        +-------------+--------------+--------------+-------------+
                      |                             |
                      v                             v
              +-------+-------+             +-------+-------+
              | Operator IR   |             | Search / plan |
              | learned ops   |             | experiment    |
              +-------+-------+             +-------+-------+
                      |                             |
                      +-------------+---------------+
                                    |
                                    v
                           +--------+--------+
                           | Evolution loop |
                           | descendants    |
                           +--------+--------+
                                    |
                                    v
                           sandboxed candidates
```

## Active package map

The public architecture is organized under:

- `genesis/core/` — lineage identity, self-model boundary and cognitive architecture;
- `genesis/memory/` — episodic, semantic, causal and capability memory;
- `genesis/languages/` — language substrate and adapters;
- `genesis/operators/` — universal, structural, semantic and learned operations;
- `genesis/learning/` — failure analysis, capability acquisition and distillation;
- `genesis/evolution/` — candidate generation, ablation, benchmarking and promotion;
- `genesis/runtime/` — sandboxing, scheduling, resources and execution.

The repository still contains historical flat modules in `genesis/`. They remain compatibility surfaces while the active code is migrated incrementally. Their presence is not the desired final architecture.

## 1. Language substrate

A language adapter does not contain a repair cookbook. It exposes facts.

Target flow:

```text
source
  -> parse
  -> structural IR
  -> symbols/types/references
  -> toolchain diagnostics
  -> transformation
  -> compile/test
  -> normalized evidence
```

Initial families: Python, Java, C#, Rust, Go and TypeScript/JavaScript.

The long-term goal is transfer through a language-neutral intermediate representation rather than independent bug engines per language.

## 2. Universal operator IR

Genesis should learn concepts such as replace-expression, insert-guard, alter-branch-predicate, alter-iteration-bound, change-call-arguments, coordinated-reference-update and structured-configuration-edit.

The operator identity should describe semantics and constraints rather than a literal patch. A language adapter materializes that operation into local syntax.

## 3. Failure model

The current A6c work begins this layer.

A failed search should produce an attributable limitation such as missing knowledge, insufficient representation, missing transformation primitive, search-budget exhaustion, retrieval failure, evaluator ambiguity, toolchain deficiency or planner/scheduler misallocation.

The failure model is the bridge from task solving to machinery improvement.

## 4. Self model

Genesis needs a causal map of its own active machinery:

`task -> perception -> representation -> retrieval -> planning -> operator generation -> execution -> evaluation -> retention`

For each stage Genesis should be able to record evidence, transformations, budget, known failure modes and possible intervention points.

The self model is operational metadata, not personality or consciousness.

## 5. Memory

Memory is split by role rather than accumulated as one undifferentiated store:

- episodic: what happened in a run;
- semantic: general facts learned from repeated evidence;
- causal: which intervention changed which outcome;
- capability: which operator/tool/strategy exists, with provenance and validity domain.

Retention should be selective. Genesis should be able to forget redundant detail while preserving sufficient evidence to reproduce a capability.

## 6. Experiment generator

A mature Genesis should generate experiments about its own limitations.

Example: observe coordinated multi-file failures; hypothesize that retrieval loses dependency edges; compare symbol-aware retrieval, graph retrieval and a larger text window on a hidden matched-budget set; retain only improvements to the capability/resource frontier.

This is automated R&D rather than repeated task repair.

## 7. Evolution and promotion

Mutable Genesis can produce candidate descendants. It does not promote itself.

```text
parent
 -> candidate descendants
 -> isolated execution
 -> matched-budget evaluation
 -> causal ablation
 -> external/trust-root decision
 -> adoption or rejection
 -> persistent evidence
```

## 8. Efficiency model

Genesis evaluates descendants on a Pareto frontier: capability, reliability, transfer, external-model dependence, latency, compute, memory, candidate evaluations and energy when actually measured.

A descendant can therefore be better even without a higher raw success rate if it preserves capability while substantially reducing cost.

## 9. Specialist learning and distillation

Before attempting frontier-model training, Genesis should replace repeated expensive reasoning with cheaper validated mechanisms: compiled operators, retrieval indexes, decision tables, small classifiers, small specialist models, cached proofs and deterministic programs.

The intended loop is `expensive discovery -> validated pattern -> cheaper reusable mechanism`.

## 10. Successor loop

The long-term software-RSI criterion is repeated, prospective descent:

```text
G0 -> discovers I1 -> G1
G1 -> uses inherited I1 -> discovers I2 -> G2
G2 -> discovers I3 -> G3
```

For each transition the project must show that the child differs materially, the parent causally contributed, the child improves on fresh evidence, the gain survives restore, ablation weakens the gain, resource cost is recorded, and later generations build on prior machinery.

A repeated chain meeting these conditions is the point at which the project can seriously discuss domain-bounded recursive self-improvement.