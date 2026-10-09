# Coordinated repair development and pilot — 9 October 2026

The machinery and DEV_REPAIR_TRANSACTIONS1 protocol were committed before execution
in `ad164001`. This is Codex-assisted infrastructure development under Anthony's
direction, not an autonomously invented Genesis primitive. Prior results remain intact.

## Implemented capability

An opt-in proposer accepts one to three existing production files per candidate.
The construction rejects the complete candidate if any edit is invalid, a path is
duplicated, a symlink is encountered or a declared test directory is targeted.
No candidate file is written during construction. The validator applies all candidate
files before compiling, then uses the existing triggering-test and full-suite gates.
It attempts byte-exact restoration of every file in its finally block, including
after exceptions. This is coordinated application and rollback, not a filesystem
transaction guaranteed to survive a forced process kill. The existing runner restores
production sources when starting a case after an interruption.

One complete transaction consumes one validation. Successful patches include all
file diffs. Legacy one-file digests remain unchanged. The representation adapter is
authored: the child gets a files-array tool schema and a trusted instruction overriding
the old one-file rule. No bug-specific solution hint is added.

Eighty-eight focused tests passed before the freeze, including joint-file validation,
whole-candidate rejection, restoration after compile interruption and a second-file
write failure, nested test-directory rejection, path checks, digest compatibility,
patch recording and the trial's receipts/mode verifier.

## Frozen pilot result

Both arms use application feedback, the same seed genome and external Haiku model,
up to eight requests and six validations per case. Mockito-17, Jsoup-54 and Mockito-23
are previously exposed development cases, each run twice in alternating arm order.

| Measure | One-file parent | Coordinated-file child |
| --- | ---: | ---: |
| Repaired case-runs | 4/6 | 4/6 |
| Model requests | 20 | 22 |
| Validated candidates | 10 | 9 |
| Known API cost, USD | 0.025220645 | 0.024116685 |
| Sum of arm elapsed seconds | 457.6 | 451.7 |

Both arms pass the trigger and full suite for Mockito-17 and Jsoup-54 in both
repetitions. Mockito-23 fails in all four attempts. No baseline extra failures are
tolerated. Forty-two call receipts sum to USD 0.049337330, below the USD 0.20 ceiling,
with no unknown-cost calls. The record verifier checks pair order, budgets, genome,
submission mode, journal matching and summary arithmetic. It is not independent
replication. Arm elapsed time excludes initial baseline preparation and is not a
monetary infrastructure cost estimate.

All twelve parsed child proposals change one file each; some duplicates are not
validated again. Thus the pilot does not exercise the new multi-file capability.
There is no demonstrated gain or cost-efficiency result. One parent submission is
inapplicable. One child call in the last round of Mockito-23 repetition 2 fails with
`TypeError: string indices must be integers, not 'str'`; its cost and failed outcome
remain in the record. Exact malformed arguments were not retained, so their structure
cannot be reconstructed from this evidence. There was no interruption or provider 404.

## What the traces suggest next

In child repetition 1, one answer modification exposes DelegatingMethod as the next
nonserializable class. A candidate combining an answer change and serialization
settings exposes MockUtil. The following settings-only candidate encounters
ReturnsDeepStubs$2 again. This is evidence of exception transitions and regression,
not proof that either partial edit is semantically correct or must be retained.

Merely allowing more files does not ensure coherent reasoning or cumulative repair.
The next useful investigation is an explicit archive of candidate branches: let the
agent inspect a prior candidate's virtual source and propose extensions, while the
external validator still evaluates complete candidates and full suites from the
original tree. This must be tested, not assumed to improve repair rates. Mutation of
the solver's executable improvement mechanism remains a separate outstanding step.

Argument handling also needs typed rejection and bounded retained diagnostics.
Any subsequent hardening is prospective and must not replace this failed model call.

No policy is promoted, no held-out case is consumed and canonical memory remains
292 events. Successful patches and verdicts are retained in the experiment artifacts.
No general RSI or independent autonomous learning claim follows.

## Prospective argument hardening after the pilot

After closing the result, the parser now rejects malformed file layouts without
attempting to index strings as file objects. Unsupported layouts are retained in
the call record and receive the normal rejection feedback; a correction is possible
only within remaining planned requests. Transaction construction checks container,
path and edit types before using them. Record verification enforces the applied-file
limit on applicable proposals, rather than treating a rejected malformed response
as a resource grant.

Four additional offline cases cover null, string, object and string-list layouts,
followed by a valid correction using a scripted model. Ninety-two focused tests pass.
No new live call was made for this hardening. The exact historical malformed payload
is unavailable, so these tests cannot establish that it would have been recovered.
The forty-two original receipts and failed result remain unchanged.
