# Checking commits for secrets

`script/check_secrets.py` runs Gitleaks 8.30.1 locally with fully redacted findings. The first run downloads the official scanner archive and verifies a pinned SHA-256; later runs verify and reuse the ignored `.tools/` cache. Source and credentials are not uploaded to a scanning service. macOS/Linux ARM64 and x86-64 are supported.

```sh
python3 script/check_secrets.py --staged
python3 script/check_secrets.py --history
```

Staged mode rejects private configuration, signing-key exports, databases, logs, raw captures, local agent state and generated benchmark output before scanning contents, including files force-added past `.gitignore`. `.env.example` remains eligible as a template. History mode scans patches across all locally available Git refs. Fetch all branches/tags first for complete local reachable-history coverage.

The local pre-commit hook is installed in the audited development checkout. Hooks do not activate automatically on clone. For another checkout, install `.githooks/pre-commit` at the path reported by `git rev-parse --git-path hooks/pre-commit`, mark it executable, and preserve or explicitly compose any existing hook rather than replacing it. Scanner/download/check failures block the commit; findings are redacted. Do not bypass the check to publish a credential.

`.github/workflows/secrets.yml` adds a full-history check to push and PR CI using a full-depth checkout. It becomes active when committed/pushed; it does not undo a secret already uploaded. A pre-commit check complements CI.

If a real credential is found, keep its value out of issues, PRs and logs. Rotate/revoke it and review all affected history and release artifacts before publishing. Removing a file or adding an ignore rule does not remove its old commits. History rewrites and repository visibility changes require an explicit request.

Scanner findings and exact-key comparisons are not an absolute guarantee. Review binary assets, discussion text, identity metadata and private configuration as well. The [pre-publication audit](validation/2026-10-11-pre-publication-secrets.md) records the current evidence and limitations. Scanner behavior: [official Gitleaks documentation](https://github.com/gitleaks/gitleaks).

## Keeping local artifacts out of downloads

`.gitignore` excludes generated test reports, diagnostics, browser captures, logs, databases, local settings, scanner output, build archives and discarded design prototypes. Test code, synthetic fixtures, product assets and sanitized benchmark Markdown remain available so contributors can reproduce the published results. Local files remain on disk; ignored files are not deleted. Ignore rules do not remove files already tracked or committed in older history.

`script/artifact_policy.py` shares the artifact rules between commit checks and app verification. The app staging and release checks reject test folders, debug output and private state, and allow only the expected app resources and engine modules. DMG packaging verifies the app before copying it. Generated reports belong in the ignored `dist/` directory, never in the app bundle or downloadable source.
