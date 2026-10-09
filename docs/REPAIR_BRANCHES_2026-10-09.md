# Case-local repair branches: implementation and development pilot

The branch substrate is implemented, but this pilot demonstrates no repair gain.
DEV_REPAIR_BRANCHES1 repaired Mockito-17 and Jsoup-54 in both repetitions and
failed Mockito-23 in both repetitions, in both arms. No branch was extended.

## Authored mechanism and validation

Codex implemented the project-controlled mechanism under Anthony Mets's direction,
following the recorded public IP review. A candidate can name a host-graded
earlier candidate as its parent, inspect that parent's virtual source and submit
incremental edits. The complete inherited correction is reconstructed and graded
from the original checkout; partial hypotheses are never treated as verified
repairs. Production files only, at most three changed files, and restoration of
original bytes remain enforced. Defaults preserve the prior interface.

One hundred focused tests passed before freezing the pilot, including virtual
reads, cumulative edits, invalid parents, file limits, joint validation and byte
restoration. Repository integrity checks passed. These are authored capabilities,
not primitives invented or improvements learned by Genesis.

## Frozen comparison

The pilot froze at commit `5c0396d5`. Both arms used application feedback,
multi-file submissions, the same Haiku model and a common manually authored
allocation of four rounds, one inspection request and one candidate per round.
The child additionally exposed branch parents and virtual reads. This common
allocation permits sequential revisions within eight requests; it differs from
earlier pilots and prevents attributing historical differences solely to branches.

Three previously exposed Java bugs were repeated twice with alternating arm order.
The API ceiling was USD 0.20; actual receipts cover all 36 calls. No reserved cases,
fixed revisions or canonical memory writes were used. Frozen source digests and
the container image identity are retained in the plan.

| Arm | Repaired | Requests | Validations | Inapplicable | API cost USD | Arm seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Without branches | 4/6 | 20 | 10 | 1 | 0.022424200 | 444.7 |
| With branches | 4/6 | 16 | 7 | 2 | 0.021433925 | 341.7 |

Total API cost: **USD 0.043858125**, with no unknown-cost calls. Time excludes
baseline preparation and is not a priced infrastructure estimate. The lower
child cost partly reflects an early failed submission; it is not evidence of
superior successful-repair efficiency. Verification checks receipt consistency,
digests, budgets and graded-parent eligibility, not independent replication.

## What failed and what was exercised

The child submitted valid one-, two- and three-file candidates, exercising joint
validation for the first time in these pilots. Every applicable child proposal
started from the original tree (`parent=""`); no virtual branch read or inherited
extension occurred. Therefore this does not measure the effectiveness of actual
branch continuation.

On Mockito-23 repetition one, child exceptions moved from `DelegatingMethod` to
`DelegatingMockitoMethodProxy`, then remained there after a three-file candidate.
This does not establish that the partial edits are correct. The fourth submission
proposed propagating the parent's serialization setting but omitted the required
parent field and was rejected. No claim that this unvalidated proposal would
solve the bug is justified. The parent also submitted a null file layout.

On repetition two, the child's first proposal tried to add `Serializable` to
`GenericMetadataSupport`, using search text that omitted its existing
`implements Serializable`. A read-only inspection of the restored buggy source
confirmed that the class already implements it. The final submission was
inapplicable and exhausted that round's planned requests; the host stopped with
zero validations. This is a hypothesis and exact-edit failure, not a 404 or an
interrupted run.

Next development should teach evidence-backed selection of an archived parent,
inspection of its virtual source and revision of causal hypotheses when exception
chasing stalls. A settings-based cause remains a hypothesis. More plumbing alone
has not demonstrated improved problem solving. Executable solver/improver
evolution and transfer remain unproven; general RSI has not been achieved.

No policy was promoted. Canonical memory remains at 292 events; successful
patches, failed attempts, costs and diagnoses are retained in trial artifacts,
without representing them as newly learned canonical procedures. All production
checkout trees were verified restored.

Artifacts: [plan](../experiment/bench/DEV_REPAIR_BRANCHES1/PLAN.json),
[result](../experiment/bench/DEV_REPAIR_BRANCHES1/RESULT.json),
[journal](../experiment/bench/DEV_REPAIR_BRANCHES1/JOURNAL.json),
[verification](../experiment/bench/DEV_REPAIR_BRANCHES1/VERIFICATION.json),
[diagnosis](../experiment/bench/DEV_REPAIR_BRANCHES1/DIAGNOSIS.json),
[baselines](../experiment/bench/DEV_REPAIR_BRANCHES1/BASELINES.json).
