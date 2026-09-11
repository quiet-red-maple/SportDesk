# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 requests、PIL、NewsItem 图片 URL
[OUTPUT]: 对外提供 download_images，返回本地 RGB 图列表
[POS]: media 的配图下载器，丢掉分享卡缩略图，缺图时用色块兜底，不复制同一张
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import List

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from agent.media.fonts import load_fonts

from agent.paths import work_dir

CACHE = work_dir() / ".cache" / "images"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"


def _placeholder(label: str) -> Image.Image:
    img = Image.new("RGB", (1080, 720), (28, 12, 16))
    draw = ImageDraw.Draw(img)
    for i in range(8):
        draw.rectangle((i * 140, 0, i * 140 + 80, 720), fill=(120 + i * 8, 18, 28))
    img = img.filter(ImageFilter.GaussianBlur(12))
    font = load_fonts()[1]
    draw = ImageDraw.Draw(img)
    draw.text((48, 300), label[:16] or "SPORTS", font=font, fill=(255, 220, 80))
    return img


def _open_bytes(data: bytes) -> Image.Image:
    img = Image.open(BytesIO(data))
    return img.convert("RGB")


def _share_card(img: Image.Image) -> bool:
    w, h = img.size
    return min(w, h) <= 280 and abs(w - h) <= 16


def download_images(urls: List[str], label: str = "") -> List[Image.Image]:
    CACHE.mkdir(parents=True, exist_ok=True)
    photos: List[Image.Image] = []
    seen = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        name = hashlib.md5(url.encode()).hexdigest() + ".jpg"
        dest = CACHE / name
        try:
            if dest.exists() and dest.stat().st_size > 2000:
                img = Image.open(dest).convert("RGB")
            else:
                resp = requests.get(url, headers={"User-Agent": UA, "Referer": "https://news.qq.com/"}, timeout=12)
                resp.raise_for_status()
                img = _open_bytes(resp.content)
                img.save(dest, "JPEG", quality=90)
            if _share_card(img):
                continue
            photos.append(img)
        except Exception:
            continue
        if len(photos) >= 5:
            break
    if not photos:
        photos.append(_placeholder(label))
    return photos
