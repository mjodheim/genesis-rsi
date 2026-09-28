# Energy / Compute Frontier experiments

This directory contains prospective experiments for the Energy/Compute Frontier defined in `docs/ENERGY_COMPUTE_FRONTIER.md`.

## Rules

- Energy experiments are independent from frozen RSI experiments.
- No E-track result may retroactively change an RSI verdict.
- CPU time, latency, request count, node count, FLOPs or TDP are not energy measurements.
- Joules require a real identified measurement instrument.
- Evaluator, case set, hardware/runtime context, budget and measurement method are frozen before comparing candidates.
- Negative, null and instrument-failure results are preserved.
- Mutable Genesis may propose candidates but may not rewrite the evaluator, instrument, budget, adoption rule or evidence ledger.

## First target

The first target is E0: establish reproducible capability/resource observation and characterize measurement variance before any resource-aware selection pressure is introduced.
