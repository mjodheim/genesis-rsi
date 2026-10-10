# What limits repair: one component changed at a time — 10 October 2026

General RSI remains the objective, not an achieved result. The observational attribution
of this date named the fault localizer as the component that limits repair;
DEV_COVERAGE_REPAIR1 did not bear it out. This report names a component from
interventions only, and records a hypothesis of mine that the trial refuted.

## How the seed agent's attempts end

`scripts/run_repair_interventions.py stops` reads four sealed records of the seed
configuration (Claude Haiku 5.5, 8 requests and 6 validations per case): 208 attempts on
105 development cases, 68 of them failed. No model is involved. Output:
`experiment/g12/REPAIR_STOPS1.json`, digest `6e58b619…`.

| how a failed attempt ended | attempts |
|---|---|
| nothing was tested: the model submitted an empty list | 23 |
| nothing was tested: edits could not be applied, or no usable answer | 9 |
| candidates tested, the failing tests still fail | 27 |
| candidates tested, other tests break | 9 |

32 of 68 failures end without one candidate tested, and with half the requests unused: an
empty round ends the case. 51 of 68 leave requests unused and all 68 leave validations
unused. Reads of a file were refused 22 times in failed attempts and never in a repaired
one: the model gives the start line as a range, the tool answers with an error name only.

From these counts I expected the stopping rule, the tools or the split of the budget to be
what loses cases. The trial below was built to test exactly that, with the model and the
localizer as comparisons.

## Trial DEV_REPAIR_INTERVENTIONS1

`genesis/intervention_diagnosis.py` reruns a system on cases it failed, once unchanged and
once per variant, each variant changing one component, and compares each variant with the
unchanged rerun on the same cases (exact one-sided sign test). The unchanged rerun is what
keeps a case lost by chance from being credited to a change. A component is named when its
variant gains at least 3 cases net with p ≤ 0.05.

Cases: the 32 development cases the seed agent failed in at least half of two or more
sealed attempts. Arms, in an order rotated per case: the unchanged agent and six variants
(`genesis/repair_interventions.py`). The stronger model (Claude Sonnet 5.5) was run on the
first 16 cases only, to bound spending. Preregistration
`experiment/g12/DEV_REPAIR_INTERVENTIONS1_PREREG.json`, digest `7505a45d…`, pushed before
the run. "Repaired" means the project's tests pass.

| arm | component changed | repaired | gained / lost against the unchanged agent | p |
|---|---|---|---|---|
| unchanged | — | 12 of 32 | | |
| reads tolerated, refusals explained | inspection tools | 12 of 32 | 3 / 3 | 0.66 |
| an empty round does not end the case | stopping rule | 11 of 32 | 3 / 4 | 0.77 |
| one round of seven inspections | budget split | 10 of 32 | 2 / 4 | 0.89 |
| twice the requests, validations, rounds | envelope | 10 of 32 | 2 / 4 | 0.89 |
| developers' edit sites as locations | localizer (oracle) | 14 of 32 | 5 / 3 | 0.36 |
| Sonnet 5.5, same everything else | model | 11 of 16 (unchanged: 6 of 16) | 5 / 0 | 0.031 |

- The diagnosis names the model, and no other component. Six comparisons were made and no
  correction was applied, as preregistered: at 0.031 the result would not survive one.
- The unchanged agent repairs 12 of these 32 cases on a rerun. They were selected for
  earlier failures; a single attempt is noisy, which is why every comparison is paired.
- Under the changed stopping rule, empty endings fall from 11 to 3 and tested-and-failing
  ones rise from 9 to 16: the agent goes on, and what it then proposes fails. With twice
  the envelope it validates 90 candidates instead of 39 and repairs fewer cases. The
  early stop was a symptom: the model had no repair to submit.
- Even told the developers' own edit sites, the agent repairs 14 of 32. This is the upper
  bound of what any localizer could add on these cases, and it is not distinguishable from
  nothing.
- All 32 cases were usable. USD 2.92, of which 1.56 for the 16 Sonnet attempts.

## Read after the result, not preregistered

- On the 16 cases with a Sonnet arm, the five Haiku arms that do not read the fix
  (unchanged, tools, stopping rule, split, envelope) repair 8 between them; Sonnet alone
  repairs 11, including all 8. Five attempts with the weaker model, each with its own
  change to the machinery, do not reach one attempt of the stronger one.
- Over the 32 cases, those five arms repair 17 between them and 15 under none; 10 cases are
  repaired by five of five or four of five, 7 by one or two.
- 10 of 32 cases are repaired under no arm at all (4 of the 16 that had a Sonnet arm);
  five of them are Closure cases.

## What this establishes and what it does not

Established, on development cases: on the cases the agent fails, changing its tools, its
stopping rule, the split or the size of its budget recovers nothing measurable; replacing
the model recovers 5 of 16 and loses none. The component that limits repair is the one
Genesis does not own. The counts of how attempts end (half the failures with nothing
tested and budget left) pointed at the machinery and were wrong about the cause; so was
the earlier attribution to the localizer. Both were readings of rates.

Not established: that the machinery cannot matter (each variant is one hand-written
change, tried once; margins of two or three cases are within noise at this size); that
the model effect holds at a corrected level or beyond these cases; anything about the 10
cases no arm repairs.

## Consequence for G12

The repair agent's results are, to a first approximation, the model's. Configuration
lineages (LINEAGE1, LINEAGE2), a better localizer and the four machinery changes here all
moved a component around the model and none moved repair. A system that is to improve
itself on this task has to contribute something the model does not already do — its own
search, checks or accumulated material entering the candidates — and that contribution
has to be measured at equal model and equal budget, where this trial shows the baseline
is noisy and the margin small. The place to look for it is the 15 cases no Haiku arm
repairs, of which a stronger model repairs some: they separate what the model lacks from
what cannot be repaired within this envelope at all.

## Limits

- 32 cases, 16 for the model arm, one run per arm, development cases chosen because the
  agent failed them: no repair rate is estimated.
- The benchmark may be in the models' training data, more so for a larger model.
- Plausible patches were not compared with the developers' fix.
- The oracle arm reads the fixed revision through the recorded edit sites.

## Reproduction

```
python3 scripts/run_repair_interventions.py stops --name REPAIR_STOPS1
python3 scripts/run_repair_interventions.py preregister --name DEV_REPAIR_INTERVENTIONS1 --development W --cases 32 --model-cases 16
python3 scripts/run_repair_interventions.py run --name DEV_REPAIR_INTERVENTIONS1 --workspace R
```

Sealed result: `experiment/g12/DEV_REPAIR_INTERVENTIONS1_RESULT.json`, digest `57d4f10e…`.
Review: `docs/IP_REVIEWS/INTERVENTION_DIAGNOSIS_REVIEW_2026-10-10.md`. 8 focused tests pass.
