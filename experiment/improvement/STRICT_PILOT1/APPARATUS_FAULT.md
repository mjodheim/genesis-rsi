# STRICT_PILOT1 — apparatus fault

The harness is copied from the working tree at every container run. While this trial was
running, the working tree was switched to branches that hold the harness without the
`variants` and `native` modes. During that window the variant replay returned nothing, so the
variant check compared against an empty reference, and the uninstrumented replay did not
complete.

In `RESULT.json`: 39 attempts end as "did not finish" for that reason, and 6 accepted
rewrites, 37 "not cheaper" refusals carry `variants: 0`. The result is kept as sealed and is
not used for any count. The runner now stops when the machinery differs from the frozen plan
before and after each case; STRICT_PILOT2 repeats the trial on the same development cases.
