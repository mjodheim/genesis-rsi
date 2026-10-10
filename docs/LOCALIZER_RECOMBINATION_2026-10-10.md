# Localizers recombined without a model — 10 October 2026

General RSI remains the objective, not an achieved result. The failure attribution of the
same day names the fault localizer as the component that limits repair
(`FAILURE_ATTRIBUTION_2026-10-10.md`). This report covers the first change of that
component made without any model request: descendants built by Genesis from what its
earlier lineages left in the archive.

## What was built

The two sealed lineages hold 41 distinct localizer modules: the seed and 40 written by the
external model, most of them rejected. Each was run once, in the container, on the 687 development
cases, and its answers kept. A *composite* merges the answers of two members: the first
`lead` locations of one, then the locations of the other that add a new place (no kept
location of the same file within twenty lines), then what remains, six in all. Composites
are data and can nest.

Each generation pairs the champion with every other member, in either order and with every
lead from 1 to 5: 400 composites, scored by arithmetic on the 198 training cases. The best
one, if it beats the champion there, is scored on the 278 selection cases and replaces the
champion under the rule of the lineage (gained minus lost at least 5, one-sided sign test
at most 0.05). The run ends at the first generation without a promotion. The plan
(`experiment/localizer/RECOMBINE1/PLAN.json`, digest `f2ddd27d…`) was committed before the
composites were scored on selection or validation cases. No model was called.

## Result

| | training (198) | selection (278) | validation (211) |
|---|---|---|---|
| champion of LOCALIZER1 (`g3a3`) | 64 | 88 | 88 |
| generation 1: its first 3 locations, then the champion of LOCALIZER2 | 69 | 106 | 93 |
| generation 2: that composite's first 2, then the seed | 71 | 101 | not scored |

- Generation 1 is promoted: 29 selection cases gained, 11 lost, sign test 0.003.
- Generation 2 is rejected: 4 gained, 9 lost. Its training gain did not hold.
- On the validation cases, scored once: 13 gained, 8 lost, sign test 0.19. The gain is not
  established there.
- Over the 489 cases the choice never saw (selection and validation together): 42 gained,
  19 lost, sign test 0.002. This pooling was not in the plan.

The composite covers fewer whole files than its parent (137 against 140 on validation) and
more complete fixes: it trades breadth in one file list for the second lineage's places.

## What this shows and what it does not

A descendant of a component of Genesis was produced by Genesis from its own archive, with
no model request, and passed the gate that 12 model-written successors of the same
champion had failed. The winning partner is the champion of the other lineage: two chains
that had each stopped carry different knowledge, and merging them was worth more than
another rewrite. That is a use of earlier generations' products, not of a history shown to
a writer.

It is one step, not a chain: the second generation fails. The validation gain is within
noise. The merge rule was written by hand; Genesis chose the members and the lead, it did
not invent the operation. The modules merged were written by the external model. And no
repair trial was run: whether 5 more localized cases in 211 repair more defects is not
measured. The attribution estimate expects little from a change of that size.

## Limits

- The cases were prepared again for this run (the trees had been cleaned). The champion
  localizes 64 training cases here against 65 in its sealed lineage; directory order in the
  rebuilt trees is the suspected cause and was not verified. All comparisons here use the
  same stored answers.
- The validation cases had already been scored for two lineages. The composite was chosen
  without them, but this is their third use.
- 400 composites are compared on 198 training cases; generation 2 shows how such a choice
  overfits. Only the selection gate protects against it.
- Development cases only. No held-out case of the repair bench is involved; 103 remain.

Review: `docs/IP_REVIEWS/LOCALIZER_RECOMBINATION_REVIEW_2026-10-10.md`. Five focused tests
pass. Sealed files: `experiment/localizer/RECOMBINE1/`.
