# L9 archive operations and L10 independent handoff — 1 October 2026

**L9 open-endedness and L10 independent replication are not passed.** V31 adds
a positive finite archive-operations precursor around unchanged G7, not an
acquired G8 or a new causal recursive transition. This is Track B engineering;
the qualified L6–L8 Track A results remain unchanged.

## Original evidence and prospective chronology

| Stage | Commit or artifact |
|---|---|
| Initial apparatus and complete negative public pilot | `6717c354e2c75df3cfe3f1b5ecbcab44e53cc7f8` |
| Bounded retrieval and second complete public pilot | `f2e9cc4e82ec34e507548bbc226352b6edf8979c` |
| Separate prospective freeze, before any fresh execution | `ea655374fc4c2188374230902cf0cb4d1904d88e` |
| Original raw evidence, verdict and stale completion index | `f8804aacc29c154fb53882f03450baea358eb2ed` |
| Full 228-input manifest | `experiment/rsi_v31/V31_SCIENTIFIC_FREEZE.json` |
| Original, lossless raw population and exact journals | `results/rsi-v31/archive-20261001/V31_ATTEMPT_RAW.json.gz` |
| Preserved original precompletion index | `results/rsi-v31/archive-20261001/V31_PRECOMPLETION_INDEX.json` |
| Explicit metadata-only finalization provenance | `results/rsi-v31/archive-20261001/V31_INDEX_FINALIZATION.json` |

G7 remains byte-exact, SHA256
`2e43fde55b4d17f9ab48be14322acb3d7f65dec8d3663cde068837d6d68b9ff4`.
Freeze SHA256:
`676c64ff8e422cee2c15a5305f631db7b69b73e60242a6909f0b5bcb0d1df51d`.
Python 3.12.14. Zero external scientific model calls. Anthony Mets directs the
work; OpenAI Codex provides AI development assistance.

## Complete fresh comparison

Three predeclared seeds, four windows and 48 tasks per seed give 144 tasks for
each arm. Each receives G7, 12 candidate requests, eight rounds, parallelism two,
depth three and one separately charged identity-root probe per task. Old sources
are re-evaluated at full cost when retrieved. All failures and both complete
public development pilots remain available. Public iteration improved retrieval
after an initial regression; it did not establish an archive advantage.

| Arm | Solved / 144 | Newly observed solving sources | Charged evaluations |
|---|---:|---:|---:|
| Retain branches, retrieve up to two recent champions | 99 | 26 | 1,309 |
| Greedy retrieval of one last matching champion | 92 | 23 | 1,282 |
| Cold start, retrieve none | 105 | 32 | 1,268 |

The archive beats the greedy controller on coverage but loses to cold start on
both coverage and cost. This is a valid negative **search-advantage comparison**
inside a positive **operational archive assay**. It is not evidence that archive
growth improves recursive discovery efficiency.

## Growth, branching, recovery and rediscovery

| Seed | Archive semantic sizes, windows 1–4 | New solutions per 1,000 evaluations, windows 1–4 |
|---|---|---|
| 9143 | 20, 47, 72, 91 | 60, 15, 19, 9 |
| 27189 | 18, 38, 57, 78 | 22, 16, 17, 17 |
| 40733 | 21, 45, 65, 89 | 53, 8, 8, 7 |

Every fresh seed retains branching executable descendants and grows in each
window. Rotation, XOR and affine family-width combinations increase from three
to twelve inside one finite transducer domain. This is not twelve independent
software domains. The rates are positive over these measured windows and decline
substantially on two seeds. A finite positive rate cannot establish an
asymptotic rate or open-endedness. The contained width domain is explicitly 2–64.

The canonical rediscovery metric counts a previously observed source that now
solves the current task after a gap; it includes formerly partial proposals.
A stricter, separately labelled post-hoc diagnostic counts rediscovery of sources
that had already solved an earlier task: 16, 16 and 17 events on seeds 9143,
27189 and 40733. This diagnostic changes no frozen threshold or verdict.

Each canonical stream stopped after six completed tasks and resumed by loading
the exact ledger from disk. The complete public pilots also compare interrupted
and uninterrupted journal bytes. All canonical choices replay against original
receipts. A mid-task interruption reserves all 13 evaluations and fails closed;
it does not offer a free retry. Hash chains require an externally retained head
to detect whole-chain rewriting. No kernel sandbox or arbitrary hostile host-code
security guarantee is claimed.

## Completion-index fault and transparent finalization

The original computation and adjudication completed, but the persisted index
remained at the immediately preceding `STARTED` checkpoint. The strict reader
correctly rejected that mismatch. Its root cause has not been established.
The original state is preserved in commit `f8804aacc29c154fb53882f03450baea358eb2ed`
and `V31_PRECOMPLETION_INDEX.json`.

Finalization reconstructs that exact preceding checkpoint, including its original
gzip hash, from the completed payload with **only** its top-level status returned
to `STARTED`. It then writes the intended completion index atomically. The raw
compressed evidence and stored scientific verdict stay byte-exact; no candidate
is re-evaluated, selected or rerun, no scientific input changes, and there is no
second canonical attempt. The provenance checker binds the original Git bytes
and fails on modifications to the old index, new index, payload, verdict or debt.
This is a documented transport finalization, not a prospective protocol repair.

## L10 packet and remaining requirements

See [the independent handoff](../experiment/rsi_v31/L10_HANDOFF.md) and
[PROJECT_PIN.json](../results/rsi-v31/archive-20261001/PROJECT_PIN.json).
The pin fixes the exact checkout,
lineage, scientific manifest and runtime. Its checkout also contains the
completion-index failure and finalization provenance; verify
`python -m scripts.check_rsi_v31_transport_recovery` before external execution.
Pinned checkout: `6208b39fb3049bc5bfed07d3551f9f114ebf0c65`.
Project-pin SHA256:
`dbcddb7e54933b8349c1da45840fd951531248cf92f4df49b32fc86a916af43e`.

The implemented runner requires an externally signed private-bank commitment
before any execution, all three controls, complete tasks/negatives and exact
reproduction. Packet verification requires three separately configured external
roles and distinct keys, plus a signed adversarial audit. Blank templates assert
nothing. Private payloads and execution journals must stay outside this public
repository. Signatures authenticate configured keys; people must assess actual
identity, conflicts, independent authorship, rights and scientific scope.

No independent bank, reproducer or auditor has been received. The current adapter
handles finite bit transducers; materially broader independently maintained
evaluation still needs a prospectively reviewed adapter and external custody.
Neither CI, our fixture signatures nor this internal operational result can
substitute for M085/L10 independence. A sustained, externally governed L9
discovery programme and a real independent L10 evaluation remain open.

## Verification

```
python -m scripts.check_rsi_v31_transport_recovery
python -m experiment.rsi_v31.campaign check
python -m experiment.rsi_v31.independent readiness
python -m pytest -q tests/test_rsi_v31.py tests/test_rsi_v31_transport.py
```

The permanent V31 evidence workflow replays original receipts without fresh
candidate evaluation. Full project tests and the existing L6–L8 evidence workflow
also apply. Normal merge must preserve apparatus, freeze, original evidence and
finalization ancestry. `IP_ASSET_REGISTER.md` and `.github/workflows/ci.yml`
remain byte-exact.

The 36 targeted archive/trust/transport tests pass. An internal CLI rehearsal
uses 24 already consumed development tasks and three explicitly simulated roles
with separate fixture keys. Primary and reproduction reports match byte for byte
(digest `10443ee9c83d67d0cdaa40e6cf01a7e519cd75e7a73a5f0ae28f463111b8d4ba`),
and signed packet verification still returns `l10_independent_passed: false`.
This tests the handoff implementation, not real independent evidence.
