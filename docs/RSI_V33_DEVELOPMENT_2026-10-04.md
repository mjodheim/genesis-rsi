# V33 consumed-development record and disclosed instrument defect

**L9 remains open. V33 is development apparatus with an accounting defect, not a
qualified result.** All original files and evidence are preserved. The correction
belongs to the separately specified V34 successor, not to a replacement of V33.

The V32 post-hoc diagnosis counted 68 of 154 retrieved-and-evaluated programs
below the current identity root. Grouping its 216 consumed tasks by width and
root quality produced 74 buckets; 37 contained different target semantics, with
up to five meanings behind an identical scalar measurement. These are privileged
post-hoc diagnostics on consumed data; no target semantics enter actor calls.

## Prospective development and original report

V33 committed a local single-assignment apparatus/population manifest before
running all 456 already consumed V31/V32 tasks, four arms and unchanged G7/G6.
This local commitment is not a Git-committed scientific freeze. Each arm paid for
three diagnostic probes, one controller call and at most ten search evaluations,
with the same fourteen-call cap. The fast full comparison was non-isolated and
explicitly labelled DEVELOPMENT. Isolated worker execution was tested separately.

The original report, **whose solved counts exclude some successful probes**, is:

| Arm | Search-only solved / 456 | Charged evaluations | Observed retrievals below root / evaluated retrievals |
|---|---:|---:|---:|
| Three-probe adaptive | 273 | 4,762 | 41 / 154 |
| Scalar adaptive | 280 | 4,752 | 156 / 341 |
| Three-probe selector removal | 272 | 4,672 | 285 / 706 |
| Cold | 269 | 5,079 | 0 / 0 |

The original descriptive criterion is false. All arms pay the probe overhead;
therefore this matched comparison does not isolate diagnostic cost against the
older twelve-search-call V32 apparatus. In particular, do not attribute the
probe-versus-scalar difference to different budgets. The original paired record
contains two probe-only and nine scalar-only search solves.

On these 456 consumed tasks, scalar width/quality groups had 99 buckets, 58
semantically aliased, with up to ten meanings. The three-measurement fingerprint
had 334 buckets, 35 aliased, with up to three meanings. Better discrimination did
not establish better search-only coverage. This observation cannot select a fresh
population or establish a new recursive transition.

## Defect discovered after execution

V33 recorded the three paid probe receipts but built `programs`, `solved`, novelty
and history only from search nodes. Thus a diagnostic probe could execute an exact
solution without the task counting as solved; a failed or successful probe not
later chosen by search was absent from archive retention.

Raw receipts contain eighteen omitted probe-only task successes in each of probe,
scalar and cold, and twenty-five in selector removal. These numbers disclose the
defect; they do not rewrite the original report. Correcting only the arithmetic
would still leave the archive/history defect and its downstream search effects.

V34 therefore retains every distinct evaluated source, counts any charged exact
solution, records probe versus search success separately and keeps repeated actual
evaluation costs. It preserves V33's complete apparatus, thresholds, reports and
negative/partial candidates. A real consumed fixture at seed 101, position 15
demonstrates the omission: the rotation-by-one probe solves, but cold search does
not. Corrective tests must exercise that case and actual recovery/replay.

## Evidence and verification

Original local artifacts are under
`results/local/v33-probe-development-20261004/`: `MANIFEST.json`, thirty-two
append-only journals, lossless `DEVELOPMENT.json.gz`, `REPORT.json` and immutable
`COMPLETION.json`. These are ignored local research artifacts, not published
canonical evidence. Preserve them with the prepared environment snapshot.

```bash
python -m experiment.rsi_v33.development check \
  --output-dir results/local/v33-probe-development-20261004
python -m pytest -q tests/test_rsi_v33.py tests/test_rsi_v34.py
```

Mechanical receipt/journal replay passed; it reproduces the original reporting
defect rather than repairing it. Fifteen V33 tests and eleven corrective V34
tests pass. The full V33 regression passes 5,313 tests with eleven explicit skips
under Python 3.12.14 and Node 20.20.2; V34 tests run separately. No external
scientific model calls, fresh task population, acquired G8, L9 or L10 are claimed.

The [sustained programme proposal](L9_SUSTAINED_PROGRAMME_DRAFT_2026-10-04.md)
identifies the remaining domain, descendant-machinery and prospective measurement
requirements. Project-directed finite diagnostic fixes do not close that gap.
