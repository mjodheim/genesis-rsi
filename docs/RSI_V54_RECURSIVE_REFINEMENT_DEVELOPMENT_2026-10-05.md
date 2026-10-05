# RSI V54 — recursive scaffold refinement development — 2026-10-05

## Purpose

V54 tested whether V53 could become cumulatively recursive rather than merely
remembering successful scaffolded solutions.

Two development variants were explored on the already-consumed V53 prospective
population only. No V54 prospective population was frozen or executed.

1. **Descendant replay**: successful descendants of V53 scaffolds were
   distilled into new cross-width scaffolds.
2. **Refinement operators**: instead of replaying the descendant, V54 learned
   the delta that transformed a scaffold into a successful descendant
   (rotation delta plus transferred mask toggles), then applied that delta to a
   later V53 base scaffold.

Both variants preserved the inherited 14-evaluation task cap and the V53 root
budget of at most two scaffold candidates.

## Refinement development result

Matched replay on the consumed V53 seeds:

| Seed | V53 solved | V54 solved | V53 evals | V54 evals |
|---|---:|---:|---:|---:|
| 530061 | 65 | 65 | 1824 | 1824 |
| 530062 | 59 | 59 | 1885 | 1889 |
| 530063 | 67 | 67 | 1829 | 1829 |
| **Total** | **191** | **191** | **5538** | **5542** |

Across the three seeds:

- generation-2 refinement memory was created successfully;
- 55 refinement uses were exercised;
- 0 refinement uses were causally helpful versus V53;
- 0 direct solve gains versus V53;
- 0 direct solve regressions versus V53;
- no lineage advanced beyond generation 2;
- the late zero-discovery windows remained unchanged.

Therefore the recursive-refinement hypothesis is rejected as the next L9
mechanism.

## Root-cause diagnosis

The negative result exposed a property of the development bank that matters
more than memory depth.

Each new window independently samples fresh bit positions. The learned V54
refinements therefore encode facts such as "toggle bit 2", while the following
window may require unrelated positions. There is no cross-window signal that
can make that literal bit identity predictively useful.

Inspection of the unchanged G7 interface shows an additional bottleneck:

- `programs.neighbors()` enumerates mask-bit toggles in increasing bit order;
- rotation mutations are yielded only after every bit toggle;
- G7 candidate ordering uses the candidate index as a late tie-break;
- G7's action descriptor represents all non-zero rotations simply as
  `"rotation"`, hiding the actual rotation value.

At large widths this creates a deterministic search-coverage bias. A fixed
budget can exhaust its requests before it probes the bit positions required by
the current task. The late-window failure is therefore not evidence that more
cross-task memory is needed.

## Consequence

The next successor should target **intra-task diagnostic exploration under the
same external budget**, while keeping the current task target hidden.

Promising directions are:

- richer candidate action descriptors that expose candidate-local rotation
  values without exposing the target;
- balanced or feedback-driven mutation proposal;
- diagnostic/group probes whose observed scalar quality narrows the set of
  plausible sparse mask bits;
- causal comparison against frozen V53 under the same 14-evaluation cap.

V54 remains a valid negative development result. It does not change the V53
prospective verdict and does not establish L9.
