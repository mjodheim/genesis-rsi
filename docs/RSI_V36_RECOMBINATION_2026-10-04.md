# V36 — recombination helps, fixed-depth continuation fails

The prospectively committed V36 development pilot is a **valid negative for
progression**. All 1,536 tasks, 192 epochs, donor identities, paid calls, native
references, decisions, recovery and global reservations fully replay. No V36 fresh
attempt was spent. V35's scoped positive remains unchanged; general L9 remains open.

| Arm | All solves / 384 | Calls | Transfer solves / 192 | Transfer calls |
| --- | ---: | ---: | ---: | ---: |
| Diverse archive with learned splices | 203 | 3,740 | 36 | 2,261 |
| Same archive, point mutations only | 184 | 3,905 | 2 | 2,487 |
| Latest successful body with splices | 159 | 3,994 | 14 | 2,399 |
| No memory | 142 | 4,292 | 0 | 2,496 |

Actual evaluations total 15,931, within the prospectively reserved 21,504.
Nineteen transfer solves have an evaluated learned splice as the solving proposal;
the other solves include paid rediscovery of previously acquired composite bodies.
The archive beats every control on transfer coverage in each seed/domain, and
costs no more than cold. This supports executable-fragment reuse on these consumed
development tasks; it does not establish a new policy generation.

Three frozen predicates fail: complete initial acquisition, a discovery in every
transfer epoch, and strictly growing solved archive state. All eight archive
cohorts have zero discoveries and zero solves at the final twelve-slot epoch.
Rates and negatives are retained in the original report without threshold changes.

## Failure diagnosis

The separately labelled post-pilot audit uses hidden targets only outside actor
execution. It computes exact point/splice grammar distance: in each aligned block,
take the minimum of direct point differences and one admitted splice plus its
remaining point differences. A second splice of that block overwrites the first,
so it cannot improve this bound. Sum independent block minima. Exhaustive graph
enumeration checks the formula on small complete state spaces.

Of 156 unsolved transfer tasks:

- 101 are beyond depth three from every paid screened root.
- 3 have a reachable paid alternative, but the selected root is beyond depth three.
- 52 are reachable from the selected root but are not found by G7 within its calls.

138 unsolved tasks lack at least one exact target block in the acquired library.
These categories overlap with missing-block status and must not be added together.
Fragment proposals can interfere with initial point acquisition, and diverse
whole-body screening does not guarantee the needed branch prefix. Therefore neither
the retrieval failure nor the ordering failure should be renamed purely as a
budget failure. Depth obstruction is real for the 101 specified tasks.

## A separate information bound

Consider an idealized externally hidden, independently uniform rewrite of `b`
positions, each containing one of four known three-slot motifs. There are `4**b`
possible behaviors. If the actor receives only a scalar matched-slot count, one
evaluation has at most `3*b + 1` outcomes. A deterministic adaptive search with
`C` evaluated candidates can exactly solve at most
`sum((3*b + 1)**i for i in range(C))` targets: every query-tree node proposes one
body, and a witnessed exact body identifies at most one target. Conditioning on
the history or algorithm randomness gives the same bound.

For fixed `C`, the maximum covered fraction is polynomial in `b` divided by
`4**b`, tending to zero. This is a statement about a blind scalar-feedback model,
not a proof that L9 or all environmental continuations are impossible. The public
seeded bank is not itself an independently uniform infinite stream. Physical
runtime/storage remain finite. The bound motivates a prospectively dimensioned
construction budget or informative public task interfaces; it cannot justify
weakening V36's observed fourteen-call criterion retrospectively.

The next implementation should separate initial acquisition from fragment reuse,
assemble at multiple positions through paid scalar feedback, and compare an
identical point-construction scheduler. Explicit scaling and declining rates must
remain visible. A host-authored scheduler alone is not an acquired G8.

## Evidence and provenance

Apparatus commit `ed5f3fd1`, preserved by `provenance/v36-apparatus-20261004`,
predates the pilot. [Protocol](../experiment/rsi_v36/PROTOCOL.md),
[IP review](IP_REVIEWS/V36_LEARNED_RECOMBINATION_REVIEW.md),
[original receipts and retrospective audit](../results/rsi-v36/recombination-pilot-20261004/README.md).
The 16 prospective V36 tests and 3 separately authored audit tests pass. The
original apparatus inputs remain byte-exact; corrections require successors.
Anthony Mets directs the research; OpenAI Codex provided substantial AI assistance.
