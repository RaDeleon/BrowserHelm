# Client removal controls — BrowserHelm 0.5.1

Added Connect/Remove controls for Claude Desktop and Codex to Settings → MCP clients and Connectors. Removal requires the native confirmation and removes only the matching BrowserHelm stdio entry. Existing sessions remain until the client restarts. Other connectors, settings, keys, metrics and experience memory are retained.

Validation: 206 engine tests and 24 release/native-settings tests passed. Seven new removal tests cover TOML nested/quoted tables, unrelated bytes/settings preservation, private backups, Claude JSON preservation, missing-entry no-op, sole-server removal, conflicts/invalid input, symlinks and concurrent changes.

Built and installed BrowserHelm 0.5.1 build 19 in Applications. Previous 0.5.0 app retained privately for rollback; settings hash unchanged. Installed code signature and fresh Neo/client handshakes verified. Native Settings displayed both Remove buttons; the Codex confirmation was opened and canceled, leaving the live connection configured. Tests removed only temporary fixture configurations, not the user's real connectors.

At the time of this validation, source changes were local and uncommitted. Existing client processes may still require a new chat/restart to load the latest cached catalog; the saved launch commands report 0.5.1.
