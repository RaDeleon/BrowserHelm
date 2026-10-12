# Local Qwen versus cloud DeepSeek vision — 2026-10-11

**Two actual Opus High tasks, both independently verified.** One trial per vision provider; stopped after the agreed pair. OpenRagnar 0.4.12, Claude Code 2.1.296, `claude-opus-5-5` with High effort, same controlled canvas workload and task-specific tool exposure. Memory disabled in isolated settings; production provider/experience choices preserved.

The task was to click the blue circle beneath APPLY exactly once and verify the result. The fixture server independently recorded `blue_circle`, count 1 in both arms. Private keys were accessed through the installed native helper; metadata-only checks verified cloud image input and required JSON/reasoning/output controls before inference. Keychain preparation is outside task timing.

| Measure | Local Qwen3-VL 2B | OpenRouter DeepSeek V4.1 Flash |
| --- | ---: | ---: |
| Independently verified | True | True |
| End-to-end task elapsed | 12.931s | 9.144s |
| Main-agent turns | 5 | 3 |
| Main-agent tool calls | 4 | 2 |
| Vision inference calls | 2 | 1 |
| Summed vision inference latency | 1.775s | 4.048s |
| Main-agent API-equivalent list cost | $0.0834622 | $0.0354928 |
| Vision external API fee | $0 (local compute unpriced) | $0.00002503 (reported) |
| Known API subtotal | $0.0834622 | $0.0355178 |

In this pair, DeepSeek used **29.3% less task time** (1.41× speed ratio) and **57.4% lower known API subtotal**. This subtotal combines Claude API-equivalent list pricing with the cloud provider's reported fee; it is not a Max subscription charge, allowance reduction or fully priced task cost.

## Why cloud completed faster

Local Qwen initially returned `found:false` without clicking. Claude then requested a screenshot, inspected it and sent a more specific target instruction. The second local vision call succeeded; only one click was dispatched. The successful task includes all of that recovery. DeepSeek found the target on its first call, followed by a browser read to verify the confirmation and count.

Cloud inference itself took 4.048s, versus local calls of 1.603s and 0.172s. Its whole task was faster because this run avoided the screenshot fallback and two extra planner turns. The result favors DeepSeek for this one workload; it does not establish that cloud inference is intrinsically faster or generally more accurate.

Local reported 2,388 prompt and 45 completion tokens across both calls. OpenRouter reported 308 prompt and 18 completion tokens and $0.0000250272 cost. Provider token counts use different image encodings/tokenizers and are not directly comparable. Claude usage and cache categories are retained separately in the JSON.

## Boundaries and evidence

One sample per provider is insufficient for reliable median/tail latency or broad rankings. Local ran first; cache/network/model state and main-agent variation are confounds. The same task was submitted, but Claude chose slightly different grounding instructions; this measures the complete agent pipeline, not identical model-prompt inference. Elapsed time includes fresh Claude/MCP startup and independent post-task verification; fixture preparation is outside it. There are no learned repeats, cloud fallbacks, other task families or remote OpenViking measurements in this pair. Local compute/energy costs are unknown. The 10× target remains unproven.

Raw prompts, Claude JSONL, MCP traces, provider usage and isolated SQLite records: ignored `dist/benchmarks/vision-local-cloud-0.4.12/{local,cloud}/`. Consolidated comparison: `dist/benchmarks/vision-local-cloud-0.4.12/comparison.json`. Production settings file hash is unchanged.

This supplements, rather than replaces, the [18-task retest](2026-10-11-six-case-retest-0.4.12.md). No additional paid repeats were launched.
