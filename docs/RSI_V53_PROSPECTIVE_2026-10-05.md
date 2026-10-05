# RSI V53 — prospective selective-scaffold assay — 2026-10-05

## Frozen apparatus

V53 was frozen before the first prospective behavioral execution.

- freeze SHA-256: `35ae3edca283d1fcc6e0431e55f09796e7312fd3d96209e3176eb05170d43bfc`;
- population SHA-256: `151d1a027440ac713f91ddbafabee37b2847d99599386e7aa95aeffc2793a68a`;
- seeds: 530061, 530062, 530063;
- 14 windows per seed;
- widths 3 through 16;
- 12 tasks per window;
- 504 total tasks;
- inherited cap: 14 charged evaluations per task;
- isolated execution;
- selective rotation scaffolds: top-k 2, width >= 10, root quality <= 799;
- exact compatible memory remains authoritative;
- when a scaffold is active it replaces whole-recipe abstraction rather than widening the root population.

The campaign ran from an exported snapshot of the frozen commit. No threshold,
seed, gate, top-k or task budget changed after prospective execution began.

## Aggregate prospective result

| Condition | Solved | Charged evaluations |
|---|---:|---:|
| **V53 selective scaffold** | **191 / 504** | **5,538** |
| V52 abstraction memory | 177 / 504 | 5,670 |
| V32 adaptive archive | 175 / 504 | — |
| V51 structured memory | 173 / 504 | — |
| Cold G7 | 171 / 504 | — |

V53 therefore produced:

- **+14 solved tasks vs V52**;
- **+20 solved tasks vs cold**;
- **132 fewer charged evaluations than V52**;
- 117 evaluated scaffold candidates;
- 8 direct scaffold solve gains vs V52;
- **0 direct scaffold solve regressions**.

The fact that aggregate gain (+14) exceeds direct scaffold solve gain (+8)
indicates a cumulative downstream effect: solutions reached through scaffolds are
remembered and influence later search.

## Per-seed result

### Seed 530061
- V53: **65 / 168**, 1,824 evaluations;
- V52: 61 / 168, 1,862 evaluations;
- cold: 58 / 168;
- archive: 60 / 168;
- all 14 windows retain positive first discovery;
- both new horizon windows 12 and 13 remain positive.

### Seed 530062
- V53: **59 / 168**, 1,885 evaluations;
- V52: 53 / 168, 1,939 evaluations;
- cold: 51 / 168;
- archive: 51 / 168;
- zero first discovery in windows 9 and 13.

### Seed 530063
- V53: **67 / 168**, 1,829 evaluations;
- V52: 63 / 168, 1,869 evaluations;
- cold: 62 / 168;
- archive: 64 / 168;
- zero first discovery in windows 12 and 13.

## Frozen adjudication

Passed:

- all committed tasks retained;
- V53 aggregate solved > V52;
- V53 aggregate solved > cold;
- V53 aggregate cost <= V52;
- no seed drops below cold;
- scaffold routing exercised on every seed.

Failed:

- every seed/window retains positive first discovery;
- both new horizon windows remain positive on every seed.

Therefore:

```text
scoped_sustained_scaffold_assay_passed = false
l9_general_open_ended_passed = false
verdict = VALID_NEGATIVE_SCOPED_SUSTAINED_SCAFFOLD_ASSAY
```

## Interpretation

V53 provides the strongest sustained-development evidence in the L9 programme so
far. Learned components can causally seed later search at greater widths while
improving both solved count and cost. One prospective seed sustains positive
first discovery across the full width-3-to-16 horizon.

The remaining failure is concentrated in late-window novelty exhaustion. V54
should therefore test **recursive scaffold provenance**: descendants that owe
their success to a scaffold should become explicitly marked scaffold descendants
and be eligible to seed later scaffolds. The causal question is whether this
second-order reuse keeps discovery positive where V53 still exhausts, without
increasing the inherited task budget.

Raw evidence:
`results/rsi-v53/prospective-scaffold-20261005/REPORT.json`
(SHA-256 `fecbb8f2407263cd2dbad7877996fe1a2c893bfe3d6f956aac31a634a2027792`).
