# -*- mode: python ; coding: utf-8 -*-
"""
[INPUT]: 依赖 PyInstaller、项目根 sport_desk.py / web/static / assets
[OUTPUT]: 打出 SportDesk.app（macOS）或 SportDesk.exe（Windows）
[POS]: packaging 的规格书，双系统共用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all

root = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [
    (os.path.join(root, "web", "static"), os.path.join("web", "static")),
    (os.path.join(root, "assets"), "assets"),
]
binaries = []
hidden = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on",
    "web.app",
    "agent",
    "numpy",
    "PIL",
    "imageio_ffmpeg",
]
pkg_datas, pkg_bins, pkg_hidden = collect_all("imageio_ffmpeg")
datas += pkg_datas
binaries += pkg_bins
hidden += pkg_hidden

a = Analysis(
    [os.path.join(root, "sport_desk.py")],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SportDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=(sys.platform == "win32"),
    disable_windowed_traceback=False,
    argv_emulation=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SportDesk",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SportDesk.app",
        icon=None,
        bundle_identifier="com.sportdesk.agent",
        info_plist={
            "CFBundleName": "热点短视频",
            "CFBundleDisplayName": "热点短视频",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )

