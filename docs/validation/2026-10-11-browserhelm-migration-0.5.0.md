# BrowserHelm 0.5.0 migration validation — October 11, 2026

The app was migrated from OpenRagnar 0.4.12 build 17 to BrowserHelm 0.5.0 build 18. Packet Studio replaces the Viking theme and typography across the native screens, using the approved original text-free icon. The GitHub repository is now `RaDeleon/BrowserHelm`; its privacy and default branch were preserved, the checkout remote was updated. At the time of migration validation, source changes had not yet been committed or pushed.

## Regression and packaging

- Pre-migration baseline: 193/193 engine tests passed using bundled Python 3.12 and loopback permissions.
- Post-migration: 199/199 engine tests, including six identity/state migration tests; 24/24 release/native settings tests.
- Native release build passed; the staged and installed bundle use the BrowserHelm executable and `com.techinsf.browserhelm` bundle identifier.
- A transport regression subprocess initially omitted `-B` and generated unsigned stdlib bytecode caches in the installed runtime. Only those generated caches were removed; the harness now propagates `-B`. Deep/strict signature verification passed afterward.
- Installed `/Applications/BrowserHelm.app` deep/strict code signature verified.
- `BrowserHelm-0.5.0-arm64.dmg` packaged, mounted read-only and verified, including bundled Python imports and signature checks. SHA-256: `9840600616a9efb720531c7cd2ad72aae80372c48a77cb013cab4bfd912d2d92`.
- Local build is ad-hoc signed, not notarized; no public release or tag was created.

## State and connection migration

Settings were copied byte-for-byte; Jev remains the decision provider, DeepSeek V4.1 Flash via OpenRouter remains enabled for vision, and OpenViking remains enabled. The stable Keychain service was retained without exporting keys. The original app is archived outside Applications and its support directory remains intact for rollback.

SQLite backup preserved committed WAL contents and all recorded rows in the metrics, diagnostics and experience databases. Private row counts and local session inventories are omitted from this public summary.

Private backups were written for Codex TOML and Claude Desktop JSON. Only the recognized gateway server entries changed from openragnar to browserhelm and the installed launcher path. Other servers/settings were preserved. Claude Code had no top-level OpenRagnar gateway entry to migrate. Historical data/source namespaces and historical validation/release evidence retain compatibility.

## Live checks

- Installed gateway negotiated MCP 2025-11-25 and exposed all 29 tools, with only BrowserHelm helper names in the catalog.
- Fresh handshakes through both saved client commands returned BrowserHelm 0.5.0. Hidden legacy `openragnar_status` alias accepted; current `browserhelm_status` accepted.
- Owned example.com tab: DOM write, snapshot refs, act fill and independent readback passed; large-output retrieval passed; fixture tab was closed.
- Executor: six deterministic fixture tasks per path verified; batched extraction and expected escalation passed; bounded public navigation verified. This establishes behavior, not a new performance benchmark.
- Jev live decision test passed (jev-1.13.0, 351 input + 33 output tokens).
- DeepSeek model availability passed. One real screenshot point request on an owned local fixture located the correct blue tile; no click dispatched, memory disabled for the fixture, tab closed. OpenRouter reported 305 prompt + 18 completion tokens and $0.0000249084. The first harness attempt used an unsupported session-label SDK method and failed before any tab/vision request; the corrected attempt used the advertised name_session tool.
- Existing OpenViking connection passed; its stable experience collection is reused without re-embedding.
- Installed native UI opened with the new title, icon, cyan theme, sans-serif dashboard and preserved histories; the migrated explicit appearance preference was honored.
- Claude Desktop was idle, quit/reopened, and its actual active diagnostic connections report version 0.5.0 and the installed build fingerprint.

## Remaining client action

The current Codex chat cannot restart its own client while this work is active. Its saved new command has been verified, but its cached tool catalog reload has not been verified. Restart Codex or open a fresh chat, then confirm BrowserHelm 0.5.0 tools are loaded before calling client reconnection complete.

Raw local reports: `dist/browserhelm-install-report.json`, `dist/browserhelm-client-verification.json`, `dist/full-access-verification.json`, `dist/browserhelm-cloud-grounding.json`, `dist/executor-validation.json`, and the DMG verification report. No main-agent task benchmark was run for the name/UI change.
