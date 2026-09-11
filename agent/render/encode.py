# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 imageio_ffmpeg、numpy、canvas/text/audio/look，接收 bgm_id
[OUTPUT]: 对外提供 encode_video，把脚本帧流写成 mp4
[POS]: render 的编码器，Ken 图一次放大、文案光晕缓存后推 RGB 混 WAV
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image
import numpy as np

from agent.media.audio import build_soundtrack
from agent.news.copywrite import Script
from agent.render.canvas import blend_frames, frost_base, place_sharp, prepare_sheet
from agent.render.look import Look, roll_look
from agent.render.text import CopyPack, click_times, type_plan
from agent.style import FPS, HEIGHT, WIDTH

ProgressFn = Callable[[str, int], None]


def _scene_index(frame_i: int, n_frames: int, n_photos: int, fade_sec: float):
    if n_photos <= 1:
        return 0, 0, 0.0, frame_i / max(1, n_frames - 1)
    slot = float(n_frames) / n_photos
    fade = min(int(fade_sec * FPS), max(1, int(slot * 0.18)))
    idx = min(n_photos - 1, int(frame_i / slot))
    local_t = frame_i - idx * slot
    local = min(1.0, local_t / max(1.0, slot))
    if idx < n_photos - 1 and local_t >= slot - fade:
        mix = (local_t - (slot - fade)) / max(1, fade)
        return idx, idx + 1, mix, local
    return idx, idx, 0.0, local


def encode_video(
    script: Script,
    photos: List[Image.Image],
    dest: Path,
    wav_path: Path,
    on_progress: Optional[ProgressFn] = None,
    bgm_id: Optional[str] = None,
    look: Optional[Look] = None,
) -> Path:
    look = look or roll_look()
    photos = list(photos)
    if look.shuffle and len(photos) > 1:
        rng = random.Random(look.seed)
        rng.shuffle(photos)
    plan = type_plan(script.body, look)
    n_frames = len(plan)
    duration = n_frames / FPS
    clicks = click_times(plan)
    build_soundtrack(duration, clicks, wav_path, bgm_id=bgm_id)

    if on_progress:
        on_progress("预渲染毛玻璃", 18)
    frosts = [frost_base(p, look) for p in photos]
    sheets = [prepare_sheet(p, look) for p in photos]
    pack = CopyPack(script.title, script.hook, script.body, look)

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "ultrafast",
        "-threads",
        "0",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-aspect",
        "9:16",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    title_punch_frames = max(1, int(look.type_delay * FPS) + 8)
    try:
        for i, visible in enumerate(plan):
            a, b, mix, local = _scene_index(i, n_frames, len(photos), look.fade_sec)
            frame_a = place_sharp(frosts[a], sheets[a], local, look)
            if mix > 0:
                frame_b = place_sharp(frosts[b], sheets[b], 0.0, look)
                frame = blend_frames(frame_a, frame_b, mix)
            else:
                frame = frame_a
            punch = min(1.0, i / title_punch_frames)
            painted = pack.stamp(frame, visible, punch)
            proc.stdin.write(np.asarray(painted, dtype=np.uint8).tobytes())
            if on_progress and i % 12 == 0:
                on_progress("渲染帧", 20 + int(70 * i / n_frames))
        proc.stdin.close()
        err = proc.stderr.read() if proc.stderr else b""
        code = proc.wait()
        if code != 0:
            raise RuntimeError(err.decode("utf-8", errors="ignore")[-1200:])
    except Exception:
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
        proc.kill()
        raise
    if on_progress:
        on_progress("封装完成", 100)
    return dest
