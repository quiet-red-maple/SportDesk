# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 numpy、imageio_ffmpeg、agent.media.bgm、agent.style、assets/audio/sfx
[OUTPUT]: 对外提供 build_soundtrack、preview_wav
[POS]: media 的声音层，欢快编曲垫乐 + ElevenLabs 键击采样对齐字符时间轴
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from agent.media.bgm import Track, default_bgm, resolve_track
from agent.paths import asset_dir
from agent.style import BGM_LEVEL, CLICK_LEVEL, SAMPLE_RATE

Midi = Sequence[float]
SFX_PATH = asset_dir() / "audio" / "sfx" / "elevenlabs_typing.mp3"
_CLICK_BANK: Optional[List[np.ndarray]] = None


def _env(n: int, attack: int, release: int) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack, dtype=np.float32)
    if release > 0:
        env[-release:] = np.linspace(1, 0, release, dtype=np.float32)
    return env


def _hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def _place(buf: np.ndarray, t: float, wave: np.ndarray) -> None:
    i = int(t * SAMPLE_RATE)
    if i >= len(buf) or i + 1 < 0:
        return
    i = max(0, i)
    j = min(len(buf), i + len(wave))
    buf[i:j] += wave[: j - i]


def _tone(n: int, freq: float, decay: float, amp: float, harm: Midi = (1.0, 0.42, 0.18, 0.07)) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    wave = np.zeros(n, dtype=np.float32)
    for k, h in enumerate(harm, 1):
        wave += float(h) * np.sin(2 * np.pi * freq * k * t)
    return (wave * np.exp(-t * decay) * amp).astype(np.float32)


def _bell(n: int, freq: float, amp: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * freq * t)
    wave += 0.38 * np.sin(2 * np.pi * freq * 2.76 * t)
    wave += 0.16 * np.sin(2 * np.pi * freq * 5.4 * t)
    return (wave * np.exp(-t * 7.2) * amp).astype(np.float32)


def _strum(chord: Midi, n: int, amp: float) -> np.ndarray:
    out = np.zeros(n, dtype=np.float32)
    delay = int(SAMPLE_RATE * 0.007)
    for k, midi in enumerate(chord):
        start = min(k * delay, n - 8)
        tone = _tone(n - start, _hz(midi), 11.5, amp * (1.0 - k * 0.1), (1.0, 0.55, 0.22))
        out[start:] += tone
    return out


def _kick(n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    body = np.sin(2 * np.pi * (118.0 * np.exp(-t * 16)) * t)
    click = np.diff(np.random.randn(n).astype(np.float32), prepend=np.float32(0)) * np.exp(-t * 90) * 0.12
    return (body * np.exp(-t * 10) * 0.92 + click).astype(np.float32)


def _hat(n: int, amt: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    noise = np.diff(np.random.randn(n).astype(np.float32), prepend=np.float32(0))
    return (noise * np.exp(-t * 55) * amt).astype(np.float32)


def _clap(n: int, amt: float = 0.2) -> np.ndarray:
    out = np.zeros(n, dtype=np.float32)
    noise = np.random.randn(n).astype(np.float32)
    for ms, gain in ((0.0, 1.0), (0.011, 0.75), (0.019, 0.5)):
        i = int(ms * SAMPLE_RATE)
        env = np.exp(-np.arange(n - i, dtype=np.float32) / (SAMPLE_RATE * 0.035))
        out[i:] += noise[: n - i] * env * amt * gain
    return out


def _norm(wave: np.ndarray, level: float) -> np.ndarray:
    peak = float(np.percentile(np.abs(wave), 99.2)) or 1.0
    return np.clip(wave / peak * level, -1.0, 1.0).astype(np.float32)


def _synth_click() -> np.ndarray:
    """采样缺失时的机械键盘兜底。"""
    sr = SAMPLE_RATE
    space = np.random.rand() < 0.08
    n = int(sr * (0.062 if space else 0.048))
    t = np.arange(n, dtype=np.float32) / sr
    thock_f = float(np.random.uniform(120, 170) if space else np.random.uniform(175, 250))
    house_f = float(np.random.uniform(380, 560) if space else np.random.uniform(640, 980))
    click_f = float(np.random.uniform(1680, 2100) if space else np.random.uniform(2350, 3250))
    air_f = float(np.random.uniform(5200, 7800))
    amp = float(np.random.uniform(0.82, 1.0))

    noise = np.random.randn(n).astype(np.float32)
    clack = np.diff(noise, prepend=noise[:1]) * np.exp(-t * 210)
    k = max(2, int(sr * 0.0007))
    impulse = np.zeros(n, dtype=np.float32)
    impulse[:k] = np.linspace(1.0, 0.0, k, dtype=np.float32)

    ping = np.sin(2 * np.pi * click_f * t) * np.exp(-t * 78)
    ping += 0.32 * np.sin(2 * np.pi * click_f * 2.02 * t) * np.exp(-t * 110)
    house = np.sin(2 * np.pi * house_f * t) * np.exp(-t * (22 if space else 36))
    house += 0.28 * np.sin(2 * np.pi * house_f * 1.48 * t) * np.exp(-t * 48)
    thock = np.sin(2 * np.pi * thock_f * t) * np.exp(-t * (16 if space else 26))
    air = np.sin(2 * np.pi * air_f * t) * np.exp(-t * 150)

    wave = impulse * 0.62 + clack * 0.28 + ping * 0.52 + house * 0.3 + thock * 0.26 + air * 0.16
    wave *= _env(n, 1, int(sr * 0.016)) * amp
    peak = float(np.max(np.abs(wave))) or 1.0
    return (wave / peak).astype(np.float32)


def _slice_clicks(wave: np.ndarray) -> List[np.ndarray]:
    sr = SAMPLE_RATE
    win = int(0.003 * sr)
    env = np.sqrt(np.convolve(wave * wave, np.ones(win) / win, "same"))
    thr = max(float(np.percentile(env, 84)), float(np.max(env) * 0.2))
    min_gap = int(0.032 * sr)
    peaks: List[int] = []
    i = 0
    while i < len(env) - 1:
        if env[i] >= thr and (not peaks or i - peaks[-1] > min_gap):
            peaks.append(i)
            i += min_gap
        else:
            i += 1
    bank: List[np.ndarray] = []
    pre = int(0.004 * sr)
    fade_n = int(0.008 * sr)
    for k, p in enumerate(peaks):
        start = max(0, p - pre)
        nxt = peaks[k + 1] if k + 1 < len(peaks) else min(len(wave), p + int(0.09 * sr))
        end = min(len(wave), start + min(int(0.085 * sr), nxt - start))
        sl = wave[start:end].copy()
        if sl.size < 32 or float(np.max(np.abs(sl))) < 0.05:
            continue
        fade = min(fade_n, len(sl) // 3)
        if fade:
            sl[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        peak = float(np.max(np.abs(sl))) or 1.0
        bank.append((sl / peak).astype(np.float32))
    return bank


def _load_clicks() -> List[np.ndarray]:
    global _CLICK_BANK
    if _CLICK_BANK is not None:
        return _CLICK_BANK
    if not SFX_PATH.exists():
        _CLICK_BANK = []
        return _CLICK_BANK
    try:
        _CLICK_BANK = _slice_clicks(_decode_file(SFX_PATH))
    except Exception:
        _CLICK_BANK = []
    return _CLICK_BANK


def _click() -> np.ndarray:
    bank = _load_clicks()
    if not bank:
        return _synth_click()
    wave = bank[int(np.random.randint(0, len(bank)))].copy()
    return (wave * float(np.random.uniform(0.88, 1.0))).astype(np.float32)


# ---------------------------------------------------------------------------
# 编曲 · 一套引擎，多套大调花絮
# chords / bass 按小节循环；melody 按八分音符，0 为空拍
# ---------------------------------------------------------------------------
Groove = Dict[str, object]

GROOVES: Dict[str, Groove] = {
    "bright": {
        "bpm": 128.0,
        "chords": ((60, 64, 67, 72), (67, 71, 74, 79), (69, 72, 76, 81), (65, 69, 72, 77)),
        "bass": (36, 43, 45, 41),
        "melody": (72, 0, 76, 79, 76, 0, 74, 72),
        "kick": 1, "clap": 1, "hat": 0.14, "shake": 0.06,
        "pad": 0.07, "pluck": 0.17, "bell": 0.13, "bass_amp": 0.17,
    },
    "rush": {
        "bpm": 136.0,
        "chords": ((60, 64, 67, 72), (67, 71, 74, 79), (69, 72, 76, 81), (67, 71, 74, 79)),
        "bass": (36, 43, 45, 43),
        "melody": (79, 76, 72, 0, 81, 79, 76, 72),
        "kick": 1, "clap": 1, "hat": 0.18, "shake": 0.08,
        "pad": 0.05, "pluck": 0.14, "bell": 0.12, "bass_amp": 0.2,
    },
    "studio": {
        "bpm": 118.0,
        "chords": ((60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67)),
        "bass": (36, 41, 43, 36),
        "melody": (67, 72, 76, 72, 69, 72, 74, 72),
        "kick": 1, "clap": 1, "hat": 0.1, "shake": 0.05,
        "pad": 0.08, "pluck": 0.2, "bell": 0.1, "bass_amp": 0.15,
    },
    "pulse": {
        "bpm": 132.0,
        "chords": ((60, 64, 67, 71), (65, 69, 72, 76), (67, 71, 74, 79), (60, 64, 67, 72)),
        "bass": (36, 41, 43, 36),
        "melody": (72, 72, 79, 0, 76, 72, 67, 0),
        "kick": 1, "clap": 1, "hat": 0.2, "shake": 0.09,
        "pad": 0.04, "pluck": 0.12, "bell": 0.11, "bass_amp": 0.22,
    },
    "news": {
        "bpm": 124.0,
        "chords": ((64, 67, 71), (60, 64, 67), (65, 69, 72), (67, 71, 74)),
        "bass": (40, 36, 41, 43),
        "melody": (76, 0, 79, 76, 74, 0, 72, 71),
        "kick": 1, "clap": 1, "hat": 0.12, "shake": 0.05,
        "pad": 0.06, "pluck": 0.16, "bell": 0.14, "bass_amp": 0.16,
    },
    "epic": {
        "bpm": 108.0,
        "chords": ((60, 64, 67, 72), (65, 69, 72, 77), (67, 71, 74, 79), (60, 64, 67, 76)),
        "bass": (36, 41, 43, 36),
        "melody": (72, 0, 76, 0, 79, 76, 74, 72),
        "kick": 1, "clap": 0, "hat": 0.08, "shake": 0.03,
        "pad": 0.11, "pluck": 0.1, "bell": 0.16, "bass_amp": 0.18,
    },
    "chill": {
        "bpm": 102.0,
        "chords": ((60, 64, 69), (65, 69, 72), (67, 71, 74), (64, 67, 72)),
        "bass": (36, 41, 43, 40),
        "melody": (72, 0, 74, 76, 0, 74, 72, 69),
        "kick": 0, "clap": 0, "hat": 0.06, "shake": 0.04,
        "pad": 0.1, "pluck": 0.14, "bell": 0.1, "bass_amp": 0.12,
    },
    "tense": {
        "bpm": 112.0,
        "chords": ((57, 60, 64), (55, 59, 62), (53, 57, 60), (55, 59, 62)),
        "bass": (33, 31, 29, 31),
        "melody": (72, 0, 71, 0, 69, 67, 0, 64),
        "kick": 0, "clap": 0, "hat": 0.2, "shake": 0.07,
        "pad": 0.1, "pluck": 0.08, "bell": 0.09, "bass_amp": 0.16,
    },
    "ache": {
        "bpm": 84.0,
        "chords": ((57, 60, 64, 69), (53, 57, 60, 65), (55, 59, 62, 67), (57, 60, 64, 72)),
        "bass": (33, 29, 31, 33),
        "melody": (76, 0, 0, 72, 69, 0, 67, 0),
        "kick": 0, "clap": 0, "hat": 0.0, "shake": 0.0,
        "pad": 0.12, "pluck": 0.09, "bell": 0.14, "bass_amp": 0.1,
    },
    "night": {
        "bpm": 96.0,
        "chords": ((57, 60, 64), (53, 57, 60), (55, 59, 64), (52, 55, 60)),
        "bass": (33, 29, 31, 28),
        "melody": (69, 0, 72, 0, 76, 72, 0, 69),
        "kick": 1, "clap": 0, "hat": 0.07, "shake": 0.03,
        "pad": 0.12, "pluck": 0.08, "bell": 0.08, "bass_amp": 0.2,
    },
}


def _arrange(seconds: float, g: Groove) -> np.ndarray:
    sr = SAMPLE_RATE
    total = int(sr * seconds)
    out = np.zeros(total, dtype=np.float32)
    beat = 60.0 / float(g["bpm"])
    eighth = beat / 2.0
    chords: Tuple[Midi, ...] = tuple(g["chords"])  # type: ignore[arg-type]
    bass: Midi = tuple(g["bass"])  # type: ignore[assignment]
    melody: Midi = tuple(g["melody"])  # type: ignore[assignment]
    step, pos = 0, 0.0
    while pos < seconds + 0.02:
        bar = (step // 8) % len(chords)
        eighth_in_bar = step % 8
        on_beat = eighth_in_bar % 2 == 0
        beat_in_bar = eighth_in_bar // 2
        if on_beat and g["kick"]:
            _place(out, pos, _kick(int(sr * 0.17)))
        if on_beat and g["clap"] and beat_in_bar in (1, 3):
            _place(out, pos, _clap(int(sr * 0.2), 0.18))
        if g["hat"]:
            _place(out, pos, _hat(int(sr * 0.045), float(g["hat"]) * (0.55 if on_beat else 1.0)))
        if g["shake"]:
            _place(out, pos, _hat(int(sr * 0.022), float(g["shake"])))
        if on_beat:
            _place(
                out,
                pos,
                _tone(int(sr * beat * 0.92), _hz(bass[bar % len(bass)]), 5.2, float(g["bass_amp"]), (1.0, 0.62, 0.28, 0.12)),
            )
            if float(g["pluck"]) > 0 and beat_in_bar % 2 == 0:
                _place(out, pos, _strum(chords[bar], int(sr * 0.34), float(g["pluck"])))
        if eighth_in_bar == 0 and float(g["pad"]) > 0:
            n = int(sr * beat * 4)
            pad = np.zeros(n, dtype=np.float32)
            share = float(g["pad"]) / max(1, len(chords[bar]))
            for midi in chords[bar]:
                pad += _tone(n, _hz(midi), 1.05, share, (1.0, 0.28))
            _place(out, pos, pad)
        note = melody[step % len(melody)]
        if note and float(g["bell"]) > 0:
            _place(out, pos, _bell(int(sr * 0.3), _hz(float(note)), float(g["bell"])))
        pos += eighth
        step += 1
    return _norm(out, BGM_LEVEL)


def _decode_file(path: Path) -> np.ndarray:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-vn", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("无法解码音频: " + path.name)
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def _loop_to(wave: np.ndarray, n: int) -> np.ndarray:
    if wave.size == 0:
        return np.zeros(n, dtype=np.float32)
    reps = int(np.ceil(n / float(wave.size)))
    out = np.tile(wave, max(1, reps))[:n].astype(np.float32)
    fade = min(int(SAMPLE_RATE * 0.35), n // 6)
    if fade > 0:
        out[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        out[: max(1, fade // 3)] *= np.linspace(0, 1, max(1, fade // 3), dtype=np.float32)
    return out


def _render_bgm(track: Track, seconds: float) -> np.ndarray:
    n = int(SAMPLE_RATE * seconds)
    if track.kind == "silent":
        return np.zeros(n, dtype=np.float32)
    if track.kind == "file" and track.path:
        return _norm(_loop_to(_decode_file(Path(track.path)), n), BGM_LEVEL)
    wave = _arrange(seconds, GROOVES.get(track.track_id, GROOVES["bright"]))
    return wave if len(wave) >= n else np.pad(wave, (0, n - len(wave)))


def _write_wav(mix: np.ndarray, dest: Path) -> Path:
    pcm = (np.clip(mix, -1.0, 1.0) * 32767).astype(np.int16)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return dest


def build_soundtrack(
    duration: float,
    click_times: List[float],
    dest: Path,
    bgm_id: Optional[str] = None,
) -> Path:
    track = resolve_track(bgm_id or default_bgm())
    n = int(SAMPLE_RATE * duration) + SAMPLE_RATE // 4
    mix = _loop_to(_render_bgm(track, duration + 0.4), n)
    for t in click_times:
        click = _click()
        i = int(t * SAMPLE_RATE)
        if i < 0 or i >= n:
            continue
        j = min(n, i + len(click))
        mix[i:j] += click[: j - i] * CLICK_LEVEL
    return _write_wav(np.clip(mix, -1.0, 1.0), dest)


def preview_wav(track_id: str, dest: Path, seconds: float = 6.0) -> Path:
    track = resolve_track(track_id)
    mix = _render_bgm(track, seconds)
    if track.kind == "silent":
        t = 0.35
        while t < min(2.2, seconds):
            click = _click()
            i = int(t * SAMPLE_RATE)
            mix[i : i + len(click)] += click * CLICK_LEVEL
            t += float(np.random.uniform(0.07, 0.13))
    return _write_wav(np.clip(mix, -1.0, 1.0), dest)
