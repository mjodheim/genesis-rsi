# V32 — useful archive ranking, negative adaptive-selection qualification

V32's frozen primary verdict is **`VALID_NEGATIVE_FINITE_MEMORY_USEFULNESS`**.
Adaptive retrieval solves 138/216 fresh tasks versus cold 135/216, using 2,005
versus 2,195 charged evaluations (8.7% fewer). It loses to always retrieving the
closest two (141/216) and most-recent-two (139/216). The acquired G7 selector's
new use is therefore not qualified by the precommitted comparison. All negatives
remain recorded; this result is not permission to tune or repeat the attempt.

**Bounded L6–L8 remain positive. Open-ended L9 and independent L10 remain unpassed.**
This is project-directed Track B archive apparatus around unchanged G7, with no
new acquired G8, independent task authorship, general RSI or AGI claim.

## What changed and how it was frozen

V31 kept every branch but proposed the two most recently successful programs.
Post hoc diagnostic evaluation on that consumed population found 120 of 252
proposals worse than the current identity root, with no exact solutions among
those proposals. These counterfactuals are development diagnostics, not additional
fresh observations.

V32 records the identity-root quality observed on each past task that a program
solved. It ranks stored successes by the nearest such quality to the current
revealed identity quality, then recency, success count and source hash. The
adaptive arm uses byte-exact G7's acquired `select_target` to retrieve two when
that distance is <=25 milli-points and choose cold generation otherwise. This
diagnostic mapping and retrieval machinery are human-directed engineering. They
were not learned by G7. Scalar similarity can alias different tasks.

The policy decisions receive only the permitted measured diagnostics, revealed
qualities and static candidate descriptors. They receive no hidden target, input
pairs, task name, family label or future quality. Pure candidate transforms are
executed on the task inputs by the external evaluator, as required to evaluate
their behavior. Every arm performs an isolated controller call and identity probe,
plus at most twelve candidate evaluations: maximum fourteen charged evaluations,
eight rounds, parallelism two and mutation depth three. All actual search policies
and transducer sources use unchanged G7, SHA-256
`2e43fde55b4d17f9ab48be14322acb3d7f65dec8d3663cde068837d6d68b9ff4`.

All eight tolerances and four controls over all 240 consumed V31 tasks are retained
in [the complete development archive](../experiment/rsi_v32/DEVELOPMENT.json.gz).
The declared selection rule chose 25, with 180/240 development solves versus cold
173/240. V31's formerly fresh tasks are explicitly consumed development here.
These outcomes did not establish a new gate.

The exact apparatus was committed at
`14131340299001127702e94cd5d2e7b90657bc4b`, then all 250 scientific inputs,
selected tolerance, controls and the new population were frozen in commit
`ac848e7320be6197d291a3276af3fb887ef057a9` before first fresh behavior.
[The freeze](../experiment/rsi_v32/V32_SCIENTIFIC_FREEZE.json) has digest
`a48bb0976f5b732fed8394f6f119627a1c46225dad7f8a0df25657a0f69cea22`.
See [the frozen protocol](../experiment/rsi_v32/PROTOCOL.md).

## All fresh results

One canonical attempt, Python 3.12.14, seeds 72859, 109987 and 154873. Each arm
gets all 216 tasks: six windows of twelve tasks per seed, widths 3 through 8.
XOR, rotation and affine transformations remain one finite bit-transducer domain.
Repeated target semantics deliberately permit rediscovery; new task bytes do not
imply new semantics or independent task authorship. Each seed/arm starts empty.
There are zero external scientific model calls.

| Arm | Solved / 216 | Sum of best quality (milli) | Newly observed solving sources | Charged evaluations |
|---|---:|---:|---:|---:|
| Adaptive G7 routing | 138 | 189,541 | 41 | 2,005 |
| G6 selector removal; always closest-two | **141** | **190,581** | 43 | **1,970** |
| Fixed most-recent-two | 139 | 189,868 | 41 | 2,240 |
| Fixed closest-one | 134 | 188,629 | 40 | 2,034 |
| Fixed cold generation | 135 | 188,703 | 45 | 2,195 |

The selector-removal controller is exact G6: absence of `select_target` defaults
to identity, mapped prospectively to closest-two retrieval. The actual search
still uses G7. This isolates use of the acquired selector for the new routing
purpose rather than replacing the inherited search mechanism.

| Seed | Adaptive solved / cost | Closest-two solved / cost | Recency solved / cost | Closest-one solved / cost | Cold solved / cost |
|---|---:|---:|---:|---:|---:|
| 72859 | 42 / 694 | 44 / 679 | 41 / 758 | 43 / 694 | 41 / 767 |
| 109987 | 46 / 666 | 48 / 656 | 48 / 748 | 45 / 661 | 44 / 712 |
| 154873 | 50 / 645 | 49 / 635 | 50 / 734 | 46 / 679 | 50 / 716 |

The primary criterion required adaptive to solve strictly more tasks than **every**
control, cost no more than cold, avoid solved-task regression against cold on every
seed, exercise both routes, and verify complete evidence/caps/recovery/replay.
Only the strict all-control solved advantage failed. The other four predicates
passed. Adaptive used memory on 96 tasks and cold generation on 120.

Paired comparison with cold contains four adaptive-only solves, one cold-only
solve, 134 both-solved and 77 neither-solved. Against closest-two there are three
adaptive-only solves and six control-only solves. These observations support a
small finite advantage over cold and a failure of the stronger adaptive claim;
they are not estimates of broad-domain performance or independent replication.

Always closest-two, the predeclared control, achieves two more solves than recency
with 270 fewer evaluations (12.1%). That is evidence that the new ranking can help
this finite population. It is not an acquired G8 and is not a post-outcome promotion
of that control to a qualified successor.

## Growth and discovery limits

Archive semantic size grows in every measured window. Newly observed solving
sources stay positive, but discovery rates fall as the population grows:

| Seed | Semantic archive sizes, windows 0–5 | New solving sources per 1,000 charged evaluations, windows 0–5 |
|---|---|---|
| 72859 | 17, 38, 65, 87, 115, 132 | 34, 33, 25, 6, 7, 8 |
| 109987 | 18, 37, 61, 89, 111, 133 | 54, 30, 17, 18, 7, 8 |
| 154873 | 14, 40, 62, 82, 100, 120 | 57, 25, 30, 15, 16, 8 |

"New solving source" means an exact source not previously observed, including as
a partial candidate. The retained rediscovery metric also includes previously
observed partial programs later solving a task. Neither metric establishes
unbounded novelty, cross-domain diversity or sustained open-ended discovery.
Cold produces more newly observed solving sources than adaptive (45 versus 41).
Lower finite cost is not proof that memory improves the ability to discover later
improvement machinery.

## Original evidence, durability and verification

The complete original raw evidence was committed at
`7ad05ae0d35b9a066ab04e7a5da9b8e9a72adca7` before this analysis. It retains every
episode, negative, decision, evaluation receipt and complete journal for all
fifteen seed/arm streams. [The raw archive](../results/rsi-v32/memory-20261001/V32_ATTEMPT_RAW.json.gz)
is 7,205,680 bytes, SHA-256
`6b9c0798bab2853f7f90af45e22298ae713ee56c4ae437153c5bbf329e92ee06`.
See [the full adjudication](../results/rsi-v32/memory-20261001/V32_FINAL_ADJUDICATION.json),
[immutable reservation](../results/rsi-v32/memory-20261001/V32_RESERVATION.json) and
[separate completion receipt](../results/rsi-v32/memory-20261001/V32_COMPLETION.json).

The new writer never overwrites a reservation or result. It publishes files
atomically without replacement, fsyncs them and their directory, reads back the
bytes, then publishes completion last. Every stream stopped after task six and
reconstructed history from disk; pending tasks remain quarantined with their full
reserved cost. All 1,080 episodes passed isolated policy/selector receipt replay
and external evaluator-math verification before completion. Replay repeats
decisions using original receipts; it is not fresh evaluation or independence.
V31's original completion-index failure and its transparent metadata-only recovery
remain intact, along with every inherited scientific input and negative.

The 23 targeted tests cover hidden-information and authority limits, the precise
selector ablation, equal costs, byte-exact boundary recovery, tamper rejection,
single-assignment publication and incomplete-attempt refusal. The permanent V32
workflow verifies retained evidence and its negative verdict without launching a
new scientific attempt. Repository integrity and layout were checked during
preparation. Full regression and final CI outcomes are recorded on the PR.

Reproduce the evidence check without consuming another attempt:

```sh
python -m experiment.rsi_v32.campaign check
python -m pytest -q
python scripts/check_repository_integrity.py
```

## What remains for L9 and L10

The finite ranking result helps identify the next problem: a scalar compatibility
proxy is not sufficient evidence for choosing when to abandon memory. Any new
diagnostic, learned selector, grammar extension or fresh assay belongs in V33+;
V32 may now be used only as consumed development and retained evidence.

L9 still needs a growing, diverse descendant process with demonstrated continuing
discovery beyond a fixed finite apparatus. L10 still needs real external task
authorship/custody, independent reproduction and adversarial audit. No external
participant or private independently authored bank has been received. The
[unchanged V31 external packet](../experiment/rsi_v31/L10_HANDOFF.md) remains
pinned to its exact V31 apparatus and G7; it does not silently validate V32 routing.
Actual identity, scope and the contributor-rights boundary must be respected.
Project-controlled code, CI, AI agents or simulated signatures cannot fill those
roles or establish general RSI.
