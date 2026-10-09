# Repair feedback development — 9 October 2026

## Hypothesis and attribution

The previous local revision pilot found no gain (4/6 versus 4/6). Inspection identified
two actionable instrument limits: an inapplicable submission immediately ends the
proposer's round, and rejected descendants do not inform subsequent successor writing.
Anthony authorised starting the next development step. The design and code below are
OpenAI Codex-assisted infrastructure changes, not autonomously discovered Genesis skills.
Publication review precedes implementation in
`IP_REVIEWS/REPAIR_FEEDBACK_REVIEW_2026-10-09.md`.

My working hypothesis is that a proposer must distinguish failure to express an edit
from failure of its repair hypothesis before broader code evolution can be evaluated.
More informative feedback may also consume context or encourage overfitting. Improvement
is therefore a hypothesis, not a consequence of the infrastructure tests passing.

## Implemented experimental mode

New lineage plans can opt into `--cumulative-feedback --no-meta`:

- A nonempty submission with no applicable edits receives a tool response identifying
  refused paths or nonunique/missing search text. If requests remain in that round,
  the model may read the actual production source and correct its submission.
- The request allocation, model spending ledger and validation ceiling do not grow.
  Explicit empty submissions still stop, and a final-step failure cannot obtain an
  additional request. Mixed submissions return the applicable candidates without
  spending extra requests to repair the rejected ones.
- The call journal records edit proposals, applicability diagnostics and bounded
  read-only tool output excerpts. Detailed training reports include these observations.
- Subsequent successor writing receives the current parent's training report plus
  bounded reports of the last eight attempted descendants, including rejected ones.
  Reports retain configuration changes and training feedback. Selection scores and
  promotion/rejection decisions are not fed back. Reports are capped at 24,000 characters;
  this is a bounded recent history, not an unlimited archive or semantic skill library.
- Experimental evaluation caches use a separate suffix. Held-out preregistration
  records the mode and runs both arms with the same feedback setting. Legacy plans
  default to the previous behavior. Previously frozen evidence is unchanged.

The existing meta comparison is explicitly disabled for this mode until its comparison
protocol is adapted and frozen. This change does not enable self-editing solver code.

## Verification and limits

Thirty focused tests passed: five new feedback/history checks, twenty lineage checks
and five local-revision checks. The new tests verify a rejected edit followed by a
source read and corrected proposal, request exhaustion, intentional empty submission,
bounded training-only history and the complete two-generation evolution loop with a
rejected child. In that offline loop the next writer receives the rejected child's
training failure while selection details stay excluded and no child is promoted.

These tests use authored examples and scripted model responses. No new live model
calls or real-bug measurements were performed. There is no verified repair-rate gain,
no promotion, no claim of autonomous mechanism invention and no general RSI result.

## Next experiment

Freeze a paired development comparison of the old and new feedback paths, with equal
request/validation ceilings and a shared spending limit. Measure usable submissions,
validated candidates, verified repairs and total cost, including failed calls. Keep
previously exposed cases labelled development. A later transfer evaluation must use
fresh reserved cases after the mechanism and selection rule are frozen.

Only then extend the mutation space to bounded executable solver modules and compare
old/new improvement mechanisms from the same starting solver at equal resources.
An archive may retain exploratory variants without authorising their deployment.
