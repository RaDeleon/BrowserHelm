# Qwen3.8 Flash and UI-TARS 1.5 7B trials

Date: October 15, 2026 (America/Los_Angeles). BrowserHelm 0.5.2, installed bundled Python 3.12, BrowserOS Neo. Gemini was not called. Saved selection remains DeepSeek V4.1 Flash.

## Scope and outcome

Qwen3.8 Flash is already selectable in the installed app's OpenRouter picker. The question is whether it deserves a tested recommendation; these trials do not support promoting it. UI-TARS was exercised through a test-only native-action adapter and is not installed or exposed by the app. No new app build was created, and neither model was selected in saved settings.

The two main workloads per model each contain three point proposals for clear targets, one absent-target refusal, one ambiguous-target refusal, and one explicit fixture click with independent text verification. One pass per wording/workload, no automatic retries, temporary gateway state, memory disabled. All attempts, including invalid results, are retained. Qwen used the existing strict JSON point adapter; UI-TARS used a bounded native-action parser. No model-provided code was executed, and no non-fixture click was sent.

| Metric | Qwen3.8 Flash | UI-TARS 1.5 7B | Earlier DeepSeek trial |
| --- | --- | --- | --- |
| Points within correct tile | 4/6 | 6/6 | 6/6 |
| Verified fixture clicks | 2/2 | 2/2 | 2/2 |
| Missing target correctly refused | 0/2 valid refusals; 2 format errors, no click | 2/2 | 2/2 |
| Ambiguous target correctly refused | 0/2 | 0/2 | 0/2 |
| Format validation errors | 4/12 | 0/12 | 0/12 |
| Cases passing all supplied checks | 6/12 | 10/12 | 10/12 |
| Median reported inference, valid responses only | 6.168s (8 responses) | 0.963s (12 responses) | 3.719s (12 responses) |

The overall smoke acceptance criteria failed for both models. UI-TARS's two failures were both ambiguous-target selections; Qwen had the same ambiguity problem plus four malformed/out-of-bounds responses. Four Qwen failures were rejected before action. Both providers independently produced `Vision test complete` after each explicit triangle click.

For precise-shape descriptions, an additional independent geometric oracle checks the actual white triangle, circle and square, not just the larger clickable tile. Using retained canvas bounds, UI-TARS hit all 3 point targets plus the click target (4/4). Qwen hit 2/3 point targets plus the click target (3/4); the remaining triangle response failed validation. The new harness records this finer oracle explicitly. Earlier DeepSeek reports did not retain the required canvas geometry, so no exact-shape score is claimed for that run.

## Diagnostic follow-up

A separately labeled Qwen diagnostic checked only the previously problematic square and missing target, with synthetic response text/usage captured. Both returned valid JSON on that follow-up. The earlier invalid outputs were not captured, so their exact format fault remains unresolved. This diagnostic is not pooled with the main 12-attempt score or presented as evidence that the original failures were fixed. It adds $0.00011045232 of reported cost.

## Costs and timing

- Qwen main trials: **$0.00112550328 known reported cost**, with 4 additional calls of unknown cost/usage because their responses failed validation. This is a lower bound, not a complete bill.
- UI-TARS main trials: **$0.001753092 reported cost** across all 12 calls; no missing reported usage/cost.
- Earlier DeepSeek: **$0.000205942176 reported cost** across 12 calls. UI-TARS was more expensive on these fixture calls. Its image preparation, tokenization and cache state differ; no general cost-per-task ratio is established.
- Full Qwen trial elapsed times: 34.081s and 30.585s; full UI-TARS trial elapsed times: 11.050s and 6.538s. Median case time including errors and browser work: Qwen 6.402s, UI-TARS 1.123s. These are fixture measurements, not general end-to-end agent speedups. The first UI-TARS trial overlapped the diagnostic Qwen subset in separate sessions; the second ran separately. No 10x completion claim is made.

## UI-TARS prototype details

The fixed model is `bytedance/ui-tars-1.5-7b` through OpenRouter, using only supported output limits and temperature controls. It does not pretend to support the existing reasoning-disabled strict JSON request. The test-only adapter asks for one `Action: click(start_box='(x,y)')` proposal or an explicit `finished` refusal, validates it with full-string matching and strict bounds, then supplies a normalized point to the existing visual action boundary. It rejects plans, extra actions, code, unsupported syntax and out-of-bounds coordinates. No `eval`, generated scripts, or autonomous UI action loop is used.

The published Qwen2.5-VL/UI-TARS preprocessing rounds image dimensions to multiples of 28. For this prototype, `/usr/bin/sips` explicitly prepares the synthetic PNG at those dimensions; native absolute pixels are mapped back through normalized full-image coordinates. This is test infrastructure, not a new runtime dependency in the installed app. Ambiguity rejection remains unproven and failed both attempts; the parser cannot establish semantic target uniqueness on its own.

Sources checked: [UI-TARS repository](https://github.com/bytedance/UI-TARS), [deployment/response format](https://github.com/bytedance/UI-TARS/blob/main/README_deploy.md), [coordinate preprocessing](https://github.com/bytedance/UI-TARS/blob/main/README_coordinates.md), [live endpoint controls](https://openrouter.ai/api/v1/models/bytedance/ui-tars-1.5-7b/endpoints).

## Case records

| Model | Wording | Case | Passed | Format error | Exact shape hit | Seconds including failure |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8 Flash | Tiles | triangle | True | False | not scored | 1.697 |
| Qwen3.8 Flash | Tiles | circle | True | False | not scored | 7.873 |
| Qwen3.8 Flash | Tiles | square | False | True | not scored | 2.579 |
| Qwen3.8 Flash | Tiles | absent | False | True | not scored | 6.954 |
| Qwen3.8 Flash | Tiles | ambiguous | False | False | not scored | 5.604 |
| Qwen3.8 Flash | Tiles | click | True | False | not scored | 8.945 |
| Qwen3.8 Flash | Shapes | triangle | False | True | False | 1.548 |
| Qwen3.8 Flash | Shapes | circle | True | False | True | 1.639 |
| Qwen3.8 Flash | Shapes | square | True | False | True | 6.52 |
| Qwen3.8 Flash | Shapes | absent | False | True | not scored | 7.622 |
| Qwen3.8 Flash | Shapes | ambiguous | False | False | not scored | 6.283 |
| Qwen3.8 Flash | Shapes | click | True | False | True | 6.537 |
| UI-TARS 1.5 7B | Tiles | triangle | True | False | not scored | 2.584 |
| UI-TARS 1.5 7B | Tiles | circle | True | False | not scored | 1.173 |
| UI-TARS 1.5 7B | Tiles | square | True | False | not scored | 1.895 |
| UI-TARS 1.5 7B | Tiles | absent | True | False | not scored | 1.18 |
| UI-TARS 1.5 7B | Tiles | ambiguous | False | False | not scored | 1.826 |
| UI-TARS 1.5 7B | Tiles | click | True | False | not scored | 1.783 |
| UI-TARS 1.5 7B | Shapes | triangle | True | False | True | 0.942 |
| UI-TARS 1.5 7B | Shapes | circle | True | False | True | 1.026 |
| UI-TARS 1.5 7B | Shapes | square | True | False | True | 1.073 |
| UI-TARS 1.5 7B | Shapes | absent | True | False | not scored | 0.776 |
| UI-TARS 1.5 7B | Shapes | ambiguous | False | False | not scored | 1.048 |
| UI-TARS 1.5 7B | Shapes | click | True | False | True | 1.053 |

## Recommendation and verification

Keep DeepSeek selected. Do not promote Qwen as a dependable first choice based on these trials. UI-TARS is a credible specialist for further testing, with clean output and accurate shapes here, but its ambiguity failures and higher measured fixture cost do not justify silently installing or selecting it as the preferred provider. A candidate app option would need a reviewed production adapter, representative real-screen tests, and explicit handling of uncertain/duplicate targets. Gemini remains outside this task.

Thirty script/native-settings/release tests passed, including new checks proving that a correct tile is insufficient for an exact-shape hit, and that UI-TARS parsing rejects extra actions, executable text and invalid coordinates. No production adapter or native UI source was changed in this test phase, and no reinstall is required.

Raw main reports and the separate diagnostic are retained under ignored `dist/`; these source scripts reproduce the authorized test, incur provider charges and preserve saved settings:

```sh
python3 -B script/jev_vision_smoke.py --provider openrouter --model qwen/qwen3.8-flash --report dist/qwen-tiles-new.json
python3 -B script/jev_vision_smoke.py --provider openrouter --model qwen/qwen3.8-flash --shape-targets --report dist/qwen-shapes-new.json
python3 -B script/uitars_grounding_trial.py --provider openrouter --model bytedance/ui-tars-1.5-7b --report dist/uitars-tiles-new.json
python3 -B script/uitars_grounding_trial.py --provider openrouter --model bytedance/ui-tars-1.5-7b --shape-targets --diagnostics --report dist/uitars-shapes-new.json
```
