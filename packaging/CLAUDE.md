# packaging/
> L2 | 父级: ../CLAUDE.md

成员清单
SportDesk.spec: PyInstaller 规格，收 web/static、assets、imageio-ffmpeg；darwin 才 BUNDLE
build_mac.sh: 本机打 SportDesk.app + dist/SportDesk-Mac.dmg（仅 Apple Silicon）
_python.bat: 找真 python.exe，跳过微软商店假入口
run_win.bat: Windows 免打包；纯 ASCII/CRLF；清华镜像；start 开浏览器
build_win.bat: 本机打 exe；拷到桌面 SportDesk\SportDesk.exe，并做 SportDesk.lnk

Mac 的 dist 里只有 dmg，永远没有 exe。「打开工作台.bat」也不生成 exe。要 exe：推 GitHub 等 Actions 下 zip，或在 Windows 上双击「生成Windows程序.bat」，等到出现 OK，去桌面看 SportDesk 文件夹。批处理必须是 CRLF，不能含中文，否则会报「不是内部或外部命令」。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
