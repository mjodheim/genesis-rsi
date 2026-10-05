# V35 fresh native archive receipt snapshot

The [result and its limitations](../../../docs/RSI_V35_FRESH_2026-10-04.md) are
authoritative navigation for this scoped Track B assay. Original prospective
sources and freeze are in `experiment/rsi_v35/`.

`MANIFEST.json`, `RESERVATION.json`, `REPORT.json` and `COMPLETION.json` are copies
of the original single-assignment campaign files. `EPOCH_RECEIPTS.json` collects
every original epoch completion and prior-head/history binding, preserving all
432 epochs and all controls. `DERIVED_DIVERSITY.json` explicitly distinguishes
cohort discovery events from a post-assay cross-cohort union. `AUDIT.json` is the
separate retrospective full-replay and auxiliary-ledger check.

This snapshot contains receipts and complete summaries. Full compressed raw
traces and journals are local at `results/local/v35-native-fresh-20261004/`.
Checking that directory requires those original bytes. Reproduction using the
public generator is consumed-data verification and does not create an independent
fresh assay. General L9, L10 and a new policy generation remain unpassed.
