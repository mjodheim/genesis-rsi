# G11 — Program Understanding (pre-implementation protocol)

Status: DESIGN ONLY. No claim of autonomous repair or G11 validation.

## Scientific question
Does explicit Java program analysis increase the rate of fully validated repairs on unseen defects, at a fixed candidate/time budget?

## Arms
- A: existing Genesis machinery, frozen memory snapshot.
- B: A plus compiler-derived AST, resolved symbols/types, control-flow and local def-use information.
- C: B plus explicit causal hypotheses, predicted effects, and falsification tests.

## Trusted boundaries
- Keep holdout selection, test execution, score computation, and solution reveal outside mutable Genesis code.
- Never use human patches, hidden tests, or evaluation outcomes to generate hypotheses before blind freeze.
- Run all arms on identical Java/JDK/Defects4J versions, hardware quotas, candidate budgets, and time limits.
- Pin toolchain versions and hashes; record all inputs, outputs, provenance, and failures.
- Existing ER4 holdouts 23, 45, 53, 44 have already appeared in ER3 attempts. They must not be represented as clean unseen cases.
- Do not reuse ER3/ER4 memory snapshots for a clean holdout without verifying complete exposure provenance.

## Implementation gates
1. Build a read-only Java analysis adapter using a pinned Java parser/compiler. Emit typed AST references, symbol resolution, method call graph, and control-flow summaries in a versioned JSON schema.
2. Test on small hand-verified Java examples: shadowing, null branches, overloads, exception paths, and side effects. Measure analyzer precision and failures.
3. Add data-flow summaries and invariant/hypothesis generation; attach each hypothesis to source locations and falsifiable observations.
4. Integrate behind a feature flag. Analyzer failure must degrade to baseline without altering benchmark selection or revealing patches.
5. Run A/B/C on genuinely untouched cases; freeze all outputs before any solution reveal; compare full-suite valid repairs, plausible-only repairs, compute cost, and cross-project transfer.

## Decision criteria
No promotion solely for more operators, generations, plausible patches, or trigger-only successes. Promote only when a reproducible improvement on independent held-out cases is established, with confidence intervals and disclosed failures.

## Operational note
The autonomous ER3 systemd service was stopped after discovering holdout overlap. Do not restart it without an explicit exclusion guard and a fresh scientifically valid partition.
