# A5 three-language retained-strategy transfer — 2026-10-06

**Development verdict: PASS**

Genesis has now reused the retained `integer_delta` repair strategy across
three language families with **zero external LLM calls**:

- JavaScript — A2
- Python — A3
- C# — A5

## Preserved negative carriers

A5 did not discard tasks that the retained strategy could not honestly solve.

### Rust — FuelLabs/fuelup#836

The frozen issue required coordinated changes in two retry loops. The current
single-site retained operator could not produce a semantically valid repair.
No candidate was charged and the carrier was preserved as a negative result.

### Java — ledger-lite#3

The defect required replacing floating-point/`Math.floor` fee computation
with `BigDecimal`, percentage math and `RoundingMode.HALF_EVEN`.
`integer_delta` could not express that structural rewrite. The carrier was
preserved rather than receiving a task-specific operator.

## Positive C# carrier

- repository: `JoshuaRamirez/RoslynMcpServer`
- frozen commit: `46f6fe0bc96e845d5b5cae2318cbf8d335d9b4e3`
- public issue: #724
- defect: depth-of-inheritance undercounted the `System.Object` root
- retained operator under test: `integer_delta`

The frozen baseline failed the issue objective.

The frozen scalar generator produced **105** candidates in the issue-named
source file. Retained-memory ordering searched `integer_delta` candidates
first.

After **37 charged candidate executions**, Genesis found:

```diff
- var depth = 0;
+ var depth = 1;
```

Candidate:

- id: `scalar-35a14e4b56eaccbb`
- digest: `35a14e4b56eaccbb4d4462e74eb197490f1dbe0901eeca2c9d0b727108ab46cb`
- operator: `integer_delta`

The frozen issue objective passed, and exact replay passed.

## Relevant regression validation

The exact generated winner was then replayed in a fresh workspace against:

- the frozen A5 depth-of-inheritance objective; and
- the repository's existing `GetCodeMetricsOperationTests`.

Result:

- **17 passed**
- **0 failed**
- restore: pass
- external model calls: **0**
- manual candidate repair: **none**

Canonical A5 result digest:

`d40fe24cff8f7fa901b4f6ca30a4fd58266fb203293d40dd7bb941665c717e68`

## Preserved apparatus abort

The first C# run aborted before semantic baseline execution because the carrier
pins .NET SDK 9.0.308 while the VPS exposed .NET 10 only.

That run is preserved. V2 side-installed the exact requested .NET 9.0.308 SDK
without changing repository source, task objective, candidate generation or
winner rule.

## Claim boundary

This establishes **A5 DEVELOPMENT PASS** under the current autonomy ladder:
one retained zero-LLM repair strategy has transferred successfully across
JavaScript, Python and C# external/public carriers.

It does not establish general multi-language repair. The negative Rust and Java
carriers are important evidence of the current boundary.

A6 is next: a prospectively frozen multi-repository campaign must show that
external-LLM fallback demand actually decreases under repeated autonomous work.
