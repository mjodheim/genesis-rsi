# Chained improvements of functions in working libraries — 10 October 2026

General RSI remains the objective, not an achieved result. This report covers the first
mechanism in this repository that proposes improvements inside programs that already work,
keeps only those a model-free judge verifies on calls the writer never saw, and builds each
improvement on the previous one.

## What was built

A case is one top-level function of a pinned pure-Python library
(`experiment/improvement/CORPUS_V1.json`: 19 packages, each pinned by the SHA-256 of its
source distribution). The library's own tests are run once with a recorder that captures
every call reaching the function. The behaviour to keep is the original function's outcome
on each recorded call: a canonical form of the result or exception and of the arguments
afterwards. The cost is the number of instructions executed between two markers, counted
by Callgrind; two runs of the same code differ by 0.015 % to 0.1 %.

The external model (Claude Haiku 5.5 through OpenRouter) sees the function, its module
context, eight recorded calls and the record of its earlier attempts on that function. It
returns one function with the same interface. The reply is checked without being executed,
then judged in a container with no network, a read-only root and no capabilities. A rewrite
is accepted when all three hold:

1. its outcome is identical on every recorded call, shown and hidden;
2. no library test that passed before fails;
3. on at most 150 hidden calls it executes at most 97 % of the instructions of the version
   it replaces.

An accepted rewrite becomes the base of the next step. A chain stops when a step of two
attempts yields no accepted rewrite, or after ten steps.

Roles are fixed by a hash of the case name. Of 233 eligible cases, 63 served to develop the
mechanism and 170 were kept for the trial. Library sources, recorded calls and rewritten
functions stay outside the repository; the sealed files hold digests, counts and outcomes.

## Trial IMPROVE1

The plan (`experiment/improvement/IMPROVE1/PLAN.json`, digest `dc00449b…`) was committed
before the first request. Two arms ran on the same 170 cases:

- **isolated**: each function alone;
- **accumulating**: functions in a fixed order, the writer also receiving what earlier
  functions taught (accepted and refused rewrites), refreshed every eight cases.

| | isolated | accumulating |
|---|---|---|
| functions improved at least once | 97 of 170 | 96 of 170 |
| improved a second time | 53 | 48 |
| longest chain | 5 | 9 |
| accepted rewrites | 191 | 206 |
| refused: not cheaper | 332 | 342 |
| refused: behaviour differs | 35 | 37 |
| final instruction ratio, improved functions (geometric mean) | 0.615 | 0.606 |
| final instruction ratio, all functions | 0.757 | 0.754 |
| ratio after the first step, improved functions | 0.720 | 0.738 |
| requests, cost | 647, USD 1.12 | 689, USD 1.38 |

Chaining works: of 97 improved functions, 53 are improved again from the accepted rewrite,
29 a third time, and the mean ratio moves from 0.72 after one step to 0.61 at the end of
the chain. Every chain stops well before the ten-step limit except one of nine steps.

The record of earlier functions changes nothing measurable. On the 146 cases after the
24-case warm-up, 12 functions are improved only in the isolated arm and 11 only in the
accumulating arm (sign test 0.66); the final ratio is lower by more than one point 40 times
on each side (0.54). The accumulating arm has longer chains at the tail and a slightly
worse first step; one run does not separate either from chance.

## Reading of accepted rewrites (not preregistered)

"Identical on recorded calls" is not equivalence. After the result was sealed, the final
rewrite of 24 improved functions of the isolated arm was read against the original; the 24
are the first by SHA-256 of `audit:` followed by the case name. Suspected differences were
executed in the same container.

- **15 of 24** are equivalent as far as reading shows: hoisted lookups, fast paths with
  the original kept as fallback, inlined helpers, precompiled patterns, closed forms.
- **5 of 24** behave the same but reach into internals the original did not: private
  attributes of graph or message objects, a constructor bypassed with `object.__new__`,
  and one that calls the undecorated function behind the library's backend dispatch, which
  changes behaviour as soon as a backend is configured.
- **4 of 24** change behaviour on inputs the tests never exercise. Three were confirmed by
  execution: a combinations generator that now raises on unhashable elements, an index
  computation that treats NaN as equal to itself, and a breadth-first search that returns
  edges for a depth limit of zero. The fourth returns a value where the original raised on
  a negative width.

The largest gain of the sample (ratio 0.14) is one of the four. Roughly one accepted chain
in six is therefore wrong outside the recorded calls, and the count of 97 overstates the
number of improvements a maintainer would merge.

## Limits

- The judge counts instructions. A single native timing per call, which includes the
  canonical encoding of the result and was taken while six workers shared the machine,
  gives a geometric mean of 0.91 on the improved functions of the isolated arm, with 62 of
  97 faster. Instruction counts overstate what a user would feel.
- Values computed at import time by a rewrite are outside the measured region.
- The pilot showed a rewrite accepted after dropping a branch that needs a package absent
  from the container. The judge sees only the environment it runs in.
- One run per arm; one writer model; pure-Python functions with recorded calls only.
- The 170 trial cases are now consumed.

## What this establishes and what it does not

Established: an external writer, a model-free judge and a chain in which each accepted
change is the base of the next produce verified cost reductions on most functions of
working libraries, at about USD 0.007 per function.

Not established: that accumulated experience helps (the paired comparison is null), that
the accepted rewrites are equivalent (about one in six of those read is not), or anything
about Genesis improving its own machinery. The writer, the judge and the acceptance rule
were fixed by hand throughout. Before any larger trial the judge needs generated inputs
beyond the recorded calls and a refusal of new uses of private attributes.

## Reproduction

```
python3 scripts/run_program_improvement.py fetch   --workspace W
python3 scripts/run_program_improvement.py prepare --workspace W
python3 scripts/run_program_improvement.py plan    --workspace W --name IMPROVE1 --role trial
python3 scripts/run_program_improvement.py run     --workspace W --name IMPROVE1 --workers 6
python3 scripts/run_program_improvement.py report  --workspace W --name IMPROVE1
```

The protocol options of the trial are those recorded in `PLAN.json`.

Sealed result: `experiment/improvement/IMPROVE1/RESULT.json`, digest `8387a32e…`.
The image is built from `deploy/program-improvement/`. 36 focused tests pass.
Review: `docs/IP_REVIEWS/PROGRAM_IMPROVEMENT_REVIEW_2026-10-10.md`.
