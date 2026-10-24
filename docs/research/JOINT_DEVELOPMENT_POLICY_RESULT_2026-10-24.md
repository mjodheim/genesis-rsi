# Joint bounded development-policy result — 24 October 2026

## Result

Genesis now owns a content-addressed, lineage-bound DEVELOPMENT policy for an
allowlisted no-model repair consumer. A policy can reorder five admitted repair
rules and vary a candidate budget from one to eight. It cannot contain source,
commands, prompts or new operations. The one-step descendant generator is
finite and deterministic.

The selector consumes only externally attributed observations. It requires the
same named cases and candidate budget for the parent and every descendant,
rejects incomplete or duplicate evidence, then adopts only a strict
lexicographic gain in passed cases, false positives and candidate use. Its
selection certificate binds parent, selected artifact and evidence digests.

The public interoperability vector is reproduced by the separate Mira C#
consumer: the canonical generation-zero policy has SHA-256
`822339855399daf1c3e2cb73e9777d225e7b96bf079b45861d1bb79b8bac58e1`.
This repository contains neither Mira source nor private evaluation data.

## Validation

- five focused Genesis tests pass;
- the shared canonical JSON and digest reproduce in Python and C#;
- malformed fields, invented executable authority, digest drift, unmatched
  budgets, incomplete cases and absent judge identity are negative controls;
- a three-case synthetic DEVELOPMENT fixture promotes a strict improvement
  from score `(1, -1, -10)` to `(2, 0, -4)` under the same four-candidate
  ceiling. This validates selection mechanics, not repair generality;
- Mira separately validates baseline refusal, deterministic ranking, retained
  verified changes and exact rollback.

## Relation to more advanced systems

[GenProg](https://doi.org/10.1109/TSE.2011.104) demonstrates test-suite-guided
generate-and-validate program repair. This work keeps that external-verdict split
but deliberately exposes a much smaller transformation language.
[STOP](https://arxiv.org/abs/2310.02304) applies an improver to itself while
not claiming full recursive self-improvement. This work likewise separates a
mutable policy from fixed apparatus, but uses no model and requires a strict
external promotion gate. [Gödel Agent](https://aclanthology.org/2025.acl-long.1354/)
allows much broader self-modification through an LLM; this mechanism does not:
its closed schema and rule alphabet are intentional safety and attribution boundaries.

## Claims boundary and next gate

This work establishes a safe joint evolutionary interface, not general RSI. It
does not show invention outside the allowlist, transfer to novel bug families,
senior engineering or improvement of the selector. The next credible gate is
a prospective, independently judged multi-repository trial in which Genesis
selects policies on development cases and the frozen winner is evaluated once
on unseen repositories. Only after retained transfer should the mutation
language itself become a lineage-owned, evidence-gated artifact.
