# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fetch / copywrite
[OUTPUT]: 对外转出口 NewsItem、fetch_hot、list_channels、to_script
[POS]: news 模块门面
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from agent.news.copywrite import Script, to_script
from agent.news.fetch import NewsItem, fetch_hot, list_channels

__all__ = ["NewsItem", "Script", "fetch_hot", "list_channels", "to_script"]
