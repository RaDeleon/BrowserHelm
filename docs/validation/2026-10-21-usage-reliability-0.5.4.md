# Usage reliability update — 0.5.4 build 22

Validated October 21, 2026 (America/Los_Angeles).

## Changes

- An HTTP 404/410 on an established Neo session invalidates that session. A subsequent request performs serialized initialization without the stale session header, negotiates the returned protocol, and sends the initialized notification. Each recovery handshake operation is bounded to ten seconds or the shorter executor deadline. The rejected action is never replayed. Failed recovery blocks dispatch of the waiting action; timeouts do not trigger replay.
- Overview reports task-linked call coverage and usage by direct, delegated, vision, and local helper paths. Path counts exclude explicitly test/validation-named clients, but do not claim all remaining clients are production-only. Existing unknown usage and cost remain unknown. A Track a task action opens the existing task controls without enabling extra agent marker calls.
- Validation-mode direct outcomes are retained with a test label but cannot seed production failure signatures. Navigation capture honors validation mode. Legacy records are labeled on display without rewriting stored history; provider-labeled validation navigation remains excluded from route reuse.
- SQLite transaction contexts in metrics, diagnostics, experience memory, and task tracking explicitly close connections.
- Build-only mode no longer stops the running GUI.

## Verification

- 243 engine tests passed with the installed Python 3.12 runtime, including seven new reliability/coverage/transaction regressions.
- 30 script/release/native settings tests passed.
- Native release build passed. Packaging rejected an unrelated certificate file in the cached fallback runtime; packaging then succeeded using the existing installed runtime explicitly via BROWSERHELM_RUNTIME_SOURCE.
- Staged and installed native MCP initialization returned 0.5.4, negotiated protocol 2025-11-25, and listed 29 tools. No browser action or paid provider call was used.
- Installed dashboard JSON includes measurement coverage and the retained tasks.
- Installed strict deep code-signature verification passed. This remains a local ad-hoc signed build, not a notarized public release.
- Installation found zero running tracked tasks and more than four hours since the last recorded browser tool call. Idle native launchers were stopped before replacement. Settings bytes and database table row counts were preserved; the prior app and private database/settings backups were retained under BrowserHelm Update Backups.

## Remaining verification

The existing Codex connector returned Transport closed after replacement. A fresh native MCP session passed, but existing Claude/Codex sessions still require a client-side reconnect before the update is fully active there. Native computer-use automation returned "Sky Computer Use native pipe closed before response", so rendered UI inspection and UI-driven client reconnection were unavailable.

No matched end-to-end benchmark ran. These checks establish the mechanisms and regressions, not a 10x speedup or lower total task cost. Existing vision-provider work and user settings were preserved.
