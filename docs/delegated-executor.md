# Delegated browser execution (0.4.10)

`openragnar_execute` runs one explicit read-only plan without returning to the main agent between each step. It does not turn an arbitrary goal into an unrestricted autonomous task.

## Claude/Codex instructions

> When OpenRagnar is available, prefer `openragnar_execute` for supported multi-step read-only browser work. Supply a bounded plan, explicit allowed actions and current-page text/selector completion checks. Use direct tools for unsupported work or a simple one-off action. Read partial results before recovery; do not repeat actions blindly. Use vision only when DOM information is insufficient. Preserve user approvals.

The gateway supplies this guidance during MCP initialization and in the tool catalog. Reconnect after updating. Instructions influence tool choice; they do not guarantee delegation.

## Enable or disable delegation (0.4.11)

In **Settings → Browser execution**, change **Delegate routine browser steps**, save, then reconnect Claude/Codex to refresh its catalog. Existing configurations keep delegation enabled. This preserves the previous behavior; it does not mean delegation has won a quality/speed comparison.

- **On:** the executor, delegated navigation and configured visual-action tool are available. The main agent still chooses whether to delegate and retains complex reasoning and recovery.
- **Off:** those three tools are hidden; even a cached call is rejected before browser/provider execution. Direct Neo tools, compact responses, output recovery and task tracking remain available. Turning this off does not cancel a plan already running. Provider settings and credentials are retained for later use.

This compares who performs the browser steps through Ragnar. To measure Ragnar's total benefit, also test the same client with Neo directly. See the [matched delegation comparison](benchmarks.md#delegation-onoff-comparison).

## Example: typography inspection

```json
{
  "page": 153,
  "goal": "Inspect page typography and navigation",
  "allowedActions": ["inspect", "extract"],
  "steps": [
    {"action": "inspect"},
    {"action": "extract", "fields": [
      {"name": "heading", "selector": "h1", "read": "style"},
      {"name": "navigation", "selector": "nav a", "read": "style"}
    ]}
  ],
  "completion": {"selectorsPresent": ["h1"]},
  "maxSeconds": 45,
  "maxBrowserCalls": 20
}
```

Use the actual page ID. Alternatively pass a public HTTPS `startUrl` to open an owned tab. Consecutive inspections/extractions and their completion evidence share one current-page read. Absent or invalid extraction selectors return `missing`/`invalid_selector` with null values. To require the navigation element above, include `nav a` in `selectorsPresent`.

## Supported steps

| Action | Behavior |
| --- | --- |
| `inspect` | Bounded visible headings and links. Optional `includeStyles: true` adds heading/body styles. |
| `extract` | Up to 12 named CSS selectors: text (1,200 characters), computed style or href. Text reports `truncated`, `totalChars`, `offset`; optional `contains` returns an excerpt around a literal phrase, or `missing_text`. |
| `navigate` | Expected `text` and 1–3 `maxHops`. Decision provider chooses among observed visible public same-origin links; URL/href rechecked before navigation. No query strings, downloads or known action URLs. |
| `scroll` | Explicit nonzero scroll of at most 2,000 pixels. |
| `locate` | Explicit `instruction` invokes the selected vision provider for a point proposal. No click; coordinate accuracy remains unverified. |

Limits: eight steps, 2–40 browser dispatches, 5–90 seconds. Network timeouts use the remaining budget; cancellation/budgets are checked before new dispatches. An in-flight action may already have changed state, so timeouts never trigger automatic replay. Missing keys, uncertainty, stale links and failed checks return partial progress and escalation. Owned tabs remain open for inspection.

No forms, button presses, submission, downloads, purchases or caller/model-generated JavaScript. Direct tools remain available for separately authorized operations. Jev receives goal, URL, expected text and link labels only when a navigation choice needs inference. Explicit visual locate sends a screenshot to the selected provider; local remains the default and there is no cloud fallback.

## Verification and learning

`verified: true` means all supplied current-page text/visible-selector checks passed after the plan, not that the broader user goal is complete. Missing optional fields and unverified visual proposals remain explicit.

Navigation reuse is keyed by the whole plan, allowed actions and checks. Two matching locally verified successes enable route reuse; live-link and final checks remain. Failed/stale attempts invalidate support and changed plans do not inherit shortcuts. The existing background OpenViking sync receives bounded outcomes. This learns navigation routes, not model weights or automatically improved inspection plans.

Decision/vision calls feed task-ledger usage events. Host usage still requires client-reported data; missing usage and memory costs remain unknown. Track the overall user prompt with `openragnar_task`, not each internal step.

## Validation

Run `python3 -m unittest discover -s neo-personal -p 'test_executor.py'` and optional `python3 neo-personal/live_executor.py`. The live check uses owned fixture tabs, guarded extraction, missing completion checks and public TypeSafe navigation with a deterministic selector. No paid inference or fixture memory upload. Report: ignored `dist/executor-validation.json`.

A warm fixture compared two individual Neo reads with one batched executor read: 6/6 verified completions each, two dispatches versus one. Neo clients can also batch reads directly. This proves batching, not superiority over optimally batched Neo, Claude token savings or general 10× speed. Follow [benchmarks](benchmarks.md).

## Pilot fixes (0.4.12)

Each step now advertises its own required fields. `navigate` requires literal destination `text`; only `locate` accepts `instruction`. Invalid arguments fail before dispatch. Use `neo_help` with `topic: "openragnar_execute"` for complete examples, available before catalog discovery. Task markers are opt-in; see [task tracking](task-tracking.md). These changes address pilot overhead; another matched host benchmark is needed to measure total speed/cost improvement.
