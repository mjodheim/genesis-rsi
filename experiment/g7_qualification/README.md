# G7 scientific qualification

Status: **`G7_SCIENTIFIC_GATE_PASSED` under the preregistered project-defined criterion.**

Frozen chronology:

- `b7aad58e` — externally authorized lineage apparatus;
- `07dc9646` — G7 candidate lineage set;
- `fd10fbb2` — prospective G7 qualification;
- `fca80392` — positive result and persisted lineage store.

Result:

- Round A: 1/4 parent -> 4/4 D1 -> adopt;
- Round B: 4/4 active -> 1/4 reversion candidate -> reject;
- rejection leaves the active state digest unchanged;
- external rollback restores the exact seed artifact;
- Round C after rollback: 2/4 parent -> 4/4 D2 -> adopt;
- restart/replay succeeds after every transition;
- artifact/decision/journal/state tamper probes: 4/4 rejected;
- external model calls: 0;
- frozen predicates: 17/17 true.

Holdout SHA-256:

`83211370525d160de22cf2ddcfb84d4cf830197f2de50c6292a9b7a27e4713ae`

See `docs/G7_QUALIFICATION_2026-10-07.md` for the exact claim boundary.