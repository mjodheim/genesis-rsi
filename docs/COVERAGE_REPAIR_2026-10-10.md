# Does covering the fix make the agent repair? — 10 October 2026

General RSI remains the objective, not an achieved result. The failure attribution of this
date named the fault localizer as the component that limits repair, from sealed records:
where the evidence covered the developers' edit, 25 of 26 cases were repaired; elsewhere 28
of 54. That estimate was observational. Three localizer improvements later, this report
covers its first causal test.

## Trial DEV_COVERAGE_REPAIR1

The paired trial of 9 October drew 40 cases at random; on most of them both localizers
covered the fix or neither did, and it ended level (27 against 26). Here every case is one
where the two differ. Among the 211 validation-role development cases, the champion of
LOCALIZER1 and the searched program of PROGRAMS1 cover every edit site on 88 and 94 cases;
on 24 cases exactly one of them does (the program on 15, the champion on 9). All 24 were
run: the same repair agent (seed configuration, Claude Haiku 5.5 through OpenRouter, same
envelope) twice per case, once told to look where each localizer points, arm order
alternating. Locations are those stored when the localizers were scored. The
preregistration (`experiment/localizer/PROGRAMS1/DEV_COVERAGE_REPAIR1_PREREG.json`, digest
`a628c3ff…`) was pushed before the run. "Repaired" means the project's tests pass; a
plausible patch is not necessarily a correct one.

| | repaired of 24 | requests | inspections |
|---|---|---|---|
| arm whose locations cover the fix | 22 | 58 | 47 |
| arm whose locations do not | 18 | 80 | 82 |

- Paired: 18 cases repaired in both arms, 4 only where the fix is covered, 0 only where it
  is not, 2 in neither. One-sided exact sign test 0.0625: the direction is the expected
  one and the effect is not established under the rule of the plan.
- By localizer: 21 repaired with the program's locations, 19 with the champion's.
- All 24 cases were usable; no arm fell back on the collected evidence. USD 0.21.

## Why the arm without coverage still repairs

Read after the result, not preregistered. In the 18 cases the uncovered arm repairs, 17
patches edit the developers' own file, most of them at the developers' lines; in 5 of these
the file was not among the locations the arm was given at all. The repair agent has
read-only inspection tools (search a text, read a range of a file) and uses them: the
uncovered arm makes 82 inspections against 47. The agent localizes by itself when the
evidence points elsewhere. What a better localizer buys on these cases is mostly effort
(38 % more requests without coverage), and perhaps a few repairs.

## What this does to the attribution

The observational gap was 44 points (96 % against 52 %). Had it been causal, covering the
fix on 24 uncovered cases would have added about ten repairs; the paired difference here is
four. The two figures are not strictly comparable: these 24 cases are ones some localizer
covers, likely easier than uncovered cases at large. But the reading that the localizer
*limits* repair does not hold in the form the attribution gave it: cases where the
evidence missed the fix were mostly harder cases, not cases lost for lack of evidence. The
attribution orders conditions and compares rates; it does not separate a component's
effect from the difficulty of the cases where the component fails. Its report stands as
written, with this test as its correction.

## Limits

- 24 cases, one run, one model, development cases; the benchmark may be in the model's
  training data, which would also explain repairs at the developers' lines.
- Cases chosen because the localizers differ: not an estimate of either one's repair rate.
- Plausible patches were not compared with the developers' fix.

## What this establishes and what it does not

Established: with inspection tools, the repair agent repairs three cases in four when the
supplied locations miss the fix, and reaches the developers' lines by itself. The
localizer's gains (EXTERNAL1, PROGRAMS1) are real as localization and worth little as
repair on this agent.

Not established: that coverage has no effect (4 against 0); what limits repair. The 2
cases repaired in neither arm, and those the earlier trials left unrepaired, are where the
next diagnosis has to look, and it has to rest on interventions, not on rates.

## Reproduction

```
python3 scripts/run_coverage_repair_trial.py preregister --development W --name DEV_COVERAGE_REPAIR1
python3 scripts/run_coverage_repair_trial.py run --workspace R --name DEV_COVERAGE_REPAIR1
```

Sealed result: `experiment/localizer/PROGRAMS1/DEV_COVERAGE_REPAIR1_RESULT.json`, digest
`0a41a813…`. 2 focused tests pass.
