# OpenRagnar

**A native macOS MCP gateway for browser agents, with compact tool output, configurable decision providers, experience memory and usage telemetry.**

OpenRagnar connects an MCP client such as Claude Desktop or Codex to a separately running [BrowserOS Neo](https://github.com/browseros-ai/BrowserOS) instance. Neo executes browser actions. OpenRagnar controls how much browser context comes back and can delegate bounded navigation to Jev or another configured model.

Version **0.4.3** targets Apple Silicon Macs running macOS 14+. This is an experimental portfolio project. Preview DMGs are ad-hoc signed, not notarized. Neo is required and is not bundled.

Download the DMG from [GitHub Releases](https://github.com/RaDeleon/OpenRagnar/releases). While this repository is private, downloads require repository access. Each release includes a SHA-256 checksum and a packaging verification report. Version tags trigger a tested Apple Silicon build and attach the DMG automatically.

## Why build this?

Browser agents can repeatedly send large tool catalogs, page snapshots and duplicate results to the main model. OpenRagnar explores reducing that overhead while preserving access to complete browser output and making the execution path observable.

The engineering work includes MCP negotiation, context compaction and recovery, provider adapters, locally verified navigation, durable memory uploads, concurrent telemetry, macOS Keychain integration and app packaging. Payload reductions are measurable; Claude subscription savings still require matched task benchmarks.

## Capabilities

| Capability | Behavior |
| --- | --- |
| Browser gateway | Preserves Neo read/write tools and `run`; the tested full catalog has 26 tools including gateway helpers. |
| Diagnostics | Searchable error records, HTTP/MCP codes, request correlation, app/connection identity, legacy Claude MCP log projection and local JSON report export. |
| Context control | Shortens documentation, removes recognized duplicates and bounds inline text with recoverable private artifacts. |
| Providers | TypeSafe AI / Jev, OpenRouter, Ollama, LM Studio and custom OpenAI-compatible endpoints. |
| Delegation | Selects observed same-origin public links, rechecks them and verifies a requested phrase locally. |
| Memory | Recalls OpenViking outcomes, reuses locally proven navigation routes and records direct-request failure/recovery lessons. |
| Desktop UI | Dashboard, Connectors, Sessions, Memory and Settings. |
| Telemetry | Request/session counters, provider usage, approximate moves and manually entered matched benchmarks. |

General read/write remains available through Neo's tools. The autonomous loop excludes forms, buttons, query-string URLs and cross-origin navigation, and escalates on uncertainty, errors, cancellation or exhausted budgets.

## Architecture

```mermaid
flowchart LR
    Client[Claude Desktop / Codex / MCP client] -->|stdio MCP| Launcher[Swift launcher]
    Launcher --> Engine[Python gateway]
    Engine -->|loopback HTTP MCP| Neo[BrowserOS Neo]
    Neo --> Pages[Browser pages]
    Engine --> Providers[Jev / OpenRouter / local models]
    Engine --> Memory[Experience adapter]
    Memory --> Viking[OpenViking service]
    Memory --> Outbox[Private SQLite outbox]
    Engine --> Metrics[Private request metrics]
    Engine --> Artifacts[Output artifacts]
    UI[SwiftUI app] -->|CLI snapshots| Metrics
    UI -->|CLI snapshots| Outbox
    UI --> Settings[Settings / macOS Keychain]
```

Each MCP connection launches its own gateway. Closing the GUI does not stop a client's gateway. Main-agent planning and recovery remain with the MCP client; the decision provider handles delegated choices.

## Build and connect

Requirements: an Apple Silicon Mac, macOS 14+, Xcode selected with `xcode-select`, running BrowserOS Neo, and a relocatable Apple Silicon Python **3.12** runtime for packaging. Python unit tests also support 3.9+.

```sh
git clone https://github.com/RaDeleon/OpenRagnar.git
cd OpenRagnar
```

Download an `aarch64-apple-darwin` Python 3.12 `install_only` archive from the official [python-build-standalone releases](https://github.com/astral-sh/python-build-standalone/releases). Extract its `python` directory to `.runtime/python`, retaining its license notices. Alternatively set `OPENRAGNAR_RUNTIME_SOURCE` to that directory. A system or Homebrew Python installation is not a substitute for the relocatable runtime.

```sh
./script/build_and_run.sh --build
./script/package_dmg.sh
open dist/OpenRagnar.app
```

This creates `dist/OpenRagnar-0.4.3-arm64.dmg`. Install the app in Applications before configuring clients. **Connectors → Connect Claude Desktop** backs up and merges a separate `openragnar` entry, preserving other servers. Reconnect the client after changes; old processes retain their loaded engine.

Local builds are ad-hoc signed. The [release guide](docs/releases.md) covers isolated test builds, Developer ID signing, notarization and the feature → staging → main workflow. Public signing remains unverified pending Apple Developer enrollment; setting up these scripts does not make an existing DMG notarized.

Other MCP clients can use:

```json
{
  "mcpServers": {
    "openragnar": {
      "command": "/Applications/OpenRagnar.app/Contents/MacOS/OpenRagnar",
      "args": ["--mcp"]
    }
  }
}
```

Select a provider and save its endpoint, model and key in **Settings**. Keys use macOS Keychain and are fetched lazily; regular browser tools need no decision-provider key. **Test provider** makes a real provider request. Keychain may request approval after an ad-hoc rebuild.

See the [user guide](README-OpenRagnar.md) for provider endpoints, Codex configuration and setup details.

## Try a delegated task

With Neo running and a provider configured, ask your MCP client:

> Use OpenRagnar's openragnar_navigate. Start at https://docs.typesafe.ai/models, find the API reference describing choice-answer probabilities, and verify the phrase "floats that sum to 1". Use maxSteps 3. Report completion and the provider usage returned by the tool.

Success means the phrase was found in rendered page text, not that a broader goal is proven. Selected links must still exist on the current page. There are no automatic browser-action retries or paid-provider fallbacks.

## Dashboard appearance

OpenRagnar takes its name from Ragnar Lothbrok. The native dashboard uses bronze and stone tones with a runic mark. Choose System, Light or Dark from the appearance menu or Settings. Context savings use a ring and comparison bars; the recent-request chart shows the latest 24 retained tool requests. Neo estimates, provider-reported tokens and manually entered Claude comparisons remain separate. Empty and unknown values are labeled instead of presented as measured zeroes.

The **Diagnostics** page adds searchable metadata-only events, failure explanations and next steps, connection/build identity, a fresh Neo connection check and local report export. New connections retain bounded events independently of token counters. Older failed counter rows and Claude MCP log codes remain visible with their limited detail clearly labeled. See the [diagnostics guide](README-OpenRagnar.md#diagnostics-and-debugging-041).

## Experience memory

Enable **Settings → OpenViking memory** to use an existing private `~/.openviking/ovcli.conf` connection. The Memory page shows uploaded/pending outcomes, recalled-hint counts and recent tasks.

- Retrieval is scoped to `viking://~/memories/experiences/openragnar`, with at most two hints and a combined 1.6 KB hint budget per decision.
- Records contain user-provided goals and success phrases, public routes, provider/model and checked outcomes. Page bodies, screenshots, form contents and model reasoning are excluded. Common credential/email patterns are redacted; do not put confidential information in public-navigation goals.
- Offline uploads queue privately, use stable URIs and cross-process leases, and back off without retrying browser actions.
- Two local text-verified runs of the same navigation task can bypass a provider decision, while live link checks and text verification remain. Later route failures revoke eligibility. Remote hints remain advisory and cannot independently seed reuse.
- Direct requests retain metadata-only MCP outcomes and private HMAC fingerprints. Repeated identical failures return fixed guidance; failure/recovery lessons sync to OpenViking. This cannot infer the overall task goal or business completion, and never replays writes or trains model weights.
- The Memory page distinguishes recalled hints from provider calls avoided and reused tasks whose text was verified. Local cache hits avoid a remote retrieval call.

Uploads use vector-only processing. OpenViking embedding/storage costs may apply and are not included in the gateway's provider-token counter.

## Validation and measurement

The 0.4.0 source suite has **67 regression tests**. The local app passed MCP 2025-11-25 negotiation, the 26-tool catalog, writing/filling/readback on an owned public tab, complete omitted-output recovery, and read-only DMG relocation/signature checks. A live memory check saved a verified route and recalled it with an empty local cache; its selector was deterministic and made no model call.

The 0.4.1 suite adds diagnostics coverage for safe error classification, malformed/failed MCP responses, correlation, bounded retention, legacy log projection, missing counter storage and logging failures without action retries. A live constant-return call and controlled JavaScript exception verified that a real browser execution failure appears in Diagnostics and matches its request. The native UI connection check, failure filter, request link and local JSON export were exercised on this Mac.

The 0.4.2 suite has **101 gateway, diagnostics and learning tests**. A controlled live three-run navigation check required selector calls `[1, 1, 0]`: the third run reused a locally proven route and still made five browser calls with live link/text verification. A repeated real Neo error received prior-failure guidance. One explicitly tagged test outcome passed OpenViking upload/readback. This used a deterministic selector, not Jev, and establishes mechanism correctness rather than a model accuracy, speed or quota improvement. See [learning and performance](docs/learning-and-performance.md) for evidence and next-stage architecture.

After Keychain approval, an installed 0.4.0 Jev trial completed one public documentation task with one decision, five browser calls, 1,416 reported input tokens and 197 output tokens. It retrieved two experience hints, verified the requested phrase, and saved the outcome to OpenViking with confirmed readback. An earlier 0.2.1 trial reported 1,232 input tokens and 197 output tokens. These are separate smoke tests, not a matched savings or reliability benchmark. Other adapters have unit coverage; real OpenRouter/local-model servers were not exercised.

The dashboard keeps text token equivalents (UTF-8 bytes divided by three), provider-reported usage, Neo's estimates and manually entered matched benchmarks distinct. Neo's aggregate statistics include gateway traffic and are not added to gateway savings. No Claude quota-savings percentage is claimed: hidden reasoning, full conversation replay, media billing, cache rates and subscription weighting are not observable here.

Run offline tests without browser accounts or paid model calls:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s neo-personal -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s script -p 'test_*.py'
```

The current source suites have 102 gateway/diagnostics/learning tests and 19 release-tooling tests, for 121 tests in total. GitHub Actions runs both Python suites and a separate native Swift compile check. Live checks are opt-in; the [benchmark procedure](docs/benchmarks.md) explains their effects and how to measure matched tasks.

## Source map

| Location | Responsibility |
| --- | --- |
| `mac-app/Sources/OpenRagnar/` | Native UI, launcher, settings and Keychain. |
| `neo-personal/gateway.py` | MCP transport, compaction and output recovery. |
| `neo-personal/openragnar.py` | Delegation, verification, CLI and instrumentation. |
| `neo-personal/decision.py` | Provider adapters. |
| `neo-personal/experience.py` | Retrieval, durable uploads and memory status. |
| `neo-personal/metrics.py` | Counters, connector discovery and Neo statistics. |
| `neo-personal/test_*.py` | Transport, privacy, concurrency and recovery regressions. |
| `script/` | Build, staging, packaging and relocation checks. |

The early installer remains only for rollback regression helpers; its direct CLI is disabled. Use the separate OpenRagnar entry rather than replacing official Neo entries.

## License and acknowledgments

Original OpenRagnar code is [Apache-2.0](LICENSE). Dependencies retain their own licenses; see [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md).

[BrowserOS Neo](https://github.com/browseros-ai/BrowserOS) supplies external browser execution under its own AGPL-3.0 license. [OpenViking](https://github.com/volcengine/OpenViking) supplies external memory. Neither project is bundled in this source repository or app. Provider names identify compatibility and do not imply endorsement.
