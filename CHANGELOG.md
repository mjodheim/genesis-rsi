# Changelog

## Unreleased

- **A blind repair bench, and a model allowed to propose.** `genesis/repair_bench.py` freezes a hash-derived split of the pinned Defects4J benchmark (`experiment/bench/REPAIR_BENCH_SPLIT_V1.json`: 167 held-out cases, 687 development; Lang and every already-opened case can never be held out), derives a case's evidence only from a run of its own failing tests, and validates every candidate identically behind the container boundary: compile, failing tests, full suite. Arms run in rounds and see their own earlier verdicts. `genesis/repair_proposers.py` provides two proposers at one budget: the existing operator families, and a language model reached through the `claude` client, with or without read access to a copy of the buggy sources. This departs from the no-large-model line by decision of the research director after the search-space audit; the operator arm stays as the control. `scripts/run_repair_bench_trial.py` preregisters and runs a trial; `scripts/audit_repair_bench_trial.py` afterwards reports how many accepted patches are the developer's own. **A test-passing patch is not a correct one, and a public benchmark may be in the model's training data**: every record says so. No held-out case is consumed by this change and nothing is claimed.

- **The recorded 0/12 on unseen Defects4J bugs is a search-space failure, not a budget failure.** `scripts/audit_repair_search_space.py` regenerates every candidate the strategist can produce on the 14 already-exposed cases and compares it with the human fix. On the 11 cases that never received a hand-written operator, the fixed file is in focus in 10, 9,239 candidates are generated, and **a single case has any candidate on a line the fix edits; none contains the fix**. 97 % of atomic candidates perturb existing tokens while 13 of 14 fixes add lines, and the specialised families fire only on the case each was written for. `scripts/audit_defects4j_fix_shapes.py` adds benchmark-wide fix shapes (17 % one-line replacements, 98 % add a line). Full account in `experiment/g12/REPAIR_SEARCH_SPACE_DIAGNOSIS_20261008.md`. The 14 cases are development-only; **no result changes and no capability is claimed**. `Defects4JSandbox.export` now returns the bare property value.

- **Defects4J validation moves behind a container boundary.** Compiling a repair candidate and running the project test suite executes untrusted code, and until now `defects4j compile` and `defects4j test` ran directly on the host, as the operator's user, with the network up. `genesis/defects4j_sandbox.py` runs every Defects4J command in a fresh container with no network, a read-only root filesystem, no capability, an unprivileged uid and memory, CPU, process and wall-clock ceilings; the caller's workspace is the only writable host path. `Defects4JSandbox.probe()` observes the boundary from inside and seals what it saw, so an evidence file can state the isolation that was enforced rather than the isolation that was requested. The image is built from `deploy/defects4j/Dockerfile` with Defects4J pinned at `8c16da82`. **No study has been re-run through it and no recorded result changes**; the existing G11 and V2.1 scripts still call the host installation and must be ported before any new trial.

- **Genesis v2 foundation reset — efficiency-first recursive machinery research.** The active public identity is now **Genesis** (formerly Mira Genesis). The reader-facing README, principles, architecture and roadmap now center capability-per-resource, language-neutral structural understanding, failure attribution, self-modeling, autonomous experiment generation, component evolution, causal promotion, distillation and repeated successor generation. Historical frozen evidence remains in place and the pre-reset README, roadmap and project-state snapshots are preserved under `docs/history/` and `docs/state-history/`. The reset makes **no new RSI/AGI claim and changes no frozen scientific verdict**. Repository-integrity maintenance performed during the reset also classifies 40 autonomy `carrier_commit` values as external-repository objects and adds provenance tags for 21 recent cited Genesis commits that had been reachable but unprotected from future branch cleanup.


- **M114 = `instrument-aborted`. Three delivery attempts, three HTTP 429s, zero banks, H59
  untested.** The frozen sequence ran to the end of its budget on 27 August 2026: requests at
  13:02:39Z, 13:03:40Z and 13:04:41Z, each an explicit capacity rejection carrying no completion and
  no evidence the model executed. The model was never reached, so **nothing about H59 was measured**.
  A negative result is a measurement; this is a fact about a queue. `P22` was neither computed nor
  approached, and H59 is exactly as untested as H58 remains.
  **The evidence names its own cause, three times, which M113's could not.** All three responses are
  byte-identical — one digest, `f0a0b94c…`, across attempts a minute apart — and each carries
  `provider_error_code: service_overloaded`, `limit_source: upstream_provider_shared_pool`,
  `is_byok: false` and `retry_after_seconds: 1`. M113 made one request, got a 429, and its client
  discarded the body, leaving a status code from which the cause had to be inferred. **The provider
  asked for a 1-second wait; the frozen rule waited 60, and was rejected anyway, twice.** The
  constraint is not a matter of patience.
  **The delivery separation did exactly what it was built to do.** Three physical network requests
  occurred and zero model calls did, and the record reports those as two different numbers —
  `physical_delivery_attempts: 3`, `bank_materializations: 0`. Under M113's protocol there was no
  vocabulary in which to say that. The ledger validates **in full** under the frozen rule: within
  budget, byte-identical frozen body every time, nothing served so nothing substituted, each outcome
  recomputed from its own evidence, the 60-second wait honoured before attempts 2 and 3. An abort is
  not a violation, and the corrective `P15` refuses this record for the right reason — the
  qualification and delivery halves hold, the generator half does not, because there is no bank.
  **No fourth attempt exists to take.** The budget is spent and the frozen spec `e12337a4…` can
  never authorize a bank; the phase machine concludes it directly from the ledger. Nothing is
  relaunched under M114. Whether a successor is opened, and with what instrument, is the owner's
  decision and was not taken here. Twenty-one tests pin the aborted record by digest and assert that
  nothing downstream of a bank may ever appear under it.
  **A redaction, recorded.** OpenRouter's 429 envelope carries a `user_id` identifying the account.
  It is not the API key and grants no access, but it identifies the owner and this record is
  published, so it is replaced in all three attempts — with the replacement, its reason and the
  ledger's pre-redaction digest `6a0684f7…` recorded inside the ledger itself. **No quantity the
  frozen rule reads was touched** and the ledger still validates; the cause the provider named
  survives, only the caller is gone. The client now strips identifying fields at capture. An intermediate revision of the
  development branch carried the unredacted value; **the branch history was rewritten before merge
  to remove it**, so it never enters `main`'s ancestry. The rewrite changed no measured quantity —
  the freeze remains a distinct commit preceding the attempts, and the chronology stays
  demonstrable: freeze, attempt 1, attempt 2, attempt 3, instrument-aborted, redacted record.
  M113 is untouched and remains closed. The M114 plan and spec remain frozen and are not re-frozen.
  No seal, public commitment, tested-system freeze, reveal, qualification, canonical run or result
  exists. **No generality gate moved.**

- **M114's analysis plan and generator spec are frozen — the second freeze, the first having been
  withdrawn.** Plan commitment `e4c659e5c8f5ab0884a4de862876302d7fefc699d914ff0776fefb322ac026af`,
  the candidate unchanged; generator identity at spec commitment
  `e12337a4a78045394e4db7b39cb710d3c6dacbd435d01f9a92530e239c288fc3`. The identity is M113's,
  checked field by field: the same `deepseek/deepseek-v4-flash-0731` served by Morph at bf16, the
  same sampling, the same routing switches, the same canonical request body `02a71fb5…`. The freeze
  moved exactly four bookkeeping fields on the spec and nothing the instrument will send; a test
  asserts that set exactly. Both frozen artifacts are pinned by digest and pushed **before the first
  delivery attempt**, so the order is verifiable from the history rather than asserted afterwards.
  The withdrawn first freeze stays visible: `b98116d8` is now an ancestor of `main` — #219 was merged
  with a merge commit rather than squashed, precisely so it would be — and a test asserts that
  `experiments/M114/FREEZE_WITHDRAWN.md` survives and that the withdrawn commitments are not the ones
  in force. It is never to be rewritten as though it had not existed.
  Phase is `spec_frozen`. Four owner gates remain. H59 is untested and no generality gate moved.

- **M114's `P15` is versioned rather than imported, and the freeze that preceded the correction is
  withdrawn.** M113 defines `P15`'s generator half as the number of **physical invocations**, on the
  stated ground that a series of physical requests must never be presentable afterwards as one
  logical invocation. M114's separation of delivery from materialization makes that no longer a
  single number — and M114's first form set `model_calls_in_bank_generation = bank_materializations`
  while claiming `P1`–`P22` were imported unchanged. **That claim was false.** A milestone whose
  entire subject is a conflated counter cannot ship a conflated counter of its own and describe it
  as an import, so the claim is corrected everywhere it was made rather than quietly narrowed:
  `P1`–`P14` and `P16`–`P22` retain M113's scientific computations; `P15` is the explicitly
  versioned corrective boundary predicate `m114-phase-boundary-v1`.
  **The corrective `P15` is recomputed independently** from the preserved record — never from a
  field the runner wrote about itself, and the whole delivery ledger is now preserved into the
  result rather than only its summary. It is the conjunction of three halves: a qualification phase
  with zero model calls, zero network calls and zero remote-execution calls under a guard whose
  self-test actually fired; exactly one bank materialization; and a delivery record that is valid in
  full under the frozen rule — within the budget of three, byte-identical request bytes on every
  attempt, the same model and the same provider with no fallback available, only explicit 429s
  carrying no completion and no evidence of model execution preceding a retry, the frozen 60-second
  wait honoured, at most one materializing response, nothing attempted after materialization, and
  every ambiguity terminal.
  **Six quantities are now reported separately and none carries two meanings**:
  `physical_delivery_attempts`, `bank_materializations`, `model_execution_evidence`,
  `network_calls_in_qualification`, `model_calls_in_qualification` and
  `remote_execution_calls_in_qualification`. A 429 before generation is a physical network request
  even though it is not a model execution; `model_calls_in_bank_generation` is gone from M114's
  result entirely, because under this separation there is no single number that field could
  honestly hold.
  **This gives H59 nothing.** The delivery checker is a gate and only a gate: a violation makes the
  run `invalid`, zero materializations make it `instrument-aborted`, and no clause can turn `P22`
  false into `P22` true. Twenty-four new adversarial tests attack each clause with a record built to
  slip past it — two rejections then a materialization, a 429 that carried a completion followed by
  a retry, an ambiguous timeout followed by a retry, two materializations, one byte of difference
  between attempts, a provider or model substitution, a fallback left available, an absent ledger, a
  forged ledger, an understated attempt count, and a perfect bank under a guard that never proved
  itself live — and one asserts the subtractive property directly by sweeping every delivery-record
  shape against a run whose science already fails.
  **The freeze consumed at 11:34:19Z is withdrawn**, recorded in
  `experiments/M114/FREEZE_WITHDRAWN.md` rather than erased: it ran one step early and while this
  defect was still open, and repairing the defect moves the plan commitment. Between that freeze and
  its withdrawal **no delivery attempt was made, no bank was materialized, and nothing about H59 was
  observed** — the freeze constrained an instrument that never acted, which is why withdrawing it is
  a correction and not the repair of a result. The withdrawn commitments stay in the record and the
  bytes remain reachable at commit `b98116d8`. M114 is back at phase `draft` with five owner gates
  outstanding.

- **M113's two obsolete global metadata fields are reconciled — record reconciliation only.**
  `PROJECT_STATE.yaml` still carried `status: candidate_not_frozen_bank_does_not_exist` and
  `phase: draft`, and `PROJECT_STATE.md`'s heading still read "a candidate, not a result", all of
  which predated the invocation. They now read `status: aborted_without_verdict` — the register's
  existing value for exactly this shape — and `phase: spec_frozen`, which is what the phase machine
  reports for M113 today. The historical truth is stated plainly: generator identity frozen, one
  qualifying delivery attempt aborted at HTTP 429, zero bank materializations, **H58 untested**,
  instrument failure, record closed.
  **Nothing under `experiments/M113/` is touched.** None of the four digests pinned by
  `tests/test_m113_record_is_closed.py` moves, no bank, reveal or result is created, and the record
  is neither repaired nor reinterpreted. The lock bites exactly as it did before.

- **M114 opens as a corrective instrumental replication of M113, under H59.** M113 is closed. It
  froze an identity, made one physical request, received HTTP 429, materialized no bank and left
  H58 untested; that record is not re-frozen, not reinterpreted, not repaired and not completed,
  and `tests/test_m113_record_is_closed.py` pins its four digests and fails if a bank, a reveal or
  a result ever appears under `experiments/M113/`. M114 takes a **new hypothesis number** rather
  than inheriting H58, following the M106 precedent that replicated M105 under H51: a replication
  that reused its predecessor's number would make that predecessor's record read as still open.
  `P22` is H59 exactly as `P22` was H58.
  **Every scientific rule is imported, not copied.** `m114_carrier_bank` delegates its plan and
  generator-spec rules to `m113_carrier_bank`; the qualification runner imports M113's sealed scope
  and arms; the checker imports `P1`-`P14` and `P16`-`P22`; the generation client imports M113's
  stdlib transport;
  the prompt, the output schema and the qualifying input are M113's files byte for byte, pinned by
  digest and checked against both milestones' copies. The generator identity, the sampling, the
  routing switches and the canonical request body are M113's, digest-identical. 24 carriers,
  minimum 3 qualifying, minimum 3 distinct structures, exact per-carrier fixed-point closure, no
  selection, no manual correction, and an insufficient bank is still a negative result. A copy
  would drift; an import cannot.
  **What changes is delivery semantics, and only that.** M113's protocol used one predicate, "one
  physical request", for two quantities: how many times the instrument may *reach* the generator,
  and how many times the generator may *produce* a bank. Those coincide only while the network
  cooperates, and a capacity rejection spent the second budget without ever spending the first.
  `m114_delivery` separates `delivery_attempt` from `bank_materialization`: at most 3 attempts for
  at most 1 materialization, every attempt sending the byte-identical frozen body, a further
  attempt permitted only after an explicit HTTP 429 carrying no completion and no evidence the
  model executed, after a fixed pre-registered 60-second wait. Three capacity rejections end the
  milestone as `instrument-aborted`, which is a fact about transport capacity and not a result
  about H59. Nothing else is ever retried -- invalid JSON, a schema violation, a truncated
  completion, a refusal, an insufficient bank, an ambiguous timeout, a lost connection, any status
  other than 429, and above all any scientific outcome including `P22` false.
  **Ambiguity resolves terminally, never retryably.** An attempt counts as a capacity rejection
  only when every condition holds at once; any doubt classifies as `failed_ambiguous`, which is
  final. The asymmetry is deliberate and lopsided: the conservative mistake costs one unused
  attempt, while the opposite would permit a second draw against a model that may already have
  produced one, and no downstream check could recover the difference.
  **The checker recomputes the rule instead of reading the ledger's summary** -- the budget, index
  contiguity, request-digest identity across attempts, provider and model substitution, each
  outcome against the evidence carried, that nothing follows a terminal outcome, each recorded
  retry permission, each wait, that at most one attempt materialized and nothing follows it, the
  declared materialization index, and the spec binding. Two verdicts are added on top of
  the predicates and both are **strictly subtractive**: a violating ledger is `invalid`, a ledger with
  no materialization is `instrument-aborted`, and neither can turn a negative into a positive.
  Sixty-six tests attack the contracts and the instrument directly, including a fourth attempt, an attempt after a
  terminal outcome, a retried ambiguous timeout, a 429 carrying a completion, two materializations,
  a changed request body, a mislabelled outcome, a forged retry permission and a shortened wait.
  **The rule was decided after M113's instrument failure, before any M114 bank existed, and without
  any observation of H58 or H59 whatsoever.** It was never part of M113 and is never described as
  though it had been. Those four statements are booleans in `m114_carrier_bank.FILIATION` that the
  frozen plan must reproduce exactly or fail validation. M114's plan and spec are candidates; the
  bank does not exist; the phase is `draft`. No generality gate moved.

- **M113's generator identity was frozen and its single qualifying invocation returned HTTP 429.
  No bank exists and H58 is untested.** The identity was pinned at spec commitment `c0f13b69…` --
  `deepseek/deepseek-v4-flash-0731` served by Morph at bf16, twenty-four carriers, one invocation,
  retries forbidden at eight named layers -- and committed before the invocation so the order is
  verifiable from the history. Morph was selected under a criterion the owner recorded: among
  providers satisfying every already-frozen constraint, the one whose declared quantization most
  faithfully preserves the weights; of the twenty capable providers it was the only bf16. The
  criterion is stored with its timing checked rather than described, and quantization is pinned as a
  `provider_discovery_catalogue` property with `quantization_is_runtime_attested` false, because
  OpenRouter reports it in the catalogue and not in the completion response.
  **The failure is an instrument failure and not a negative result**, and the record is built to
  keep those apart. A negative result is a measurement; nothing ran. The generator was never
  reached, no carrier was produced, `P22` was not computed or approached. Under the frozen rule the
  attempt is not repeated: the ledger records attempt 1 as `aborted` with no payload, and the shared
  contract concludes what follows -- the frozen spec has materialized 0 banks where exactly one is
  required, so it can never authorize one. Re-freezing is the owner's decision and was not taken.
  The risk was known before the freeze: the pre-freeze probe needed two attempts, the first a 429
  from a shared upstream pool, and that was recorded together with the observation that the same
  condition would end the milestone for a reason with no scientific content. The owner declined the
  BYOK remedy because a new credential path could alter the served identity after the instrumental
  choice was frozen, and authorized the invocation with the risk understood.
  **Two client defects, both found by the failure and neither before it.** The ledger outcome was
  written as `failed`, a word the shared closed vocabulary does not contain, and only the phase
  machine reading the record back caught it; the correct word is `aborted` and the encoding was
  corrected without touching the facts. And the failure response was discarded, so only the status
  code is evidenced for the one attempt that mattered -- the development probe's 429 named its
  cause, and that cause is deliberately not carried across, because borrowing it would be inventing
  evidence this attempt did not leave. Both repaired, both pinned by tests, and a failed attempt now
  preserves its full response as `GENERATION_FAILED_ATTEMPT.json`.
  The analysis plan remains frozen and untouched at `66003159…`. M107-M112 are unaffected. No
  generality gate moved.

- **The M113 pre-freeze sequence is one command, and it checks its own post-conditions.**
  `run_m113_generation.py --prepare` discovers which providers actually serve the exact model,
  adopts one under a rule stated before the data, runs the non-qualifying probe and then asserts
  that no ledger, no sealed bank, no commitment, no reveal authorization and no result exists and
  that the phase is still `draft`. The sequence has an order that matters and a hand-run one can
  silently skip a step: an unadoptable discovery must never reach the probe, and a failed probe must
  never reach the freeze. It stops at the first step that cannot proceed, so a stop is a diagnosis
  rather than a partially applied state. The provider rule is deliberately narrow -- adopt **if and
  only if exactly one** provider serves the exact model with strict structured output; one candidate
  is a fact, several is a judgement made after seeing the catalogue, and that is the shape this
  milestone exists to keep out of the record, so several stops and goes to the owner. Adoption
  answers only the three fields discovery is entitled to answer, and a test requires the adopted
  candidate to **still fail** `validate_generator_spec`: a discovery run may not consume the freeze
  gate however complete its findings. Six tests cover it, including the whole pass against a stubbed
  transport that counts physical requests -- three, never four -- and the three ways it must stop.
  Still nothing executed against the real endpoint: this environment has no credential and
  `openrouter.ai` remains refused by egress policy.

- **M113's analysis plan is frozen, and the model-network boundary it needs is now measured rather
  than asserted.** The plan is frozen as the candidate unchanged, at commitment `66003159...`,
  before any carrier exists -- the first of the six owner gates, and the only one that can be
  consumed without a generator. A twelfth pre-freeze defect was then found while auditing the one
  boundary this milestone introduces and its predecessors did not have. M113 is the first milestone
  in this lineage whose *bank* is produced by a model over a network, and it had **regressed from
  M112 on exactly that boundary**, in two places. `P15` read three unqualified counters --
  `model_calls`, `network_calls`, `remote_execution_calls` -- that `run_m113_qualification.py`
  wrote into its own result as literal zeros, so the predicate agreed with the program it was
  judging and **could not fail**: the M086-A shape the readiness checker's own docstring cites, in
  the one predicate whose whole job is to say the tested system never reached for the model that
  wrote its world. And `m113_carrier_bank.py` declared `GENERATION_LEDGER_PATH` and **never read
  it**, so nothing counted the physical invocations that produce the bank and several requests could
  have been presented afterwards as one logical invocation. Both halves are repaired and neither is
  a number the runner chooses. The qualification phase runs inside a sealed scope that replaces the
  two entry points every outbound connection in CPython passes through, counts each attempt and
  refuses it; because an unarmed guard and a silent run record the same zero, the scope ends by
  making the guard fire once against a reserved TEST-NET-1 address that routes nowhere, and `P15`
  credits the silence only when that self-test proves the instrument was live. Reaching a model and
  dispatching execution elsewhere both need a socket, so one measurement entails all three counts.
  The generator phase is counted by the ledger, which the phase machine now requires, validates
  against the shared contract and binds to the frozen spec; a canonical result must record exactly
  one invocation, and a development run reports that half as *not applicable* rather than quietly
  satisfying it. The repair changed the instrument's honesty and not its measurements: re-running
  development at the same sample and seed reproduces every arm total, the whole generational
  decomposition and the same **21 of 22 with `P22` false**, and only `result_digest` moved.
  **The qualifying invocation itself is not in this change and could not be.** No Hermes client and
  no OpenRouter credential exist in this environment, and `openrouter.ai` is refused by egress
  policy with a 403 on the CONNECT tunnel -- each independently fatal to a single blind invocation.
  The authorization permits a transport fallback but no substitution of model or provider, and the
  session holding it knows H58 and M107-M113 and may therefore never author the carriers itself.
  Recorded as an instrument blocker beside the Docker one, not worked around.

- **The M113 generator identity now has a contract, written before any identity could be pinned.**
  M112 could freeze a container image digest, a model blob digest and a runtime version, and could
  say afterwards exactly what emitted its bank. A hosted model offers none of those; it offers an
  identifier, a provider, and routing switches that decide whether the frozen request is the served
  one. `validate_generator_spec` pins those and refuses every shape in which the served identity
  could differ from the frozen one -- a model **alias** or auto-router, a **provider left open**, a
  model or provider **fallback**, and **retries** at each of eight named layers. Two honesty
  conditions have no M112 analogue: a seed is recorded as requested and never as a guarantee, and a
  hosted generator may not claim determinism; and no credential may appear anywhere in the spec,
  including the canonical request body it publishes. `GENERATOR_SPEC_CANDIDATE.json` holds
  everything pinnable without the instrument and lists the six fields discovery must fill; it
  **cannot validate as frozen**, which is the point of it. `scripts/run_m113_generation.py` is the
  client and **has never been executed**: discovery, a non-qualifying smoke probe whose input is
  checked against the qualifying digest, and one qualifying invocation that refuses a spec which has
  already materialized a bank, sends the committed body byte for byte, and fails closed when the
  served model or provider is not the frozen one. Its transport is `http.client` from the standard
  library, driven directly -- no vendor SDK and no third-party HTTP client, because each carries
  retry behaviour that would have to be disabled correctly and the way to disable it correctly is
  not to have it.
  **Defect thirteen was found by the contamination checker, not by a reader.** The frozen
  `OUTPUT_SCHEMA.json` carried a `title` of `mira-blind-carrier-v1 emission`. The schema travels to
  the generator inside the request as the structured-output contract, so its own strings are part of
  the generator's sole input: a blind emitter would have been told the name and version of the
  contract it was emitting for, by the one artifact whose job is to constrain the shape of the
  answer and say nothing about its purpose. Nothing frozen bound the schema yet, so it was repaired,
  and every file the generator sees is now required to be contamination-free. The credential guard
  needed narrowing for the same reason in reverse: its first form matched any key ending in `_key`
  or `_token` and refused the carrier meta-schema itself, whose wire surface has an `action_key`, an
  `argument_key`, a `status_key`, an `ok_token` and an `error_token`.

- **M113 is pre-registered and built; it has not run and its bank does not exist.** M112 removed
  world authorship and left the carrier. M113 puts the carrier's interaction language in a blind
  generator's hands: the emitter chooses the state cells and their domains, which of them are
  latent, the action names and arities, the preconditions that make the carrier impose a protocol,
  the effects, the error vocabulary and which of four wire surfaces it speaks with which tokens.
  The project supplies the contract of reception -- `metamorphosis/carrier_host.py`, a host that
  holds no carrier semantics and is checked to be **equivariant under a consistent renaming** of
  every cell, action, error and token. Closure is an exact fixed point rather than an inherited
  bound: M112's `P5` failed because seven expression nodes closed the image on 1 160 project worlds
  and not on the first blind one, and the devkit survey here already sees observations first
  appearing at depth 11. One carrier is one record, that identity is declared and mechanically
  checked, and M112's cardinality defect would now fail the guard -- as would the same defect one
  level up, because the minimum is stated over **distinct qualifying structures** under a
  renaming-invariant signature the checker recomputes from preserved carrier bodies, so a bank of
  twenty-four renamings of four machines is refused rather than counted as twenty-four. Eleven pre-
  freeze defects were found by measuring the apparatus rather than reading it, all repaired, each
  with a regression test -- including three that only the whole suite could find, and that arrived
  in sequence. The root `.gitattributes` is bound apparatus of M106's frozen protocol and M113's
  first commit had appended to it; moving those entries into the per-directory files broke an M107
  test instead, because M107 binds those files too; and the tested system was bound by raw bytes
  although five of its eleven members are predecessor files no attributes file here may write. Every
  attributes file in the repository is already frozen apparatus, so an attributes entry is not a
  mechanism a successor can use: M113 declares only `experiments/M113/.gitattributes` and binds
  every source member by a declared `lf_normalized` digest mode, with an undeclared mode refused.
  All twelve declared arms run: producer death executes the full descendant in a capsule whose
  import path cannot reach either producer result, and every isolated verdict matches the in-process
  one; the preservation arm finds M110 and M111 reproducing their
  result digests with 24 of 24 conditions each. The development run, bound to its own `result_digest`
  `2e89b665…` so the text and the file cannot drift apart, returns **21 of 22, P22 false**: the full
  descendant constructs 23 against the fresh control's 13 and attributes correctly 21 times against
  10, while its calibrated refusals fall from 29 to 6 and its invented adapters rise from 13 to 15.
  The checker now decomposes that sum into the generations that produced it, and **generation two
  moves no outcome measure at all** -- one attribution row, and nothing else -- while the M111
  diagnostic policy carries the entire effect in both directions. A positive H58 must be reported
  with that decomposition and credited accordingly; whether the ablation bites is measured, never
  required, because making an inert generation refute H58 would be a different claim. Freezing the
  plan, pinning a generator identity and running the single invocation remain owner gates, and the
  Docker daemon is still not running as of 26 August 2026, so the attested isolated invocation
  cannot be planned from here.

- **M104 qualifies the unchanged constructor-reach mechanism on a fresh population.** The owner
  accepted candidate `6416e54b…`, froze protocol `b3d8a6b3…`, then separately authorized one attempt
  on pool `a84fa3c…`. Result `f2be4d85…` and stable evidence `9f2d1758…` were preserved before the
  one checker invocation. Independent replay matched and P1-P15 are true (`7032528b…`), with zero
  model/network/remote calls. This is bounded acquired constructor-reach evidence; the feature
  vocabulary and lower interpreter remain authored.

- **M103 remains negative by fail-closed checker instrumentation.** Its runner result is preserved,
  but the first frozen checker command could not import the replay runner and left P15 uncomputed.
  D072 forbids retry or repair; M104 does not retroactively change that verdict.

- **M102 qualifies bounded registry-policy improvement under interference.** The unique authorized
  attempt 1 ran from frozen protocol `59689da6…` and the untouched thirteen-record population
  `3d6785dd…`, with zero model, network or remote-execution calls. The lineage acquired generic
  carrier+slot policy K after observable flat-key collisions, prevented demonstrated destructive
  forgetting, survived producer death, then used live K plus M101 B to acquire C and pass real
  SQLite state checks. The independent checker computed P1-P15 true; result `92d4ed3e…`, stable
  evidence `eab68a79…`, report `3ba2f130…`. The pre-freeze runtime-binding failure remains preserved.

- **M101 qualifies bounded cross-family cumulative transfer.** From corrected v4 freeze `b3e172b`,
  one carrier-neutral combinator A was acquired from public text demand, survived producer death and
  passed 8/8 held-out text/record/Python-syntax worlds. Eight equal-budget fresh T0 baselines passed
  zero hidden cases. A then remained a live content-addressed prerequisite for acquired syntax
  operation B. M100 conservation, mutation/ablation/corruption, exact rollback and stable replay all
  passed: 15/15 conditions, zero model/network/remote calls. Result `486f33e…`; stable evidence
  `45f18dc6…`; checker `95bffc8b…`. This is partial bounded G4 evidence, not G4 closure.

- **M099 qualifies stable hard process-death persistence.** From freeze `62a29b0`, the unchanged
  M098 process mechanism persisted the exact M097 registry, terminated its producer and reconstructed
  the operation in eight isolated fresh consumers with no project imports. The extension solved
  3/3 new worlds; absence, semantic mutation and corruption failed; live fault and byte-exact
  rollback removed then restored the capability. A precommitted complete ephemeral projection made
  clean replay exact: 12/12 conditions true. Result `17642e0e…`; stable evidence `497b6aab…`;
  checker `d2a381a6…`.

- **M098 attempt 1 is preserved negative at 11/12.** Every direct persistence, isolation, control,
  fault and rollback condition passed, but the frozen stable projection removed singular PID fields
  while retaining the aggregate `consumer_pids` list. Replay therefore failed P12. Removing only
  that field in a disclosed post-verdict diagnostic made the records equal, but M098 was not
  repaired or rerun. Result `3cce5155…`; checker `b04513a2…`.

- **M097 qualifies endogenous repair-operation acquisition.** From freeze `3b1dd98`, the lineage
  exhausted 2,800 symbolic stack programs and registered the minimal independently accepted
  `PUSH_LEFT, PUSH_RIGHT, SUB` definition. Inherited/acquisition-ablated scored 0/4; the restored
  extension execution-confirmed 4/4 fresh real-Python worlds. All 12 conditions replayed true.
  Result `e976788f…`; checker `00334618…`. Hard process persistence is later qualified by M099.

- **M096 qualifies contract-safe compositional reach.** H41's frozen 4 × 3 population ran locally
  once from `d0c91c3`: exact closed mapping contracts demonstrated 8/8 positive relations and kept
  4/4 zero-demand controls negative, with zero model, network or remote calls. The independent
  replay computed all 10 conditions true. All six partial-contract positives failed under inherited
  subset acceptance while both complete-contract liveness controls succeeded in both arms. Result
  `feb53219…`; checker `fe31bc05…`. M095 remains negative; M097 is the next boundary.

- **M095 attempt 1 is a preserved negative qualification.** H40, an eleven-condition protocol and
  an exhaustive nine-entry structural population were frozen before any qualification chain ran.
  From clean commit `951c7c2`, with zero model/network calls and no retry, all nine entries ran:
  0/6 demand-bearing entries execution-confirmed B after A, while 3/3 zero-demand witnesses remained
  negative. The checker recomputes eight passes and three failures — P3, P5 and P6 — and replays every
  entry exactly. A was reached in all six positives, but its locally accepted renderer emitted extra
  keys; B's exact nested mapping rejected every structural survivor. Result `bdd35111…`, checker
  `bb24a484…`. H40 is refuted, D064 records the negative, and no post-verdict repair is made.

- **Sixteen commits cited by SHA in the registers were reachable from no ref at all.** Among them
  M042's frozen protocol, the M050-M052 development results, the M012/M013e status records and
  M094's own freeze commit `dd79665`. They resolved only because one clone had not yet garbage-
  collected them; routine branch cleanup would have made those citations unresolvable while
  leaving the record looking intact. All sixteen are now preserved as annotated `provenance/<sha>`
  tags pushed to the remote, and every tip that was not merged into `main` as a `branch/<slug>`
  tag. `docs/COMMIT_CITATIONS.json` records all 189 cited commits with the ref that preserves each,
  and `scripts/check_repository_integrity.py --citations` fails if any citation stops resolving or
  if a new one is added without a preserving ref. A shallow clone is reported as unanswerable
  rather than passing.
- **A failure record for eight frozen milestones existed on no branch reachable from `main`.** The
  account of why every independent checker from M077 through M083 failed on a fresh Windows
  checkout was written on 2026-08-11 on a side-car branch. The repair travelled to `main` as a
  one-line `.gitattributes` commit (`531a447`); the explanation did not, and the branch was never
  merged. It is now in `FAILURE_LOG.md`, with its contemporaneous text unaltered and the range
  discrepancy in its own source recorded rather than quietly resolved. Its successor-facing
  warning matters beyond that incident: `git add --renormalize .`, the obvious repair, would have
  staged CRLF bytes as new blob content and rewritten every frozen digest in exactly the direction
  the fix exists to prevent.
- **`experiments/M086/DISQUALIFICATION.md` stated that the repair "has never been merged".** True
  when committed at 09:33 on 2026-08-12, false seven hours later. The sentence is preserved as
  written and corrected in place beneath, because it is a claim about repository history and not
  about M086-A's disqualification, which is unchanged.
- Deleted the branches whose work `main` already carries, after establishing per branch — by
  patch-id, blob identity and full tree comparison — that nothing on them was absent from `main`.

- **The M095 counterfactual was the control, run a second time.** Its world was built as S0 and
  left untouched, so it searched a byte-identical tree for the same requirement with the same
  operation set — both digest alike, both examine 191, both find nothing — while being presented
  as a fourth independent pillar. It now replays the S0 round skipping only the repair that made
  the nested operation applicable, so it removes A rather than everything: unchanged in the
  declared world, and 143 examined with B still unreachable where capabilities tie. The claim
  becomes *A specifically*, not merely some first-round repair.
- **A probe that never ran was recorded as candidates that ran and failed.** `executed` came from
  the survivor count whatever happened, so an instrument that could construct no case reported
  *N executed, 0 confirmed* — a refutation of the repair, where in fact nothing was tested.
  Amendment A1 for the fifth time in this milestone, in the very field added to repair A2.
- **M049's qualification commit does not exist in this repository.** `PROJECT_STATE.yaml` and
  `experiments/M049/{PROTOCOL,DEVELOPMENT_RESULT}.md` name `b8a8bb06` as the commit CI run
  31076192847 qualified for M049's positive bounded development result. The object is absent —
  not dangling, absent — so it predates the provenance tags and could not have been preserved
  by them. The result is not wrong; it is **unverifiable from the record as it stands**. Found
  because the citation guard was extended to check values written in `*_commit` fields, which
  is the only part of it that can see a citation lost before the manifest existed. Recorded
  under `known_unresolvable` as a loss rather than excused.
- **The citation guard could launder the loss it exists to catch.** Three defects in the check
  added earlier on this branch, all found adversarially. `--record` rebuilt the manifest only
  from what was reachable, so an unreachable citation vanished silently and the next check went
  green — deleting nine provenance tags in a clone took 192 entries to 183 with exit 0 and no
  output. The tag preflight could not tell a missing fetch from a deleted tag, and its early
  return suppressed the list of what was actually gone while offering a remedy that cannot
  work. And a citation that resolves to nothing was structurally invisible, because the scan
  matched against reachable commits — the population it could not see was exactly the
  population already lost. All three repaired, with `--record` now refusing to drop a recorded
  citation.
- **An adversarial pass found that two of M095's three arms reported `satisfied` while the
  mechanism they measure was dead.** Five independent machine review passes were asked to break the arms
  rather than confirm them. `more_budget` derived its verdict from an empty sweep, which is
  exactly what a dead searcher produces — three separate kills each left it passing, one of them
  amendment A1 running backwards, with an unconstructible case read as a confirmation.
  `random_target`'s pass was fixed before it ran, because B needs a renderer on the inner class
  and every eligible rival targeted the outer one; it also counted the control's own target as a
  rival, and a test asserted the resulting miscount. It now reports **`unrunnable`** in the
  declared world, which is what this world can honestly support.
- **Amendment A4's defect survived a third time, inside the loop written to remove it.**
  Reversing the tied set — legitimate, since A4's premise is that tied members are
  indistinguishable by the measure — flipped the whole `inner==outer` regime and refuted the
  published domain. The mechanism had worked: the nested repair was reached in the first round,
  after its enabler, and the record only read the second round. Now recognised in either round
  and pinned by a test that permutes every tie and requires the sweep unchanged. Two further
  asserted booleans were removed, one of them written by the commit that removed the previous
  three; `enabling_demonstrated` no longer accepts a run that never identified A.
- **M095's enabling relation now holds in every world where an enabling repair exists — six of
  six, up from two.** The milestone had recorded an ordering boundary it believed it had to carry:
  where the repair that enables B draws less demand than B itself, the greedy rule never ranks it
  and the chain stalled with the remedy sitting untried below it. The audit called escaping it
  something that "needs handling this milestone does not have".
  It needed one observation. **A failed search already names its own obstacle** — the operation it
  could not apply, which knows which class must supply which rendering — so the lineage asks the
  failure what would unblock it and repairs that, unranked. Nothing is added to the operation set;
  only which target is attempted changes, which is what keeps it inside M095 rather than M096. The
  claim loses its ordering qualifier and keeps a smaller one about existence: if the inner class is
  never rendered directly there is no insufficiency to descend to. The arrangement arm sweeps two
  such points so it still has arrangements that must come out negative, and the test that asserted
  the old boundary — written so that a boundary moving outward would be loud — is what made the
  improvement visible rather than silent.
- **M095's enabling result held in two of six worlds, and said so nowhere.** `DESIGN.md` disclosed
  the world's one arrangement — three inner call sites against two outer — and separately that the
  diagnosis's selections are not authored. Both true; neither answers whether the result *depends*
  on the arrangement. Sweeping every way the two demands can compare showed it does. A second
  design-audit pass records four further defects (5–8): amendment A4's tie rule was applied at S1
  and not at S0, where `run` took the head of a name-sorted list; `WorldFacts` reported the module
  constants rather than the world on disk, so every point of the sweep would have been recorded as
  the declared world; `A` was defined by position rather than as the repair after which the nested
  operation can apply. Repairing the S0 rule recovers the equal-demand worlds — four of six. The
  remaining two are a boundary, not a bug: where the outer class has more call sites the enabling
  repair is outranked by the repair it enables, and a greedy rule cannot reach downward. The claim
  now carries that domain and is pinned in both directions. Four of the eight audit defects were
  regressions of amendments already bought and written down.
- **Three M095 arms are built** in `metamorphosis/m095_arms.py`, each reporting M094's
  three-valued outcome. World-arrangement: `satisfied` over six derived points, and able to fail in
  both directions — a world in the excluded regime that *starts* working refutes it too. Random
  target: every rival exhausted rather than one drawn, so no seed is needed; `satisfied`. More
  budget: swept to a ceiling equal to the offered operation set, exhaustive by construction because
  no operation applies twice; nothing reached at any bound and the search closes at 4.
- Fixed a gap in `check_repository_integrity.py --orphans`: `from package import module` recorded
  only the package, so any module imported by the idiom this codebase mostly uses looked
  unreachable from every entry point.

- **Historical pre-freeze M095 state:** the mechanism was built and measured while nothing was
  frozen or armed. It asks
  whether an adopted repair changes what the lineage can reach. In an authored, disclosed world
  the diagnosis selects `Reading` first and `Sample` second on its own, and the repair it builds
  for `Sample` calls the method it built for `Reading`. From S0 the second repair is
  **unreachable** — the search exhausts 191 compositions and finds none — and from S1 it is
  reachable with 12. Two counterfactuals separate the causes: removing A leaves B unreachable, and
  withholding the nested operation at S1 leaves B unreachable. So A is necessary and the operation
  is the vehicle, which is a smaller claim than "A enabled B" and the one the evidence supports.
  The operation set is identical in both states; what changes is that one member can apply, read
  from the code. `experiments/M095/DESIGN.md`.

- **M094 returned a positive qualified scientific result**: the lineage located the component
  limiting it and built the repair, without being told which component or what the change was.
  Run at `43ef9d30` as attempt 2. The diagnosis selected `mira_core/contracts.py` by measurement
  and repaired both classes tied at the top demand, `Goal` and `Observation`; the adopted mechanism
  is `259e12f5`. The qualification, drawn after adoption from the mechanism's own digest, is 2/2
  satisfied and cross-component — `AgentResult`, which needs a computed `@property` rendered, and
  `ContainerSpec`, which needs a key bound to a differently-named field. All twelve conditions are
  computed and true. The random-selection and template-only arms each closed nothing, and more
  budget over the same operations reached the same mechanism.
- **Four amendments preceded the run, all before arming and all recorded permanently in
  `experiments/M094/PROTOCOL.json`.** A1: the qualification pool's hidden cases had been synthesised
  and never executed, and seven of nine entries raised on construction, so the instrument could not
  measure — the pool was regenerated with every case verified by construction and the superseded
  pool preserved. A2: acceptance inspected a candidate's syntax where it needed to run it, so a
  repair that read correctly and raised when executed could be adopted. A3: the protocol's
  design-audit digest named no committed artifact, and nothing compared them — the check was added
  first and the digest corrected second. A4: when two classes tie on demand the one repaired was
  decided by alphabetical order, so every class the measure ranks equal first is now repaired.
- **Attempt 1 is withdrawn and preserved, not deleted.** Its verdict was positive and its P11
  evidence was not what P11 claims: `restoration_is_byte_exact` was computed over decoded text and
  could not see the rollback normalise a component's line endings from CRLF to LF. Rather than
  repair the defect after a verdict — a falsifier the protocol names — the attempt was withdrawn,
  `TransformationStore` was corrected to adopt and restore in bytes, and attempt 2 was run on the
  same mechanism and therefore the same draw. `experiments/M094/POST_VERDICT_DISCLOSURE.md` keeps
  attempt 1's account unaltered.
- Recorded a repository audit at `docs/REPOSITORY_AUDIT_2026_08_18.md`, which is where the M094
  pipeline and checker defects were first measured, and ran the suite in parallel: 46m19s serial to
  15m28s with `pytest-xdist`, identical results. `pytest-xdist` is the only new third-party
  dependency and is declared in `docs/THIRD_PARTY_DEPENDENCIES.md`.

- Added M092-B's deterministic, resumable typed program enumerator without running target search.
  It visits structured one-loop programs breadth-first under the frozen seed, cap, opcode, register,
  literal, jump and loop bounds; alpha-normalises register-renaming duplicates; derives a
  target-neutral quota that reaches every length 6–14 despite multi-billion raw layers; statically
  checks reachability and the stack frame; and commits every raw proposal to a digest-bound cursor
  and ordered event chain. A 512-proposal replay is byte-identical across a serialized resume at
  ordinal 137.
  The enumerator has no target postcondition, executes no program and produces no certificate,
  qualification, extended state, receipt or result; raw proposals are not protocol candidates.
- Added M092-B's post-freeze structural and anti-cheating candidate gate without starting search.
  It binds certificates to exact K1 bytes, enforces the frozen 14-instruction/opcode/literal/loop
  surface and scans generated support for tables, masks, equality chains, callbacks/imports,
  fixtures, target names and domain-sized output carriers without executing the candidate. All five
  frozen rejection fixtures fail for their exact expected codes, a hostile callback is never
  called, and the neutral baseline redigests byte-identically after restoration. The self-test also
  passes in a read-only `python:3.13-slim` container with no network. No search, qualification,
  extended state, receipt or result exists; H38 and D062 remain unclaimed.
- Implemented the post-freeze M092-B exact certificate verifier without starting extension search.
  It recomputes each candidate CFG, symbolically covers integer branch paths, checks normalized
  affine induction and postcondition obligations from candidate-supplied integer witnesses, proves
  a well-founded variant and linear K1 fuel bound, and establishes the stack/slot/input frame
  structurally. The only positive development fixture is the frozen neutral countdown-to-zero
  rehearsal; wrong binding, false proof, non-decreasing variant, wrong postcondition, false frame
  and finite-vector certificates all refuse. No qualifying candidate or result exists; H38 and
  D062 remain unclaimed.
- Froze the M092-B pre-search protocol against the exact M092-A checkpoint: eleven causal/control
  arms, six dependency ablations and fifteen conjunctive conditions. Global correctness is an exact
  program-bound affine certificate over every `x >= 0`; execution over `0..2999` is explicitly
  separate corroboration. The candidate/program/certificate searches, isolated validation receipt,
  content-addressed registration, downstream language dependency, two-family hidden draw, three
  rollback boundaries and anti-table scanner are all bounded before search. No M092-B candidate,
  qualification, extended substrate, receipt or result exists at this freeze; H38 and D062 remain
  unclaimed.
- Froze the separate M092-A checkpoint before any substrate-extension search or qualification.
  Checkpoint `d8bacb1c...6ce8` binds seventeen exact blobs from source commit `5adfaa6`, proves the
  six M092-B artifact paths absent there, preserves zero acquired substrate operations and seals the
  `296230ae...c84717` state digest after 2,340,480 exhaustive legal comparisons with zero mismatch.
- Continued the pre-checkpoint review after Claude's handoff and corrected two defects while M092-A
  was still unfrozen: fuel now scales with stack and slot operands as well as inputs and call
  arguments, and ambiguous serialized contracts (negative dimensions/arity, duplicate domains or
  primitive identifiers, inconsistent dispatch and unavailable capabilities) fail closed. The
  substrate digest and every conservation outcome are unchanged. Recorded public disposition P-008
  before the branch's first remote push. H38 and D062 remain unclaimed; M092-B has not started.

- Added M091, in which the lineage adds an operation to the language it actually owns. **Positive,
  attempt 1, no retry**, fourteen frozen conditions computed and passed; H37 supported, no gate.
  Protocol frozen at `5e4a0fe`, result `d83b836d...4c07af`, 0 model calls.
- Chose an expressive gap that is deliberately **not** M089's. That one was fan-in and is spent;
  M091's requirement reads one input position and is instead **non-affine**, and the validator
  refuses M090's fan-in probe as overbroad. The insufficiency is proved by a closure lemma over the
  whole abstract domain — a one-step property that induction carries to any length and therefore any
  budget — an abstraction re-checked against the concrete interpreter, and a finite certificate that
  refutes an infinite class with three non-collinear points.
- Answered the M055 falsifier by measurement rather than argument: the `macro_only_extension` arm
  reproduces M055 on purpose, memoizing a composition and cutting its own search from 38,848
  programs to 5,477 and its program from four operations to three, and solves 0/2 qualifying worlds.
  The adopted primitive appears in the same table with the opposite entry — unreachable without it,
  two operations with it. Cost is not reach.
- Split the generic search into `m091_search` so the persistence check holds the interpreter, the
  requirement schema and nothing that could rebuild a primitive. The fresh process prints its own
  import census and it is checked.
- Registered M091's digest-bearing artifact paths in `.gitattributes` in the same commit as the
  frozen protocol, before any digest existed, and verified the committed blob is byte-identical to
  the working tree. Recorded the pre-publication IP disposition as P-007 in the same commit.
- Raised the sealed-bank CI job's timeout to 30 minutes and made `check_m091_result.py` decisive
  there: it re-runs the acquisition, re-verifies every certificate against the requirement and the
  body, re-materializes the qualification from a recomputed salt, replays every arm including the
  depth-six budget arm, and recomputes the verdict.

- Added M086-C, the third attempt at H32 and the first that could have failed for a scientific
  reason. **Nine of ten conditions passed; P2 failed.** H32 moves from untested to **not supported**
  by the two attempts with a qualified instrument, M086-B and M086-C — a statement about those
  attempts, not a finding that meta-plasticity is impossible.
- Corrected the bank grammar after M086-B by probing what M047's templates can actually repair:
  `add` and `mul` collide with `tool_core`, `mul` has no product expression, and a tool named
  `max` shadows its own builtin. **`mean` is the only repairable missing-route operation**, so the
  routeless operation cannot vary and the protocol says so rather than pretending to a choice.
- Recorded, before the run, the falsifier that then fired: a `mean a b c` case is passed by both
  the `mean` and `midpoint` expressions whenever the operands are arithmetic, the frozen order
  takes `midpoint`, and the hidden cases decide. The salt drew `1 2 3`, and the adopted patch was
  `synthesize_tool:mean:midpoint`.
- Recorded D054 and a FAILURE_LOG entry naming what was never mutable: every meta-primitive acts on
  the hypothesis schema or the rule set, and the greedy selection rule that picks the adopted
  candidate is frozen and human-authored. Capability to generate is not capability to solve.

- **Reclassified M086 as M086-A, post-hoc disqualified development evidence.** Review of PR #130
  found four defects: the recorded protocol digest binds the CRLF working-tree copy rather than the
  committed blob (the M064 class recurring), P8 was never implemented and P7–P10 never entered
  `evaluate()`, the holdout existed before the meta-search, and the replay covered 3 of 14 fields
  per arm. H32 returns to untested; no gate moves.
- Preserved every M086-A artifact, digest, CI record and history entry unchanged. Only the claim was
  withdrawn, and `experiments/M086/DISQUALIFICATION.md` states why.
- Recorded D053 and a FAILURE_LOG entry. The four defects share a shape: each makes part of the
  frozen contract unenforceable while leaving every visible signal green.

- Added M086, which makes the mechanism that turns evidence into candidate transformations a mutable
  artifact. M047 froze it in one line — `ModuleDiagnosis.sufficient` is `self.module is not None` —
  and against evidence naming two stages at once it emits **zero** candidates.
- Proved the expression faithful before using it: over 10 differential probes on two bodies, M0
  returns the same diagnoses and the same candidate sets as M047's own functions.
- Enumerated the starting mechanism's complete constructive image for the holdout and found it empty,
  so the control's failure is structural rather than budgetary — a capability difference, which is
  what M084's efficiency-only result said the next milestone had to produce.
- Recorded that the lineage rejected seven meta-transformations on disposable descendants before
  adopting one, and that the adopted one was **not** the composition the protocol predicted: widening
  the hypothesis schema alone sufficed.
- Kept the evaluator outside the mutable body, enforced by a checker: the mechanism cannot name the
  hidden cases, cannot reach the sandbox, and the meta-search is only ever handed the development
  limitation. M069 is the recorded precedent.
- Studied HyperAgents (arXiv 2603.19461) from the paper and the official repository and recorded
  `docs/HYPERAGENTS_COMPARISON.md`: their question was taken, their method refused, and the archive,
  population and parent selection deliberately postponed.
- Recorded H32, D052, and two FAILURE_LOG entries: a latent defect in M047's `render_tool_module`,
  which emits a self-recursive `def max` for a tool named `max` and is deliberately **not** repaired
  because it would change M047's preserved digests; and an M086 bank whose repair revealed a new
  fault while a greedy tie-break locked in a wrong alias, which looked like a clean negative and was
  a property of the bank.

- Prepared M085, the first experiment here aimed directly at G4, and left it **blocked**. Its design
  protocol, domain adapter contract, intake kit, maintainer brief, fail-closed gate and 32
  regressions are committed; no scientific protocol is frozen, no bank exists, no payload has been
  requested and no held-out domain has been drawn.
- Built a separate external boundary rather than reusing M075's. That validator hard-codes refusal
  thresholds, the `gpt-5.6-sol` identity and a refusal-transfer-only claim, so a G4 protocol fails
  it on every such field. `exact_mcnemar_two_sided` is imported from M075 rather than restated, and
  M075's own private experiment remains open and unsubstituted.
- Made correctness the primary outcome, not cost. The bank must supply tasks where an action is
  accepted without effect, a later step is only correct if it took effect, and committing on the
  false premise reaches a terminal state the budget cannot undo. The freeze validator rejects a
  protocol that promotes a cost metric to the primary outcome.
- Made the held-out domain undrawable in advance: it comes from the sealed payload digest and a salt
  the maintainer withholds until after the protocol is frozen.
- Chose the threshold and the minimum bank size together — six discordant tasks give an exact
  two-sided p of 0.03125, five give 0.0625 — and asserted both halves in a regression so neither can
  be moved alone.
- Recorded H31 and D051. Running M085 on project-authored domains is listed as a prohibited
  adaptation, because it is the cheap substitute available on any day the external route feels slow.
- Built the organism-side shim before any bank exists, and found what named negative 5 anticipated:
  M084's `Embodiment` abstracted acting and observing, while the organism still reached into M084's
  own carrier tables in **ten** places — memory keys, memory contexts, carrier costs, probe carriers,
  the seeded carrier, the value alphabet and the one-carrier-at-a-time read.
- Routed all ten through a registered `DomainView`. M084's three substrates register views built from
  the tables they already used, and every arm re-derives its recorded numbers exactly.
- Added a wiring control on a toy domain sharing no vocabulary with M084, and recorded in
  `FAILURE_LOG.md` that its first version passed while running zero probes and zero repair cycles: a
  modulo cost formula made the discarding slot expensive, so the planner routed around the trap it
  existed to hit. The control now fails if it does not exercise repair.

- Added M084, one persistent lineage crossing `shell → browser → desktop → shell` in four separate
  operating system processes. It reached 11/11 reachable goals scored from environment state,
  refused 5/5 unreachable ones with zero false refusals, and on its return to the shell — with
  carrier names the first stage never saw — needed no diagnostic probe, no repair cycle and no
  affordance discovery.
- Composed the Phase 8 mechanisms instead of restating them: M077's journal, M080's bounded table,
  M079's plan enumeration and the M081–M083 environments are all imported, and a regression and the
  checker fail if any is redefined.
- Extracted M079's uniform-cost plan enumeration into `metamorphosis/bounded_search.py` so both
  experiments use one copy. Behaviour-preserving: M079's checker re-derives its arms live and still
  reproduces result `5f7ccf21`.
- Added `DesktopEnvironment.colour_at` for targeted single-cell reads, 0.3 s against 8.9 s for the
  whole grid. `state` is unchanged and the M083 result is untouched.
- Recorded that M081, M082 and M083 are **interface** results: the agent they carry across four real
  substrates replays an action list computed by their bank generator and detects no failure. M084
  deliberately does not import it, and the protocol, a regression and the checker enforce that.
- Answered the M082 state-ownership failure structurally rather than by inspection. Each stage runs
  in a separate process against an organism file, the parent never calls a perception, planning or
  action function, and the organism records the digest of the file it loaded.
- Detected a corruption injected after stage 1 **in the stage-2 child** and restored to the digest
  stage 1 had recorded before the corruption existed, never to the checkpoint's own digest.
- Recorded amendments A1–A3 from two pre-materialization rehearsals on throwaway salts. A1 fixes a
  carrier-rejection predicate that generalized from one-sided evidence and made the lineage falsely
  refuse a reachable goal; the zero-false-refusal clause is what caught it.
- Recorded H30 and D050. **No generality gate advances.** The ablation costs no correctness, so
  persistence bought cost and earliness rather than capability, and a fact learned in one substrate
  is never offered to another, so nothing here is cross-domain transfer.

- Added M083, a real X11 desktop session as a fourth environment under M081's unchanged
  four-action interface. It is addressed only by mouse clicks at screen coordinates and observed
  only by decoding exact palette colours from a screenshot; the interface completed all five
  completable tasks.
- Stated in the protocol, the result, a regression and the checker that this is **not a virtual
  machine**. A container shares the host kernel, no hypervisor was available, and the only VM
  present was the host's own WSL2 distribution. G6's desktop-VM clause remains unmet.
- Discovered the client-area origin from the X server at run time instead of assuming it. The
  window manager places the window where it chooses, and an assumed origin painted and read
  different cells while every call still returned success.
- Dropped the keyboard by design, with the reason recorded: xdotool could not focus a Tk entry,
  and a clicked palette exercises coordinate-and-pixel interaction fully.
- Recorded H29 and D049. G6 stays at partial mechanism evidence: no desktop VM, no physical
  device, no external suite, and coordinate-and-pixel competence on one authored window rather
  than general desktop competence.

- Added M082, a real Chromium browser as a third environment under M081's unchanged four-action
  interface. The interface completed 5/5 completable tasks in the container shell, the HTTP
  service and the browser, covering all three in one run.
- Kept the browser from being the service in a costume. Its store lives in localStorage with no
  HTTP route, reachable only by filling inputs, clicking and reading rendered DOM nodes; the
  crossed-driver arm completes nothing in all three environments, which demonstrates rather than
  asserts that the substrate differs.
- Imported M081's agent and both prior environments unchanged rather than restating them, with a
  regression and the checker failing if any is redefined.
- Recorded three transport defects found while proving the mechanics: MSYS path conversion
  mangling `docker exec` arguments on Windows, the same class as the negative M070; a fresh
  browser profile per action that would have left the harness holding the state instead of the
  browser while every test still passed; and a page flattened into an environment variable where
  a `//` comment silently disabled the save handler.
- Recorded H28 and D048. G6 stays at partial mechanism evidence: **no desktop VM**, no physical
  device, no external suite, and DOM competence on one authored page rather than general web
  competence.

- Added M081, a second real environment under one unchanged agent interface. A POSIX shell in a
  network-disabled Alpine container and a real Python HTTP server process in its own container
  both receive the same four abstract actions; the shared interface completed 5/5 completable
  tasks in each, judged from a fresh environment-state read.
- Made the scoring rule measurable rather than asserted. Each environment carries one task whose
  action returns success while the state does not change — a shell script swallowing a failed
  write with `; true`, and a service answering `204` to a write it discards. Judged by the
  agent's claim the interface looks 12/12; judged by environment state it is 10/12.
- Added a crossed-driver control that completes nothing, which is what shows the two environments
  are distinct systems rather than one mock wearing two labels.
- Recorded amendment A1 and two construction fixes. The first freeze required all six tasks per
  environment to complete while specifying one that is uncompletable by construction; A1 resolves
  it by strengthening, requiring the sealed task to be observed failing while claimed. The crossed
  arm originally swapped both driver and environment and crossed nothing, and the sealed task
  originally expected nothing and scored its own discard as a pass.
- Recorded H27 and D047. G6 stays at partial mechanism evidence: **no browser, no desktop VM**, no
  physical device and no external suite, and the container-backed regressions skip in CI under the
  existing opt-in, so CI attests the structural half only.

- Added M080 and measured forgetting for the first time. Six skills are acquired in sequence into
  one bounded 24-slot table where later skills reuse an earlier rule and demand a different output
  for an exception key the donor owns, so the cheap in-place rewrite is always available and always
  destructive. The lineage lost zero capabilities, used 19 slots against a private-slot ceiling of
  24, reused three rules and rolled back twice byte-identically.
- Recorded the limitation as a headline, not a caveat: retention is **replay-dependent**. Removing
  the replay of earlier examples costs five capabilities, exactly as much as removing consolidation.
  The protocol preregistered no direction for this measure so neither outcome could be chosen after
  the fact.
- Fixed and recorded three instrument defects before materialization: capacity pressure alone never
  bound so no arm evicted anything; retention scored on holdouts alone hid damage that lands on
  exception keys; and the rollback check compared the checkpoint against its own digest and could
  never fail. A regression and the checker now assert that a rollback mismatch stays reachable.
- Recorded H26 and D046. G5 stays at stronger partial bounded evidence with forgetting measured;
  closure needs capabilities maintained outside this project plus independent reproduction.

- Added M079 and exercised all four G3 clauses in one bank: planning with no supplied
  decomposition, plan revision under revealed evidence, terminal verification from world state,
  and calibrated clarification. The planner solved 8/8 static and 8/8 revision tasks within
  budget, revised on all eight, asked on 8/8 ambiguous goals and 0/16 unambiguous ones, and
  reached zero unsafe terminal states.
- Made committing on an ambiguous goal demonstrably harmful rather than merely possible. Every
  ambiguous episode admits two terminal states that both satisfy the literal goal and differ on
  safety, with the hazardous one strictly closer, so the `never_ask` control took it
  deterministically and reached six unsafe terminal states. The `always_ask` floor solved
  nothing, and asking is never scored as success.
- Recorded two construction fixes rather than hiding them: sealed states became terminal in the
  search, and the revision family now blocks an edge the initial plan actually traverses after an
  arbitrary block was routed around in three of eight episodes. No threshold moved.
- Recorded H25 and D045. G3 stays at partial bounded evidence with all four clauses exercised;
  closure needs a world maintained outside this project plus independent reproduction.

- Added M078 and exercised the one G1 clause M068 never tested: an incompatible opaque body must
  produce a calibrated refusal rather than an invented adapter. One unchanged procedure adapted all
  four compatible bodies with 12/12 hidden observations each, refused all four incompatible bodies,
  and produced zero false refusals, zero invented adapters and zero empty-set refusals.
- Built each incompatible body so refusal cannot be an exhausted search. One command is stitched
  from two skills over their disjoint public inputs, so a candidate fitting every public observation
  always exists. The `never_refuse` control adopted one on all four bodies and failed hidden
  validation four times, which is what establishes the public evidence as insufficient; the
  `always_refuse` control recovers nothing.
- Enforced the M069 information boundary structurally: a regression and the checker both parse the
  `discover` function and assert it never reads hidden observations, the body class, the aliased pair
  or the internal operation table.
- Recorded H24 and D044. G1 does **not** advance: the bodies are project-authored, and closure needs
  an externally maintained interaction language plus independent reproduction. D044 also forbids
  citing M078 as repairing M074, whose negative remains the only result on model refusal.
- Added the M075 independent-maintainer intake kit. The readiness gate already states that the
  project may not proceed without a signed external attestation, but reconstructing its 22-field
  closed envelope, opaque domain identifiers and signature namespace from source was hours of work
  for an outside volunteer. `metamorphosis/m075_intake_kit.py` and
  `scripts/run_m075_intake_kit.py` emit the template, print the exact `ssh-keygen` commands and
  validate a candidate envelope before it is sent, reusing the gate's own validator so the two
  cannot diverge.
- Added `experiments/M075/MAINTAINER_BRIEF.md`, a standalone brief for someone with no prior
  knowledge of the project: what they attest, what they must refuse to hand over, and the ordering
  that makes the arrangement evidence rather than theatre.
- Pinned the boundary in regressions: the kit has no process, network or archive module in its
  import graph, so it cannot sign or open payload, and it still rejects a project author as signer.
  Readiness remains fail-closed and unchanged at four blockers.
- Added M077 and preserved it as a **negative** result on H23. One persistent lineage ran shifts of
  32, 128, 512 and 2048 episodes over a typed sixteen-slot pool with a digest-chained journal, under
  four declared invariants and four injected fault kinds.
- Refuted the preregistered dissociation. Removing checkpoint recovery cost exactly restoration
  (0.00 at every horizon) while leaving detection numerically identical, as predicted. Removing the
  boundary constraint monitor did **not** cost detection: silent corruption eventually breaks a
  guarded operation, so the monitor buys detection latency rather than coverage.
- Preserved two positive sub-results without promoting them to a gate advance: the full arm held
  every invariant, recovered every fault and required zero interventions at all four horizons with
  no degradation as the horizon grew; and checkpoint recovery was causally isolated by its matched
  ablation. G7 remains open.
- Recorded both M077 instrument corrections in the result rather than hiding them, and added a
  checker that fails closed if the preserved negative is ever silently converted to positive.
- Added M076, the first endogenous result to address generality gate G2. One persistent
  deterministic agent consumes a UTF-8 instruction, an ordered structured mapping and a raw
  1728-byte RGB888 raster, and emits both symbolic `set_dial` calls and embodied effector moves
  scored from terminal grid state. The full arm reached 36/36 across three precommitted families.
- Recorded an exact triple dissociation under matched ablations that preserve byte length, key
  order and token count: each ablation zeroes its own dependent family and leaves both others at
  exactly the full-arm score, against a measured guessing floor of 3/36. G2 moves from open to
  partial mechanism evidence and is explicitly not closed.
- Preserved M076 amendment A1 rather than repairing it silently. The first freeze paired a
  chance-distribution floor with a bound of one success across 36 episodes, which no faithful
  guessing policy can satisfy; the bound was corrected before materialization and the arithmetic
  is recorded in the protocol.
- Added M075's fail-closed pre-private readiness layer. It accepts only a signed closed-metadata
  envelope from a non-project maintainer, requires at least eight matched capability pairs across
  four opaque domains, and refuses reveal until an exact scientific protocol binds the envelope.
- Precommitted the paired causal minimum: each private task runs once per condition on fresh clones;
  thresholds require 6/8 true refusals, zero false refusal, complete feasible success, eight saved
  steps, six context-only/zero baseline-only correct terminals, exact McNemar `p <= 0.05`, zero
  faults and separate-bank reproduction. Current readiness correctly remains false.
- Completed M075's single committed public model-development comparison: 12/12 fresh containers,
  43 live decisions, zero defect/retry/replacement. Epistemic context produced 2/3 true refusals,
  no false refusal, 3/3 feasible external success and four wasted steps versus baseline 0/3, no
  false refusal, 3/3 and twelve.
- Preserved the read-only-write miss: even with three visible failures and one remaining decision,
  the model acted again. D041 closes tuning on the contaminated bank and requires a causal-control
  and sealed external-bank review before any private execution. H21 remains untested.
- Added permanent byte-exact protocol/result verification for all task/code/runtime bindings, 43
  request/response records, information boundaries, ledgers, Docker attestations, live labels,
  external outcomes and recomputed calibration. Result SHA-256 `dadd2028`; calibration `d0226c09`.
- Exact evidence commit `0c19d6b` passed the complete local Python 3.14.6 suite on its first run:
  1,369 passed, two skipped in 2,390.27 seconds, plus all repository-integrity modes.
- Published head `2dd6ccb` passed first CI run `31398661236`: 1,370 passed/1 skipped on Python 3.11
  and Python 3.13, plus integrity. Attribution run `31398661318` passed; no workflow rerun was used.
- Began M075 as a separately numbered successor to the negative M074 result. Added a task-agnostic
  epistemic projection of remaining budget, failure persistence and exact action repetition without
  exposing labels, solutions, evaluators or arm identity.
- Added a distinct public Node/write/read development bank. Its zero-token deterministic policy
  completed 12 fresh real-container episodes with six exact live labels and zero defect; preserved
  record SHA-256 `cb194a40`. This is apparatus evidence only and H21 remains untested.
- Preserved M074's single frozen scientific campaign as a negative result. All 12 paired episodes
  completed without defect or retry; all six feasible arm episodes succeeded and no impossible
  episode did, but the model emitted zero refusals, producing margin 0.0 and zero saved steps.
- Froze M074 at protocol commit `28ddd8b` before every model decision. First CI run `31385331662`
  and attribution `31385331849` passed without rerun. The result's raw SHA-256 is `75e84682` and
  its calibration digest is `78d7b27e`.
- Added permanent verification of code/task/runtime bindings, live container attestations,
  capability labels, 24 live decisions, 24 exact paired replays, ledgers, evaluator outcomes and
  the negative verdict. D039 closes M074 and prohibits an in-place retry.
- Exact result commit `1eeb345` passed first CI run `31388068187`: 1,341 passed and one skipped on
  Python 3.11 and Python 3.13, plus integrity. Attribution run `31388066466` passed; both workflows
  used attempt 1 and no rerun.
- Qualified the M074 refusal-calibration apparatus locally without a scientific model call. Six
  exact real-container labels split 3/3 feasible/capability-impossible; a label-blind zero-token
  policy completed 12 fresh two-arm episodes with external final-state checks and no defect.
- Reduced M074 to one causal contrast: identical authority, isolation, budgets and hash-chained
  audit, with only refusal termination ablated. The terminal arm produced development margin 1.0
  and zero wasted steps; the nonterminal arm produced margin 0.0 and 12 wasted steps.
- Hardened capability certificates with explicit absence codes, probe/environment SHA-256 binding,
  cross-environment rejection and exact per-arm task coverage. Preserved the first live failure in
  which unexpected BusyBox code 127 correctly became `INCONCLUSIVE` instead of false absence.
- Added persistent non-root, no-network, read-only-root Docker workspaces with materialized fixtures,
  exact `/workspace` probes, external final-state evaluation and a permanent verifier for the two
  non-scientific M074 development records. The later frozen scientific result remains separate.
- Exact M074 apparatus commit `27a2e1f` passed first CI run `31377768229`: 1,322 passed and one
  skipped on Python 3.11 and Python 3.13, plus repository integrity. Attribution run `31377768244`
  passed; no workflow rerun was used.
- Post-hoc disqualified M069's positive qualification under D037. Candidate code executed in the
  evaluator process holding hidden cases and could return them through an admitted public-output
  path, so the Phase 8 hidden-evidence-reachability falsifier fires. Historical rewards and learner
  behavior remain diagnostic; there is no evidence the frozen learner exploited the path.
- Added an append-only evaluator-isolation disclosure and corrected the status, hypothesis,
  generality, state and roadmap registers without rewriting M069's frozen protocol, bank, learner,
  evaluator or result bytes.
- Preserved M073's first preregistered result: four frozen single-call external demonstrations
  induced one committed identifier-generalized AST capsule. After teacher removal it passed 12/12
  holdouts and 84/84 cases; unchanged-source and exact-hash memorizer controls passed 0/12, the
  corrupted-teacher control induced no capsule and no scientific retry occurred. Result `edaf03b4`.
- Added a permanent M073 verifier that reconstructs teacher prompt bindings, induction, the
  capsule-before-holdout commit boundary, all holdout outcomes, controls and final verdict. The
  supported claim is bounded model-to-lineage skill appropriation, not general programming,
  Genesis Gate 2, safe deployment or AGI.
- Exact M073 evidence head `2eaa5c7` passed first CI run `31370311326`: 1,257 passed and one
  skipped on both Python 3.11 and Python 3.13, plus repository integrity. Attribution run
  `31370349333` passed; no workflow rerun was used.
- Recorded M072's already-fused positive causal-governance result in the root registers: full
  governance satisfies the frozen authored invariants over 48 scenarios, while admission and audit
  ablations each lose 18 matching invariants. No represented action or external model was executed.
- Froze M071 runtime `0820ebc`, Harbor bridge `132476a` and 17 committed blobs before pinning a
  benchmark revision or selecting a fresh external identifier. Commitment `2e76a1b8`; no M071
  scientific result exists.
- Pinned the unchanged Terminal-Bench 2 remote head and a one-draw cryptographic blind-selection
  salt before enumerating eligible identifiers. The rule excludes both closed M070 tasks before
  ranking and forbids replacement.
- Applied the committed M071 rule once: 87 of 89 identifiers were eligible and the fresh pair is
  `sqlite-with-gcov`, then `custom-memory-heap-crash`. Inventory digest `c21c3e62`; neither task
  was opened before the binding.
- Froze M071 execution before any trial: Harbor 0.20.0, digest-pinned images, no-network agent
  phases, four ordered single attempts, zero valid retries/replacements, external success and
  composed-system score attribution. Solutions and verifier tests remain unopened.
- M071 passed its narrow external threshold: official rewards were `0.0` on SQLite and `1.0` on
  custom-memory, while both `nop` floors were `0.0`. All four jobs had zero Harbor exception,
  retry or replacement; success remained evaluator-owned.
- The final local Python 3.14 preservation suite passed 1,225 tests with two skips in 2,257.69
  seconds; repository integrity and every committed external artifact check passed.
- Exact M071 evidence commit `0875fa7` passed first CI run `31332620871`: 1,226 passed and one
  skipped on Python 3.11 and 3.13, plus integrity. Attribution run `31332620902` passed; no
  workflow rerun was used.
- Replaced locale-dependent model and Docker control pipes with strict UTF-8 bytes transport and
  replaced parent-only timeout kills in the model, container and terminal paths with one shared
  whole-process-tree supervisor. Real Windows regressions prove that `U+2011` survives and delayed
  descendants cannot act after a timeout.
- Changed the closed M070 freeze audit to verify the exact historical commit and its committed
  blobs instead of forbidding legitimate post-M070 evolution of the current working tree.
- Rebound the task-agnostic Harbor bridge to a separately named M071 policy, manifest schema and
  agent identity so new evidence cannot be mistaken for a rerun of the closed M070 design.
- Split the endogenous bounded-lineage and M070+ model-mediated tracks explicitly. Genesis Gate 2
  remains unchanged; external model proposals are not lineage-owned and benchmark rewards belong
  to the named composed system rather than Mira's governance layer alone.
- Corrected the stale prior-art statement that no runtime used an external model. The Python
  package still has no provider dependency, but M070+ has an explicit operational Codex/model
  dependency. Added D033 and the Track B attribution rule before M071 target selection.
- Preserved M070 as a negative external development result. The agent design and blind selection
  rule were committed before two of 89 Terminal-Bench 2 tasks were opened or executed.
- Official Harbor v0.20.0 returned reward `0.0` for both Mira trials and both `nop` controls, with
  no Harbor exception, scientific retry or task replacement. Agent phases were `no-network` and
  success remained evaluator-owned.
- Diagnosed the frozen backend failure: locale-dependent subprocess text mode rejected a true
  `U+2011` under Windows `cp1252`, while orphan `node`/`codex` descendants retained the pipe after
  the wrapper timeout. M070 remains unmodified; M071 must freeze a UTF-8/process-tree correction
  before selecting a fresh pair.
- Added the M070 pre-target engineering baseline before selecting any external task: a strict
  provider-neutral structured-model policy, explicit read-only Codex adapter and digest-pinned
  isolated Docker body.
- The container body verifies Docker's realized no-network, no-capability, no-new-privileges,
  read-only-rootfs, resource-limit and single-task-mount contract, and fails closed on mismatch.
- Model/backend and body-reset failures now enter the tamper-evident episode ledger. Submission
  never self-declares success; a later external evaluator must decide from final container state.
- Added the separately frozen M069 repair policy. One unchanged policy repairs four governed
  real-file/process workspaces, passes 3/3 hidden cases per task and refuses an incompatible
  protocol before any write or process execution.
- All ten M069 falsifiers pass, including write-authority ablation, under-declaration, traversal,
  immutable command schema, environment stripping, hidden-output suppression and source-
  inspection controls. A second process reproduces manifest digest `c5c80701` exactly.
- Added a compact governed-terminal demonstration and documented the finite supplied repair
  language, project-authored targets, trusted-host-command and non-AGI limits.
- Qualified exact learner `c603dd5` in run `31319062535`: 1,181 tests on Python 3.11 in
  1,241.52 seconds, 1,181 on Python 3.13 in 1,260.38 seconds and repository integrity all passed.
  Attribution run `31319062599` passed. The final local Python 3.14.6 suite passed 1,180 tests with
  one Windows symlink test skipped in 2,088.15 seconds.
- Recorded H15, D031 and the G1/G6/G10 evidence change; the next accepted step now requires
  post-design external tasks and container or VM isolation.
- Migrated the permanent CI and attribution workflows to the Node 24-based checkout, Python setup
  and Node setup action majors before GitHub's Node 20 action-runtime retirement.
- Added `GovernedTerminalBody` for bounded real-file reads, atomic writes and immutable registered
  subprocesses without a shell, plus path, symlink, environment, timeout and output controls.
- Added body-owned authority requirements so an action cannot gain access by under-declaring what
  its body needs; broken and under-declared contracts fail closed before execution.
- Froze M069 before its repair policy: four compatible real-terminal tasks, one incompatible
  protocol, eleven supplied replacements, hidden evaluator cases and ten falsifiers.
- Added the M068 open command-language learner after a separate target freeze. One unchanged
  engine scans all 37,448 admissible words and discovers four distinct complete adapters.
- All four unique public classes pass 12/12 disjoint hidden observations. Declaration-order,
  lexical-semantic, empty-transcript, corrupted-source, unknown-action, non-command and semantic-
  mutation controls reject, and a second process reproduces the exact manifest bytes.
- Recorded deterministic M068 manifest digest `0f012c41` and tamper-evident Mira Core evidence
  digest `75df381e`; preserved project-authored-target, finite-language and non-AGI limits.
- Qualified exact M068 learner commit `f033ac7` in first run `31314960014`: 1,153 tests on
  Python 3.11 and 1,153 on Python 3.13 plus integrity; attribution run `31314960009` passed.
- Added the first installable `mira_core` runtime with stable body/policy contracts, a bounded
  agent loop, immutable least-privilege admission and deterministic hash-chained memory.
- Added exact checkpoint restoration, tamper rejection, explicit policy refusal, body-fault
  evidence and fail-closed step budgets, plus a dependency-free runnable demonstration.
- Extended repository integrity checks from the historical `metamorphosis` package to every
  installable Mira package and documented the operational architecture and its current limits.
- Defined ten preregistered Mira generality gates covering interface novelty, multimodal grounding,
  planning, transfer, continual learning, real environments, long horizons, governed
  self-improvement, evaluation integrity and safety. M067 remains mechanism evidence, not AGI.
- Added the M068 pre-learner freeze: four opaque command-language bodies, eight action handles,
  37,448 admissible non-empty words, fixed public/hidden evidence and eight required controls.
- Bound the M068 runtime, bank and protocol by portable SHA-256 before any discovery engine exists.
  D028 forbids later target drift and explicitly declines an independent-authorship claim.
- Began Phase 8 with M067, a distinct adaptive-embodiment question that removes the complete
  supplied target adapter retained by the closed M043–M066 construction line.
- Added a separately executed four-body bank committed by SHA-256. Its interface exposes opaque
  handles, acceptance bits and raw replies but no frame, checksum, opcode or decoder descriptor.
- Added a bounded 288-candidate contract search. One uniform procedure discovered four distinct
  adapters across register, stack and mailbox frames; each unique public survivor passed 12/12
  disjoint hidden observations.
- Added empty-transcript, corrupted-transcript, default-adapter, framing-only and semantic-mutation
  falsifiers. All reject; the discovery API has no hidden-evidence parameter.
- Added the Phase 8 agenda, D027, H14, M067 protocol/result records and permanent tests. The result
  is positive and qualified in development. Exact experiment commit `7d38ac8` passed run
  `31311020868`: 1,130 tests on Python 3.11 and 1,130 on Python 3.13 plus integrity;
  attribution run `31311020869` passed.
- Licensed all project software under AGPL-3.0-only and the non-software research record
  under CC BY 4.0.
- Added explicit authorship, citation, provenance and trademark records naming Anthony Mets as
  project author and research director while disclosing AI-assisted implementation and analysis.
- Added Developer Certificate of Origin sign-off requirements for future contributions so that
  public authorship and licensing provenance remain auditable.

## 0.41.0 — 2026-08-09

M065 is preserved as a negative canonical guard qualification. M066 corrects only the Git-history
scope that caused the false rejection; every scientific input and result remains frozen.

- Qualified exact M065 parent `b1489d7a3a264de8a9e783eb139dafe28732b040` in first run
  `31286019961`: 1,101 tests on Python 3.11 and 1,101 on Python 3.13 plus integrity.
- Preserved canonical run `31287477458`, attempt 1, on marker commit
  `a517e6bb76e8476ab6aca8c0a68c5bcfc3501d57`. Guard job `93178824313` rejected before
  bank selection; result and reproduction jobs were skipped and no artifact was created.
- Identified the exact defect: `git rev-list --all` counted the canonical marker and the lateral
  pull-request ref. D025 now defines canonical marker identity over first-parent `main` history.
- Added M066 with no scientific changes, a new executable digest
  `f66ab480dfa0631e730753b7e45e3b83da7e2938d3e28e4aa2f497a6e383d66b` and a portable
  23-file commitment `02cabd7d86a93ceaba811b591b6c271cf066653add61044af83143558e2fd1c0`.
- Added a real Git graph falsifier proving that lateral marker refs are ignored while repeat
  first-parent occurrences are rejected. The first-result job remains attempt-one only.
- Repeated all four banks through the unchanged M065 engine: complete lineage 18/18 with three
  accepted cycles and 68/68 retained; every control 0/18 with zero accepted cycles. Eleven M066
  tests passed in 202.78 seconds; the complete repository passed 1,112 tests in 1,689.93 seconds
  and repository integrity passed.
- Qualified exact parent `4a4b4a1a1e4831a4e1f8a40f896e3b2921cdc6e5` in first run
  `31290364464`, then armed it with marker-only head `2cf454ca4e393a319f89ae5afbcd5e3f9250182c`.
- Preserved positive canonical run `31291899534`, attempt 1: bank 0, three accepted cycles, v12,
  68/68 retained and 18/18 hidden versus 0/18 for every control. Python 3.13.14 reproduced the
  exact 51,553 Python 3.11 result bytes with SHA-256
  `eaf6fee975bddaae583e0f739d0a5ad050209b303d304eddc81bb6320c642ace`.
- Added the immutable raw result, reproduction, first-result seal, independent evidence verifier
  and canonical audit. All ten bounded completion gates are true; D026 closes the M043–M066
  construction line while leaving M045's separate measurement question open.

## 0.40.0 — 2026-08-09

M064 is preserved as a failed pre-canonical qualification and M065 carries the required
scientific and governance corrections without changing the task bank, budgets, thresholds,
substrates, candidate grammar or four-arm decision rule.

- Preserved M064 commit `ec92af78b57203d32c2ee504db91b4166ec83fdf` and GitHub run
  `31281234286`, attempt 1. Integrity and attribution passed; Python 3.11 passed 1,084/1,085
  tests in 1,037.15 seconds and Python 3.13 passed 1,084/1,085 in 1,094.43 seconds. Both rejected
  the same checkout-dependent source hash. No marker or canonical result was created.
- Recorded the review finding that M064's rollback receipt compared the untouched saved input to
  itself. D023 therefore requires M065 rather than a scientific repair under M064.
- Added an M065 transaction that corrupts a distinct staged state, deserialises the committed
  pre-transaction bytes into the state actually returned, audits that object and requires exact
  byte and state-digest restoration before continuing.
- Repeated all four banks. The complete lineage remains 18/18 hidden with three accepted cycles
  and 68/68 retained cases; every control remains 0/18 with zero accepted cycles.
- Required the canonical marker to be its first occurrence anywhere in path history and gated the
  first-result job on `github.run_attempt == 1`; reruns can only consume the preserved artifact.
- Added portable LF-normalised source commitments. M064's historical 21-file audit and M065's
  22-file audit now agree across Windows and Linux checkouts.
- The complete corrected repository suite passes **1,101 tests in 1,762.37 seconds**. An earlier
  full M065 invocation passed 1,100 and exposed the last CRLF-based M064 guard fixture; that
  fixture alone was normalised before the clean rerun.

## 0.39.0 — 2026-08-08

M064 assembles the real-substrate completion experiment in one continuous
CPython → Node ESM → whole-WebAssembly lineage. It is positive in development and eligible for
freeze; no canonical verdict is added yet.

- Reconstructed M047 version six and M048 version eight, scanned all 256 arithmetic bytes and
  replayed M061's six structural shapes before compiling the entire accepted body into a
  1,834-byte, zero-import WebAssembly module with 32/32 inherited capabilities.
- Added a serialised seven-node expression constructor and dynamic whole-body compiler. Each
  accepted route recompiles parser aliases, arities, route admission and tool dispatch into one
  native module; Node remains only a passive bounded host.
- Added four equal-budget post-migration arms and three committed task families. Across all four
  preverified banks the complete lineage accepts three rewrites, reaches version twelve and
  passes 18/18 hidden observations; fresh-on-B, unchanged-parent and learned-state-ablated arms
  each accept zero rewrites and pass 0/18.
- Required class-wide D021 admission: 12, 8 and 8 public survivors are each independently
  recompiled, inspected for zero imports and executed on retained, public and hidden evidence
  before digest selection.
- Archived exact parents 9, 10 and 11, appended three causal-memory episodes, forced a corrupt
  journal binding, restored code and behaviour exactly, and replayed the final state.
- Added a marker-only canonical guard, immutable first-result runner and separate Python 3.13
  exact-reproduction job. These mechanisms remain closed until the frozen-parent commit passes
  qualification and a separate marker commit is made.
- Preserved the authorship boundary: the whole-body compiler, block structure, finite grammar,
  task families and evidence remain human-written and precommitted. M064 claims bounded
  construction and continuity, not unrestricted compiler synthesis or open-ended evolution.
- The first complete four-bank test invocation finished every scientific computation. Nineteen
  tests passed; one fixture expected two intermediate module
  sizes incorrectly. The fixture was corrected without changing engine, protocol, bank,
  threshold or result. The clean M064 rerun then passed **26/26 tests in 274.65 seconds**. The
  complete local repository suite subsequently passed **1,085 tests in 2,035.10 seconds**.

## 0.38.0 — 2026-08-08

M063 transfers M062's bounded arrangement mechanism from byte copying to byte reduction. The
development result is qualified; no canonical claim is added.

- Replayed M061/M062 effect discovery and constructed 96 checksum-loop arrangements from the
  transferred topology, predicate, exit-position and step-permutation dimensions.
- Retained six public survivors and admitted all six on three disjoint hidden cases under both
  exit-region representatives: 12/12 complete programs.
- Emitted a 91-byte `(source, count) -> checksum` WebAssembly module with an accumulator local,
  zero imports and no memory write.
- Added a cross-body negative control: M062's selected copy body passes only the zero checksum
  case and fails both non-zero cases.
- Added D022: a claimed mechanism transfer needs a target with a distinct observable contract
  and a source-body control that the target evidence can falsify.
- Kept the boundary explicit. The checksum decomposition, three atomic steps, finite grammar,
  emitter, encodings and evidence cases remain authored. A third small loop using the same
  pattern would not count as the next advance.
- Added 16 permanent M063 falsifiers. The complete M063 file passes locally in 130.94 seconds,
  the joint M062–M063 regression passes 31 tests in 310.38 seconds and the complete repository
  suite passes **1,054 tests in 1,763.31 seconds**. The required GitHub matrices are recorded
  below.
- Qualified exact head `d4eb5ed981727fd1343e6e1031494771d9dec220` on the first and only
  GitHub Actions run `31275085485`, attempt 1: 1,054 tests on Python 3.11 in 969.51 seconds,
  1,054 on Python 3.13 in 985.12 seconds, repository integrity and attribution, with no failed
  job or rerun.

## 0.37.0 — 2026-08-08

M062 begins the arrangement frontier left by M061. This is a qualified development result; no
canonical or real-substrate claim is added.

- Replayed the six M061 structural scans and added a seventh 256-opcode region-effect scan.
  A discovered branch distinguishes exit behaviour from repetition without using `block` to
  expose `loop` or the reverse.
- Preserved the scan's real ambiguity: `0x02` and `0x06` form the observed exit-region class;
  `0x03` is the sole repeat-region candidate. No familiar opcode is preferred silently.
- Constructed 480 copy-loop arrangements from a finite grammar rather than a catalogue of
  finished programs. Sixteen satisfy the three public cases.
- Required all sixteen public survivors with both exit-region representatives to pass all three
  hidden cases: 32/32 complete programs admitted. The canonical digest therefore selects source
  representation, not hidden behaviour.
- Added D021: canonicalisation inside an observational equivalence class is allowed only after
  every member survives independent validation.
- Preserved the first region-scaffold defect: it declared an empty result and could not transport
  the value its post-region addition consumed. The permanent witness test caught it before the
  complete lineage; the fixed `i32` blocktype is now part of the explicit floor.
- Kept the boundary explicit. The task decomposition, grammar, emitter, scaffold shapes,
  blocktypes, label encoding and cases remain authored. M062 is not arbitrary compiler synthesis,
  and does not close the real-substrate canonical frontier.
- Qualified exact head `f5cfe35c265cf83640fddc2ae80e54805776f84f` on the first and only
  GitHub Actions run `31269732461`, attempt 1: 1,038 tests on Python 3.11, 1,038 on
  Python 3.13 and repository integrity, with no failed job or rerun.

## 0.36.0 — 2026-08-08

Register synchronisation, again. The previous release synchronised the registers on 6 August
with M053 as the frontier. Eight experiments landed in the two days since and none of them
reached the root registers, so `PROJECT_STATE.md` still announced a frontier that had been
superseded six times. No scientific claim is changed by this release; the records under
`experiments/` were already authoritative.

- **Recorded M053 as a positive bounded development result.** Documented head `12b0c31`, run
  `31162378285`, 852 tests. Its capability gain is structural and real; its mechanism filters a
  declared sixteen-AST meta-language, which is selection at a higher level.
- **Recorded M054** as construction rather than selection — 29,330,422 admissible candidates
  under a budget of 1,024 — together with the three design defects found before it ran and
  disclosed in its protocol.
- **Recorded M055 as negative on its central claim.** The construction, adoption, forced fault
  and exact restore all work. The ablation still solves the reuse task with 737 candidates
  against 48, so the acquisition bought a fifteen-fold search saving and no new expressive
  power. This is the result behind **D019**.
- **Added Phase 6 — substrate discovery and the whole-body crossing**, covering M056 through
  M061: an acquisition survives a second crossing; the authored migration map is removed; the
  authored list of operations is removed and discovery finds `copysign`, which a person had
  omitted; the lineage judges its substrate and reverses; the whole body crosses into a
  1,792-byte WebAssembly module with zero imports; and the structural instructions are
  identified by their effect alone.
- **Recorded that none of M056–M061 discharged its own qualification rule.** Each result was
  written before CI returned and none was updated, so all six still read *PENDING
  QUALIFICATION*. The CI runs are now listed retrospectively — one run per experiment commit,
  no rerun, no selection among runs — as evidence that the suite was green and explicitly not
  as a discharge of those rules.
- **Added D020 — a manifest field is a claim, and reading it back proves nothing.** M061
  asserted `copy_loop_uses_only_discovered_instructions: True` while its builder wrote seven
  opcodes in by hand. Sixteen permanent tests passed over it because the test read the field
  back. The same shape appears in M053's `rollback_exact` and M048's `replay_identical`: the
  falsifier's input was downstream of the thing it was supposed to falsify.
- **Entered the M061 false manifest into `FAILURE_LOG.md`.** It was found by external review of
  PR #90, not by the test suite, the integrity audit or the green CI run. It reached `main` in
  merge `1c7cceb` because the correction was pushed after the merge, and is corrected by PR #91.
- **Recorded that the scan contradicted the authored code and was right.** `i32.le_s` is
  `0x4c`; the hand-written copy loop carried `0x4d`, the unsigned comparison. Nothing caught it
  because the loop counter never goes negative. M060's emitter was independently correct.
- **Replaced the frontier with two questions instead of one experiment.** The compiler that
  arranges the discovered instructions is still written by a person, and nothing built on a
  real substrate is claimable: gates 8, 9 and 10 have no working parts there. Fifteen
  consecutive development results without a claimable one is the pattern **D016** and the M052
  series closure exist to prevent.
- Rewrote `PROJECT_STATE.yaml` with `phase_five`, `phase_six` and a two-question frontier,
  replacing the `active_construction_frontier` block that still described M053 as unqualified.

## 0.35.0 — 2026-08-06

Register synchronisation. The root registers had not been updated since M047 was still the
frontier, while `main` had advanced through M048–M052. No scientific claim is changed by
this release; the experiment records under `experiments/` were already authoritative.

- **Recorded M048 as a positive integrated development result.** The accepted M047
  version-six body was compiled into nine native Node.js ESM modules and executed without
  semantic delegation back to Python. Twenty-eight inherited capabilities survived, the
  inherited `mean` tool was used after migration, a new `tool_max` module was learned in the
  new runtime as version eight, forced journal corruption was detected and version eight
  restored exactly.
- **Recorded M049–M052** as bounded development results, with their run numbers, commits and
  test counts, and recorded that the series is closed at M052.
- **Added D016 — the M049–M052 series is closed at its own success.** Every step passed and
  none of them changed what the lineage can express; the closure lists the six continuation
  patterns that can no longer justify a successor experiment.
- **Added D017 — an infrastructure failure is not a qualification verdict.** A run enters the
  append-only qualification history only if the experiment's own code executed and produced
  the failure.
- **Entered the preserved negative verdicts into `FAILURE_LOG.md`.** M048's runs 402 and 403
  and M050's run 410 were documented only under `experiments/`, so the project's central
  failure register did not contain them. For a project whose append-only negative history is
  a load-bearing claim, that was the largest gap in the registers.
- **Recorded the M053 frontier as proposed and unqualified**, and recorded its first CI
  attempt as an infrastructure event rather than a negative result, per D017.
- Added M047 to `PROJECT_STATE.yaml`, which had never carried it, and added a `phase_four`
  block for trans-runtime continuity.

## 0.34.0 — 2026-08-03

- **Corrected a selector that was named for a mechanism it did not implement.**
  `minimal_criterion_survivors` admitted on a threshold and then ranked the admitted by
  agreement, preferred the smaller body on a tie, and truncated. M037's own report
  asserted that "a minimal criterion admits or rejects; it does not rank" while the code
  ranked. Found by external review, not by the test suite or any audit.
- **Withdrew a false attribution.** The rule was justified by M021's 750 per mille.
  `rank_by_minimal_criterion` filters on viability, ranks the viable by **novelty**, ranks
  the rejected by energy and lets `Population.select` truncate; M035 implemented none of
  that. The figure was attributed to a mechanism that was never run.
- Named three selectors apart, so none borrows another's evidence:
  `thresholded_elitist_truncation` keeps M035's historical 6/12,
  `viability_then_novelty` keeps M021's 750 per mille, and the new
  `positive_population_floor_admission_with_body_diversity` inherits neither and has
  produced no experimental result at all. Every rate in M037 belongs to the historical
  selector, which the runner still uses unchanged.
- Named the admission bar for the whole of what it does. `max(1, min(score))` is a
  population floor **plus** a viability condition, and its cost is stated: the protection
  claimed for neutral duplicates applies only to viable lineages, since a neutral
  duplicate of a never-scoring parent sits below the bar with its parent and is rejected
  with it. Pinned by test, including the degenerate all-zero population.
- Separated admission from capacity reduction. Admission consults the score once, at the
  threshold. Reduction orders by `SHA-256(domain || commitment || seed || generation ||
  digest)`, which sees no score, no size, no structural cost and no input position, and
  draws from its own hash rather than the mutation generator — sharing that stream would
  couple selection to variation.
- **Fixed a second hidden dependency.** Deduplication kept whichever organism the loop met
  first per body digest, so permuting the population changed the surviving *lineage* while
  the surviving *bodies* stayed identical. A separate `representative_key`, under its own
  domain separator, now decides which lineage represents a body. The invariant test
  written alongside had compared digests only and passed while the defect was present.
- Declared the unit of reduction as the **distinct body**, chosen on mechanism before any
  measurement and named as a diversity policy rather than neutrality: ten clones present
  one candidacy. Per-individual reduction would let a heavily replicated clone crowd out
  rare structures by multiplicity alone.
- Named the admission rule for what it is. The threshold is the current population's
  minimum score, recomputed each generation and able to fall. A comment claiming it "rises
  only when the whole population clears it" was false. The near-vacuous bar is deliberate:
  a neutral duplication carries exactly its parent's score, so any rising bar would
  eventually exclude the duplicates before they could drift.
- Requalified M037's replay as **level 2, adopted-mutation replay from a supplied
  founder** — a Gate 9 prerequisite, not Gate 9. The founder is given as a DFA rather than
  rebuilt from a seed, and task reveals, observations, rejected candidates, costs and
  selection decisions are not reproduced.
- Marked cases 0–11 and 12–23 as consumed. Neither may choose a policy, tune a threshold
  or confirm a later claim; a fresh guarded block is required before the next experimental
  decision.
- Renamed the machine-readable replay fields to say what they demonstrate:
  `adopted_mutation_replayable`, `adopted_mutation_steps`, `adopted_mutations` and
  `all_winning_adopted_mutation_chains_replayable`. The code, the tests, the emitted JSON
  and the report now make the same claim, and none of them says Gate 9.
- Added a test exercising the runner's own threshold rule rather than a hand-supplied
  one. The earlier tests passed a threshold in directly and never exercised
  `max(1, min(score))` against a population containing a zero, which is exactly where the
  positive floor differs from the current minimum.
- Pinned the rejected alternative too: under an exact `min(score)` floor the null lineage
  would survive. Variant 1 is not adopted, and the trade-off stays visible in a test
  rather than only in prose.
- Added 19 metamorphic selection tests and recorded the misclassification in
  `FAILURE_LOG.md`.

## 0.33.0 — 2026-08-03

- Made the lineage replayable, as Gate 9 requires. Every organism now carries its full
  chain of mutations — the operation itself, not a pointer to its outcome — and
  `replay(founder, ancestry)` rebuilds any descendant from the founder body and the chain
  alone, with no seed, no population and no search. Verified 20/20 in development and
  **12/12 on untouched cases**, on chains up to 36 mutations deep. A truncated chain
  provably fails to rebuild the organism, so the record is load-bearing.
- Fixed the survival rule, which sorted by score and cut at capacity: elitist truncation
  wearing a minimal criterion's name, and the rule M021 measured as the most destructive
  of four at 0 per mille against 750. The symptom was unmistakable once swept — raising
  generations from 60 to 150 changed nothing on every configuration, because the
  population reached a fixed point and stopped exploring. Deduplicating by body before the
  cut restores exploration.
- Recorded an instructive intermediate error: ordering the distinct bodies by structural
  cost scored **0/12 everywhere**, because cost rises with size and a size-ordered cut
  discards exactly the organisms that have grown. Both errors share a shape — a minimal
  criterion admits or rejects, it does not rank, and each order slipped into it restored a
  pressure the mechanism cannot survive.
- **Rejected a tuning illusion.** A sweep found 9/12 on cases 0–11 against 6/12 for the
  delivered defaults. Confirmed on untouched cases 12–23 it scores 3/12, while the
  defaults score 5/12 — the swept configuration is not merely no better but worse, and the
  sweep had found the parameters that flattered the twelve cases being watched rather than
  improving the mechanism.
- Confirmed the delivered result generalises: 5/12 on cases never used to choose anything,
  against a control that stays at 0/12 by proved impossibility rather than by budget.

## 0.32.0 — 2026-08-03

- Added the `grow` atom to the structural language: duplicate the state holding a role,
  routing one incoming edge to the twin. It is the only capacity-increasing edit; every
  other preserves or reduces the state count. Additive by design — `all_atoms()` is
  unchanged, so every recorded experiment keeps its vocabulary, its reachable set and its
  digests.
- Added M036, a single organism that meets a task, proves its body too small, grows and
  retries. **Recorded as a negative**: it solves 2/8 where the M035 population solves 6/12
  on the same generator, and a control without growth solves 0 by impossibility.
- Established that the explicit Myhill–Nerode diagnosis is unnecessary and too weak to
  gate on. Once growth is in the search vocabulary the search finds when to grow by
  itself, and the greedy bound missed 3 of 6 cases that genuinely required growth, so
  gating suppressed exactly the episodes needing it. Failure is the better trigger.
- Established that growth must be composable rather than preparatory: inside the
  vocabulary 2/8, as a phase before the search 0/8. A depth-3 trajectory can be
  edit-grow-edit only if growth is a symbol.
- Established by exhaustive enumeration that growing is not sufficient: of six cases, the
  diagnosis missed three, two grew to a reachable target, and one grew to a target still
  unreachable at depth 3. A size bound says *that* a body must grow, never *where* the
  missing distinction lives.
- Corrected a measurement error of this session's own making. M036 was first reported at
  0/8 as a structural failure; the smoke test used a 60,000-node budget while depth-3
  enumeration over 44 symbols needs up to 85,184. At the protocol's 200,000 the same code
  solves 2/8. The conclusion stands, the first number did not.

## 0.31.0 — 2026-08-03

- Measured the structural ceiling of the existing organism: across 53,280 atom
  applications, 18,540 changed the state count and **none increased it**. Every change was
  a decrease. Capacity is fixed at birth and can only be lost, so no descendant can be
  structurally novel and "self-improvement" is search inside a budget the organism did not
  choose and cannot change.
- Added `metamorphosis/m035_evolution.py` with a capacity-increasing operator:
  duplication of a state into a behaviourally identical twin. Neutral at birth — 12/12
  preserve behaviour exactly, so selection cannot see it — and 12/12 increase the state
  count. This is NEAT's *add node* mutation, itself transposed from gene duplication; the
  contribution here is not the mechanism but a domain where "unreachable" is proved.
- Ran the decisive comparison against `make_out_of_language_target`, which M017 uses as a
  *negative* control precisely because it adds a state. Twelve cases, all requiring growth:
  the atoms-only arm solved **0/12**, by structural impossibility rather than bad luck, and
  the duplication arm solved **6/12**, using growth in 12/12.
- Added `required_states_lower_bound`, a Myhill–Nerode diagnosis by which an organism
  proves it needs more states **without seeing the target**, from oracle answers alone.
  Sound in 0/24 violations, never demanding growth against its own behaviour, firing on
  8/12 targets that require it. This is Gate 1, autonomous diagnosis of a limitation, in a
  decidable form.
- Recorded two failed refinements rather than tuning them away. Size-based speciation
  scored 1/12 and diagnosed growth 2/12, both against 6/12 for a random trigger, and both
  solved faster when they solved — more directed, less exploratory. Their mechanisms are
  identified in the result, and neither correction is applied: re-measuring a corrected
  rule on the same seeds is the post-hoc adjustment §7 of the M017 protocol and D010 forbid.
- Selected survivors by minimal criterion, chosen from this repository's own measurement:
  M021 scored it 750 per mille against 416 for novelty, 312 for quality-diversity and 0 for
  the direct objective. At equal agreement the smaller organism survives, so growth is
  never free.

## 0.30.0 — 2026-08-03

- Recorded the human signature on the §2 thresholds of M017 and translated the candidate
  protocol to English before hashing, because D012 governs the active surface and a
  document frozen forever must be frozen in the repository's language. The French
  candidate is retained unchanged as the pre-signature record.
- Added `metamorphosis/m017_sealed.py`, the sealed specification required by §10. Its
  nonce is derived from the immutable head SHA rather than drawn at random, per §8.3,
  which is stricter than M012b, M013e and M014b: the environments cannot be computed
  before the commit they judge, and they reproduce from that commit alone.
- **Blocked the freeze.** Writing that generator put the admission conditions under a seed
  set the development bench had never used, and the out-of-language negative control
  produced a false success: a 7-state target, a 6-state source, a 6-state announced
  solution that is not equivalent, separated by `(0, 0, 1, 0, 0, 0)`.
- Established the cause as a scope assumption rather than a coding error. `_confirm`
  states its own bound — the structural language does not create states, so a target
  cannot have more than the source — and the negative control is defined by adding one.
  §3.2 therefore asks the organism to reject targets its own confirmation cannot see.
- Measured the repair: raising the bound to `source + 1` grows the suite from 34 to 69
  words and restores detection. Because it also changes query cost, which §2 measures, the
  bound is a protocol parameter to be signed rather than adjusted after observation.
- Established that the development pass was a favourable draw. Gate 5 was declared passed
  on two negative controls; an independent sweep of 24 yields 2 false successes, an escape
  rate near 8 per cent, so two clean controls occur about 85 per cent of the time.
- Re-opened gate 5 and recorded the finding in `FAILURE_LOG.md` and §11 of the protocol.
  This is the third instance in M017 of a small favourable sample taken for a guarantee,
  after the 96-word probabilistic confirmation and the unminimised W-method hypothesis.

## 0.29.0 — 2026-08-03

- Repaired the D014 negative-constant defect in the rewrite kernel. The fix is in the
  reader rather than the writer: `_negative_int_literal` makes both `_TargetCollector` and
  `_IndexedNodeTransformer` treat a `-<int>` expression as one constant target, so a patch
  replaces the whole negation instead of the literal nested inside it.
- Constant patches are now idempotent for every sign, the AST no longer grows under
  repeated negative patches, and the effective behaviour no longer alternates.
- Measured the consequence honestly: the repair moves all four recorded M033 digests,
  because `ConstantRewriteTool.propose` filters on `value != current` and previously read a
  negative constant as positive. Every search in the construction stack was carrying
  phantom candidates; removing them lowers candidate medians by 3 to 7 per cent.
- **No finding changed.** Every paired outcome reproduces identically across the two kernel
  generations, along with exactness, held-out exactness, output-only immobility and the
  parent/ablation separation.
- Recorded D015: artifacts are scoped by the kernel generation that produced them rather
  than re-run, as M012 is scoped against M012b. A cost figure may only be compared against
  another from the same generation.
- Retired `tests/test_m020_negative_constant_defect.py`, which pinned the defective
  behaviour so a fix could not land unnoticed, and replaced it with
  `tests/test_m020_negative_constant_round_trip.py`, which guards the repair.
- Added `MacroCost`, an opt-in edit-budget rule. `PER_OPERATION` is the default and charges
  a learned tool what its constituent primitives cost; `UNIT` charges it as a single edit.
  `_rank_key` now ranks on budget rather than trace length, which is identical under the
  default and lets a one-step macro outrank the longer primitive path it replaces.
- Added `metamorphosis/m034_reachability.py`, an exact capability measure. Deterministic
  cost conflates how close a lineage started with how much it can do; the reachable
  behaviour set separates them, and is enumerable here rather than estimated.
- Established two results, both pinned: under `PER_OPERATION` a learned tool adds **nothing**
  to the reachable set at any budget, being a composition of primitives charged what they
  cost; under `UNIT` it enlarges the set — 2/16 to 4/16 at budget 1, 7/16 to 10/16 at
  budget 3 — with the old set a proper subset of the new.
- Gave M017 a decidable success criterion it lacked: does a self-extending language
  increase reachability at constant budget?

## 0.28.0 — 2026-08-03

- Added rewrite provenance: `RewriteCandidate.proposing_tools` and
  `RewriteResult.reused_learned_tools` record which tool proposed each adopted step, so
  Gate 9's reuse clause can be proved rather than guessed. Provenance is excluded from the
  ranking key, and all four recorded M033 digests reproduce exactly.
- Established that a learned tool costs the same edit budget as its constituent
  primitives: it saves search depth, not budget, since its operations count individually
  against `max_edits`.
- **Found a latent correctness defect in the M020 rewrite kernel.** `apply_patch` does not
  round-trip negative integer constants: `ast.unparse` writes `-2`, re-parsing yields
  `UnaryOp(USub, Constant(2))`, and each further patch at that index stacks another
  negation. Constant patches are non-idempotent for negative values, the AST grows without
  bound, and the search can reach bodies whose outputs leave the declared state range.
- Audited the blast radius: nothing recorded is contaminated. 776 of 776 adopted sources
  across the four M033 calibration blocks contain no negative constant.
- Recorded the defect as D014 and in `FAILURE_LOG.md`, and pinned it with
  `tests/test_m020_negative_constant_defect.py`. It is deliberately **not** repaired here,
  because correcting it changes the reachable candidate set and may move recorded digests.
- **Withdrew the Gate 9 demonstration.** An exhaustive finite check found 4 candidate
  reuse lineages out of 195 cycle-1/cycle-2 pairs; all four depended on the defect. Gate 9
  remains undemonstrated and must be re-measured on a corrected kernel.

## 0.27.0 — 2026-08-03

- Measured D013's predicted repair path instead of leaving it as an argument: a
  three-cycle lineage over three distinct finite targets accumulates three learned tools,
  one of which can still act on the final body.
- Established the exact mechanism: the newest tool is always inert, because it is by
  construction the trace that produced the current body, and an earlier tool becomes able
  to act again only once a later cycle moves the body away from what it wrote.
- Recorded that Gate 9 is a **precondition** for Gate 8's learned-tool comparison, which
  is a sequencing constraint on the roadmap rather than a threshold choice, and that
  M033's thresholds may not be frozen before repeated cycles exist.
- Added `tests/test_m020_multicycle_tool_reactivation.py`, five tests pinning the tool
  accumulation, the inert newest tool, the reactivation of an earlier tool, and the
  single-cycle contrast.

## 0.26.0 — 2026-08-03

- Established that a learned rewrite tool is a literal replay, not a generalising
  transformation: `PatchOperation` binds each edit to a positional AST index and
  `LearnedRewriteTool` returns its operations verbatim, so a tool cannot fire at an
  equivalent site with a different index.
- Established the consequence for Gate 8: the tool a single-cycle lineage carries is the
  trace that produced its body, so applying it there is a no-op and the learned-tool
  ablation compares two lineages whose only difference cannot act.
- Reclassified that control from failed to **structurally uninformative**, since a tie
  there is evidence about the rewrite language rather than about transported plasticity.
- Withdrew the requirement, added in 0.25.0, that the primary generator demand a component
  the migrated body does not encode. It was unsatisfiable: the precondition is a relation
  between registry and body, not between lineage and task.
- Recorded that Gate 8's tool control must be evaluated on a multi-cycle or rolled-back
  lineage, so Gates 8 and 9 are not independent.
- Added `tests/test_m020_learned_tool_replay_limit.py`, five tests pinning the index
  binding, the no-op property and the absence of site transfer.
- Recorded the finding as D013 and connected it to D009: the tool language is closed in
  the same way the retired catalogue was.
- Noted that the memory mechanism is unaffected, because it is decoded and re-applied
  against current evidence and can therefore act on a body it did not produce.

## 0.25.0 — 2026-08-03

- Found and repaired a control-design defect that removed one of Gate 8's four required
  controls: every earlier M033 block anchored all lineages on the task's own baseline
  source, so the migrated body was never read and the unchanged parent and the
  learned-tool ablation presented byte-identical surfaces.
- Added `TaskAnchor`, leaving `TASK_BASELINE` as the default so the fixed, structural and
  combined blocks stay byte-reproducible and are not retroactively re-scored; verified by
  re-running all three after the change and reproducing every recorded digest exactly.
- Added the body-anchored control block on the disjoint seed range 4096–4127, where the
  two collapsed controls separate on 32 of 32 seeds.
- Established that transported competence does real work: the complete lineage beats
  fresh-B 32/0/0 and its own unchanged parent 32/0/0, at a median of 26 candidates
  against 1,427.5 and 264.5.
- Established that the learned tool contributes nothing independent in this rig, tying the
  complete lineage 0/32/0 at an identical median of 26, because it encodes the same
  transformation the adopted rewrite already baked into the body.
- Recorded Gate 8 as unmet with a per-control verdict, and recorded that the remedy is a
  generator change rather than a threshold change.
- Verified the isolation and integrity audits and a byte-identical replay with raw digest
  `394f9904b675ac2a8c9d143b8265022b32285efb0d56a01799f45e43b17571a8`.
- Left the reserved primary block 0–63 uninstantiated and unobserved.

## 0.24.0 — 2026-08-03

- Added M033's combined memory-and-tool control block on the disjoint seed range
  3072–3103, running the four structural scaffolds through the memory-guided execution
  path so both transported mechanisms are measured together for the first time.
- Recorded a mixed and largely negative result: all five learning-capable variants were
  exactly equivalent on all 32 tasks, and the complete lineage beat fresh-B 24/0/8 but
  went 8/16/8 against its unchanged parent, 8/16/8 against the learned-tool ablation and
  16/0/16 against the learning-state ablation.
- Established that the two mechanisms act on disjoint scaffolds: memory carries scaffolds
  0 and 1 at a median of 264 candidates, learned tools carry scaffold 3 by cutting search
  from 1,879 to 568, and neither helps on scaffold 2.
- Established that the advantage is not attributable to the adopted rewrite, because the
  unchanged parent retains the same learning state and matches or beats the complete
  lineage on three of four scaffolds.
- Charged the memory probe honestly: one candidate evaluation whether accepted or
  rejected, which alone decides the scaffold-3 loss against the learning-state ablation
  at 569 against 568.
- Verified 236 repository tests, the isolation and integrity audits and a byte-identical
  replay with raw digest
  `0ef00f0f4168a95235f33050751b7871366ad1e2d2c08ed07bfb90b908423372`.
- Left the reserved primary block 0–63 uninstantiated and added two questions the
  threshold-freeze amendment must now answer: the status of the unchanged-parent
  comparison, and whether a one-candidate margin is a win or an abstention.

## 0.23.0 — 2026-08-03

- Added M033's post-migration plasticity rig: six lineage constructors covering the
  complete migrated M032 lineage, fresh-B, unchanged parent, output-only and the
  learning-state and learned-tool ablations.
- Added two disjoint development control blocks — fixed-structure seeds 1024–1031 and
  four-scaffold structural seeds 2048–2063 — with a static audit proving no pre-M033
  module reaches the M033 task, target or held-out surfaces.
- Isolated the learned-tool mechanism causally: median post-reveal candidates were 959
  for the complete lineage against 976 for fresh-B, the unchanged parent and the
  learned-tool ablation, cheaper on 8/8 seeds, with 0/8 on the disjoint negative family.
- Isolated the memory mechanism causally: a relevant transported trace reached a median
  of 264 candidates against 959 for empty memory and 960 for a permuted trace, cheaper on
  8/8 seeds, while all three stayed exactly equivalent.
- Recorded a deliberately mixed structural result — 12/16 complete-lineage wins with
  per-scaffold directions of 4/4, 4/4, 0/4 and 4/4 — and kept scaffold 2 as a declared
  counterexample to any rule demanding universal directional improvement.
- Reported every lifecycle cost as a separate vector rather than one synthetic score, and
  verified output-only immobility, fail-closed post-migration regression and exact
  rollback.
- Passed 27 focused tests, the repository integrity and task-isolation audits and
  byte-identical replays of both calibration families in run `30792247244`.
- Kept the reserved primary block 0–63 uninstantiated and unobserved; no post-migration
  plasticity advantage is claimed and no threshold is frozen.

## 0.22.0 — 2026-08-03

- Added M032's fail-closed bridge from M025's adopted executable rewrite to M013e's
  experimentally discovered opaque substrate and native DFA body.
- Added a canonical trans-substrate packet carrying the M025 passport, source DFA,
  opaque body, discovered opcode identifiers, memory, uncertainty and exploration
  frontier.
- Added exact rollback after finite-compilation or substrate-migration failure and
  integrity rejection for tampered passports, DFAs, opaque bodies and opcode registries.
- Verified five focused M032 controls, repository integrity and 211 repository tests on
  both Python 3.11 and Python 3.13.
- Preserved the boundary between this bounded integration result and the still-open
  post-migration learning, autonomous diagnosis and repeated-cycle claims.

## 0.21.0 — 2026-08-02

- Added M031's split-scaffold generator with length-three generic motifs and eight
  cyclic/permuted triad tasks.
- Transported the frozen component-uniform information rule: 737 per mille
  clade/exact-CMP concordance, +1,070 over development adaptive, and +500 per mille
  median paired final hidden quality with 43 wins, 18 ties and 3 losses.
- Passed every structural, probe, coverage, uniqueness, selector-isolation and aligned
  control on exactly 64 paired primary seeds.
- Recorded 256 trajectories, 65,792 expansions, 198,144 unique evaluations and a
  byte-identical 48,018,205-byte replay.

## 0.20.0 — 2026-08-02

- Added M030's pre-written confirmation of M029's component-uniform diagnostic on the
  untouched seed block 64–127.
- Confirmed every gate: component-uniform guidance reached 662 per mille
  clade/exact-CMP concordance, +1,186 over development adaptive, and +1,000 per mille
  median paired final hidden quality with 48 wins, 16 ties and no losses.
- Preserved the untouched boundary by using only seeds 128+ for unit and smoke
  validation before the frozen confirmation commit.
- Recorded 256 trajectories, 30,720 expansions, 92,928 unique evaluations and a
  byte-identical replay.

## 0.19.0 — 2026-08-02

- Added M029's hidden-disjoint compositional transfer probes and a frozen rerun of the
  M028 performance-adaptive baseline.
- Preserved the 64-seed mixed development result: component-adaptive clade/exact-CMP
  concordance reached 699 per mille, but its paired final advantage remained zero with
  31 wins, 32 ties and 1 loss, below the pre-written policy gates.
- Recorded the pre-declared component-uniform diagnostic: 50 wins, 14 ties and no
  losses against development-adaptive guidance, without promoting it to a registered
  claim on already observed seeds.
- Recorded 384 trajectories, 46,080 expansions, 139,392 unique evaluations and a
  byte-identical replay.

## 0.18.0 — 2026-08-02

- Added M028's finite adaptive evaluation-weighting comparison over the common M027
  breadth-seeded archive.
- Preserved the 64-seed negative development result: adaptive allocation improved
  clade/exact-CMP concordance by only 40 per mille, produced no median hidden-quality
  advantage and returned 2 wins, 60 ties and 2 losses against uniform allocation.
- Recorded 256 trajectories, 30,720 expansions, 92,928 unique evaluations and a
  byte-identical replay without exposing hidden fields to either selector.
- Localised the next measurement failure: performance-adaptive weighting can sharpen a
  misaligned proxy while allocating less evidence to high-potential lineages.

## 0.17.1 — 2026-08-02

- Hardened human-only attribution with exact registered identities and a trusted-base
  pull-request check that never executes proposed code.

## 0.17.0 — 2026-08-02

- Added M027's hidden-blind exhaustive coverage through the first reward-bearing depth.
- Preserved the 64-seed negative development result: exposing productive descendants
  did not align the unweighted clade estimator or improve final hidden quality.
- Added permanent human-attribution rules and pull-request checks for commit authors,
  committers, co-authors, branch names, titles and descriptions.
- Removed historical automated inline-review comments and neutralized the submitted
  review summaries that GitHub does not permit the repository owner to delete.

## 0.16.0 — 2026-08-02

- Added M026, the first direct literature-facing benchmark, with explicit mappings to
  DGM, HGM and SGM and equally explicit non-reproduction boundaries.
- Added an exact finite performance/potential reversal, an exhaustive aligned control,
  selector isolation, fixed-point stochastic policies and four-worker replay.
- Preserved the 64-seed negative development result: HGM-inspired clade aggregation
  did not beat DGM-inspired immediate guidance under the fixed expansion process.
- Recorded the frozen implementation and protocol identities, the reproducible
  512-run artifact hash and a byte-identical full replay.

## 0.15.0 — 2026-08-02

- Ran M021 across 24 paired seeds and preserved the development result: implemented
  selection measures produced different exact hidden transferred quality.
- Added M022's pre-written seed-0 positive and negative adaptation controls with full
  row-level evidence; cross-seed stability remains open.
- Hardened M023 so independent adoption fails closed when the parent workspace fails.
- Added M024's integrity-checked rewrite passport for the active body, rollback lineage
  and complete learned-tool registry.
- Added M025's transactional portable rewrite lifecycle. Rejection or exceptions now
  restore both the body and registry exactly; accepted state migrates, replays its
  learned transformation and survives forced rollback.
- Reconciled the public project narrative, state and roadmap in English and recovered
  the useful evidence that had existed only on stale local branches.

## 0.14.0 — 2026-08-01

- Reoriented the project onto what its own failures identified: **when does a proxy
  measure stop tracking what it claims to track?** (D011, H9)
- Added `MEASURES.md`, a first-class register beside `FAILURE_LOG.md`, cataloguing six
  measures that came loose from what they claimed to measure — with ground truth.
- Made that catalogue executable: `scripts/reproduce_measure_failures.py` replays every
  case on demand.
- Replaced the probabilistic confirmation with an exact conformance test
  (`metamorphosis/conformance.py`). M017's "zero false successes" had been a favourable
  draw, not a guarantee.
- M017: all six freeze gates passed. The 50-environment sweep invalidated the proposed
  10× threshold and the criterion became directional.
- M018: hypothesis not supported — destroying does not restore improvement.
- M019: rig not valid — selection too impatient to value learning.
- M021 opened: do these selection measures move true quality?
- Parallelised the measurement scripts, verified bit-identical against the sequential
  outputs.
- Repository made public and translated to English (D012).

## 0.13.0 — 2026-07-31

- Consolidated the repository around living code only: retired the orphan M012/M013b
  stack, about 2,400 lines forming a disconnected import subgraph (D007).
- Added the first permanent CI and `scripts/check_repository_integrity.py` (D008).
- Fixed `pytest -q` and `pip install -e ".[dev]"`, both of which had never worked.
- M014c halted before evaluation and replaced by M017 — self-extending language (D009).
- D010: a measured quantity must have an established dynamic range.

## 0.12.0 — 2026-07-31

- Created the canonical repository.
- Consolidated Metamorphosis M001–M011.
- Added protocols, reports, aggregated results, tests and scripts.
- Created the state, hypothesis, decision and failure registers.
- Opened phase M012: autonomous morphogenesis.

## M105 — negative checker-instrument result (2026-08-25)

The unique canonical attempt executed once from frozen protocol `43d270df…` and its first bytes
(`0ae9c096…`) were preserved and tagged before any checking. The single frozen checker replay then
exited 1 with `ModuleNotFoundError: No module named 'scripts'` and left P1-P16 uncomputed, so the
frozen all-true rule makes attempt 1 negative. D074 forbids retry or repair; H50 is unsupported but
not refuted. This repeats D072's M103 defect, which M104 had closed for its own checker.

## M106 — positive qualified replication (2026-08-25)

The unique canonical attempt ran once from frozen protocol `e92e1b08…`; its first bytes `7c22c889…`
were preserved and pushed before any checking, and the single checker replay computed P1-P16 all
true (`76299018…`) with replay equality and zero external calls. The mechanism module
`metamorphosis/m105_runtime.py` was imported unchanged and the target semantic was fixed before
implementation, so H51 replicates the question M105 could never evaluate. D075; M105 stays negative.

## M107 - positive qualified interpreter extension (2026-08-25)

The first Genesis result in which an acquisition changes what the lower interpreter can express.
From frozen protocol `928c4990...` the unique attempt produced `a11d6b3b...`, preserved before
checking; the single checker replay computed P1-P16 all true (`0c5f9378...`). `complete_image` goes
4 -> 16 by one acquired unary operator held as lineage state, with the exclusion proved by a
monotonicity lemma rather than a search bound. D076. Recursive depth remains zero.

## M108 - positive qualified machinery modification (2026-08-25)

The first Genesis result in which an acquisition changes the machinery that performs later
acquisitions. From frozen protocol `0160def2...` the unique attempt produced `9bb97e2d...`,
preserved before checking; the single checker replay computed P1-P16 all true (`9c5627fb...`). The
attribution rule is held as lineage state and expressed in the lineage's own language; the monotone
rule space contains zero consistent rules, so M107's acquisition is a proved precondition. D077.
Recursive depth of two remains unmeasured, and the episode blame labels are authored supervision.

## M109 - positive qualified two-generation machinery chain (2026-08-25)

The first Genesis result in which a modified acquisition machinery produces the next modification,
and in which the lineage determines its own blame labels by controlled trial rather than reading host
annotations. From frozen protocol `8e76b30f...` the unique attempt produced `262e0bd5...`, preserved
before checking; the single checker replay computed P1-P18 all true (`ff167573...`). ReachImprove is
6 subset 20 subset 243, strict at both inclusions. The dependency between generations is the
monotonicity lemma applied to the attribution cascade, not a failed search. D078. Recursive depth of
three and acceleration remain unmeasured, and conservative adoption is declared load-bearing for the
positive half.
