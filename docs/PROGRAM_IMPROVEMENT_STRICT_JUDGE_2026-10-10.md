# A stricter judge for chained improvements — 10 October 2026

General RSI remains the objective, not an achieved result. IMPROVE1 accepted rewrites that
were identical on the recorded calls and wrong elsewhere: 4 of 24 read
(`PROGRAM_IMPROVEMENT_2026-10-10.md`). This report covers the correction of the judge and
its check on development cases. The 170 trial cases of IMPROVE1 are consumed and are not
used as a new test.

## What changed

1. **Generated variants.** Up to 400 variants of 16 recorded calls are built in the
   container: one argument edited at a time (boundary numbers, empty or reversed sequences,
   an unhashable element, defaults written out and replaced), and every repeated value
   replaced by one shared NaN or by an unhashable box. The original is replayed twice;
   variants on which it gives the same outcome twice are kept. A rewrite must return the
   same outcome on each, or raise the same exception type.
2. **Private access.** A rewrite may not use a private attribute the original function does
   not use, nor `__new__`, `__dict__`, `__wrapped__`, `__code__`, `__globals__`, nor import a
   private name from outside the library.
3. **Real cost.** Without instrumentation, in alternating runs against the version it would
   replace: at most 1.05 of its processor time and at most 1.2 of its peak allocation plus
   64 KiB. Two runs of identical code differ by up to 4 %.

The instruction gain of 3 %, the recorded calls and the library tests remain required.

## Check 1: the rewrites IMPROVE1 accepted, judged again (contaminated, no model)

`experiment/improvement/IMPROVE1/STRICT_REJUDGE_ISOLATED.json`: of the 97 final rewrites,
71 are kept, 12 refused for private access, 8 refused on variants, 6 have no usable variant
(arguments the generator cannot edit). Against the 24 read by hand:

- of the 4 that change behaviour, 3 are refused; the NaN case is missed, because the shared
  value does not occur at the places the generator edits;
- 5 are refused for private access, including one the reading had judged equivalent;
- 1 of the 15 read as equivalent is refused on variants that break an invariant of the
  argument (a number tuple with an inconsistent bit count). The judge refuses some correct
  rewrites.

These rewrites were used to design the judge. The figures describe it; they test nothing.

## Check 2: a new run on the 63 development cases

STRICT_PILOT1 is kept with its fault and counts for nothing: the working tree was switched
during the run, which replaced the harness copied into each container
(`experiment/improvement/STRICT_PILOT1/APPARATUS_FAULT.md`). The runner now stops when the
machinery differs from the frozen plan. STRICT_PILOT2 repeats it, plan committed before the
first request, one arm, USD 0.46.

| | STRICT_PILOT2 |
|---|---|
| functions improved | 37 of 63 |
| improved a second time | 22 |
| longest chain | 5 |
| refused on variants | 8 attempts |
| refused as slower natively | 1 attempt |
| instruction ratio, improved functions (geometric mean) | 0.584 |
| processor-time ratio without instrumentation, same functions | 0.596 |
| improved functions faster in processor time | 37 of 37 |
| accepted rewrites with a higher peak allocation, within the allowance | 21 of 83 |

On the 24 cases the first judge had also seen in development, 17 were improved under the
first judge and 16 under the strict one. Six cases have no usable variant and are judged on
the recorded calls only; 5 of them are among the 37.

The final rewrite of 12 improved functions, the first by SHA-256 of `audit2:` followed by
the case name, was read against the original. No change of behaviour was found. Three of
them inline helper functions of the library and were not verified line by line.

## Correction of an earlier statement

The first report gave a native timing ratio of 0.91 and concluded that instruction counts
overstate what a user would feel. That timing included the canonical encoding of every
result. Measured on the function alone, processor time follows the instruction count:
0.596 against 0.584. The earlier sentence was wrong.

## Limits

- 63 development cases, one run, one writer model. Nothing here is a held-out result.
- Twelve rewrites read is a small sample: finding none wrong does not bound the rate
  tightly, and it was 4 of 24 before.
- The variants are edits of recorded calls. A difference that needs a new shape of input is
  not found, as the NaN case shows. Variants that violate an invariant refuse correct
  rewrites.
- A rewrite that calls around a public mechanism without touching a private attribute is
  not detected.
- Values computed at import time remain outside the measured cost and allocation.

Review: `docs/IP_REVIEWS/PROGRAM_IMPROVEMENT_REVIEW_2026-10-10.md`. 41 focused tests pass.
