# Mira Genesis — Adaptive Embodiment

Mira Genesis is a public, auditable research program on **adaptive software lineages**: systems that
can diagnose limitations in their own executable body, construct and validate changes, adopt them
transactionally, preserve useful state across substrate changes, and continue adapting under strict
measurement boundaries.

The project was originated and is directed by **Anthony Mets**.

The project is deliberately narrower than the phrase “self-improving AI” usually suggests. It does
not treat a model rewriting source code as proof that a lineage owns the improvement process. The
research question is instead whether progressively more of the machinery for diagnosis,
transformation, validation, adoption and later improvement can become **lineage-owned, causal and
replayable**.

> **Objective:** build a program capable of **empirical metamorphosis** — a persistent lineage that
> diagnoses its own limitations, modifies its body and progressively its own acquisition machinery,
> evaluates its descendants experimentally, adopts or rejects transformations on evidence, retains
> what it acquired, and continues after a change of body or substrate. Stated in full at
> [`docs/METAMORPHOSIS_TARGET.md`](docs/METAMORPHOSIS_TARGET.md).
>
> **Where the line stands:** the M095–M102 acquisition line qualified cumulative, carrier-neutral
> acquisition under real interference. M107 then extended the lower interpreter endogenously, M108
> modified the acquisition machinery itself, M109 had a modified machinery produce the next
> modification from the lineage's own blame findings, M110 carried such a modification into a
> materially different consumer family, and M111 reached self-directed diagnosis at recursive depth
> three. M112 removed project authorship of the worlds. M113–M125 are an apparatus-convergence line
> against a separate carrier question and remain **untested**, not negative.
>
> **What is missing is not another mechanism.** These primitives had never run as one program.
> The integrated runtime now exists at [`genesis/`](genesis/), and one lineage runs the whole cycle
> end to end — measure, diagnose, transform, verify, adopt or reject, retain, change substrate, and
> evolve again in the new form. It runs against **fixtures**, it is DEVELOPMENT apparatus, and it
> advances no gate. What it establishes is that the mechanisms compose and that the program refuses
> what it claims to refuse; whether the same holds with a real mechanism attached is the current
> frontier. Ten defects found in it after the fact, and the questions still open, are recorded at
> [`experiments/GENESIS/RUNTIME_NOTES.md`](experiments/GENESIS/RUNTIME_NOTES.md); what a run has to
> exhibit, and which of those properties are driven to their negative, at
> [`experiments/GENESIS/DEMONSTRATION_DEFINITION.md`](experiments/GENESIS/DEMONSTRATION_DEFINITION.md).

For the detailed current snapshot, see
[`docs/CURRENT_RESEARCH_FRONTIER.md`](docs/CURRENT_RESEARCH_FRONTIER.md).

The separate RSI policy line now has **positive bounded L6, L7 and L8 results**
in V28–V30, extending [V26's bounded L5](results/rsi-v26/frontier-20261001/RESULT_SUMMARY.md).
The lineage completes three causal improvement transitions, transfers its unchanged
policy across four actual algorithmic domains, then selects which part of its own
faulted pipeline to repair from measured evidence. Adaptive target selection solves
44/58 new cases against 38/58 for the best fixed target. All original trials,
including V27's negative, are retained. These are finite project-authored experiments
with zero external scientific model calls; independent task authorship, general RSI
and AGI remain unestablished. See [the complete evidence and limits](docs/RSI_L6_L8_RESULTS_2026-10-01.md).

V31 adds persistent branching, task-boundary recovery and rediscovery around
unchanged G7, plus a pinned independent-replication packet. Its finite archive
solves 99/144 new tasks versus 105/144 for cold start; **L9 open-endedness and L10
independence remain unestablished**. See [the archive evidence, preserved transport
fault and external handoff](docs/RSI_L9_L10_READINESS_2026-10-01.md).

V32 tests observed-quality memory ranking on 216 new tasks per arm. Adaptive
retrieval solves 138/216 versus cold 135/216 with 8.7% fewer evaluations, but
always retrieving the closest two solves 141/216: **the strict adaptive criterion
is negative**. Every trial is preserved. L9 and L10 remain unpassed; see
[the complete finite comparison and limits](docs/RSI_V32_MEMORY_RESULTS_2026-10-01.md).

## What the project is trying to establish

The long-term research target is not “make the benchmark number go up”. It is a causal chain in
which improvements become part of the machinery that makes later improvements possible:

```text
S0
  -> acquire A
S1 has new reach
  -> acquire B using that reach
S2 has new transformation capability
  -> acquire C
...
```

A stronger successor would show that earlier acquisitions improve the **ability to discover later
acquisitions** — for example by exposing missing prerequisites, reducing search cost, improving
selection or extending the transformation language itself.

The current staged objective is:

1. **real self-repair** — diagnose and repair a real repository component without being handed the
   target or finished patch;
2. **improvement enabling improvement** — show that adopting A causally changes whether B is
   reachable;
3. **endogenous language extension in the real-software line** — show that a needed transformation
   lies outside the inherited operation language and that the lineage acquires an extension rather
   than receiving it;
4. **hard persistence** — kill the process and prove the acquired transformation capability returns
   from lineage-owned persisted state;
5. **bounded repeated cumulative cycles** — repeat the causal chain across fresh tasks while
   conserving and reusing earlier operations; M100 qualifies this inside one affine family;
6. **cross-family cumulative transfer** — derive later targets from materially different observed
   demands instead of another preselected target inside the same representation; M101 qualifies
   this across three bounded project-authored carriers;
7. **depth and interference** — retain and extend the chain when later learning can damage earlier
   acquisitions; M102 qualifies this in a bounded project-authored schedule with real SQLite;
8. **acquisition machinery and external pressure** — make an acquired improvement change what later
   acquisition can construct, then move toward independently authored held-out domains.

M091 demonstrated endogenous extension in a bounded abstract setting; M097 brought one acquired
operation into the real-software line, M100 repeated the enabling relation twice, M101 moved the
relation across authored text, record and Python-syntax carriers, and M102 acquired a registry
policy under real forgetting pressure before reusing the chain in SQLite. The current frontier is
whether an acquired state-owned improvement can expand the constructive reach of the acquisition
machinery itself.

## Where the project stands now

| Milestone | Status | Current reading |
|---|---|---|
| M042 | **Positive canonical** | First bounded Genesis completion in deterministic finite DFAs; all ten frozen completion gates passed together. |
| M066 | **Positive canonical** | The same bounded gate structure was confirmed on a CPython → Node ESM → whole-WebAssembly lineage. |
| M091 | **Positive scientific result** | A state-owned transformation language was extended endogenously beyond the inherited language's constructive image. |
| M092 | **Aborted without verdict** | Canonical exhaustive search was stopped voluntarily before terminal candidate, reproduction or qualification. |
| M093 | **Engineering rehearsal** | Real repository transformation, sandbox validation, adoption, persistence and rollback worked, but the target, diagnosis and patch were substantially authored. |
| M094 | **Positive qualified scientific result** | The lineage measured the limiting real component, selected the tied top targets and assembled an executable repair from composable operations; 12/12 conditions passed. |
| M095 | **Negative qualified result — attempt 1** | The development chain works, but 0/6 demand-bearing structural qualification worlds execution-confirm B after A; 3/3 negatives remain negative. Eight of eleven conditions pass; P3/P5/P6 fail. |
| M096 | **Positive qualified scientific result** | Exact closed mapping contracts restore compositional reach: 8/8 positives, 4/4 negatives, and 10/10 conditions independently replayed true. |
| M097 | **Positive qualified scientific result** | The lineage assembled and registered a new binary-expression repair operation; inherited scored 0/4, extended 4/4, and 12/12 conditions replayed true. |
| M098 | **Negative qualified result — attempt 1** | Every direct persistence condition passed, but stable replay retained an aggregate PID list; 11/12 conditions passed and P12 failed. |
| M099 | **Positive qualified scientific result** | The M097 operation survived producer death, ran in isolated fresh consumers on 3/3 new worlds, failed under absence/mutation/corruption, recovered after exact rollback, and replayed 12/12 true. |
| M100 | **Positive qualified scientific result** | Registered subtraction enabled acquisition of addition; registered addition enabled weighted addition; all three remained live on 9/9 fresh worlds and all 12 conditions replayed true. |
| M101 | **Positive qualified scientific result** | A carrier-neutral capability acquired from text added reach on 8/8 held-out text/record/syntax worlds versus 0 hidden passes for eight fresh baselines, then remained a live prerequisite for B; 15/15 conditions replayed true. |
| M102 | **Positive qualified scientific result** | Observable flat-registry collisions caused acquisition of state-owned policy K; K prevented destructive forgetting and remained necessary with M101 B for later SQLite capability C. Real-state, retention, causal-control, rollback and replay checks passed 15/15. |
| M103 | **Negative fail-closed instrument result — attempt 1** | The runner completed, but the first frozen checker command could not import its replay runner; P15 was uncomputed. D072 forbids retry or repair. |
| M104 | **Positive qualified scientific result** | The unchanged M103 mechanism qualified on a fresh population with a corrected checker: acquired S-prime added later constructor reach beyond S0, and all P1-P15 independently replayed true. |
| M105 | **Negative checker-instrument result — attempt 1** | The unique runner executed and its result was preserved before checking, but the single frozen checker exited on a module-import error and materialised a negative without evaluating one predicate. D074 forbids retry or repair. |
| M106 | **Positive qualified scientific result** | Corrective replication of the constructor-vocabulary extension: P1-P16 all true, replay equal, zero external calls. Both fresh arms refused by underdetermination with the semantic image exhausted. |
| M107 | **Positive qualified scientific result** | First result in which an acquisition changes what the **interpreter** can express. S0's complete image is four of sixteen and excludes both targets by a monotonicity lemma at every bound; the lineage acquired one unary operator as state, survived producer death and reached sixteen. Ablation returns exactly to four. Recursive depth zero: the acquisition machinery is untouched. |
| M108 | **Positive qualified scientific result** | First result in which an acquisition changes the **machinery that performs later acquisitions**. The attribution rule is held as lineage state and expressed in the lineage's own language; every rule consistent with its blame record is non-monotone, so a lineage without M107's acquisition could not express its own corrected attribution at all. |
| M109 | **Positive qualified scientific result** | First result in which a **modified machinery produces the next modification**, and in which the blame labels are the lineage's own experimental findings rather than host annotations. `ReachImprove` is 6 ⊂ 20 ⊂ 243, strict at both inclusions. A fresh lineage handed generation two's record is refused with zero consistent rules, by lemma. |
| M110 | **Positive qualified scientific result** | First measured transfer of an acquired **machinery** modification into a materially different consumer family, and its bound: the restored cascade strictly adds capability inside the producer's attribution census and strictly removes it outside, where a fresh control succeeds 6/6 and both descendants refuse 6/6. Reproduced 24/24 byte-stable. |
| M111 | **Positive qualified scientific result** | Bounded self-directed diagnosis at recursive depth three: two demands presenting the identical feature row with different limiting components make every static strategy fail one of them, while an acquired policy spends a scarce probe exactly where its own pooled record shows the vocabulary undetermined. Reproduced 24/24 byte-stable. |
| M112 | **Mixed qualified result** | Removes project **world** authorship: a blind generator with no repository mount and no network produced the worlds, and the commitment was published before the tested system was frozen. Procedure 10/10 true, M111 diagnosis reproduced 24/24, M110 transfer 22/24 negative. The carrier remains project-authored. |
| M113-M120, M122-M125 | **Untested — apparatus convergence** | A separate carrier-line question. Successive instrument failures, transport aborts and readiness closures; H58-H65 and H67-H70 are **untested, not negative**, and advance no gate. The cross-instrument delivery allowance stands at 4 of 6 spent. |
| M121 | **Preregistered, apparatus in DEVELOPMENT** | Targets a bounded part of long-horizon autonomy. Its v2 apparatus was found unable to return a negative and its v3 successor cannot currently return a positive; both findings are recorded and the canonical salt remains owner-gated. Neither supports any claim. |

The repository preserves M095's frozen negative attempt 1, M096/M097's positive successors, M098's
disclosed negative, M099's positive hard-persistence result, M100's positive cumulative result and
M101's bounded cross-family result, plus M102's bounded interference result. M100–M102 were developed and qualified locally under the
recorded `PUBLIC_AGPL_COMMERCIAL_OPTION` disposition; remote automation is used only for repository
validation after local evidence is green. M104 then qualifies the unchanged constructor-reach
mechanism on an entirely fresh population; it does not retroactively alter M103.

## M094 — original qualified repair anchor

M094 remains the qualified anchor for autonomous diagnosis and repair on the active real-software
line; M096–M102 extend the causal chain beyond it.

Its preserved second attempt produced a **positive** verdict with **12/12 protocol conditions
computed and true**. The mechanism used **zero model calls and zero network calls**. Diagnosis
selected `mira_core/contracts.py` by measurement and repaired both classes tied at the highest
demand, `Goal` and `Observation`.

Qualification was drawn after adoption from the adopted mechanism digest and passed **2/2
cross-component requirements**:

- `AgentResult`, including a computed `@property` alongside declared fields;
- `ContainerSpec`, including a key mapped to a differently named field.

Random-selection and template-only controls closed nothing. More budget over the same operation set
recovered the same mechanism.

M094 also preserves a withdrawn first positive-looking attempt. A post-verdict audit discovered that
rollback had been tested over decoded text and missed CRLF → LF byte normalization. The attempt was
withdrawn instead of retroactively repaired into a success, the storage mechanism was corrected to
adopt and restore bytes, and the second attempt reused the same mechanism and qualification draw.

See `experiments/M094/` and PR #177 for the full evidence.

## M095 — why the current work matters

M095 does not ask whether the lineage can perform two repairs in sequence. It asks whether the first
repair changes the **constructive reach** of the second.

In the development world, the outer repair requires a renderer on an inner value object. At S0 that
renderer does not exist, so the outer repair cannot be built. The lineage repairs the inner object;
after adoption, the **same operation set** can construct the outer repair.

The active audit then found a more interesting selection problem: when the needed enabler was ranked
below the blocked target, a greedy strategy stalled. The failed search already named the operation it
could not apply, and that operation identified the missing supplier. The lineage can now use that
failure as evidence, descend to the lower-ranked enabler, repair it, and retry the blocked target.

That development relation now holds across all six tested demand-bearing arrangements, including
cases where the enabler is initially outranked. Two deliberately negative arrangements remain where
no inner demand exists and therefore no visible enabler exists to descend to.

This remains useful **development evidence**, but qualification is negative. The current M095 line
recorded 31 pre-freeze defects across seven adversarial passes, with 30 repaired and defect 19
disclosed. Attempt 1 then ran all nine frozen entries: 0/6 positives demonstrate the full relation,
3/3 negatives remain negative, and the checker reports eight passes with P3/P5/P6 failed. A's local
renderer may emit extra keys; B's exact nested contract rejects them. No post-verdict repair is made.

M096 then froze a new population and accepted only complete exact output contracts. It demonstrated
8/8 positive relations and preserved 4/4 negative controls; the checker replayed all ten conditions
true. See `experiments/M095/` for the preserved negative and `experiments/M096/` for its successor.

## What has already been completed — and what “complete” means

The project has a frozen **bounded Genesis completion definition** in
[`GENESIS_COMPLETION_CRITERIA.md`](GENESIS_COMPLETION_CRITERIA.md).

M042 was the first continuous lineage to satisfy all ten gates together in the deterministic
binary-DFA laboratory. M066 later supplied a separate bounded real-substrate confirmation.

Those results are complete **inside their declared task, substrate and budget families**. They do
not imply unrestricted self-modification, general intelligence or open-ended evolution.

The active real-software line deliberately asks a stronger question: how much of the improvement
process can become endogenous in a continuing lineage, and whether one acquisition can become a
real prerequisite or tool for the next. M096 establishes contract-safe composition within its
finite authored domain; M097 establishes bounded language extension and M099 establishes hard
process-death persistence after M098's preserved replay-normalisation failure. M100 establishes two
further bounded cumulative acquisition cycles with exact conservation and live dependency. M101
establishes bounded transfer of acquired reach across authored carrier families. M102 establishes
bounded state-owned registry improvement under measured interference and real SQLite execution.
M103 remains a negative checker-instrument attempt. M104 positively qualifies the unchanged
acquisition-hypothesis-machinery mechanism on a fresh population. Independently authored domains,
ownership of the constructor vocabulary/lower interpreter and deeper chains remain open.

## What Mira Genesis does not currently claim

Mira Genesis does **not** currently establish:

- AGI;
- consciousness or sentience;
- unrestricted or open-ended recursive self-improvement;
- arbitrary self-modification;
- superiority to frontier language models;
- autonomous authority over production systems, credentials, networks or deployment;
- that competence supplied by an external model belongs to the endogenous lineage.

Generality language is governed separately by
[`MIRA_GENERALITY_CRITERIA.md`](MIRA_GENERALITY_CRITERIA.md). A bounded mechanism or benchmark score
cannot be promoted into an AGI claim by wording alone.

## Two epistemic tracks

The repository separates two kinds of evidence:

**Endogenous lineage track**

Studies capabilities that belong to lineage state, transformation machinery and executable body.
This is the track relevant to M091 and the current M094/M095 frontier.

**Model-mediated governed-agent track**

Allows a named external model to propose actions while Mira supplies authority control, isolation,
budgets, audit and evaluator-owned success. External-model competence remains attributed to the
composed system, not silently reassigned to Mira.

See [`docs/EPISTEMIC_TRACKS.md`](docs/EPISTEMIC_TRACKS.md).

## Scientific discipline

The repository is intentionally designed so that a failed experiment can remain useful evidence.
Its operating rules include:

- freeze protocols, thresholds and decision rules before the evidence they decide exists;
- keep hidden qualification material outside the mechanism being evaluated;
- execute candidates rather than infer success from structure where behaviour matters;
- preserve negative, withdrawn and disqualified results instead of replacing them;
- distinguish development demonstrations from qualified scientific results;
- use causal controls and ablations that can genuinely come out the other way;
- replay from preserved artifacts and keep provenance resolvable;
- keep release authority outside the self-modifying lineage.

That rule applies to historical claims as well: **M086-A remains POST-HOC DISQUALIFIED** and is not
restored to a positive qualification by later work.

The failure history is not cleanup debt; it is part of the research record. See
[`FAILURE_LOG.md`](FAILURE_LOG.md).

## Safety and authority boundary

Even a scientifically autonomous lineage remains inside an externally controlled release boundary.
Candidate code runs in disposable environments with explicit limits. Scientific autonomy inside a
sandbox does not grant permission to modify production systems, credentials, external networks or
deployment infrastructure.

The long-term research goal does not require making Genesis impossible for humans to stop, inspect or
contain.

## Quick navigation

| If you want to know... | Read... |
|---|---|
| Where the active research stands today | [`docs/CURRENT_RESEARCH_FRONTIER.md`](docs/CURRENT_RESEARCH_FRONTIER.md) |
| The long-form authoritative project record | [`PROJECT_STATE.md`](PROJECT_STATE.md) and [`PROJECT_STATE.yaml`](PROJECT_STATE.yaml) |
| The historical construction path | [`ROADMAP.md`](ROADMAP.md) |
| The bounded Genesis finish line | [`GENESIS_COMPLETION_CRITERIA.md`](GENESIS_COMPLETION_CRITERIA.md) |
| What would justify stronger generality language | [`MIRA_GENERALITY_CRITERIA.md`](MIRA_GENERALITY_CRITERIA.md) |
| **The objective the project is building toward** | [`docs/METAMORPHOSIS_TARGET.md`](docs/METAMORPHOSIS_TARGET.md) |
| What the integrated runtime does, and the defects found in it | [`experiments/GENESIS/RUNTIME_NOTES.md`](experiments/GENESIS/RUNTIME_NOTES.md) |
| How M107–M111 map onto that runtime's primitives | [`docs/GENESIS_PRIMITIVE_AUDIT.md`](docs/GENESIS_PRIMITIVE_AUDIT.md) |
| What generality validation would additionally require, and who can do it | [`docs/COMPLETION_PATH.md`](docs/COMPLETION_PATH.md) |
| How to serve as an independent task-bank maintainer | [`docs/CALL_FOR_INDEPENDENT_MAINTAINERS.md`](docs/CALL_FOR_INDEPENDENT_MAINTAINERS.md) |
| The endogenous/model-mediated attribution boundary | [`docs/EPISTEMIC_TRACKS.md`](docs/EPISTEMIC_TRACKS.md) |
| Preserved failures and disqualifications | [`FAILURE_LOG.md`](FAILURE_LOG.md) |
| Scientific hypotheses | [`SCIENTIFIC_HYPOTHESES.md`](SCIENTIFIC_HYPOTHESES.md) |
| Project decisions | [`DECISIONS.md`](DECISIONS.md) |
| Current qualified real-software experiment | [`experiments/M094/`](experiments/M094/) |
| Active improvement-enabling-improvement work | [`experiments/M095/`](experiments/M095/) |

## Reproducing the repository checks

The normal development verification path is:

```bash
python -m pip install -e ".[dev]"
pytest -q
python scripts/check_repository_integrity.py
```

Individual frozen experiments may require additional commands, runtimes, artifacts or checkers.
Follow the experiment-local protocol rather than treating the generic test suite as a scientific
verdict.

## Licensing and contributions

Project-controlled software intentionally published in this repository is available under
**AGPL-3.0-only** according to [`LICENSE_POLICY.md`](LICENSE_POLICY.md). Public AGPL use and separate
commercial permissions are compatible; see [`COMMERCIAL_LICENSING.md`](COMMERCIAL_LICENSING.md).

Externally authored copyrightable contributions are currently subject to the temporary rights
boundary in [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues, reproducibility reports and technical
criticism remain welcome.

## Citation and provenance

Use [`CITATION.cff`](CITATION.cff) for citation metadata and [`PROVENANCE.md`](PROVENANCE.md) for the
repository's provenance policy.

Mira Genesis treats the ability to resolve the exact commits behind scientific claims as part of
reproducibility, not as optional repository hygiene.
