# Genesis V2.1 — New-project repair examination, reconciled

Date: 2026-10-08. Experimental branch: feat/genesis-v2-discovery-core.

## Selection and frozen experiment

Chart-23, JacksonXml-4 and Mockito-22 were selected from three new
Defects4J projects by a deterministic seed, then committed before opening
their buggy code. Public Defects4J projects are not guaranteed unseen by
foundation models, but these bugs were not part of the prior Genesis
G11/G12 test or development corpus.

The V1 and V2.1 semantic-DSL arms each generated at most 96 proposals and
each selected the first eight for test, with the same source focus and
budgets. The code policy was locked at revision
bdc2b6199ecd48331fbf36b65acd09196e7190c6. All candidate hashes for
all cases and both arms were frozen and committed before any candidate
validation.

## Scientific result after infrastructure correction

| New bug | V1 compilable / 8 | V2.1 compilable / 8 | Full repairs |
|---|---:|---:|---:|
| Chart-23 | 8 | 8 | 0 |
| JacksonXml-4 | 7 | 7 | 0 |
| Mockito-22 (corrected evaluator) | 8 | 8 | 0 |
| Total | 23/24 | 23/24 | 0/3 |

Both arms produced exactly the same ranked candidate indexes.
V2.1 proposed ZERO new semantic hypotheses across the three projects.
Every patch that compiled still failed an original public trigger. There
was no positive full-suite candidate and no repaired bug.

## Preserved error and correction

The original trial falsely marked eight Mockito patches as compile
failures. The validator copied projects with a blanket directory ignore
pattern named build. This accidentally omitted Mockito's required
lib/build dependencies; a pristine unmodified project could not compile
inside the isolated candidate validator. Therefore those original eight
compile-failure claims are INVALID.

The original report and freeze were not overwritten. An explicit signed
amendment was committed before any retest. A validator that retains nested
build directories compiled the unchanged project successfully as an
isolation positive control. The exact original eight candidate hashes
were then retested: eight compiled, and all eight failed an original
public trigger. Chart-23 and JacksonXml-4 were unchanged.

This is a transparent POSTFREEZE infrastructure remediation for Mockito,
not a fully pristine original validation for that project. The original
report, amendment, corrected evidence and reconciled JSON audit remain
separate files with linked digests. A unit regression test now checks
that nested build dependencies survive project isolation.

## Interpretation

The principal failure is NOT overall inability to generate syntactically
valid Java. It is limited behavioral understanding and a narrow repair
hypothesis language. V2.1's current static grammar infers only peer-method
Boolean guard contracts, and found no applicable cases here.

The new result is 0 successful repairs across 3 additional distinct cases;
the previous 9 independent cases also had zero repairs. Therefore 0/12
has been OBSERVED across these small, non-statistically-powered experiments,
not that Genesis will always fail.

This experiment tests a frozen V2.1 generator, not autonomous modification
of its hypothesis grammar. No general recursive self-improvement claim
can be made.

Next meaningful experiment: a controlled causal reasoning/search loop that
replays a minimal public failure, records dynamic state/exception/dataflow,
proposes competing explanatory hypotheses, synthesizes operator-grammar
extensions BEFORE a winning patch, and validates these extensions in
isolated descendants against an immutable evaluator. Separate released
training cases from new holdouts and always run unchanged-clone compile
controls for each prospective project.
