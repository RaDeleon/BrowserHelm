# BrowserHelm 0.5.1: personal macOS execution gateway

A separately named macOS companion for installed BrowserOS Neo. Not a Chromium fork. Claude Desktop and Codex use its stdio MCP executable; Neo performs browser actions. Jev or a chosen model makes bounded navigation decisions inside the gateway.

## Install and connect

1. Open the DMG and drag **BrowserHelm.app** into Applications. This Apple Silicon test build is ad-hoc signed, not notarized. If macOS blocks a downloaded copy, use Privacy & Security → Open Anyway for this app.
2. Start official BrowserOS Neo and its MCP server (default `http://127.0.0.1:9010/mcp`). Open BrowserHelm and click **Check connection**.
3. Open **Settings** (also ⌘,). Select a provider, set its API base URL and exact model ID, enter its key and click **Save settings**. Keys live in macOS Keychain; each provider has a separate key. Blank key fields preserve saved keys; **Remove key** deletes one. No keys enter MCP config or the repo.
4. Click **Test provider**. This sends one synthetic decision request, which can incur provider charges. Local servers need a running model with structured JSON support.
5. In **Connectors**, click **Connect Claude Desktop**. This backs up and merges an `browserhelm` entry, preserving other servers. Quit and reopen Claude Desktop and enable BrowserHelm's tools. Disable duplicate direct Neo tools for a clean comparison in the test chat.

`Connect Claude Desktop` uses the app's current path. Install it in Applications before connecting; repeat if you move it. Existing connected MCP processes keep their settings until reconnected. App GUI can be closed while MCP runs. Keychain may ask you to allow access.

For Claude Code or another client, use **Copy MCP config**. The Codex card offers **Copy Codex MCP config**. Codex example:

```toml
[mcp_servers.browserhelm]
command = "/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm"
args = ["--mcp"]
```

## Providers

- **TypeSafe AI / Jev:** `https://api.typesafe.ai/v1`, `jev-latest`; typed `choice` API. Requires key. Chosen-option probability below 0.70 escalates; this is a threshold, not a correctness guarantee.
- **OpenRouter:** `https://openrouter.ai/api/v1`, enter exact model ID; requires key and a model supporting strict JSON schema. Parameter support is required; unsupported models fail rather than silently removing the schema.
- **Ollama:** `http://127.0.0.1:11434/v1`; use an installed model ID. Local server normally needs no key.
- **LM Studio:** `http://127.0.0.1:1234/v1`; use the server's model ID, start server in Developer tab. Optional authentication key. **Bionic is a separate LM Studio agent app**, not a rename of this API server.
- **Custom OpenAI-compatible:** configurable HTTPS API base URL (HTTP allowed only on loopback), optional key and exact model ID. Structured JSON schema support required.

Cloud providers receive the goal, success phrase, page URL/title, and at most 60 candidate links/labels. They do not receive screenshots or the full page text. Local models can keep the decision request on your Mac; a local server may still route to a cloud model if you configure it that way. No provider is contacted in Gateway-only mode or for regular Neo tools.

Sources: [Jev API](https://docs.typesafe.ai/api), [OpenRouter structured output](https://openrouter.ai/docs/guides/features/structured-outputs), [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility), [LM Studio server](https://lmstudio.ai/docs/developer/core/server), [Bionic](https://lmstudio.ai/docs/bionic).

## Diagnostics and debugging (0.4.1)

Open **Diagnostics** to search errors, warnings and successful requests by tool, category, code or correlation ID. Select a row for its explanation, exception type when available, HTTP/MCP code and suggested next step. **Sessions → Problems only** filters unsuccessful requests; select a request and choose **View request diagnostics**. Sessions initially selects the newest retained session with tool requests, rather than mixing all sessions.

**App builds & connections** shows the current app version/fingerprint, recorded connection versions and negotiated protocols, and running MCP launcher paths. A path differing from Claude's configured launcher is flagged. Older processes cannot report their loaded build: finish their active task, then restart the client to use the configured app and begin recording detailed diagnostics. A matching path alone does not prove an old process loaded the latest app contents.

**Check Neo connection** performs fresh MCP negotiation and tool discovery using saved settings. It does not change browser tabs, save settings or contact the decision provider. Passing this check does not prove an existing client connection is healthy. **Export report** saves the displayed diagnostics snapshot as a local JSON file for review and sharing. The report is never automatically uploaded.

New connections write structured events to private `~/Library/Application Support/BrowserHelm/diagnostics.sqlite` and safe summaries to the client's MCP stderr log. The database retains up to 10,000 events / 14 days; the UI and export display the newest 500 combined records. Logging failures never repeat browser actions. Diagnostics remain independent of token-counter storage. Neo `run` failures expressed as `structuredContent.ok=false` are recognized before compaction, even if the outer MCP envelope lacks `isError`.

For older builds, Diagnostics reads unsuccessful rows from the counter database and error codes from the last 256 KiB of `~/Library/Logs/Claude/mcp-server-browserhelm.log`. These are labeled `legacy-counters` or `claude-mcp-log`; original error details and correlation cannot be recovered. Both sources can describe the same failure, so the error count is a count of displayed diagnostic records, not unique failed tasks or Claude API errors.

Diagnostics stores fixed error classifications and suggested actions, not raw exception messages, tool arguments/results, browser URLs/page contents, API keys or model reasoning. Exported metadata includes client names, app paths with the home directory abbreviated, timing and correlation IDs. Review the file before sharing it. Claude model/quota failures that never reach the local MCP connector are outside this gateway's visibility.

Read-only CLI report:

```sh
/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm --diagnostics
```

## First delegated trial

Ask Claude:

> Use BrowserHelm's browserhelm_navigate. Start at https://docs.typesafe.ai/models, find the API reference describing choice-answer probabilities, and verify the phrase "floats that sum to 1". Use maxSteps 3. Report completion and the provider usage returned by the tool.

Use `dryRun: true` for a single proposed link with no follow-through. A fresh owned tab is still opened for observation. The tool leaves its tab open for inspection, does not touch other tabs, follows only observed same-origin public HTTPS links without query strings, excludes obvious action URLs, performs no forms/buttons and stops on uncertainty/error/budget. Public GET navigation is not a universal guarantee against server side effects. Authenticated workflows, cross-origin research, form filling, and general agent planning remain with Claude/Codex through `run`; they are outside this prototype's autonomous loop.

Success means the requested text is present, verified by code against rendered page text. It is not a claim of a broader task's completion. Model choices are locally validated; generic models have no calibrated probability. Cancellation stops the loop between network/browser steps; an in-flight call may finish. No automatic action retries or automatic fallback to another paid provider.

## Efficiency and limits

The full Neo catalog is enabled by default, with granular read/write tools, `run`, original docs on demand, output retrieval, navigation and status. Existing 0.2 settings migrate to the full catalog. Optional compact mode publishes `run`, session/human-help tools and BrowserHelm helpers; full browser capability is still available through `run`. Native Neo tool annotations and input schemas remain available. Text results default to a ~2,000-token byte estimate and omitted output is recoverable locally. Do not request every omitted chunk if only a small excerpt is needed. Active agents and duplicate server catalogs still affect your Claude usage.

Payload reductions are not measured billed-token savings. Real-provider decision quality and total cost need repeated task benchmarks. Do not assume this reproduces BrowserOS Ultrafast.

## Build

`./script/build_and_run.sh` builds with SwiftPM, stages and opens the app. `--build` stages only; `--verify`, `--debug`, `--logs`, and `--telemetry` are available. The Codex Run button uses this script. Requires Xcode for building, but the staged DMG contains a standalone Python 3.12 stdlib runtime and does not require Xcode/Python to run. For a portable source build, extract an Apple Silicon Python-build-standalone 3.12 install_only archive into `.runtime/python`, or set `BROWSERHELM_RUNTIME_SOURCE` to its extracted python directory. The original developer workstation also supports its existing Codex runtime cache as a fallback. Its license is retained under `Contents/Resources/runtime/lib/python3.12/LICENSE.txt`.

Tests: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s neo-personal -p 'test_*.py'`.

## Validation on this Mac

56 regression tests passed for 0.3.0, including cross-process counter concurrency, private storage, missing usage, negative savings, media handling, full tool access and protocol negotiation. The earlier 0.2.1 packaged MCP initialization and eight-tool catalog worked against Neo 0.0.68. A live Jev 1.13.0 task starting in the TypeSafe Reference section reached the API page and verified the requested phrase: one decision, 1,232 input tokens, 197 output tokens, five internal browser calls, 1.106 seconds, one main-agent MCP call. A broader trial starting from Introduction stopped on uncertainty after two decisions. These are smoke tests, not reliability or Claude plan-savings benchmarks. OpenRouter, Ollama, LM Studio and custom adapters passed request/response unit tests; their real model servers were not exercised.

The earlier gateway installation under official Neo names has been restored to its original transports. BrowserHelm has its own Claude Desktop entry. Disable duplicate direct Neo tools in a comparison chat so their catalogs do not consume context alongside BrowserHelm.

## 0.2.1 connection fix

The initialize request now sends the client-offered MCP version in its HTTP header, then uses the server-negotiated version for subsequent requests. This fixes Claude Desktop offering 2025-11-25 while the gateway previously sent 2025-03-26. Regression coverage includes negotiation to both the offered and older versions.

## Dashboard, connectors and session history

- **Dashboard** has a persistent stats bar for gateway context used/saved, upstream browser calls and provider-reported tokens. It also displays Neo's own all-time/30-day/7-day savings and recent direct Neo sessions. The same-call comparison models the raw forwarded Neo text versus the compacted gateway text; it is not an independently executed end-to-end benchmark. Gateway savings include input overhead, catalogs, instructions and local artifact retrieval. Negative savings are displayed honestly.
- **Connectors** shows Neo availability, local BrowserHelm entries for Claude Desktop/Claude Code/Codex, recorded open MCP client sessions, and other configured MCP server names. Other client connectors are not proxied or metered by BrowserHelm. A configured entry is not proof of an active connection. Cloud connectors are not enumerated from these local files.
- **Sessions** shows each recorded gateway session and the newest 1,000 requests, with duration, outcome, context estimates, savings, provider tokens and upstream calls. Approximate moves use Neo dispatch rows correlated to the request's time interval, including internal SDK steps. Concurrent requests or unavailable Neo audit data leave moves unknown. Neo history also shows the latest 100 sessions, including old gateway sessions predating this update.
- **Enter benchmark** in a selected gateway session accepts user-obtained end-to-end token totals for a matched task: Claude alone, Claude + Neo directly, and Claude + BrowserHelm. The dashboard compares matched Claude-alone/BrowserHelm totals when both exist. These are clearly identified as user-entered totals, not measurements made by MCP.

Token equivalents use text UTF-8 bytes divided by three. They are not a tokenizer or Claude billing/quota totals. Screenshot/audio billing, hidden reasoning, conversation replay, cache rates and plan weighting are unknown to this gateway. Provider-reported tokens remain a separate counter; missing/partial usage is marked unknown. Neo's own savings are its estimates versus a screenshot-first baseline and include gateway traffic, so the dashboard never adds those savings to gateway savings.

Counters are stored in `~/Library/Application Support/BrowserHelm/metrics.sqlite`, with a private directory and database. No API keys, browser tool arguments/results, page contents or MCP transport IDs are persisted there; transport matching uses one-way hashes. Client names and optional session labels are metadata. Retention is 90 days; displayed session/request lists have explicit limits. The GUI polls local read-only Neo APIs and needs no decision-provider key to display statistics. Closing the GUI does not stop MCP clients.

Existing client processes continue using their already-loaded engine until reconnected. Restart Claude Desktop **after any current task finishes** to load 0.4.0 and begin recording its new sessions. Keep Neo running. General read/write workflows use Neo's tools and `run`; `browserhelm_navigate` remains the bounded public-link navigation prototype described above.

The 0.3.0 packaged build was verified against the installed Neo with MCP 2025-11-25 and all 26 tools. A fresh owned example.com tab passed granular DOM writing, snapshot refs, act fill, verified readback and large-output retrieval, then was closed. The GUI displayed live Neo stats, local connector entries and real request counters. Regular browser tools no longer unlock provider keys at startup; provider credentials are fetched through a private native helper only when needed. macOS may ask you to allow Keychain access again after a local ad-hoc rebuild.

## OpenViking experience memory and learning (0.4.2)

Enable **Settings → OpenViking memory → Learn from navigation and request outcomes**. BrowserHelm uses the existing private `~/.openviking/ovcli.conf` URL and API key, with HTTPS or a loopback HTTP endpoint. Change that connection in OpenViking's own configuration. No memory-service credential is copied into app settings, MCP configuration, logs, or this repository. The Memory page and Connectors page show the connection, queued/uploaded outcomes, tasks with recalled hints, and recent outcomes. **Test OpenViking** checks the live service; **Sync pending** sends up to five pending files.

Before `browserhelm_navigate` decisions, it checks the local cache first, then OpenViking's collection at `viking://~/memories/experiences/openragnar` when matching local evidence is absent. Records must match the start URL, goal and requested success phrase. Up to two outcomes fit within a total 1.6 KB hint budget. Successes supply routes; failures supply fixed lessons and attempted links, even when execution failed before any link was followed. Memory never supplies instructions or evidence of current completion.

After **two separate locally recorded, text-verified successes** for the same task within 30 days, the gateway can choose a route link without calling Jev. The link must be among the current observed options and pass a fresh live-page check. The requested text is checked after navigation. Conflicting routes, missing links, changed goals, validation/test records or a later failure fall back to the provider. Two new successes after a route failure are required to restore eligibility. Remote memories alone cannot seed automatic route reuse. Exact local task fingerprints prevent redacted goals from being merged.

Direct tools also record metadata-only MCP outcomes locally. A repeated failure with **identical tool arguments** adds fixed guidance to the returned error for Claude/Codex; a later accepted request retires that warning. HMAC fingerprints match requests without retaining their code/arguments, and those fingerprints/keys are not uploaded in direct-request lessons. Failure and recovery classifications queue for OpenViking; successful low-level calls otherwise stay local. This does not infer the overall task goal, verify business completion, replay writes, rewrite arbitrary JavaScript, or route ordinary `run` calls through Jev.

The **Memory → Learning in use** panel shows route-reuse tasks, provider calls avoided, reused tasks whose text was verified, retained direct requests/failures and repeat-failure hints shown. A recalled hint is not proof of improvement. Calls avoided are counts of decision requests actually skipped, not a token or latency estimate.

After delegated navigation, it records the user-provided goal and success phrase, public routes and labels, provider/model and local text-presence verification. It excludes page bodies, screenshots, form contents, model reasoning and API credentials; common credential and email patterns are redacted. Do not put confidential material in a public-navigation goal. Dry runs are not saved as outcomes. Finding the literal phrase verifies only that postcondition, not the broader user goal. Failed tasks retain their unverified status. This is experience reuse, not Jev model retraining, and improvement requires repeated task benchmarks.

A private `experiences.sqlite` outbox retains 90 days / up to 3,000 uploaded records and up to 500 pending outcomes. Local direct-request history retains 14 days / up to 10,000 records. Background uploads run every 30 seconds while an enabled MCP session is alive; unavailable services never retry browser actions. Retries reuse the same file URI, use cross-process leases, and back off at least 60 seconds. Queued files are pinned to the original endpoint and credential fingerprint; a changed connection cannot receive the old queue. Disabling memory stops new capture, recall, reuse and uploads; retained records are not deleted. Existing MCP processes need reconnection to load this version.

Uploads request OpenViking `vectors_only` processing, avoiding generated reflection and semantic-summary model calls. OpenViking embedding/storage costs remain separate and may still apply. The gateway does not know those billed tokens. The recalled hint text contributes to the decision provider's real usage; no token-savings guarantee is claimed. Service acceptance and eventual indexing are distinct states. A minimal integration-validation record is marked as a test and excluded from decision hints.

API references: [OpenViking retrieval](https://docs.openviking.ai/en/api/06-retrieval), [HTTP API conventions](https://docs.openviking.ai/en/api/01-overview). The locally running service's OpenAPI schema was verified as v0.5.0.

### Remove a client connection

In **Settings → MCP clients** or **Connectors**, choose **Remove from Claude Desktop** or **Remove from Codex** and confirm. Only BrowserHelm’s matching MCP entry is removed, with a private backup; other connectors and app data remain. Finish active browser work first. Restart the client to unload its cached tools. Use Connect to add the entry again.
