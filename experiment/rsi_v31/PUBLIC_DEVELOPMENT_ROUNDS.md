# Complete development before the fresh archive assay

Initial apparatus and receipts: commit
`6717c354e2c75df3cfe3f1b5ecbcab44e53cc7f8`.
`DEVELOPMENT.json.gz` contains all 48 tasks for each of seeds 101 and 211, all
three arms and the task-boundary recovery comparison. This round consulted all
matching historical proposals, including unsuccessful ones. It performed worse
than the cold control: archive solved 13/48 and 17/48, versus cold 36/48 and
32/48, at costs 581/501 versus 441/397. Preserve this negative engineering result.

Before any fresh execution, limit retrieval to two recent already successful
champions, while preserving the full archive. The second complete development
round is `DEVELOPMENT_002.json.gz`, on the same consumed development seeds.
Its exact implementation file digests are inside that archive. Neither round is
fresh, independent, a G8 acquisition, an L9 pass or an L10 pass. No task/outcome
filtering or parameter search on the future fresh seeds is permitted.

Round 2 archive solved 32/48 on each seed, at costs 474 and 414. Greedy solved
33/48 and 31/48 (costs 460 and 404); cold still solved 36/48 and 32/48 (costs
441 and 397). Retrieval is substantially less harmful than round 1, but archive
still has no aggregate coverage/cost advantage over the controls. Freeze this
operational apparatus rather than selecting another variant on fresh outcomes.
