# Historical owner identity compatibility — 5 October 2026

The registered human remains Anthony Mets, GitHub account `mjodheim`. The native
research integration contains fifteen frozen commits made with the same owner's
historical contact identity, whereas the current attribution checker registers
only his GitHub noreply identity. Rewriting those commits would change apparatus
and freeze hashes and damage scientific provenance.

The proposed correction registers that exact historical name/email pair in
addition to the existing noreply pair. It admits no new person, email wildcard,
service author or pull-request account. Existing bot, unregistered-human and
tool-credit rejection remains. The test includes both acceptance of the historical
owner pair and rejection of a different name with that email.

This correction is a separate commit based directly on current main so the trusted
base attribution workflow can validate it with the already registered noreply
identity. It must be integrated before the legacy scientific-history PR: the
workflow deliberately loads the checker from the PR's base, not the proposed
head. No workflow file, branch protection, frozen experiment or scientific criterion
is changed. Codex supplies substantial AI assistance under the owner's integration
delegation; that disclosure remains in the provenance documentation.
