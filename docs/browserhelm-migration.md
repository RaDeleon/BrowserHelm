# OpenRagnar → BrowserHelm 0.5.0

BrowserHelm is the new app and repository identity. Packet Studio replaces the Viking theme with graphite/navy, cyan accents, native navigation and the approved text-free browser/routing icon. BrowserOS Neo is still required.

## What changes

- App: `/Applications/BrowserHelm.app`, executable `Contents/MacOS/BrowserHelm`, bundle `com.techinsf.browserhelm`.
- MCP server: `browserhelm`; new tools use `browserhelm_` (execute, navigate, visual_act, status, task). Old `openragnar_` tool calls are accepted for cached clients but are not advertised in the new catalog.
- Swift package/source target: BrowserHelm. Python engine: `browserhelm.py`; `openragnar.py` remains a compatibility import for existing external scripts.
- Current docs, build/release scripts, DMG and execution diagrams use BrowserHelm. Historical validation/release notes retain their original names, versions and measured evidence.

## State preservation

The installer/first launch copies `~/Library/Application Support/OpenRagnar` into `~/Library/Application Support/BrowserHelm` only when the destination is absent. SQLite backup includes committed WAL contents; settings, outputs, metrics, task records, diagnostics, local experience evidence and fingerprint secrets are retained. The original directory is kept for rollback and is not merged into an existing new directory.

The Keychain service **com.techinsf.openragnar** intentionally remains stable; API keys are not exported or rewritten. macOS may require allowing the newly signed launcher to access those items. Existing appearance preferences are imported; new installations default to Dark with accessible Light/System variants.

The OpenViking collection and serialized experience source stay **openragnar** for compatibility with existing remote outcomes and queued upload URIs. This is a storage namespace, not an app label. No memory is moved, deleted or re-embedded. Historical tool names remain recognized by task accounting and Neo session classification.

## Client migration

Only recognized OpenRagnar stdio entries are renamed. Commands switch to the installed BrowserHelm launcher; arguments, disabled state, tool restrictions and timeouts remain intact. Unrelated settings and MCP entries are preserved. Configurations receive private backups and concurrent changes/conflicting entries abort the migration.

Finish active browser tasks before switching. Restart Claude Desktop after configuration migration; open a new Codex chat or restart Codex to reload its server catalog. Fresh handshakes from saved commands verify the installed server name/version, but do not prove an existing client's cached catalog refreshed. Keep BrowserOS Neo running.

The previous app is retained in a private rollback directory outside Applications after verification, rather than deleted. The local checkout is named BrowserHelm. A compatibility symlink at the former OpenRagnar path keeps attached Codex chats and project references usable; its Git remote and product identity use BrowserHelm.

## Rollback

Stop new MCP work first. Restore the saved client config backups and the original app from the rollback directory, then reconnect clients. The old support directory is retained. New history recorded after migration is in BrowserHelm's directory and should not be discarded or overwritten during rollback.
