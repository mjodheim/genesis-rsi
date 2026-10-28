# Owner standing delegation of publication and governance decisions

**Decision date:** 28 October 2026
**Owner:** Anthony Mets, sole human research director and release/acceptance decision-maker
**Default disposition:** `PUBLIC_AGPL_COMMERCIAL_OPTION`

Anthony Mets wants Mira to carry Genesis forward autonomously. On 17 October 2026 the autonomous
chantier stopped for eleven days on a publication formality: no register entry covered CIRCUIT2, and
`AGENTS.md` §3 required an owner decision before enabling disclosure. This record is that decision,
made once for the work to come.

## 1. What is delegated

For prospective work in this public repository, Mira (with Codex as reviewer) decides and records,
without waiting for the owner:

- **Publication.** A materially new core mechanism receives `PUBLIC_AGPL_COMMERCIAL_OPTION`, unless a
  concrete reason from `docs/IP_PUBLICATION_POLICY.md` §4 applies. Mira writes the short review of §2
  in `docs/IP_REVIEWS/` (mechanism, provenance including AI assistance, third-party material and
  licences, frozen boundaries touched). This delegation stands in for the "owner's publication
  decision and date".
- **Frozen perimeters.** Mira states which files a frozen plan covers, by its recorded digests. A
  frozen file is never edited in place. A change goes into a new, separately versioned protocol that
  leaves the earlier one and its results untouched.
- **Scientific choices.** Mira picks the next milestone, the protocol and the pre-registered criteria,
  under the rules of `AGENTS.md` and of the frozen protocols.

CIRCUIT2 is covered: its plan and negative results are already public (#411). The inherited NAND
procedure, its recursive search and the CIRCUIT2 protocol are `PUBLIC_AGPL_COMMERCIAL_OPTION`.

## 2. What stays with the owner

The owner's own decision remains required for:

- any spending, paid service, new subscription or model API call in an experiment;
- credentials, accounts and hardware (including GPU use);
- deployments outside this repository's CI;
- Mira's private repair code. Only its results are published, as decided for #433;
- any case where a reason from `IP_PUBLICATION_POLICY.md` §4 (patent, trade secret, confidential third
  party, embargo, security, commercial private) is plausible, or a third-party licence cannot be
  verified;
- changes to `.github/`, the attribution policy and its test.

In those cases the agent stops and asks, as `AGENTS.md` §3 already requires.

## 3. Boundaries that do not move

This delegation authorises no relaxation of a frozen criterion, no rewriting of a published result, no
replacement of an independent judge and no claim of general RSI. Negative results stay published as
they are.

## Provenance

Anthony Mets gave the instruction ("il faut qu'elle soit autonome", 28 October 2026). Anthropic Claude
drafted this record from that instruction and from the blocked request of 17 October. Claude has no
acceptance or release authority. The owner can withdraw or narrow this delegation at any time by
replacing this record.
