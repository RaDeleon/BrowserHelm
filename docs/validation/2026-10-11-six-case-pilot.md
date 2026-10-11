# Six-case Opus High pilot — 2026-10-11

**18 actual Claude trials; 18 independently verified.** One attempt per case/mode. No repeats were launched after the user selected an 18-task pilot followed by usage review.

Main agent: verified `claude-opus-5-5`, High, Claude Code 2.1.296. Tested engine: packaged 0.4.11; installed GUI is 0.4.10 at measurement time. Task-specific tool exposure and isolated settings/memory: see [protocol](../six-case-benchmark.md). Elapsed times include fresh CLI/MCP startup/shutdown and independent verification; fixture setup is outside the clock. These are not persistent Claude Desktop timings. First suite runs are not guaranteed cold caches; prior preflights and the later Jev arms affect cache/order comparability.

| Use case | Neo directly | Ragnar off | Ragnar on, local vision |
| --- | ---: | ---: | ---: |
| Guarded typography inspection | 5.65s (pass) | 7.68s (pass) | 8.74s (pass) |
| Public multi-step navigation | 15.95s (pass) | 10.83s (pass) | 29.68s (pass) |
| Long-page constrained comparison | 6.43s (pass) | 9.25s (pass) | 11.03s (pass) |
| Canvas visual target | 13.13s (pass) | 16.21s (pass) | 11.54s (pass) |
| Unknown-outcome recovery | 7.97s (pass) | 13.33s (pass) | 12.35s (pass) |
| Fresh-session learned navigation | 16.44s (pass) | 15.91s (pass) | 10.66s (pass) |

## Findings

- Direct Opus was fastest for styles, constrained comparison and unknown-outcome recovery. Ragnar off was fastest for the open-ended public navigation case. Ragnar on was fastest for the canvas and the supplied repeatable-plan case. These are individual pilot outcomes, not reliable default selections.
- Local delegated vision completed in 11.54s versus 13.13s directly: about 1.14× faster in this task. Main-agent reported token volume was 49,926 versus 57,879 (13.7% lower); its API-equivalent list cost was $0.054148 versus $0.0815788. Local inference separately reported 1,182 prompt and 22 completion tokens and 1.727s latency. Local compute/energy was not priced.
- The supplied repeatable plan completed in 10.66s versus 16.44s directly, about 1.54× faster. It was a first acquisition run, not a learned repeat. Jev resolved to `jev-1.13.0`, chose with 0.96 probability, reported 1,223 input and 197 output tokens, and took 0.104s; the executor itself took 0.914s. Claude additionally retrieved the field explanation through grep. Jev API cost was not reported.
- Open-ended navigation on took 29.69s with 11 main-agent turns and four tool errors. Opus supplied `instruction` to inspect/navigate steps, then omitted the required navigation `text`; `neo_help` also did not recognize the executor. A later broad inspection spilled into output recovery. The task eventually passed, but this case never invoked Jev. It therefore measures the enabled executor interface and recovery overhead, not Jev decision quality.
- All recovery trials exercised a synthetic post-dispatch lost response and independently recorded exactly one submission. This does not establish real Neo session-expiry/reconnect behavior.
- Ragnar’s instructions asked Opus to call `openragnar_task` at start and finish, adding two main-agent calls. Those calls remain in this baseline. Move tracking out of the planner loop or make it optional, clarify action-specific schemas and return more focused results before the next optimization comparison.

## Aggregate pilot usage

| Mode | Verified | Sum of six task times | Main-agent turns | Main-agent API-equivalent list cost |
| --- | ---: | ---: | ---: | ---: |
| neo | 6/6 | 65.58s | 24 | $0.419124 |
| off | 6/6 | 73.22s | 31 | $0.514019 |
| on | 6/6 | 84.00s | 35 | $0.567924 |

The 18 main trials reported **$1.501068 API-equivalent list cost** on Max. Actual invoice/allowance impact and total task cost are unknown. Input categories: 156 uncached input, 127,420 cache-created input, 876,618 cached reads, 15,288 output tokens. These categories cannot be translated into subscription usage percentages.

Model preflight ($0.011811) and the strict-oracle harness preflight ($0.1058502) are outside the 18-task workload. Including them, known main-agent API-equivalent list cost is $1.618729. Provider costs remain separate/unknown. On’s aggregate main-agent list cost and time were higher than direct Neo in this pass; token volume alone is not a savings claim.

## Learning and remaining coverage

The separate deterministic control used three fresh gateway connections, all verified: selector calls 1, 1, 0; the third avoided one choice. Times were 0.735s, 0.733s, 0.687s, with five browser dispatches each. A stale failure invalidated eligibility. No Opus/Jev inference was measured in that control; OpenViking upload/recall was disabled. It proves local route reuse and invalidation, not end-to-end learned Opus gains.

Keychain access was verified after the user approved it, and the two outstanding arms completed. Cloud vision, matched learned Opus repeats, varied-order distributions and live session-expiry coverage remain unmeasured. A clean learning comparison requires at least three fresh chats with the same isolated cache; the pilot ran only the first. Stop for usage review before spending more Claude allowance.

## Evidence and next decision

Raw prompts, per-attempt JSONL, MCP traces, usage, provider SQLite events, JSON and CSV remain under ignored `dist/benchmarks/`; consolidated data is `dist/benchmarks/six-case-pilot.json`. Retain `pilot-provider-free`, `pilot-public-control` and `pilot-jev-completion` together. A staged completion after Keychain approval is an order/time confound to address in repeats. Production settings and experience caches were not replaced. Ollama was started for local inference; no model download was needed.

Retained harness preflights: an initial relative MCP-config path failed before inference; a style answer was initially misclassified because `absent` was not accepted as equivalent to `missing`. The corrected pilot oracle accepts both. These are harness setup failures, not browser-mode failures.

**Decision:** keep delegation optional. There is no 10× verified-completion result or general total-cost saving. Target task-marker overhead, executor schema discoverability/help and oversized inspection results next. Preserve this baseline and compare the optimized version only after the user reviews usage and authorizes repeats.
