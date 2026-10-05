# L9 diagnosis: broadening tasks breaks the closed codec guarantee

Analysis prepared on 5 October 2026 under Anthony Mets's delegated research
direction, with substantial Codex assistance. This is an argument about a stated
oracle model, not a new empirical assay, a general RSI impossibility theorem or a
qualification result. V49/V50 frozen sources, protocols and evidence remain
unchanged.

## A concrete task family outside the continuation premise

V50 proves that distinct codec words have distinct outputs at the declared base
input. At word length n there are therefore 4^n distinct target behaviors in its
idealized format model. Now draw the next target uniformly from U of those words
that have never previously been observed, independently of the actor's complete
archive, learned policy, public task descriptor and random seed. The actor knows
the length and codecs; the target word and expected output remain outside it.

Every paid query receives only exact whole-output acceptance. A proposed output
can match at most one word, because V50's words are behaviorally injective at the
base. A rejection rules out that one word and reveals no partial distance or
operator location. Repeated queries, failed programs, verification, root screens
and controller calls cannot be free.

## Adaptive archive search is still bounded by q/U

Condition on the complete past archive and the actor's random seed. Before the
first acceptance, all answers are rejection. The actor consequently has one
well-defined all-rejection path containing at most q distinct proposed outputs.
If it succeeds within q queries, the target must be one of the at most q words
matched along that path. A uniform target in the U-word population therefore has
success probability at most min(1, q/U). Averaging over actor seeds preserves
this bound. Early stopping, adaptive proposal ordering, larger remembered
archives and executable policy descendants do not remove it under these premises.

The experiment's mandatory paid confirmation makes this upper bound generous.
It counts any exact discovery in at most q calls, rather than promising a spare
confirmation call after discovery on call q. An instrument failure only reduces
the attainable coverage and remains charged.

For the existing 26-call cap and no excluded words:

| Target word length | Distinct behaviors | Maximum success probability |
| ---: | ---: | ---: |
| 4 | 256 | 10.15625% |
| 8 | 65,536 | 0.0396728515625% |
| 16 | 4,294,967,296 | approximately 0.0000006053596735% |
| 32 | 18,446,744,073,709,551,616 | approximately 0.0000000000000001409463% |

If the unseen target population U grows without bound while q stays fixed,
expected new discoveries per task tend to zero. Since every task costs at least
one paid query, the ratio of expected new discoveries to expected paid queries
also tends to zero. This is an expectation bound for this task distribution,
not an assertion that every finite trajectory contains a particular zero window.

## Why this does not refute V50's induction

V50's continuation premise restricts the next target to sixteen pairwise products
of four retained parent tools. Complete enumeration can cover that entire
population within its fixed cap. The model's unbounded word lengths do not make
its conditional next-task uncertainty grow beyond those sixteen choices.

Replacing that closed curriculum with arbitrary unseen words invalidates the
sixteen-product completeness premise. Longer words alone and additional random
seeds do not supply the missing information. Conversely, a learned task
distribution, reusable algorithms, useful partial feedback or a prospectively
different work budget can invalidate the independence/exact-oracle premises of
this diagnosis. Such alternatives need their own externally frozen evaluator,
causal controls and accounting; the actor cannot grant itself richer feedback.

## Consequence for the next research line

The useful successor question is whether lineage-selected construction or
representation machinery captures reusable task structure across diverse native
problems, compared with the same paid predecessor and mechanism ablation. A
host-generated next target explicitly built from the last four winning tools
cannot independently establish that broader capability.

Selection must use public development evidence and precede its fresh population.
Preserve negative descendants, branch/recovery histories, all diagnostic and
adoption costs, exact novelty definitions, and both query and native-work rates.
This diagnosis spends no fresh attempt and authorizes no changes to previous
thresholds. General L9 and independent L10 remain open.
