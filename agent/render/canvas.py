# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 PIL、numpy、agent.style、agent.render.look
[OUTPUT]: 对外提供 frost_base、prepare_sheet、place_sharp、blend_frames
[POS]: render 的画面基底，毛玻璃降采样模糊；Ken Burns 一次放大，逐帧只裁切
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from agent.render.look import Look
from agent.style import CANVAS, FROST_BLUR, FROST_DARKEN, HEIGHT, KEN_BURNS, WIDTH


def _cover(img: Image.Image, size: Tuple[int, int], resample) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    nw, nh = int(img.width * scale + 1), int(img.height * scale + 1)
    fitted = img.resize((nw, nh), resample)
    x = max(0, (nw - tw) // 2)
    y = max(0, (nh - th) // 2)
    return fitted.crop((x, y, x + tw, y + th))


def _vignette(frost: Image.Image, vig: float) -> Image.Image:
    pix = np.asarray(frost, dtype=np.float32)
    h = pix.shape[0]
    yy = np.arange(h, dtype=np.float32) / max(1, h - 1)
    top = 0.12 + vig * 0.4
    bot = 0.22 + vig * 0.5
    shade = np.ones(h, dtype=np.float32)
    shade -= np.clip((top - yy) / max(top, 1e-6), 0, 1) * min(1.0, vig * 1.1)
    shade -= np.clip((yy - (1.0 - bot)) / max(bot, 1e-6), 0, 1) * min(1.0, vig * 1.25)
    shade = np.clip(shade, 0.0, 1.0).reshape(h, 1, 1)
    return Image.fromarray(np.clip(pix * shade, 0, 255).astype(np.uint8), "RGB")


def frost_base(photo: Image.Image, look: Optional[Look] = None) -> Image.Image:
    blur = look.frost_blur if look else FROST_BLUR
    dark = look.frost_dark if look else FROST_DARKEN
    vig = look.vignette if look else 0.22
    covered = _cover(photo.convert("RGB"), CANVAS, Image.Resampling.BILINEAR)
    small = covered.resize((WIDTH // 4, HEIGHT // 4), Image.Resampling.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(max(1, blur // 4)))
    frost = small.resize(CANVAS, Image.Resampling.BILINEAR)
    frost = ImageEnhance.Brightness(frost).enhance(dark)
    return _vignette(frost, vig)


def _focal(ken: str, progress: float) -> Tuple[float, float, float]:
    p = min(1.0, max(0.0, progress))
    amt = 0.10
    if ken == "out":
        return 0.5, 0.5, 1.0 + amt * (1.0 - p)
    if ken == "left":
        return 0.32 + 0.36 * p, 0.5, 1.0 + amt * 0.5
    if ken == "right":
        return 0.68 - 0.36 * p, 0.5, 1.0 + amt * 0.5
    if ken == "up":
        return 0.5, 0.64 - 0.28 * p, 1.0 + amt * 0.45
    if ken == "down":
        return 0.5, 0.36 + 0.28 * p, 1.0 + amt * 0.45
    return 0.5, 0.5, 1.0 + amt * p


def _max_zoom(look: Optional[Look]) -> float:
    amt = look.ken_amt if look else KEN_BURNS
    return 1.0 + amt


def prepare_sheet(photo: Image.Image, look: Optional[Look] = None) -> Image.Image:
    zmax = _max_zoom(look)
    scale = (WIDTH / max(1, photo.width)) * zmax
    nw = max(1, int(photo.width * scale))
    nh = max(1, int(photo.height * scale))
    return photo.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)


def place_sharp(frost: Image.Image, sheet: Image.Image, progress: float, look: Optional[Look] = None) -> Image.Image:
    ken = look.ken if look else "in"
    amt = look.ken_amt if look else KEN_BURNS
    fx, fy, zoom = _focal(ken, progress)
    zoom = 1.0 + (zoom - 1.0) * (amt / 0.10)
    zmax = 1.0 + amt
    nw = max(1, int(round(sheet.width * zoom / zmax)))
    nh = max(1, int(round(sheet.height * zoom / zmax)))
    if nh >= HEIGHT:
        view_w = min(sheet.width, max(1, int(round(WIDTH * zmax / zoom))))
        view_h = min(sheet.height, max(1, int(round(HEIGHT * zmax / zoom))))
        left = int(max(0, min(sheet.width - view_w, (sheet.width - view_w) * fx)))
        top = int(max(0, min(sheet.height - view_h, (sheet.height - view_h) * fy)))
        crop = sheet.crop((left, top, left + view_w, top + view_h))
        if crop.size != CANVAS:
            crop = crop.resize(CANVAS, Image.Resampling.BILINEAR)
        return crop
    canvas = frost.copy()
    sharp = sheet if (nw, nh) == sheet.size else sheet.resize((nw, nh), Image.Resampling.BILINEAR)
    if sharp.width > WIDTH:
        sleft = int(max(0, min(sharp.width - WIDTH, (sharp.width - WIDTH) * fx)))
        sharp = sharp.crop((sleft, 0, sleft + WIDTH, nh))
        left = 0
    else:
        left = (WIDTH - sharp.width) // 2
    y = int((HEIGHT - sharp.height) * fy)
    y = max(0, min(HEIGHT - sharp.height, y))
    canvas.paste(sharp, (left, y))
    return canvas


def blend_frames(a: Image.Image, b: Image.Image, alpha: float) -> Image.Image:
    alpha = min(1.0, max(0.0, alpha))
    return Image.blend(a.convert("RGB"), b.convert("RGB"), alpha)
