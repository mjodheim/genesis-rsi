# A4 repository-evidence strategy acquisition — 2026-10-06

**Development verdict: PASS**

Genesis acquired a new reusable edit strategy from repository evidence plus
evaluator selection, with **zero external LLM calls**.

## Why A4 exists

A3A exposed a concrete expressivity gap. The frozen scalar grammar could not
produce the primary repair needed for `chris-monahan/tictactoe#4`:

```js
currentArray[xPos]
```

needed 1-based index arithmetic, while the old grammar could only mutate
integer literals, boolean literals and comparison operators.

That failure was preserved rather than patched by hand.

## Acquisition substrate

A4 adds a generic repository-exemplar learner. It does not contain the
issue-specific rule “subtract one from xPos”.

Instead it:

1. mines adjusted subscript expressions that already exist in the repository;
2. finds analogous plain subscript expressions using the same identifier;
3. proposes reuse of observed structural variants;
4. lets the frozen evaluator decide whether a candidate is useful;
5. distills a successful candidate into an identifier-agnostic strategy.

For the frozen carrier, Genesis observed an existing `[xPos - 1]` pattern
elsewhere in `GridState.js` and proposed that observed form at the plain
`[xPos]` site.

## Old-grammar ablation

The frozen A2 scalar grammar generated **970** candidates on the carrier.

Candidates capable of producing the required
`currentArray[xPos - 1]` edit: **0**.

So the A4 winner was not already expressible by the old repair grammar.

## Baseline

The direct frozen evaluator exercised the primary one-based coordinate
semantics plus regression checks.

Baseline:

- `getColumn(1)` returned column 2 values;
- `getColumn(4)` returned out-of-range/null values;
- all non-target regression checks passed;
- primary objective: **FAIL**.

## Acquired candidate

The repository-exemplar generator produced exactly **1** candidate:

`observed_subscript_delta:src/GridState.js:7206:-1`

Its provenance records:

- generator: `repository_exemplar_mutations`
- origin: `repository_observation`
- observed delta: **-1**
- external-model calls: **0**

The candidate passed the primary objective and every frozen regression check,
then passed exact replay.

## New retained strategy

Genesis distilled the winning observation into:

```text
before: [$IDENT]
after:  [$IDENT - 1]
```

Strategy digest:

`709d7b24a453bf28e9b4bdba03ecf2637d4039bbae57cce4a1f929076fd9032b`

Result digest:

`b0eb7064ffea38f618bdca26ec37dd5dca523321e929dd953c9152b3d102ef82`

The identifier has been abstracted away: the retained strategy is not tied to
`xPos`.

## Preserved evaluator abort

A4 V1 attempted to use the repository's react-scripts/Jest path, but the
frozen dependency graph loaded Babel 7.19.6 with a plugin requiring >=7.22.
No semantic test executed.

That run is preserved as an **APPARATUS_ABORT**. V2 changed only the evaluator
transport: it loads the same frozen source deterministically through Node's VM
and executes the frozen primary objective/regression checks. Candidate
generation and the acquisition mechanism were unchanged.

## Claim boundary

This establishes **A4 DEVELOPMENT PASS** in the current autonomy ladder:
Genesis acquired one new reusable transformation template from observed
repository structure and evaluator feedback rather than receiving that
issue-specific repair as host-authored code.

This is **not** unrestricted program synthesis. The exemplar-mining substrate
is still host-engineered, the A4 objective covers the primary indexing defect
rather than the issue's separate ordering concern, and the acquired strategy
still needs held-out transfer testing.

That held-out transfer is part of A5.
