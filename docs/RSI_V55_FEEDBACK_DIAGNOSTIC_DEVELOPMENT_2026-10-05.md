# RSI V55 — feedback-driven sparse-mask diagnosis — development — 2026-10-05

## Why V55 exists

V53 improved sustained search through learned scaffolds, but still exhausted in a
few late windows. V54 tested deeper cross-task recursive memory and failed to
improve V53.

The V54 diagnosis showed that the remaining late-window failure was not mainly
a memory problem. Each window independently samples fresh mask-bit positions,
while the unchanged G7 search enumerates bit toggles in increasing bit order.
At larger widths, the fixed request budget can therefore expire before the
current target bit is ever probed.

V55 targets that intra-task coverage bottleneck without reading the hidden
target and without increasing the inherited external budget.

## Mechanism

When all of the following are true:

- width >= 10;
- no compatible exact memory is available;
- the observed root quality is exactly consistent with a rotation-zero sparse
  mask containing one or two differing bits;

V55 temporarily replaces speculative cross-width memory with target-blind
diagnostic probes.

From the root quality, V55 infers only the number of differing bits. It then
maintains every sparse mask consistent with observations. Each diagnostic probe
is selected to split the current hypothesis set as evenly as possible. The
probe's scalar quality determines only how many target bits intersect the probe,
which filters the hypothesis set. Once one hypothesis remains, it is evaluated
as the diagnostic solution candidate.

During diagnosis, only the root branch is exposed. This deliberately prevents
G7's second parallel parent from spending the fixed budget on unrelated
branches while the sparse mask is being identified.

No target value, expected output, task family, hidden task identifier or future
quality enters the diagnostic planner.

## Exhaustive development property

For every one-bit and two-bit mask at widths 10 through 16, the committed
diagnostic planner identifies the exact mask in at most six probes.

Additional pre-freeze analysis showed:

- widths 17 through 23: at most seven probes, zero failures;
- width 24: four sparse masks exceed the eight-round horizon.

The V55 prospective horizon is therefore frozen only through width 20, leaving
one full round for the final solution evaluation after the worst observed seven
probes.

## Matched consumed-data result

The policy was selected on the already-consumed V53 prospective seeds only.

| Seed | V53 solved | V55 solved | V53 evals | V55 evals |
|---|---:|---:|---:|---:|
| 530061 | 65 | **81** | 1824 | **1693** |
| 530062 | 59 | **85** | 1885 | **1661** |
| 530063 | 67 | **85** | 1829 | **1650** |
| **Total** | **191** | **251** | **5538** | **5004** |

Development observations:

- +60 solved tasks vs V53;
- 534 fewer charged evaluations;
- 42 diagnostic routes;
- 42 / 42 diagnostic tasks solved;
- 178 diagnostic probes evaluated;
- 0 diagnostic aborts;
- 30 direct solve gains vs V53;
- 0 direct diagnostic solve regressions;
- every one of the 14 consumed V53 windows remains positive on every seed;
- the V53 zero windows are repaired.

These numbers are development evidence only and cannot qualify V55.

## Prospectively frozen next assay

The fresh V55 campaign extends the horizon to:

- seeds 550071, 550072, 550073;
- 18 windows per seed;
- widths 3 through 20;
- 12 tasks per window;
- 648 total tasks.

No V55 parameter may change after the first prospective behavioral execution.
