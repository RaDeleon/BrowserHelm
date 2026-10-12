# Source publication review

The product is **BrowserHelm**. The default-branch README must be updated with the renamed source before sharing it publicly. Current source/app version is 0.5.1; the earlier published preview is OpenRagnar 0.4.3. A new release requires the separately documented tag/build/publish workflow.

## Included folders

- `mac-app/`: native Swift source and original app artwork.
- `neo-personal/`: engine source, tests and a synthetic HTML fixture. The directory name and `openragnar.py` compatibility import remain stable; they are not private user data.
- `benchmarks/`: harness source, synthetic workloads and oracle tests. These make the published measurements reproducible.
- `docs/`: guides, release notes, diagrams and sanitized validation summaries. Historical OpenRagnar names preserve the identity of measured builds.
- `script/`: reproducible build/release tools and opt-in live validation scripts. Live checks can affect a browser or contact paid providers; they do not run just because the source is downloaded.
- `.github/` and `.githooks/`: workflow and commit-hook templates. Credentials come from the user's Keychain, private configuration or GitHub Actions secrets, not committed values.

## Excluded local material

`dist/`, Swift build directories, the separate `BrowserOS/` checkout, `.tools/`, local code indexes/agent state, design drafts and internal backlog stay ignored. Generated logs, databases, settings, captures, raw benchmark output, private audit reports and signing material are blocked by the artifact policy. Gitignore does not remove files previously committed.

Commit checks reject recognized private/generated paths, including force-added files. App staging/DMG verification rejects local/test artifacts and unexpected app resources. These are preventive controls, not a guarantee against every possible disclosure.

## Review before publication

Review the actual files in the proposed commit, run the redacted secret check on staged content and all branch/tag history, and check packaged downloads independently. Keep current source version, published release version and historical benchmark versions distinct. Local Codex checkpoint refs are private recovery data and must not be mirror-pushed. Do not change repository visibility or rewrite history as part of a documentation cleanup.

```sh
python3 script/check_secrets.py --staged
python3 script/check_secrets.py --history
git diff --cached --stat
```

See [secret/artifact checks](secret-checks.md), [the release workflow](releases.md) and [the documented audit scope and limitations](validation/2026-10-11-pre-publication-secrets.md).
