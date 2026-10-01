# Externally maintained algorithmic environments for V29

These four domains were listed in the prospective V27–V29 publication review
before L6 development. Final native wrappers, seeded faults, all case generators,
oracles, and variant order are authored and committed before the first V29
candidate-policy transfer. No V29 transfer outcome selected or adjusted them.

| Domain | Actual algorithm executed | External maintenance | Primary references |
|---|---|---|---|
| Relational SQL | SQLite in-memory query engine, aggregation, predicates, ordering | SQLite development team | https://www.sqlite.org/about.html ; https://www.sqlite.org/copyright.html |
| Regular expressions | CPython `re` compiled matcher, splitter, substitution engine | CPython core project / PSF | https://docs.python.org/3.12/library/re.html ; https://docs.python.org/3.12/license.html |
| Structured JSON | CPython JSON parser/encoder, decimal conversion and ordered pair hooks | CPython core project / PSF | https://docs.python.org/3.12/library/json.html ; https://docs.python.org/3.12/license.html |
| Binary compression | zlib gzip/raw-deflate decoding and stream finalization | zlib maintainers Jean-loup Gailly / Mark Adler | https://www.zlib.net/ ; https://www.zlib.net/zlib_license.html |

Primary documentation was reviewed on 1 October 2026. The scientific manifest
records detected versions and the actual Python executable's SHA256, which
also identifies the statically linked SQLite, zlib, `_sre`, and `_json` kernels
in the canonical environment. Each receipt records which kernel executed.
These are actual dependency algorithms, not merely four labels on Python code.
The two CPython domains share a maintenance project; there are four algorithmic
domains and three external maintenance groups, not four independent maintainers.

SQLite is public-domain software; zlib uses its zlib licence; Python uses the
PSF licence with incorporated-software notices. No upstream implementation or
documentation code is vendored or relicensed in this repository. Only new,
project-controlled wrappers, fault variants, cases, and evidence are published.
The repository's commercial option does not imply control of those dependencies.

Cases and faults are project-authored with Codex assistance under Anthony Mets'
direction. External maintenance does not make final cases independently authored.
V29 does not supply M085/L10 independent task evidence or replication. Candidate
programs receive inputs, never expected answers. Policy decisions remain in the
separate pure V27 sandbox under unchanged evaluator/budget authority.
