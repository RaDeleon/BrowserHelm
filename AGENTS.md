# BrowserHelm development instructions

<!-- codebase-memory-mcp:start -->
For structural codebase exploration, use the installed `codebase-memory` skill.
<!-- codebase-memory-mcp:end -->

## Product objective and performance acceptance

- Target at least **10× faster end-to-end verified task completion** than the same Claude/Codex client using BrowserOS Neo directly. This is the development target, not an achieved performance claim.
- Aim for equal or lower **total cost per successful task**. Include main-agent, decision-provider, vision-provider and memory embedding/storage costs. A 10× speedup at 10× the cost does not meet the goal. Report any cost increase explicitly; do not infer an acceptable increase from speed alone.
- Preserve or improve task completion accuracy. Keep failures, recovery time, escalation and verification costs in the results. Do not optimize away freshness checks, postconditions or required human approvals to improve timings.
- Prioritize reducing expensive planner round trips through bounded multi-step execution, deterministic browser evidence, verified experience reuse and compact results. These are development priorities; do not describe unimplemented delegation as available.
- Use local vision as the default starting path. Cloud/OpenRouter is an explicit user choice and must justify its extra cost through measured total-task benefit. Avoid mandatory extra model or reflection passes without evidence that they improve the overall result.
- Learning should reuse independently verified procedures and relevant failure lessons, invalidate stale or unsuccessful evidence and verify the current page. Separate learned-repeat gains from first-run performance; do not claim online weight training or guaranteed improvement on every run.

## Benchmark and reporting requirements

- Follow `docs/benchmarks.md`. Compare equivalent tasks, the same main-agent model, comparable browser state and tool exposure. Include Neo directly and BrowserHelm local/cloud modes, with and without learning. Report first runs, warmed runs and learned repeats separately.
- Measure elapsed time from task submission through independently verified completion. Publish the workload, settings, sample size, success rate, median/tail latency, main-agent turns and usage, provider usage and total cost assumptions. Retain failed attempts rather than reporting only fast successes.
- Keep measured API costs, client-reported tokens, approximate text token equivalents, Neo estimates and subscription allowance usage distinct. Missing usage or cost is unknown, not zero. Lower token usage does not by itself prove a lower subscription bill or a specific quota reduction.
- Passing regressions, smaller payloads, avoided calls, individual model latency and controlled fixture results establish those mechanisms. Claim 10× performance only for a matched end-to-end workload that demonstrates it; disclose the corresponding quality and cost results.

## Installing updated builds

- After validating a new BrowserHelm app build, install it at `/Applications/BrowserHelm.app`. Creating a DMG or staging a copy in `dist/` does not complete the update.
- Preserve the user's settings, Keychain entries, metrics, diagnostics, and experience memory during installation.
- Wait for active MCP/browser tasks to finish before replacing the installed app; do not interrupt their work to update it.
- Verify the installed version and code signature. Reconnect MCP clients after installation and confirm they report the new version before calling the update complete.

## Publishing releases

- For every validated BrowserHelm version update, commit and push the release source and publish a GitHub release with matching version tag, release notes, verified installer and checksum. A local build/install alone does not complete a release.
- Keep generated captures, private settings, metrics, credentials and local experiment outputs out of commits and release assets.
- Identify preview/ad-hoc signing and notarization status accurately. Verify the published tag, source commit and downloadable assets before reporting publication complete.
