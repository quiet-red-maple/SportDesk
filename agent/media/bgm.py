# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 assets/audio/bgm 的 Mixkit 曲库与用户导入音频
[OUTPUT]: 对外提供 Track、DEFAULT_BGM、default_bgm、list_tracks、resolve_track、save_upload、pick_bgm
[POS]: media 的曲库；默认仅打字机，真曲可选；pick_bgm 仍按新闻词族打分
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from agent.paths import asset_dir, frozen, work_dir

BGM_DIR = asset_dir() / "audio" / "bgm"
USER_BGM = work_dir() / "bgm"
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# ---------------------------------------------------------------------------
# Mixkit 免版税曲库：文件名即展示名，顺序即选择器顺序
# ---------------------------------------------------------------------------
STOCK_TRACKS: Tuple[Tuple[str, str], ...] = (
    ("欢快时光.mp3", "欢快 / 口播"),
    ("笑容满面.mp3", "欢快 / 口播"),
    ("心情不错.mp3", "欢快 / 口播"),
    ("尤克里里.mp3", "轻快 / 花絮"),
    ("夏日阳光.mp3", "轻快 / 花絮"),
    ("跳跃节奏.mp3", "轻快 / 花絮"),
    ("轻快早晨.mp3", "口播 / 盘点"),
    ("旅行路上.mp3", "口播 / 盘点"),
    ("律动不错.mp3", "节奏 / 资讯"),
    ("空中天赋.mp3", "电子 / 资讯"),
    ("赛场集锦.mp3", "燃向 / 集锦"),
    ("热血摇滚.mp3", "燃向 / 集锦"),
    ("敢闯敢拼.mp3", "爆点 / 冲突"),
    ("击倒瞬间.mp3", "爆点 / 冲突"),
    ("游戏开场.mp3", "预告 / 开场"),
)
STOCK_DEFAULT = "欢快时光.mp3"

SYNTH_TRACKS = (
    ("bright", "轻快花絮", "合成 / 口播", "synth"),
    ("rush", "热血冲刺", "合成 / 冲突", "synth"),
    ("studio", "解说垫乐", "合成 / 盘点", "synth"),
    ("pulse", "电子脉冲", "合成 / 集锦", "synth"),
    ("news", "新闻快讯", "合成 / 热搜", "synth"),
    ("epic", "史诗铺垫", "合成 / 高光", "synth"),
    ("chill", "清爽铺底", "合成 / 故事", "synth"),
    ("tense", "紧张揭秘", "合成 / 内幕", "synth"),
    ("ache", "悲情余味", "合成 / 告别", "synth"),
    ("night", "夜色低音", "合成 / 复盘", "synth"),
    ("silent", "仅打字机", "无背景音乐", "silent"),
)


@dataclass
class Track:
    track_id: str
    name: str
    mood: str
    kind: str
    path: str = ""

    def as_dict(self):
        return asdict(self)


def _file_id(path: Path) -> str:
    return "file:" + path.name


def default_bgm() -> str:
    return "silent"


DEFAULT_BGM = default_bgm()


def _write_dir() -> Path:
    dest = USER_BGM if frozen() else BGM_DIR
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def list_tracks() -> List[Track]:
    seen = set()
    tracks: List[Track] = [Track("silent", "仅打字机", "无背景音乐", "silent")]
    for name, mood in STOCK_TRACKS:
        path = BGM_DIR / name
        if not path.is_file():
            continue
        tracks.append(Track(_file_id(path), path.stem, mood, "file", str(path)))
        seen.add(path.name)
    tracks.extend(
        Track(tid, name, mood, kind)
        for tid, name, mood, kind in SYNTH_TRACKS
        if tid != "silent"
    )
    extras = []
    folders = [BGM_DIR]
    write_dir = _write_dir()
    if write_dir != BGM_DIR:
        folders.append(write_dir)
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in AUDIO_EXTS or not path.is_file():
                continue
            if path.name in seen:
                continue
            extras.append(Track(_file_id(path), path.stem, "本地导入", "file", str(path)))
            seen.add(path.name)
    tracks.extend(extras)
    return tracks


def resolve_track(track_id: Optional[str]) -> Track:
    tracks = list_tracks()
    wanted = (track_id or "").strip() or default_bgm()
    by_id = {track.track_id: track for track in tracks}
    if wanted in by_id:
        return by_id[wanted]
    fallback = default_bgm()
    if fallback in by_id:
        return by_id[fallback]
    return by_id.get("silent") or next(iter(by_id.values()))


def save_upload(filename: str, data: bytes) -> Track:
    folder = _write_dir()
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        raise ValueError("只支持 mp3 / wav / m4a / aac / flac / ogg")
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("音频超过 16MB")
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", stem).strip("_") or "bgm"
    dest = folder / (safe + ext)
    n = 1
    while dest.exists():
        dest = folder / ("%s_%d%s" % (safe, n, ext))
        n += 1
    dest.write_bytes(data)
    return Track(_file_id(dest), dest.stem, "本地导入", "file", str(dest))


# 词族打分，命中乘 4；榜单只加 2。同分真曲压合成。silent 不参与。
_NEEDLES = (
    ("ache", ("去世", "逝世", "悼念", "遇难", "病逝", "身亡", "追悼会", "哀悼", "离世", "讣告")),
    ("clash", ("冲突", "打架", "推搡", "红牌", "怒斥", "互殴", "大骂", "争议", "罢赛", "内讧")),
    ("fire", ("夺冠", "冠军", "绝杀", "逆转", "封王", "金牌", "破纪录", "决赛", "捧杯", "神迹")),
    ("game", ("游戏", "电竞", "原神", "英雄联盟", "公测", "开服", "steam", "主机")),
    ("tech", ("AI", "人工智能", "芯片", "机器人", "华为", "折叠屏", "发布会", "大模型", "算力")),
    ("news", ("突发", "快讯", "回应", "官方", "通报", "立案", "政策", "央行")),
    ("chill", ("专访", "回忆", "往事", "纪录片", "故事", "人物")),
    ("fun", ("花絮", "搞笑", "名场面", "整活", "笑翻")),
    ("ent", ("恋情", "离婚", "官宣", "演唱会", "新剧", "综艺", "复合")),
)
_TRACK_FAMILY = {
    "击倒瞬间": "clash",
    "敢闯敢拼": "clash",
    "rush": "clash",
    "tense": "clash",
    "赛场集锦": "fire",
    "热血摇滚": "fire",
    "epic": "fire",
    "pulse": "fire",
    "游戏开场": "game",
    "空中天赋": "tech",
    "律动不错": "news",
    "news": "news",
    "studio": "news",
    "ache": "ache",
    "night": "ache",
    "chill": "chill",
    "轻快早晨": "chill",
    "旅行路上": "chill",
    "笑容满面": "ent",
    "心情不错": "fun",
    "欢快时光": "fun",
    "尤克里里": "ent",
    "夏日阳光": "fun",
    "跳跃节奏": "fun",
    "bright": "fun",
}
_CHANNEL_FAMILY = {
    "sports": "fire",
    "ent": "ent",
    "tech": "tech",
    "finance": "news",
    "mil": "clash",
    "world": "news",
    "game": "game",
    "auto": "news",
    "edu": "chill",
    "top": "news",
}


def _stem(track: Track) -> str:
    if track.kind == "file":
        return Path(track.path).stem if track.path else track.name
    return track.track_id


def pick_bgm(text: str = "", channel: str = "") -> Track:
    blob = (text or "") + " " + (channel or "")
    hits = {}
    for family, words in _NEEDLES:
        n = sum(1 for w in words if w and w in blob)
        if n:
            hits[family] = n
    chan_fam = _CHANNEL_FAMILY.get((channel or "").split(":")[0])
    best = None
    best_key = (-1, 0)
    for track in list_tracks():
        if track.kind == "silent":
            continue
        fam = _TRACK_FAMILY.get(_stem(track))
        score = hits.get(fam, 0) * 4 if fam else 0
        if chan_fam and fam == chan_fam:
            score += 2
        if track.kind == "file":
            score += 1
        key = (score, 1 if track.kind == "file" else 0)
        if key > best_key:
            best_key = key
            best = track
    return best or resolve_track(default_bgm())

