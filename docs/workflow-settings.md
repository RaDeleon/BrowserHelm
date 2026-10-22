# BrowserHelm workflow settings — 0.5.3

Configured October 15, 2026 at the user's request to keep DeepSeek for vision. These are conservative settings based on current tests, not a demonstrated global optimum.

| Setting | Value | Purpose |
| --- | --- | --- |
| Decision provider | TypeSafe / Jev, pinned `jev-1.13.0` | Keep the tested navigation model stable rather than following an alias. |
| Vision | Enabled, OpenRouter, `deepseek/deepseek-v4.1-flash` | Keep the user's explicitly selected cloud grounder. |
| Bounded delegation | On | Expose supported multi-step plans; the main agent chooses when to use them. |
| Verified learning | On | Preserve the existing configured memory and independently verified reuse. |
| Agent task markers | Off | Avoid two optional planner round trips per task. Manual tracking remains. |
| Compact-only catalog | Off | Retain the full tool surface and original documentation access. Results remain bounded. |
| Result budget | 2,000 approximate tokens | Retain compact results and access to omitted output. This is not billed model usage. |

1. Keep planning, judgment, visual review and recovery with Claude/Codex.
2. Prefer DOM/accessibility refs for ordinary controls. Batch deterministic reads and known actions in `run`; simple inspection needs no Jev or vision call.
3. Use `browserhelm_execute` for useful bounded multi-step plans. Its navigation steps call Jev only when selecting observed links; it can reuse independently verified routes with current-page checks.
4. Use the selected DeepSeek grounder only for a unique visual target DOM refs cannot identify. Resolve duplicate or ambiguous controls before asking for coordinates.
5. Preserve freshness guards, explicit click authorization, cancellation and postconditions. Inspect state after uncertain writes instead of blind retry. No automatic provider switching or mandatory reflection pass is added.

DeepSeek performed well on clear fixture targets but failed ambiguity refusal. The current cloud choice is the user's preference, not evidence that it beats Opus directly across full tasks. Older one-pass pilots were mixed. Follow [benchmarks.md](benchmarks.md) before claiming lower total cost, better accuracy or 10x end-to-end speed.

Local vision remains the initial default for a new configuration; a new user explicitly choosing OpenRouter gets DeepSeek as its model default. Existing saved model selections are never silently replaced. For this installation, only the requested vision/workflow fields and the Jev pin are changed. Credentials, history, experience databases and unrelated settings are preserved.

TypeSafe recommends versioned IDs where thresholds depend on model behavior: [model aliases](https://docs.typesafe.ai/models#aliases). Jev vision stays on its separate pinned experimental 1.14 provider and is not selected by this profile.
