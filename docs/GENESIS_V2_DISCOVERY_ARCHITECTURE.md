# Genesis V2 — Autonomous Discovery Core

**Executable research prototype, NOT a validated RSI system.**

V2 is isolated on branch feat/genesis-v2-discovery-core, based on the existing
experimental branch. It changes no V1 service or production policy by default.

## Architectural inversion

V1 asks which prewritten mutation to try. V2 asks which part of its own search
policy should be altered and how to test whether the descendant really helps.

                 IMMUTABLE TRUST ROOT
     +------------------------------------------+
     | Admission / budgets / independent judge  |
     | Frozen evaluations / promotion authority |
     +------------------------------------------+
                    ^           |
          test receipts         | admitted tasks and features
                    |           v
     +------------------------------------------+
     |            V2 DISCOVERY CORE             |
     | Genome -> bounded self-mutations         |
     |            -> population comparison      |
     |            -> retained training lineage  |
     |            -> opt-in live proposal order |
     +------------------------------------------+
                 ^                 |
          experience store         v
                           language / reasoning tools
                           -> source candidates

The trusted evaluator, limits and adoption decision are outside the mutable
genome. This first genome is a five-feature, bounded integer policy (not
arbitrarily executable source). Its decisions are cryptographically identified
and linked to their parent. It cannot amend the evaluator, run code, alter
tests, introduce new mutation operators, or select hidden solutions.

## Construction components

- genesis/v2/genome.py: typed bounded genome, self-generated mutations and
  parent digests.
- genesis/v2/traces.py: convert nine already released G11 cases into a
  provenance-checked common pool of only previously evaluated candidates.
  Export no source patches.
- genesis/v2/discovery.py: two-generation bounded tournament, full-suite
  success as the primary objective, compilation as a secondary proxy.
- genesis/v2/gates.py: trusted promotion refusal for exposed cases.
- genesis/v2/live_adapter.py: optional real planner reranking of already
  generated candidates, without modifying proposal source.
- scripts/run_v2_discovery.py and scripts/run_v2_assessment.py: deterministic
  reproducible retrospective evidence.
- tests/test_v2_*.py: corruption and boundary tests, equal budgets, actual
  planner integration, synthetic evolution examples, V1 nonregression.

V1's repair strategist accepts optional v2_discovery_genome. Without it,
the planner has unchanged candidate order and strategy digest. V2 cannot
currently be combined with G12 reserved probe slots or compiler preflight.

## First retrospective development result

Nine **previously examined** Defects4J projects supply 191 distinct,
actually evaluated proposals. No additional program executions or human
patch inspections occur in this retrospective comparison. The corpus is
already exposed: no evaluation here counts as a new independent holdout.

Six projects used for training:
Math-53, Csv-16, Collections-24, Gson-2, Jsoup-68, JacksonCore-11.
Three old projects used only for a development check:
Cli-34, Time-22, JxPath-12.

Genesis evaluated 20 self-proposed genome variants, retaining two successive
weight mutations: atomic +1, then non_modifier +1.

Metric                              Seed       V2 descendant
Compilation pass, training           19              35
Compilation pass, dev check          16              21
Complete repaired bugs, dev check     0               0
New independent repair successes      0               0

On Cli the result was 0 -> 6, on Time 8 -> 8, on JxPath 8 -> 7.
There is a **per-project regression**. The independent development gate
explicitly refuses promotion for exposed cases, zero new full-suite repairs
and regression. The +5 compilation result is a narrow engineering signal,
not proven better general repair performance or general RSI.

This is offline reranking of the union of previously tested candidates from
both old arms. It does not predict success of untested candidates or claim
that V2 proposed repairs for new bugs.

## Next steps

V2.1: create a typed, compiler-checked semantic hypothesis and transformation
language, enabling proposals BEFORE a winning patch is known.
V2.2: let Genesis propose bounded changes to its own diagnosis/search
subsystems, tested in isolated worktrees with rollback and resource quotas.
V2.3: preregister fresh external tasks and compare V1, V2 reordering only,
and V2 with genuinely new transformations on equal candidate/test budgets.
V2.4: require multiple prospective self-proposed *mechanism* generations
which improve the next improvement process and outperform the frozen parent
on independent holdouts, with ablations and no hidden-test leakage.

Do not restart the stopped ER3 systemd campaign without its repaired guard.
Do not reuse exposed ER4 Lang cases as clean holdouts. No merge to V1 until
CI and independent prospective validation. No arbitrary generated execution
inside the trusted host.
