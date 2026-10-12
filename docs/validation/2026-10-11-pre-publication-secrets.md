# BrowserHelm pre-publication credential/privacy audit — 2026-10-11

Target verified as `RaDeleon/BrowserHelm` (formerly OpenRagnar). GitHub visibility remains **private**. This was a secrets/privacy review, not a full application vulnerability audit. No visibility change, history rewrite, commit or push was performed.

## Results

No credential findings were detected by checksum-verified Gitleaks 8.30.1 in:

- All fetched branch/tag history: 17 reachable commits, non-shallow checkout. An additional exact-value comparison checked 325 historical file blobs and current commit-eligible files against the saved Jev credential, including base64 and URL-encoded forms; no matches.
- Tracked files and unignored pending BrowserHelm changes. The final scan, including the audit documentation and new prevention files, covered 139 commit-eligible files with zero findings.
- Published v0.4.3 release assets, its read-only-mounted app bundle, and the local BrowserHelm app bundle. No saved settings, Keychain exports, user databases, logs or private signing files were packaged. Printable strings in both native executables were also scanned.
- All seven GitHub issue/PR descriptions and their available discussion text, plus inline PR review comments.
- Local offline OCR of 10 unique current/historical image assets: all recognized successfully, no secret findings, credential prefixes or email patterns. No images were sent to a cloud model for this audit.

Email/credential-URL pattern hits in source were synthetic validation fixtures; raw-transcript-like field names were task schema code. No real private endpoint credentials or personal Mac paths were detected in commit-eligible text.

## Privacy detail and limits

Git author/committer metadata includes one identity using an email address other than GitHub's no-reply addresses. Publishing exposes that existing metadata. No author identity or Git history was rewritten. Using a no-reply address for future commits would not change old commits.

The optional OpenRouter exact-value comparison was unavailable because macOS Keychain required approval. Its credential format was covered by pattern scanning and a generated invalid fixture was detected. The exact Jev comparison succeeded. Coverage does not include every old rotated value, unknown remote object or later change. Unusual encodings may evade detection. OCR/pattern scanners can miss data; the result is **no detected secrets in the reviewed scope**, not a guarantee.

## Prevention added locally

- `script/check_secrets.py`: pinned official scanner/checksums, redacted output, staged/history modes and failure blocking.
- `.githooks/pre-commit` and the current checkout's Git hook: clean staged data passes; a generated invalid OpenRouter token and binary signing-key export block; a safe `.env.example` passes. These checks used a disposable Git repository, not the real index.
- `.github/workflows/secrets.yml`: full-depth Git history scan for pushes/PRs; pending commit/push.
- `.gitignore`: added `.tools/`, benchmark preflight metadata and `.p12`/`.pfx` exports; existing environment/key/log/database/output exclusions retained.

Reports with redacted findings and private audit material stay outside the repository in owner-restricted temporary storage. Setup and limitations: [secret checks](../secret-checks.md). Scanner source/release: [Gitleaks](https://github.com/gitleaks/gitleaks), [v8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1).
