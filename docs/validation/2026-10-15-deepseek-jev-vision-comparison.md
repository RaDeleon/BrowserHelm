# DeepSeek vs Jev vision: controlled BrowserHelm 0.5.2 comparison

Date: October 15, 2026. This evaluates the current provider adapters on a synthetic canvas fixture, not a general model ranking or end-to-end agent benchmark.

## Setup

- Same `vision-targets.html`, six cases per workload: triangle, circle, square, missing target, ambiguous target, and a triangle-tile click followed by text verification.
- Two wording workloads per provider: whole colored tiles and precise white shapes. Each provider made 12 inference calls, with no retries or learned reuse. All results, including failures, are retained.
- BrowserOS Neo owned fresh fixture tabs; isolated temporary gateway state; existing user tabs, saved settings and production experience memory were not modified. Credentials came from the installed app's Keychain helper through private captured IPC.
- DeepSeek used `deepseek/deepseek-v4.1-flash` through the existing OpenRouter adapter: strict `found/x/y` JSON, reasoning disabled, 80 output tokens, required parameter support. Jev used pinned `jev-1.14.0` with one Noul unique-target question and one Box question; both target probability and box confidence had to reach 0.9.
- The adapters have different acceptance policies. This compares the configured systems, not intrinsic model accuracy at matched confidence thresholds. Jev refusals do not establish where its rejected raw boxes would have landed.
- Jev trials were retained from the earlier run today. The two DeepSeek workloads overlapped in separate browser sessions. Therefore elapsed trial times are descriptive only; they are not matched sequential throughput or end-to-end task measurements. All returned screenshots were 1280×780. Screenshots were not retained, so byte-identical rendered frames across providers cannot be proven.

## Results

| Outcome | DeepSeek | Jev |
| --- | --- | --- |
| Points inside correct target tile | 6/6 | 1/6 |
| Missing-target refusal | 2/2 | 2/2 |
| Ambiguous-target refusal | 0/2 | 2/2 |
| Verified fixture clicks | 2/2 | 0/2 |
| Passed individual cases | 10/12 | 5/12 |
| Median provider inference | 3.719s | 0.134s |

Both overall DeepSeek smoke checks still failed because ambiguity refusal is part of the acceptance criteria. DeepSeek selected one candidate when asked for “A colored tile containing a white shape,” although three tiles matched. These were point-only requests, so no ambiguous click was sent. Its two explicit triangle clicks each produced `Vision test complete`, independently re-read from the fixture's outcome element. Jev's two click requests were refused before dispatch.

The point oracle checks containment within the correct 180×180 canvas tile. It does not establish that a proposed point is inside the white shape itself, nor that it would hit a small real-world icon. The fixture handles clicks anywhere in the tile. Correct tile placement and verified clicks therefore demonstrate coarse control targeting only.

## Usage and cost

DeepSeek reported **$0.000205942176** across its 12 calls through OpenRouter `usage.cost`; all 12 included usage and cost. The Jev reports contain **$0.001519938** as a published-rate input-cost estimate across its 12 calls, using $0.042 per million reported input tokens and free output. These are different accounting bases; no billed-cost ratio is claimed. Main-agent cost, learning costs and total cost per successful real task were not measured. The test makes no subscription-savings or 10× completion claim.

## Case-level outcomes

| Workload | Provider | Case | Passed | Found | Clicked | Verified | Inference seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tiles | Jev | triangle | False | False | False | False | 0.139 |
| Tiles | Jev | circle | True | True | False | False | 0.174 |
| Tiles | Jev | square | False | False | False | False | 0.139 |
| Tiles | Jev | absent | True | False | False | False | 0.11 |
| Tiles | Jev | ambiguous | True | False | False | False | 0.129 |
| Tiles | Jev | click | False | False | False | False | 0.129 |
| Shapes | Jev | triangle | False | False | False | False | 0.125 |
| Shapes | Jev | circle | False | False | False | False | 0.162 |
| Shapes | Jev | square | False | False | False | False | 0.139 |
| Shapes | Jev | absent | True | False | False | False | 0.12 |
| Shapes | Jev | ambiguous | True | False | False | False | 0.117 |
| Shapes | Jev | click | False | False | False | False | 0.14 |
| Tiles | DeepSeek | triangle | True | True | False | False | 3.809 |
| Tiles | DeepSeek | circle | True | True | False | False | 3.492 |
| Tiles | DeepSeek | square | True | True | False | False | 3.648 |
| Tiles | DeepSeek | absent | True | False | False | False | 3.789 |
| Tiles | DeepSeek | ambiguous | False | True | False | False | 3.46 |
| Tiles | DeepSeek | click | True | True | True | True | 3.961 |
| Shapes | DeepSeek | triangle | True | True | False | False | 3.478 |
| Shapes | DeepSeek | circle | True | True | False | False | 3.878 |
| Shapes | DeepSeek | square | True | True | False | False | 4.24 |
| Shapes | DeepSeek | absent | True | False | False | False | 3.954 |
| Shapes | DeepSeek | ambiguous | False | True | False | False | 3.46 |
| Shapes | DeepSeek | click | True | True | True | True | 3.344 |

## Decision

Keep the existing DeepSeek vision selection for clearly specified visual targets. It demonstrated more successful coarse targeting and verified clicks on this fixture, while Jev was substantially faster per inference but refused most intended targets under its current threshold. DeepSeek's ambiguity failures mean unique descriptions, current DOM refs when available, and explicit postconditions remain necessary. Neither provider is proven best for general GUI work. Representative independent trials, varied order, local baselines and matched end-to-end task costs are required for broader conclusions.

## Reproduction and artifacts

The existing harness now accepts `--provider openrouter` (DeepSeek) while retaining Jev as its default. Use a different report path for every run to retain failures:

```sh
python3 -B script/jev_vision_smoke.py --provider openrouter --report dist/deepseek-tiles.json
python3 -B script/jev_vision_smoke.py --provider openrouter --shape-targets --report dist/deepseek-shapes.json
```

Raw reports are local ignored artifacts:

- `dist/jev-vision-smoke-0.5.2-initial.json`
- `dist/jev-vision-smoke-0.5.2-shapes.json`
- `dist/deepseek-vision-smoke-0.5.2-tiles.json`
- `dist/deepseek-vision-smoke-0.5.2-shapes.json`
