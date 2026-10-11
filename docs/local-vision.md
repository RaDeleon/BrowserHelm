# Local vision grounding

OpenRagnar can send a browser viewport screenshot directly to a local vision model and return a small point/click report to Claude or Codex. The main agent supplies the target instruction; the local model locates it; BrowserOS Neo executes the requested click. Jev remains the separate text-choice provider. Current DOM/accessibility refs are preferred when they identify the target reliably.

The BrowserOS [BrowserVLM article](https://www.browseros.com/blog/browservlm/) describes this division of work. Its checkpoint/code links still say coming soon as checked October 10, 2026. OpenRagnar therefore uses the available [Qwen3-VL 2B](https://ollama.com/library/qwen3-vl:2b-instruct) as a configurable starting model. It does not recreate BrowserVLM's trained patch/subpatch grounding heads, training pipeline or compression architecture. These models are distinct; no equivalent accuracy or 10× performance claim is made.

## Setup

1. Start Ollama and run `ollama pull qwen3-vl:2b-instruct` (approximately 1.9 GB). Qwen's model weights are Apache 2.0; they are downloaded separately and are not bundled in the DMG. Ollama 0.12.7 or newer supports this model.
2. In OpenRagnar → Settings → Local vision, enable grounding. Select Ollama, API URL `http://127.0.0.1:11434`, model `qwen3-vl:2b-instruct`.
3. Click Test vision server. This checks the downloaded model's vision capability and that it is not an Ollama remote/cloud model. It does not test target accuracy.
4. Save and reconnect your MCP client. The tool catalog adds `openragnar_visual_act` only when vision is enabled. Keep BrowserOS Neo and Ollama running.

LM Studio uses its local OpenAI-compatible URL, normally `http://127.0.0.1:1234/v1`, and the exact loaded model ID. Its adapter requires image input and JSON output with normalized 0–1000 coordinates. Only numeric loopback endpoints are accepted; proxy environment variables and redirects are disabled. OpenRagnar cannot verify an arbitrary local server's internal routing, so configure LM Studio for local inference. Cloud vision, credentials and remote fallback are not part of this feature.

## Agent usage

For a visual target without a reliable DOM ref:

```json
{"page":42,"instruction":"The green tile containing the white triangle","action":"point"}
```

`point` is the default and does not click. For one explicitly requested click, use `action: "click"`. Add `successText` to check expected text after the action. A successful click dispatch is reported as `clicked_unverified` until that text is observed. Even `text_verified` establishes only text presence, not a purchase, publication or broader business outcome. Do not use the tool to bypass login, CAPTCHA or human approvals.

The tool requests the whole visible viewport within 1280×960 image pixels, compensating for Retina device scale, receives normalized coordinates and maps them to CSS viewport pixels. Before acting it captures again and checks exact pixels in a 64-image-pixel neighborhood around the target when the full frame differs. It also compares the URL, scroll, viewport and visible DOM layout/text fingerprint inside the same browser run that sends the click. PNG decoding is bounded and local; unsupported encodings stop the action. Changed or zoomed pages, uncertain/absent targets, malformed points and server failures return control to the agent. Animated canvas/video content outside the target neighborhood may change without a DOM change. State can also change after observation; these checks do not prove that every pixel stayed identical through dispatch. Screenshots/models can misidentify controls; use a fresh observation and an explicit postcondition for meaningful writes.

There is no blind retry. Starting in 0.4.5, verified local coordinate reuse is available under the exact-scene policy below. If a click was sent but text verification fails, the report retains `clicked: true` and advises inspection. MCP cancellation is checked before action. Other client connections can change a shared tab; clients should avoid simultaneous writes to it.

## Measurement and privacy

The tool report includes local model usage, inference latency, screenshot bytes, CSS point, action and text-verification status. Provider-token counters include local vision inference tokens; these are not Claude subscription tokens. The screenshot is not returned to the client, written by this module to output storage, or added to OpenViking. BrowserOS Neo may still retain its own local replay/screenshots. Visual outcomes sync without screenshots, URLs, instructions, postcondition text, scene fingerprints or coordinates. Coordinate evidence is local and separate from navigation routes. Model weights are never trained by this feature.

Using the tool can avoid sending screenshots to the main model for target grounding. It cannot intercept an agent that keeps requesting the ordinary screenshot tool, nor avoid screenshots needed for design review or visual quality assessment. Model loading/inference can increase latency. Compare matched tasks, correctness, main-agent turns and client-reported usage before claiming savings.

Run the opt-in controlled canvas test with BrowserOS Neo and Ollama running:

```sh
python3 script/vision_smoke.py --report dist/vision-smoke.json
```

It opens its own test page, proposes a point, then performs one click and verifies the fixture's expected text. It also checks two additional points against independently known tile bounds. It reads no provider keys or saved app settings. It leaves its test tabs for inspection, stops its temporary local server, and reports main-client response bytes separately from screenshot size. This is a capability check, not a broad model benchmark. The live trial passed with the triangle, circle and rightmost brown square descriptions. Describing the brown tile as orange returned no point; that failed trial is retained locally, and sent no click for that target.

## Verified visual learning (0.4.5)

Enable OpenViking memory in Settings as well as Local vision. For an explicit `click` with `successText`, the text must be absent before the action and present afterward. If it already exists, the tool returns `already_satisfied`, takes no action and gives no learning credit. Text presence remains a narrow postcondition, not proof of business completion.

Two separately observed, model-generated text-verified runs qualify an identical task for reuse. The key includes the complete URL, exact instruction, successText and provider configuration; scene matching includes the full PNG bytes and viewport/layout metadata. Evidence is scoped to this installation and OpenViking identity, expires after seven days and is limited to 2,000 local records. Different pixels, intent, postcondition, provider or viewport require a new model call. Remote memories cannot supply points or qualify them for reuse.

A qualifying later request still captures the current screen, rechecks the target pixels and DOM/viewport, sends at most one explicitly requested click, and verifies the text. The report identifies `groundingSource: verified_local_memory`, zero inference tokens and one local provider call avoided. It does not claim Claude token savings. Failed or unverified attempts revoke that exact shortcut until two new model successes occur; reused successes do not count as independent model evidence. Point-only requests cannot promote reuse. Storage failures fall back to model execution without retrying browser writes.

The Experience memory page displays recorded visual attempts, text-verified outcomes, local model calls avoided and verified reuse. Disabling memory stops capture and reuse as well as uploads. OpenViking preserves outcome/lesson records while the local evidence table enforces the execution policy. This improves repeat execution for proven identical scenes; it does not guarantee improvement on every new task or improve the model's weights.

Run the opt-in repeated-task and failure-recovery trial:

```sh
python3 script/vision_learning.py --report dist/vision-learning.json
# Also save and read back one clearly marked validation outcome:
python3 script/vision_learning.py --remote --report dist/vision-learning-remote.json
```

The trial uses its own canvas page and temporary database. It runs three targets three times, reopens memory before each third attempt, moves the triangle, injects a verification failure, then requires two fresh model successes before reuse returns. It also verifies already-present text does not trigger another click. These are controlled capability tests, not broad GUI accuracy, Claude quota or 10× benchmarks.
