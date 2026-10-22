# From Claude to the browser and back

This describes the **0.4.7 implementation**, checked against the gateway, decision, vision and experience adapters. Claude can be replaced by Codex or another MCP client.

**0.4.10 update:** [`browserhelm_execute`](delegated-executor.md) now combines supported inspection, extraction, public navigation, scrolling and optional vision point proposals in one bounded read-only plan. The separate-tool workflows below remain available; their diagrams describe the earlier coordination path.

**Claude plans the task. BrowserHelm manages browser requests, bounded delegation, verification and compact results. Jev chooses among observed public links. Vision locates a visual target. BrowserOS Neo performs the browser operations. OpenViking stores and retrieves past outcomes.**

There are three useful workflow patterns below. The third combines two existing tools under Claude's coordination; there is no implemented autonomous Jev-plus-vision executor. Vision can also be used by itself without Jev.

## Before the first action

Claude connects over stdio MCP to the BrowserHelm Swift launcher, which starts a Python gateway for that client connection. The gateway negotiates MCP with the separately running Neo over loopback HTTP. The native app manages settings and Keychain credentials; closing its GUI does not stop an existing client's gateway.

BrowserHelm supplies shorter tool descriptions and instructions, preserving original documentation through `neo_help`. The default catalog keeps Neo's granular tools and `run`; optional compact catalog mode exposes fewer entries while retaining browser capability through `run`. Enabling vision adds `browserhelm_visual_act` after reconnection.

When you submit a browser task, **Claude chooses the tools and decomposes the goal**. BrowserHelm does not automatically inspect every task and choose Jev or vision. Normal tool forwarding, delegated navigation and visual grounding are distinct dispatch paths.

## 1. Direct browser tools: no Jev or vision

![Direct browser execution with savings annotations](images/browser-path-direct.png)

1. Claude chooses a Neo tool such as `snapshot`, `evaluate`, `act`, or `run` and sends its arguments to BrowserHelm.
2. BrowserHelm forwards that request to Neo. A `run` request can contain several browser operations written by Claude; that is execution of Claude's code, not autonomous Jev planning.
3. Neo reads or changes the page and returns the result to BrowserHelm.
4. BrowserHelm removes recognized duplicate representations and bounds oversized text. Complete omitted text and structured fields remain in a private, session-scoped artifact, available through `neo_read_output` for one hour. Non-text media is preserved, so this forwarding path can still return a screenshot to Claude.
5. Claude receives the compact result, decides whether more work is needed, checks the overall outcome and replies to you. Low-level tool success alone does not prove the user's task is complete.

**Where this saves:** shorter tool context, duplicate removal and bounded browser text reduce what Claude receives. No decision or vision inference is added by BrowserHelm. Claude still handles ordinary planning and recovery, so fewer planner turns are not guaranteed by forwarding alone. Reading every omitted chunk spends that context again. The default output limit is a **6,000-byte text budget**, derived from 2,000 approximate token equivalents, not a 2 KB limit or Claude tokenizer measurement.

With memory enabled, direct calls record metadata and private keyed fingerprints locally. An identical repeated failure receives fixed recovery guidance; failure/recovery lessons queue for OpenViking. This does not replay writes or send ordinary tools through Jev.

## 2. Delegated public navigation: Jev chooses, BrowserHelm verifies

![Jev navigation with savings annotations](images/browser-path-jev.png)

Claude makes one `browserhelm_navigate` call with `startUrl`, a bounded `goal`, literal `successText` and `maxSteps` (default 4, maximum 6).

1. BrowserHelm opens its own Neo tab and observes rendered page text and visible links. If the requested phrase is already present, it returns completion without loading Jev's key or recalling advisory hints.
2. It filters the current links to eligible, unvisited same-origin public HTTPS destinations. There are at most 60 candidate links plus `BLOCKED`. Forms, buttons, query-string URLs and obvious action URLs are outside this loop.
3. It checks locally verified routes first. If reuse is eligible, it can skip Jev. Otherwise, optional local-first OpenViking recall supplies at most two past-outcome hints within a combined 1.6 KB budget.
4. Jev receives the goal, success phrase, current URL/title, bounded URL/label options and any hints. It returns a choice, probabilities and reported usage. It receives neither a screenshot nor a full page body through this decision adapter. A choice outside the observed set is rejected; `BLOCKED` or a chosen probability below 0.70 escalates. Other configured text providers can serve this role but do not supply calibrated probabilities.
5. BrowserHelm uses Neo to recheck that the page and visible selected link still match, then navigate in the same browser request. Jev does not connect to Neo or execute actions itself.
6. BrowserHelm observes again and checks the phrase locally. It repeats within the step/time budget, or returns escalation on uncertainty, stale evidence, error or cancellation. There is no automatic action retry or paid-provider fallback.
7. BrowserHelm records the outcome and returns Claude a bounded report: completion/escalation, URL/page ID, verification excerpt, decisions, browser-call count, elapsed time and reported provider usage. Claude evaluates whether that literal text postcondition actually satisfies the broader request.

**Where this saves:** several link choices and browser observations can happen inside one Claude tool call, avoiding an intermediate Claude planning turn per hop. Jev gets bounded text instead of unrestricted browser context. A learned route can skip the decision call entirely. Provider inference and memory hints also add usage; the net task saving needs measurement.

## 3. Jev and vision in the same task: separate calls coordinated by Claude

![Claude-coordinated Jev and vision workflow with savings annotations](images/browser-path-jev-vision.png)

For example, Claude can use Jev-assisted navigation to reach a public page, receive that result and its page ID, then request a visual target that current DOM references cannot identify. `browserhelm_navigate` never invokes vision; `browserhelm_visual_act` uses the selected vision provider, which can now be experimental Jev image grounding (0.5.2). It does not invoke the navigation decision adapter. This pattern has an intermediate return to Claude.

The navigation stage follows path 2. In the visual stage:

1. Claude calls `browserhelm_visual_act` with a page ID, target instruction, `action: point` or `action: click`, and optionally `successText`. `point` is the default and sends no click.
2. BrowserHelm obtains current URL/DOM/viewport metadata through Neo. For a click with expected text already present, it returns without clicking or earning learning credit.
3. Neo captures a screenshot for BrowserHelm. Eligible identical-task/scene evidence is checked locally before inference. Otherwise, the selected vision model receives the screenshot and target instruction. Local Ollama/LM Studio is the starting path; explicitly selected OpenRouter or TypeSafe sends the screenshot to that cloud provider. Jev image grounding combines unique-target probability and box-confidence checks in one request; see [vision setup](local-vision.md).
4. Vision returns `found` and normalized coordinates. BrowserHelm validates them and converts them to CSS viewport pixels. Vision supplies grounding, not a task plan or a browser action.
5. Before a click, BrowserHelm captures again and checks scene/target pixels. Neo also rechecks DOM/viewport state immediately before dispatch. Changed evidence returns a stale result. Freshness checks narrow risk but do not make a browser click atomic.
6. For `click`, Neo sends one explicitly requested click. If a success phrase was supplied, BrowserHelm waits for that text and reports whether it appeared. Without it, a dispatched click stays unverified. A failure never triggers a blind repeat click.
7. Claude receives coordinates, grounding source, click/verification status, usage and latency. This tool returns **no screenshot to Claude**. Claude decides the next step or final response.

**Where this saves:** the screenshot is interpreted by the selected grounder instead of being returned to Claude by this tool. Local inference avoids a cloud vision API charge, while still consuming local compute and time. A verified visual repeat can avoid inference altogether. Using both Jev and vision costs more than skipping them when structured evidence suffices, and the current composition still needs Claude to coordinate stages.

## OpenViking and local evidence are complementary

OpenViking is an optional persistent memory service, not a mandatory hop between the models and Neo. The gateway's adapter is scoped to `viking://~/memories/experiences/browserhelm`; it does not automatically retrieve your entire preference/profile library for every browser request. A Claude/Codex memory integration can separately retrieve preferences, as distinct from this execution adapter.

| Layer | What it does | Saving and boundary |
| --- | --- | --- |
| Local navigation evidence | Matches the start URL, exact task identity, success phrase and current candidate link. Two separate locally recorded, text-verified successes within 30 days can authorize reuse. | Skips Jev and advisory recall for a proven choice; live link and final text checks remain. Conflicting routes or later failures remove eligibility; two new successes restore it. Remote hints alone cannot authorize reuse. |
| Local visual evidence | Matches task, URL, expected text, provider/account identity and scene. Two independent model-grounded, text-verified clicks within seven days can support coordinate reuse. | Skips vision inference, while fresh screenshots and DOM/viewport guards remain. Scene changes miss the shortcut; failures revoke it. Reused successes do not count as new independent model evidence. Coordinates and screenshots stay local. |
| OpenViking recall | Searches relevant navigation outcomes on a local cache miss, checks task matching and returns bounded advisory hints. | May reduce wrong choices; adds hint tokens and can add retrieval latency. A local cache hit avoids the service round trip. Remote records never prove current completion. |
| Durable upload outbox | Saves outcomes locally, queues scoped OpenViking records and retries unavailable uploads with leases/backoff. Uploads request `vectors_only` processing. | Avoids an extra reflection/summary model pass in this upload path. Embedding/storage can still cost money. Upload failure never repeats a browser action. |
| Failure lessons | Stores classified navigation failures, generic visual outcomes and direct-request failure/recovery lessons. | Can help later attempts avoid a known failure. It is procedure reuse and advice, not model-weight training or guaranteed improvement. |

Navigation records include redacted goals/success phrases, public routes and checked outcomes, excluding page bodies, screenshots, form contents and model reasoning. Visual uploads contain generic outcomes/lessons; URL, instruction, expected text, coordinates and scene fingerprints stay local. Direct-request lessons exclude raw tool arguments and their local fingerprints.

## What the savings labels mean

The diagrams label mechanisms. They do not claim measured Claude subscription savings or a universal speedup.

| Evidence | Observed result | What it establishes |
| --- | --- | --- |
| Historical payload smoke test | Instructions 7,322 → 1,474 characters (~80% smaller); catalog 47,582 → 28,707 bytes (~40% smaller); one snapshot 134,750 → 1,976 bytes (~98.5% smaller first response). | Less text delivered in that earlier configuration; full recovery available. Not current catalog guarantees, billed-token reductions or whole-task savings. |
| 0.4.7 vs 0.4.6 public documentation task, six runs/version | 6/6 verified completions each; browser calls 5 → 4; median complete-call time 0.7626 → 0.7142 seconds (~6.4% lower). | One fewer gateway-to-Neo call per followed link. Deterministic selection, warm/browser caches and no main-agent comparison; not Jev cost savings or Neo-direct superiority. |
| Controlled local visual repeats | Three targets, nine verified clicks; learned third runs 0.261–0.282 seconds with zero local inference tokens. Moving a target forced inference; a failed click revoked reuse. | Verified identical-task/scene inference avoidance. Local model tokens, not Claude quota; narrow warm fixture timings. |

Total task cost includes **Claude + decision provider + vision provider + memory embedding/storage**, plus relevant local compute costs. Unknown usage remains unknown. Text byte estimates, provider-reported tokens, client-reported tokens, API charges and fixed subscription allowance are separate measures. Do not add Neo's aggregate savings to gateway savings because they overlap.

The **10× faster verified task completion** objective remains a target. Compare Neo directly and BrowserHelm local/cloud modes, with and without learning, using equivalent tasks and the same main-agent model. Report first runs, warmed runs and learned repeats separately; retain failures, recovery, quality, median/tail latency and all cost assumptions. See [benchmarks](benchmarks.md), [learning evidence](learning-and-performance.md), [0.4.7 optimization evidence](validation/0.4.7-optimization-review.md) and [visual learning evidence](validation/0.4.5-vision-learning.md).

Implementation: [`browserhelm.py`](../neo-personal/browserhelm.py) dispatches and verifies; [`gateway.py`](../neo-personal/gateway.py) forwards and compacts; [`decision.py`](../neo-personal/decision.py) calls Jev; [`vision.py`](../neo-personal/vision.py) grounds and guards visual actions; [`experience.py`](../neo-personal/experience.py) controls recall, local reuse and uploads. Editable SVGs accompany the PNGs; regenerate them with `python3 script/generate_execution_diagrams.py`.
