# ER2 v3 — String-predicate literal equivalence closure

J11 revealed a missing atomic semantic capability: an OR-chain of repeated string
predicates did not close over obvious ASCII-case-equivalent literal variants.

ER2 v3 adds a source-local closure operator. It detects repeated calls to the same
receiver and method with related string literals and proposes missing ASCII case
variants. No NumberUtils, startsWith, hexadecimal literal, Lang-16, test, issue,
commit or line identity is encoded.

Validation: 7/7 focused tests passed. On consumed J11 evidence, the new primitive
alone produced a trigger-passing repair at planner index 200 with zero evaluator
errors and zero external model calls. J12+ remain fresh holdouts.
