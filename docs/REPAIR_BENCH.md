# Repair bench

The bench scores a repair mechanism on bugs nobody involved has looked at. See
`genesis/repair_bench.py`, `genesis/repair_proposers.py` and `docs/DEFECTS4J_SANDBOX.md`.

## Split

`experiment/bench/REPAIR_BENCH_SPLIT_V1.json` assigns each active case of the pinned Defects4J
revision to `held_out` when `sha256("genesis-repair-bench-v1|" + case) mod 5 == 0` and the case was
never exposed; everything else is `development`. The whole Lang project and every case a recorded
study, audit or smoke test opened are exposed. The file is written once and sealed by digest.

Held-out cases are listed in hash order and trials take them from the front. A case is consumed
when a preregistration names it. It is never used twice.

Benchmark-wide statistics were computed before the split existed
(`experiment/g12/REPAIR_SEARCH_SPACE_DIAGNOSIS_20261008.md`). They are aggregates and did not
inform any mechanism here, but the split is not pristine in the strictest sense.

## What a case shows a proposer

Only what running the buggy revision's relevant tests shows: failing test names, stack traces,
source around the test frames, and numbered source around the production frames. When no trace
enters production code, the class the failing test is named after is shown instead. The fixed
revision is never checked out during a trial.

## Arms

| Arm | Proposer |
|---|---|
| `strategist` | the existing operator families, no model call (control) |
| `model` | a language model given the evidence in one prompt |
| `model_explore` | the same, with read and search access to a copy of the buggy sources and tests |

Every arm gets the same number of validations per case. An arm works in at most four rounds; each
round it is shown its own earlier candidates with what the validator observed (compiler errors, the
test that still fails, the tests it broke), and it stops at the first candidate that passes the full
suite. Model proposals that touch anything outside the production source directory are dropped.

## Verdict and its limits

A candidate is `plausible` when it compiles, the failing tests pass and the full developer suite
passes. That is not correctness. After a trial is sealed, `scripts/audit_repair_bench_trial.py`
reads the fixed revisions of the solved cases and counts the accepted patches identical to the
developer's, which is a lower bound on correct.

Defects4J is public. A model may have seen these fixes in training, so a model arm's score measures
the loop end to end, not unaided reasoning. Bugs published after a model's training cutoff are the
way to separate the two.

## Running a trial

```
python scripts/run_repair_bench_trial.py preregister --name T1 --held-out 24 --budget 10 \
    --arms strategist model model_explore --model claude-sonnet-5-5
git add experiment/bench/TRIAL_T1_PREREG.json && git commit && git push   # before running
python scripts/run_repair_bench_trial.py run --name T1 --workspace /srv/genesis/bench
python scripts/audit_repair_bench_trial.py --name T1 --workspace /srv/genesis/bench
```

A rehearsal names development cases with `--cases` instead of `--held-out`.
