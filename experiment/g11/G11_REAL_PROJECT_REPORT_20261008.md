# G11: first real-project probes (2026-10-08)

Status: both experiments **negative** within the stated candidate budgets.
No evidence of successful general autonomous bug repair, RSI, or cross-language
transfer has been established.

## Scientific protocol

- Case selection from public Defects4J metadata used SHA-256 seeds and was
  preregistered and committed before checkout.
- Only buggy versions of the two projects were checked out.
- Original projects compiled and each reproduced exactly one failing test.
- Generated candidate indexes were frozen and hashed before any validation.
- Candidates were compiled and subjected to the full project test suite in
  isolated fresh copies. A result passes only with zero failing tests.
- Each arm generated at most 80 candidates and validated its first 8.
- No ER4 holdouts, revealed human fixes, or issue descriptions were used.

| Case | Distinct candidate fixes tested | Full-suite fixes | Result |
|---|---:|---:|---|
| Codec-15 | 16 | 0 | All three arms fail |
| Compress-6 | 13 | 0 | All three arms fail |

Provenance records are in G11_CODEC15_PREREG_20261008.json,
G11_CODEC15_RESULTS_20261008.json,
G11_COMPRESS6_PREREG_20261008.json and
G11_COMPRESS6_RESULTS_20261008.json.

## Codec-15: file allocation failure

All three original arms concentrated their top eight candidates on Encoder.java
while the failing test concerned SoundexTest. G11 Java semantic analysis had
unresolved symbols because the pilot omitted the compiled project classpath,
so no meaningful hypotheses were produced.

Posthoc on the already exposed development case, experimental source balancing
spread top eight candidates evenly across Encoder, EncoderException, Soundex
and SoundexUtils. Source coverage improved, NOT verified repair performance.
The production Defects4J adapter now provides the compiled project classpath.

## Compress-6: compilation validity failure

The baseline top eight candidates all targeted ArchiveEntry.java; experimental
source balancing instead spread eight candidates among ArchiveEntry (3),
ZipArchiveEntry (3) and ZipExtraField (2).

All eight balanced candidates failed full project compilation. Of 13 distinct
candidate patches, only three compiled; none passed the complete test suite.

The separate first Compress pilot likewise lacked G11 compiler classpath on
relevant source files; its zero hypotheses are not proof that hypotheses are
ineffective with project-aware analysis.

## Posthoc engineering improvement

An opt-in, read-only Java compiler preflight now checks candidate compilation
against the buggy project's existing classpath. It verifies that the original
source compiles with the same compiler options first. Otherwise it returns
inconclusive rather than giving unreliable negative scores.

The posthoc audit on the already exposed Compress-6 patches reported **13/13**
agreement on compile validity: 3 valid and 10 invalid. This is NOT a
new blinded repair success. Audit is stored in
G11_COMPRESS6_COMPILE_PREFLIGHT_AUDIT_20261008.json.

G11 hypothesis observations for Java now cover simple compiler-confirmed
comparison boundary, numeric threshold and null-guard changes. Each record
includes falsification suggestions and explicitly disclaims any proof of
correctness. Synthetic tests passed; real-project hypothesis utility remains
unproven.

## Safeguards

- All new source balancing, hypothesis reporting and compile preflight remain
  separately opt-in; the baseline behavior remains unchanged.
- Neither project has been repaired within the evaluated budget.
- These cases are now development cases, NOT future fresh holdouts.
- The ER3 autonomous service remains intentionally stopped.
- Future evaluations need completely untouched defects, registered budgets,
  full project dependency context and independent grading.

## Posthoc development repair of Compress-6

The preregistered original Codec-15 and Compress-6 negative results were
NOT altered or retroactively rescored.

Further inspection of the already exposed Compress-6 source found a Java
subclass with a local String field still null after its constructor forwarded
the value to the parent, despite an inherited-value fallback getter. The
subclass equality method compared the uninitialized local field. Consequently,
two objects with distinct parent values could be treated as equal.

Genesis' operator set did not express this state-consistency initialization.
A new generic source-derived repair candidate family was implemented:
initialize_shadowed_inherited_state. The family depends on structural
relations among a local nullable field, a forwarding constructor, a
superclass-aware getter and local-field equality comparison. No benchmark
name, class name, source line ID, issue or human patch is encoded.

Then, even with this new operator present, the candidate search buried
the useful one-edit patch beneath high-scoring unrelated two-edit composed
patches. On the already exposed Compress-6 defect, the correct uncomposed
candidate was placed at rank 51 with source balancing alone, beyond the
first eight full tests. An opt-in atomic-first frontier and a weak source
hint from the failing test classname place the simple patch at rank 1.

The independent full Defects4J suite passed: compilation succeeded and
zero tests failed. The posthoc result was reproduced in a fresh buggy-only
workspace and saved at
G11_COMPRESS6_POSTHOC_REPAIR_20261008.json.
Reproduction command:
PYTHONPATH=. python3 scripts/g11_compress_dev_replay.py

This is a DEVELOPMENT SUCCESS on a previously known defect, not a fresh
external blind success. Independent held-out repair successes remain zero.
The operator family was explicitly engineered by the assistant: no
spontaneous open-ended recursive self-improvement is claimed.

A genuine future success requires freezing this machinery before encountering
new unrelated bugs, retaining equivalent budgets and independent evaluation.

## Independent three-project cross-repository evaluation (2026-10-08)

Math-53, Csv-16 and Collections-24 were selected by preregistered SHA-256
rules, frozen in commit ef103168 before their buggy code was accessed.
Candidate indexes for both configurations were frozen in commit b9e53388
before any candidate validation. Each baseline version compiled and failed
its own tests (Math: 1, Csv: 1, Collections: 2).

Results: 0/3 success for the previous candidate frontier and 0/3 for
the balanced/atomic-first variant, with up to 80 candidates generated
and eight validated per arm. Public failing-test assertions were used as
early rejection signals, but no patch was reported successful without
the full suite. This negative result is permanently filed in
G11_3REPO_RESULTS_20261008.json and its frozen candidate metadata is in
G11_3REPO_FROZEN_INDEX_20261008.json.

These three cases are now exposed and may be used for development, never
counted again as fresh blind evidence. A general sibling-method guard
transfer pattern was identified from the already-exposed Math-53 case;
this was an assistant-engineered capability, not autonomous invention.
The operator is experimental-only and requires evaluation on fresh cases.

Additional engineering: typed public test feedback observations and a
hash-chained, explicitly training-only operator outcome memory. The memory
stores portable operator/outcome metadata and deliberately refuses
holdout records. It does NOT change candidate selection or certify
its own repair success.

The overarching RSI target is not achieved: no autonomous algorithm
invention, new-case full-suite repair or proven recursively improving
repair machinery has yet been demonstrated.

## Additional Math-53 posthoc full-suite repair

On already-exposed Math-53, a new pattern compared multiple sibling methods
sharing the same invalid-state guard and proposed inserting the missing guard
into another sibling method. The generic operator
java_transfer_sibling_invalid_state_guard was written by the assistant, not
autonomously created by Genesis, and is disabled unless explicitly enabled.

The opt-in G11 planner selected the resulting atomic candidate at rank 1,
and the independent Defects4J full suite was passed with zero failures,
including the previously failing ComplexTest::testAddNaN.

Proof: G11_MATH53_POSTHOC_REPAIR_20261008.json, reproducible via
PYTHONPATH=. python3 scripts/g11_math_dev_replay.py.

This is a development repair, NOT independent blind validation. The
original negative Math-53 heldout result remains unchanged. Future
independent evaluations must use untouched bugs, with all proposals frozen
before evaluator feedback.

## Test-body source localization (additional opt-in prototype)

A new failure-analysis module examines the *specific public failing Java test
method*, masks comments and strings, and counts references to production
types on the already observed runtime loaded-classes list. It prefers exact
test-class matches, referenced type names, typed test fields, and package
overlap; records the evidence but cannot establish the actual causal fault
location. All source files are read from the buggy checkout; no human
reference fix is consulted.

On FIVE already exposed *development* cases, this method ranked the
test-referenced class at position one: Math-53 Complex, Csv-16 CSVParser,
Collections-24 UnmodifiableBoundedCollection, Compress-6 ZipArchiveEntry,
and Codec-15 Soundex. These are observations about source attribution,
NOT repairs and NOT an unseen accuracy measurement.

The Defects4J adapter supports
--g11-test-source-localization-experimental. Only when explicitly
enabled will it use the public test body to select and order loaded
source paths. Default and previously sealed independent experiments
remain unchanged.

## Second fully frozen independent batch: Gson-2, Jsoup-68, JacksonCore-11

All three buggy checkouts compiled and reproduced one failing test each.
Project IDs and revisions were preregistered in
G11_SECOND_BATCH_PREREG_20261008.json *before checkout*.
Full candidate-order digests and top-12 candidates per arm were sealed in
G11_SECOND_BATCH_FROZEN_INDEX_20261008.json before validator feedback.

In the preregistered top-12 per arm budget (100 generated per arm), both
the baseline and experimental atomic-first, source-balanced, sibling-guard
configurations repaired **zero out of three** cases according to the
public failing tests and independent full-suite acceptance rule.
Full outcomes and compile failures remain immutable in
G11_SECOND_BATCH_RESULTS_20261008.json.

No success, performance benefit or RSI milestone is claimed. These three
case IDs are now exposed and become development cases only.
An improved public-test-method-to-source-type localization heuristic was
developed separately and **did not influence** any proposals in this
already frozen evaluation.

## Training-only feedback and scientific readiness gate

The first preregistered Math/Csv/Collections batch has now been explicitly
released as training examples and imported into a hash-chained SQLite operator
outcome ledger. The event database is outside the source repository, while
G11_RELEASED_TRAINING_SUMMARY_20261008.json persists its integrity-linked
aggregate. There are 47 recorded distinct candidate attempts across three
released buggy cases and five operator families. No experiment's candidate
selection is automatically changed by this memory, and no private/heldout
candidate is imported.

An auditable, conservative readiness evaluation is provided by
scripts/g11_rsi_readiness.py, writing RSI_READINESS_20261008.json.
It checks public preregistration/result integrity and reports independent
project/count coverage separately from posthoc training successes. It rejects
the false assertion that a set of historical internal G1-G10 labels is
equivalent to general recursive self-improvement. New operator invention,
success across independent unseen projects, validation against equivalent
budgets, and unattended verified operational capability are distinct gates.
