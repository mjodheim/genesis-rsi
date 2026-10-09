# Evidence-checking citation correction: prospective result

After preserving the strict-quote regression, the citation interface was
corrected and measured prospectively. Both versions repair 2/3 cases; no
repair gain is demonstrated and Mockito-23 remains unresolved.

Under Anthony Mets's direction, Codex changed citation comparison to tolerate
boundary whitespace only. Internal characters, the 1-based line number, chosen
virtual source tree, host failure signal, previous prediction assessment and
literal presence/absence checks remain enforced. Patch search/replace stays exact.
The check establishes literal premises, not semantic truth of the explanation.

Before live calls, the corrected checker accepted all seven retained evidence
records previously rejected at a boundary-whitespace mismatch. No old patch was
validated by this audit and no historical outcome was replaced. Meaningful tests
cover formatting tolerance, altered string-literal content, incorrect line numbers
and false absence claims. **116 focused tests pass**, with repository integrity
checks passing before the prospective freeze.

DEV_REPAIR_CAUSAL_EVIDENCE2 froze at `4bbb9989`. Three exposed Java cases, one
repetition, paired alternating order, fresh checkout/evidence, identical model,
playbook, branch tools, four rounds and request/token/validation ceilings in both
arms; only the child requires evidence checks. API ceiling USD 0.10. This is a
small interface-recovery pilot, not a fresh-case generality evaluation or
independent replication. Comparing historical 0/6 with this 2/3 alone is not a
controlled causal measurement; the within-pilot comparison is 2/3 versus 2/3.

| Arm | Repaired | Calls | Validations | Inapplicable | API cost USD | Arm seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 2/3 | 10 | 4 | 1 | 0.012621475 | 196.0 |
| Corrected checked child | 2/3 | 7 | 3 | 1 | 0.010978750 | 152.1 |

All 17 calls have cost receipts: **USD 0.023600225**. Together with the preserved
first pilot, 55 calls cost **USD 0.078140475**. API cost excludes infrastructure;
time excludes baseline preparation. The child's lower cost includes early
termination on the hard case and does not establish better solving efficiency.

Both Mockito-17 and Jsoup-54 pass the complete external validation gates in
both arms. No source-quote mismatch occurs in the corrected child. On Mockito-23,
the child's first candidate passes the evidence check but fails with `MockUtil`.
Its final second-round submission exposes null hypothesis/files/parent/evidence
in parsed receipts and is rejected. The original raw candidate item was not
retained, so the precise malformed layout is unknown; it must not be described
as a reconstructed or repaired historical payload. The final inapplicable
submission stops the arm despite unused global requests.

The reference repeats a candidate with an already graded digest on round three;
the host stops when there is no fresh candidate. Thus malformed submissions and
duplicate proposals still truncate search. Literal grounding alone has not fixed
causal reasoning or generation reliability. These are explicit remaining limits,
not successful RSI or newly learned canonical procedures.

Verification checks stored receipts, digests, budgets and observation/prediction
consistency against host verdicts; it is not an independent reproduction. No
observed 404 or process interruption. Production trees are restored, no policy
is promoted, no reserved/fixed revisions are used, and canonical memory remains
292 events. Success patches and failures are retained in the trial artifacts.

Artifacts: [plan](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE2/PLAN.json),
[result](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE2/RESULT.json),
[diagnosis](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE2/DIAGNOSIS.json),
[citation audit](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE2/BOUNDARY_WHITESPACE_AUDIT.json),
[verification](../experiment/bench/DEV_REPAIR_CAUSAL_EVIDENCE2/VERIFICATION.json).
