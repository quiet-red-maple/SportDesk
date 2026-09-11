# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 news.fetch / copywrite / media.images / media.bgm / render.encode
[OUTPUT]: 对外提供 run_pipeline、preview_script、list_hot、clear_output
[POS]: agent 总编排；未指定垫乐时用仅打字机
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from agent.media.bgm import default_bgm
from agent.media.images import download_images
from agent.news.copywrite import Script, to_script
from agent.news.fetch import NewsItem, fetch_hot, find_item, enrich_images
from agent.render.encode import encode_video

from agent.paths import work_dir

ROOT = work_dir()
OUTPUT = ROOT / "output"
CACHE = ROOT / ".cache"

ProgressFn = Callable[[str, int], None]


def list_hot(limit: int = 16, channel: Optional[str] = None) -> List[NewsItem]:
    return fetch_hot(limit=limit, channel=channel)


def preview_script(item: NewsItem, title: Optional[str] = None, hook: Optional[str] = None, body: Optional[str] = None) -> Script:
    enrich_images(item)
    return to_script(item, title=title, hook=hook, body=body)


def _pick(items: List[NewsItem], news_id: Optional[str], index: int) -> NewsItem:
    if news_id:
        for it in items:
            if it.news_id == news_id:
                return it
        raise ValueError("找不到这条资讯: " + news_id)
    if not items:
        raise RuntimeError("热点列表为空")
    return items[max(0, min(index, len(items) - 1))]


def clear_output() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT.iterdir():
        if path.suffix.lower() in {".mp4", ".txt"}:
            path.unlink(missing_ok=True)


def run_pipeline(
    news_id: Optional[str] = None,
    index: int = 0,
    title: Optional[str] = None,
    hook: Optional[str] = None,
    body: Optional[str] = None,
    bgm_id: Optional[str] = None,
    channel: Optional[str] = None,
    on_progress: Optional[ProgressFn] = None,
) -> Path:
    def tick(msg: str, pct: int) -> None:
        if on_progress:
            on_progress(msg, pct)

    tick("清空上一条", 2)
    clear_output()
    tick("准备稿件", 5)
    item = find_item(news_id, channel) if news_id else None
    if item is None:
        tick("拉取热点", 8)
        items = fetch_hot(channel=channel)
        item = _pick(items, news_id, index)
    tick("补正文配图", 10)
    enrich_images(item)
    script = to_script(item, title=title, hook=hook, body=body)
    tick("下载配图", 12)
    photos = download_images(script.image_urls, label=script.title)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() else "_" for ch in script.title)[:18]
    dest = OUTPUT / f"{stamp}_{safe}.mp4"
    wav = CACHE / "audio" / f"{stamp}.wav"
    tick("开始渲染", 16)
    if not bgm_id:
        bgm_id = default_bgm()
    video = encode_video(script, photos, dest, wav, on_progress=on_progress, bgm_id=bgm_id)
    caption = dest.with_suffix(".txt")
    caption.write_text(script.channels_caption + "\n", encoding="utf-8")
    return video
