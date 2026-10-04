# V42 complete continuing-archive prefix — 4 October 2026

**Valid negative against the frozen continuing-archive criterion. L9 and L10 remain unpassed.**

The prospectively frozen eight-epoch prefix is complete: three seeds, four matched
arms and 468 tasks per arm, with all 1,872 episodes retained. V42 solves more tasks
at lower cost overall, but the third adaptive lineage remains one solved task
behind cold start and discovers no new solving behavior in its final epoch.

## Complete comparison

| Arm | Solved / tasks | Charged evaluations | New solving behaviors |
|---|---:|---:|---:|
| Adaptive V42 | 254 / 468 | 4,590 | 84 |
| Recency | 227 / 468 | 5,084 | 63 |
| Greedy | 232 / 468 | 5,191 | 66 |
| Cold start | 227 / 468 | 5,200 | 68 |

Adaptive solves 27 more tasks than cold start with 610 fewer evaluations
(11.73% lower cost). Those aggregate gains do not erase either failed predicate.

| Frozen predicate | Result |
|---|---|
| Complete initial eight-epoch prefix | Pass |
| Positive archive growth and new discovery in every seed/epoch | **Fail** |
| More solved tasks than cold start and greedy | Pass |
| Cost no greater than cold start | Pass |
| No individual seed regresses against cold start | **Fail** |

| Seed | Adaptive solved | Cold solved | Adaptive new solving behaviors by epoch |
|---|---:|---:|---|
| 86028121 | 91 | 73 | 3, 4, 4, 5, 5, 3, 2, 4 |
| 86028157 | 82 | 72 | 3, 4, 7, 9, 2, 2, 2, 2 |
| 86028193 | 81 | 82 | 3, 3, 4, 6, 4, 2, 1, **0** |

## Recovery and chronology

The earlier discussion had published epochs 0–5. Its workspace also held the
complete original epoch 6, including raw data, adjudication and completion receipt.
The takeover recovered those bytes and replayed all 288 epoch-6 episodes before
publishing them. It did not repeat that scientific epoch.

Epoch 7 ran once, after publication of the previous complete epoch, using the
frozen Python 3.11.16 runtime. All four arms, checkpoint recovery and complete
receipt replay finished before its completion receipt was published. The complete
raw epoch was committed before this interpretation and the aggregate prefix report.
The shared reservation was mirrored into the former workspace so that an attempted
duplicate execution would fail closed. No frozen apparatus, seed, budget,
threshold, negative result or earlier scientific input was changed.

Original evidence is in
[`results/rsi-v42/continuing-20261002/`](../results/rsi-v42/continuing-20261002/).
The authoritative report is
[`PREFIX_REPORT.json`](../results/rsi-v42/continuing-20261002/PREFIX_REPORT.json).
The prospective manifest remains
[`V42_SCIENTIFIC_FREEZE.json`](../experiment/rsi_v42/V42_SCIENTIFIC_FREEZE.json).

## Diagnosis and next boundary

In the last epoch of seed 86028193, the novelty frontier actually activated on
22 of 24 tasks, and both memory probes were charged. Nevertheless there were zero
new solving behaviors. Source and behavior archives grew, and five tasks were
solved, but those solutions reused behavior already present in the lineage. The
failure is therefore not explained simply by an inactive stagnation trigger.

The implementation considers the five most recent same-domain observations across
the retained history. Consequently activation can continue across window boundaries;
the original development prose's description of only a sixth/window-final task is
not a general description of later epochs. The frozen implementation and original
receipts remain authoritative and are not retrospectively repaired.

A successor must be developed on consumed data and address discovery after memory
saturation, rather than change a threshold or extend this negative prefix until an
aggregate becomes favorable. Development should retain all candidate variants and
compare them under the same external evaluation budget. New scientific evidence
requires a separate prospective apparatus, freeze and single-assignment attempt.

V42 is project-directed Track B engineering around byte-exact G7. It establishes no
new recursive G8 acquisition, independent task authorship, independent replication,
general RSI or AGI. Its four authored domains and fixed grammar/governance capacity
cannot prove open-endedness from this finite prefix. L10 remains deferred to the
separate external evaluation work requested by the project owner.

## Validation and reproduction

Every original epoch adjudication was reproduced with the frozen checker and
isolated receipt replay. Epochs 0–5 were independently replayed in separate
processes; recovered epoch 6 was replayed before publication; epoch 7's canonical
writer replayed all its receipts before completing. The aggregate report reproduces
from those eight complete original epochs.

The initial full Python 3.11.16 regression reported 5,314 passes, 11 skips,
32 failures and 20 setup errors. The fresh environment had installed dependencies
but not the project, so fresh interpreter subprocesses could not import its
packages. After editable installation and completion of the workflow inventory
update, all 83 tests in the affected modules and the six new evidence-gate tests
passed. The five frozen V42 boundary tests also passed. These are the complete
initial regression plus focused corrections, not a claim that a second full suite
or final-head GitHub CI has already run.

The permanent evidence workflow requires the entire prefix and report, and rejects
missing evidence, a forged positive verdict and finite-result promotion to L9/L10.
Superseded V39–V41 development workflows are archived without changing their bytes;
the fresh-run workflow now pins the exact already-frozen Python version.

```sh
python -m pip install -e '.[dev]'
python -m scripts.check_rsi_v42_evidence
python -m pytest -q tests/test_rsi_v42.py tests/test_rsi_v42_fresh.py tests/test_rsi_v42_evidence.py
python scripts/check_repository_integrity.py
python scripts/audit_repository_layout.py --check
```

Anthony Mets remains the sole human research director. OpenAI Codex supplied
substantial development, recovery, verification and documentation assistance as
tooling, with zero external model calls in the scientific experiment.
