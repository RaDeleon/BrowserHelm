#!/bin/bash
set -euo pipefail
MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT_DIR/dist/BrowserHelm.app"
# Never stop a --mcp child that an active agent may be using.
for pid in $(pgrep -x BrowserHelm || true); do
  args=$(ps -p "$pid" -o args=)
  if [[ "$args" != *"--mcp"* ]]; then kill "$pid" || true; fi
done
export CLANG_MODULE_CACHE_PATH="$ROOT_DIR/mac-app/.build/module-cache"
export SWIFTPM_MODULECACHE_OVERRIDE="$CLANG_MODULE_CACHE_PATH"
cd "$ROOT_DIR/mac-app"
swift build -c release --disable-sandbox
cd "$ROOT_DIR"
/usr/bin/python3 "$ROOT_DIR/script/stage_app.py"
case "$MODE" in
  --build) ;;
  run) /usr/bin/open -n "$APP" ;;
  --verify) /usr/bin/open -n "$APP"; sleep 1; pgrep -x BrowserHelm >/dev/null ;;
  --debug) lldb "$APP/Contents/MacOS/BrowserHelm" ;;
  --logs|--telemetry) /usr/bin/open -n "$APP"; /usr/bin/log stream --info --style compact --predicate 'subsystem == "com.techinsf.browserhelm" OR process == "BrowserHelm"' ;;
  *) echo 'Usage: script/build_and_run.sh [--build|--verify|--debug|--logs|--telemetry]' >&2; exit 2 ;;
esac
