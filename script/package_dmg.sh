#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT_DIR/dist/OpenRagnar.app"
DMG="$ROOT_DIR/dist/OpenRagnar-0.4.0-arm64.dmg"
STAGE="$(mktemp -d /private/tmp/openragnar-dmg.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT
/usr/bin/xattr -d com.apple.FinderInfo "$APP" 2>/dev/null || true
/usr/bin/codesign --verify --deep --strict "$APP"
mkdir -p "$STAGE"
/usr/bin/ditto --norsrc --noextattr "$APP" "$STAGE/OpenRagnar.app"
ln -sfn /Applications "$STAGE/Applications"
cp "$ROOT_DIR/README-OpenRagnar.md" "$STAGE/START-HERE.md"
/usr/bin/hdiutil create -volname OpenRagnar -srcfolder "$STAGE" -ov -format UDZO "$DMG"
/usr/bin/hdiutil verify "$DMG"
/usr/bin/shasum -a 256 "$DMG" > "$DMG.sha256"
printf 'DMG: %s\n' "$DMG"
