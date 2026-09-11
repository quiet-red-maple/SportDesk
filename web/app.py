# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 FastAPI、agent.pipeline
[OUTPUT]: 对外提供 app，多榜单 / 自定义类目热搜 / 文案 / 曲库 / 出片；垫乐默认仅打字机
[POS]: web 控制台后端；/api/news 失败也回 JSON，不甩 Internal Server Error
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional

from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.media.audio import preview_wav
from agent.media.bgm import default_bgm, list_tracks, save_upload
from agent.news.fetch import DEFAULT_CHANNEL, find_item, list_channels
from agent.paths import asset_dir
from agent.pipeline import CACHE, OUTPUT, list_hot, preview_script, run_pipeline

STATIC = asset_dir().parent / "web" / "static"

app = FastAPI(title="体育热点短视频 Agent")
_JOBS: Dict[str, "Job"] = {}


class Job(object):
    def __init__(self) -> None:
        self.status = "queued"
        self.message = "排队"
        self.percent = 0
        self.path = ""
        self.error = ""
        self.caption = ""
        self.hashtags_line = ""


class GenerateBody(BaseModel):
    news_id: str
    title: Optional[str] = None
    hook: Optional[str] = None
    body: Optional[str] = None
    bgm_id: Optional[str] = None
    channel: Optional[str] = DEFAULT_CHANNEL


class ScriptBody(BaseModel):
    news_id: str
    title: Optional[str] = None
    hook: Optional[str] = None
    body: Optional[str] = None
    channel: Optional[str] = DEFAULT_CHANNEL


def _item(news_id: str, channel: Optional[str] = None):
    it = find_item(news_id, channel or DEFAULT_CHANNEL)
    if it:
        return it
    raise HTTPException(404, "资讯不存在或已刷新，请重新拉取")


@app.get("/api/channels")
def api_channels():
    return {"default": DEFAULT_CHANNEL, "channels": list_channels()}


@app.get("/api/news")
def api_news(channel: str = DEFAULT_CHANNEL):
    try:
        items = list_hot(channel=channel)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc) or "热点源暂时连不上，请稍后刷新")
    return [
        {
            "news_id": it.news_id,
            "title": it.title,
            "summary": it.summary[:180],
            "published": it.published,
            "source": it.source,
            "url": it.url,
            "cover": it.image_urls[0] if it.image_urls else "",
            "images": it.image_urls[:5],
            "channel": it.channel,
        }
        for it in items
    ]


@app.post("/api/script")
def api_script(body: ScriptBody):
    item = _item(body.news_id, body.channel)
    script = preview_script(item, title=body.title, hook=body.hook, body=body.body)
    track = next((t for t in list_tracks() if t.track_id == default_bgm()), None)
    data = asdict(script)
    data["bgm_id"] = default_bgm()
    data["bgm_name"] = track.name if track else "仅打字机"
    data["bgm_mood"] = track.mood if track else "无背景音乐"
    return data


def _run_job(job_id: str, body: GenerateBody) -> None:
    job = _JOBS[job_id]

    def tick(msg: str, pct: int) -> None:
        job.status = "running"
        job.message = msg
        job.percent = pct

    try:
        path = run_pipeline(
            news_id=body.news_id,
            title=body.title,
            hook=body.hook,
            body=body.body,
            bgm_id=body.bgm_id or default_bgm(),
            channel=body.channel or DEFAULT_CHANNEL,
            on_progress=tick,
        )
        job.status = "done"
        job.percent = 100
        job.message = "完成"
        job.path = path.name
        note = path.with_suffix(".txt")
        if note.exists():
            job.caption = note.read_text(encoding="utf-8").strip()
            lines = [ln for ln in job.caption.splitlines() if ln.startswith("#")]
            job.hashtags_line = lines[-1] if lines else ""
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        job.message = "失败"


@app.post("/api/generate")
def api_generate(body: GenerateBody):
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = Job()
    thread = threading.Thread(target=_run_job, args=(job_id, body), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return {
        "status": job.status,
        "message": job.message,
        "percent": job.percent,
        "file": job.path,
        "error": job.error,
        "url": ("/media/" + job.path) if job.path else "",
        "caption": job.caption,
        "hashtags_line": job.hashtags_line,
    }


@app.get("/api/bgm")
def api_bgm():
    return {
        "default": default_bgm(),
        "tracks": [t.as_dict() for t in list_tracks()],
    }


@app.get("/api/bgm/preview")
def api_bgm_preview(id: str):
    dest = CACHE / "audio" / ("preview_" + id.replace(":", "_") + ".wav")
    try:
        preview_wav(id, dest)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return FileResponse(dest, media_type="audio/wav", filename="preview.wav")


@app.post("/api/bgm/upload")
async def api_bgm_upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        track = save_upload(file.filename or "bgm.mp3", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return track.as_dict()


@app.get("/media/{name}")
def api_media(name: str):
    path = _video_path(name)
    return FileResponse(path, media_type="video/mp4")


@app.get("/download/{name}")
def api_download(name: str):
    path = _video_path(name)
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=name,
        headers={"Content-Disposition": "attachment; filename*=UTF-8''%s" % quote(name)},
    )


def _video_path(name: str) -> Path:
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "非法文件名")
    path = OUTPUT / name
    if not path.exists() or path.suffix.lower() != ".mp4":
        raise HTTPException(404, "成片不存在")
    return path


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
