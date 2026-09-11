# -*- coding: utf-8 -*-
"""
[INPUT]: 无
[OUTPUT]: 对外转出 download_images、build_soundtrack、load_fonts、default_bgm、pick_bgm
[POS]: media 模块门面
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from agent.media.audio import build_soundtrack, preview_wav
from agent.media.bgm import DEFAULT_BGM, default_bgm, list_tracks, pick_bgm, resolve_track, save_upload
from agent.media.fonts import load_fonts
from agent.media.images import download_images

__all__ = [
    "DEFAULT_BGM",
    "default_bgm",
    "build_soundtrack",
    "list_tracks",
    "load_fonts",
    "pick_bgm",
    "download_images",
    "preview_wav",
    "resolve_track",
    "save_upload",
]
