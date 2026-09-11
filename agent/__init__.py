# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 agent.pipeline 的出片编排
[OUTPUT]: 对外提供 VERSION、run_pipeline
[POS]: agent 包入口，CLI 与 Web 都从这里走进流水线
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from agent.pipeline import run_pipeline

VERSION = "1.0.0"

__all__ = ["VERSION", "run_pipeline"]
