# Genesis External Reality Track ER1-J1 — blind real-repository diagnosis and repair

**Status at freeze:** protocol and selection rule only. No ER1 bug identity, buggy checkout, trigger test, fixing patch, issue text, or post-fix history has been inspected by Genesis.

## Scientific question

Can the post-G10 Genesis machinery diagnose and repair a real historical bug in a third-party repository when it is not told which source file, class, method, or line is faulty?

ER1-J1 is not a G11 claim. It is the first external-reality transfer assay after the project-defined G10 bounded recursive-successor result.

## External source

The first assay uses an active Apache Commons Lang bug from Defects4J. Defects4J is external to Genesis and provides real historical faults with buggy/fixed revisions and triggering tests.

The dataset is fetched only after this protocol is committed. Its exact Git revision and the SHA-256 of the active Lang bug list are frozen before the deterministic selector is executed.

## Deterministic case selection

Let:

- G10 = ccbc75ac2de8bbf821dc6912b32d2d08fbbf5f284d51775bcedbfd5a2f8d80f2
- eligible = sorted active Apache Commons Lang bug ids as integers
- selector = SHA256("GENESIS-ER1-J1|" + G10)
- index = int(selector, 16) mod len(eligible)
- selected case = eligible[index]

No selected bug may be replaced because it is difficult, inconvenient, or produces a negative result. Replacement is permitted only for a mechanically documented environment failure that also prevents the Defects4J reference checkout from reproducing under the frozen environment. Any replacement rule must be committed before observing a substitute case.

## Environment

- Java version: 11
- timezone: America/Los_Angeles
- network: allowed only during environment/materialization setup; disabled for the Genesis diagnosis/repair phase
- repository source: buggy revision only
- post-fix commit/history: unavailable to Genesis
- .git: removed from the Genesis-visible workspace
- Defects4J bug metadata, issue text, patch, fixed tree and benchmark bug id: unavailable to Genesis
- evaluator/verdict authority: outside the mutable Genesis workspace

## What Genesis may see

Genesis receives:

1. the stripped buggy project source tree;
2. ordinary project build files that existed in that buggy revision;
3. a generic task statement saying a regression exists and must be diagnosed and repaired;
4. access to execute the public/visible project test command exposed by the ER1 harness.

Genesis is not told:

- the Defects4J project/bug identifier;
- the issue URL or issue description;
- the fixing commit;
- the changed file(s);
- the faulty class/method/line;
- the human patch;
- hidden evaluator expectations.

A stack trace or test name naturally emitted by the project test suite is considered runtime evidence, not a location hint supplied by the experimenter.

## Search and repair boundary

The candidate may inspect and modify project source and ordinary tests visible in the buggy checkout, subject to the frozen writable policy.

Genesis must produce:

- a diagnosis record with ranked suspected source locations and evidence;
- a source patch;
- the number of files inspected;
- the number of candidate patches/evaluations;
- wall/process resource accounting;
- a machine-readable final proposal.

Direct edits to evaluator files, harness authority, hidden tests, task metadata, or the test wrapper are forbidden and fail closed.

## Evaluation

The external evaluator performs, from a fresh copy of the frozen buggy checkout:

1. patch applicability and writable-boundary checks;
2. the Defects4J triggering test(s);
3. the relevant Defects4J project test suite;
4. regression checks available from the fixed benchmark definition;
5. source-change accounting;
6. comparison with the known human fix only after Genesis has frozen its proposal.

The human patch is never used as an input to Genesis.

## ER1-J1 pass criterion

ER1-J1 passes only if all of the following hold:

- the original buggy reference reproduces the expected triggering failure;
- the fixed reference reproduces the expected pass under the same frozen environment;
- Genesis receives no post-fix history or benchmark solution metadata;
- Genesis proposes a non-empty source change without being given a source location;
- the patched candidate passes all frozen triggering tests;
- the patched candidate passes the frozen relevant regression suite;
- evaluator/harness authority remains unchanged;
- the project still builds/tests from a fresh candidate checkout;
- the complete action/resource trace is preserved whether positive or negative.

A pass establishes one blind real-repository diagnosis-and-repair transfer. It does not establish broad real-world software engineering competence or general RSI.

## Follow-up ladder

If ER1-J1 is interpretable, later assays should expand across independent bugs/projects and languages:

- ER1-J2/J3: additional deterministic Java bugs;
- ER2: issue-only diagnosis on external repositories;
- ER3: hidden-test repair across multiple repositories;
- ER4: cross-language transfer;
- ER5: autonomous anomaly discovery without a supplied failing test.

Every later assay must preserve the same separation between mutable Genesis and evaluator/verdict authority.
