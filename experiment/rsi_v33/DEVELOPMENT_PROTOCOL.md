# V33 consumed-data development, declared before its first run

Evaluate all four gain margins `(0, 25, 50, 100)` with the adaptive arm and all
four controls at margin zero. Use every consumed V31 population (101, 211, 9143,
27189, 40733) and every consumed V32 population (72859, 109987, 154873), 456 tasks
per variant. Preserve all complete episodes, failures, charges and summaries.
Use the nonisolated development mode only here. No V33 fresh task is executed.

Choose the adaptive margin lexicographically by solved count, summed best quality,
negative charged evaluations, then smaller margin. No other implementation or
bank choice is selected by this sweep. The complete immutable development file
binds source bytes, all variants and population bytes. Code changes after observing
this sweep require a separately labelled development successor, never replacement
of the original archive. Apparatus and separate prospective freeze precede fresh
isolated behavior.
