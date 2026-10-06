# Genesis

> **Efficient recursive self-improvement research through causal learning, automated experimentation and evolvable software machinery.**

Genesis — formerly published as **Mira Genesis** — is an experimental software lineage created and directed by **Anthony Mets**.

Its central hypothesis is deliberately different from make-the-model-larger:

> **Capability should grow primarily by improving machinery, not by unbounded growth in machinery.**

Genesis studies whether a persistent system can observe its own limitations, improve representations/search/memory/operators/tools, validate descendants under controlled evidence, retain useful changes and use them to make later improvements easier.

## What Genesis is not

Genesis is **not** currently AGI, ASI or general RSI.

It is also not intended to become a monolithic Transformer whose main path to improvement is more parameters, more context and more compute. Transformer models can be used as external tools, baselines or bounded specialist components, but they are not the identity of the Genesis lineage.

The core research target is **better capability per unit of resource**.

See [PRINCIPLES.md](PRINCIPLES.md).

## Current scientific position

The repository contains several generations of bounded experiments. Important current anchors include:

- the project-defined finite operational **L9 gate passed** in OE1-v3: 16/16 frozen predicates, 576/576 coded transfer tasks and an independent replay of 33,215 retained candidate receipts with no mismatch;
- the public external-transfer L10 pilot has at least one successful external carrier, while strict independently governed L10 remains open;
- the A6/A6b autonomy campaigns preserved negative evidence showing that the dominant limitation is often **expressivity**, not simply more search;
- the A6c development line now contains a failure-driven self-extension prototype that diagnoses an expressivity gap, retains the diagnosis before seeing the solution, acquires a generic structural operator from validated evidence and later reuses it with zero model calls;
- the Genesis v2 G1-G5 foundation now composes a six-family language substrate, cross-language universal operator IR, evidence-backed failure attribution, a content-addressed self model and prospective matched-budget self-experiment design;
- the project-defined **G5 scientific gate passed on 7 October 2026**: a G5-generated preregistered experiment selected `universal_operator_ir` as the useful internal mechanism on a sealed six-case C# holdout (5/6 versus 0/6 parent, 0/6 after ablation, zero external model calls);
- the project-defined **G6 scientific gate passed on 7 October 2026**: Genesis generated three source-level descendants of its own universal operator matcher from prior G5 evidence, froze the selected descendant before a new eight-case holdout, and improved from 2/8 parent to 8/8 descendant while preserving all parent successes, using the same candidate budget and zero external model calls. Reverting the machinery change returned performance to 2/8.

These results do **not** establish general RSI. They establish bounded pieces of the machinery needed to test it. See [docs/G1_G5_FOUNDATION_2026-10-06.md](docs/G1_G5_FOUNDATION_2026-10-06.md), [docs/G5_QUALIFICATION_2026-10-07.md](docs/G5_QUALIFICATION_2026-10-07.md) and [docs/G6_QUALIFICATION_2026-10-07.md](docs/G6_QUALIFICATION_2026-10-07.md) for the exact boundaries.

Historical claims remain governed by their frozen experiment records.

## Historical integrity markers

The architecture reset does not erase or soften frozen historical outcomes. In particular, the **M086-A** attempt remains **POST-HOC DISQUALIFIED** and withdrawn exactly as recorded in its experiment evidence. Historical milestone labels remain valid identifiers even when they are no longer part of the active reader-facing roadmap.

## New architecture direction

Genesis is being reorganized around seven active surfaces:

```text
genesis/
  core/        lineage identity, self-model, cognitive architecture
  memory/      episodic, semantic, causal and capability memory
  languages/   parsers, AST/symbol/type/toolchain adapters
  operators/   universal, structural, semantic and learned operations
  learning/    failure analysis, acquisition, distillation
  evolution/   descendants, ablation, benchmarking, promotion
  runtime/     sandbox, scheduling, resources, execution
```

The existing flat `genesis/*.py` modules remain compatibility surfaces while migration occurs incrementally. Frozen experiments are not rewritten merely to make the tree prettier.

See [ARCHITECTURE.md](ARCHITECTURE.md).

## The improvement loop

```text
observe
  -> model the limitation
  -> identify the limiting machinery
  -> propose machinery changes
  -> create isolated descendants
  -> evaluate on fresh matched-budget evidence
  -> ablate
  -> retain or reject
  -> reuse the retained improvement
  -> repeat
```

The critical distinction is that **failure must be able to enlarge the future search machinery**.

A retry that explores the same inadequate space is not recursive self-improvement.

## Efficiency is part of correctness

Future serious campaigns should report not only task success but also external model calls, candidate/evaluation count, wall time, CPU/GPU time, peak memory, retained-memory size and measured energy when a real instrument exists.

Genesis should prefer Pareto improvements. A system that preserves capability while using one fifth of the resources may be a better descendant even if its benchmark score is unchanged.

## Roadmap

The active roadmap no longer uses the historical milestone sequence as its main reader-facing structure.

1. **G1 — Language substrate**
2. **G2 — Universal operator IR**
3. **G3 — Failure model**
4. **G4 — Self model**
5. **G5 — Autonomous experiment generation**
6. **G6 — Component evolution**
7. **G7 — Causal promotion and rollback**
8. **G8 — Distillation and local specialization**
9. **G9 — Successor generation**
10. **G10 — Recursive successor chain**

The strongest software-domain target is a prospectively verified chain such as `G0 -> G1 -> G2 -> G3`, where each generation improves on fresh evidence and inherited improvements causally help produce later improvements.

See [ROADMAP.md](ROADMAP.md).

## Repository map

| Path | Role |
| --- | --- |
| `genesis/` | active lineage/runtime implementation |
| `tests/` | regression, authority and research-apparatus tests |
| `experiment/` | newer RSI/autonomy experiment apparatus and results |
| `experiments/` | historical milestone experiment corpus |
| `results/` | retained result artifacts |
| `docs/` | research records, audits, designs and history |
| `archives/` | explicitly retired material |
| `metamorphosis/` | historical adaptive-embodiment implementation line |
| `mira_core/` | retained historical compatibility/research components |

The duplicate historical experiment roots are intentional **for now** because many frozen records and tests bind their paths. They will be consolidated only through compatibility-safe migrations.

## Quick start

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For focused current autonomy/self-extension work:

```bash
pytest -q tests/test_capability_gaps.py tests/test_structural_operators.py tests/test_failure_driven_self_extension.py
```

## Research integrity

Genesis follows hard rules:
- negative results are preserved;
- a failed frozen experiment is never silently repaired into a pass;
- evaluator identity and evidence provenance matter;
- candidate generation is separated from final acceptance;
- resource ceilings belong to the trust boundary;
- historical evidence is not rewritten to match the current narrative;
- claims remain narrower than the strongest reproducible evidence.

See [PROJECT_STATE.md](PROJECT_STATE.md) for the authoritative state snapshot and [docs/](docs/) for experiment-level evidence.

## License

The repository is licensed under the terms recorded in [LICENSE](LICENSE), [NOTICE](NOTICE) and the repository licensing policy.

## Historical reader-facing material

The pre-reset README and roadmap have been preserved verbatim in:

- `docs/history/README_PRE_GENESIS_V2_2026-10-06.md`
- `docs/history/ROADMAP_PRE_GENESIS_V2_2026-10-06.md`

The project is changing direction; its evidence is not being erased.
## Historical integrity anchors

Genesis is the renamed continuation of **Mira Genesis**; the rename does not alter authorship, licensing, provenance or any frozen experimental result.

**M086-A remains POST-HOC DISQUALIFIED.** Its former positive-looking development qualification was withdrawn and is neither silently restored nor reinterpreted by this architecture reset.

Historical evidence that carries the Mira Genesis name remains valid under that recorded project identity.