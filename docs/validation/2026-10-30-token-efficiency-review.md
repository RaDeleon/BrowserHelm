# Token-efficiency review — October 30, 2026

The current objective is 10× fewer client-reported main-agent tokens per independently verified task. Elapsed time and total cost are separate measures. Earlier reports retain their historical speed objective; they are not evidence of this token target.

## Recent evidence

Read-only local telemetry review covered October 25–30, America/Los_Angeles, through the inspection time. These are observed tool requests, not independently verified tasks or a controlled benchmark.

- 198 tool calls: 184 recorded successful and 14 errors (7.1%). Eight errors were HTTP 404 expired-session responses on tab listing. Six were unsuccessful browser executions: four evaluate, one act and one run. Metadata does not identify the underlying scripts/selectors, so specific execution causes remain unknown.
- Separately, 132 initialization requests failed with an upstream connection error. These are startup failures, not 132 failed browser actions. Startup and catalog traffic must stay separate from task success statistics.
- No executor, delegated navigation, visual-action or provider calls were recorded in this window. Enabled delegation was not exercised. No additional task usage/benchmark entries establish current end-to-end token savings or total cost.
- 307 catalog responses delivered 13,235,077 text bytes; tool calls delivered 253,954. These retained traffic totals do not reveal what the main agent actually tokenized, cached or paid for.
- The latest visible GitHub Actions runs were October 11 Pacific time and passed. The October 21 validation report records 243 engine and 30 script checks. There is no recent matched host benchmark in these sources.

Connection availability and expired sessions require operational recovery. Version 0.5.4 already invalidates expired HTTP sessions and renews on a subsequent request without replaying the rejected action. Retained failures alone do not establish a new transport bug; no writes were replayed during this review.

## Source changes

Initialization now gives supported read-only executor plans priority over its generic run instruction. Repeated routing explanations were consolidated while retaining explicit allowed actions, completion checks, partial-progress recovery, DOM-first vision selection, human approvals and no retry of possibly completed writes. It still leaves judgment and recovery with the main agent. This only influences clients using BrowserHelm; direct Neo clients do not pass through this gateway. The user's direct-Neo browser preference and saved provider/settings were not changed.

## Measurement correction and live check

An initial experiment deduplicated the common operating-guide suffix in tool descriptions exposed by the Codex tool registry. That sample appeared 9.66× smaller in description bytes, but a live raw MCP initialization/catalog check showed **zero such suffixes in Neo's raw tools/list response**. The client adds initialization guidance to tool metadata. The apparent reduction was not a gateway improvement. That experiment was removed; no 9.66× claim applies to the final patch.

The local Neo metadata handshake currently succeeds without browser actions or provider inference. Raw catalog: 25 tools, 65,894 serialized bytes, 19,851 description bytes; upstream initialization instructions: 8,995 bytes. The latest unreachable-endpoint event was October 29 at 09:59 Pacific; expired-session and browser-execution errors also occurred October 30. A working handshake does not validate browser execution or eliminate intermittent session errors.

Compare HEAD with the edited source using that raw catalog and isolated, delegation/vision-enabled configuration:

| Measure | HEAD baseline | Edited source |
| --- | ---: | ---: |
| Initialization instruction UTF-8 bytes | 2,974 | 2,479 |
| Serialized transformed catalog bytes | 43,067 | 43,067 |
| Tools available | 32 | 32 |

Initialization instructions are 16.6% smaller. Catalog bytes remain unchanged. This is a byte measurement, not model tokenization, total prompt usage, subscription savings or task performance. The client may repeat initialization guidance in exposed tool descriptions, but its actual token accounting requires a host benchmark. Ignored metadata samples/comparisons remain under dist/; production telemetry/settings are unchanged.

## Validation and remaining work

245 engine tests passed under packaged Python 3.12. Earlier host-Python runs passed, with non-failing unclosed-SQLite ResourceWarnings under Python 3.15; the packaged runtime did not report those warnings. 32 script/privacy tests and five benchmark-oracle tests passed. No new native build, installed-app replacement, version update or release was performed.

Next evidence needed: varied-order matched host trials with the same model/effort, comparable tool exposure, client-reported input/output/cache categories, independent postconditions and complete recovery accounting. Compare direct Neo, BrowserHelm forwarding and executor modes; separate first/warm/learned runs and local/cloud provider costs. Unknown main-agent or provider costs remain unknown. Guidance compaction alone cannot establish 10× task-token or subscription savings. Most savings will require executing and verifying supported plans without returning to the main agent for each browser step, then measuring actual adoption and usage.
