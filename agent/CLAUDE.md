# agent/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 包入口，转出 VERSION / run_pipeline
__main__.py: CLI，list / pick / channel / query / web；Windows startfile 开浏览器，失败弹窗
paths.py: 安装包读包内资源，成片写 ~/SportDesk
pipeline.py: 总编排；点选/出片抽本文事实入口播，配图只用本文；未指定垫乐则仅打字机
style.py: 视觉宪法，1080x1920 / 描边默认值 / 打字机 CPS

子目录
news/ - 采集与醒目文案
media/ - 字体、配图、音轨
render/ - 毛玻璃画布、文字层、FFmpeg 封装

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
