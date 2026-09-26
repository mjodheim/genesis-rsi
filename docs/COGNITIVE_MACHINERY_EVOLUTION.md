# Evolvable cognitive machinery — foundation

Status: **DEVELOPMENT engineering design**, 24 September 2026. No scientific claim, no gate movement,
no V22/V22R/V23/V24 result, and no change to the immutable trust root.

## Baseline before this line

This line began immediately after the identity-corrected retained-evaluator V22R replication apparatus
was integrated. It is continuously rebased/merged forward onto the live scientific mainline without
editing frozen evidence.

At branch creation, active work already existed in PRs #332–#336 around V23 replay, repository/state
synchronisation, real-project gate hardening, and prospective L6–L8 RSI apparatus. Later V23/V24 work
has continued independently on main. This line remains orthogonal to those experiments: it does not
edit their frozen evidence, select an RSI outcome, or reuse hidden observations.

The integrated runtime already has several prerequisites this line should preserve rather than rebuild:

- immutable genesis.trust_root separated from mutable Genesis;
- persistent generated program bodies and interpreter-form migration;
- search-policy and MetaPolicy evolution;
- recursive research strategy;
- provenance classes distinguishing lineage-owned, host-written and model-mediated artifacts;
- explicit budget accounting;
- compute proxies that deliberately refuse to masquerade as energy measurements.

## Research question

Can Genesis improve the **machinery that produces cognition**, rather than only search for a better
program inside fixed machinery, while remaining externally measurable and resource-bounded?

The target is not “a larger Transformer”. A Transformer, state-space model, recurrent network,
memory system, router, symbolic module, mixture of specialists, or a future mechanism without a
current name should all be representable as possible descendants. Architecture family must therefore
be mutable data rather than a hard-coded design decision.

A later experiment should optimise a frontier such as:

    capability / reliability / transfer
                   versus
    measured compute / latency / memory / energy when actually instrumented

No scalar “intelligence score” or energy estimate is introduced in this foundation.

## Implemented increments

### Increment 0 — canonical cognitive architecture genome

`genesis/cognitive_architecture.py` provides a canonical, content-addressed graph representation with
externally admitted primitive identifiers, complete configuration in identity, explicit feedforward
and recurrent edges, acyclic within-step dependencies, optional external node/edge bounds and
deterministic structural profiling. It deliberately makes no FLOP, watt, energy, latency,
parameter-count or intelligence inference from topology.

### Increment 1 — executable primitive registry

`genesis/cognitive_executor.py` executes a deliberately small deterministic primitive catalogue under
an externally imposed node-execution ceiling. Recurrent state remains outside the genome. Recurrent
edges have source -> target semantics across logical steps, so recurrent topology changes affect
execution rather than remaining decorative structure. Actual CPU process time is reported only as a
compute proxy; energy remains unavailable unless it is independently instrumented.

### Increment 2 — bounded architecture mutations

`genesis/cognitive_mutation.py` applies explicit externally chosen mutation intents and validates the
result against admitted primitives and externally supplied size bounds. Primitive/config replacement,
node addition/removal and edge addition/removal are implemented. Every applied mutation can emit a
content-addressed `MutationRecord` binding the canonical parent digest, proposal digest and child
digest. Input/output protection, admitted primitive constraints and node/edge ceilings fail closed.

Mutation policy, scoring and scientific selection remain outside this module; the mutation engine
therefore cannot decide that its own descendant is better.

## Boundary that must not move

Mutable Genesis may eventually change topology, primitive selection, memory layout, recurrence,
routing, learning/update rules, mutation operators, architecture search policy and allocation of its
own admitted compute budget.

It must not gain authority over hidden/fresh evaluation cases, correctness grading, final
accept/reject, resource ceilings, measurement provenance, evaluator identity, rollback or integrity
checks. Those remain external or trust-root-governed.

## Planned increments

### Increment 3 — lineage-held architecture search (proposal path implemented)

`genesis/cognitive_search.py` now represents bounded architecture-search policy as canonical,
content-addressed lineage data. A fixed interpreter deterministically enumerates structurally valid
descendants through the bounded mutation engine, deduplicates equal child architectures, skips
retained candidate identities and refuses a policy whose candidate limit or primitive vocabulary
exceeds externally supplied ceilings.

`genesis/cognitive_search_controller.py` binds the seed policy into `LineageState`, runs its proposal
step inside the existing isolation boundary and reconstructs the expected candidate host-side before
returning it. Proposal generation cannot spend the external budget, mutate lineage state, inspect a
grader or emit a verdict. The policy survives checkpoint restoration.

The evaluation/adoption half of Increment 3 remains separate: candidate architectures still need an
external matched-budget measurement record before any descendant may be adopted. That next layer
must preserve the policy/parent/proposal/child identities emitted here and must not move scoring into
the mutable search policy.

### Increment 4 — resource-aware causal adoption (measurement foundation implemented)

`genesis/cognitive_measurement.py` now creates content-addressed external measurement records that bind
architecture, evaluator, case-set and budget identities. Matched comparison refuses changed evaluators,
case sets or budgets and reports capability, node-execution and CPU-process-time deltas without issuing
an adoption verdict. CPU time remains explicitly a compute proxy.

Energy stays unavailable by default. An energy value is admitted only together with the identity of a
real measurement instrument; the framework does not derive joules from CPU time.

Matched comparison now also requires the exact identities of the cases actually evaluated, preventing
two partial subsets from being compared merely because they claim the same case-set identity.
`genesis/cognitive_adoption.py` adds content-addressed external adoption/rejection and rollback records
plus paired causal-ablation evidence. Adoption binds an external authority, prospective rule and
proposal identity to matched measurements; rollback restores the exact recorded parent. Ablation
compares parent/candidate and parent/ablated measurements under the same evaluator, cases and budget,
but deliberately emits no causal verdict. Scientific adjudication therefore remains outside mutable
lineage machinery.

### Increment 5 — mutate the mutation machinery

Only after architecture descent works, make the operators/search strategy themselves lineage-held and
content-addressed. A descendant may then improve how Genesis changes architectures, while the trust
root still decides whether that meta-change produced better externally measured descendants.

### Increment 6 — world/curriculum factory

Add a separate environment generator that produces new externally verifiable pressures near the
current capability frontier. Keep generation seeds, verifiers and hidden evaluation inaccessible to
the organism being judged.

## What would count as progress

A meaningful future result is not “Genesis generated a novel graph”. It should demonstrate at least:

1. a descendant architecture differs materially from its parent;
2. the difference is lineage-produced and survives restore;
3. it improves fresh capability or the capability/resource frontier under matched external budgets;
4. the gain disappears or weakens under an appropriate causal ablation;
5. later descendants inherit and build on the acquired machinery;
6. the evaluation/root-of-trust bytes and hidden cases remain outside the lineage.

Until those hold, this remains DEVELOPMENT apparatus.
