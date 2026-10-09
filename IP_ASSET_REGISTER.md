# Mira Genesis — IP asset register

**Current audit snapshot: 12 August 2026; publication ledger recorded through 6 September 2026**

This register supports provenance, licensing, publication decisions and future due diligence. It is
not a legal opinion and does not create ownership where applicable law or a third-party licence says
otherwise.

## Control and provenance snapshot

- Project: **Mira Genesis**
- Repository: `mjodheim/mira-genesis`
- Project author / research director: **Anthony Mets** (`mjodheim`)
- Human-development declaration at this snapshot: **Anthony Mets is the sole human developer and
  research director of Mira Genesis**.
- GitHub contributor enumeration observed at this audit: the `mjodheim` human account plus repository
  automation; no second human contributor account was observed.
- Copyright notice used by the repository: `Copyright (C) 2026 Anthony Mets.`
- Public repository visibility at this audit: **public**.
- AI development assistance is recorded in
  [`docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`](docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md): OpenAI
  Codex, Anthropic Claude, OpenAI ChatGPT where historically used, and repository automation.
- Externally authored copyrightable material is not currently accepted for merge unless an
  appropriate contributor-rights arrangement has first been approved. DCO sign-off is provenance,
  not copyright assignment.
- The initial third-party/tooling inventory is recorded in
  [`docs/THIRD_PARTY_DEPENDENCIES.md`](docs/THIRD_PARTY_DEPENDENCIES.md).

The sole-human declaration and current Git history materially simplify diligence relative to a
repository with multiple uncontracted human copyright holders. They remain evidence, not a substitute
for claim-specific legal analysis of authorship, inventorship, copyrightability, third-party
provenance or contractual encumbrances.

## Licensing model

The project's intended operating model is now:

**public `AGPL-3.0-only` software + separately negotiated alternative commercial licensing for rights
controlled by the project owner.**

The public AGPL grant permits commercial use subject to its terms. It is not a non-commercial
licence. The commercial offering exists for customers that need negotiated rights beyond the public
AGPL grant, for example proprietary/closed-source integration or redistribution where the signed
agreement permits it.

See:

- [`LICENSE_POLICY.md`](LICENSE_POLICY.md);
- [`COMMERCIAL_LICENSING.md`](COMMERCIAL_LICENSING.md);
- [`docs/DUAL_LICENSING_STRATEGY.md`](docs/DUAL_LICENSING_STRATEGY.md).

## Asset classes

| Asset class | Current status | Current / intended treatment | Due-diligence note |
|---|---|---|---|
| Public project-controlled software | Public | `AGPL-3.0-only`; alternative commercial permissions may be sold separately where rights permit | Public AGPL rights remain available after any commercial deal or acquisition. |
| Public research prose, protocols and records | Public | `CC-BY-4.0` where `LICENSE_POLICY.md` applies | Preserve attribution/provenance. |
| M085 external-bank preparation | Public; readiness infrastructure | Existing repository licensing; no qualifying G4 result merely from preparation | Independent external-maintainer boundary remains genuine. |
| M086+ research mechanisms | **Public after pre-publication review by default** | Expected disposition: `PUBLIC_AGPL_COMMERCIAL_OPTION` unless a specific confidentiality reason is recorded | New/commercially valuable does not itself imply private. |
| Patent-sensitive candidate | Prospective | `PATENT_FIRST` temporarily before disclosure | Public disclosure can affect novelty; obtain qualified advice before filing decision. |
| Intentional trade secret | Prospective | `TRADE_SECRET_PRIVATE` | Requires actual confidentiality/access controls; cannot be reconstructed as secret after disclosure. |
| Product-specific implementation and operations | Prospective | Public or `COMMERCIAL_PRIVATE` by explicit decision | Product layer can remain proprietary even while research core stays public. |
| `Mira Genesis` name and visual identity | Publicly used; registration not asserted | Controlled by `TRADEMARKS.md`; registration decision pending | Search/file before claiming registration. |
| External task banks / maintainer payloads | Third-party / future | Rights/confidentiality defined by owner/protocol | Never treat external material as project-owned without basis. |
| Third-party software/tooling | Mixed | Governed by upstream terms/licences | Commercial licence cannot grant rights the project does not control. |

## Publication/disclosure ledger

Add or update one row **before the first enabling public disclosure** of each materially new core
mechanism. When that rule was missed historically, the later row must say so explicitly rather than
pretending the decision predated disclosure.

| ID | Mechanism / asset | Publication posture | Human provenance | Third-party review | Disposition | Decision date | Evidence / notes |
|---|---|---|---|---|---|---|---|
| P-001 | M086 / evolvable improvement mechanism | **Protocol publicly disclosed on `research/m086-evolvable-improvement-mechanism`**; implementation not yet recorded as publicly disclosed at this snapshot | Sole-human/AI-assisted framework established; mechanism-specific provenance remains required as implementation lands | Initial repository inventory complete; milestone-specific scan pending | **`PUBLIC_AGPL_COMMERCIAL_OPTION` for the disclosed protocol/research design** | 2026-08-12 | `experiments/M086/PROTOCOL.md`, `PROTOCOL.json` and `docs/HYPERAGENTS_COMPARISON.md` were pushed publicly before this ledger update. Do not claim those disclosed design details remain secret. Any materially new implementation-specific invention not already disclosed may receive a separate pre-disclosure review before first public push. |

| P-002 | `mira-blind-bank-v1` / blind externally materialized sealed task-bank contract (M075-B) | **Publicly disclosed on `research/m075b-blind-bank-generation`**: contract, schemas, isolation boundary, sealing chain, reveal gate, checkers and tests | Sole-human/AI-assisted framework established; see `docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md` | Initial repository inventory complete | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-12 | Method and instrument only. It holds **no** task content: no bank exists, no generator is chosen and no reveal is authorized. Any future sealed payload is confidential by construction and may never enter this repository, a pull request or a public workflow artifact — `scripts/check_blind_bank_leakage.py` enforces that as a decisive CI step. Publishing the contract does not disclose any bank materialized under it later. |
| P-003 | M087 / evolvable evidence-acquisition and candidate-selection mechanism | **Publicly disclosed on `research/m087-evolvable-evidence-acquisition`**: protocol, selection-policy DSL and interpreter, meta-primitive language, evidence boundary, three problem families, checker, tests and preserved result | Sole-human/AI-assisted framework established; see `docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`. Track A: no external model participates in the scientific run, and the result records 0 model calls | Initial repository inventory complete; milestone-specific scan complete for this mechanism | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-13 | Successor to M086 under the same public research disposition recorded for P-001. The mechanism is a bounded meta-transformation language over a serialized selection policy; the meta-primitives, instruction set, experiment space and problem families are authored and disclosed. No confidential third-party material, no security-sensitive material, and no sealed task-bank content is involved. |
| P-004 | M088 / endogenous experiment-space construction mechanism | **Publicly disclosed on `research/m088-endogenous-experiment-space`**: protocol, experiment constructor and its meta-language, three interactive worlds, checker, tests and preserved result | Sole-human/AI-assisted framework established; Track A for the scientific run, with 0 recorded model calls | Initial repository inventory complete; milestone-specific scan complete for this mechanism | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-13 | Successor to M087 under the same public research disposition recorded for P-001 and P-003. The mechanism is a bounded meta-transformation language over a serialized experiment constructor; the interaction vocabulary, constructor rule set, meta-primitives and worlds are authored and disclosed, and no new primitive was invented. No confidential third-party material, no security-sensitive material, and no sealed task-bank content is involved. |
| P-005 | M089 / endogenous meta-language extension mechanism | **Publicly disclosed on `research/m089-endogenous-meta-language-extension`**: protocol, L0 language and its invariant, extension substrate, primitive contract and validator, checker, tests and preserved NEGATIVE result | Sole-human/AI-assisted framework established; Track A for the scientific run, with 0 recorded model calls | Initial repository inventory complete; milestone-specific scan complete for this mechanism | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-13 | Successor to M088 under the same public research disposition recorded for P-001, P-003 and P-004. The mechanism is a bounded stack substrate from which a working-language primitive is assembled and registered; the substrate, the micro-operations, the L0 language and the validator are authored and disclosed. No new authority is granted to any acquired primitive. No confidential third-party material, security-sensitive material or sealed task-bank content is involved. |
| P-006 | M090 / executable meta-language state | **Publicly disclosed on `research/m090-executable-meta-language-state`**: protocol, state-owned language representation, fixed generic interpreter substrate, migration and conservation proof, checker, tests and preserved result | Sole-human/AI-assisted framework established; Track A for the scientific run, with 0 recorded model calls | Initial repository inventory complete; milestone-specific scan complete for this mechanism | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-13 | Architectural precondition succeeding M089, under the same public research disposition recorded for P-001, P-003, P-004 and P-005. The interpreter substrate, its micro-operations, parameter kinds and capability list remain authored and disclosed; state ownership grants no new system authority. No confidential third-party material, security-sensitive material or sealed task-bank content is involved. |

| P-007 | M091 / endogenous extension of a state-owned executable meta-language | **Publicly disclosed on `research/m091-endogenous-meta-language-extension`**: protocol, the inherited language's expressive invariant and its machine-checked closure lemma, the refutation-certificate method, the bounded assembly substrate, the independent validator and its non-macro certificate, the world schema, the checker, tests and preserved result | Sole-human/AI-assisted framework established; Track A for the scientific run, with 0 recorded model calls | Initial repository inventory complete; milestone-specific scan complete for this mechanism | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-13 | Successor to M090 under the same public research disposition recorded for P-001 and P-003 through P-006, and reviewed before the first enabling commit rather than after it. The materially new parts are the expressive-limitation diagnosis — an abstract domain over the inherited language plus a finite certificate refuting an entire infinite function class — and the non-macro certificate that separates an expressive gain from M055's search-cost gain. The interpreter substrate, the assembly substrate, the micro-operations, the signature space, the capability list and the world schema all remain authored and disclosed. An acquired primitive gains expressive power inside the language and **no** authority against the system: the permitted capability set is unchanged and network, filesystem, subprocess, credential, repository, evaluator, gate and production authority remain forbidden and unreachable. No confidential third-party material, security-sensitive material or sealed task-bank content is involved. |

| P-008 | M092 / state-owned and endogenously extensible assembly substrate | **Prepared on the local `research/m092-endogenous-substrate-extension` branch and not yet pushed at this review**: design audit, eventual-polynomial impossibility theorem and certificate machinery, target-neutral K1 lower kernel, serialized M092-A substrate migration, conservation/authority evidence and checkpoint apparatus | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; Anthropic Claude implemented the initial M092-A work and OpenAI Codex performed the resumed pre-checkpoint audit and hardening. Track A is required for any later scientific run, with zero model and network calls during qualification | Repository dependency inventory re-checked for the milestone: Python standard library plus the repository's existing pytest development dependency; no new third-party package, model, data, benchmark or confidential payload is introduced. No sealed task-bank material, credential or security-sensitive authority is present | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-14 | Successor to M091 under the same public research disposition. The materially new public mechanism moves the authored assembly substrate into serialized executable state above an explicitly authored lower kernel, while M092-A conserves the complete registered M091 semantics and introduces no acquired operation. The K1 instruction set, resource rule, state schema, invariant proof and future certificate/checker method are project-authored and disclosed; they remain the next ceiling and must not be described as self-hosting or substrate independence. A resumed review before the first remote push found and corrected an inputs-only fuel rule and under-validated serialized contracts. The M092-A checkpoint must be committed before M092-B extension search or qualification; H38 and D062 remain unclaimed at this entry. No patent-first, trade-secret, contractual, confidential-third-party or security-sensitive reason for temporary private treatment was identified. |

| P-009 | M095 / structural-composition qualification | **Authorised for first public disclosure with this register update**: frozen protocol, precommitted pool and arms, reach analysis, checker, tests, preserved NEGATIVE result and causal diagnosis | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; Anthropic Claude and OpenAI Codex assistance is recorded in the repository provenance. Track A qualification records zero model and network calls | Milestone dependency, leakage and repository-integrity reviews complete; no new runtime dependency, third-party dataset, model, benchmark, confidential payload, credential, sealed task-bank content or security-sensitive authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Qualification of the public M094 mechanism. The negative result is preserved unchanged: none of six positive worlds demonstrated the target, while all three negative controls remained negative. The owner's confirmation authorises the complete M095-M099 branch update before its first public push. |
| P-010 | M096 / contract-safe structural composition qualification | **Authorised for first public disclosure with this register update**: frozen protocol, exact closed-output-contract mechanism, qualification worlds, checker, tests and preserved POSITIVE result | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; Anthropic Claude and OpenAI Codex assistance is recorded in the repository provenance. Track A qualification records zero model and network calls | Milestone dependency and repository-integrity review complete; no new runtime dependency, third-party dataset, model, benchmark, confidential payload, credential, sealed task-bank content or security-sensitive authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Distinct successor to the preserved negative M095 attempt. It tests the exposed contract-closure cause without repairing, rerunning or relabelling M095. The owner explicitly confirmed this disposition in the local Codex task before the first public push. |
| P-011 | M097 / endogenous acquisition of a state-owned expression operation | **Authorised for first public disclosure with this register update**: frozen protocol, inherited-language impossibility certificate, bounded stack-program assembly, independent validator, persisted language state, checker, tests and preserved POSITIVE result | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; OpenAI Codex assistance is recorded in the repository provenance. Track A acquisition and qualification record zero model and network calls | Milestone dependency and repository-integrity review complete; the mechanism uses the Python standard library and existing development test tooling. No third-party data/model, confidential payload, credential, sealed task-bank content or new system authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Successor to M096. The bounded substrate assembles and registers subtraction inside the serialized operation language; it does not grant filesystem, network, credential, repository, evaluator, deployment or other external authority. The owner explicitly confirmed this disposition in the local Codex task before the first public push. |
| P-012 | M098 / hard inter-process persistence qualification | **Authorised for first public disclosure with this register update**: frozen protocol, standalone producer and isolated-consumer capsule, fault/rollback controls, checker, tests, preserved NEGATIVE result and post-verdict diagnosis | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; OpenAI Codex assistance is recorded in the repository provenance. Track A qualification records zero model and network calls | Milestone dependency and repository-integrity review complete; isolated consumers use the local base Python runtime and no project imports. No third-party data/model, confidential payload, credential, sealed task-bank content or remote execution is involved | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Successor to M097. The negative 11/12 verdict is preserved unchanged: the frozen stable projection retained an aggregate PID list; 11/12 conditions passed and P12 failed. Result `3cce5155…`; checker `b04513a2…`. |
| P-013 | M099 / stable hard inter-process persistence qualification | **Authorised for first public disclosure with this register update**: frozen successor protocol, recursively defined process-ephemera projection, fresh qualification worlds, checker, tests and preserved POSITIVE result | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research; OpenAI Codex assistance is recorded in the repository provenance. Track A qualification and independent replay record zero model and network calls | Milestone dependency, leakage and repository-integrity reviews complete; no new runtime dependency, third-party data/model, confidential payload, credential, sealed task-bank content or remote execution is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Distinct successor to preserved M098, using fresh worlds and a precommitted recursive ephemera projection while retaining causal process-boundary evidence. It validates persistence after producer death, isolated fresh consumers, negative controls, live corruption and exact-byte rollback. The owner explicitly confirmed this disposition in the local Codex task before the first public push. |
| P-014 | M100 / repeated cumulative acquisition across persisted process-separated cycles | **Authorised for local development and first public disclosure before enabling implementation**: a bounded state-derived assembly language in which the persisted M097 subtraction operation enables acquisition of a distinct addition operation, which in turn enables a later weighted-addition operation under a frozen construction bound; planned protocol, isolated runtime, qualification population, controls, checker and tests | Sole-human/AI-assisted framework established; Anthony Mets directs and explicitly authorises the research and public disposition; OpenAI Codex assistance is recorded in the repository provenance. Track A is required for the canonical run, with zero model, network and remote-execution calls | Pre-implementation review identifies Python standard-library runtime code plus the repository's existing development test tooling only. No third-party data/model/benchmark, confidential payload, credential, sealed task-bank content or new system authority is planned | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-22 | Successor to M099. The planned claim is bounded cumulative constructive reach and live dependency across fresh processes, not new unbounded expressivity, self-hosting, open-ended evolution or general intelligence. Registered definitions remain dependency-bearing state rather than cached host semantics. The owner confirmed this exact disposition in the Codex task before any M100 enabling file was created. Outcome: M100 attempt 1 qualified positively at 12/12; result `241292fc…`, checker `d8e945a5…`. |
| P-015 | M101 / cross-family cumulative transfer mechanism | **Authorised for local development and first enabling public disclosure before implementation push**: a bounded carrier-neutral two-stage combinator acquired from public text demand, persisted as lineage state, transferred across text/record/Python-syntax carriers, and used as a live prerequisite for a later three-effect syntax acquisition; planned frozen 15-world population, fresh baseline, isolated capsule, mutation/ablation/corruption/rollback/replay controls and independent checker | Sole-human/AI-assisted framework established; Anthony Mets directs and authorises the research and public disposition. OpenAI ChatGPT provided substantial AI-assisted research-design and implementation support for this pre-freeze work and is recorded as tooling, not authorship. Track A canonical qualification requires zero model, network and remote-execution calls | Pre-implementation review and IP review are recorded before this enabling implementation disclosure. Planned implementation uses Python standard library plus existing pytest development tooling and the already-public frozen M100 runtime; no third-party data/model/benchmark, confidential payload, credential, sealed task-bank content or new system authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-23 | Successor to M100 under pre-registration H46/D070 merged at `d7970655…`. Outcome: M101 attempt 1 qualified positively at 15/15 with zero model/network/remote calls; result `486f33e…`, checker `95bffc8b…`. D070 limits the result to partial bounded cross-family mechanism evidence: all carriers/evaluators remain authored, so it does not close G4 or establish natural-world generality, self-hosting, open-ended evolution or AGI. |
| P-016 | M102 / acquired registry addressing under cumulative interference | **Authorised for local development and first enabling public disclosure before implementation**: a bounded state-owned registry-policy language acquired after an observable flat-key collision, transactional migration that preserves the exact M101 predecessor, destructive-interference controls, and a later M101-dependent transformation executed and scored against actual SQLite state | Sole-human/AI-assisted framework established; Anthony Mets directs the continuing Genesis II research under the standing public-research policy. OpenAI Codex provides substantial research-design and implementation assistance and is recorded as tooling, not authorship. Track A canonical qualification requires zero model, network and remote-execution calls | Pre-implementation review records Python standard-library `sqlite3` plus its independently maintained SQLite engine. SQLite's official record describes the deliverable as public domain. No external model/data/benchmark, confidential payload, credential, sealed bank or new system authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-23 | Successor to M101/D070. Planned claim: bounded state-owned improvement of registry addressing prevents measured catastrophic forgetting and becomes causally necessary for a later jointly retained capability under a real SQLite interface. Fixtures/adapters/evaluator remain project-authored; this does not close G4/G5, establish independent external-domain transfer, self-hosting, open-ended improvement, general-agent evidence or AGI. |
| P-017 | M103 / state-owned hypothesis-constructor extension | **Authorised for local development and first enabling public disclosure before implementation**: exact M102 U2 migration, exhaustive context-invariant S0 closure, bounded acquisition and serialization of a generic context-conditioned constructor extension S-prime, process-death reuse in later configuration/filesystem acquisitions, ambiguity refusal, equal-budget/fresh-lineage controls and predecessor conservation | Sole-human/AI-assisted framework established; Anthony Mets directs the Genesis II successor work after M102. OpenAI Codex provides substantial research-design and implementation assistance and is recorded as tooling, not authorship. Track A canonical qualification requires zero model, network and remote-execution calls | Pre-implementation review identifies Python standard library plus existing development tooling only. `configparser`, `pathlib` and disposable filesystem execution are real interfaces but not independent task authorship. No external package/model/data/benchmark, confidential payload, credential, sealed bank, network service or new system authority is introduced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-24 | Successor to M102/D071. Planned claim: bounded improvement of the machinery that constructs later hypotheses, measured as new constructive reach rather than search efficiency. S-prime must remain causally necessary for a later acquisition, but compiled consumers are not falsely required to depend on it at execution. Feature vocabulary, carriers, tasks, adapters and evaluator remain authored; this cannot establish self-hosting, recursive/open-ended self-improvement, close a generality gate, provide general-agent evidence or support an AGI claim. See `docs/IP_REVIEWS/M103_PUBLICATION_REVIEW.md`. |
| P-018 | M104 / fresh-population M103 checker-instrument successor | **Authorised for public pre-registration and implementation before enabling code**: exact M103 mechanism, fresh qualification population, experiment adapter and direct-script checker bootstrap/preflight | Sole-human/AI-assisted framework established; Anthony Mets directs the research and OpenAI Codex provides substantial design, implementation and audit assistance as tooling. Track A qualification requires zero model, network and remote-execution calls | Python standard library and existing development tooling only. No external model/package/data/benchmark, confidential payload, credential, sealed bank or new authority | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-24 | D072-prescribed successor to the negative M103 checker instrument. M104 may not edit, rerun or relabel M103. A positive fresh-population result would remain bounded project-authored constructor-reach evidence and would not close a generality gate or support an AGI claim. See `docs/IP_REVIEWS/M104_PUBLICATION_REVIEW.md`. |
| P-019 | M105 / executable state-owned constructor-vocabulary extension | **Authorised for public pre-registration, enabling implementation, freeze, one canonical attempt/checker and merge before implementation**: exact M104 V3 migration, initially empty feature registry, complete bounded Boolean semantic substrate, DEVELOPMENT-only acquisition of a content-addressed executable feature, later generalized JSON/SQLite consumers and causal controls | Sole-human/AI-assisted framework established; Anthony Mets directs and explicitly authorises the continuing sequence. OpenAI Codex provides substantial design, implementation, audit and documentation assistance as tooling, not authorship. Track A canonical qualification requires zero model, network and remote-execution calls | Python standard library, existing development tooling, public M104/M103 implementation and SQLite through the standard-library binding. No external model/package/data/benchmark, confidential payload, credential, sealed bank, network service or new authority | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-24 | Successor to positive M104/D073. Planned claim is bounded executable constructor-vocabulary extension beyond finite exact-context dispatch, not lower-interpreter ownership, open-ended improvement, gate closure, general-agent evidence or AGI. The fixed Boolean operators, two-signal interface, bounds, carriers, tasks, adapters and evaluator remain authored. See `docs/IP_REVIEWS/M105_PUBLICATION_REVIEW.md`. |
| P-020 | M116 / H61 strict-JSON capacity corrective replication | **Authorised for public pre-registration, development-only transport validation, enabling implementation, freeze and one future canonical H61 attempt**: preserve the closed M115 record and the M115 scientific target while prospectively hardening the blind-bank generator against the observed terminal `invalid_json` admission failure. Development probes must remain non-qualifying and may not send the H61 qualifying input | Sole-human/AI-assisted framework established; Anthony Mets remains the sole human research director and the sole acceptance/release decision-maker. OpenAI ChatGPT provided substantial earlier research-design/audit assistance including the original pre-registration candidate. Anthropic Claude subsequently provided substantial implementation, code-review, testing and research-analysis assistance for the prospective pre-freeze instrument hardening (telemetry allowlist and read boundary, deterministic terminal classifier, machine-only pre-seal admission and positional carrier envelope, derived schema-complexity census, pre-generation tested-system freeze and its mechanical inventory checker). OpenAI Codex or comparable tooling may additionally provide independent review or execution assistance. All are recorded as AI tooling and AI development assistance, none as human authorship, and none holds acceptance authority | Python standard library and existing development tooling plus the already-used OpenRouter/DeepSeek external generation route. No credential, plaintext blind bank, confidential third-party payload or new system authority may be committed. M115 remains closed and immutable | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-08-31 | Corrective successor to M115/H60, which ended `instrument-aborted` with H60 untested after one legitimately revealed completion failed strict-JSON admission. M116 may change only predeclared generator/instrument controls needed to obtain an admissible blind bank; it may not retry, repair or relabel M115. Prospective pre-freeze hardening additionally moves the tested-system freeze ahead of the qualifying generation, so that no content-correlated operational metadata can exist while the tested system is still editable. Any H61 result remains bounded blind-generated-bank evidence and does not by itself advance a generality gate or support an AGI claim. See `docs/IP_REVIEWS/M116_PUBLICATION_REVIEW.md`. |
| P-021 | M117 / H62 route-qualification instrument development and calibration | **Retroactively recorded owner disposition for already-public M117 instrument-development and calibration work**: route qualification, candidate-universe commitment, DEVELOPMENT probes, audit/checker apparatus and the closed M117 record. M117 is not a scientific result; H62 was never tested | Sole-human/AI-assisted framework established; Anthony Mets remains the sole human research director and explicitly confirms this publication disposition on 2026-09-02. Anthropic Claude, OpenAI Codex and OpenAI ChatGPT assistance is treated as AI tooling where recorded in repository provenance, not as human authorship or release authority | Existing external model/provider routes were used only within the recorded instrument-calibration boundary. No credential, confidential third-party payload, plaintext sealed bank or new system authority is committed | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-02 | This row acknowledges that M117 was already publicly disclosed before the ledger was updated; it does not rewrite that chronology. M117 closed as instrument development/calibration with H62 untested and no generality gate advanced. |
| P-022 | M118 / H63 instrument design and audit | **Retroactively recorded owner disposition for already-public M118 instrument-design and hostile-audit work**: fixed-route readiness checks, preregistration/freeze apparatus, decomposition/arms design, checker/tests and the closed M118 record. M118 was deliberately stopped before any scientific generation; H63 was never tested | Sole-human/AI-assisted framework established; Anthony Mets remains the sole human research director and explicitly confirms this publication disposition on 2026-09-02. Substantial AI assistance remains recorded as tooling, not human authorship or acceptance authority | The already-calibrated external route was used only for DEVELOPMENT readiness calibration. No qualifying scientific generation, confidential third-party payload, credential, plaintext sealed bank or new system authority is introduced by this disposition | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-02 | This row acknowledges prior public disclosure rather than pretending the review preceded it. M118 closed as an instrument-design/audit milestone; qualifying scientific invocations remained zero and no generality gate advanced. |
| P-023 | M119 / H64 minimal carrier-bank qualification instrument | **Owner-authorised public disposition for the already-public PR/branch and its mergeable record**: frozen minimal generator/qualification apparatus, sealed/reveal chronology, carrier bank, checker/tests and `instrument_aborted` outcome. H64 remains UNTESTED; no arm ran and no scientific comparison was made | Sole-human/AI-assisted framework established; Anthony Mets remains the sole human research director and explicitly authorises continued public disclosure and merge on 2026-09-02. Anthropic Claude and OpenAI Codex review/implementation assistance is recorded as AI tooling, not human authorship or release authority | One qualifying external generation invocation was spent under the frozen protocol. `SEALED_BANK.json.gpg` is ciphertext; no passphrase, credential or plaintext sealed payload is committed. The revealed `CARRIER_BANK.json` is public by protocol after authorised reveal. Two post-reveal checker weaknesses are disclosed and intentionally left frozen for successor correction | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-02 | The branch/PR was already public before this owner decision was entered, so this is a transparent backfill, not a claim of pre-disclosure review. Canonical M119 used the committed plan and measurements and replays byte-identically; the preserved verdict is `instrument_aborted`, H64 untested, with no negative scientific inference and no generality gate movement. |
| P-024 | M120 / H65 live-route carrier-contract readiness milestone | **Retroactively recorded owner disposition for already-public M120**: carrier-contract redesign, readiness instrument, tests and closed readiness record. H65 remained UNTESTED and no qualifying scientific invocation was sent | Anthony Mets remains sole human research director and explicitly accepted this public disposition on 2026-09-05. AI implementation/review assistance remains tooling, not human authorship or release authority | Existing external route used for DEVELOPMENT readiness only; no credential, sealed bank, confidential third-party payload or new system authority is committed | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-05 | Transparent post-disclosure reconciliation. M120 closed at readiness after the candidate schema required eight array-of-object levels while the route enforced five. No scientific result or generality-gate movement. See `docs/IP_REVIEWS/M120_PUBLICATION_REVIEW.md` and `docs/IP_REVIEWS/OWNER_RECONCILIATION_2026-09-05.md`. |
| P-025 | M121 / H66 long-horizon quiescent-fault preregistration and design | **Retroactively recorded owner disposition for the already-public M121 preregistration/design work**. Public prospective hardening may continue, but this row does **not** authorise a canonical salt, one-shot scientific execution, reveal or result acceptance | Anthony Mets remains sole human research director and explicitly accepted this public disposition on 2026-09-05. AI systems may assist with design/audit but hold no acceptance authority | No scientific run has occurred. The independent preimplementation audit remains binding and requires schedule/fault grammar/endpoints to be frozen before any future canonical draw | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-05 | Publication permission is separated from scientific-run authority. M121/H66 remains preregistered and owner-gated for any canonical execution. See `docs/IP_REVIEWS/M121_PUBLICATION_REVIEW.md`, `docs/audits/M121_PREIMPLEMENTATION_REVIEW_2026-09-05.md` and `docs/IP_REVIEWS/OWNER_RECONCILIATION_2026-09-05.md`. |
| P-026 | M123 / H68 empirically sized readiness successor | **Retroactively recorded owner disposition for already-public M123**: inherited M122 carrier contract, empirical stress sizing, corrected unanswered-vs-unenforced accounting, cross-milestone delivery ceiling, tests and closed readiness record | Anthony Mets remains sole human research director and explicitly accepted this public disposition on 2026-09-05. AI assistance is tooling only | Existing external route used for DEVELOPMENT readiness. No carrier bank, qualifying scientific generation, sealed bank or reveal was produced | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-05 | M123 remains closed at its frozen `not_ready_stress` readiness verdict; H68 remains UNTESTED. The decision is retrospective and does not reinterpret the malformed completion. See `docs/IP_REVIEWS/M123_PUBLICATION_REVIEW.md` and `docs/IP_REVIEWS/OWNER_RECONCILIATION_2026-09-05.md`. |
| P-027 | M122 / H67 flattened live-route carrier contract and readiness instrument | **Retroactively recorded owner disposition for already-public M122**: flattened carrier contract, capability probes, stress/readiness gate and closed readiness record | Anthony Mets remains sole human research director and explicitly accepted this public disposition on 2026-09-05. AI assistance remains tooling, not acceptance authority | Existing external route used for DEVELOPMENT readiness only; no qualifying scientific invocation, bank or reveal | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-05 | Ledger ID follows P-026 because M122's missing review was prepared later; milestone chronology is unchanged. Nine of nine capability classes conformed, but the stress produced 30,957 tokens against the inherited 32,000 threshold, so H67 remained UNTESTED. See `docs/IP_REVIEWS/M122_PUBLICATION_REVIEW.md` and `docs/IP_REVIEWS/OWNER_RECONCILIATION_2026-09-05.md`. |
| P-028 | M124 / H69 no-finish_reason readiness successor | **Retroactively recorded owner disposition for already-public M124 and its preserved readiness attempt**. The owner also decided on 2026-09-05 to close M124 **without replay**; that stopping decision is experimental governance, not a reclassification of the archived attempt | Anthony Mets remains sole human research director and explicitly accepted this disposition and no-replay closure on 2026-09-05. AI systems assisted with implementation and hostile review but hold no acceptance authority | Existing external route used for DEVELOPMENT readiness only. No qualifying scientific generation, carrier bank, seal, reveal or scientific result exists | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-05 | Archived readiness attempt remains `not_ready_delivery`, H69 remains UNTESTED, and the remaining allowance is deliberately unused. Known delivery/attribution defects are prospective M125 requirements and do not reinterpret M124. See `experiments/M124/OUTCOME.md`, `docs/IP_REVIEWS/M124_PUBLICATION_REVIEW.md` and `docs/IP_REVIEWS/OWNER_RECONCILIATION_2026-09-05.md`. |
| P-029 | M125 / H70 prospective bounded readiness and fresh-calibration instrument | **Owner-authorised before enabling implementation**: public implementation and offline DEVELOPMENT hardening/tests may proceed; no M125 request or scientific execution is authorised by this row | Anthony Mets remains sole human research director and explicitly accepted this disposition on 2026-09-06. AI systems may assist with design, implementation, tests and audit but hold no acceptance authority | Planned implementation uses existing project-controlled Python apparatus, standard library/existing development tooling and the already-used external route only after a separately frozen request protocol. No credential, confidential third-party payload, plaintext sealed bank or new system authority is authorised | **`PUBLIC_AGPL_COMMERCIAL_OPTION`** | 2026-09-06 | P-029 is prospective: it precedes enabling M125 implementation. H70 has zero scientific observations. The inherited global delivery count remains 4/6. Historical M122/M123/M124 token observations are excluded from M125 calibration. Any network request remains blocked until the exact M125 protocol is committed and mechanically verified; any H70 qualifying scientific generation/reveal remains separately owner-gated. See `docs/IP_REVIEWS/M125_PUBLICATION_REVIEW.md`, `docs/IP_REVIEWS/P029_OWNER_DECISION_2026-09-06.md` and `docs/audits/M125_PREIMPLEMENTATION_REVIEW_2026-09-06.md`. |

Allowed dispositions:

- `PUBLIC_AGPL_COMMERCIAL_OPTION`
- `PUBLIC_RESEARCH`
- `PATENT_FIRST`
- `TRADE_SECRET_PRIVATE`
- `CONFIDENTIAL_THIRD_PARTY`
- `CONTRACTUAL_EMBARGO`
- `COMMERCIAL_PRIVATE`
- `ABANDONED`

The disposition must describe reality. Do not retroactively mark already public information as
secret.

### Prospective RSI V25 review — 1 October 2026

| ID | Mechanism / asset | Publication posture | Human provenance | Third-party review | Disposition | Decision date | Evidence / notes |
|---|---|---|---|---|---|---|---|
| P-030 | V25 / executable predecessor-bound L5 apparatus | Reviewed before enabling implementation; public preparation and a prospectively frozen one-shot attempt under the owner's instruction to continue toward L5 | Anthony Mets directs the work; OpenAI Codex assists as tooling | Python standard library and existing test tooling; exact public project-controlled Cellar/Vibe Arcade snapshots with source attribution; no private repository or vendor code | `PUBLIC_AGPL_COMMERCIAL_OPTION` under the standing public-research disposition | 2026-10-01 | `docs/IP_REVIEWS/V25_EXECUTABLE_L5_PUBLICATION_REVIEW.md`. No scientific result, independent-maintainer claim, new mutable authority or revision of V23/V24 evidence is licensed by this entry. |

## Alternative commercial licensing chain-of-title rule

Alternative commercial licensing is only possible to the extent the project controls the rights
needed for the requested permissions.

Until a qualified contributor agreement is adopted, externally authored copyrightable code,
documentation, tests or other substantive material must not be merged merely under DCO sign-off.

Any future contributor agreement intended to preserve commercial relicensing or acquisition
optionality should explicitly address the rights needed for:

- public AGPL licensing;
- alternative proprietary/commercial licensing;
- modification and distribution;
- assignment/acquisition of the project owner's controlled rights.

## AI-assisted-development diligence

OpenAI Codex and Anthropic Claude are recorded as substantial development tools, not human
contributors. OpenAI ChatGPT is also recorded where historically used. Preserve human problem
formulation, architecture/protocol decisions, selection/rejection/editing and release decisions for
material future assets.

Provider terms are a separate contractual layer. Do not assume provider output-ownership language
clears third-party code licences, establishes copyrightability, or resolves inventorship.

See [`docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`](docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md).

## Third-party and dependency review

The initial repository-level inventory is in
[`docs/THIRD_PARTY_DEPENDENCIES.md`](docs/THIRD_PARTY_DEPENDENCIES.md). Before a commercial release
or acquisition data-room snapshot, generate a release-specific SBOM/licence inventory covering all
components actually distributed.

The alternative commercial licence must exclude or separately account for third-party material that
cannot be relicensed under the negotiated terms.

## Acquisition-readiness checklist

| Item | Status | Note |
|---|---|---|
| Human contributor snapshot | **RECORDED** | Sole-human development declaration + GitHub enumeration recorded |
| AI-assisted development provenance | **RECORDED** | Codex, Claude, historical ChatGPT and automation roles documented |
| Public AGPL + commercial-option strategy | **ACTIVE** | Public research is default after review; commercial rights sold separately where controlled |
| Historical public-licence boundary | **RECORDED** | Public history is not retroactively restricted |
| Initial third-party dependency inventory | **RECORDED** | Repository-level inventory exists; release SBOM still needed |
| Release-specific SPDX/CycloneDX SBOM | **PENDING** | Generate for exact commercial artefact/data room |
| External contributor agreements | **NOT CURRENTLY NEEDED / POLICY READY** | Required before future substantive external merge |
| Trademark search/filing | **PENDING** | Registration not asserted |
| Patent screening/filing | **PENDING PER CANDIDATE** | Must precede enabling disclosure when patent-first is considered |
| Standard commercial customer agreement | **PENDING** | Have first binding agreement reviewed by qualified counsel |
| Commercial licence/customer register | **PENDING UNTIL FIRST DEAL** | Preserve signed grants, versions, scope, fees and encumbrances |

Before presenting the project for acquisition or exclusive licensing, additionally verify:

- chain of title for every material right proposed for transfer;
- list of public AGPL/CC assets that remain public after the transaction;
- complete release-specific third-party licence/dependency inventory;
- every alternative commercial licence already granted and any surviving obligations;
- trademark/patent status accurately recorded;
- private trade-secret assets, if any, backed by real confidentiality measures;
- reproducible scientific evidence separated from proprietary product assets where relevant.

## Non-claims

Prospective development integration recorded on 9 October 2026:
`repair_self_improvement`, multilingual exercise execution and bounded
outcome-driven search-order adaptation follow `PUBLIC_AGPL_COMMERCIAL_OPTION`
under the standing public-research disposition. Anthony authorised starting RSI
development; OpenAI Codex assists as tooling. Review preceded enabling
implementation in `docs/IP_REVIEWS/REPAIR_SELF_IMPROVEMENT_REVIEW_2026-10-09.md`.
No independent RSI gate or new publication/execution authority is claimed.

This register does not claim that:

- public AGPL rights can be revoked;
- AGPL prohibits commercial activity;
- every commercial user must buy a licence;
- every line in the repository is copyrightable or exclusively controlled;
- sole-human development automatically proves ownership of every AI-generated or third-party-derived
  fragment;
- a commercial agreement can relicense third-party material beyond upstream rights;
- M086 or any other mechanism is patentable;
- `Mira Genesis` is a registered trademark;
- an AI system is a legal author or inventor;
- an external maintainer's material belongs to Mira Genesis.

Prospective repair-transformation review — 9 October 2026: bounded Java lexical
abstraction of verified development recipes, own-outcome local search and
separate transfer/promotion gates follow PUBLIC_AGPL_COMMERCIAL_OPTION under
the standing owner disposition. Anthony authorised implementation and three
new trials. Review preceded enabling implementation in
`docs/IP_REVIEWS/REPAIR_TRANSFORMATION_LEARNING_REVIEW_2026-10-09.md`.
OpenAI Codex assists with development; assisted repairs retain model attribution.
No independent/general RSI gate or new authority is claimed.

Prospective compiler-grounded repair quality review — 9 October 2026:
operator provenance, existing sandboxed Java AST/type analysis, expression
projection and outcome-aware selection follow PUBLIC_AGPL_COMMERCIAL_OPTION.
Anthony authorises end-to-end development and teacher/fresh-transfer trials.
Review precedes enabling publication in
`docs/IP_REVIEWS/REPAIR_QUALITY_LEARNING_REVIEW_2026-10-09.md`.
OpenAI Codex assists; external teacher origins remain attributed. No general RSI
or independent-maintainer gate is claimed.

Prospective assertion-localisation review — 9 October 2026: under the same owner
authorisation and PUBLIC_AGPL_COMMERCIAL_OPTION, an explicit opt-in fallback may
infer production method locations from failing-test API calls. Expected literals
are excluded and static hypotheses are not runtime coverage. Review precedes
publication in `docs/IP_REVIEWS/ASSERTION_LOCALIZATION_REVIEW_2026-10-09.md`.
Frozen quality-trial results remain unchanged; exposed-case engineering checks
are separately labelled. OpenAI Codex assists with development.

Prospective failed-search recovery review — 9 October 2026: bounded failure-derived
search generations and explicit stall diagnoses follow PUBLIC_AGPL_COMMERCIAL_OPTION.
Review precedes implementation in docs/IP_REVIEWS/REPAIR_STALL_RECOVERY_REVIEW_2026-10-09.md.
Anthony authorises iteration; OpenAI Codex assists. Existing frozen outcomes remain unchanged.

9 October 2026 — contract-guarded insertion learning follows
PUBLIC_AGPL_COMMERCIAL_OPTION under Anthony's authorisation to start transferable
capabilities. Review precedes implementation in
`docs/IP_REVIEWS/REPAIR_CONTRACT_RULE_REVIEW_2026-10-09.md`. OpenAI Codex assists;
model-derived provenance and explicit supplied-contract limits remain visible.

9 October 2026 — self-revising repair lineage follows PUBLIC_AGPL_COMMERCIAL_OPTION
under Anthony's authorisation to continue toward recursive improvement. Review precedes
implementation in `docs/IP_REVIEWS/REPAIR_LINEAGE_REVIEW_2026-10-09.md`. Configurations
are written by an external model inside a fixed envelope; held-out scoring happens once,
after the lineage is frozen. No general RSI claim.

9 October 2026 — local single-leaf genome revision follows
PUBLIC_AGPL_COMMERCIAL_OPTION under continued RSI authorisation. Review precedes
implementation in docs/IP_REVIEWS/REPAIR_LOCAL_REVISION_REVIEW_2026-10-09.md.
OpenAI Codex assists; external-model origin, exposed-development scope and
human-authored revision constraints remain explicit.
