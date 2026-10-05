# V35 supplemental audit boundary

During the fresh campaign, code review found gaps in the frozen `check`
command's adversarial validation: it did not reread the whole-campaign
`RESERVATION.json`, and its recovery check did not explicitly compare the recorded
interruption head with the corresponding actual journal event. Task reservations,
all paid evaluations and normal recovery execution are still checked by the
original apparatus. These gaps do not change observed task scores or call counts,
but could allow altered auxiliary receipts to pass that command.
The explicit manifest input dictionary also omits the V23 guard and sandbox
loaded indirectly by V25. Their versions are included in the original apparatus
Git commit, but the original checker does not compare their current bytes with
that commit. The supplemental audit makes that comparison, including the V23
worker referred to by the loaded sandbox, and records the exact file digests.

The original V35 source, tests, pilot, freeze and fresh evidence are preserved.
No instrument was silently patched, no task was retried and no acceptance
threshold was changed after observation. A separate read-only audit helper,
`scripts/audit_v35_native_campaign.py`, supplements the original full replay with
exact checks of the original campaign reservation, committed freeze chronology,
transitive guard/sandbox bytes, interrupted ledger head, restored history and
aggregate caps. Its adversarial tests reject altered reservation cost, identity,
single-attempt status, interruption head and transitive guard source.

This helper was written after the pilot and during the fresh campaign. It is an
explicit retrospective audit of existing requirements, not a newly frozen
experimental evaluator, another canonical attempt or independent replication.
Future apparatus should incorporate these checks prospectively in a new version.
Any L9 interpretation must acknowledge this chronology alongside the substantive
append-extension limitation described in the protocol and continuation argument.
