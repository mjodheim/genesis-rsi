# Representation-discovery pilot — unpublished development experiment

17 October 2026. This is exploratory engineering, not independent evidence, general RSI, a new language, or a new scientific gate.

## Research question

Can a bounded system improve a numerical representation it uses, instead of merely selecting more programs within an unchanged representation?

The system starts with Boolean truth tables. A candidate representation is an invertible composition of GF(2) butterfly passes along input axes. The genome is an integer bitmask that selects passes; the learner is not told a preferred mask, but the entire primitive operation family is human-specified. It mutates and selects representation programs; it does not invent its own transformation grammar.

## Protocol, limits, and guards

- Training: only original CIRCUIT1 LEARN families (and, or, parity, equal, mux, adder, majority).
- Development evaluation: original CIRCUIT1 HELD_OUT families (less, subtract, popcount, exactly, multiply). These are accessible in the code and therefore NOT a newly hidden or blinded holdout.
- Fixed seed, counted candidate evaluations, and identity and equal-budget random-search controls.
- Objective: ACTUAL round-trippable packed-or-sparse binary encoding bits including tags and a one-time changed-representation descriptor; NOT latency or energy. Transform work counted separately.
- Exact reconstruction of every task target required; no candidate may modify the evaluator.
- Selection is training-only; evaluation is calculated AFTER selecting the representation.
- Output is a deterministic development trace with digests and lineage.
- Historical CIRCUIT results, immutable judges and commit citations are untouched.

Run from repository root with development dependencies:

    python -m experiment.representation_discovery.prototype > /tmp/genesis-representation-dev.json
    pytest -q tests/test_representation_discovery.py

## Before public release or experimental claim

1. Record project-owner IP/publication disposition: unpublished local worktree until review.
2. Freeze the candidate grammar, cost accounting, matched compute budget and independent evaluator before fresh tasks.
3. Use genuinely novel tasks excluded from both model training and representation designers' prior inspection; audit task equivalence and structural leakage.
4. Compare fixed representation, evolved representation, matched-budget random, full Mobius transform, and larger-compute baselines.
5. Require causal ablation plus a second generation that improves future representation discovery (not only compresses examples).
6. Promotion and research verdict must remain under a trusted independent evaluator.

## First development run (17 October 2026)

All checks in this worktree: 35 focused tests passed, structural repository hygiene passed, orphan-module scan passed. The selected six-input transformation is mask 63 (the full GF(2) Mobius transform), with 42 distinct transformation candidates examined. On the *already available* CIRCUIT1 development-evaluation tasks at arity six, the actual reversible encoded lengths summed to 652 bits versus 889 bits using the original representation; an equal-candidate-count random control obtained 721 bits, and the explicitly coded full-Mobius control also obtained 652 bits. Smaller arities retained the original representation.

This outcome is not invention of a wholly new transform, not a blind generalization result, not a latency speedup, and not improved ability to evolve the next generation. The full-Mobius comparator matching the selected program underscores that this finite grammar mainly recovers a known transform. An honest next study should expand or endogenize the primitive grammar *before* a genuinely unseen task bank is frozen.

Human publication/IP review is pending. The commit is intentionally **local-only**, not pushed to GitHub or promoted to main.
