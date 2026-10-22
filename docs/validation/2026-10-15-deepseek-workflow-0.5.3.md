# BrowserHelm 0.5.3 — DeepSeek workflow configuration

Validated and installed October 15, 2026 (America/Los_Angeles).

## Installed settings

- Vision enabled: OpenRouter / `deepseek/deepseek-v4.1-flash`.
- Decision provider: TypeSafe / pinned `jev-1.13.0`.
- Bounded delegation and existing verified learning: on.
- Optional agent task markers and compact-only catalog: off.
- Result budget: 2,000 approximate token equivalents; full tool catalog retained.
- Guidance: DOM/accessibility first, batch deterministic work, bounded plans where useful, vision for unique visual targets, current-page freshness and explicit postconditions. Main agent retains planning, judgment and recovery.

DeepSeek is first in the picker and the default when explicitly selecting OpenRouter. Qwen is labeled experimental with its mixed fixture results. Gemini was removed from curated presets; UI-TARS remains test-only. Existing explicit model selections are preserved by configuration decoding; new installations still start with local vision disabled. This user's cloud selection was explicitly authorized.

## Checks

- 236 engine tests passed on bundled Python 3.12.
- 30 script/release/native settings tests passed.
- 5 benchmark oracle tests passed.
- Native Swift release compile passed; release metadata validates v0.5.3, build 21.
- Installed `/Applications/BrowserHelm.app` version and build verified.
- Strict deep signature verification passed before and after native runtime checks.
- Fresh native `BrowserHelm --mcp` initialization reported 0.5.3. Updated DOM-first/unique-target guidance and configured execute/navigation/vision helpers were verified without model inference or changes to user tabs.

## Installation and preservation

Installation ran only after confirming no live tracked browser tasks and an idle gateway activity window. The previous app and private settings backup are retained under `~/Library/Application Support/BrowserHelm Update Backups/20261016T012957Z/`. Requested workflow fields and the Jev pin were applied atomically; unrelated settings, Keychain entries and existing history table rows were preserved.

The existing Codex BrowserHelm transport returned `Transport closed` after idle launcher shutdown. Fresh native initialization passed, but existing Claude/Codex connectors still need reconnecting or their client restarted. The active Codex app was not quit.

No paid model trial or matched end-to-end benchmark ran for this configuration update. These are conservative workflow choices, not demonstrated globally optimal settings, lower total-task cost or 10x completion speed. See [workflow settings](../workflow-settings.md) and the retained vision comparisons for limitations.
