# A lineage of improvers, each written by its parent — protocol, 11 October 2026

General RSI remains the objective, not an achieved result. This document fixes, before any
lineage runs, what is built, what will be measured and what each outcome would mean.

## Why the architecture changes

On program repair every component Genesis owns was changed in turn (configuration,
localizer, tools, stopping rule, budget) and none moved the result; the model did
(`REPAIR_INTERVENTIONS_2026-10-10.md`). A pass/fail task that a model solves or not in a
few attempts leaves the surrounding system nothing to improve. Recursive self-improvement
needs an object the system owns, a score that is graded rather than binary, a judge that is
exact and cheap, and an improvement procedure that can be its own object.

## What is built

- **Task**: asks for a Python program and scores it without any model. Twelve families,
  each with an instance generator, a trivial answer and a cost; quality is
  `1 - cost / cost of the trivial answer`. Six *development* families (bin packing, graph
  colouring, quadratic assignment, regression, weighted tardiness, travelling salesman) and
  six *held-out* families (clustering, job shop, multi-dimensional knapsack, maximum cut,
  sequence prediction, set cover) that no lineage sees. `genesis/improver_runtime.py`.
- **Improver**: a module defining `improve(task, lm, budget) -> str`. The seed
  (`genesis/improver_seed.py`, 40 lines) asks the model for a better program and keeps it
  when it scores higher.
- **The task "improver"**: the program asked for is an improver; its score is the mean
  quality of what it returns on ordinary tasks. An improver given this task with its own
  source as the initial program is improving itself; the same code does both.
- **Generation**: one such self-application. What comes back is the candidate. The host
  then runs parent and candidate on the same fresh development tasks with the same budget
  and promotes under a fixed rule. A promoted improver performs the next self-application.
- **Model**: Claude Haiku 5.5 for every lineage, reached only through the host, which
  counts requests: 6 per ordinary task, 150 for a self-application including everything
  the improver spends evaluating its candidates.
- **Boundary**: improvers and their programs run in containers without network; the score
  that counts is recomputed by the host in a fresh container on five instances per task
  that the improver never saw.

## What the model contributes and what the system contributes

Every improver after the seed is written by the model. The claim examined is therefore
not "without a model" but: *with the model and the budget held fixed, does the procedure
that uses the model get better, by its own action, at producing good programs and at
producing better procedures?* The model alone (one request) and the seed are the
references. A gain of a later improver over the seed at equal budget is a gain of the
procedure, since the model did not change.

## What would count as evidence, in order

1. **Chain**: at least three successive promotions in one lineage under the fixed rule.
2. **Transfer**: final improver against seed on the six held-out families, fresh tasks,
   equal budget, run once under its own preregistration.
3. **Recursion**: the final improver is better than the seed *at improving improvers*:
   both are given the same starting improver and budget, several times, and their outputs
   are compared on fresh tasks. Without this, a chain shows repeated improvement of an
   object, not improvement of the improving.
4. **Reproduction**: the same from two further lineages with other task numbers.
5. **Another model**: the final improver's gain over the seed holds with a different model.

Each is preregistered separately. 1 alone is a development result. 1 and 2 show an
improved procedure that generalises to unseen kinds of task. Only 1 to 4 together would
support "bounded recursive self-improvement of the improvement procedure, with a fixed
model, on tasks given as a program and a score". Nothing here can support more than that:
the model bounds what any procedure can reach, and tasks without a cheap exact score are
outside.

## Known weaknesses, stated in advance

- A candidate is chosen by its parent on four tasks, a noisy signal; the host's comparison
  on thirty tasks is what protects a lineage from lucky candidates.
- An improver must fit one model answer (4096 tokens): improvers cannot grow without bound.
- Two development families (bin packing, colouring) are nearly saturated by one request.
- The scoring runtime is readable inside the container; a program naming it is refused,
  and every promoted improver is read for attempts to reach hidden instances or to spend
  outside its budget. Any such attempt is reported, whatever the scores.
- The task families are classical; solutions may be in the model's training data. This
  affects levels, not the comparison between improvers that use the same model.

## Pilot (apparatus check, not evidence)

Two tasks per development family, numbers 9000 and 9001, never reused: one request to the
model 0.48 mean quality; the seed improver 0.59. USD 0.30 including a first pass made
before a scoring fault was fixed (programs containing an ordinary `__main__` guard were
refused).

## A second channel and a second model

Lineages after SELF1 may reach a model through the Codex client under a subscription
(`genesis/improver_codex.py`, `scripts/run_codex_improver_lineage.py`): `gpt-6.1-sol`, low
reasoning effort, one read-only run in an empty directory per request. The channel is
looser than the metered one: answer size, temperature and system prompt are the client's,
and requests are bounded per day (300), not priced, so a generation spans days and resumes
from what is stored. Such a lineage has its own plan and its own model throughout; it
serves as reproduction (point 4) and as the other model (point 5), never as a continuation
of a lineage begun on another model. Apparatus check, tasks numbered 9002: the seed scored
0.84 on travelling salesman and 0.16 on quadratic assignment, about 55 seconds and 18,000
tokens per request.

## Reproduction

```
python3 scripts/run_improver_lineage.py plan --name SELF1
python3 scripts/run_improver_lineage.py generation --name SELF1 --workspace W
```
