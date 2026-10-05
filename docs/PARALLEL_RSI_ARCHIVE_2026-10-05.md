# Preserve both RSI research lines — 5 October 2026

The native line and the remote development line both used names V33–V35 for
different apparatus. Their frozen paths and source hashes cannot share one active
Python package. Neither line's original experiment may be rewritten to resolve
that collision.

The complete parallel tree at `f9929b31` is therefore retained as the optional
Git submodule `archives/parallel-rsi-v48`, pinned to its original commit, while its
history is included as a merge parent. This is archival integration, not an
activation, rerun or reclassification of its experiments. The root native V35–V38
and V49 source bodies and original raw evidence remain unchanged. No parallel
workflow is copied into the active root CI directory.

The snapshot contains original V33–V48 apparatus, public raw development records,
the complete negative V42 prefix and V43–V47 diagnoses, including the consumed
positive V47 pilot. V48's prospective machinery is preserved; this integration
does not spend its fresh population or claim its execution. The parallel tag
`provenance/remote-v48-development-20261005` also retains the exact commit.

Default checkout/tests do not initialize this submodule. To inspect the preserved
line, first verify the pinned commit, then use:

```sh
git submodule update --init archives/parallel-rsi-v48
git -C archives/parallel-rsi-v48 rev-parse HEAD
```

The returned commit must equal the pinned gitlink. Read that snapshot's own
AGENTS.md, protocols, source manifests and runtime requirements before testing it.
Its standalone package names and repository-root resolution then match its
original files. Its prospective V48 protocol specifies Python 3.11.16; the root
native line uses a separately recorded runtime. Do not combine their environments,
evidence directories or success claims. No independent replication or L9 closure
is inferred from preserving either tree.
