# V53 — selective learned-component scaffolds

V53 follows the valid negative V52 prospective abstraction-memory assay. V52
improved solved count and cost versus V51, but late windows still reached zero
first discovery on two prospective seeds.

## Development selection

All V53 policy choices were made only on the already-consumed V52 prospective
seeds 520051, 520052 and 520053. Those outcomes are development evidence only.

Direct injection of several completed cross-parent affine compositions was tested
and rejected because it interfered with the inherited G7 ordering. The selected
mechanism is narrower: reuse a learned rotation abstraction as a **search
scaffold**, then let the unchanged G7 neighborhood complete the candidate.

The frozen policy is:

- V51 exact structured memory remains authoritative;
- V52 one-recipe cross-width abstraction remains the default;
- scaffold routing opens only when current width is at least 10 and the
  already-observed root quality is at most 799 milli-quality;
- at most two historical rotation recipes are exposed as scaffolds;
- a scaffold may be reused even when its whole-recipe V52 utility is negative,
  because component utility and complete-solution utility are distinct roles;
- scaffolds are disabled whenever compatible exact memory is available;
- when scaffolds are exposed they replace, rather than add to, simple V52
  abstraction at the root;
- no current target output or current task family label enters scaffold ranking;
- evaluator, G7 source, mutation depth and 14-call task cap are inherited
  unchanged.

Matched development replay over the consumed 432 V52 prospective tasks:

| Seed | V52 solved | V53 solved | V52 evals | V53 evals |
|---|---:|---:|---:|---:|
| 520051 | 52 | 52 | 1648 | 1648 |
| 520052 | 56 | 59 | 1596 | 1565 |
| 520053 | 56 | 61 | 1571 | 1526 |
| **Total** | **164** | **172** | **4815** | **4739** |

The mechanism therefore gained 8 solved tasks while using 76 fewer charged
evaluations. It did not eliminate every zero-discovery window, so this is not L9.

## Fresh prospective population

Before any V53 prospective behavioral execution, the repository commits:

- seeds 530061, 530062 and 530063;
- fourteen windows per seed;
- twelve tasks per window;
- widths 3 through 16;
- 504 total tasks;
- deterministic generator and population digest;
- apparatus hashes and frozen thresholds.

The horizon is deliberately longer than V52's 12 windows.

Every task is matched across V53, frozen V52, V51 structured memory, V32 archive
and cold G7 search.

## Frozen scoped acceptance predicates

The finite V53 assay is positive only if all are true:

1. all 504 committed tasks are retained;
2. every one of the 14 windows on every seed has at least one first discovery;
3. V53 solves strictly more tasks in aggregate than V52;
4. V53 solves strictly more tasks in aggregate than cold;
5. V53 uses no more charged evaluations in aggregate than V52;
6. V53 does not solve fewer tasks than cold on any seed;
7. scaffold routing is exercised on every seed;
8. the new horizon windows 12 and 13 retain positive first discovery on every
   seed.

No seed, threshold, width gate, top-k or task budget may change after the first
fresh behavioral execution. Negative results are retained.

## L9 boundary

Even a positive finite V53 assay is not general open-ended L9. The population is
project-authored and remains inside the bounded bit-transducer grammar. A positive
result would establish sustained learned-component scaffolding over a longer
frozen horizon, after which general L9 would still require materially broader or
externally sourced task diversity under the same governance.
