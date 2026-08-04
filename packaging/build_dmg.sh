#!/usr/bin/env bash
# Build a standalone CueKey.app and wrap it in a distributable DMG.
#
# Usage: packaging/build_dmg.sh   (run from anywhere; needs the dev venv)
# Output: dist/CueKey-<version>.dmg
set -euo pipefail

cd "$(dirname "$0")/.."
VENV="${VENV:-.venv}"

"$VENV/bin/pip" install --quiet pyinstaller

VERSION="$("$VENV/bin/python" -c 'import cuekey; print(cuekey.__version__)')"

echo "==> Building CueKey.app v$VERSION"
"$VENV/bin/pyinstaller" --noconfirm --clean \
    --windowed \
    --name CueKey \
    --icon packaging/icon.icns \
    --osx-bundle-identifier dev.cuekey.app \
    --collect-submodules librosa \
    --collect-data librosa \
    --collect-data cuekey \
    packaging/cuekey_gui_entry.py

APP="dist/CueKey.app"
test -d "$APP" || { echo "app bundle missing"; exit 1; }

# Stamp the real version into the bundle (crash reports otherwise say 0.0.0),
# then re-apply the ad-hoc signature invalidated by the plist edit.
for key in CFBundleShortVersionString CFBundleVersion; do
    /usr/libexec/PlistBuddy -c "Set :$key $VERSION" "$APP/Contents/Info.plist" 2>/dev/null \
        || /usr/libexec/PlistBuddy -c "Add :$key string $VERSION" "$APP/Contents/Info.plist"
done
codesign --force --deep -s - "$APP"

if [ -z "${CUEKEY_SKIP_SMOKE:-}" ]; then
    echo "==> Smoke testing the bundled app"
    CUEKEY_SMOKE=1 "$APP/Contents/MacOS/CueKey"
else
    echo "==> Skipping smoke test (CUEKEY_SKIP_SMOKE set)"
fi

echo "==> Creating DMG"
STAGE="dist/dmg-stage"
DMG="dist/CueKey-$VERSION${CUEKEY_DMG_SUFFIX:+-$CUEKEY_DMG_SUFFIX}.dmg"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "CueKey $VERSION" -srcfolder "$STAGE" -format UDZO -quiet "$DMG"
rm -rf "$STAGE"

du -sh "$DMG"
echo "==> Done: $DMG"
echo "    First launch on another Mac: right-click CueKey.app > Open (unsigned build)."
