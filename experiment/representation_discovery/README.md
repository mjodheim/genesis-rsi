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

## Next development iteration: unrestricted sequences of provided reversible primitives

Two additional prototype modules and their tests study whether a broader
search grammar escapes the plateau in the first finite-mask experiment:

- adaptive_basis.py: a multi-generation greedy/beam search over axis passes
  and arbitrary invertible truth-table coordinate XOR shears. It is vulnerable
  to a documented valley: all one-axis transformations worsen the training
  encoding score for six-input tasks, while the complete six-axis transform
  improves it. The bounded greedy/beam search retained identity and learned
  no change for these development tasks. This negative observation is
  preserved in ADAPTIVE_BASIS_DEV_2026-10-17.json.
- macro_search.py: explicit bounded enumeration of all 2^n axis
  combinations, then train-guided or random shear proposals. The larger
  search finds the full transform at arity six. In three reproducible seeds,
  the guided and random searches select identical output programs. Guided
  prescreening expends extra training-only probes without improving the
  result. See MACRO_SEARCH_DEV_2026-10-17.json.

At arity six on the historically exposed CIRCUIT1 evaluation set:

| Representation | Data bits | Data + representation descriptor bits |
| --- | ---: | ---: |
| Original identity | 889 | 889 |
| Full GF(2) Mobius (known baseline) | 652 | 690 |
| Guided macro-search | 652 | 690 |
| Random macro-search | 652 | 690 |

This improves a toy serialization metric compared to identity but not
relative to the known full-Mobius baseline. On the previously available
four-input development evaluation set the known Mobius transform uses
fewer data-only bits (208 versus 224), yet costs 236 including its
description; the train-selected identity stays at 224. The independent
negative-control random truth tables likewise do not gain here.

Claim boundary: The search does not invent its own primitive operation
family. It does not beat the best known baseline, and it has no demonstrated
recursive improvement of the improvement procedure. Its evaluation families
were available in the source before the experiment. The equal number of
scored proposals is not an equal-CPU comparison because the guided arm
performs extra prescreening. No sealed experiment, external reproduction,
performance/energy saving, or RSI claim is made.

Next useful design change: optimize future discovery rate and transfer
across unseen task structures, not this handcrafted encoding proxy. A serious
prospective experiment must be separately frozen and judged externally
before viewing any new qualification results. This branch remains
local-only until an owner IP-publication disposition is recorded.
