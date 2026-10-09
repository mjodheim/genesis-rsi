# Fault localizer rewritten as code — 9 October 2026

General RSI remains the objective, not an achieved result. This report covers the first
lineage in this repository where the thing that changes is executable code of Genesis, the
judge needs no model, and each generation is scored on cases it was not shown.

## What was built

The repair bench tells the repair agent where to look by reading the failing tests' stack
traces. That rule is now generation zero (`genesis/localizer_seed.py`) of a lineage of
Python modules: `localize(case)` receives the stack traces and read access to the buggy
sources and returns at most six suspect locations. A case is *localized* when every place
the developers changed lies within forty lines of a returned location in the same file.

A successor is written by the external model (Claude Haiku 5.5 through OpenRouter) from the
current module, its score, ten of its misses on training cases with the place the fix
really was, and the record of earlier attempts. It is checked without being executed
(syntax, entry point, standard-library imports), then run in a container with no network,
a read-only root and read-only cases. The developer fixes are not mounted there. Scoring is
arithmetic, so every candidate is measured on hundreds of cases at no model cost.

All 687 development cases of the repair bench were prepared: buggy sources, the stack
traces Defects4J ships for the triggering tests, and the edit sites derived from the
developer patch. Their roles are fixed by a hash of the case name: 198 training cases
(the only ones whose misses are shown to the model), 278 selection cases (they decide
promotion) and 211 validation cases (scored once, after the lineage is frozen). Held-out
cases of the repair bench are not involved: none was checked out and their fixes remain
unextracted. 103 remain unconsumed.

Each generation has four attempts. The attempt with the most training cases localized, if
it beats the champion there, is scored on the selection cases and replaces the champion
when it gains at least five more cases than it loses with a one-sided exact sign test at
most 0.05. A lineage stops after three generations without a promotion. The plans were
committed before the runs.

## Two lineages

LOCALIZER1 gives the writer the record of earlier attempts; LOCALIZER2 is the same
protocol without it. Cases localized:

| Lineage | Module | Training (198) | Selection (278) | Validation (211) |
| --- | --- | ---: | ---: | ---: |
| both | seed | 32 | 41 | 43 |
| LOCALIZER1 | generation 1 | 56 | 67 | 73 |
| LOCALIZER1 | generation 3 | 65 | 86 | 88 |
| LOCALIZER2 | generation 1 | 56 | 94 | 80 |

LOCALIZER1 promoted two successors (generations 1 and 3) and
rejected the best attempt of generations 2 and 4 on the selection cases; generations 5 and
6 produced no attempt better than the champion on training. On the validation cases each
step holds: 43 to 73 (31 gained, 1 lost) and 73 to 88 (18 gained, 3 lost), 45 gained and
none lost from seed to final.

LOCALIZER2 promoted one successor and stopped after three generations without another. On
validation it goes from 43 to 80 (39 gained, 2 lost). Its selection score of 94 overstates
it: a module chosen because it did well on the selection cases looks better there than it
is, which is what the validation cases are for.

The promoted modules add general signals to the stack-trace rule: production methods the
failing test calls, files whose identifiers share words with the failure message, and the
production class a test class is named after. A search of the promoted modules finds no
project, package or class name from the benchmark.

24 and 16 attempts, 25 and 17 model requests, USD 0.151 and USD 0.115, no request of
unknown cost. One answer was refused for being cut off and was corrected in the same
attempt.

## What it does not show

**It does not keep improving.** Both lineages stop after one or two promotions: the last
three generations of each, twelve attempts, produce no successor.
This is a short chain followed by a plateau, not open-ended improvement.

**The record of earlier attempts is not shown to help.** With it the lineage ends at 88 of
211, without it at 80, in one run each. A first-generation attempt ranged from 17 to 56
training cases within one lineage; one run per arm cannot separate the two.

**A better localizer did not make the repair agent repair more.** DEV_LOCALIZED_REPAIR1,
preregistered before it ran, gave the same repair agent (seed configuration, same model,
six validations and eight requests per case) forty validation-role cases twice: once with
the evidence collected from the stack trace, once with production excerpts around the
locations of LOCALIZER1's final module.

| Measure | Stack trace | Final localizer |
| --- | ---: | ---: |
| Repaired (plausible) | 26 of 40 | 27 of 40 |
| Repaired by this arm only | 2 | 3 |
| Evidence covers the developer fix | 11 | 15 |
| Repaired when it does | 11 of 11 | 14 of 15 |
| Repaired when it does not | 15 of 29 | 13 of 25 |
| Candidates validated | 48 | 55 |
| Model requests | 144 | 131 |
| API cost, USD | 0.175 | 0.211 |

The one-sided exact sign test gives 0.5: no difference. When the evidence covers the fix
the agent almost always repairs the case, and the localizer covers four more cases; but
the agent also repairs half of the cases where the evidence misses the fix, because it can
read and search the sources itself and because a patch that passes the tests need not be
the developers' patch. Where the agent is told to look is not what limits it. Twice as
good on the proxy was worth one case in forty, which is nothing.

"Repaired" means the candidate passes the triggering tests and the whole suite, tolerating
failures already present on the unmodified buggy revision. It is not semantic correctness,
and Defects4J may be in the model's training data.

## What carries over

The apparatus is the part worth keeping: code as the evolving object, a container
boundary for model-written code, a model-free measure on hundreds of cases, three roles
with validation untouched until the end, and a preregistered end-to-end check that can
contradict the proxy, as it did here. It separated a real component gain from the absence
of a system gain in one evening for under one dollar.

The next lineage should target what a measurement says limits the whole system, not what
is convenient to score. For the repair agent that is the eleven of forty cases neither arm
repairs and the cases repaired only when the fix is covered; for the wider goal it is a
measure defined on a working program (time, memory, covered code) with its tests as the
judge.

## Record

Deviations and limits, none of which changes a score: a dry run on the first 47 prepared
cases preceded the plan and showed the model misses from training-role cases only; in
LOCALIZER1 one attempt that beat the champion on training without being the best of its
generation is labelled "not better on training" (57 against 56, generation 3), a label
the writer also saw in the record of earlier attempts, corrected for LOCALIZER2; the
stack traces of the lineage are the ones Defects4J ships, while the repair trial uses the
traces of its own test run. The lineage machinery changed by that label after LOCALIZER1
was verified, so LOCALIZER1's plan no longer matches the current machinery digest.

Artifacts: `experiment/localizer/LOCALIZER1` and `experiment/localizer/LOCALIZER2` (plan,
lineage, every attempted module under `modules/`, validation), and
`DEV_LOCALIZED_REPAIR1_PREREG.json` / `_RESULT.json` in LOCALIZER1. Prepared cases and
edit sites are derived data kept outside the repository. 25 focused tests pass.
Review: `docs/IP_REVIEWS/LOCALIZER_LINEAGE_REVIEW_2026-10-09.md`.
