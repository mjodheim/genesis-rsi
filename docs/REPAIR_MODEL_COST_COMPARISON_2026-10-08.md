# Development model cost comparison — 8 October 2026

Three exposed development cases: Codec-15, Csv-16 and Collections-24. This is a small descriptive comparison, not evidence of general model superiority or general RSI.

Each model had up to two candidate validations per case, four proposal rounds, four API requests per round and 4,096 output tokens per response. GLM and DeepSeek used reasoning effort `low`; Qwen3 Coder is the full model, not Coder Next. Conservative reservation guards were identical: $0.03 per request / $0.06 per proposal round, with provider tariff ceilings of $0.35 input / $1.30 output per million tokens.

| Model | Suite passes | Actual API spend | Input tokens | Output tokens (including reasoning) | Reasoning subset | Cost / suite pass |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3 Coder | 0/3 | $0.012620 | 67730 | 1450 | 0 | undefined (zero passes) |
| GLM-5.3 Flash | 1/3 | $0.005049 | 48854 | 6343 | 4439 | $0.005049 |
| DeepSeek V4.1 Flash | 0/3 | $0.013393 | 42946 | 10460 | 10128 | undefined (zero passes) |
| DeepSeek V4 Pro | 0/3 | $0.007127 | 48167 | 7273 | 6756 | undefined (zero passes) |

All attempted calls, including unsuccessful and truncated responses, are counted. There are no unknown call costs in this campaign. Reasoning tokens are already part of output tokens and are not added twice. Total API spend: $0.038189. Historical pilots and infrastructure costs are excluded.

GLM passed Csv-16. Qwen was stopped by conservative budget guards in all three cases, and DeepSeek variants also encountered output truncation and/or budget limits. These observations compare the current agent configuration under its limits; they do not establish the models’ maximum capability. API/tool failures and incomplete trials remain visible in the evidence.

The original protocols were not changed after results. Cases not started because an earlier model error halted a trial were run under separate protocols. No started case was retried. DeepSeek V4 Pro was added after the user requested DeepSeek models, so its inclusion was not part of the initial three-model plan.

Evidence and exact totals: [sealed comparison record](../experiment/bench/DEV_MODEL_COST_COMPARISON1_RESULT.json). Original aborted trials remain unsealed; the comparison record explicitly retains their aborted events and completed partial outcomes. The evidence snapshot contains usage/cost records and outcome records, not API credentials.

Accounting tool: `scripts/audit_repair_model_costs.py`. Three accounting tests passed; 52 focused OpenRouter/benchmark/sandbox tests passed.
