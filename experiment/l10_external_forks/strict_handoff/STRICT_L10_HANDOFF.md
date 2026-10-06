# Strict L10 external handoff

Status: **prospectively frozen handoff preparation; no strict-L10 claim yet**

This packet starts from the public L10-C result tagged
`l10c-public-external-transfer-v1` at commit
`64c189b02e175887ebc09ad72940e51af48412a8`.

The public carrier is `sharkdp/bat`, issue #4039. The frozen baseline reproduced
the public capacity-overflow panic; the single blind proposer candidate passed the
frozen issue objective and 147/147 frozen library regression tests.

Strict L10 is intentionally outside project control. This packet cannot be
completed by Anthony Mets, mjodheim, this assistant, project-controlled agents,
CI, or additional internal runs.

## Required external roles

Three distinct external roles are required.

1. **Task authority / maintainer** — a person outside the project who can attest
   that the task originated and was maintained outside Mira Genesis and that no
   hidden project-authored task content was substituted.
2. **Independent reproducer** — a person or organisation outside the project,
   using infrastructure not controlled by the project, who reproduces the frozen
   baseline failure and candidate success from a clean checkout.
3. **Adversarial auditor** — a separate person who can fail the claim and who is
   **not selected by the Genesis project**. The reproducer (or task authority)
   nominates the auditor after the reproducer identity is fixed.

The three identities disclose conflicts and must not be aliases of Anthony Mets,
mjodheim, a project-controlled AI identity, or each other. Compensation is
permitted only when it is fixed independently of the outcome.

## Frozen evidence to inspect

- Genesis tag: `l10c-public-external-transfer-v1`
- Genesis commit: `64c189b02e175887ebc09ad72940e51af48412a8`
- Carrier: `sharkdp/bat@4608fc959aa8abf80d32198836511a570b7ae9ea`
- Public issue: `sharkdp/bat#4039`
- Candidate tree: `ff26b2985facb5c97468801295c8bf61a95ff939`
- Candidate commit in the experimental fork:
  `332a959afa41468e6b99b646832f3336d377b13f`
- Evaluator freeze:
  `ef8773e6ce9b69b2db6b8246c25918bb4f32162f`
- Result:
  `experiment/l10_external_forks/l10c/results/CANDIDATE_RESULT.json`
- Narrative:
  `docs/L10C_BAT_4039_EXTERNAL_TRANSFER_2026-10-06.md`

## Reproduction decision rule

The reproducer checks out the exact public Genesis tag and obtains the exact
carrier commit from the public upstream. They must independently verify the
hashes above before execution.

A reproduction is positive only when all of these are observed without editing
the frozen candidate or evaluator:

- frozen baseline issue case fails with the recorded capacity-overflow panic;
- frozen control behaves as recorded;
- candidate regression returns zero and all 147 frozen library tests pass;
- candidate issue case returns without panic and satisfies the frozen graceful
  outcome rule;
- no network access, hidden evaluator change, candidate repair, retry, or
  replacement is introduced after seeing an outcome.

A different outcome is retained as a negative reproduction. It must not be
silently retried until positive.

## Adversarial audit minimum

The auditor receives the repository history, protocol files, task-selection
records, proposer bundle/output, candidate freeze, baseline records, reproduction
report and public issue chronology.

The auditor must actively try to falsify at least these points:

- issue existed outside the project before task inspection;
- metadata-only selection preceded issue-body inspection;
- baseline truly failed at the frozen upstream commit;
- proposer had no evaluator or baseline-result visibility;
- exactly one candidate attempt was used;
- structured edits were imported deterministically without manual repair;
- the evaluated candidate tree is the frozen tree;
- failures/aborts in L10-A/L10-B/L10-C were retained rather than erased;
- reproduction used infrastructure outside project control;
- task authority, reproducer and auditor are genuinely distinct;
- claim wording does not inflate this result into AGI or unrestricted RSI.

The auditor may add attacks. A discovered material flaw makes the audit negative
until a **new prospective experiment** is designed; the old result is not
rewritten.

## Signing and custody

Each role fills its template in this directory and signs the exact JSON bytes
with an externally controlled key. Public keys, signatures and attestations may
be published after the signer approves publication. Private identity evidence or
private infrastructure details remain with the signer when necessary.

Suggested namespace:

`mira-genesis-strict-l10-v1`

Example:

```sh
ssh-keygen -Y sign -f /secure/reviewer_key \
  -n mira-genesis-strict-l10-v1 /secure/REPRODUCER_ATTESTATION.json
```

## Claim transition

Until all three real external attestations exist and the adversarial audit is
positive, the authoritative state remains:

`l10_independent_passed=false`

Only after those records are checked against this frozen handoff may a new,
separate adjudication commit consider setting strict L10 true. This handoff
itself moves no gate.
