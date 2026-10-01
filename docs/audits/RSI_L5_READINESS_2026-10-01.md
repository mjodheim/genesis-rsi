# RSI L5 readiness audit — 1 October 2026

Status: V24 is a preserved negative L5 result. V25 is development apparatus, not an L5 result.

Anthony Mets asked to inspect Mira Genesis and advance L5. OpenAI Codex provided
substantial repository inspection, implementation and test assistance under that direction.
This audit introduces no external code, dependency, confidential task bank or new authority.

## Verified predecessor evidence

The successful V24 workflow is run 36431055231 at source commit
`35e26649ae63c890d322eaa18ece31b1c54480e2`. Its artifact 10974011977,
`v24-l5-fresh-holdout-evidence`, has archive SHA-256
`14b70400a42a0256a2934c79dbfa01d9f5d1d3dff2d6b4d0fd92926b063122b0`.

The twelve task results and final adjudication were downloaded, checked against that
archive identity and every hash already recorded in the preserved evidence manifest,
then copied byte-for-byte to `results/rsi-v24/l5-20260928/`. No V24 arm was rerun,
rescored or edited. All three aggregates remain `(2, 2500, -17, -17)`: the successor
ties both comparators, so `l5_positive` remains false.

The V25 citation registry had a nonexistent full SHA sharing the first twelve characters
with the real workflow source. The live registry is corrected to the observed source,
subject and evidence path. The source history is retained as a merge parent of the
V25 integration so that deleting the historical experiment branch cannot erase it.

## Development defects corrected before any V25 final freeze

The default pytest population included only `tests/`, omitting all nineteen tests in
`experiment/rsi_v25/`. Running those tests explicitly exposed two failures: equal-utility
selection retained unused novelty/depth parameters, and their single-component ablations
therefore had identical utility. These were real failed causal checks, not evidence of L5.

The prospective tie-break now prefers fewer acquired components before the content digest.
The selected development mechanism must still strictly outperform every matched ablation.
All V25 tests are now included in the ordinary suite and both Python CI populations.
This change concerns public development traces only; no V25 holdout was authored or consumed.

The builder previously counted arbitrary files and associated their working-tree bytes
with HEAD without checking they were committed. It now verifies all thirteen identities,
checks task schemas and recomputes the negative aggregates, then requires every apparatus
and evidence byte to match its named commit. Its output is explicitly a development
apparatus commitment and cannot authorize a final holdout.

## Remaining scientific requirements

1. Bind executable descendant search and matched control searches to the actual preserved
   predecessor. A synthetic FIFO root is not the historical G2/G3 lineage, and enumeration
   by a fixed outer evaluator alone does not demonstrate recursive causal discovery.
2. Freeze and verify zero-tolerance L4 retention for the selected executable successor.
3. Prospectively commit a genuinely new population, evaluator, host identities, budget
   accounting and one-shot run/adjudication path before successor selection. The consumed
   V24 tasks cannot become a fresh holdout again.
4. Execute that frozen comparison once and preserve its actual verdict. L5 requires strict
   global-utility improvement over both required comparators, with all causal, retention,
   identity, budget and no-leakage predicates passing.

The public development gate passing or CI being green does not close these requirements.
