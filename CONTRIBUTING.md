# Contributing to Genesis

Thank you for your interest in Genesis (formerly Mira Genesis). Genesis treats provenance, negative results and
experimental boundaries as part of the research output, so contribution history must remain
auditable.

## Temporary external-contribution boundary

**Externally authored copyrightable contributions are not currently accepted for merge unless a
separate written contributor-rights agreement has first been approved for that contributor.**

This includes substantive external code, tests, executable specifications, documentation, diagrams
and other copyrightable project material.

The reason is chain-of-title clarity. Genesis intends to keep its research software public under
AGPL while preserving the project owner's ability to grant separate commercial permissions for
controlled material and to assign/acquire those rights later. A Developer Certificate of Origin is
useful provenance, but it is not a copyright assignment and by itself does not preserve that
commercial-relicensing flexibility.

Do not open a copyrightable pull request expecting DCO sign-off alone to make it mergeable while this
boundary is in force.

Issues, reproducibility reports, bug reports and non-confidential technical suggestions remain
welcome. Do not disclose trade secrets, credentials, private task banks or other confidential or
proprietary information in a public issue, discussion or pull request.

A future contributor agreement intended to permit externally authored contributions will be reviewed
before adoption. This file deliberately does not improvise that legal agreement.

## Licence of already accepted / project-controlled contributions

Material published in the repository remains governed by the licence applicable to that material, as
described by `LICENSE_POLICY.md`.

Nothing in this contribution policy revokes or narrows rights already granted under those licences.

If and when an external contributor-rights agreement is adopted, it must address the rights needed
for contribution, public AGPL licensing, alternative commercial licensing and potential assignment
or acquisition. The exact legal form will be determined separately rather than inferred from DCO
sign-off.

## Developer Certificate of Origin

Commits for which DCO sign-off is required must be signed off under the [Developer Certificate of
Origin](DCO). Add a sign-off with:

```text
git commit --signoff
```

The resulting commit message must contain a `Signed-off-by:` line matching a contributor identity
that you are authorised to use. The sign-off certifies the complete DCO; **it is not a copyright
assignment and does not override the external-contribution boundary above.**

## Authorship and AI assistance

- Preserve existing copyright, licence, citation and provenance records.
- Describe material changes accurately and do not claim authorship of unchanged upstream work.
- Disclose substantial use of generative tools when it affects the provenance of code, evidence,
  analysis or prose.
- Confirm that submitted AI-assisted material can be used under the applicable project terms.
- Do not present a fork or derivative as the official Genesis project; Mira Genesis remains the historical project identity.
- Record human design, selection, review, editing and integration decisions when material to
  provenance or later rights diligence.

## Prospective IP publication boundary

Read [`docs/IP_PUBLICATION_POLICY.md`](docs/IP_PUBLICATION_POLICY.md) before working on materially new
core R&D.

Starting with M086, **public research is the normal path after a short pre-publication review**.
Commercial value alone is not a reason to move the work to a private repository. Project-controlled
software that is intentionally published remains under AGPL, while alternative commercial
permissions may be negotiated separately where the project controls the necessary rights.

Use a private workspace only when a specific temporary disposition has been recorded, such as
patent-first review, intentional trade-secret treatment, confidential third-party material,
contractual embargo, security-sensitive material or deliberately proprietary product code.

The publication/licensing boundary must never be used to weaken scientific controls or to hide an
already materialised frozen negative result.

See [`docs/DUAL_LICENSING_STRATEGY.md`](docs/DUAL_LICENSING_STRATEGY.md).

## Scientific changes

Changes to public scientific material must preserve frozen and canonical artifacts. A negative result
must not be deleted or rewritten as a success. New claims require tests, explicit authority
boundaries and reproducible evidence appropriate to their scope.

Before opening an eligible pull request, run:

```text
pytest -q
python scripts/check_repository_integrity.py
```

Pull requests should explain the changed claim or behaviour, the relevant validation and any effect
on frozen or canonical evidence.
