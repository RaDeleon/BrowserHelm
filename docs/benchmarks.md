# Testing and benchmarking

The reproducible [six-case Opus High suite](six-case-benchmark.md) compares direct Neo, compact forwarding and optional delegation. Its [first pilot report](validation/2026-10-11-six-case-pilot.md) retains the blocked arms and separates controlled learning evidence from main-agent task results.

The [0.4.12 retest](validation/2026-10-11-six-case-retest-0.4.12.md) keeps the next 18 attempts separate: fewer marker/argument round trips, with workload-specific speed/cost results and one retained independent-verifier discrepancy.

## Offline regressions

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s neo-personal -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s script -p 'test_*.py'
```

Tests use synthetic responses, temporary files and local HTTP servers. No browser account, memory service or provider key is needed. Credential strings in tests are fixtures.

## Native compile

On macOS with Xcode selected:

```sh
cd mac-app
swift build -c release --disable-sandbox
```

Compilation alone does not verify packaging, signing, Keychain or browser behavior. Supply a relocatable runtime and build the app as described in the root README.

## Optional live checks

Run from the root after building, with Neo running. Checks use your saved settings and add labeled validation sessions to local telemetry. Generated reports remain ignored local files.

| Command | Requirements and effects |
| --- | --- |
| `python3 neo-personal/check_claude_handshake.py` | Packaged MCP initialization and catalog. No decision-provider call. |
| `python3 neo-personal/live_delegation_modes.py` | Packaged gateway with isolated settings, owned synthetic DOM and no inference. Checks direct reads with delegation off, executor reads with it on, and cached-call rejection after opt-out. Closes its owned tabs. |
| `python3 neo-personal/live_full_access.py` | Opens an owned example.com tab, creates/fills/reads test DOM, checks output recovery and closes that tab. No decision-provider call. |
| `python3 neo-personal/live_browserhelm.py` | Defaults to `/Applications/BrowserHelm.app`, matching the installed Keychain identity. Override with `--app dist/BrowserHelm.app`. Public documentation navigation using your configured provider/key/server. Can incur provider charges; returns failure if completion is unverified. Leaves the owned tab for inspection. |
| `python3 neo-personal/live_memory.py` | Deterministic public-documentation route, verified text, upload and remote recall with an empty local cache. No decision-model call; memory embedding costs may apply. Closes its owned tab. |
| `python3 neo-personal/live_learning.py` | Three public-documentation navigation runs in a temporary cache. Verifies the third skips a decision request while checking the current link/text. Also exercises repeat-failure guidance with two controlled Neo errors. No decision-model call; closes its owned tabs. |
| `python3 neo-personal/live_learning.py --remote` | Adds one explicitly test-tagged OpenViking outcome upload/readback, excluded from production hints/reuse. Memory embedding/storage costs may apply. |
| `python3 script/verify_dmg.py` | Read-only DMG mount, signature/license checks and bundled SSL/SQLite imports. Offline; no provider key or Neo needed. |
| `python3 script/verify_dmg.py --live` | Adds relocated MCP and public HTTPS checks. Requires Neo; no decision-provider call. |

A failed check can leave an owned tab open. Inspect before retrying. Telemetry or upload failures do not justify repeating browser actions.

## Matched task procedure

Choose a public task with an independently checked postcondition. Record the task, website, models, settings and output budgets. Run each mode from equivalent initial conditions:

1. Main agent alone with its usual browser mechanism.
2. Main agent with Neo directly.
3. Main agent with BrowserHelm and the same Neo backend.

Use fresh chats and equivalent tool exposure. Repeat with varied order, accounting for warm caches, page changes and history. Capture completion, failures/escalations, latency, client-reported main-agent usage, gateway text bytes and decision-provider usage. Keep failed runs in the results.

Enter client-reported end-to-end totals in **Sessions → Enter benchmark**. Those are manual inputs, not usage inferred by MCP. Publish the protocol and sample size with savings claims.

## Interpretation

- Raw versus compacted gateway output compares the same calls, not independent task runs.
- UTF-8 bytes divided by three is a text token equivalent, not tokenization or billing.
- Hidden reasoning, media billing, full conversation replay, cache treatment and plan weighting are not observed.
- Provider usage, main-agent usage and memory embedding costs are separate. Missing usage is unknown, not zero.
- Neo's aggregate cockpit statistics include gateway traffic; do not add them to gateway savings.
- Phrase presence verifies that postcondition, not every part of a broader goal.
- Memory is advisory. Benchmark with and without memory; hints can add tokens even when they save steps.

Current evidence establishes transport, read/write forwarding, recovery and memory integration. It does not establish a Claude quota-savings percentage or production-wide task reliability.

## Delegation on/off comparison

Use the exact same main-agent model and effort setting in every run, including the user's selected Opus model on High. Keep complex interpretation and recovery with that model; compare whether handing routine browser work to Ragnar improves the whole task. Do not infer model rankings or a quality advantage from smaller payloads.

Test these modes in fresh chats with equivalent Neo state and the same granular tool exposure:

| Mode | Configuration | Purpose |
| --- | --- | --- |
| Neo directly | Disable the Ragnar connector; expose Neo only. | Baseline for total Ragnar benefit. |
| Ragnar, delegation off | Disable **Settings → Browser execution → Delegate routine browser steps**; save and reconnect. Expose Ragnar only. | Isolate compact forwarding while the main agent controls browser steps. |
| Ragnar, delegation on | Enable the switch; save and reconnect. Expose Ragnar only. Use the same decision provider and local vision settings throughout. | Measure bounded delegation, including its model/recovery overhead. |
| Ragnar, cloud vision | Separate explicitly selected cloud-vision trial. | Measure extra cost and task benefit separately from local mode. |

Keep compact-catalog settings identical. Never expose both Neo and Ragnar in the same comparison chat. A model ignoring an available executor is a recorded result, not a delegated success. Separate memory-off first runs, warm runs without learning and learned repeats; preserve production experience memory and use isolated benchmark caches when a clean learning baseline is needed.

Start with three public read-only workloads:

1. **Navigation/extraction:** From `https://docs.typesafe.ai/models`, find the API reference, report the first heading and the explanation of the probabilities field. Independently verify the destination, heading and quoted field text.
2. **DOM inspection:** On the same page, report the first heading's computed font family, size, weight and color; report the first navigation link's style. Report a deliberately absent selector (`[data-browserhelm-benchmark-missing]`) as missing. Independently check against current DOM values. This tests whether the main agent avoids unnecessary decision/vision inference.
3. **Judgment-heavy reading:** Compare two documented API/model choices and explain which fits a specified use case, with links to supporting text. Check the interpretation independently. Ragnar can gather evidence; the main model must make the recommendation. This tests whether delegation loses context or adds recovery work.

Use at least five varied-order attempts per workload/mode for an exploratory result; ten or more are preferable before broader claims. Run equivalent first-state conditions and include every failure, recovery, escalation and human wait. Report success/accuracy first, followed by median/tail verified-completion time, main-agent turns and reported usage, decision/vision usage, memory costs and total cost per successful task. If Claude Desktop does not expose exact usage, mark it unknown; do not translate gateway bytes into subscription savings.

Choose delegation for workloads where accuracy is preserved and measured total time/cost improve. Keep it optional where evidence is mixed or missing. Controlled fixtures and provider latency alone cannot decide whether Ragnar improves the user's Opus workflow.

## Per-prompt measurements

Use explicit [task tracking](task-tracking.md) boundaries rather than treating an MCP session as a prompt. Report boundary and verification sources. Claude API-equivalent estimates, provider-reported costs and pricing estimates remain separate from subscription billing.
