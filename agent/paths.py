# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 sys / pathlib
[OUTPUT]: 对外提供 frozen、bundle_dir、work_dir、asset_dir
[POS]: agent 的路径宪法；安装包读 _MEIPASS，成片与缓存写用户目录
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def work_dir() -> Path:
    if frozen():
        path = Path.home() / "SportDesk"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return bundle_dir()


def asset_dir() -> Path:
    return bundle_dir() / "assets"
