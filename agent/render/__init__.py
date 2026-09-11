# -*- coding: utf-8 -*-
"""
[INPUT]: 无
[OUTPUT]: 对外转出 encode_video、frost_base、place_sharp、paint_copy
[POS]: render 模块门面
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from agent.render.canvas import frost_base, place_sharp
from agent.render.encode import encode_video
from agent.render.text import paint_copy

__all__ = ["encode_video", "frost_base", "place_sharp", "paint_copy"]
