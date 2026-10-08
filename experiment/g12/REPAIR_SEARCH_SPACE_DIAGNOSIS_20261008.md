# Why the repair search returns nothing on unseen bugs (2026-10-08)

Status: **diagnosis of recorded negative results. No new repair, no new blind evidence, no RSI claim.**

Twelve prospectively frozen Defects4J cases produced zero full-suite repairs (G11: 0/9, V2.1: 0/3).
The earlier reports attributed this to budget, file allocation and compile validity. This audit
measures the search space itself.

## Method

`scripts/audit_repair_search_space.py` takes the 14 cases whose buggy code a recorded study has
already opened, regenerates **every** candidate the strategist can produce with all experimental
families enabled and no top-k cut, then reads the human fix and compares. All Defects4J commands ran
through the container boundary of `genesis/defects4j_sandbox.py`. Result:
`REPAIR_SEARCH_SPACE_AUDIT_20261008.json`.

Reading the fix spends these cases for good: they are development cases only.

Three of the 14 (marked `*`) later received an operator written by hand after the bug was seen.
They say nothing about unseen bugs and are excluded from the summary.

## Result

| Case | Fixed file rank | Human fix (lines removed -> added) | Candidates | In fixed file | On the fix lines | Exact fix |
|---|---|---|---:|---:|---:|---|
| Codec-15 | 1 of 5 | 5->3, 0->3 | 1727 | 767 | 0 | no |
| Compress-6 * | 1 of 3 | 0->1, 2->4, 1->1 | 2213 | 2116 | 65 | no |
| Math-53 * | 1 of 16 | 0->3 | 694 | 185 | 19 | rank 1 |
| Csv-16 * | 1 of 9 | 0->1, 0->1, 1->4, 1->0 | 2547 | 373 | 27 | no |
| Collections-24 | 1 of 7 | 0->1, 1->1, 0->5 | 883 | 120 | 0 | no |
| Gson-2 | 34 of 39 | 1->4, 0->9 | 525 | 0 | 0 | no |
| Jsoup-68 | 2 of 43 | 4->1 | 718 | 44 | 0 | no |
| JacksonCore-11 | 1 of 40 | 0->1 | 965 | 45 | 0 | no |
| Cli-34 | 9 and 2 of 17 | 1->1, 1->1 (two files) | 1251 | 229 | 0 | no |
| Time-22 | 21 of 66 | 1->1, 0->5 | 587 | 19 | 0 | no |
| JxPath-12 | 19 of 90 | 1->2 | 583 | 40 | 0 | no |
| Chart-23 | 1 of 41 | 0->19 | 719 | 19 | 0 | no |
| JacksonXml-4 | 22 of 27 | 0->4, 1->1 | 1024 | 35 | 0 | no |
| Mockito-22 | 1 of 77 | 1->3 | 257 | 17 | 6 | no |

On the 11 cases without a hand-written operator:

- the fixed file is in the 32-file focus set in **10 of 11**, and ranked first in 5;
- **9,239** candidates are generated in total;
- **1 of 11** cases has any candidate that edits a line the fix edits (Mockito-22, first at rank 125);
- **0 of 11** contain the fix.

## Reading

1. **The fix is not in the search space.** Validating 8 or 12 candidates per arm was not the binding
   limit: validating all of them would have changed nothing in 10 of 11 cases.
2. **The space is closed and small.** 97 % of the atomic candidates on these cases (1,826 of 1,873;
   the rest of the 9,239 are pairs of them) come from three
   families that perturb tokens already present: `scalar` (986), `java_structural` (689) and
   `java_symbol` (151). Every family is capped at 64 to 96 candidates per case.
3. **The fixes need code that is not there.** 13 of the 14 fixes add lines; five add four or more.
   Nothing in the strategist synthesises a statement from the failure.
4. **There is no line-level localisation.** Candidates are spread over a file with no evidence
   about where the failure occurs. In JacksonCore-11 the fix is one inserted line in the
   first-ranked file and none of the 45 candidates in that file is on it.
5. **The specialised families are memorised cases.** `java_state_consistency`,
   `java_sibling_guard` and `java_stream_iterator` each emit exactly one candidate, on exactly the
   case they were written for after it was exposed. `java_calendar`, `java_empty_segment`,
   `java_test_switch`, `java_range` and `java_default_normalization`, written the same way for the
   ER1 Lang cases, emit nothing on any of the 14.

File-level localisation is therefore not the problem, and budget is not the problem. The mechanism
has no way to produce a repair it was not handed.

## How large the target is

`scripts/audit_defects4j_fix_shapes.py` counts fix shapes over all 854 active bugs of the pinned
benchmark (`DEFECTS4J_FIX_SHAPES_20261008.json`):

| Shape of the human fix | Bugs | Share |
|---|---:|---:|
| touches one file | 727 | 85 % |
| one file, one hunk | 473 | 55 % |
| one hunk, at most 3 changed lines | 269 | 31 % |
| one line replaced by one line | 142 | 17 % |
| adds at least one line | 837 | 98 % |
| failing-test stack trace passes through the fix hunk | 157 | 18 % |

**Contamination notice.** These are aggregates over the whole benchmark. They were computed before
any held-out split existed. A split must be frozen before further work, and nothing may be computed
on its held-out part again.

An exploratory, unversioned pass over the 142 one-line fixes abstracted each edit into a token
pattern and asked whether the same pattern occurs in a *different* project: 40 of 142 do, but only
5 without a free slot that must be filled with the right identifier from scope. Treat those two
numbers as an order of magnitude only.

## Consequence

A mechanism with no large model that learns edit patterns from released fixes and fills them from
the surrounding code can reach a few percent of unseen bugs, not more: that is also what published
template-based repair systems report under realistic localisation. It would be the first non-zero
blind result here and it gives a measurable learning curve, but it is not general repair.

Whatever generates candidates, three things are missing and are needed first:

1. line-level fault localisation from the failing run (stack trace, then coverage);
2. validation of hundreds of candidates per case instead of 8 to 12, behind the container boundary;
3. a development / held-out split frozen before any further look at the benchmark.
