# L10-C public external transfer: bat #4039

**Result:** PASS under the frozen L10-C public external-transfer protocol.

- Carrier: `sharkdp/bat@4608fc959aa8abf80d32198836511a570b7ae9ea`
- Public issue: #4039, “Capacity overflow panic with huge negative --line-range on macOS”
- Baseline: reproduced `capacity overflow` panic with return code 101.
- Candidate proposer: Claude Code 2.1.289 / `claude-sonnet-5-5`, one invocation, read/search-only tools, no evaluator or baseline output visible.
- Candidate transport: deterministic exact structured edits; 2/2 substitutions matched exactly once.
- Candidate tree: `ff26b2985facb5c97468801295c8bf61a95ff939`.
- Frozen objective after candidate: PASS; huge negative range returned 0 with no panic.
- Frozen control `:-2`: PASS.
- Frozen Rust regression: 147 passed, 0 failed.

## Claim boundary

This is the first successful **public external-transfer** carrier in the L10 pilot. It is materially stronger than L9 because the task originated in a live independently maintained external repository and the frozen upstream baseline demonstrably failed.

It does **not** set strict `l10_independent_passed=true`. Selection, evaluator construction and adjudication are still controlled by the Genesis project/assistant. Strict L10 remains reserved for independently governed reproduction and adversarial audit.
