# 热点短视频 Agent - 多榜单抓热点并剪成竖屏口播片
Python 3.9 + Pillow + FFmpeg(imageio-ffmpeg) + FastAPI

<directory>
agent/ - 出片大脑 (3子目录: news media render)
web/ - 本地工作台 (1子目录: static)
assets/ - 运行时缓存与素材锚点
packaging/ - Mac dmg / Windows 免打包启动与 exe 规格
.github/ - CI 打 Windows 包 (1子目录: workflows)
打开工作台.bat - Windows 直接跑工作台，不生成 exe
生成Windows程序.bat - Windows 打 exe，成功后放到桌面 SportDesk
output/ - 成片落地
</directory>

<config>
requirements.txt - 渲染与 Web 依赖钉死
agent/style.py - 视觉宪法：1080x1920 / 打字机节奏
agent/render/look.py - 每片随机皮肤：色盘 / 排版 / 配图动效
agent/news/fetch.py - 腾讯多榜单 + 自定义类目热搜，默认体育
</config>

启动: `venv/bin/python -m agent` 出片 · `--web` 打开工作台 · `packaging/build_mac.sh` 打 Mac 包 · 推 GitHub 后 Release `windows` 出 SportDesk-Windows.zip · Windows 本机打 exe 双击 `生成Windows程序.bat`（产物在桌面 SportDesk） · 不要 exe 双击 `打开工作台.bat`
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
