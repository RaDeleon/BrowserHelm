# OpenRouter GUI vision candidates

Date: 2026-10-15. Research only: no inference calls, model setting changes, or performance claims.

## Recommendation

Test **Qwen3.8 Flash** as the closest adapter-compatible alternative, and **Gemini 3.8 Flash** as the strongest explicitly documented computer-use candidate after fixing its reasoning settings. Neither is a proven winner over DeepSeek in BrowserHelm. General model rankings and provider latency dashboards do not establish target localization, abstention accuracy, verified task completion, or total cost in our workload.

| Candidate | Purpose fit and current availability | Adapter compatibility from public metadata |
| --- | --- | --- |
| `qwen/qwen3.8-flash` | OpenRouter describes visual understanding and desktop interaction; accepts text, image, video; Alibaba endpoints. Listed input/output price $0.15/$0.47 per million tokens. | Endpoints list `response_format`, `structured_outputs`, `max_tokens`, and `reasoning`. Catalog reports reasoning optional (`mandatory:false`). Closest fit for the existing reasoning-disabled JSON request; real compatibility and schema fidelity still require inference validation. |
| `google/gemini-3.8-flash` | Google explicitly recommends this model for computer use; OpenRouter exposes image input and text output via Google AI Studio/Vertex. Standard listed price $0.75/$3.75 per million tokens; routing tiers and discounts vary. | Endpoints list schema outputs and `max_tokens`, but catalog says reasoning **mandatory**, with low/medium/high efforts. Current `reasoning.enabled:false` is not a valid assumption. Use supported low effort and sufficient output budget, recording reasoning tokens and cost. |
| `bytedance/ui-tars-1.5-7b` | Purpose-built GUI agent model, currently listed through Parasail on OpenRouter; image/text input, text output; $0.10/$0.20 per million tokens. | Endpoint lists `structured_outputs` and `max_tokens`, but not `response_format` or `reasoning`. Do not assume the current strict `response_format` JSON request works unchanged. Specialized action/coordinate parsing may be required. |

Sources: [Qwen model](https://openrouter.ai/qwen/qwen3.8-flash), [Qwen endpoint metadata](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints), [Google model](https://openrouter.ai/google/gemini-3.8-flash), [Google endpoint metadata](https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints), [Google computer-use documentation](https://ai.google.dev/gemini-api/docs/computer-use), [UI-TARS model](https://openrouter.ai/bytedance/ui-tars-1.5-7b), [UI-TARS endpoint metadata](https://openrouter.ai/api/v1/models/bytedance/ui-tars-1.5-7b/endpoints), [ByteDance repository](https://github.com/bytedance/UI-TARS).

## Important distinctions

Google's native computer-use tool returns UI actions within an execution loop. BrowserHelm's screenshot-to-JSON point locator is a different interface. Availability of the model through OpenRouter does **not** establish that OpenRouter exposes Google's native `computer_use` tool or its safety mechanisms. Evaluating the model as a JSON point locator tests only that narrower route. [Google native API documentation](https://ai.google.dev/gemini-api/docs/computer-use).

The live [OpenRouter model catalog](https://openrouter.ai/api/v1/models) reports Gemini's mandatory reasoning and Qwen's optional reasoning. Google also documents low/medium/high thinking and says minimal is unsupported. Reasoning can consume the completion budget and is billed; hiding reasoning does not remove its cost. [Google model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

Ai2's **MolmoPoint-GUI-8B** is specifically designed to point at software interfaces and is open source, but no Molmo model appeared in the live OpenRouter model catalog during this check. It is a separate hosting/integration investigation, not a confirmed OpenRouter selection. [Ai2 release](https://allenai.org/blog/molmopoint), [OpenRouter catalog](https://openrouter.ai/api/v1/models).

## Proposed next comparison

Use the same screenshots, target descriptions, independent geometric/click oracles, missing-target cases, and duplicate-target cases as the existing DeepSeek/Jev fixture. First check each exact request shape, then compare all attempted cases, including errors and abstentions. Record time, provider/routing tier, visible and reasoning tokens, measured API cost, and verified clicks. Follow with matched full browser tasks against direct Claude/BrowserClaw before choosing defaults. Keep current settings until there is evidence of a better quality/time/cost tradeoff.
