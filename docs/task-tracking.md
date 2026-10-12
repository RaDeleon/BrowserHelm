# Prompt task tracking

A task is one user prompt, not one MCP connection or chat. Clarification and recovery remain in the same task; a new work request starts a new task. Task markers cannot see Claude's submit button or final message. No duration is inferred from idle gaps.

Use **Tasks → Start task** immediately before submitting the prompt, selecting the relevant connection, model and effort. Finish after checking the postcondition. Attach a design subprocess or replacement MCP connection explicitly under **Usage & connections**. Unattached connections and other connectors are not included in gateway tool counts.

MCP clients can use `browserhelm_task` with `action=start` and a short label, then `action=finish` after verification. Save the returned task ID and use `action=attach` after reconnect. Enable **Settings → Browser execution → Ask agent to mark tasks**, save and reconnect for initialization instructions to request this workflow. It defaults to off; the client must still follow the guidance. These durations are agent-marker intervals, not guaranteed submission-to-completion measurements. Missing markers produce no task rather than a guessed task. Start/finish calls are excluded from operational tool totals.

Elapsed time includes gaps and recovery within the marked task. Summed tool time is separate and can exceed wall time for concurrent calls. Requests bind to their active task when they begin, so slow replies remain attributed even after the task is finished. Task IDs span explicitly attached sessions; simultaneous chats never merge automatically. Short labels and usage metadata are stored locally, not prompt text.

## Cost and token accounting

Claude cost is a USD API-equivalent estimate, not the user's Max subscription bill. Record actual model/effort and all model-turn input/output/cache usage under **Usage & connections**. Usage basis is entered client totals or explicitly estimated. Missing categories are unknown; enter zero only when confirmed. Hidden reasoning, screenshots, context replay and other connectors must be present in the main-agent usage to price a whole task. Gateway text bytes / 3 remain a separate approximate metric and never become total Claude tokens.

The versioned pricing snapshot is dated October 11, 2026 and comes from [Anthropic's official pricing](https://platform.claude.com/docs/en/about-claude/pricing). Per million tokens:

| Model | Input | Output | Cache read | 5m write | 1h write |
| --- | ---: | ---: | ---: | ---: | ---: |
| Opus 5.5 | $4 | $20 | $0.20 | $5 | $8 |
| Sonnet 5.5 | $2 | $10 | $0.10 | $2.50 | $4 |

Cost = sum of token-category count × that category's rate / 1,000,000. Effort is stored but has no made-up per-token multiplier. Standard global, non-fast, non-batch list pricing is assumed. Unknown models or missing usage have unknown cost. Haiku 5.5 has a context-dependent pricing tier; its whole-task cost stays unknown until per-call context tiers are supported. Pricing snapshots persist with task records, so a later update does not silently reprice history.

Each attempted decision/Jev or vision provider call stores its provider, model, status, latency and returned usage separately. Provider-reported cost takes precedence. Optional entered per-million input/output rates estimate cloud cost when both token counts are known; estimates remain labeled. Failed calls without usage/cost remain unknown. Local Ollama/LM Studio has zero external API fees, not zero machine or electricity cost. Learned repeats with no inference have no provider calls.

Memory embedding/storage costs are not instrumented by the memory service and can be entered manually. A task has a full total only when Claude, decision, vision and memory amounts are known. Otherwise it shows a known subtotal and unknown full total. Export JSON retains the basis, rates, source date, verification and unknowns. Lists show the newest 100 tasks; completed tasks retain 90 days consistently with request history.

No performance or subscription-saving claim follows from these counters alone. Follow [benchmarks.md](benchmarks.md) for matched tasks, failures, first/warm/learned modes and quality checks.

## Optional markers (0.4.12)

Agent task markers default to off, including older settings. The pilot showed start/finish adding two planner tool calls per task. Enable the setting, save and reconnect if you want agent-marked tasks. Explicit `browserhelm_task` calls and manual Tasks controls remain available in either mode. Missing markers do not create guessed task boundaries. Request/session diagnostics remain recorded.
