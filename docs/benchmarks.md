# Testing and benchmarking

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
| `python3 neo-personal/live_full_access.py` | Opens an owned example.com tab, creates/fills/reads test DOM, checks output recovery and closes that tab. No decision-provider call. |
| `python3 neo-personal/live_openragnar.py` | Defaults to `/Applications/OpenRagnar.app`, matching the installed Keychain identity. Override with `--app dist/OpenRagnar.app`. Public documentation navigation using your configured provider/key/server. Can incur provider charges; returns failure if completion is unverified. Leaves the owned tab for inspection. |
| `python3 neo-personal/live_memory.py` | Deterministic public-documentation route, verified text, upload and remote recall with an empty local cache. No decision-model call; memory embedding costs may apply. Closes its owned tab. |
| `python3 script/verify_dmg.py` | Read-only DMG mount, signature/license checks and bundled SSL/SQLite imports. Offline; no provider key or Neo needed. |
| `python3 script/verify_dmg.py --live` | Adds relocated MCP and public HTTPS checks. Requires Neo; no decision-provider call. |

A failed check can leave an owned tab open. Inspect before retrying. Telemetry or upload failures do not justify repeating browser actions.

## Matched task procedure

Choose a public task with an independently checked postcondition. Record the task, website, models, settings and output budgets. Run each mode from equivalent initial conditions:

1. Main agent alone with its usual browser mechanism.
2. Main agent with Neo directly.
3. Main agent with OpenRagnar and the same Neo backend.

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
