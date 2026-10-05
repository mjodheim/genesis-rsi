[Reading 80 lines from start (total: 80 lines, 0 remaining)]

# V52 — abstraction memory and prospective sustained assay

V52 follows V51's structured experimental memory. V51 showed that persistent,
scored memory can beat cold at lower cost, but at least one late window reached
zero first discoveries. Post-merge diagnosis showed the remaining ceiling was not
storage alone: on one width-10 window even the cold G7 search failed all twelve
tasks despite simple single-bit and rotation targets.

## Development selection (consumed V51 population)

All V52 policy choices below were made on the already-consumed V51 development
seeds 510051, 510052 and 510053. None of those outcomes may count as V52 fresh
evidence.

V52 distils successful executable genomes into cross-width recipes. Development
tested low-edge, high-edge, scaled, rotation and mask variants. Broad recall was
harmful: top-k 4 and 6 overloaded candidate ordering. A single recalled
abstraction was best. Restricting abstraction to tasks where exact V51 memory had
no compatible successful recall further reduced interference.

The selected mechanism is therefore frozen as:

- exact structured V51 memory remains available;
- at most one cross-width abstraction is exposed per task;
- abstraction is exposed only when exact memory has no compatible successful hit;
- all recipe modes remain eligible; no target/family label selects a mode;
- recipe ranking uses only already-observed root quality, historical support,
  historical utility and source-width distance;
- if an evaluated abstraction does not improve quality over the matched V51
  baseline, its utility receives a strong negative update so a later task explores
  another recipe;
- evaluator, G7 policy, mutation depth and 14-call task cap are inherited unchanged.

On the consumed 288-task V51 population this final policy kept first-discovery
count positive in every window of all three seeds, while using fewer evaluations
than V51. This is development evidence only.

## Prospective population

Before any V52 prospective behavioral execution, source commits:

- seeds 520051, 520052 and 520053;
- twelve windows per seed;
- twelve tasks per window;
- widths 3 through 14;
- 432 total tasks;
- the complete deterministic generator and population digest.

Every task is matched across four arms:

1. V52 exact + abstraction memory;
2. V51 exact structured memory ablation;
3. V32 adaptive archive;
4. cold start.

All negative tasks, zero-discovery windows and costs are retained.

## Frozen scoped acceptance rule

The finite prospective V52 assay is positive only if all are true:

1. all 432 committed tasks are present;
2. every one of the 12 windows on every seed has at least one first discovery
   under V52;
3. V52 solves at least as many tasks in aggregate as V51;
4. V52 solves strictly more tasks in aggregate than cold;
5. V52 uses no more charged evaluations in aggregate than V51;
6. V52 does not solve fewer tasks than cold on any seed;
7. abstraction recall and its feedback path are actually exercised.

A failed predicate is retained as a valid negative result. No seed, window,
recipe mode, cap or threshold may be changed after the first prospective run.

## L9 boundary

Even a positive result is a **scoped sustained abstraction assay**, not general
L9. The population is finite, project-authored and remains inside the bounded bit
transducer grammar. General L9 still requires evidence that the positive discovery
process survives materially broader task diversity under fixed external
governance; L10 independently maintained replication remains separate.

[executed on device: Mjodheim-Ubuntu-cx33 (915d6eb6-54f1-400c-8c12-a1e043b0a356)]