# CIRCUIT2 multi-seed independence: development audit, 17 October 2026

**Status:** Non-qualifying, DEVELOPMENT-ONLY audit of the local proposed fix for
PR #428. No frozen plan, blinded task bank, historic result, or scientific
acceptance criterion was changed.

Run from repository root:

    python tools/audit_circuit2_seed_diversity.py
    python tools/audit_circuit2_seed_diversity.py --require-npn-isolation
    python -m pytest -q tests/test_circuit2_seed_diversity_audit.py

The second command MUST exit 2 against this candidate corpus: the
currently generated HELD_OUT is not structurally isolated from LEARN.

## Verified measurements

Analysis is bounded to input arities **2 and 3**, which are the input
sizes used for the planned CIRCUIT2 preparation (MAX_INPUTS=3).
Twenty deterministic seeds were analyzed (0–19) after the fix preserving
the prior seed-zero corpus and varying seeds 1–19.

| Quantity | LEARN | HELD_OUT |
| --- | ---: | ---: |
| Task slots across 20 seeds | 200 | 60 |
| Unique (inputs, truth table) pairs | 37 | 21 |
| Reused task slots | 163 | 39 |
| NPN equivalence classes | 5 | 2 |
| Largest repetition of one table across seeds | 20 | 6 |
| Distinct whole-suite digests | 20 | 20 |

Each HELD_OUT seed exposes only three instances under this arity bound.
A total of **one NPN class occurs in both LEARN and HELD_OUT** across the
twenty seeds; a within-seed exact-table collision is *not* present.
NPN canonicalization is exhaustive for up to three inputs, not an
estimated semantic similarity metric.

Consequently, the twenty different suite fingerprints do NOT provide
twenty structurally independent qualification tasks. Simple repeated-seed
wins, or a binomial sign test interpreting those observations as independent
classes, would overstate what the experiment establishes. Repeated seeds
can still test stability conditional on this shared task family, provided
the claims are appropriately bounded.

## Guardrails for the next prospective protocol

1. Preserve all historical CIRCUIT1/CIRCUIT2 records, including the
   registered seed-zero digest. Do NOT modify an already-frozen criterion
   in response to these findings.
2. Create a separately versioned prospective experiment. Freeze the
   task-construction grammar, train/evaluation class split, budget and
   success criterion before generating new qualification samples.
3. Select independent NPN-equivalence classes, ideally problem-family
   structures rather than merely transformed instances, for evaluation.
   Have an independent trusted evaluator enforce class membership and
   maintain the appropriate blinded bank; do not inspect those future
   evaluation instances while editing the generator.
4. Report unique truth tables, unique structural classes, class overlap,
   repeated exact tables and dependence among samples.
5. Keep fixed-search, known-mathematical transform, matched-compute and
   random-selection baselines. Neither this audit nor the seed fix can
   establish general RSI or transfer to unseen problem classes.

No attempt is made to manufacture or inspect a new hidden held-out bank.
