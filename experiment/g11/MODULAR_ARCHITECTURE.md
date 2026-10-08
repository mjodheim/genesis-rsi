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
   ranking prior. It does not generate new repair operators yet.

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

The baseline with no flags remains unchanged for candidate planning. G11
records a source-structure observation during training-only candidate planning;
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
