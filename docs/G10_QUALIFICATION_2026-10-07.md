# Genesis G10 qualification — 7 October 2026

**Verdict: `G10_SCIENTIFIC_GATE_PASSED` under the strengthened project-defined criterion.**

This result establishes a bounded recursive self-improvement chain in the
prospectively frozen synthetic software-repair composition assay. It does
**not** establish general RSI, AGI, ASI, open-world autonomy, or independent
third-party validation.

## Question

Can a qualified Genesis successor repeatedly produce better descendants, while
the machinery acquired by intermediate generations causally improves their
ability to produce the evidence needed for the next successor under matched
resource budgets?

The strengthened G10 criterion was intentionally stricter than “perform several
self-edits.” Transitions 2 and 3 had to show a **recursive-production
advantage**: the current generation had to outperform its direct ancestor on
the same next-successor discovery bank under the same candidate ceiling.

## Frozen chronology

The G10 apparatus, external bank generator, external evaluator, stage criteria
and final adjudicator were frozen first in commit:

- apparatus/protocol freeze: `c6a231b2`

No G10 qualification holdout existed at that point.

### Stage 1 — G0 -> G1

1. G0 was built from the already-qualified G9 successor.
2. Visible discovery evidence was collected with zero external-model calls.
3. G1 was generated and frozen before H1 existed:
   - successor freeze commit: `a136d784`
   - G0 profile: `613138e45bb05f4cae884bbb9e951e82bee1a19f858f7d6e9875af8fbce8f4b3`
   - G1 profile: `90c30ced7af6ad9b351dbfb5ccc875792f2807a5df1ccfc4ddbde05cce726cf9`
4. H1 was then generated outside the repository.
5. Only its SHA-256 was committed before reveal:
   - preregistration commit: `2aed97f8`
   - H1 SHA-256: `578a565e61a83f892f0880215cfcb740699396a37b96af2f7421c623f8a5b2a4`
6. The revealed result was preserved in `610038b7`.

Fresh score:

- G0: **2/6**
- G1: **6/6**
- retained single-site block: **2/2 -> 2/2**
- new paired-composition block: **0/4 -> 4/4**
- verdict: `G10_STAGE_1_PASSED`

## Stage 2 — G1 -> G2

Before G2 existed, G1 and its direct ancestor G0 were evaluated on the same D2
discovery bank under the same six-candidate-per-case ceiling.

Discovery-production comparison:

- G1: **4/4**, **4 candidate executions**
- G0: **0/4**, **16 candidate executions**

Only G1 therefore produced sufficient successful evidence for the next
successor. G2 was frozen before H2 existed:

- successor freeze commit: `9bf326f7`
- G2 profile: `3d9d3aa46effc2af1703efcdbeb380727eaa5a7a77f999c4c3879e8e648d5815`
- preregistration commit: `e40285c7`
- H2 SHA-256: `4186f259f173bc9695b46a18433529b95d9130c89855562ae717f0934e7dd8c3`
- result commit: `123386a6`

Fresh score:

- G1: **4/8**
- G2: **8/8**
- every G1 success preserved
- new scope-binding block: **0/4 -> 4/4**
- verdict: `G10_STAGE_2_PASSED`

This is the first recursive-production result in the chain: the machinery
acquired by G1 improved both discovery yield and candidate-execution cost for
producing G2 relative to G0.

## Stage 3 — G2 -> G3

The same causal comparison was repeated before G3 existed.

Discovery-production comparison:

- G2: **4/4**, **8 candidate executions**
- G1: **0/4**, **20 candidate executions**

Only G2 produced sufficient successful evidence for G3. G3 was frozen before
H3 existed:

- successor freeze commit: `03477d6f`
- G3 profile: `be03c081af05af4e1adb51dd4b8966283c96658875824d7eeaca3391d21ce2c8`
- preregistration commit: `cebf06dc`
- H3 SHA-256: `054c73a1729abd524ec9e2d7d55d661aab9d0a1300c207ab14bf86d2a0b6cbdd`
- result commit: `b062230a`

Fresh score:

- G2: **6/10**
- G3: **10/10**
- every G2 success preserved
- new multi-scope iteration block: **0/4 -> 4/4**
- verdict: `G10_STAGE_3_PASSED`

This is the second recursive-production result: the machinery acquired by G2
again improved both discovery yield and candidate-execution cost for producing
the next descendant relative to G1.

## Final chain adjudication

The final adjudicator was part of the apparatus frozen in `c6a231b2`. It was
not added or edited after seeing the stage outcomes.

The preserved final result is commit `c5b6fb44`, result digest:

`ccbc75ac2de8bbf821dc6912b32d2d08fbbf5f284d51775bcedbfd5a2f8d80f2`

The content-addressed chain is:

`613138e45bb0... -> 90c30ced7af6... -> 3d9d3aa46eff... -> be03c081af05...`

or, by campaign generation:

`G0 -> G1 -> G2 -> G3`

All final predicates returned true:

- all three prospectively frozen stage gates passed;
- the profile chain is digest-contiguous;
- campaign generations are exactly 0, 1, 2 and 3;
- every child strictly improves on fresh evidence;
- every child preserves every parent fresh success;
- transitions 2 and 3 show causal recursive-production advantage;
- that advantage improves both discovery yield and candidate-execution cost;
- generation/runtime external-model calls are zero;
- mutable lineage never owns evaluator or verdict authority.

Final verdict:

**`G10_SCIENTIFIC_GATE_PASSED`**

## What changed across the chain

The bounded assay deliberately exercised increasingly capable software-repair
machinery rather than scaling a larger statistical model.

- G0: retained single-site local repair machinery inherited from G9/G8.
- G1: evidence-driven paired retained-template composition.
- G2: evidence-driven scope-bound pair search.
- G3: evidence-driven iterated scope-pair composition.

Each generation retained the lower-level routes as fallbacks.

## Resource boundary

Every qualification arm used the same ceiling of **6 candidate executions per
case** and **0 external-model calls**.

The recursive-production comparisons were also matched-budget:

| Transition being produced | Improved generation | Direct ancestor |
| --- | ---: | ---: |
| G1 -> G2 discovery | 4/4 in 4 executions | G0: 0/4 in 16 |
| G2 -> G3 discovery | 4/4 in 8 executions | G1: 0/4 in 20 |

Thus the relevant inherited machinery did not merely improve task scores; it
improved the ability to obtain the evidence needed to construct the next
successor inside the frozen budget.

## Claim boundary

The strongest warranted statement is:

> Genesis has demonstrated a **bounded, project-defined recursive
> self-improvement chain in a software-repair composition assay**, including
> causal evidence that intermediate inherited machinery improves the ability to
> produce later successors.

This is the first active Genesis v2 gate at which the project supports the term
**domain-bounded RSI under the exact frozen assay**.

It is not evidence of unrestricted or general recursive self-improvement.
The task families and apparatus remain project-authored, the environment is
bounded, and no independent third party has yet reproduced the result. In
particular, the level-0→1→2→3 successor **mechanism families are host-authored
in the frozen apparatus**; Genesis selects/instantiates advancement from its
own measured discovery evidence, but it does not yet invent an unconstrained
new successor mechanism family. That stronger open-ended capability remains a
post-G10 research target.

The next scientific frontier is therefore not “G11 = claim AGI.” It is
**external reproduction, broader software-domain transfer, and eventually
generalization beyond software repair while preserving the same causal and
resource accounting discipline.**
