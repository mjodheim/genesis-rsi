# V35 complete public pilot — 2 October 2026

Apparatus committed before this pilot at `d39ab2a1141f427bf9e2fa5c6d9e917c74f5e61f`.
Both declared public seeds, all four arms and all four epochs are preserved in
`DEVELOPMENT.json.gz`, with the prior immutable reservation and input hashes.

| Arm | Solved / 120 | Charged evaluations | New solving behavior signatures |
|---|---:|---:|---:|
| Adaptive, behavior-distinct paid probes | 96 | 899 | 32 |
| Recency | 85 | 1101 | 27 |
| Greedy | 91 | 1090 | 30 |
| Cold | 95 | 1043 | 33 |

Adaptive new behavior counts by epoch are 3, 5, 4, 5 on seed 503 and 3, 3, 4, 5
on seed 887. Adaptive solves 48 tasks on each seed; cold solves 47 and 48.
The gain over cold is only one task, with 144 fewer charges (13.8%). Cold still
discovers one more new behavior overall. This does not justify claiming broad
superiority or generality. The finite pilot predicates pass, but the nonisolated
development data do not qualify fresh performance.

Both domain age and probe diversity changed prospectively, so this comparison
does not isolate their individual causal effects. All arms receive the same V35
tasks. V34's negative result is retained and not compared as if it used the same
population. No implementation or threshold is changed after this observation.
Proceed to the declared prospective eight-epoch fresh prefix; retain any negative.
