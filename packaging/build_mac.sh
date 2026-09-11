#!/bin/sh
# [INPUT]: 项目 venv + PyInstaller + hdiutil
# [OUTPUT]: dist/SportDesk.app 与 dist/SportDesk-Mac.dmg
# [POS]: packaging 的 Mac 打包脚本
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/venv/bin/python"
"$PY" -m pip install -q pyinstaller
rm -rf "$ROOT/build" "$ROOT/dist/SportDesk" "$ROOT/dist/SportDesk.app"
"$PY" -m PyInstaller --noconfirm --clean "$ROOT/packaging/SportDesk.spec"
APP="$ROOT/dist/SportDesk.app"
if [ ! -d "$APP" ]; then
  echo "没有生成 SportDesk.app" >&2
  exit 1
fi
DMG="$ROOT/dist/SportDesk-Mac.dmg"
rm -f "$DMG"
hdiutil create -volname "热点短视频" -srcfolder "$APP" -ov -format UDZO "$DMG"
echo "MAC_APP $APP"
echo "MAC_DMG $DMG"
