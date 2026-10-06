# L9-OE1 v3 qualification — 6 October 2026

## Verdict

**L9_OPERATIONAL_GATE_PASSED**

Frozen post-run audit: **L9_OE1_V3_ARCHIVE_OK**

L9-OE1 v3 is the first retained successor certificate that combines the positive
operational L9 result with a closed transitive source manifest and independent
candidate-by-candidate native re-execution.

This closes the project's finite **operational L9 gate** under the prospectively
frozen criterion. It does not close L10 and is not a mathematical proof of
asymptotic open-endedness, general RSI or AGI.

## Prospective chronology

- v3 apparatus + fresh materialized population commit: `614ee1396d54728ef487973bcccb39c47cc02ec2`
- v3 freeze commit, pushed before first v3 behavior: `23681605`
- population seed: `86753243`
- population SHA-256: `e3a306c2de4815b1b0ae901639df15fa4e9c1d915bc2a5648216c97e084867d5`
- freeze SHA-256: `c418d25c260b7e89fb66b852d9096033134272a5ccf1c519cd61a79b9faf3250`
- exact population: 768 tasks/arm, 192/domain, 12 epochs/domain, 16 tasks/epoch
- arms: coded-archive, archive-G7, greedy-G7, cold-G7
- native call cap: 14/task

Neither the population, thresholds, mechanisms, source manifest nor audit rules
were changed after the v3 freeze.

## Frozen adjudication

Every one of the 16 frozen predicates passed, including:

- exact presence of all 16 arm/domain streams;
- exact ordered task IDs and hashes from the committed population;
- exact epoch-zero defaults, state recovery chains and terminal-state digests;
- all per-task call caps;
- candidate-level receipt consistency and explicit negative retention;
- coded transfer solve rate ≥95%;
- ≥90% coded solve rate and ≥4 first-solving semantics in every transfer epoch/domain;
- required aggregate and per-domain margins over all controls;
- coded evaluation cost no greater than archive-G7;
- four learned motif parents/domain and persisted 2–10-block codebook descendants;
- rediscovery in every coded transfer epoch/domain;
- terminal coded-state/codebook regeneration.

## Aggregate transfer result

| Arm | Transfer solve rate | Transfer evaluations |
|---|---:|---:|
| coded-archive | **100.00%** | **5,368** |
| archive-G7 | 11.98% | 7,105 |
| greedy-G7 | 1.39% | 7,412 |
| cold-G7 | 0.00% | 7,488 |

The coded arm retained 144 newly first-solving transfer semantics and 320
rediscoveries. The full archive retains 31,153 negative candidate receipts.

## Independent frozen audit

The audit implementation itself was included in the pre-behavior freeze.

After the campaign it:

1. verified the compressed and raw evidence hashes;
2. verified the closed 20-file transitive apparatus manifest and exact population;
3. re-adjudicated all 16 streams from candidate-level evidence;
4. independently re-executed **33,215 retained candidate receipts** using the frozen
   native implementation;
5. rebuilt and compared every evaluator receipt;
6. re-verified each terminal coded codebook.

Final audit receipt: `L9_OE1_V3_ARCHIVE_OK`.

No retained candidate produced a native-output or evaluator-receipt mismatch.

## Evidence integrity

- raw report size: 90,527,763 bytes
- raw report SHA-256: `e61b0f0a019835ba24e55c80e6610bdaa05cb0d474ece9104bfe4b98e0d3e6e9`
- deterministic gzip SHA-256: `7043db928789e995426d4e8fb6578bc0c9ba8c66d033b5cd5bc8375d9e343bea`
- archived report: `results/l9-oe1/v3-qualification-20261006/REPORT.json.gz`
- machine-readable summary: `results/l9-oe1/v3-qualification-20261006/SUMMARY.json`
- audit receipt: `results/l9-oe1/v3-qualification-20261006/AUDIT.json`

## Why v3 supersedes v2 as the closure certificate

V1 and v2 remain preserved as historical evidence. V3 was created rather than
retroactively altering v2 after review identified two certificate weaknesses:
the v2 source freeze did not bind the entire transitive execution chain, and the
v2 archive audit did not independently re-execute each retained candidate.

V3 addresses both prospectively on a new population. The positive v2 result is
therefore not rewritten; v3 is the stronger closure certificate.

## Claim boundary

This is finite, project-authored empirical evidence for the project's operational
L9 definition. **L10 remains open** and requires separately governed independent,
private or externally authored replication.
