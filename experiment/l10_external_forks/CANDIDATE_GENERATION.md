# L10-A candidate generation — frozen before baseline or candidate evaluation

Candidate generation is a declared external variation source. It is not counted as lineage-owned competence.

- proposer: official Codex CLI `0.154.0`
- model: `gpt-5.6-sol`
- one proposer invocation per selected carrier
- the proposer may inspect the frozen carrier checkout and the selected public issue body
- the proposer receives no baseline result, evaluator source, evaluator output, hidden result, or prior candidate outcome
- the proposer may edit the disposable carrier worktree but may not execute tests, build commands, network commands, Docker, GitHub, or deployment commands
- after the proposer exits, its complete diff is frozen before any evaluator is run
- no second proposer invocation, repair, retry or patch replacement is allowed for that carrier in this pilot
- the evaluator and Genesis selection gate remain external to the proposer

Attribution: a successful patch demonstrates competence of the composed proposer + Genesis evaluation pipeline. It does not establish that the endogenous L9 archive invented the patch.

Baseline is still measured before the candidate is scored. If the frozen upstream baseline already satisfies the issue objective, the carrier is recorded `BASELINE_ALREADY_SATISFIES_OBJECTIVE` and its candidate is not scored as an improvement.
