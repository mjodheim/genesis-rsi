# V33 — complete consumed development, not fresh qualification

The declared single-assignment sweep retains eight complete variants and 456
already consumed V31/V32 tasks per variant. It performs no V33 fresh behavior.
The original sources and every episode are bound in `DEVELOPMENT.json.gz`.

| Variant | Solved / 456 | Best quality sum | Charged evaluations | New solving sources |
|---|---:|---:|---:|---:|
| Adaptive, margin 0 | 333 | 414099 | 3636 | 126 |
| Adaptive, margin 25 | 335 | 414448 | 3620 | 130 |
| Adaptive, margin 50 | 337 | 414625 | 3582 | 133 |
| Adaptive, margin 100 | 331 | 412102 | 3623 | 132 |
| Exact selector removal, forced best probe root | 245 | 395023 | 4463 | 67 |
| Fixed recency, forced best probe root | 208 | 384430 | 5085 | 55 |
| Greedy, forced best probe root | 195 | 379743 | 5046 | 48 |
| Cold, best improving local probe root | 307 | 407164 | 4337 | 119 |

The declared lexicographic rule selects margin **50**. Adaptive has 30 more
solves than cold and 755 fewer charges (17.4%) on these consumed tasks. These
are outcome-conditioned development observations, not a holdout, new recursive
acquisition, independent evidence or L9 qualification. The controls' weaknesses
and all nonwinning adaptive margins are retained. Fresh superiority is unknown
at apparatus publication.

The primary fresh utility criterion concerns useful branch retention against
cold and greedy; exact selector removal and recency are also reported, with a
separate stricter all-control comparison. V33 does not rewrite V32's different
primary criterion or its negative verdict.
