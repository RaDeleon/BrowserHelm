# Third-party components and integrations

The root Apache-2.0 license applies to original OpenRagnar code. It does not replace licenses of third-party components or services.

## Packaged Python runtime

App builds include [Python-build-standalone](https://github.com/astral-sh/python-build-standalone), [CPython](https://github.com/python/cpython), and runtime extension dependencies, each under its own terms. The build system's license is distinct from licenses of the generated Python distribution.

Staging retains the installation's combined notices at `Contents/Resources/runtime/lib/python3.12/LICENSE.txt` and rejects a runtime missing that file. Binaries are not tracked in this repository. Builders must provide a complete Apple Silicon Python 3.12 installation and retain the notices associated with that distribution.

## External integrations

- **BrowserOS Neo:** https://github.com/browseros-ai/BrowserOS. AGPL-3.0 project providing execution through a separately running MCP server. Its browser/agent implementation is not bundled here.
- **OpenViking:** https://github.com/volcengine/OpenViking. Separately installed memory service accessed through HTTP. Its source/runtime is not bundled.
- **Decision providers:** TypeSafe AI / Jev, OpenRouter, Ollama and LM Studio are configurable external integrations. Users provide their own accounts or servers; provider terms/licenses remain separate.

Apple frameworks are supplied by macOS. The native Swift package has no third-party package dependencies. Names identify compatibility, not endorsement. Future vendored source/binaries must retain their notices and receive a license review before release.
