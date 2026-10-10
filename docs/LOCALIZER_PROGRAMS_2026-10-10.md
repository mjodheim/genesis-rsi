# Searched programs over archived localizers — 10 October 2026

General RSI remains the objective, not an achieved result. RECOMBINE1 improved the fault
localizer without a model, but with one merge rule fixed by hand. This report covers a
mechanism in which the rule is searched, and its judgment on projects that took no part in
any development.

## What was built

A *program* is a tree of at most fifteen nodes. Its leaves are members of the archive (the
41 modules the two lineages left). Its nodes are nine operations on ranked lists of
locations: `head` and `tail` (first or remaining items), `apart` (drop an item standing
within 10, 20 or 40 lines of one already kept), `shift` (move lines by 15 or 30), `join`,
`weave` (alternate two lists), `agree` (keep what another list confirms within the window)
and `files` (keep what lies in a file another list names). A program reads no file and runs
no model-written code: judging one is arithmetic on answers computed once.

Each generation:

1. **diagnosis** — the champion's misses on the search cases are split into those some
   member localizes alone, those whose edit sites are each covered by some member, and those
   no combination can reach;
2. **search** — 40 rounds of mutation and crossover, 300 new programs a round, about 11 000
   distinct programs scored; programs that localize exactly the same cases count once among
   the survivors;
3. **gate** — the best program, if it beats the champion on the search cases, is scored on
   the selection cases and replaces the champion under the rule of the lineage (gained
   minus lost at least 5, one-sided sign test at most 0.05);
4. a promoted program joins the archive under its name and is a leaf afterwards.

Search cases: 198 development training cases and the 293 cases of the first external part
(scored once by EXTERNAL1, used here as development material). Selection: 278 development
selection cases. Final: the 254 prepared cases of the second external part, 70 projects no
earlier work touched, scored once. The development validation cases are not used. The plan
(`experiment/localizer/PROGRAMS1/PLAN.json`, digest `7f9ac356…`) was pushed before the
search ran. No model was called.

## Result

| | search (491) | selection (278) | final, unseen projects (254) |
|---|---|---|---|
| champion of LOCALIZER1, model-written | 199 | 88 | 125 |
| composite of RECOMBINE1, rule fixed by hand | — | 106 | 129 |
| generation 1, program `p-9bbff1853910` | 246 | 107 | 136 |
| generation 2 | 258 | 108 | not scored |

- Generation 1 is promoted: 30 selection cases gained, 11 lost, sign test 0.002. The
  program weaves four lists drawn from six members, restricts two of them to files another
  names, shifts two by fifteen lines and keeps items twenty lines apart. The champion it replaces is
  not among its leaves.
- Generation 2 is rejected: 3 gained, 2 lost. Twelve more search cases did not carry over.
- Final cases, scored once: against the champion, 23 gained and 12 lost, sign test 0.045,
  established under the rule of the plan, narrowly. Against the hand-written composite, 16
  gained and 9 lost, sign test 0.11: not established.
- The composite of RECOMBINE1 against the champion on these cases: 14 gained, 10 lost,
  sign test 0.27. Its gain on the first external part (29 against 8) is not repeated on the
  second.

## Ablations (search and selection cases only)

The whole run was repeated with each operation removed in turn.

| removed | generation 1, search | generation 1, selection | chain |
|---|---|---|---|
| none | 246 | 107 | 1 |
| `head` | 244 | 119 | 1 |
| `tail` | 242 | 108 | 1 |
| `apart` | 244 | 116 | 1 |
| `shift` | 244 | 100 | 2 |
| `join` | 249 | 114 | 1 |
| `weave` | 247 | 115 | 1 |
| `agree` | 247 | 113 | 1 |
| `files` | 240 | 109 | 1 |

No operation is necessary: every reduced language reaches 240 to 249 search cases and a
promoted first generation. Seven of the eight reduced runs score higher on the selection
cases than the full run. Removing an operation changes the whole random course of the
search, so these rows measure the spread between searches as much as the worth of an
operation; that spread, 100 to 119, is wider than the difference between the searched
program and the hand-written rule. The gain comes from combining members. Nothing shows
that it comes from a particular operation, and the run of the plan is not the best of the
nine. None of the eight others was scored on the final cases.

## What the system's diagnosis says

After generation 1 the champion misses 245 of the 491 search cases:

- 92 are within reach of a combination (76 localized by one member alone, 16 by pooling
  members). Second generations gain 7 to 13 of them on the search cases and few on
  unseen ones (at most 5 net): which member is right changes from case to case, and a program applies the
  same combination to every case. The language has no condition on the case.
- 153 are out of reach of any combination. Read without a model: 79 have every edited file
  named by some member but no window on the edit (62 of these files do not appear in the
  failure report); 45 have an edited file no member names; 29 have more than six separate
  edit sites, which six windows cannot cover.

The component that now limits localization is therefore the evidence the members produce
inside the right file, then the choice of member per case. Recombination of what exists is
close to exhausted: of ten runs (RECOMBINE1, this one, eight ablations), nine stop after
one generation and one after two.

## Limits

- One search run under the plan; the ablations show a different seed could have given a
  noticeably different program.
- The final gain over the champion is at the threshold (0.045) on one part of one catalogue.
- Java only; localization, not repair.
- The operations and their parameters were written by hand; the search composes them.
- The selection cases have now been used by two lineages, RECOMBINE1, this run and eight
  ablations. They should not carry a further claim.
- The second external part is consumed for these three localizers. The reserve (173 cases)
  is untouched.

## What this establishes and what it does not

Established: a program found by search over archive members, with no model request,
localizes more than the model-written champion on 70 projects that took no part in any
development (136 against 125 of 254). With EXTERNAL1, the model-free step past the
lineage's plateau is confirmed twice on independent projects.

Not established: that the searched program beats the hand-written rule; that any operation
of the language matters; that a chain of model-free generations exists (it stops at one);
that localization gains repair more bugs.

## Reproduction

```
python3 scripts/run_external_localization.py prepare --source G --workspace E --part second
python3 scripts/run_localizer_programs.py answers --external E
python3 scripts/run_localizer_programs.py evolve  --external E --development W --name PROGRAMS1
python3 scripts/run_localizer_programs.py ablate  --external E --development W --name PROGRAMS1
python3 scripts/run_localizer_programs.py verify  --external E --development W --name PROGRAMS1
```

Sealed: `EVOLUTION.json` (`7c7debe2…`), `FINAL.json` (`8378b154…`), `ABLATIONS.json`
(`1b74652d…`) under `experiment/localizer/PROGRAMS1/`. 6 focused tests pass.
Review: `docs/IP_REVIEWS/LOCALIZER_PROGRAMS_REVIEW_2026-10-10.md`.
