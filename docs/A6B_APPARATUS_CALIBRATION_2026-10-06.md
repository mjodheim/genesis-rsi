# A6b apparatus calibration — 2026-10-06

**Status: DEVELOPMENT CALIBRATION ONLY — not prospective evidence**

A6 failed prospectively because accumulated memory could starve useful generic
candidates and because the autonomous runner could not compose multiple
individually expressible edits.

A6b changes the search apparatus before selecting any fresh A6b evidence tasks.

## Architectural changes

1. **Target-aware memory use** — retained/template/exemplar candidates outside
   the frozen task source scope are removed before scheduling.
2. **Fair candidate scheduling** — generator families are interleaved with
   fixed weights instead of concatenating all memory candidates ahead of the
   generic grammar.
3. **Bounded multi-site scalar composition** — compatible generic scalar edits
   can be coordinated across source sites.
4. **Causal learned-template composition** — two applications of the same
   template learned from a prior passing result may be combined across distinct
   files into one candidate.
5. **Legacy-safe rendering** — retained Go templates preserve short declaration
   syntax and postfix increment spacing.

No task-specific repair rule is added.

## Retrospective calibration

Tasks 9 and 10 from the failed A6 campaign were replayed only to check whether
the new apparatus addresses the observed mechanisms. They can never count as
A6b evidence.

### A6 task 9 — search starvation

The original A6 runner had the correct zero-LLM scalar repair at full mixed-pool
rank **524**, outside the budget of 256.

With the frozen A6b scheduler, the same exact candidate is evaluated at rank
**157** and passes.

Result digest:

`42ad1e98da501252b82976fb5f12d0b818608b50c0940a2709e58294ba56f7aa`

### A6 task 10 — causal multi-file reuse

Task 10 required the same retry-boundary correction in two files. During A6,
the single-site runner could not compose those edits.

A6 task 9's successful fallback had already produced a retained generic line
template for the comparison-boundary change.

The A6b apparatus applies that **previously learned template** to both analogous
files, composes the two applications, and passes task 10 at candidate rank
**1**, with zero model calls.

Result digest:

`30f5683d1c12bc37d0c2899c353674d40f41ac2344859933942c0c540114b297`

This is especially important architecturally because the later candidate is
not a new host-authored fix: it is composed from experience learned on the
previous evaluated task.

## Boundary

These results are contaminated by prior task inspection and therefore prove
only that the apparatus now addresses two known A6 failure modes.

A6b must be frozen and evaluated on **fresh public external tasks** before any
claim of decreasing fallback dependence can be made.
