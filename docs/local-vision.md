# Local vision grounding

OpenRagnar 0.4.4 can send a browser viewport screenshot directly to a local vision model and return a small point/click report to Claude or Codex. The main agent supplies the target instruction; the local model locates it; BrowserOS Neo executes the requested click. Jev remains the separate text-choice provider. Current DOM/accessibility refs are preferred when they identify the target reliably.

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

The tool requests the whole visible viewport within 1280×960 image pixels, compensating for Retina device scale, receives normalized coordinates and maps them to CSS viewport pixels. Before acting it compares the URL, scroll, viewport and visible DOM layout/text fingerprint inside the same browser run that sends the click. Changed or zoomed pages, uncertain/absent targets, malformed points and server failures return control to the agent. Animated canvas/video content may change without a DOM change: the layout check is a useful guard, not proof that every pixel stayed identical. Screenshots/models can misidentify controls; use a fresh observation and an explicit postcondition for meaningful writes.

There is no blind retry or coordinate memory replay. If a click was sent but text verification fails, the report retains `clicked: true` and advises inspection. MCP cancellation is checked before action. Other client connections can change a shared tab; clients should avoid simultaneous writes to it.

## Measurement and privacy

The tool report includes local model usage, inference latency, screenshot bytes, CSS point, action and text-verification status. Provider-token counters include local vision inference tokens; these are not Claude subscription tokens. The screenshot is not returned to the client, written by this module to output storage, or added to OpenViking. BrowserOS Neo may still retain its own local replay/screenshots. Existing memory captures metadata-only tool outcomes; vision points do not enter navigation route reuse or train model weights.

Using the tool can avoid sending screenshots to the main model for target grounding. It cannot intercept an agent that keeps requesting the ordinary screenshot tool, nor avoid screenshots needed for design review or visual quality assessment. Model loading/inference can increase latency. Compare matched tasks, correctness, main-agent turns and client-reported usage before claiming savings.

Run the opt-in controlled canvas test with BrowserOS Neo and Ollama running:

```sh
python3 script/vision_smoke.py --report dist/vision-smoke.json
```

It opens its own test page, proposes a point, then performs one click and verifies the fixture's expected text. It also checks two additional points against independently known tile bounds. It reads no provider keys or saved app settings. It leaves its test tabs for inspection, stops its temporary local server, and reports main-client response bytes separately from screenshot size. This is a capability check, not a broad model benchmark. The live trial passed with the triangle, circle and rightmost brown square descriptions. Describing the brown tile as orange returned no point; that failed trial is retained locally, and sent no click for that target.
