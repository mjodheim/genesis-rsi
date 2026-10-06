# A3 causal retained-strategy reuse — 2026-10-06

**Development verdict: PASS**

Genesis retained the successful strategy signal from A2 and causally reused it
on a fresh external public task with **zero external LLM calls**.

## Prior experience retained

A2 produced one unique successful operator:

- source result digest:
  `f36ca5c56023e5cabbe1b23ef489a18a949438ea50268eb3edd08ce3b4eaf6aa`
- successful operator: `integer_delta`
- retained-memory digest:
  `9be25ef2ab02a706934d0744d68e4065df060677d0327d8a26648319497fdc79`

The A3 memory does not encode a new issue-specific fix. It stores only the
operator identity that previously succeeded and uses that as a ranking prior.

## Preserved carrier mismatches

A3 did not silently cherry-pick the first task that worked.

Four prospectively frozen carriers were retained before the positive result:

1. `chris-monahan/tictactoe#4` — primary fix required identifier index
   arithmetic outside the frozen scalar grammar.
2. `Pranav-Singh-Devloper/harness-demo-bookshop#1` — changing the scalar
   literal alone fixed exact multiples but broke the existing partial-page
   behavior; a structural ceil expression was required.
3. `BenjaminSRussell/cozy-game#112` — frozen carrier did not contain the
   stated failing implementation, so the baseline was not reproducible.
4. `Changyi-Li/dsh-github-issue-agent-scratch#2` — issue body and frozen
   source showed the title-level baseline was already correct.

Those records remain in `experiment/autonomy_a3/A3*_REJECTED.json`.

## Positive carrier

- repository: `caorantaoyao/mm-truncate`
- frozen commit: `53bdc652b0e8c5879158b9cc3927e9bddbba3a00`
- public issue: #1, “truncate() off-by-one returns one extra character”
- language: Python
- evaluator: repository-owned tests only
- baseline: **1 failed, 1 passed**

The defect was:

```python
return text[: max_len + 1] + "..."
```

The frozen generic scalar grammar generated six candidates. The unique useful
candidate retained the mechanically generated form:

```python
return text[: max_len + 0] + "..."
```

No human cleanup to `text[:max_len]` was performed.

## Causal ablation

Both arms received exactly the same six candidates and exactly the same frozen
repository test evaluator.

Without retained memory:

- first passing candidate rank: **5**
- charged executions to success: **5**

With A2 retained strategy memory:

- first passing candidate rank: **1**
- charged executions to success: **1**

The same candidate moved from rank 5 to rank 1 solely because
`integer_delta` had succeeded in A2. Exact replay passed again.

That is a **5× reduction in charged search executions** on this task.

Canonical result digest:

`1956f8c7ff25d4f452025c488c1bff744e5546ea64fce1265d938410eae40464`

## Claim boundary

This establishes **A3 DEVELOPMENT PASS**: a strategy signal learned from one
zero-LLM external repair causally improved search on a fresh external task.

It does not yet show that Genesis can invent a new transformation family.
The underlying scalar operators are still host-authored. A4 is therefore the
next critical gate: Genesis must acquire a new transformation strategy from
observed evidence/results rather than receiving that repair operator from host
code.
