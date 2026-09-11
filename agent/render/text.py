# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 PIL、agent.style、agent.media.fonts、agent.render.look
[OUTPUT]: 对外提供 CopyPack、paint_copy、wrap_body、type_plan、click_times
[POS]: render 的文字层，CopyPack 排版一次并缓存标题光晕，打字机只描可见字
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from agent.media.fonts import load_fonts
from agent.render.look import Look
from agent.style import (
    CANVAS,
    END_HOLD,
    FPS,
    HEIGHT,
    MARGIN_X,
    MIN_DURATION,
    SAFE_BOTTOM,
    SAFE_TOP,
    TYPE_CPS,
    TYPE_DELAY,
    WIDTH,
)

_FONT_BAG: Dict[Tuple[int, int, int], tuple] = {}
_DUMMY = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def fonts(look: Optional[Look] = None):
    key = (look.title_size, look.hook_size, look.body_size) if look else (88, 50, 46)
    if key not in _FONT_BAG:
        _FONT_BAG[key] = load_fonts(*key)
    return _FONT_BAG[key]


def _span(text: str, font: ImageFont.FreeTypeFont, stroke: int) -> Tuple[int, int]:
    box = _DUMMY.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return box[2] - box[0], box[0]


def wrap_lines(text: str, font: ImageFont.FreeTypeFont, stroke: int, max_w: Optional[int] = None) -> List[str]:
    limit = WIDTH - MARGIN_X * 2 if max_w is None else max(24, max_w)
    lines: List[str] = []
    line = ""
    for ch in text or "":
        trial = line + ch
        w, _ = _span(trial, font, stroke)
        if w > limit and line:
            lines.append(line)
            line = ch
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def wrap_body(text: str, font: ImageFont.FreeTypeFont) -> List[str]:
    return wrap_lines(text, font, 5)


def _anchor_x(text: str, font: ImageFont.FreeTypeFont, align: str, stroke: int) -> int:
    w, origin = _span(text, font, stroke)
    room = WIDTH - MARGIN_X * 2
    if w >= room or align == "left":
        left = MARGIN_X
    else:
        left = (WIDTH - w) // 2
        left = min(max(left, MARGIN_X), WIDTH - MARGIN_X - w)
    return left - origin


def _band(count: int, size: int, gap: int) -> int:
    return count * (size + gap) - gap if count else 0


def _tilt_pad(lines: Sequence[str], font: ImageFont.FreeTypeFont, tilt: float) -> int:
    if not tilt or not lines:
        return 0
    widest = max(_span(line, font, 5)[0] for line in lines)
    return int(abs(math.sin(math.radians(tilt))) * widest * 0.5) + 8


def _fit_y(block: int, stack: str, room: int) -> int:
    floor = HEIGHT - SAFE_BOTTOM - block - room
    if stack == "top":
        wanted = 132
    elif stack == "bottom":
        wanted = HEIGHT - block - 160 - room
    else:
        wanted = (HEIGHT - block) // 2
    return min(max(wanted, SAFE_TOP), max(SAFE_TOP, floor))


def type_plan(body: str, look: Optional[Look] = None) -> List[int]:
    cps = look.cps if look else TYPE_CPS
    delay = int((look.type_delay if look else TYPE_DELAY) * FPS)
    hold = int((look.end_hold if look else END_HOLD) * FPS)
    frames: List[int] = [0] * delay
    acc = delay
    for i, ch in enumerate(body, start=1):
        step = FPS / cps
        if ch in "，、；：":
            step += FPS * 0.07
        elif ch in "。！？":
            step += FPS * 0.16
        acc += step
        while len(frames) < int(acc):
            frames.append(i)
    frames.extend([len(body)] * hold)
    min_frames = int(MIN_DURATION * FPS)
    if len(frames) < min_frames:
        frames.extend([len(body)] * (min_frames - len(frames)))
    return frames


def click_times(plan: Sequence[int]) -> List[float]:
    times: List[float] = []
    last = 0
    for i, n in enumerate(plan):
        if n > last:
            times.append(i / FPS)
            last = n
    return times


def _shown_lines(lines: Sequence[str], n_chars: int) -> List[str]:
    shown: List[str] = []
    left = max(0, n_chars)
    for line in lines:
        if left <= 0:
            break
        shown.append(line[:left])
        left -= len(line)
    return shown


def _punch_off(punch: float, kind: str) -> Tuple[int, int]:
    t = 1.0 - min(1.0, max(0.0, punch))
    if kind == "rise":
        return 0, int(t * 48)
    if kind == "fade":
        return 0, 0
    return 0, int(t * 12)


def _stroked(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    stroke: Tuple[int, int, int],
    width: int,
    fake_bold: bool = False,
) -> None:
    x, y = xy
    shifts = [(0, 0), (1, 0), (0, 1), (1, 1)] if fake_bold else [(0, 0)]
    for dx, dy in shifts:
        draw.text((x + dx, y + dy), text, font=font, fill=fill, stroke_width=width, stroke_fill=stroke)


class CopyPack:
    """排版只量一次；标题光晕按 punch 缓存，正文逐帧只描可见字。"""

    def __init__(self, title: str, hook: str, body: str, look: Optional[Look] = None):
        self.look = look
        title_font, hook_font, body_font = fonts(look)
        align = look.align if look else "center"
        stack = look.stack if look else "center"
        kind = look.punch if look else "pop"
        t_fill = look.title_fill if look else (255, 255, 255)
        t_stroke = look.title_stroke if look else (18, 72, 230)
        t_glow = look.title_glow if look else (230, 36, 92)
        h_fill = look.hook_fill if look else (255, 214, 42)
        h_stroke = look.hook_stroke if look else (168, 18, 28)
        b_fill = look.body_fill if look else (255, 228, 64)
        b_stroke = look.body_stroke if look else (16, 16, 16)
        t_w = look.title_stroke_w if look else 7
        b_w = look.body_stroke_w if look else 5
        t_size = look.title_size if look else 88
        h_size = look.hook_size if look else 50
        line_h = look.body_line if look else 70
        tilt = look.hook_tilt if look else 0.0
        use_glow = look.glow if look else True
        t_measure = max(t_w, 18 if use_glow else t_w) + 1

        title_lines = wrap_lines(title, title_font, t_measure)
        hook_w = WIDTH - MARGIN_X * 2
        hook_lines = wrap_lines(hook, hook_font, 5, hook_w)
        pad = _tilt_pad(hook_lines, hook_font, tilt)
        if pad:
            hook_lines = wrap_lines(hook, hook_font, 5, hook_w - pad * 2)
            pad = _tilt_pad(hook_lines, hook_font, tilt)
        body_lines = wrap_lines(body, body_font, b_w)

        room = 48 if kind == "rise" else (12 if kind == "pop" else 0)
        avail = HEIGHT - SAFE_TOP - SAFE_BOTTOM - room
        while True:
            title_h = _band(len(title_lines), t_size, 12)
            hook_h = _band(len(hook_lines), h_size, 10)
            body_h = len(body_lines) * line_h
            block = title_h + 20 + hook_h + pad * 2 + 60 + body_h
            if block <= avail or line_h <= 52:
                break
            line_h -= 2
        y0 = _fit_y(block, stack, room)
        self.title_font = title_font
        self.hook_font = hook_font
        self.body_font = body_font
        self.align = align
        self.kind = kind
        self.title_lines = title_lines
        self.hook_lines = hook_lines
        self.body_lines = body_lines
        self.hook_h = hook_h
        self.pad = pad
        self.y0 = y0
        self.t_fill = t_fill
        self.t_stroke = t_stroke
        self.t_glow = t_glow
        self.h_fill = h_fill
        self.h_stroke = h_stroke
        self.b_fill = b_fill
        self.b_stroke = b_stroke
        self.t_w = t_w
        self.b_w = b_w
        self.t_size = t_size
        self.h_size = h_size
        self.line_h = line_h
        self.tilt = tilt
        self.use_glow = use_glow
        self.t_measure = t_measure
        self.title_span = len(title_lines) * (t_size + 12)
        self.hook_span = len(hook_lines) * (h_size + 10)
        self._heads: Dict[int, Image.Image] = {}
        self._body_key: Optional[Tuple[int, int]] = None
        self._body_img: Optional[Image.Image] = None

    def _punch_key(self, punch: float) -> int:
        return 12 if punch >= 1.0 else int(min(1.0, max(0.0, punch)) * 12)

    def _header(self, punch: float) -> Image.Image:
        key = self._punch_key(punch)
        cached = self._heads.get(key)
        if cached is not None:
            return cached
        dx, dy = _punch_off(punch, self.kind)
        alpha = int(255 * punch) if self.kind == "fade" else 255
        layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        glow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        hook_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        draw = ImageDraw.Draw(layer)
        hdraw = ImageDraw.Draw(hook_layer)
        y = self.y0 + dy
        for line in self.title_lines:
            tx = _anchor_x(line, self.title_font, self.align, self.t_measure) + dx
            if self.use_glow:
                _stroked(gdraw, (tx, y), line, self.title_font, self.t_glow, self.t_glow, 18, True)
            _stroked(draw, (tx, y), line, self.title_font, self.t_fill, self.t_stroke, self.t_w, True)
            y += self.t_size + 12
        if self.title_lines:
            y += 8
            glow = glow.filter(ImageFilter.GaussianBlur(2))
        hy = y + self.pad
        for line in self.hook_lines:
            hx = _anchor_x(line, self.hook_font, self.align, 5) + dx
            _stroked(hdraw, (hx, hy), line, self.hook_font, self.h_fill, self.h_stroke, 5, True)
            hy += self.h_size + 10
        if self.tilt and self.hook_lines:
            cy = y + self.pad + self.hook_h // 2
            hook_layer = hook_layer.rotate(self.tilt, resample=Image.Resampling.BICUBIC, center=(WIDTH // 2, cy))
        if alpha < 255:
            for im in (glow, layer, hook_layer):
                a = im.split()[-1].point(lambda v: int(v * alpha / 255))
                im.putalpha(a)
        header = Image.alpha_composite(glow, layer)
        header = Image.alpha_composite(header, hook_layer)
        self._heads[key] = header
        return header

    def _body_layer(self, n_chars: int, punch: float) -> Image.Image:
        key = (n_chars, self._punch_key(punch))
        if key == self._body_key and self._body_img is not None:
            return self._body_img
        dx, dy = _punch_off(punch, self.kind)
        alpha = int(255 * punch) if self.kind == "fade" else 255
        y = self.y0 + dy + self.title_span
        if self.title_lines:
            y += 8
        y = y + self.pad + self.hook_span + self.pad + 36
        layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for line in _shown_lines(self.body_lines, n_chars):
            lx = _anchor_x(line, self.body_font, self.align, self.b_w) + dx
            _stroked(draw, (lx, y), line, self.body_font, self.b_fill, self.b_stroke, self.b_w)
            y += self.line_h
        if alpha < 255:
            a = layer.split()[-1].point(lambda v: int(v * alpha / 255))
            layer.putalpha(a)
        self._body_key = key
        self._body_img = layer
        return layer

    def stamp(self, base: Image.Image, n_chars: int, punch: float = 1.0) -> Image.Image:
        out = base.convert("RGBA")
        out = Image.alpha_composite(out, self._header(punch))
        out = Image.alpha_composite(out, self._body_layer(n_chars, punch))
        return out.convert("RGB")


def paint_copy(
    base: Image.Image,
    title: str,
    hook: str,
    body: str,
    n_chars: int,
    punch: float = 1.0,
    look: Optional[Look] = None,
) -> Image.Image:
    return CopyPack(title, hook, body, look).stamp(base, n_chars, punch)
