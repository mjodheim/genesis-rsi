# V39 development — novelty-yield frontier memory

V39 is a development-only successor to the negative/insufficient V35–V38 line.
It does **not** consume fresh scientific data and cannot qualify L9.

The V35 grammar, tasks, witnesses, G7 controller, four arms, evaluator, search caps,
two paid probes and maximum fourteen charged evaluations are retained. Development
reuses the already-consumed V35 public seeds 503 and 887 so that the only intended
behavioral change is adaptive memory selection.

Adaptive reserves one paid memory slot for the existing task-compatibility ranking.
The second slot is selected from a deterministic novelty frontier: successful
sources are ranked by observed novel-solution yield from themselves and their
direct search children, with less-exhausted sources preferred on ties. Distinct
behavior witnesses are still required across the two adaptive memory slots.

If the novelty-frontier probe ties the identity program on current observed
quality, the fixed rule may use that frontier as the search root. This is the
anti-extinction hypothesis: an equally-good but less-exhausted basin can be worth
searching without increasing compute. No target, task label, domain, inputs or
future outcome enters the selector.

Success at development time means only that the mechanism merits a separately
committed prospective freeze on new seeds. Failure is retained and stops this
variant. L9 and L10 remain false regardless of this pilot.
