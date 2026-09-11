# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖系统中文字体与可选 assets/fonts，接收字号
[OUTPUT]: 对外提供 load_fonts(title, hook, body)
[POS]: media 的字体解析器，Mac PingFang / Win 微软雅黑 / 包内字体
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import ImageFont

from agent.paths import asset_dir
from agent.style import BODY_SIZE, HOOK_SIZE, TITLE_SIZE


def _candidates() -> List[Tuple[Path, int]]:
    bag: List[Tuple[Path, int]] = []
    fonts = asset_dir() / "fonts"
    if fonts.is_dir():
        for path in sorted(fonts.iterdir()):
            if path.suffix.lower() in {".otf", ".ttf", ".ttc"}:
                bag.append((path, 0))
    bag.extend(
        [
            (Path("/System/Library/Fonts/PingFang.ttc"), 11),
            (Path("/Library/Fonts/PingFang.ttc"), 11),
            (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),
            (Path("C:/Windows/Fonts/msyh.ttc"), 0),
            (Path("C:/Windows/Fonts/msyhbd.ttc"), 0),
            (Path("C:/Windows/Fonts/simhei.ttf"), 0),
            (Path("C:/Windows/Fonts/simsun.ttc"), 0),
        ]
    )
    root = Path("/System/Library/AssetsV2")
    if root.exists():
        bag.extend((p, 11) for p in sorted(root.glob("**/PingFang.ttc")))
    return bag


def _pick() -> Tuple[Path, int]:
    for path, index in _candidates():
        if path.is_file():
            return path, index
    raise RuntimeError("找不到中文字体，请把 .otf/.ttf 放到 SportDesk 资源 fonts 目录")


def load_fonts(title_size: int = TITLE_SIZE, hook_size: int = HOOK_SIZE, body_size: int = BODY_SIZE):
    path, index = _pick()
    title = ImageFont.truetype(str(path), title_size, index=index)
    hook = ImageFont.truetype(str(path), hook_size, index=index)
    body = ImageFont.truetype(str(path), body_size, index=index)
    return title, hook, body
