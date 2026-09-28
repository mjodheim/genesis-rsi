# Genesis Energy / Compute Frontier

Status: **prospective research track**. This document defines measurement and evaluation infrastructure. It does not make an energy-efficiency claim and it does not alter any frozen RSI result.

## Purpose

This track asks whether Genesis can improve the ratio between externally measured capability and externally measured resource use while preserving strict evaluator separation, provenance, matched budgets and rollback.

The track runs in parallel with the RSI L5→L10 program. It may share implementation infrastructure with RSI, but its experiments, success criteria, hidden cases and evidence are independent.

## Non-interference rule

1. Energy/compute measurements never rescore a frozen RSI result.
2. An RSI improvement is not automatically an energy improvement.
3. Information learned on either track may influence the other only through a new prospectively frozen experiment.
4. The mutable lineage cannot change the evaluator, measurement instrument, external resource ceilings, hidden cases, adoption rule or evidence ledger.
5. Negative and null results are preserved.

## Measurement principle

Do not infer energy from CPU time, wall time, node count, FLOPs, token count or hardware TDP.

`cpu_process_time_ns` is a compute proxy only.

A value for `energy_joules` is admissible only when accompanied by the identity and provenance of a real measurement instrument. Missing energy must remain missing.

Keep the following dimensions separate unless a prospective protocol explicitly defines a derived quantity:

- capability / task success;
- correctness / reliability;
- node or primitive executions;
- represented model/tool requests;
- CPU process time;
- wall-clock latency;
- peak memory;
- accelerator memory when measured;
- tokens / FLOPs when directly observed;
- measured joules;
- hardware identity and operating conditions.

## Frontier levels

### E0 — reproducible resource observation

Record capability together with reproducible non-energy resource measurements under an externally frozen evaluator and budget.

Minimum evidence:
- evaluator identity;
- case-set identity;
- architecture/program identity;
- hardware/runtime identity;
- external budget;
- per-case outcomes;
- node/request counts where applicable;
- CPU time and/or wall latency;
- memory where available;
- exact measurement provenance.

No energy claim is permitted at E0.

### E1 — real energy instrumentation

Add directly observed energy measurements from an identified instrument.

Requirements:
- instrument identity and measurement method;
- measurement interval boundaries;
- idle/baseline treatment frozen in advance;
- hardware/software configuration recorded;
- repeated-run variance characterized;
- energy missing rather than estimated when instrumentation fails.

### E2 — matched parent/descendant comparison

Compare parent and descendant only under a prospectively matched measurement design. The default E2 design requires equality of the exact physical device identity, hardware configuration, runtime and driver versions, power/performance settings, evaluator, cases, external resource budget, measurement instrument identity, measurement method, interval boundaries and idle/baseline treatment.

If exact physical-device identity cannot be held constant, E2 requires a prospectively frozen randomized or blocked design that explicitly controls device, instrument and operating-condition effects before any candidate outcome is observed. Merely matching a hardware class or measurement method is insufficient.

Report deltas without automatically collapsing them into a winner. No E3 capability/resource or capability/joule improvement may be attributed to a descendant from an E2 comparison that does not satisfy one of these frozen matching designs.

### E3 — reproducible capability/resource improvement

Demonstrate a reproducible improvement on a prospectively defined capability/resource frontier.

Examples may include:
- equal capability with lower measured joules;
- higher capability within the same energy budget;
- equal capability with lower compute and no material regression in reliability.

Any scalar utility must be frozen before candidate observation. Prefer Pareto-frontier reporting when trade-offs remain meaningful.

### E4 — cross-domain efficiency transfer

Show that the efficiency improvement transfers across materially different domains under fresh evaluation populations.

### E5 — endogenous bottleneck selection

Genesis selects which bounded resource bottleneck to improve next from measured evidence while an external controller retains evaluator, budget and adoption authority.

A matched fixed-target controller is required.

### E6 — real AI workload / accelerator validation

Validate the mechanism on realistic AI workloads and instrumented CPU/GPU/accelerator hardware.

The experiment must preserve exact model, quantization, batching, runtime, hardware, driver and measurement provenance.

### E7 — independent reproduction

An independent maintainer or laboratory reproduces the unchanged protocol on private or independently authored tasks and performs adversarial audit of measurement and claim boundaries.

## Relationship to RSI levels

The Energy/Compute frontier is orthogonal to the RSI L-scale.

Examples:
- L6 + E3 would support discussion of repeated self-improvement with measured resource gains.
- L7 + E4 would support a stronger cross-domain efficiency result.
- L8 + E5 would test whether the lineage can identify and improve its own resource bottleneck under external governance.
- L10 + E7 would provide the strongest current basis for an externally defensible claim.

These combinations are navigation targets, not results.

## Current foundation already present

`genesis/cognitive_measurement.py` already:
- binds architecture, evaluator, case-set and budget identity;
- records node executions and CPU process time;
- allows optional peak memory;
- accepts `energy_joules` only together with `energy_instrument`;
- performs matched parent/candidate comparisons;
- refuses to infer energy from compute proxies.

`genesis/cognitive_executor.py` already records primitive calls and CPU process time and explicitly leaves energy unavailable without instrumentation.

These are foundations for E0/E1, not evidence that E0 or E1 is complete.

## Immediate work

1. Define a canonical resource-measurement schema that can capture wall latency, memory, hardware/runtime identity and optional direct energy measurements without weakening the current measurement contract.
2. Add tests proving that missing or mismatched measurement provenance fails closed.
3. Add a small deterministic E0 benchmark with repeated runs to characterize variance before any optimization pressure is introduced.
4. Define the E1 instrument interface separately from the mutable lineage.
5. Do not optimize a proxy until its useful dynamic range and variance have been measured, following the lessons in `MEASURES.md`.
6. Keep all E-track results under a dedicated result namespace and preserve negative/null measurements.
