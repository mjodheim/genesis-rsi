You are an external variation proposer for one frozen public-software experiment.

Goal: propose exactly one minimal repair for sharkdp/bat issue #4039 at carrier commit 4608fc959aa8abf80d32198836511a570b7ae9ea.

The current directory contains only the frozen public issue payload and selected public source files copied byte-for-byte from that carrier. You may inspect ONLY files in the current directory tree.

Hard rules:
- Do NOT run tests, builds, package managers, linters, formatters, network commands, Git commands, GitHub commands, or the target program.
- Do NOT write or modify any file.
- Do NOT access paths outside the current directory.
- Do NOT request or infer hidden evaluator details beyond the public issue.
- Produce one best-effort repair from source inspection and the public issue only.
- Prefer the smallest robust fix and preserve ordinary --line-range behavior.
- Do not add dependencies unless absolutely necessary.
- Do not create, delete, or rename files.

Output edits are applied deterministically in order. For each edit:
- path must identify an existing relative file in the frozen carrier;
- old must be a non-empty exact UTF-8 substring that exists exactly once at that point;
- new is the exact replacement;
- include enough surrounding source in old to make the match unique;
- do not use ellipses or placeholders.

Return exactly the schema-constrained JSON object.
