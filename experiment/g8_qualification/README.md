# G8 scientific qualification

Status: **`G8_SCIENTIFIC_GATE_PASSED` under the preregistered project-defined criterion.**

Frozen chronology:

- `2afad013` — distillation and evaluation apparatus;
- `83655749` — distilled local specialist frozen before holdout generation;
- `e018a588` — prospective G8 qualification frozen before reveal;
- `01fd7f60` — positive result and revealed holdout/seed.

Fresh result:

- external Claude baseline: **7/8**, 8 external-model calls, `$0.2300264`, ~7.8365 s/solved task;
- distilled local specialist: **8/8**, 0 external-model calls, `$0`, ~0.03183 s/solved task;
- empty-specialist ablation: **0/8**;
- all frozen qualification predicates: **17/17 true**.

The single external-baseline miss was a correct semantic patch rejected by the frozen relative-path safety boundary. Crediting it would make the baseline 8/8 but would not alter the calls/cost efficiency conclusion.

Holdout SHA-256:

`ab7408a9bbc7cfbd12e8f4238422af190ee20d3df757d4c9f4ed42063db66df9`

See `docs/G8_QUALIFICATION_2026-10-07.md` for the exact claim boundary.