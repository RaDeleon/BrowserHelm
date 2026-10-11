# Six-case optimization retest — OpenRagnar 0.4.12

**17/18 independently verified attempts.** One attempt per case/mode; no additional repeats.

Same Opus 5.5 High model, Claude Code 2.1.296, Neo backend and task-specific tool exposure as the original pilot. Isolated fixtures/settings, local Ollama Qwen3-VL 2B for delegated vision, Jev for inferred navigation. Production memory and provider choices are preserved. The runner captures actual versions. Task markers default off in the optimized app.

| Case | Neo now | Ragnar off now | Ragnar on now | Ragnar on before |
| --- | ---: | ---: | ---: | ---: |
| Guarded typography inspection | 6.34s (pass) | 5.08s (pass) | 5.32s (pass) | 8.74s |
| Public multi-step navigation | 20.28s (fail) | 9.43s (pass) | 15.97s (pass) | 29.68s |
| Long-page constrained comparison | 8.63s (pass) | 9.62s (pass) | 6.83s (pass) | 11.03s |
| Canvas visual target | 9.14s (pass) | 11.67s (pass) | 9.64s (pass) | 11.54s |
| Unknown-outcome recovery | 9.37s (pass) | 8.37s (pass) | 7.36s (pass) | 12.35s |
| Fresh-session learned navigation | 17.50s (pass) | 8.89s (pass) | 8.14s (pass) | 10.66s |

## Observed totals

Summed times describe these six different tasks; they are not a latency distribution for a repeated workload. All attempts, including failures and recovery, remain included.

| Mode | Verified | Sum of task times | Turns | Tool calls | Marker calls | Tool errors | Main-agent API-equivalent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| neo | 5/6 | 71.25s | 24 | 18 | 0 | 1 | $0.448888 |
| off | 6/6 | 53.05s | 19 | 13 | 0 | 1 | $0.399326 |
| on | 6/6 | 53.27s | 19 | 13 | 0 | 1 | $0.431377 |

Known main-agent list-price API-equivalent: **$1.279590**. This is client-reported usage priced by Claude, not a Max subscription charge or measured allowance reduction. Provider-reported usage is retained separately. Missing provider/memory/compute costs are unknown; complete task cost and cost per successful task are not established.

## Per-arm change from original pilot

| Case / mode | Time before → now | Turns before → now | Tool errors before → now |
| --- | ---: | ---: | ---: |
| 01_styles / neo | 5.65 → 6.34s | 2 → 2 | 0 → 0 |
| 01_styles / off | 7.68 → 5.08s | 4 → 2 | 0 → 0 |
| 01_styles / on | 8.74 → 5.32s | 4 → 2 | 0 → 0 |
| 02_navigation / neo | 15.95 → 20.28s | 5 → 6 | 0 → 0 |
| 02_navigation / off | 10.83 → 9.43s | 5 → 3 | 0 → 0 |
| 02_navigation / on | 29.68 → 15.97s | 11 → 5 | 4 → 0 |
| 03_comparison / neo | 6.43 → 8.63s | 2 → 2 | 0 → 0 |
| 03_comparison / off | 9.25 → 9.62s | 4 → 3 | 0 → 0 |
| 03_comparison / on | 11.03 → 6.83s | 4 → 2 | 0 → 0 |
| 04_vision / neo | 13.13 → 9.14s | 4 → 4 | 0 → 0 |
| 04_vision / off | 16.21 → 11.67s | 7 → 4 | 0 → 0 |
| 04_vision / on | 11.54 → 9.64s | 5 → 3 | 0 → 0 |
| 05_recovery / neo | 7.97 → 9.37s | 5 → 4 | 1 → 1 |
| 05_recovery / off | 13.33 → 8.37s | 6 → 4 | 1 → 1 |
| 05_recovery / on | 12.35 → 7.36s | 6 → 4 | 1 → 1 |
| 06_learning / neo | 16.44 → 17.50s | 6 → 6 | 0 → 0 |
| 06_learning / off | 15.91 → 8.89s | 5 → 3 | 0 → 0 |
| 06_learning / on | 10.66 → 8.14s | 5 → 3 | 0 → 0 |

## Mechanism findings

Agent marker calls fell from 12 to 0 in each Ragnar mode. The delegated public-navigation arm had zero argument/help errors (four previously); its planner turns fell from 11 to 5. All three recovery arms deliberately injected one tool error and independently recorded exactly one submission. There were no unintended tool errors in this pass.

The public navigation-on task did not invoke Jev; its trace used the executor for reads and then direct tools/output recovery. The stable-plan arm invoked Jev once: 1,223 input and 197 output tokens, 0.132s latency. Local vision reported 1,180 prompt and 27 completion tokens, 1.887s latency. Provider fees are not reported.

Ragnar off and on had almost identical summed time (53.05s vs 53.27s); off had lower main-agent API-equivalent cost ($0.399326 vs $0.431377). The result supports keeping delegation optional, not making it a universal default winner.

## Failures and limits

- 02_navigation / neo: Answer or actual browser/fixture state did not meet the oracle

The unverified direct-Neo navigation answer matched the expected URL, heading and explanation, but the independent checker returned publicVerified:false. The recorded browser evaluation reported location.href at /api while its content wrapper still labeled the origin /models. The checker prefiltered tab-list URLs, so stale SPA metadata is a plausible harness false negative. The raw attempt remains unverified; this is not evidence of a Ragnar accuracy advantage. Future verification now reads current location/DOM on owned tabs before testing the destination; no paid task was rerun or raw result rewritten. The replacement verifier passed an owned synthetic DOM/location check with zero model calls; evidence is `dist/benchmarks/pilot-0.4.12/future-verifier-validation.json`.

This is a second one-pass pilot, not enough samples for stable median/tail latency, reliability rankings or broad speed claims. Browser/model caching, run order and provider/network variability remain confounds. Fresh Claude process/MCP startup and final independent verification are inside elapsed time; fixture preparation is outside it. The first acquisition case does not measure learned-repeat improvement. Cloud vision and remote OpenViking recall are outside this retest. No guaranteed improvement, subscription savings or 10× result follows from mechanism checks alone.

Raw JSONL, prompts, traces and provider SQLite records are retained in ignored `dist/benchmarks/pilot-0.4.12/`. The original pilot files were not overwritten. Stop for usage review before further paid tasks.
