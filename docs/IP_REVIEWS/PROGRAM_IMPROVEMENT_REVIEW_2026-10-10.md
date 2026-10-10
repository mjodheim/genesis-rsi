# Chained improvement of working programs — 10 October 2026

Anthony authorises extending self-revision from repairing defects to proposing improvements
inside a program that already works, in chains where each verified gain is the base of the
next, keeping an external economical model as the writer. Under the standing
PUBLIC_AGPL_COMMERCIAL_OPTION decision, publish a bounded mechanism in which single
functions of existing Python libraries are rewritten by the model, executed only inside a
network-less container, and accepted without any model: identical outcomes to the original
function on calls recorded from the library's own tests, no new failure in those tests, and
fewer executed instructions on recorded calls the writer was never shown.

Review precedes implementation. AI development assistance is as recorded in
`docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`; model-written functions keep their model and
call provenance. No third-party code is copied into the authored mechanism. The libraries
used as cases are upstream software under permissive licences, fetched by pinned version
and archive digest and kept outside this repository; recorded calls, original functions and
rewritten functions are derived from them and are likewise kept outside it. The repository
records case identifiers, digests, instruction counts and the writer's short notes.
Valgrind (GPL-2.0-or-later) is used as an unmodified tool inside the measurement image;
`deploy/program-improvement/marker.c` includes its client-request header, which Valgrind
distributes under a BSD-style licence for that purpose. Software AGPL-3.0-only; prose
follows LICENSE_POLICY.md. Alternative licensing is subject to actually controlled rights.
No patent-first, trade-secret, confidential-third-party or embargo reason identified.
Model-proposed program rewriting checked by tests and a measured cost is a known technique;
no novelty is asserted for it.

No frozen experiment changes and no Defects4J case is involved. Identical outcomes on
recorded calls is not a proof of equivalence, and fewer instructions is one measure of
improvement among others. No general RSI claim follows from any outcome of this work.
