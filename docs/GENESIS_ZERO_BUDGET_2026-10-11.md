# Genesis at no additional cost: spending, hardware, and why components bring so little

11 October 2026, evening. Anthony refuses the GPU pilot and sets the additional budget to
zero. Paid OpenRouter requests for Genesis are stopped (the two pilots still running were
killed; no result of theirs is used beyond what `SELF_IMPROVER_LINEAGES_2026-10-11.md`
already reports). General RSI remains the objective, not an achieved result.

## 1. What was spent, 8 to 11 October

Verified at the provider (OpenRouter account, read on 11 October, all uses of the key
together, Genesis and the other services that share it): USD 80 of credit bought in all,
USD 65.79 used in all, USD 22.26 this month, USD 17.77 this week, USD 14.21 left.

Verified request by request (journals of each experiment, cost returned by the provider):

| Experiment | Date | Requests | Model | USD |
|---|---|---|---|---|
| Repair lineage 1 | 9 Oct | 826 | Haiku 5.5 | 1.11 |
| Repair lineage 2 | 9 Oct | 1,150 | Haiku 5.5 | 1.27 |
| Localized repair | 9 Oct | 275 | Haiku 5.5 | 0.39 |
| Coverage repair | 10 Oct | 138 | Haiku 5.5 | 0.22 |
| Repair interventions | 10 Oct | 1,230 | Haiku 5.5, Sonnet 5.5 | 2.92 |
| Improver pilot | 11 Oct | 168 | Haiku 5.5 | 0.30 |
| Lineage SELF1 | 11 Oct | 2,530 (3.2 M tokens in, 8.8 M out) | Haiku 5.5 | 4.71 |
| Second-bench pilots | 11 Oct | 503 (0.5 M in, 1.3 M out) | gpt-oss-20b, gpt-oss-120b, mistral-nemo | 0.17 |
| **Subtotal verified** | | **6,820** | | **11.09** |

Reported in sealed documents, not recomputed here: program improvement (IMPROVE1 and its
pilots, 10 October) USD 2.50 for the two arms plus USD 0.46 for the strict pilot; localizer
lineage USD 0.27; model comparisons and small trials of 8 October about USD 0.25.
**Estimate for Genesis on OpenRouter: USD 14 to 15**, consistent with the week's account
total of USD 17.77 that also covers the other services.

Not billed per request (subscriptions): 209 Codex requests on 11 October, about 18,000
tokens each, so about 3.8 M tokens of the ChatGPT subscription; Sonnet 5.5 through the
Claude client on 8 October (the journals carry a notional cost of a few dollars that was
not charged); the working sessions themselves, whose consumption is not visible from here.
No invoice was read: everything above comes from the provider's API and from journals.

CIRCUIT1 and CIRCUIT2: no request; 80 and 11 minutes of this server's processor.

## 2. A reduced training pilot on the RTX 2060 Super (8 GB)

Read on the machine on 11 October, read-only: GeForce RTX 2060 SUPER, 8,192 MiB, 3,506 MiB
already in use by the desktop, driver 617.14, Windows; no Python on the path, no Linux
subsystem listed. Nothing was installed or changed.

What 8 GB allows, and what it does not:

| | Fits | Remark |
|---|---|---|
| Protocol proposed earlier (QLoRA on 3B, then 7B) | No | 7B in 4 bits needs 12 GB or more with training activations; 3B fits only with short sequences and the desktop closed |
| QLoRA on a 1.5B model (Qwen2.5-Coder-1.5B) | Yes, tightly | About 1.5 GB of weights in 4 bits, 3–4 GB while training on sequences of 512 tokens |
| LoRA or full fine-tuning of a 0.5B model | Yes | Comfortable |
| Generating 20,000 attempts per generation | Slow | Order of hours per generation at 0.5B–1.5B on this card; the machine must stay on |
| Small networks trained from scratch (millions of parameters) to guide a search | Yes, easily | Also feasible on the server's processor |

What the literature says to expect at that size: gains from self-generated verified data
shrink with the model (Absolute Zero: +5.7 points at 3B with an early plateau, against
+10.2 at 7B); nothing is published below 3B. A pilot at 0.5B–1.5B would test whether any
gain survives at that scale and would most likely be negative or within noise. It is a
real limit of the hardware: the size at which the effect is documented does not fit.

Conditions before anything runs there: Anthony's agreement to install Python, PyTorch and
the model on his personal machine (several gigabytes), and the machine left on. Not done.

The use of that card that fits the findings below is different: training a small guidance
network for the circuit engine's search, which needs megabytes, not gigabytes.

## 3. Why modifying components brings almost nothing

Measured on the 3,057 improvement trials CIRCUIT1 stored (932 steps, 260 lineages; the
lineages under ranking variants are near-duplicates, so counts are not independent):

| Step | Lineages still running | Components proposed per step | Tasks gained per step | Trials that gain a task |
|---|---|---|---|---|
| 1 | 260 | 4.2 | 0.98 | 26% |
| 2 | 208 | 3.7 | 2.38 | 34% |
| 3 | 205 | 3.3 | 0.69 | 26% |
| 4 | 164 | 2.1 | 0.09 | 5% |
| 5 | 65 | 2.5 | 0.23 | 11% |
| 6 | 26 | 2.8 | 0.00 | 0% |

- **The space of modifications is tiny and runs out.** Twenty-four distinct components
  appear in all. Each accepted component leaves fewer to propose, not more: the loop that
  should feed itself has a gain below one.
- **A modification is a trade, not a gain.** 24% of trials gain a task, 37% lose at least
  one, 39% change nothing. Every component is applied everywhere in a blind search, so it
  taxes every task and pays only where it shortens a circuit to within reach.
- **What helps is not predictable from what a component looks like.** Support, the seed
  procedure's ranking, predicts a gain with an area under the curve of 0.54 overall and
  below 0.4 on two of three subsets; the mean gain observed for a component in lineages on
  some families predicts its gain on others at 0.55 to 0.69.

The same three causes read across the earlier experiments:

| Condition for improvements to compound | Repair agent | Improvers (SELF1) | Circuit engine |
|---|---|---|---|
| The thing modified is what limits | No: the model limits | No: the model limits | Partly: the search limits, components only shorten it |
| A modification can be judged cheaply and exactly | No: each judgment costs model requests and test suites | No: 24 requests per noisy evaluation | Yes |
| The space of modifications is open-ended | No: a configuration | In principle (code), in practice five rewrites | No: 24 components |
| An improvement enlarges what the next step can find | No | No | Briefly, then the supply dries up |

An architecture in which improvement compounds needs all four at once. CIRCUIT2 tests the
last two on the engine that already has the second: an open space of components (H1) and a
step that ranks its proposals from the trials of earlier lineages (H2).

## 4. CIRCUIT2: both hypotheses refuted

Plan frozen before any run (`provenance/circuit-meta-plan-20261011`); same engine, tasks
and held-out families as CIRCUIT1; 125 lineages, 11 minutes of processor time, no request.
Records: `experiment/engine/CIRCUIT2/`.

**H1, opening the space: refuted.** With components of up to four inputs from sub-circuits
three layers deep, a step has 24 to 32 components to propose instead of 4, and the supply
no longer falls. Held-out tasks solved, by seed: 11, 11, 11, 11, 11, against 11, 17, 14,
11, 11 for the CIRCUIT1 lineage. No lineage keeps more than one component. More to choose
from, six tried, the useful ones not among them: the supply was not the wall.

**H2, learning to improve: refuted.** Family groups: (and, or, parity), (equal,
multiplexers), (adder bits, thresholds); ten seeds; a ranker fitted on the trials of
lineages on the other groups.

| Ranking of proposed components | Learning tasks gained | Held-out solved | Gain per trial |
|---|---|---|---|
| Random | 3.67 | 9.4 | 0.184 |
| Most shared first (seed procedure) | 3.27 | 9.4 | 0.151 |
| Learned on one other group | 3.77 | 10.0 | 0.180 |
| Learned on two other groups | 3.63 | 10.1 | 0.188 |

Learned on two groups against random: 7 pairs won, 13 lost, sign test 0.94. Against the
ranker learned on one group: 4 won, 5 lost. More experience of improving does not make
improving more productive. The diagnostic says why: the six rankers predict "this trial
gains a task" on their target group with areas under the curve of 0.43, 0.17, 0.59, 0.60,
0.06 and 0.58. On the group (equal, multiplexers) what was learnt elsewhere is nearly the
exact opposite of what helps. Held-out tasks lean the other way (10.1 against 9.4, 12
pairs won and 7 lost, sign test 0.18): not established, and not what the ranker was
fitted for.

What the two refutations establish:

- In this engine the worth of a modification is a property of the pair (modification,
  tasks), not of the modification. Nothing general about "good improvements" exists to be
  learnt at this level, so the improvement step cannot become cheaper or better with
  experience: it has to pay a full evaluation for every candidate, every time.
- Opening the space of modifications without a way to choose inside it makes things worse.
- Together with CIRCUIT1: the improvement process of this architecture has no slack left
  in selection, ranking, supply or procedure parameters. What remains is the solver's
  search itself, which is exponential in circuit size and which components only shift.

## 5. What could change the situation, at no cost

The one change that attacks the measured wall is to make the search directed: a learned
function that, given the target, says which signals are worth building. It is the part of
AlphaZero that the engine lacks, and its training data is free: every search already
produces thousands of (function, circuit) pairs, of which CIRCUIT1 and CIRCUIT2 used only
the solved targets. It fits this hardware: a network of a few hundred thousand parameters
trains on the server's processor or on the 8 GB card.

Proposed as the next and only experiment (CIRCUIT3), with its refutation fixed in advance:

- **Hypothesis.** A guidance model trained on the engine's own search traces lets the
  engine solve, at the budget of 30,000 component applications, more held-out tasks than
  the frozen engine solves with ten times that budget (18 of 41); and a second round,
  trained on the traces of the guided engine, solves more than the first.
- **Refuted if** the guided engine stays below 18, or the second round does not exceed
  the first. The first failure would mean the wall is not guidance at this scale; the
  second, that guidance helps once and does not compound.
- **Controls.** The same network with shuffled targets; the same compute spent on plain
  search.

What stays out of reach whatever is done here, stated as a limit and not worked around:
retraining a language model of the size at which self-improvement on verified data is
documented (3B and above), and searches of the scale of published program-evolution
systems (tens of thousands of model requests).

