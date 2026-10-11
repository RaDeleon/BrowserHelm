# OpenRagnar development instructions

<!-- codebase-memory-mcp:start -->
For structural codebase exploration, use the installed `codebase-memory` skill.
<!-- codebase-memory-mcp:end -->

## Installing updated builds

- After validating a new OpenRagnar app build, install it at `/Applications/OpenRagnar.app`. Creating a DMG or staging a copy in `dist/` does not complete the update.
- Preserve the user's settings, Keychain entries, metrics, diagnostics, and experience memory during installation.
- Wait for active MCP/browser tasks to finish before replacing the installed app; do not interrupt their work to update it.
- Verify the installed version and code signature. Reconnect MCP clients after installation and confirm they report the new version before calling the update complete.
