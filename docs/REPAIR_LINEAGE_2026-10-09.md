# Self-revising repair lineages — 9 October 2026

Status: two development lineages and one held-out trial. **The held-out result is
negative.** No general recursive self-improvement is claimed.

## Question

Can a repair agent improve itself when nothing is added by hand between generations?
A *genome* holds what shapes how an external model is used on a case (instructions, a
playbook, how much evidence is shown, how a fixed budget is split between reading and
proposing) and the instructions used to write the next genome. The same model reads the
agent's own results on training cases and writes the successor. Every genome works
inside one envelope: 6 validations and 8 model requests per case, 4096 output tokens per
request. Model: `anthropic/claude-haiku-5.5` through OpenRouter. Mechanism:
`genesis/repair_lineage.py`; runner: `scripts/run_repair_lineage.py`.

The seed genome is the repository's existing OpenRouter exploration configuration.

## LINEAGE1 and held-out trial L1

Plan frozen at `ab753081`: 10 training and 10 selection development cases, one
evaluation per genome, promotion on strictly more repaired cases.

| Generation | Repaired of 20 | Decision |
| --- | --- | --- |
| 0 (seed) | 4 | |
| 1 | 8 | promoted |
| 2 | 4 | rejected |
| 3 | 4 | rejected |
| 4 | 6 | rejected |

L1 was preregistered at `77878d23` before execution: seed against generation 1 on the
next 40 held-out cases, same envelope, each case run once per genome.

| | Seed | Generation 1 |
| --- | --- | --- |
| Repaired of 40 | 21 | 19 |
| Repaired by this genome only | 3 | 1 |
| Model requests | 181 | 141 |
| Model cost (USD) | 0.250 | 0.175 |

One-sided exact sign test for generation 1 over the seed: p = 0.94. The development
gain does not transfer. Generation 1 used fewer requests; that comparison was not
preregistered and is reported as an observation only.

The improver comparison (development cases, two successors of the seed per improver
text) is negative as well: successors written with generation 1's improver text
repaired 4 and 5 of 20 cases, those written with the seed's repaired 8 and 7.

## Apparatus defect found by LINEAGE1

No generation repaired any of the 6 Lang cases: their full suite contains tests that
fail in the container whatever the candidate (home directory, network). The
JacksonDatabind failing sets contained `testInetAddress`, which needs a network; both
genomes scored 0 of 6 on L1's JacksonDatabind cases. L1 penalises both arms equally, so
its comparison stands, but its absolute counts understate repair capability. Selection
in LINEAGE1 ran on a development set where 6 of 20 cases could not be won, and its
successors wrote playbook lessons about a problem that belonged to the apparatus.

Fix (`a89b50b1`, opt-in, earlier trials unchanged): failing tests are narrowed to the
triggers Defects4J declares, and tests that already fail on the unmodified buggy
revision are not held against a candidate.

## LINEAGE2

Plan frozen at `7153a7e6`: corrected apparatus, 15 training and 15 selection cases, no
exposed project, none of LINEAGE1's cases, two evaluations per genome, promotion on at
least 3 more repaired case runs out of 60.

| Generation | Repaired of 60 (two evaluations) | Decision |
| --- | --- | --- |
| 0 (seed) | 43 (21 + 22) | |
| 1 | 39 (20 + 19) | rejected |
| 2 | 37 (20 + 17) | rejected |
| 3 | 38 (19 + 19) | rejected |
| 4 | 37 (18 + 19) | rejected |

No successor was promoted, so no held-out trial was run: both arms would have been the
seed. No held-out case was consumed by LINEAGE2.

## What this establishes

- With an external model, the loop repairs a substantial share of cases it was never
  shown (21 of 40 held-out on L1 despite the apparatus defect; 72 % of development case
  runs once the defect is fixed). "Repaired" means the full developer suite passes, not
  that the patch is correct, and Defects4J may be in the model's training data.
- Configuration self-revision by the same model did not improve the agent: one
  promotion that did not transfer, then four rejections under a stricter rule. Every
  successor of LINEAGE2 scored below its parent.
- A single evaluation on 20 cases cannot carry a promotion: successors of one parent
  ranged from 4 to 8 of 20.
- Nothing here bears on repair without a model. The local operators remain at zero on
  the held-out cases T1 has run so far.

## Cost and records

Model spend: 1.11 USD for LINEAGE1, L1 and the improver comparison; 1.27 USD for
LINEAGE2. Records: `experiment/bench/LINEAGE1`, `experiment/bench/LINEAGE2`,
`experiment/bench/TRIAL_L1_PREREG.json`, `experiment/bench/TRIAL_L1_RESULT.json`.
`scripts/audit_repair_lineage.py` recomputes every decision and total from the stored
records; it reruns nothing and is not an independent replication. T1 remains unsealed
and was not touched.
