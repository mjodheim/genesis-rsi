# G11 — Modular language understanding and portable learning

Status: **opt-in implementation and unit tests; NOT scientific proof of autonomous repair**.

## Architecture

1. **Language sensor (replaceable)**: Each language module provides its name,
   suffixes, versioned identifier, and an analysis function. Registry and
   normalized records: genesis/languages/understanding.py.
2. **Common abstract concepts (portable)**: type_declaration,
   function_declaration, if_control, call, return, assignment, subscript,
   etc., plus declared capabilities, diagnostics and fidelity. These concepts
   do not promise identical semantics across languages.
3. **Independent memory (persistent)**: genesis/languages/experience.py
   records portable source-structure patterns, module provenance, operator use,
   and explicit evidence *claims* in SQLite. Records carry chained digests.
   Original source text and human patches are not stored in this ledger.
4. **Repair strategist (opt-in)**: repair_strategist.generate accepts a
   registry and optional experience ledger. Candidate edits overlapping
   compiler-derived syntax/semantic nodes receive a small, bounded structural
   ranking prior **only when explicitly experimental**. The default G11 path
   observes and annotates candidates but leaves ordering and scores untouched.
   It does not generate new repair operators yet.

## Current fidelity

- Java: real JDK compiler AST, partial resolved types, symbol IDs, method call
  targets, branch ranges and variable accesses. Not yet a full CFG or def-use.
- Python: existing CPython AST substrate, not a fully typed semantic analyzer.
- C#, Rust, Go, TypeScript/JavaScript: existing conservative lexical/structural
  interpretation only, until compiler/LSP/Tree-sitter-based modules are built.
- Other languages: any module declaring extensions may be registered with
  the genesis-language-module-v1 normalized output schema (Ruby stub tested).
  Without a module, an unknown suffix is rejected instead of pretending
  universal comprehension.

Java compiler offsets are UTF-16 units; positional scoring is disabled for
non-ASCII sources until proper normalization is implemented. Unresolved
dependencies/diagnostics remain visible.

## Persistence and what "learning" means here

A module may be unregistered, or even removed, and the SQLite experience
database survives. Generic past use patterns can still be retrieved without
installing the module. **This retains observations, not the module's ability
to parse or compile its language.** In particular, the current ledger does
not yet demonstrate causal cross-language transfer.

The ledger never promotes observations to validated repair successes.
A full-suite success *claim* requires evaluator/freeze evidence digests and
is still marked reported-not-independently-verified. Successful repair must
be established by a trusted external experiment, not the plugin itself.

## Training-only opt-in

Run the Defects4J Lang script with the new optional arguments:

    --g11-understanding
    --g11-experience-db /path/to/training-only-observations.sqlite

The baseline with no flags remains unchanged for candidate planning. By
default the G11 flags also leave candidate scores/order unchanged: reranking
requires --g11-rerank-experimental, which has **failed the first 8-case
synthetic pilot**. G11 records a source-structure observation during training-only candidate planning;
it must not mutate held-out evaluation data. The 8 previously preregistered
ER4 Lang IDs are excluded from this training script at selection and prepare
time, including cases that were selected before the new guard.

The autonomous ER3 service remains deliberately stopped after previously
exposing 4/8 ER4 holdouts. Do not restart it until a genuinely clean
partition, input snapshots and fair A/B/C budgets are established.

## Next scientific engineering gates

- Confirm precise semantic binding across multi-file Java projects.
- Construct full control-flow and def-use summaries; validate against
  independently hand-labelled programs.
- Add trusted C# Roslyn, Python typed, Rust, Go and TS language modules.
- Separate observation counts from causal effectiveness and independently
  validated full-suite fixes. Test cross-language transfer on truly unseen
  examples while recording compute costs and failures.
- Never execute untrusted plugin code outside an isolated sandbox: installed
  adapters are trusted code in this first implementation.

## Small-language tests (2026-10-08)

Reproducible command:

    python3 scripts/g11_language_smoke.py > experiment/g11/G11_LANGUAGE_SMOKE_20261008.json

The smoke matrix used **18 synthetic examples** (6 language families x 3
scenarios: branch/call, comment/string decoy, malformed source). Of 14 checks
supported by current fidelity, **14 passed** after fixing two real false
positives: compiler-generated Java implicit constructor calls and a C# method
declaration misclassified as a call. The remaining **4 checks** (malformed
syntax in C#, Rust, Go and TS) are excluded from the pass rate because their
lexical mode cannot reliably validate syntax; their incidental diagnostics
must not be counted as comprehensive syntax validation.

- Java: JDK compiler-derived AST and partial semantic bindings.
- Python: CPython AST.
- C#, Rust, Go, TS: lexical only, sufficient for small source structures but
  not proof of semantic understanding.

This verifies instrumentation/signal accuracy on narrow synthetic cases.
**It is not a Defects4J repair result, nor evidence of cross-language
generalization, nor an improvement in validated fixes.**

## Security and performance modules (first prototype)

Cross-cutting read-only module registry: genesis/insights/registry.py.
Initially installed modules (each independently removable):

- security.python.ast-v1: dynamic eval/exec review, subprocess shell=True
  review, with AST matching (not string/comment matching).
- security.java.compiler-v1: compiler-resolved Runtime.exec review.
- performance.python.ast-v1 and performance.java.compiler-v1: nested-loop
  review; these flags are **not measured time complexity or speedups**.

Module outputs include fidelity, rule ID, source line, confidence, coverage
by domain, and explicit flags describing that problems and speedups are
not verified. No source code is executed. Files with insufficient language
fidelity are marked unsupported/insufficient, NOT secure or optimized.
Never treat zero warnings as a security audit clearance.

Reproducible read-only CLI on expressly named files:

    python3 scripts/g11_module_probe.py --language-compiler --security \
      --performance genesis/java_analysis/GenesisJavaAnalyzer.java \
      genesis/repair_strategist.py

Optional --experience-db /path/to/TRAIN-only.sqlite persists portable
observation patterns; do not attach evaluation holdout files to that DB.

experiment/g11/G11_DOMAIN_PROBE_20261008.json records this first local
probe: **2 source files analyzed; 3 informational nested-loop review hints
in repair_strategist.py, zero security hints**. These are not proof of a
slowdown or proof that the files are secure.

The repair planner accepts an opt-in domain registry alongside the existing
language registry and records review findings in strategy metadata. The
Defects4J Lang training-only CLI provides:

    --g11-understanding --g11-security --g11-performance

These switches are not enabled for the systemd service. The legacy planner
still produces the same output when no G11 switches are supplied. Experience
storage is likewise opt-in via --g11-experience-db.

### Scientific and safety boundaries

- Trusted modules are explicitly registered; arbitrary plugins are NOT
  loaded from inspected repositories. Current plugin code runs in the host
  process; isolate third-party plugins before supporting installation.
- Python AST warnings cannot establish taint; Java Runtime.exec matching
  cannot establish exploitability; static nested loops cannot establish poor
  performance. Confirmation requires appropriate tests, taint reasoning,
  independent security validation and actual benchmarks.
- The ER3 systemd campaign remains intentionally stopped to protect future
  holdouts. Four prior ER4 cases were contaminated.
- The observation ledger remembers usage after a module is removed, not how
  to execute the removed analyzer. Actual generalization and any recursive
  self-improvement remain to be shown.

## Controlled synthetic repair pilot — 2026-10-08

The preregistered, sealed synthetic Java pilot is documented in:
- G11_REPAIR_PILOT_PREREG_20261008.json
- G11_REPAIR_PILOT_RESULTS_20261008.json
- G11_REPAIR_PILOT_ANALYSIS_20261008.md

Under the equal top-24 validation budget, baseline solved 7/8 synthetic
bugs, whereas experimental Java understanding reranking solved 6/8.
Security and performance domain modules did not change patch ordering.
These are full assertion suites **only for the synthetic exercises**.
No proof of real-world autonomous repair or performance improvement.

**Post-pilot safety gate:** G11 analyzes/records in shadow mode by default,
without affecting candidate selection. Experimental ranking is available
only when explicitly requested. The JDK analyzer helper is compiled once
per Python process per analyzer digest to avoid redundant compiles; source
files are still analyzed independently and no hidden tests are cached.

The 8-case shadow regression confirmed identical candidate ordering to
baseline in all 8 cases and reproduced each original experimental ordering.
Original planning totals were 0.064s baseline and 12.816s understanding;
a post-fix replay measured approximately 0.067s baseline, 5.909s G11
shadow, and 4.905s experimental mode, in one process. These times were
measured in different runs, are not controlled CPU benchmarks and should
not be interpreted as statistically reliable speedups.
