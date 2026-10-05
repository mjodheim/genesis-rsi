# V50 exact codec-word continuation model

Prospective proof specification, 5 October 2026. Native public-fixture validation
checks short implementations of the premises; it cannot empirically prove their
unbounded mathematical idealization. V49's finite-hash and native-work conclusions
remain unchanged.

## Carrier and encoders

Let X contain nonempty finite Unicode-scalar strings encodable as UTF-8. Define
four total **specification-level** encoders:

1. H: uppercase hexadecimal of UTF-8 bytes;
2. R: consecutive character runs as positive decimal count, colon, decimal Unicode
   ordinal and semicolon, concatenated;
3. J: an ASCII JSON string encoding;
4. G: canonical gzip of UTF-8 bytes, followed by base64.

Their inverses are respectively hex/UTF-8 decoding, run expansion, JSON string
decoding and gzip/base64/UTF-8 decoding. Each inverse reconstructs the original
nonempty string on its encoder's image; every encoder is therefore injective.

Their images are disjoint. H is nonempty even-length uppercase hexadecimal. R
contains a colon and semicolon, and begins with a digit. J begins with a quote.
G begins with H4sI, determined by gzip's magic/method bytes; its initial H belongs
to neither the hex alphabet, the run prefix nor the JSON-string prefix. These
properties classify the outermost encoder without consulting the source word.

The base fixture strings begin with a seedling Unicode character, outside all
four images. No arbitrary semantic tag is appended to output: distinguishability
comes from the real encoding formats.

## Exact word identity

For a finite operator word w, E_w applies its encoders in word order. Suppose
E_w(x)=E_v(x) for a base x outside the four images. If one word is empty and the
other is nonempty, the equality contradicts image exclusion. Otherwise disjoint
images identify identical last operators. Applying their common left inverse
reduces the equality to the shorter words. Induction gives w=v.

Thus every distinct finite word has a distinct behavior at this base input, and
indeed a distinct function on X. Repeated output classification and inverse decoding
recover the exact entire word and original base. The semantic identity is that
variable-length word, **not a finite hash or syntactic identity without a semantic
argument**. Provenance hashes remain useful but play no role in this proof.

## Archive induction and rate unit

Assume four distinct equal-length whole programs have succeeded and survive.
Their sixteen pairwise compositions are distinct and contain any next target
chosen from this closed composition curriculum. External exact-output feedback
at the discriminating base equals word equality by the preceding proof.
Enumerating the products finds the target within sixteen queries. Identity,
up to four screens and exact confirmation give at most 22 calls, below a 26-call
external cap. A target body is then a newly available construction tool.

If every level has four such targets, each repeated twice, complete library
retention lets the argument repeat at arbitrary symbolic depth. The first task
at each larger level has a strictly longer word than every earlier-level proposal;
injectivity makes its solved behavior new even relative to earlier failed
observations. There is therefore at least one conservative discovery per eight-task
level and at most 8*26 charged calls, giving the conditional bound **1/208**.
This is an induction under explicit premises, not extrapolation from 341 fixtures.

## Physical and generality boundary

The proof concerns unbounded codec specifications. SQLite, Python and zlib have
finite operand/representation limits; the inherited worker additionally has fixed
CPU, memory and time limits. More RAM alone does not remove every native API limit.
The native implementation is validated only on the declared bounded public words.
No native infinite execution follows from the mathematical construction.

Even in the ideal model, every length-n body performs n encoder steps per context.
If an eight-task level uses this four-context instrument and paid repetition for
every solve, it needs at least 8*2*4*n=64n codec visits. At most four new target
behaviors then imply discovery/visits at most **1/(16n)**. Output byte work may grow
faster; final transport compression also costs work. A nonzero charged-query bound
is not a nonzero native-work or wall-clock floor.

The fixed codec vocabulary and closed host curriculum remain substantial limits.
This proof selects no new recursive policy, spends no fresh archive population,
and establishes neither general L9 nor independent L10. A qualifying successor
needs a prospective archive assay, matched causal controls, broader task diversity
and a work/representation model consistent with its external governance.
