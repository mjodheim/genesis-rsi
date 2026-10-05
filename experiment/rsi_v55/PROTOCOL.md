# V55 — feedback-driven diagnostic exploration — prospective protocol

V55 follows the positive V53 scaffold mechanism and the negative V54 recursive
refinement development. Its purpose is to address the remaining late-window
coverage failure without increasing the external task budget and without using
the hidden target.

## Frozen mechanism

The V55 successor retains V53 exact memory, abstraction memory and scaffold
behavior except when a strict diagnostic gate opens.

The gate opens only when:

1. current width is at least 10;
2. no compatible exact-memory strategy is retrieved;
3. the externally observed root quality is exactly consistent with a
   rotation-zero mask differing in one or two bits.

When active:

- speculative V52/V53 cross-width memory is suppressed for that task;
- the planner infers only the number of differing mask bits from root quality;
- all one-bit or two-bit masks consistent with observations are maintained as
  hypotheses;
- the next probe is selected only from candidate-local structure to minimize
  the largest hypothesis bucket;
- scalar quality from each evaluated probe determines the observed intersection
  count and filters the hypothesis set;
- once one hypothesis remains, that mask is emitted as the diagnostic solution;
- non-root branches are withheld during diagnosis so G7 cannot spend the
  inherited fixed budget on an unrelated parallel branch.

No target value, expected output, task family, hidden task identifier, future
quality, or prospective result enters the planner.

The inherited limits remain unchanged:

- G7 source unchanged;
- 12 search requests;
- 8 rounds;
- parallelism cap 2;
- mutation depth 3;
- maximum charged task evaluations 14.

## Pre-freeze development evidence

Selection used only the already-consumed V53 prospective seeds
530061/530062/530063.

Matched development aggregate:

- V53: 191 / 504 solved, 5,538 evaluations;
- V55: 251 / 504 solved, 5,004 evaluations;
- +60 solved tasks;
- 534 fewer evaluations;
- 42 diagnostic routes;
- 42 / 42 diagnostic tasks solved;
- 0 diagnostic aborts;
- 30 direct solve gains vs V53;
- 0 direct solve regressions vs V53;
- every consumed seed/window positive.

Exhaustive planner checks before freeze:

- every 1-bit and 2-bit mask at widths 10–16 is uniquely identified in at most
  6 probes;
- every 1-bit and 2-bit mask at widths 17–23 is uniquely identified in at most
  7 probes;
- width 24 contains 4 cases that exceed the eight-round horizon.

No parameter is tuned beyond this point.

## Fresh prospective population

The prospective population is committed before execution:

- seeds 550071, 550072, 550073;
- 18 windows per seed;
- widths 3 through 20;
- 12 tasks per window;
- 216 tasks per seed;
- 648 tasks total;
- deterministic generator and population digest.

The new horizon extends four windows beyond V53.

Every task is matched across:

1. V55 feedback-driven diagnostic successor;
2. frozen V53 scaffold baseline;
3. V51 structured-memory baseline;
4. cold G7 search.

## Frozen scoped acceptance predicates

The finite prospective V55 assay is positive only if all predicates hold:

1. all 648 committed tasks are retained;
2. every one of the 18 windows on every seed has at least one first discovery;
3. V55 solves strictly more tasks in aggregate than V53;
4. V55 solves strictly more tasks in aggregate than cold;
5. V55 uses no more charged evaluations in aggregate than V53;
6. V55 does not solve fewer tasks than cold on any seed;
7. diagnostic routing is exercised on every seed;
8. no diagnostic route aborts;
9. every task on which diagnostic routing activates is solved;
10. diagnostic routing causes no direct solve regression vs V53;
11. new horizon windows 14, 15, 16 and 17 retain positive first discovery on
    every seed.

A failed predicate is retained as a valid negative result. No seed, threshold,
query pool, diagnostic rule, width bound, top-k, round limit or evaluation cap
may change after the first prospective behavioral execution.

## L9 claim boundary

Even a positive V55 result is a **scoped finite sustained diagnostic assay**.
The population remains project-authored and inside the bounded bit-transducer
grammar. Therefore V55 cannot by itself establish general open-ended L9.

A positive result would establish that the remaining V53 exhaustion was caused
by fixed-budget exploration bias and that target-blind feedback-driven
self-diagnosis can preserve discovery across a materially longer frozen horizon.
The next L9 step would then move this governance to materially different task
grammars or an externally sourced task stream.
