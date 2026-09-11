# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 agent.style 的画布常量
[OUTPUT]: 对外提供 Look、roll_look
[POS]: render 的每片视觉骰子，颜色 / 排版 / Ken Burns 掷一次用到底
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Tuple

Color = Tuple[int, int, int]

# 高对比、竖屏可读。每套是完整皮肤，不在渲染里拼颜色。
_PALETTES = (
    ((255, 255, 255), (18, 72, 230), (230, 36, 92), (255, 214, 42), (168, 18, 28), (255, 228, 64), (16, 16, 16)),
    ((255, 255, 255), (200, 16, 24), (255, 70, 40), (255, 220, 48), (140, 18, 18), (255, 255, 255), (20, 20, 20)),
    ((255, 214, 42), (24, 24, 24), (255, 140, 20), (255, 255, 255), (24, 24, 24), (255, 236, 90), (16, 16, 16)),
    ((255, 255, 255), (8, 132, 196), (40, 190, 255), (190, 240, 255), (8, 56, 110), (255, 255, 255), (10, 36, 72)),
    ((255, 255, 255), (16, 16, 16), (255, 255, 255), (255, 214, 42), (16, 16, 16), (255, 255, 255), (16, 16, 16)),
    ((255, 244, 248), (176, 18, 72), (255, 70, 120), (255, 255, 255), (120, 16, 48), (255, 220, 72), (40, 8, 20)),
)


@dataclass(frozen=True)
class Look:
    seed: int
    title_fill: Color
    title_stroke: Color
    title_glow: Color
    hook_fill: Color
    hook_stroke: Color
    body_fill: Color
    body_stroke: Color
    title_size: int
    hook_size: int
    body_size: int
    body_line: int
    align: str
    stack: str
    hook_tilt: float
    punch: str
    ken: str
    ken_amt: float
    frost_blur: int
    frost_dark: float
    vignette: float
    glow: bool
    cps: float
    type_delay: float
    end_hold: float
    fade_sec: float
    shuffle: bool
    title_stroke_w: int
    body_stroke_w: int


def roll_look(seed: int = None) -> Look:
    seed = int(seed if seed is not None else time.time_ns() % 2**31)
    rng = random.Random(seed)
    pal = rng.choice(_PALETTES)
    t_size = rng.choice((78, 84, 88, 94))
    h_size = rng.choice((44, 48, 52, 56))
    b_size = rng.choice((40, 44, 46, 50))
    return Look(
        seed=seed,
        title_fill=pal[0],
        title_stroke=pal[1],
        title_glow=pal[2],
        hook_fill=pal[3],
        hook_stroke=pal[4],
        body_fill=pal[5],
        body_stroke=pal[6],
        title_size=t_size,
        hook_size=h_size,
        body_size=b_size,
        body_line=b_size + rng.choice((18, 22, 26)),
        align=rng.choice(("center", "center", "left")),
        stack=rng.choice(("center", "center", "top", "bottom")),
        hook_tilt=rng.choice((-9.0, -5.0, 0.0, 0.0, 6.0, 10.0)),
        punch=rng.choice(("pop", "rise", "fade")),
        ken=rng.choice(("in", "out", "up", "down", "left", "right")),
        ken_amt=rng.choice((0.07, 0.10, 0.14, 0.18)),
        frost_blur=rng.choice((36, 48, 58)),
        frost_dark=rng.choice((0.52, 0.60, 0.68)),
        vignette=rng.choice((0.12, 0.22, 0.32)),
        glow=rng.choice((True, True, False)),
        cps=rng.choice((8.2, 9.0, 9.5, 10.6, 11.4)),
        type_delay=rng.choice((0.28, 0.42, 0.58)),
        end_hold=rng.choice((1.05, 1.35, 1.7)),
        fade_sec=rng.choice((0.26, 0.38, 0.52)),
        shuffle=rng.random() < 0.55,
        title_stroke_w=rng.choice((6, 7, 8)),
        body_stroke_w=rng.choice((4, 5, 6)),
    )
