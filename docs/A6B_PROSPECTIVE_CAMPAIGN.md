# A6b prospective campaign

**Status: PRE-REGISTERED BEFORE FRESH TASK INSPECTION**

A6b is the prospective successor to the failed A6 campaign.

The search apparatus is frozen at commit `d131b731`. Development calibration
on old A6 tasks showed that the new scheduler can recover a candidate that A6
starved outside budget and can causally compose a template learned on one task
into a two-file repair on the next. Those old tasks are excluded from evidence.

Fresh A6b tasks are taken sequentially from the already-frozen metadata queue,
starting at queue index **17**. Issue bodies and source are inspected only after
the candidate is frozen. Pre-outcome qualification failures are preserved.

A6b again targets 12 runnable tasks in three waves of four. The autonomous arm
gets 256 candidates and zero model calls. Claude Sonnet 5.5 remains a one-call
fallback only after autonomous exhaustion.

A6b passes only if fallback dependence is prospectively lower, at least five
tasks are solved autonomously, and at least two autonomous wins causally use
prior evaluated experience, including at least one experience learned during an
earlier A6b task.

A7 remains blocked until this gate passes.
