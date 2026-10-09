# Repair evidence consistency: strict-quote regression

The first evidence-checking pilot regressed: reference 4/6 repairs, checked
child 0/6. This negative result is preserved; no policy is promoted.

Codex, under Anthony Mets's direction, implemented opt-in mandatory evidence
records: current host failure signal, assessment of the preceding prediction,
one to three source facts, concise causal explanation and prediction. The host
checks the signal and assessment, exact quoted production lines in the selected
virtual tree, and whether a term is present or absent in each quoted line.
These are literal consistency checks, not semantic proof of causality.
Existing generation and external compiler/trigger/full-suite criteria remain.

DEV_REPAIR_CAUSAL_EVIDENCE1 froze at `2dee7ca8` after 113 focused tests passed.
Both arms use the same evidence-driven playbook, branch tools, model and four-round
allocation; only child evidence checks are mandatory. Three exposed Java bugs,
two repetitions, alternating order, USD 0.20 ceiling. No fixed revisions,
reserved cases or canonical memory writes. Source hashes and image identity
were fixed before calls; no machinery changed during the trial.

| Arm | Repaired | Calls | Validations | Evidence rejections | API cost USD | Arm seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 4/6 | 20 | 9 | 0 | 0.025986175 | 441.9 |
| Strict checked child | 0/6 | 18 | 4 | 7 | 0.028554075 | 275.0 |

All 38 calls have receipts: **USD 0.054540250**. Time excludes baseline
preparation; costs exclude infrastructure. Verification checks receipt/digest
consistency, budgets, earlier graded parents and prediction observations against
verdicts, not independent replication.

On both Mockito-17 and Jsoup-54 repetitions, quoted content matched the correct
source line after stripping boundary whitespace. Requiring indentation in a
citation rejected these proposals before patch validation. This is a defect in
the authored interface, not evidence that their patches would necessarily pass.
The exact payloads are retained; any subsequent acceptance or validation must be
reported separately and cannot replace the historical failures.

Mockito-23 repetition one passed the evidence gate for four candidates, all
failing the trigger test. Exceptions alternated between `ReturnsDeepStubs$2`
and `MockUtil`. Literal consistency did not establish correct causality. Its
second repetition stopped on a source-quote mismatch. See the per-fact diagnostic
for matching lines rather than assuming every mismatch is only indentation.

The prospective correction is to tolerate boundary whitespace in citations while
retaining exact content, line number, selected tree and literal term checks.
Search/replace patch applicability stays exact. That correction and its next
comparison are separate from this frozen result. All production trees were
verified restored; canonical memory remains 292 events. No general RSI is shown.

Artifacts: [result](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE1/RESULT.json),
[diagnosis](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE1/DIAGNOSIS.json),
[verification](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE1/VERIFICATION.json).
