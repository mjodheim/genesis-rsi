# Genesis G5 qualification — 7 October 2026

**Verdict: `G5_SCIENTIFIC_GATE_PASSED` under the preregistered project-defined criterion.**

This result qualifies the Genesis v2 G5 autonomous-experiment-generation gate in one bounded internal-software setting. It does **not** establish G6, general RSI, AGI, ASI, independent third-party validation, or open-ended self-improvement.

## Prospective chronology

1. A six-case C# holdout was created outside the repository and sealed by SHA-256.
2. Genesis received only the holdout identity and case count.
3. A separate visible C# calibration failure was run against a Python-derived structural capability.
4. G3 attributed the failure to `operator` with confidence 0.9.
5. G4 retained two plausible mutable components: `structural_operator_engine` and `universal_operator_ir`.
6. G5 generated and froze a five-arm matched-budget experiment without seeing holdout contents.
7. The preregistration was committed as `cb33aef4` before holdout reveal.
8. The sealed holdout was revealed and evaluated under the frozen rule.
9. The positive result was frozen separately as `e0a7e07c`.

## Frozen identities

- preregistration commit: `cb33aef4`
- result commit: `e0a7e07c`
- holdout SHA-256: `a20d5a00add3c11d0240ea56f638a4fa898774f091f160c341dfb0d7d29dd228`
- preregistration digest: `a5a75135b18585d7dde693866ffa455f0ad8525d3c416d535ba93b3b5cc7f404`
- result digest: `5569175e477279c31f3cc4aec04dd515b4772a7299920ee395ac290b2dc696e0`
- evaluator identity: `external-dotnet-exitcode-evaluator-v1`
- external model calls during qualification: **0**

## Calibration

The retained source capability was learned from a validated Python transformation:

`subscript_index: 1 -> 0`

The calibration target was C#. The family-bound structural parent emitted **0 candidates**, while the target language had a real available .NET toolchain. G3 therefore attributed the observed miss to `operator`, not toolchain, representation or search.

G4 refused to invent precision and returned both operator components as plausible intervention targets.

## G5-generated plan

G5 prospectively generated:

- one unchanged parent control;
- two arms targeting `structural_operator_engine`;
- two arms targeting `universal_operator_ir`;
- identical per-arm budgets of 6 candidate executions, 120 seconds and 0 external model calls;
- a hidden holdout identity rather than holdout contents;
- an external-to-lineage verdict authority;
- a Pareto capability/resource objective.

## Hidden holdout result

| Arm | Component | Solved | External model calls |
| --- | --- | ---: | ---: |
| control-parent | unchanged parent | 0/6 | 0 |
| candidate-1 | structural_operator_engine | 0/6 | 0 |
| candidate-2 | structural_operator_engine | 0/6 | 0 |
| candidate-3 | universal_operator_ir | 5/6 | 0 |
| candidate-4 | universal_operator_ir | 5/6 | 0 |

The winning component was **`universal_operator_ir`**.

The five successes covered array, string, list, span and custom-indexer contexts. The remaining hidden case used `Values()[1]`, whose local structure falls outside the current identifier-anchored operator context. That failure is preserved rather than repaired retrospectively.

## Causal ablation

Removing the winning `universal_operator_ir` component while retaining the alternative structural operator machinery reduced the result from **5/6 to 0/6**.

This satisfies the preregistered causal-ablation requirement.

## Frozen qualification predicates

All preregistered predicates returned true:

- holdout SHA-256 matches the preregistered identity;
- best candidate beats the unchanged parent;
- winning component was named by the G5 plan before reveal;
- winning arm remains within the frozen execution/time budget;
- winning arm uses zero external model calls;
- at least 4/6 hidden cases are solved;
- ablating the winning component removes the gain.

Therefore the frozen verdict is:

> **`G5_SCIENTIFIC_GATE_PASSED`**

## What this result means

Genesis did not merely execute a human-selected benchmark configuration. Starting from an observed miss, its G3/G4/G5 machinery:

1. identified the limitation class;
2. identified plausible internal machinery rather than one arbitrary component;
3. generated a matched experiment intended to discriminate those components;
4. froze the experiment before access to fresh cases;
5. discovered that one internal mechanism produced a fresh capability gain;
6. survived causal ablation.

This meets the active roadmap's G5 exit criterion for **one bounded internal-software experiment**.

## What this result does not mean

- G6 is not passed: Genesis has not yet generated a materially new descendant implementation and demonstrated that descendant dominates its parent prospectively.
- G4's strongest independent/static-control criterion is not automatically closed by this result.
- The evaluator is external to mutable Genesis but this is not independent third-party governance.
- The holdout is finite and project-created.
- This is not evidence of general RSI, AGI, ASI or unrestricted self-modification.

## Evidence

- `experiment/g5_qualification/PREREGISTRATION.json`
- `experiment/g5_qualification/HOLDOUT_REVEALED.json`
- `experiment/g5_qualification/RESULT.json`
- `tests/test_g5_qualification_record.py`
- `scripts/build_g5_qualification_preregistration.py`
- `scripts/run_g5_qualification.py`