# Six-case matched benchmark

Compare the same `claude-opus-5-5` model with effort `high`, using fresh Claude Code sessions and the same Neo backend. No skill packs, subagents, normal project instructions or other MCP connectors. This is a controlled Claude Code comparison, not an exact reproduction of Claude Desktop.

| Case | User task | Independent success check | What it tests |
| --- | --- | --- | --- |
| 1. Typography | Inspect exact heading/link styles and an absent element. | Known fixture styles and explicit absence; guarded DOM reads. | Simple tasks where adding inference may waste time; missing-element handling. |
| 2. Public navigation | Models page → API reference, heading and probabilities explanation. | Current rendered API URL, h1 and literal field text. | Main-agent navigation versus bounded Jev choices and extraction. |
| 3. Long-page decision | Cheapest EU/zero-retention/low-latency plan in 120 rows. | Correct eligible plan and price; retain main-model interpretation. | Compaction, output recovery, scoping and lost-context risk. |
| 4. Vision | Click a blue circle drawn beneath APPLY on a canvas, once. | Fixture server records the actual target and exactly one click. | Main-model screenshots versus delegated local/cloud grounding. No canvas-code/pixel shortcuts. |
| 5. Recovery | Submit a disposable fixture once; transport response is lost after dispatch. | Injected fault exercised, correct request ID, completed state and one submission. | Observe-before-retry, duplicate-write prevention and recovery cost. No real account changes. |
| 6. Learning | Repeat the same public route in fresh chats with a stable plan contract. | Current rendered completion plus independent provider/reuse records. | First-run acquisition versus learned repeats. Later stale-route checks test invalidation separately. |

Six families cover these mechanisms; they cannot establish reliability for every website, task, approval flow or model configuration.

## Modes

- **Neo directly:** original Neo descriptions/results through a capture-only stdio bridge.
- **Ragnar off:** compact gateway; delegated tools disabled.
- **Ragnar on:** executor for supported cases, selected vision grounder for case 4, main-model judgment/recovery retained. Direct tools remain for unsupported actions.

Expose the same task-specific granular tools (`run`, `evaluate`, `snapshot`, `screenshot`, `read`, `grep`, `name_session`) in every arm. Ragnar's additional helper/delegation tools are part of its measured context. This deliberately excludes unrelated browser capabilities; report that exposure when extrapolating to default catalogs.

Fixture creation, tool discovery and model startup are measured separately from task completion where practical. The current runner's elapsed time starts immediately before the fresh Claude process and ends after its final answer and independent verification, so includes process/MCP startup. Preserve that boundary for all arms. Fixture preparation is outside it. Verification overhead remains included.

Use rotating run order across repeats. Record every attempt, failure, timeout, escalation, tool call, client-reported input/output/cache usage, API-equivalent list cost and provider usage. Do not equate API-equivalent cost on Max with an invoice or subscription allowance. Missing provider costs/usage are unknown. First page visits are not guaranteed system-wide cold caches; call these first suite runs, not cold-start claims.

Memory uses a dedicated case-6 SQLite cache shared only across its fresh chats; global experiences and settings remain untouched. Background OpenViking upload/recall is disabled in this controlled cache to avoid contaminating production memory. This isolates local verified-route reuse and does not measure remote memory/storage cost or OpenViking retrieval benefit. Record them as outside this workload, not zero for general product cost.

## Running

Build/stage the version under test first. The runner records its actual engine and Claude CLI versions. Run with the bundled Python:

```sh
dist/OpenRagnar.app/Contents/Resources/runtime/bin/python3.12 -B benchmarks/six_cases/run.py --repeats 1
```

Use `--repeats 3` for acquisition and a third learned-repeat sample; all other cases also get three independent attempts per mode. A one-pass pilot cannot pick a reliable winner. Use `--vision local` (default) for the installed Ollama `qwen3-vl:2b-instruct`; `--vision saved` uses the user's explicit saved choice in isolated configuration. Supplement cloud vision only after verifying its key and spending limit.

`--cases` and `--modes` accept comma-separated identifiers; `--timeout` bounds each attempt and `--api-equivalent-cap` bounds aggregate reported main-model list-cost estimates, not subscription quota or unknown provider bills. Never retry an actual browser write automatically after a timeout.

Raw results, prompts, traces, usage and SQLite evidence are saved under ignored `dist/benchmarks/`; retain failed preflights separately. Publish only sanitized summaries. Stop at the agreed pilot budget and review usage before enlarging the study. Choose a winner per workload only when quality and total cost support it; missing costs or one sample mean the decision remains provisional.
