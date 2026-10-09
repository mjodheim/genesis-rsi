# Outcome-driven repair improvement — 9 October 2026

Anthony asked to begin work explicitly towards RSI. Two prospectively frozen,
model-free development experiments were implemented and executed. They connect
existing exemplar acquisition to persisted policy descendants and an external
host-side promotion decision. No existing scientific protocol was changed.

## Results

| Development measurement | Parent | Descendant |
|---|---:|---:|
| Final model-free repair probes after three acquisition cycles | 0/9 | 9/9 |
| Final repair probes after search-order adaptation | 3/3 | 3/3 |
| Candidate validations for those three search probes | 12 | 3 |

The first experiment acquired offsets -1, +1 and -2 from production-source
examples in Python, JavaScript and Java. A successful training candidate proposed
an identifier-independent rule. Each child was compared to its parent on a
separate development selection set, including previous capabilities. All three
children achieved three additional task passes without a task regression and
were retained. The final policy was frozen before the nine final transfer
probes, which contained no fresh source exemplars. They establish functioning
cross-language parameter reuse inside this authored substrate.

Acquisition cost exposed a limitation: the three training repairs needed one,
two and three validations because retained rules preceded new observations.
The second experiment's authored diagnosis read only released training outcomes
and proposed a descendant search policy that prioritizes observations when
available. The set of admitted repair strategies remained fixed. Three separate
promotion tasks checked strict success/efficiency improvement and no regression;
the known-rule Java control remained one validation in both arms. The new policy
was admitted before final evaluation. Three subsequent probes passed in both
arms, with four validations each for the parent and one each for the descendant:
75% fewer candidate validations on these probes. Candidate pools were identical;
only ordering differed.

Both experiments made zero external LLM calls and incurred $0 API spend.
Infrastructure, electricity and development effort are excluded. Real Python,
Node.js and Java runtimes executed candidates in disposable Docker containers
with a pinned local image ID, no network, read-only task mounts/root, cleared
environment, nonroot user and resource ceilings. These flags are recorded as
requested isolation; this experiment does not include an independent kernel or
container-boundary audit. Expected outputs were compared by the host rather
than accepting a success flag from candidate code.

## Evidence and limits

- [Acquisition protocol](../experiment/bench/DEV_REPAIR_SELF_IMPROVEMENT1/PLAN.json)
  and [result](../experiment/bench/DEV_REPAIR_SELF_IMPROVEMENT1/RESULT.json).
- [Search-adaptation protocol](../experiment/bench/DEV_REPAIR_SEARCH_ADAPTATION1/PLAN.json)
  and [result](../experiment/bench/DEV_REPAIR_SEARCH_ADAPTATION1/RESULT.json).
- Per-task candidate sets were sealed before validation; every attempt,
  parent/child comparison and policy is retained alongside the aggregate result.
  Source snapshots are preserved outside the repository in each experiment's
  workspace. Digests provide integrity, not author/evaluator authentication.
- An invalid offset was caught during preparation of the second protocol,
  before any task execution or sealed protocol existed. The error and correction
  are retained in `DEV_REPAIR_SEARCH_ADAPTATION_PREPARATION_ERROR_20261009.json`.

All exercises, test vectors, acquisition substrate, diagnosis and the two
available search orderings are project-authored. Selection and final tasks
share a narrow subscript-offset family and closely related source structures;
final outcomes are development probes, not independent blind evidence.
Acquiring an offset and transferring it is not invention of a new semantic
primitive. Choosing a better authored ordering is bounded search-policy
adaptation, not unrestricted self-rewriting. General RSI is not demonstrated.
These opt-in development controllers do not replace the canonical Genesis
runtime or promote exercise-derived policies into its production lineage.

Focused regression validation passed 91 tests; one live Defects4J integration
test was skipped because its dedicated image is unavailable locally. The
multilingual experiments used the separately available pinned executor image
and ran successfully. Repository orphan, dependency and citation checks pass.
Posthoc verification independently recomputed the recorded grades of 69
evaluations and 102 candidate attempts from container outputs and confirmed
equal candidate pools in all six search-order comparisons. This verification
checks stored evidence, not independent execution replication.

## Next research step

Use the same parent/descendant gate on released real-project tasks, with multiple
bug families and a genuinely separated final task set. Expand the mutable search
mechanisms only when results identify a specific limitation. Compare whether a
descendant improves the next improvement cycle, including its failures, total
validation effort and API spend. New-rule invention requires additional evidence
beyond this finite parameter and ordering space. Reserved benchmarks and
external-maintainer scientific gates retain their original boundaries.
