# Genesis G7 qualification — 7 October 2026

**Verdict: `G7_SCIENTIFIC_GATE_PASSED` under the preregistered project-defined criterion.**

This result qualifies the Genesis v2 G7 causal promotion/rollback gate in one bounded lineage-management setting. It does **not** establish G8, G9, a recursive successor chain, general RSI, AGI, ASI, or independent third-party validation.

## What G7 tests

G7 is not another repair benchmark. It tests whether a lineage can safely make a validated descendant active while keeping the verdict outside mutable Genesis.

The required properties are:

- candidate isolation before decision;
- external evaluator and authority identity;
- prospectively frozen promotion rule;
- automatic adoption of a better candidate;
- automatic rejection of a regression without active-state mutation;
- exact rollback to the recorded parent;
- restart/replay from persisted content-addressed state;
- tamper detection for artifact, decision, journal and state records.

## Prospective chronology

1. A 12-case Python holdout with three four-case rounds was created outside the repository and sealed by SHA-256.
2. The externally authorized lineage-promotion apparatus and evaluator were frozen in `b7aad58e`.
3. The G7 candidate lineage set was generated from already revealed G5/G6 evidence only and frozen in `07dc9646`.
4. The entire G7 rule, authority identities, sequence and 17 exit predicates were preregistered in `fd10fbb2` before holdout reveal.
5. The sealed holdout was revealed and the frozen external evaluator executed the sequence.
6. The positive result, revealed holdout and complete persisted lineage store were frozen in `fca80392`.

## Frozen identities

- apparatus commit: `b7aad58e`
- candidate-set commit: `07dc9646`
- preregistration commit: `fd10fbb2`
- result commit: `fca80392`
- holdout SHA-256: `83211370525d160de22cf2ddcfb84d4cf830197f2de50c6292a9b7a27e4713ae`
- candidate-set digest: `121380c3774c58c5f45cd1f4bd2a5d8a89e065f67b1e5edf914984c2d30a8531`
- preregistration digest: `7c52bd9a89f737933afacb7e2003e7057f456e17d08b4a696bfc1fa07ab083a4`
- result digest: `5937c6797e2f49e76bb3b76431f1d08c3c4f3719883d8b395e536fa85b157730`
- final state digest: `a6bb972b1b88e48d7ae864f977296594727bd444ec64dd9a969e8ac7de7cd6a6`
- final journal head: `e6122be397cb70a6b2dfdb25fb908eb4792ab523e6b460051052531eb45e223a`
- external model calls: **0**

## Frozen authority rule

The external authority may adopt a candidate only when all of the following hold on the matched fresh round:

- candidate passes strictly more cases than the active parent;
- every parent success is preserved;
- parent and candidate use the same candidate budget;
- both remain within that budget;
- both use zero external model calls.

Ties and regressions are rejected. Mutable lineage code does not own the evaluator, rule or verdict.

## Candidate lineage

The qualification froze four source artifacts:

- `seed`: exact pre-G6 parent `universal_operator_ir` source;
- `D1`: the G6 winning descendant `structural_delimiter_anchors`;
- `R1`: an exact-source reversion candidate whose lineage parent is D1;
- `D2`: an independently generated alternate descendant, `drop_wildcard_identifier_anchors`.

Candidates live in an immutable content-addressed artifact store. Staging a candidate never changes the active digest.

## Qualification sequence

### Round A — promotion

Fresh Python cases:

- active seed: **1/4**;
- candidate D1: **4/4**.

The frozen authority returned **adopt**. D1 became the active artifact. The persisted store was then reloaded and replayed successfully.

### Round B — rejection

With D1 active, R1 proposed an exact source regression toward the old parent:

- active D1: **4/4**;
- candidate R1: **1/4**.

The same frozen authority returned **reject**. The active lineage state digest remained exactly unchanged. The rejected candidate remains first-class history in the hash-chained journal.

### Exact rollback

An external rollback challenge bound to the Round-A adoption restored the exact recorded seed artifact. The source identity and artifact digest matched the original parent exactly. Restart/replay reproduced the rollback state.

### Round C — promotion after rollback

After rollback, D2 competed against the restored seed on a third fresh round:

- seed: **2/4**;
- candidate D2: **4/4**.

The frozen authority returned **adopt**. D2 became the active artifact and the persisted lineage replayed successfully after restart.

## Persisted lineage result

Final lineage generation: **3**.

Journal sequence:

1. seed;
2. candidate proposed D1;
3. candidate accepted D1;
4. candidate proposed R1;
5. candidate rejected R1;
6. rollback D1 -> seed;
7. candidate proposed D2;
8. candidate accepted D2.

The active final artifact is D2.

## Tamper probes

Four independent copies of the persisted lineage store were intentionally corrupted after qualification:

- active artifact source modified;
- external decision case-set identity modified;
- journal seed payload modified;
- persisted generation modified.

All four corrupted stores were refused on reload.

## Frozen qualification predicates

All **17/17** preregistered predicates returned true, including:

- holdout identity match;
- all raw tasks fail before repair machinery acts;
- candidate isolation before every decision;
- A adopted by frozen rule;
- B rejected by frozen rule;
- rejection leaves active state unchanged;
- exact external rollback;
- restart/replay after each transition;
- C adopted after rollback;
- final active artifact is D2;
- expected monotonic lineage generation;
- four tamper classes rejected;
- zero external model calls;
- every decision binds the frozen authority, rule and evaluator.

Therefore the frozen verdict is:

> **`G7_SCIENTIFIC_GATE_PASSED`**

## What this establishes

In this bounded setting, Genesis now has a safe lineage-control mechanism around its self-generated machinery:

`generate candidate -> isolate -> externally evaluate -> adopt/reject -> persist -> replay -> rollback exactly -> continue`

The mutable lineage can propose and hold machinery, but cannot make itself win by changing the evaluator, rule or verdict.

## What this does not establish

- G8 is not passed: expensive reasoning has not yet been prospectively distilled into a cheaper retained local specialist under a fresh qualification.
- G9 is not passed: this does not yet prove Genesis N as a whole produced and promoted a globally better Genesis N+1 under the G9 minimum criterion.
- G10 is not passed: there is not yet a repeated recursive successor chain.
- Evidence is project-created rather than independently governed by a third party.
- This is not general RSI, AGI or ASI.

## Evidence

- `experiment/g7_qualification/CANDIDATES.json`
- `experiment/g7_qualification/PREREGISTRATION.json`
- `experiment/g7_qualification/HOLDOUT_REVEALED.json`
- `experiment/g7_qualification/RESULT.json`
- `experiment/g7_qualification/LINEAGE_STORE/`
- `genesis/evolution/lineage_promotion.py`
- `scripts/build_g7_candidates.py`
- `scripts/build_g7_qualification_preregistration.py`
- `scripts/run_g7_qualification.py`
- `tests/test_lineage_promotion.py`
- `tests/test_g7_qualification_record.py`