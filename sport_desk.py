# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 agent.__main__
[OUTPUT]: 安装包入口，双击即开工作台
[POS]: 打包锚点，PyInstaller 从这里收集 agent / web / assets
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import sys

from agent.__main__ import _alert, main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback

        text = traceback.format_exc()
        print(text, flush=True)
        _alert("热点短视频 启动失败", text[-1500:])
        raise
