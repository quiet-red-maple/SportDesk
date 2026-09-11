# render/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 门面，转出 encode_video / frost_base / paint_copy
look.py: 每片掷一次视觉骰子，颜色 / 排版 / Ken Burns
canvas.py: 毛玻璃降采样模糊；Ken Burns 一次放大，逐帧只裁切
text.py: CopyPack 排版一次、标题光晕缓存，打字机只描可见字
encode.py: 预生成 Ken 图后 raw RGB 推 FFmpeg ultrafast，混 WAV

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
