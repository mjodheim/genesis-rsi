# Which component limits the system — 10 October 2026

General RSI remains the objective, not an achieved result. Issue G12 asks that Genesis
diagnose its own failures and name the part of its machinery that limits it, before
changing that part. This report covers the diagnosis only: an instrument that reads sealed
trial records without any model.

## What was built

`genesis/failure_attribution.py` takes one record per case, an ordered list of conditions
each owned by a component, and the outcome. For each condition, among the cases where the
earlier conditions hold, it reports how often success follows with and without it. The
difference, multiplied by the cases without it, estimates what the component would gain by
always meeting the condition. The component with the largest estimate is named.

A domain supplies only its conditions. Two are provided: the repair bench (the evidence
covers the place of the fix; a candidate reaches validation; one compiles; one passes the
failing tests) and chained program improvement (a rewrite could be run; it behaves like the
original; it is cheaper). The conditions are written by hand. The instrument chooses among
them; it does not discover them.

## What it says on sealed records

Source: `experiment/localizer/LOCALIZER1/DEV_LOCALIZED_REPAIR1_RESULT.json`, 40 development
cases, two arms. Output: `experiment/g12/FAILURE_ATTRIBUTION1.json`.

| arm | fix covered | repaired when covered | repaired when not | estimated gain of full coverage |
|---|---|---|---|---|
| stack trace | 11 of 40 | 11 of 11 | 15 of 29 | 14.0 cases |
| rewritten localizer | 15 of 40 | 14 of 15 | 13 of 25 | 10.3 cases |

In both arms the localizer is named. Where the evidence covers the fix, the proposer
repairs 25 of 26 cases; every other failure but one happens where it does not. The earlier
trial's reading, "no system gain from the better localizer", needs this correction: the
localizer rose from 11 to 15 covered cases, and the estimate taken from the stack-trace arm
alone expects 1.9 more repairs from those four cases; the paired trial observed 1. The gain
was small because the component moved little, not because it does not matter.

On IMPROVE1 (170 functions, isolated arm), 66 of 73 failures are first unmet at "a rewrite
is cheaper" and 7 at "behaves like the original": the writer's ideas for a gain limit that
system, not its ability to preserve behaviour on the recorded calls.

## Limits

- The estimate is observational. Cases whose fix is not covered may be harder for every
  component. It ranks what to change next; it proves nothing until a change is tried.
- One check exists, on one trial of 40 cases: 1.9 expected, 1 observed.
- All records are development records, already used. No held-out case is involved.
- A condition never met, or always met, has no estimate.

## What follows

The next experiment changes the localizer, since both arms name it. Its lineage stopped at
88 of 211 validation cases with one input, the stack trace. The same instrument is to be
applied one level down, to the localizer's own misses: which source of information (frames
of the trace, the failing test's source, names in the assertion message) would have
covered the fix. That decides which input the next generation of localizers receives.

Review: `docs/IP_REVIEWS/FAILURE_ATTRIBUTION_REVIEW_2026-10-10.md`. Five focused tests pass.
