# L9-OE1 — persistent open-ended research loop

OE1 changes the unit of evolution from a single strategy/recipe to an **improver**:
a policy that controls retrieval, search, replay, parent selection and curriculum.

## Core loop

1. Real executions append tasks, candidate nodes, search edges and evaluations to the
   persistent ExperienceStore.
2. The replay engine evaluates many mutated improvers against already-observed discovery
   graphs without calling the real evaluator again.
3. The unstructured QD archive preserves high-quality but behaviourally different
   improvers instead of collapsing onto one lineage.
4. Parent selection rewards quality, novelty and recent learning progress while penalising
   over-explored parents.
5. The curriculum generator proposes tasks at the empirical competence frontier.
6. Only replay winners earn new real executions. Fresh L9 adjudication remains separately
   frozen and cannot be used for tuning.

## Storage

Tests use SQLite. The VPS uses a dedicated PostgreSQL container on
`127.0.0.1:55432`; it is intentionally isolated from Mira and BrewTrack databases.

Example DSN:

`postgresql://genesis:<password>@127.0.0.1:55432/genesis`

Install PostgreSQL support with:

`pip install -e ".[dev,oe]"`

The database is **experience**, not evidence. Prospective populations and their freeze
files remain immutable repository artefacts. A fresh evaluation may read only the
experience explicitly allowed by its frozen protocol.
