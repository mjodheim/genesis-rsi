# Real-bug feedback ablation — 9 October 2026

The protocol and apparatus were committed before execution in `5c621f41`.
Artifacts are in `experiment/bench/DEV_REPAIR_FEEDBACK1`. This is an exposed
development pilot, not a held-out generality test. Both arms use the same seed
configuration and external Haiku model; only application feedback is enabled
for the child. Two repetitions on three bugs give six paired case-runs.

| Measure | Parent | Feedback child |
| --- | ---: | ---: |
| Repaired case-runs | 4/6 | 4/6 |
| Model requests | 20 | 20 |
| Validated candidates | 8 | 11 |
| Inapplicable submissions | 0 | 0 |
| Known API cost, USD | 0.022629165 | 0.021062630 |
| Sum of arm elapsed seconds | 367.7 | 537.8 |

Mockito-17 and Jsoup-54 pass triggering tests and the full suite in both arms
and repetitions. Mockito-23 remains unsolved in all four attempts. There are no
paired gains or losses. Total API cost is USD 0.043691795, below the USD 0.20
ceiling, with no unknown-cost calls. Baselines have no tolerated extra failures.
Elapsed arm times include model/compile/test work, exclude initial baseline
preparation, and are not a monetary estimate of infrastructure cost.

The parent has one recorded truncated model response in Mockito-23 repetition 2;
the request is charged and the failed arm is retained. There was no provider
404 or interrupted execution in this pilot. No arm exceeded eight requests or
six validations. Verification matches all forty call-journal entries against
arm receipts and recomputes the paired summary. This is stored-record verification,
not independent replication or proof that passing the benchmark is semantic correctness.

## What this result does and does not identify

The new correction path was never triggered: every submitted edit was applicable.
The small API-cost difference cannot demonstrate an economic benefit of the feedback
mechanism. Model sampling varies between calls, and more validations made the child
slower in this run. The acceptance condition for a larger test is not met. No active
policy is promoted and the canonical experience memory remains at 292 events.
Successful patches and test verdicts are retained in the experiment artifacts;
they are not presented as newly acquired autonomous repair skills.

The child trace for Mockito-23 repetition 1 identifies a more useful development
question. Two edits to ReturnsDeepStubs move the serialization failure to
DelegatingMethod. A candidate modifying DelegatingMethod alone encounters
ReturnsDeepStubs$2 again. Each candidate starts from the original buggy tree.
The current one-file representation prevents combining these observed edits in
one transaction. This does not establish that every valid repair needs multiple files.

A read-only inspection of the buggy production tree, without consulting a fixed
revision, also finds that MethodInterceptorFilter selects SerializableMethod when
mock settings enable serialization. ReturnsDeepStubs builds the child mock settings.
This suggests investigating settings propagation and captured state before changing
the class named in an exception. That interpretation is Codex-assisted post-result
analysis, not a solution generated or validated by Genesis.

## Next development boundary

Keep the negative result. The next useful substrate should let the agent express
coherent edits, retain partial-repair observations and trace dependencies from an
exception to the settings or state that caused it. Bounded multi-file transactions
would need atomic application/restoration and the same external compiler/test judge;
they must not merely disable or weaken failing tests. A source dependency explanation
must remain a hypothesis until execution validates it.

The cumulative descendant-history mechanism is not exercised by this fixed-genome
ablation. Its separate evaluation, and mutation of executable solver modules, remain
outstanding. Future pilots must be frozen prospectively; this result must not be
relabeled as a successful RSI generation.
