# An improver applied to itself — 11 October 2026

Anthony directs that recursive self-improvement be demonstrated as generally as possible,
the architecture and the language being free to change. DEV_REPAIR_INTERVENTIONS1 showed
that on program repair the model, not the machinery around it, decides the outcome. Under
the standing PUBLIC_AGPL_COMMERCIAL_OPTION decision, publish a bounded mechanism in which
the object improved is the improvement procedure itself: an improver is a program that
returns a better program for a scored task; one task asks for a better improver and scores
it by what it achieves on ordinary tasks; each generation is the current improver applied
to its own source, judged by the host on fresh tasks under a rule fixed in advance, with
one fixed model reached only through a counted channel.

Review precedes the first run. AI development assistance is as recorded in
`docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`; every improver after the seed is written by
the model at the request of its parent and is recorded with its calls. Prior art is
acknowledged and no novelty is asserted over it: self-applied scaffolding programs
(Zelikman et al., "Self-Taught Optimizer", 2023), program search with a scoring function
(Romera-Paredes et al., "FunSearch", 2023), and the classical problems used as tasks. No
third-party code is copied; the container image is the public `python:3.12-slim`, pinned
by digest. Software AGPL-3.0-only; prose follows LICENSE_POLICY.md. No patent-first,
trade-secret, confidential-third-party or embargo reason identified.

Safety boundary: model-written improvers and programs run only in containers without
network, read-only, without capabilities; the host never executes them; model requests are
counted and bounded by the host whatever the container claims; the model, its answer size
and the spending ceiling cannot be changed from inside. No frozen experiment changes. No
held-out Defects4J case and no reserve case of the external catalogue is involved. No
general RSI claim follows from the mechanism; what would count as evidence is fixed in
`docs/SELF_IMPROVER_PROTOCOL_2026-10-11.md` before any lineage runs.
