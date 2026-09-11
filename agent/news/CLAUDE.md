# news/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 门面，转出 NewsItem / Script / fetch_hot / list_channels / to_script
copywrite.py: 从这篇正文抽数字/福利/比分等事实句；标题只取一句时钩子正文补全其它分句
hashtags.py: 从文章抽专名/赛事；短汉字段跳过，不越界；topic_needles 给自定义类目扩词
fetch.py: 点选时 HTML 抽正文配图，短稿再走 getSimpleNews；视频稿无文字则留下标题分句

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
