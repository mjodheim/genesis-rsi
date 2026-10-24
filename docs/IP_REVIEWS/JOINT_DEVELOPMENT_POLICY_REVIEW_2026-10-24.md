# Joint bounded development-policy pre-publication review

**Decision date:** 24 October 2026

**Disposition:** `PUBLIC_AGPL_COMMERCIAL_OPTION`

**Scope:** DEVELOPMENT only

## Asset

This review defines an inert, content-addressed policy artifact that Genesis can vary and that a
separate consumer such as Mira can validate. The policy may only order an explicit allowlist of
previously admitted deterministic repair rules and set finite candidate/file budgets. It contains
no source code, prompt, shell command, model output, hidden evaluation or authority token.

Genesis may compare policy descendants from externally supplied outcome records under equal case
and candidate budgets. Promotion requires a strict lexicographic gain, complete matched evidence
and an independently computed artifact digest. The selector does not execute candidates and does
not own the verdict.

## Provenance and third parties

Anthony Mets directs and accepts the work. OpenAI Codex provides design, implementation, test and
documentation assistance as tooling. The Genesis implementation is limited to the Python standard
library and the repository's existing pytest development dependency. It imports no private Mira
implementation or result data.

## Security and publication boundary

- Policy fields are closed and bounded; unknown fields, rules and digest mismatches are rejected.
- Artifacts contain no executable commands and grant no filesystem, network, credential, evaluator,
  repository or deployment authority.
- Evaluation observations are inert booleans/costs attributed to an external judge.
- The public repository receives only its own implementation, tests and synthetic interoperability
  vectors. Private Mira code and operational data remain outside this repository.
- No confidential, patent-first, contractual or security-sensitive reason for private treatment was
  identified before implementation.
- `IP_ASSET_REGISTER.md` is a frozen V25 input and remains byte-identical. The disposition is entered
  in `REPAIR_REGISTER_ENTRIES_2026-10-09.md`, the established post-freeze successor ledger.

## Claims boundary

A passing implementation can establish canonical cross-runtime exchange, bounded policy mutation,
matched-budget selection and refusal of malformed evidence. It cannot establish senior software
engineering, general program repair, invention outside the admitted policy language, recursive
self-improvement, AGI or general RSI. Those require prospective external tasks and independent
judgement beyond this mechanism.
