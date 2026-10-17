# Contributor attribution — explicit owner instruction, 17 October 2026

Project-owner instruction in ChatGPT on 17 October 2026: accept legitimate
contributions from Anthony, Mira and Leona in the Genesis attribution
policy. This is an instruction to allow their **correct and distinct Git
identities**, not an instruction to claim that Leona or Mira are humans, and
not permission to falsify author/committer metadata.

Accepted author/committer pairs in the policy:

- Anthony Mets: existing registered owner emails (both retained for the
  historic frozen-commit chain).
- Mira: both existing registered Mira addresses.
- Leona (AI): leona-ai@noreply.github.com, with the exact Git name
  Leona (AI). This is an AI executor, not a new human copyright holder.

As of this change, GitHub PRs can be opened from existing approved
publisher accounts mjodheim and Mira-Mjodheim. Leona currently publishes
through the owner-approved GitHub connection; the **commit author remains
Leona (AI)**. No separate Leona GitHub login is presumed.

The existing GitHub-required workflow job name "Human-only attribution"
is preserved for backward compatibility with the required status check.
Its semantics from this owner decision onward are **registered contributors
Anthony + Mira + Leona**, not human-only. Update the GitHub branch
protection/ruleset separately if the job's name is eventually changed.

Unrecognized identities and generic bot impersonation remain rejected.
Mira's existing prohibition on editing merge-gate scripts and workflow
files is unchanged. Frozen scientific protocols, independent evaluators,
sealed records, and all required branch checks remain in force.

**Bootstrap limitation:** the workflow deliberately evaluates candidate
PRs under the trusted **base revision**. This policy change cannot make
itself pass a gate still running the older Anthony/Mira-only code. The
owner must adopt/review the new policy through a legitimate authorized
merge route; do not spoof an Anthony commit or silently bypass required
checks. Once it is actually on main, new PRs are checked using the
updated three-contributor policy.
