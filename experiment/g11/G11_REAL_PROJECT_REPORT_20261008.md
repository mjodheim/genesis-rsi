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
