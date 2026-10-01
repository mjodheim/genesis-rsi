# V31 — persistent archive operational assay (prospective)

## Claim and attribution

This is Track B archive engineering around byte-exact G7. No G8 acquisition is
claimed. The transducer proposal generator, retention modes and bank are
project-authored, not independently authored. Finite candidate domains of width
2–64 are an explicit containment limit. The four-window assay does **not** pass
L9, establish a positive asymptotic discovery rate, or pass L10.

The operational question is whether diverse executable descendants can be kept,
branched from, recovered at task boundaries and rediscovered under fixed external
governance. Discovery is a previously unobserved executable source that solves
its current task, not a renamed/comment-only program. Behavior is bit rotation
followed by XOR. Source and semantic genotype hashes are both retained.

## Prospective population and costs

Development seeds: 101, 211. Every pilot outcome, including negatives, is public
development. Fresh seeds: 9143, 27189, 40733. Each produces 48 tasks in four
12-task windows, of increasing width 3, 4, 5, 6 and three represented operator
families. All 144 fresh tasks, all three arms, order and thresholds are committed
before their first evaluation. They are held out from execution, not secret from
the project authors. Task family-width counts measure diversity inside this
transducer domain, not independent software domains.

Each arm receives the same task stream and unchanged G7, with 12 candidate
requests, eight rounds, parallelism two and mutation depth three. The measured
identity root costs one additional evaluation for **every** arm. Re-evaluating
an archived source on a new task also costs a request. Proposals and fixed archive
retrieval are externally implemented; retrieval ranks only previously observed
success and recency at matching width. G7 sees current revealed qualities, AST
descriptors and budgets, never expected outputs, hidden target genotype, future
qualities, task identifiers or author-provided family labels.

Arms: retain every branch (`archive`), retrieve only the last successful matching
champion (`greedy`), retrieve none (`cold`). Historical raw receipts remain
available for audit even for the pruning controls. Complete per-arm requests,
root probes, rounds and source hashes are recorded. Report per-window discovery
rates, coverage, archive size and rediscoveries for each seed and pooled arms.
No seed, task, window or failure may be omitted. Negative comparisons are valid.

## Recovery, ledger and containment

The evaluator, source guard, caps, task bank, checkpoint/ledger and verdict are
outside the actor's authority. The actor runs through the frozen V27 isolated
worker; the appended transform runs in a separate isolated worker with the same
one-second CPU, 512 MiB address-space, private directory and three-second wall
limits. No imports/I/O, credentials or deployment permissions are exposed to
generated source. This is a resource-limited pure-source boundary, not a claim of
a kernel security sandbox against arbitrary hostile host code.

Each JSONL record commits sequence, previous digest, body and digest. Appends
take an exclusive file lock, compare the prior head, flush and fsync. An external
retained head is needed to detect whole-chain rewriting/truncation; a hash chain
alone is not an independent trust root. Reject symlinks, nonregular files,
malformed/torn tails and stale concurrent writers.

Before each task, reserve all 13 evaluations durably. A mid-task interruption
leaves the reservation visibly pending: quarantine it, keep its budget debt and
do not silently retry. Automatic recovery is supported only at completed task
boundaries. In each canonical stream stop after six completed tasks, destroy the
executor object and resume from disk. Replay the full completed stream and
compare a no-interruption run on development seeds. Canonical fresh tasks are
not executed a second time to demonstrate recovery.

## Operational adjudication

Positive **operational precursor** requires complete frozen evidence, exact G7,
all caps/costs valid, archive size and family-width diversity increasing in every
window for every fresh seed, at least one genuinely branching parent, at least
one rediscovery, and exact checkpoint continuation/replay. Report whether every
window has positive discovery and whether archive beats controls separately;
neither is silently substituted for open-endedness. Always return
`l9_open_ended_passed: false`, `l10_independent_passed: false`.

Freeze all apparatus, tests, protocol, review, development receipts and inherited
V30 scientific inputs/results in a committed full manifest. Use an exclusive
canonical attempt marker, retain the original interrupted/negative evidence and
never overwrite a consumed attempt. Apparatus and freeze must be separate
ancestral commits. Reproduction checks replay receipts without re-consuming a
fresh population. A new extension requires new prospective external-governance
commitment; never relabel a consumed seed as fresh or revise this assay.
