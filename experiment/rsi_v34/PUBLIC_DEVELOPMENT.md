# V34 fixed public pilot — the plateau is preserved

All four arms on both declared public seeds and epochs 0–3 remain in the complete
lossless `DEVELOPMENT.json.gz`. Every arm receives all 120 public tasks. This is
implementation development, without a parameter sweep, not fresh qualification.

| Arm | Solved / 120 | Charged evaluations | New solving behavior signatures |
|---|---:|---:|---:|
| Adaptive history distance, paid probes | 65 | 1159 | 13 |
| Recency, paid probes | 65 | 1232 | 15 |
| Greedy last successful descendant | 65 | 1260 | 16 |
| Cold local probes | 65 | 1291 | 19 |

Adaptive saves 132 charges against cold (10.2%) but solves no more tasks and
discovers fewer new solving behavior signatures. Seed 503's adaptive new-solving
counts are 3, 1, 2, **0**; seed 887's are 3, 2, 1, 1. The discovery plateau and
all negative controls are retained. This pilot fails the prospective first-prefix
utility/growth requirements on this consumed population; no holdout or L9 result
follows from it. Fresh generator seeds have not been behaviorally evaluated.

The first prospective prefix, if executed, must remain the declared eight epochs
and all four arms, with no post-pilot implementation or threshold change. In
particular, a previously seen partial behavior later solving a task is not silently
renamed a new behavior. Witness signatures are observations on finite public
inputs, not full semantic equivalence classes. The grammar's 128-instruction
capacity is an explicit resource ceiling.
