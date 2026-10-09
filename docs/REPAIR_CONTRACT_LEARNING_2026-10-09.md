# First contract-conditioned insertion capability — 9 October 2026

The work starts from canonical memory with 292 events. No new model calls,
canonical-memory writes or changes to frozen old experiments are made.

## Gap diagnosis

The latest assisted real repairs require different capabilities:

| Case | Verified assisted operation | Current limitation |
| --- | --- | --- |
| Jsoup-25 | Add `textarea` to a whitespace-preservation set | Constant-only edits have no variable binding; choosing the member requires task evidence |
| Math-37 | Numerically stable rewrite of complex tangent functions | Coordinated multi-line/multi-hunk edits and new local intermediates exceed the learned replacement language |
| Compress-18 | Append a trailing-separator cleanup call | Existing lexical rules remain tied to the source call/API and surrounding statement |

An earlier verified Compress-44 repair adds two constructor null checks. Old
acquisition rejected its multiline insertion. This is the first bounded capability
implemented here because its applicability can be stated explicitly and tested.
It does not cover the three operations above and cannot guarantee avoiding 0/3.

## Acquisition and application

`genesis.repair_contract_learning.acquire` reads full-suite-passing released recipes,
verifies their sealed verdict and candidate identity, recognises pure inserted
`if (parameter == null) { throw new NullPointerException(...); }` blocks and checks
that removing those blocks recovers the old token stream. Constructor parameter
context is required. The acquired rule retains recipe/candidate/verdict digests
and teacher origin. The single current source is the attributed Compress-44 recipe.

The authored projection abstracts reference-parameter names, constructor and field
names and drops diagnostic message text. It preserves the exception class. That
projection is developer-supplied machinery, not autonomous primitive invention.

`generate` needs an explicit caller-supplied non-null contract for a production
constructor. It declines primitive/missing parameters, methods, already conditional
or throwing constructor bodies, explicit constructor delegation and unsupported
parameter syntax. Production boundaries, path traversal and symlinks are checked.
Contract truth is not inferred: an incorrect supplied contract can create an
incorrect patch, which must be rejected by validation. Overload-specific contracts,
annotations, arrays/generics and semantic nullability inference remain unsupported.
No policy is promoted automatically and no active policy pointer is created.

Opt-in adaptive CLI integration:

```
--contract-policy experiment/bench/DEV_REPAIR_CONTRACT_TRANSFER1/POLICY.json
--nonnull-contracts /path/to/reviewed-contracts.json
```

Contract format: `{"src/Holder.java": {"Holder": ["payload"]}}`. Both options are
required together. Exact memory is attempted before learned proposals; the local
phase allows four validations, then the existing economical assistance fallback.
Failures enter ordinary durable validation history; only full-suite successes teach.

## Executed authored gates

The plan was saved before execution with all six fixture sources and contracts,
policy/memory hashes, source hashes, image and zero-API scope. Java compilation and
execution occurred in the existing isolated Docker boundary. Tests stay unchanged;
production bytes are restored after each verdict.

Three distinct fixture layouts test one reference, two references, and a primitive
plus a reference parameter. **3/3 buggy fixtures fail initially and pass after the
learned insertion**, including non-null use. Their three nullable controls generate
no candidate and pass unchanged. Deliberately supplying the wrong non-null contract
on each nullable control produces a failing executable verdict (**3/3 rejected**).
This illustrates why supplied contracts are a material limitation.

There are **12** candidate/fixture compilation-and-execution attempts: six baselines,
three positive insertions and three wrong-contract insertions.
All are recorded in the runtime sandbox log; gates are bounded authored checks,
not Defects4J full-suite repairs or independent execution replication. New API cost:
**USD 0**, external calls: **0**. Canonical memory remains 292 events.

Evidence: `experiment/bench/DEV_REPAIR_CONTRACT_TRANSFER1`. A stored-record audit
checks acquisition, verdicts, counters and preserved source claims, not independent
execution. No fresh real-bug transfer success is claimed. The next scientific step
is prospective real-bug transfer with contracts justified independently of the
expected fix, a same-budget parent comparison and preserved negative outcomes.
