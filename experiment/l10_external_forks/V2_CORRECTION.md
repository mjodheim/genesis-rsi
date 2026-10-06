# L10-A v2 — evaluator-only correction after v1 instrument abort

V1 is preserved at its original freeze and result. No candidate was executed.

The Gson baseline regression passed, but the objective evaluator failed before executing its semantic assertion because `javac` attempted to emit class files beside `/authority/L10Gson453.java`, while `/authority` was intentionally mounted read-only.

V2 changes exactly one evaluator plumbing fact: `javac` writes generated class files to `/tmp/l10-authority-classes`. The Java objective source, Gson upstream commit, issue payload, Docker image digest, regression command, candidate-generation policy and claim boundary are unchanged.

Because v1 exposed no semantic Gson objective outcome and no candidate outcome, v2 may run the same frozen task without selecting or replacing a task after result inspection.
