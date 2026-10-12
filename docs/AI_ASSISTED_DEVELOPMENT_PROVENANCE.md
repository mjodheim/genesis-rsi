# AI-assisted development provenance

**Snapshot date: 12 August 2026**

This record exists to make the development history of Mira Genesis easier to audit without
converting tool usage into unsupported legal conclusions. It should be read together with
[`AUTHORS.md`](../AUTHORS.md), [`IP_ASSET_REGISTER.md`](../IP_ASSET_REGISTER.md), the Git history,
and the experiment/protocol records.

## Human development declaration

Anthony Mets (`mjodheim`) records that, as of this snapshot, he is the **sole human developer and
research director of Mira Genesis**. He sets the project objectives, selects the architecture and
research direction, decides which experiments and protocols to run, reviews and accepts or rejects
implementation changes, interprets results, and authorises repository releases.

The GitHub contributor enumeration observed at this audit is consistent with that declaration: it
shows the `mjodheim` human account and repository automation, with no second human contributor
account observed. That observation is useful provenance evidence, but it is not by itself a legal
opinion or proof that every individual repository element is copyrightable or owned by one person.

## AI development tools

Mira Genesis has been developed with substantial generative-AI assistance under Anthony Mets's
direction. The principal tools recorded for the current development process are:

| Actor / tool | Project role | Human contributor? | Repository-rights treatment |
|---|---|---:|---|
| Anthony Mets (`mjodheim`) | Developer, research director, reviewer and release decision-maker | Yes | Human provenance recorded in Git and project records |
| OpenAI Codex | Coding, review, refactoring, testing, documentation and repository assistance | No | Recorded as an AI development tool; provider/account terms remain separately applicable |
| Anthropic Claude | Coding, review, analysis, testing, documentation and research assistance | No | Recorded as an AI development tool; provider/account terms remain separately applicable |
| OpenAI ChatGPT, where historically used | Analysis, design, review, documentation and assistance | No | Recorded as an AI development tool; provider/account terms remain separately applicable |
| `github-actions[bot]` | CI/repository automation | No | Automation, not a human author or contributor |

The table records how the project was produced. It does **not** state that an AI system is a legal
author or inventor, and it does not infer ownership merely from the fact that a tool generated text
or code.

## Human control and selection record

For material work, the project should preserve evidence that the human developer exercised actual
project control. Relevant evidence can include:

- the human-defined research question, protocol, success/failure criteria and release boundary;
- architecture and scientific-governance decisions recorded in project registers;
- selection, rejection, correction or editing of generated alternatives;
- review of tests and measured environment state before acceptance;
- commit/PR history showing what was integrated and when;
- explicit decisions not to publish, merge or claim results that failed the protocol;
- invention/disclosure entries made before publication for prospective M086+ core mechanisms.

This is a provenance discipline, not a requirement to pretend that every keystroke was written
without automation.

## Provider terms are a separate diligence layer

AI-provider terms can affect the contractual treatment of inputs and outputs and can change over
time. They must therefore be archived or re-checked for the account/product actually used when a
commercial licence, acquisition or patent filing is prepared.

At this snapshot, OpenAI's European terms state, as between the user and OpenAI and to the extent
permitted by law, that the user owns Output and that OpenAI assigns any right, title and interest it
may have in Output. OpenAI's current Service Terms additionally warn that code-generator output,
including Codex output, can be subject to third-party licences. Those contractual statements do not
eliminate the need to review third-party provenance or decide whether a particular output is
copyrightable under applicable law.

Anthropic has publicly stated that its commercial terms allow commercial customers to retain
ownership rights over generated outputs. Because Mira Genesis may be developed under a consumer or
commercial Claude product at different times, this register does not assume which Anthropic contract
applies to a given session. The exact plan/account terms should be preserved when material private
R&D is performed.

Reference points checked on 12 August 2026:

- OpenAI EU Terms of Use: <https://openai.com/policies/eu-terms-of-use/>
- OpenAI Service Terms (including Codex/code-generation notice): <https://openai.com/policies/service-terms/>
- Anthropic consumer-data/terms update: <https://www.anthropic.com/news/updates-to-our-consumer-terms>
- Anthropic statement on commercial output rights: <https://www.anthropic.com/news/expanded-legal-protections-api-improvements>

These links are evidence of the snapshot, not a substitute for archiving the exact agreement that
applied to the account at the time of a material private invention.

## Third-party-output discipline

Generated code must not be assumed clean merely because it came from an AI tool. For material
M086+ private assets and any commercial release:

1. review suspiciously distinctive generated code or attribution/citation signals before accepting it;
2. do not deliberately prompt a model to reproduce proprietary source that the project is not
   entitled to use;
3. keep dependency and licence review separate from AI-provider contractual rights;
4. preserve upstream notices when third-party components are intentionally incorporated;
5. replace or independently rewrite material whose provenance cannot be made satisfactory for the
   intended commercial use.

## External human contributors

Externally authored copyrightable code, tests, documentation or other substantive material remain
subject to [`CONTRIBUTING.md`](../CONTRIBUTING.md). They are not accepted for merge unless an
appropriate contributor-rights arrangement has first been approved. A DCO sign-off is provenance,
not a copyright assignment.

Issues, reproducibility reports and non-confidential suggestions can still be received without
turning the reporter into a code contributor. If a suggestion becomes sufficiently expressive or
substantive to create a rights question, it should be handled before incorporation rather than
papered over after merge.

## Patent/inventorship caution

This document does not decide inventorship. If a future M086+ mechanism is considered for patent
protection, inventorship should be analysed claim-by-claim with qualified counsel before public
disclosure. The project should preserve the human problem formulation, conception records,
iterations, rejected alternatives and the role of AI tools so that the factual history exists for
that review.
