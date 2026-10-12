# Vision grounding

BrowserHelm can send a browser viewport screenshot directly to the selected local or OpenRouter vision model and return a small point/click report to Claude or Codex. The main agent supplies the target instruction; the local model locates it; BrowserOS Neo executes the requested click. Jev remains the separate text-choice provider. Current DOM/accessibility refs are preferred when they identify the target reliably.

The BrowserOS [BrowserVLM article](https://www.browseros.com/blog/browservlm/) describes this division of work. Its checkpoint/code links still say coming soon as checked October 10, 2026. BrowserHelm therefore uses the available [Qwen3-VL 2B](https://ollama.com/library/qwen3-vl:2b-instruct) as a configurable starting model. It does not recreate BrowserVLM's trained patch/subpatch grounding heads, training pipeline or compression architecture. These models are distinct; no equivalent accuracy or 10× performance claim is made.

## Setup

1. Start Ollama and run `ollama pull qwen3-vl:2b-instruct` (approximately 1.9 GB). Qwen's model weights are Apache 2.0; they are downloaded separately and are not bundled in the DMG. Ollama 0.12.7 or newer supports this model.
2. In BrowserHelm → Settings → Vision, enable grounding. Select Ollama, API URL `http://127.0.0.1:11434`, model `qwen3-vl:2b-instruct`.
3. Click Test vision server. This checks the downloaded model's vision capability and that it is not an Ollama remote/cloud model. It does not test target accuracy.
4. Save and reconnect your MCP client. The tool catalog adds `browserhelm_visual_act` only when vision is enabled. Keep BrowserOS Neo and Ollama running.

LM Studio uses its local OpenAI-compatible URL, normally `http://127.0.0.1:1234/v1`, and the exact loaded model ID. Its adapter requires image input and JSON output with normalized 0–1000 coordinates. Only numeric loopback endpoints are accepted; proxy environment variables and redirects are disabled. BrowserHelm cannot verify an arbitrary local server's internal routing, so configure LM Studio for local inference. Local providers never switch to cloud automatically. OpenRouter must be selected explicitly.

## OpenRouter and model switching (0.4.6)

Select **Settings → Vision → OpenRouter**, choose a model and enter your OpenRouter key. Save settings. The key stays in macOS Keychain under the existing `openrouter` account, shared with the OpenRouter decision provider; Jev uses its separate account. The fixed API origin is `https://openrouter.ai/api/v1`; local endpoints cannot silently become remote. Cloud mode sends the viewport PNG and target instruction to OpenRouter and its selected provider. Provider retention policies apply. No screenshot, instruction or credential is written into OpenViking.

The picker contains three source-backed candidates chosen for a balance of browser perception, cost and bounded agent work, checked October 10, 2026:

| Preset | Intended role | Source |
| --- | --- | --- |
| Qwen3.8 Flash | First economical candidate for screen understanding and desktop interaction | [OpenRouter](https://openrouter.ai/qwen/qwen3.8-flash) |
| Gemini3.8 Flash | Candidate for demanding visual reasoning and agent tasks | [OpenRouter](https://openrouter.ai/google/gemini-3.8-flash) |
| DeepSeek V4.1 Flash | Efficient alternative with native images and computer-use focus | [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash) |

These are recommendations, not a measured ranking of click accuracy. General reasoning benchmarks do not establish coordinate grounding. Qwen3-VL 32B is excluded because its OpenRouter page marks it deprecated October 9, 2026. The original DeepSeek experimental checkpoint is superseded by V4.1 for new image work. A **Custom OpenRouter model** field accepts other exact author/model IDs. All three preset IDs are advertised by the public endpoints API with image input, JSON response support, output limits and reasoning controls. Links show current rates; no frozen pricing is displayed in the app.

**Test OpenRouter vision** authenticates the key and checks live model metadata. It sends no screenshot and performs no paid inference. Each actual grounding uses one Chat Completions request with an inline PNG, strict point schema, 80-token output limit, reasoning disabled and `require_parameters: true`. Endpoints that cannot honor the required parameters are excluded. Provider errors, malformed JSON, absent targets and out-of-bounds coordinates stop before clicking. No BrowserHelm retry or model fallback is made; OpenRouter may route across providers for the same selected model. Completion failures are recorded as unknown provider usage rather than invented zero tokens. Successful reports retain provider-reported tokens and cost when present.

The last endpoint and model for each vision provider are remembered. **Save settings applies a model/provider switch to the next vision request in existing MCP sessions.** A request already in progress keeps the configuration it started with. First enabling vision still requires refreshing/reconnecting a client's tool catalog. Missing or malformed saved settings stop vision; an old cloud selection is never silently retained. Saved key changes clear the vision credential cache on the next call. Browser forwarding and Jev's decision configuration are unaffected by vision-only changes.

Verified reuse remains scoped to the active provider, endpoint and model. Switching models requires independent verified evidence for that model; returning to a previous selection can reuse its still-valid exact-scene evidence. No API key is included in memory identity. Unsaved edits do not affect running clients. Local remains the installed default until the user selects and saves OpenRouter.

## Agent usage

For a visual target without a reliable DOM ref:

```json
{"page":42,"instruction":"The green tile containing the white triangle","action":"point"}
```

`point` is the default and does not click. For one explicitly requested click, use `action: "click"`. Add `successText` to check expected text after the action. A successful click dispatch is reported as `clicked_unverified` until that text is observed. Even `text_verified` establishes only text presence, not a purchase, publication or broader business outcome. Do not use the tool to bypass login, CAPTCHA or human approvals.

The tool requests the whole visible viewport within 1280×960 image pixels, compensating for Retina device scale, receives normalized coordinates and maps them to CSS viewport pixels. Before acting it captures again and checks exact pixels in a 64-image-pixel neighborhood around the target when the full frame differs. It also compares the URL, scroll, viewport and visible DOM layout/text fingerprint inside the same browser run that sends the click. PNG decoding is bounded and local; unsupported encodings stop the action. Changed or zoomed pages, uncertain/absent targets, malformed points and server failures return control to the agent. Animated canvas/video content outside the target neighborhood may change without a DOM change. State can also change after observation; these checks do not prove that every pixel stayed identical through dispatch. Screenshots/models can misidentify controls; use a fresh observation and an explicit postcondition for meaningful writes.

There is no blind retry. Starting in 0.4.5, verified local coordinate reuse is available under the exact-scene policy below. If a click was sent but text verification fails, the report retains `clicked: true` and advises inspection. MCP cancellation is checked before action. Other client connections can change a shared tab; clients should avoid simultaneous writes to it.

## Measurement and privacy

The tool report includes selected model usage, inference latency, screenshot bytes, CSS point, action and text-verification status. Provider-token counters include local vision inference tokens; these are not Claude subscription tokens. The screenshot is not returned to the client, written by this module to output storage, or added to OpenViking. BrowserOS Neo may still retain its own local replay/screenshots. Visual outcomes sync without screenshots, URLs, instructions, postcondition text, scene fingerprints or coordinates. Coordinate evidence is local and separate from navigation routes. Model weights are never trained by this feature.

Using the tool can avoid sending screenshots to the main model for target grounding. It cannot intercept an agent that keeps requesting the ordinary screenshot tool, nor avoid screenshots needed for design review or visual quality assessment. Model loading/inference can increase latency. Compare matched tasks, correctness, main-agent turns and client-reported usage before claiming savings.

Run the opt-in controlled canvas test with BrowserOS Neo and Ollama running:

```sh
python3 script/vision_smoke.py --report dist/vision-smoke.json
```

It opens its own test page, proposes a point, then performs one click and verifies the fixture's expected text. It also checks two additional points against independently known tile bounds. It reads no provider keys or saved app settings. It leaves its test tabs for inspection, stops its temporary local server, and reports main-client response bytes separately from screenshot size. This is a capability check, not a broad model benchmark. The live trial passed with the triangle, circle and rightmost brown square descriptions. Describing the brown tile as orange returned no point; that failed trial is retained locally, and sent no click for that target.

## Verified visual learning (0.4.5)

Enable OpenViking memory in Settings as well as Vision. For an explicit `click` with `successText`, the text must be absent before the action and present afterward. If it already exists, the tool returns `already_satisfied`, takes no action and gives no learning credit. Text presence remains a narrow postcondition, not proof of business completion.

Two separately observed, model-generated text-verified runs qualify an identical task for reuse. The key includes the complete URL, exact instruction, successText and provider configuration; scene matching includes the full PNG bytes and viewport/layout metadata. Evidence is scoped to this installation and OpenViking identity, expires after seven days and is limited to 2,000 local records. Different pixels, intent, postcondition, provider or viewport require a new model call. Remote memories cannot supply points or qualify them for reuse.

A qualifying later request still captures the current screen, rechecks the target pixels and DOM/viewport, sends at most one explicitly requested click, and verifies the text. The report identifies `groundingSource: verified_local_memory`, zero inference tokens and one selected provider call avoided. It does not claim Claude token savings. Failed or unverified attempts revoke that exact shortcut until two new model successes occur; reused successes do not count as independent model evidence. Point-only requests cannot promote reuse. Storage failures fall back to model execution without retrying browser writes.

The Experience memory page displays recorded visual attempts, text-verified outcomes, model calls avoided and verified reuse. Disabling memory stops capture and reuse as well as uploads. OpenViking preserves outcome/lesson records while the local evidence table enforces the execution policy. This improves repeat execution for proven identical scenes; it does not guarantee improvement on every new task or improve the model's weights.

Run the opt-in repeated-task and failure-recovery trial:

```sh
python3 script/vision_learning.py --report dist/vision-learning.json
# Also save and read back one clearly marked validation outcome:
python3 script/vision_learning.py --remote --report dist/vision-learning-remote.json
```

The trial uses its own canvas page and temporary database. It runs three targets three times, reopens memory before each third attempt, moves the triangle, injects a verification failure, then requires two fresh model successes before reuse returns. It also verifies already-present text does not trigger another click. These are controlled capability tests, not broad GUI accuracy, Claude quota or 10× benchmarks.
