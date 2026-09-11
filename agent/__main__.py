# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 argparse、agent.pipeline、web.app
[OUTPUT]: 对外提供 CLI：list / 出片 / 榜单 / 自定义类目 / web
[POS]: 命令行入口；Windows 用 startfile 打开浏览器，失败弹 MessageBox；端口占用则复用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List, Optional

from agent.paths import bundle_dir, frozen, work_dir

ROOT = bundle_dir()
os.chdir(str(work_dir()))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_bgm() -> None:
    from agent.media.bgm import list_tracks

    for track in list_tracks():
        print("%-18s  %s  ·  %s" % (track.track_id, track.name, track.mood))


def _print_hot(limit: int, channel: str) -> None:
    from agent.pipeline import list_hot

    items = list_hot(limit=limit, channel=channel)
    for i, it in enumerate(items):
        flag = "图" if it.image_urls else " "
        print(f"[{i:02d}] {flag} {it.published}  {it.title}")
        print(f"     {it.news_id}  imgs={len(it.image_urls)}")


def _print_channels() -> None:
    from agent.news.fetch import DEFAULT_CHANNEL, list_channels

    for ch in list_channels():
        mark = "*" if ch["id"] == DEFAULT_CHANNEL else " "
        print("%s %-10s  %s" % (mark, ch["id"], ch["name"]))


def _render(args: argparse.Namespace) -> int:
    from agent.pipeline import run_pipeline

    def tick(msg: str, pct: int) -> None:
        print(f"[{pct:3d}%] {msg}", flush=True)

    path = run_pipeline(news_id=args.id, index=args.pick, bgm_id=args.bgm, channel=args.channel, on_progress=tick)
    print("OUTPUT", path)
    note = path.with_suffix(".txt")
    if note.exists():
        print("视频号文案")
        print(note.read_text(encoding="utf-8").rstrip())
    return 0


def _listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), 0.4):
            return True
    except OSError:
        return False


def _alert(title: str, msg: str) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40)


def _open_url(url: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(url)
            return
        if sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", url], close_fds=True)
            return
        webbrowser.open(url)
    except Exception as exc:
        print("OPEN_FAIL", exc, flush=True)
        if sys.platform == "win32":
            subprocess.Popen('start "" "%s"' % url, shell=True)


def _web(args: argparse.Namespace) -> int:
    import uvicorn
    from web.app import app

    host = args.host
    port = args.port
    show = "127.0.0.1" if host == "0.0.0.0" else host
    url = "http://%s:%d" % (show, port)
    probe = show if host == "0.0.0.0" else host
    if _listening(probe, port):
        print("ALREADY", url, flush=True)
        _open_url(url)
        _alert("热点短视频", "工作台已在运行。\n请看浏览器，或自己打开：\n" + url)
        time.sleep(0.8)
        return 0

    def later() -> None:
        for _ in range(50):
            if _listening(probe, port):
                break
            time.sleep(0.15)
        _open_url(url)
        _alert("热点短视频", "工作台已启动。\n浏览器没出来就打开：\n" + url)

    threading.Thread(target=later, daemon=True).start()
    print("WEB", url, flush=True)
    print("浏览器没打开就自己访问这个地址", flush=True)
    uvicorn.run(app, host=host, port=port, reload=False, log_level="info")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent", description="体育热点短视频 Agent")
    parser.add_argument("--list", action="store_true", help="只拉热点，不出片")
    parser.add_argument("--pick", type=int, default=0, help="按列表序号出片")
    parser.add_argument("--id", default=None, help="按资讯 id 出片")
    parser.add_argument("--web", action="store_true", help="启动本地工作台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--bgm", default="silent", help="背景音乐 id，默认仅打字机")
    parser.add_argument("--bgm-list", action="store_true", help="列出可选背景音乐")
    parser.add_argument("--channel", default="sports", help="榜单 id，默认体育")
    parser.add_argument("--query", default="", help="自定义类目，搜对应热搜")
    parser.add_argument("--channels", action="store_true", help="列出可选榜单")
    args = parser.parse_args(argv)
    if frozen() and sys.platform != "win32":
        log = work_dir() / "sport-desk.log"
        stream = open(log, "a", encoding="utf-8", buffering=1)
        sys.stdout = stream
        sys.stderr = stream
    if frozen() and not any((args.list, args.web, args.channels, args.bgm_list, args.id)):
        args.web = True
    if (args.query or "").strip():
        args.channel = "q:" + args.query.strip()

    if args.bgm_list:
        _print_bgm()
        return 0
    if args.channels:
        _print_channels()
        return 0
    if args.list:
        _print_hot(args.limit, args.channel)
        return 0
    if args.web:
        return _web(args)
    return _render(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback

        text = traceback.format_exc()
        print(text, flush=True)
        _alert("热点短视频 启动失败", text[-1500:])
        raise
