# Building and releasing OpenRagnar

All build and packaging steps live in this repository. Codex is optional. Run on an Apple Silicon Mac with Xcode command-line tools and the standalone Python 3.12 runtime described in the root README.

## Branches

Develop on `codex/<feature>` branches. Review changes into `staging`, run the regression suites and app checks there, then promote a tested commit to `main` through a release PR. Tag that commit before sharing its DMG. CI accepts `staging` as well as `main` and feature branches. Creating a branch or committing code does not install an app or publish a release.

## Local testing while enrollment is pending

```sh
./script/build_and_run.sh --build
./script/package_dmg.sh
python3 script/verify_dmg.py
```

This creates an **ad-hoc signed app and a local test DMG**, not a notarized public release. Verification mounts the image read-only, validates code signatures and license notices, and imports the bundled Python SSL/SQLite libraries without using browser accounts, provider keys or a network connection.

For relocated browser and public HTTPS checks, with Neo running:

```sh
python3 script/verify_dmg.py --live
```

The scripts derive the image filename from the app's actual version and binary architecture. The checksum sidecar uses a relative filename and can be checked from the output directory with `shasum -a 256 -c OpenRagnar-0.4.3-arm64.dmg.sha256`.

`build_and_run.sh` stops the GUI process before rebuilding, preserving `--mcp` processes. To build an isolated artifact without stopping the GUI or replacing `dist/OpenRagnar.app`, use:

```sh
(cd mac-app && swift build -c release --disable-sandbox)
OPENRAGNAR_APP_OUTPUT=/private/tmp/openragnar-test/OpenRagnar.app python3 script/stage_app.py
./script/package_dmg.sh --app /private/tmp/openragnar-test/OpenRagnar.app --output-dir /private/tmp/openragnar-test
python3 script/verify_dmg.py /private/tmp/openragnar-test/OpenRagnar-0.4.3-arm64.dmg
```

Do not point `OPENRAGNAR_APP_OUTPUT` at the installed app during active MCP tasks. It is a build destination and replaces an existing bundle there.

## Public releases after enrollment

Install a **Developer ID Application** certificate and its private key in your macOS Keychain. List available signing identities with `security find-identity -v -p codesigning`. Use the full name of your own certificate:

```sh
export OPENRAGNAR_SIGNING_IDENTITY='Developer ID Application: Your Legal Name (YOURTEAMID)'
./script/build_and_run.sh --build
./script/package_dmg.sh
python3 script/notarize_dmg.py dist/OpenRagnar-0.4.3-arm64.dmg --check
```

The build signs every bundled Mach-O, including the Python executable and extension modules, followed by the app. Developer ID builds use Hardened Runtime and secure timestamps. The packaging step also signs the DMG. Release preflight verifies the Apple certificate requirement, signing team consistency, timestamps, Hardened Runtime and notices. Ad-hoc builds cannot pass.

Configure a named `notarytool` Keychain profile locally using Apple's interactive credential-storage workflow:

```sh
xcrun notarytool store-credentials openragnar-notary
```

Follow its prompts. Keep passwords, API private keys, exported signing keys and provisioning secrets out of the repository and command history. Scripts accept the profile **name**, not credentials.

The next command explicitly uploads the DMG to Apple. Run it only when ready to submit that artifact:

```sh
python3 script/notarize_dmg.py dist/OpenRagnar-0.4.3-arm64.dmg --submit --profile openragnar-notary
python3 script/verify_dmg.py dist/OpenRagnar-0.4.3-arm64.dmg --require-notarized --live
```

The submit script waits for Apple's `Accepted` result before stapling and validating the ticket. It regenerates the checksum because stapling changes the DMG. Rejected submissions never produce a success report. If a submission is interrupted or rejected, inspect its submission ID with `notarytool info`/`log` before submitting again; scripts never automatically resubmit.

Before publishing, test the downloaded, quarantined DMG on a separate Mac or clean user account with normal Gatekeeper settings. Install in Applications, connect a client, configure a provider, grant initial Keychain access and test an update from a prior signed version. Automated local verification alone does not prove that fresh-user onboarding or Keychain migration works.

Stable Developer ID signing lets Keychain recognize signed updates. Existing ad-hoc installs may need a one-time approval when changing signing identity. Notarization does not remove legitimate user permission prompts.

**Current status:** the local path is tested. The Developer ID submission path is prepared and covered by offline policy tests, but actual certificate signing, Apple acceptance and clean-machine installation remain unverified until enrollment is approved. The tag-triggered GitHub Actions workflow publishes verified preview DMGs to GitHub Releases. The local signing/notarization scripts do not publish to GitHub or the Mac App Store.

References: [Developer ID](https://developer.apple.com/developer-id/), [notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [custom notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).

## GitHub Releases

`.github/workflows/release.yml` runs when a `v*` tag is pushed. It validates the tag against `neo-personal/version.py` and requires corresponding `docs/release-notes/<version>.md` notes. Both Python 3.9 and 3.12 must pass gateway and release-tooling tests before the Apple Silicon macOS 15 job builds. The standalone Python runtime is pinned to an official archive and SHA-256 digest. CI verifies the read-only DMG, bundled runtime, HTTPS, signatures and checksum without accessing your browser or decision-provider credentials.

The publish job alone receives repository write permission. It uploads the DMG, checksum, verification JSON and source commit before publishing an ad-hoc **prerelease**. Published versions cannot be overwritten by rerunning the workflow; use a new version for a changed build. If publishing stopped while the release was still a draft, rerunning can replace its incomplete draft assets.

For each new version, update `VERSION` and increment `BUILD` in `neo-personal/version.py`, add release notes, test and promote the commit to `main`. Then:

```sh
git tag -a v0.4.3 -m "OpenRagnar 0.4.3 preview"
git push origin v0.4.3
```

The **Release DMG** workflow can also be run manually from Actions with an existing version tag. Use this only to recover a failed build or incomplete draft. Review its run and release assets before sharing the link. Releases in a private repository require repository access; this workflow does not change visibility.

Download: [OpenRagnar Releases](https://github.com/RaDeleon/OpenRagnar/releases). GitHub-hosted macOS builds in a private repository consume the account's Actions minutes. The workflow uses a standard Apple Silicon runner, documented in [GitHub's runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

On the development Mac, install each verified new version into `/Applications/OpenRagnar.app` after active MCP tasks finish, then reconnect clients and verify their reported version. A GitHub release itself does not update existing installed apps.
