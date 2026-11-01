# Routing, startup and extraction review

Audit window: October 29, 2026 00:00 UTC through November 1, 2026 18:30 UTC, before this review's live fixture runs. Sources were read-only local BrowserHelm counters/diagnostics, Claude MCP lifecycle logs and timestamp-filtered Claude Code tool-use records, and Neo's current dispatch database. Only aggregate findings are published; raw logs and browser data remain private.

## Findings

- BrowserHelm recorded 198 tool calls, including 10 errors (5.1%): seven expired-transport failures and three browser-execution failures. It recorded 26 failed initializations separately. There were no decision-provider calls or executor calls in this window.
- BrowserHelm delivered 244,152 text bytes against 318,380 upstream text bytes across those calls. These are payload counters, not client token usage, subscription allowance or matched task savings.
- Neo recorded 1,320 top-level dispatches, including 41 marked errors. Its 466 `run` dispatches included 32 errors. Nested dispatches were excluded; Neo totals include gateway traffic and cannot be added to BrowserHelm totals. Stored arguments/results were redacted, so these records cannot establish the specific causes of those script errors.
- Timestamp-filtered persisted Claude Code history contained 157 browser tool uses, all through direct Neo; 138 were attributed to Opus and 19 to Sonnet. This history excludes non-persisted smoke tests and does not establish Desktop Chat routing.
- Fifteen BrowserHelm `wait` calls took 269 seconds combined. This identifies a review target, not proven wasted time: waits may be required for actual postconditions. The gateway does not remove waits or weaken checks automatically.
- On November 1, Claude's BrowserHelm startup failed while Neo was unavailable, then connected after Neo's service started. The direct Neo bridge also logged failed SSE reconnection attempts. These distinguish upstream availability and transport recovery from model/tool selection; they do not prove that the release caused every observed failure.
- The app's existing Claude connection action configured Desktop only. Claude Code had a separate configuration. Registering a connector does not override agent instructions that select direct Neo; that routing distinction remains visible in the setup documentation.

## Changes and mechanism evidence

1. Separate Claude Code connect/remove controls use the user configuration, keep unrelated connectors/project settings, preserve disabled entries and conflicting commands, and create private backups on writes. Repeat setup of a matching entry is idempotent. Routing preferences are not silently rewritten.
2. Initial MCP connection refusal gets up to six attempts with a ten-second overall deadline and bounded backoff. Only `ECONNREFUSED` is eligible. Timeouts, HTTP errors, accepted handshakes, notifications, and browser actions are not retried. Recovery remains visible as a diagnostic warning. This helps short startup races; it cannot bridge a prolonged browser outage.
3. Executor extraction skips unrelated link enumeration. Inspection returns at most 20 links; navigation retains its 60-link candidate limit. Full body text is read only when destination or completion text requires it. Selector checks and requested text fields still use the current page.
4. Compact initialization guidance now includes explicit profile/window binding recovery, with original upstream documentation available through `neo_help`.

The same synthetic extraction fixture (80 long public links, one heading, one selector completion check) returned **111,373 bytes before and 334 bytes after**. Both versions produced the same heading and successful check in the direct JavaScript oracle. The old response exceeds the executor's 60,000-character observation limit, so the packaged live fixture additionally verifies that the optimized extraction completes, followed by an independent DOM read. This deliberately stresses unrelated link volume; it is not a representative average or an end-to-end main-agent benchmark.

## Scope

Keep planning and judgment with the main agent, batch deterministic browser work, and use provider decisions only where required by a supported delegated step. No decision or vision model settings were changed. No 10× main-agent token saving, subscription reduction, whole-task speedup or total-cost improvement is established by this review. Follow `docs/benchmarks.md` for matched, independently verified task comparisons.
