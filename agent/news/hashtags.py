# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖口播稿与源标题 / 摘要 / 榜单
[OUTPUT]: 对外提供 hot_tags、hashtags_line、channels_caption、topic_needles
[POS]: news 的视频号热词刀，话题从文章长出，大类只垫一条
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

MAX_TAGS = 12

# 文章里出现才收录。core 只在正文没写项目名时补一个。
_CLUSTERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("乒乓球 国乒 乒超 WTT 世乒赛 樊振东 马龙 孙颖莎 王楚钦 陈梦 王曼昱 林诗栋 蒯曼 梁靖崑 林高远 刘国梁 王励勤 张本智和 张本美和 伊藤美诚 早田希娜 莎莎",
     ("乒乓球",)),
    ("网球 美网 法网 温网 澳网 郑钦文 商竣程 张之臻 王欣瑜 萨巴伦卡 阿尔卡拉斯 辛纳 ATP WTA",
     ("网球",)),
    ("篮球 NBA CBA 男篮 女篮 中国女篮 中国男篮 胡金秋 赵睿 周琦 郭艾伦 易建联 崔永熙 杨瀚森 东契奇 库里 詹姆斯 湖人 勇士 凯尔特人",
     ("篮球",)),
    ("足球 中超 国足 欧洲杯 英超 西甲 德甲 意甲 欧冠 武磊 韦世豪 张玉宁 王大雷 蓉城 海港 泰山 国安 申花",
     ("足球",)),
    ("排球 女排 男排 朱婷 吴梦洁 李盈莹 张常宁 女排精神",
     ("排球",)),
    ("羽毛球 羽联 汤杯 尤杯 苏迪曼杯 石宇奇 陈雨菲 王祉怡 安赛龙 桃田贤斗",
     ("羽毛球",)),
    ("游泳 张雨霏 潘展乐 覃海洋 泳坛", ("游泳",)),
    ("跳水 全红婵 陈芋汐 王宗源 跳水世界杯", ("跳水",)),
    ("田径 苏炳添 谢震业 短跑 马拉松 跳高", ("田径",)),
    ("斯诺克 台球 丁俊晖 奥沙利文 赵心童", ("斯诺克",)),
    ("电竞 英雄联盟 LPL 王者荣耀 无畏契约", ("电竞",)),
    ("F1 赛车 周冠宇 维斯塔潘 安东内利 意大利站 摩托 WSBK", ("F1",)),
    ("冬奥 冰雪 谷爱凌 苏翊鸣 滑雪 花样滑冰", ("冰雪运动",)),
)

_TOPIC_EXTRA = (
    ("电影 影片 票房 档期 影史", ("电影",)),
    ("人工智能 AI 大模型 智能体 具身智能 ChatGPT", ("人工智能",)),
)


def topic_needles(query: str) -> List[str]:
    q = (query or "").strip()
    if not q:
        return []
    words = [q]
    if len(q) == 2:
        words.append(q + "球")
    for blob, core in _CLUSTERS + _TOPIC_EXTRA:
        keys = blob.split() + list(core)
        if len(q) >= 2 and any(len(k) >= 2 and (q in k or k in q) for k in keys):
            words.extend(keys)
    seen = set()
    out: List[str] = []
    for word in words:
        if word and word not in seen:
            seen.add(word)
            out.append(word)
    return out

_EVENTS = (
    "美网", "法网", "温网", "澳网", "世界杯", "欧洲杯", "亚洲杯", "奥运会", "亚运会",
    "全运会", "世锦赛", "亚锦赛", "世乒赛", "世预赛", "欧冠", "中超", "乒超",
    "CBA", "NBA", "WTT", "德甲", "西甲", "英超", "意甲", "汤杯", "尤杯",
    "苏迪曼杯", "男篮世界杯", "意大利站",
)

_NAMES = (
    "樊振东", "马龙", "孙颖莎", "王楚钦", "陈梦", "王曼昱", "林诗栋", "蒯曼",
    "刘国梁", "王励勤", "梁靖崑", "林高远", "张本智和", "张本美和", "伊藤美诚",
    "郑钦文", "商竣程", "张之臻", "王欣瑜",
    "胡金秋", "赵睿", "周琦", "郭艾伦", "易建联", "崔永熙", "杨瀚森",
    "武磊", "韦世豪", "张玉宁", "王大雷",
    "朱婷", "吴梦洁", "李盈莹", "全红婵", "陈芋汐", "张雨霏", "潘展乐", "覃海洋",
    "苏炳添", "丁俊晖", "赵心童", "谷爱凌", "苏翊鸣", "周冠宇", "维斯塔潘", "安东内利",
    "石宇奇", "陈雨菲", "张博恒",
)

_TEAMS = (
    "湖人", "勇士", "凯尔特人", "掘金", "广东宏远", "辽宁男篮", "中国女篮", "中国男篮",
    "上海海港", "山东泰山", "北京国安", "成都蓉城", "上海申花", "河南",
    "皇家马德里", "巴萨", "曼城", "曼联", "阿森纳", "国足", "中国女排",
)

# 文章里出现的动作，本身就是话题，不映射成空壳词。
_ACTIONS = (
    "夺冠", "逆转", "绝杀", "下课", "争议", "退役", "转会", "破纪录", "卫冕",
    "出线", "加时", "封王", "捧杯", "签约", "换帅", "召回", "获奖", "晋级",
)

_CHANNEL_TAG = {
    "sports": "体育",
    "ent": "娱乐",
    "tech": "科技",
    "finance": "财经",
    "mil": "军事",
    "world": "国际",
    "game": "游戏",
    "auto": "汽车",
    "edu": "教育",
    "top": "新闻",
}


def _pad_tag(channel: str) -> str:
    if channel.startswith("q:"):
        return channel[2:].strip()[:8] or "新闻"
    return _CHANNEL_TAG.get(channel) or "新闻"

_STOP = {
    "最新", "消息", "快讯", "突发", "独家", "记者", "报道", "本文", "今日", "刚刚",
    "一个", "这个", "那个", "什么", "怎么", "还是", "已经", "可以", "不是", "没有",
    "自己", "他们", "我们", "因为", "以及", "但是", "如果", "所以", "问题", "情况",
    "方面", "时候", "地方", "相关", "可能", "主动权", "看点", "热点", "资讯", "新闻",
    "热门", "热议", "涨知识", "正能量", "高光时刻", "精彩瞬间", "一场", "只要", "下场",
}
_ALIAS = {"莎莎": "孙颖莎", "胖球": "乒乓球"}
_STRIP = re.compile(r"[#＃\s，,。！!？?：:；;·\|／/]+")
_BOOK = re.compile(r"《([^》]{2,12})》")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9.\-]{1,15}")
_SPLIT = re.compile(r"[，,。！!？?：:；;\|／/\s]+")
_BREAK = set("队拿独出重加夺从在以的了把被让向和与起战胜负平骂掏连创率")
_NAME_TAIL = set("大小骂")


def _hit(text: str, words: Iterable[str]) -> List[str]:
    return [w for w in words if w and w in text]


def _clean_tag(raw: str) -> str:
    tag = _ALIAS.get(raw, raw)
    tag = _STRIP.sub("", tag)
    tag = re.sub(r"^(最新|突发|快讯)", "", tag)
    return tag[:12]


def _usable(tag: str) -> bool:
    if tag in _STOP or len(tag) < 2 or len(tag) > 12:
        return False
    if tag.isdigit():
        return False
    return any("\u4e00" <= ch <= "\u9fff" or ch.isalnum() for ch in tag)


def _head_name(part: str) -> str:
    m = re.match(r"[\u4e00-\u9fff]+", part)
    if not m:
        return ""
    han = m.group(0)
    if 2 <= len(han) <= 4:
        if len(han) == 2 and len(part) > len(han):
            return ""
        return han if _usable(han) else ""
    for n in (3, 4, 2):
        if n >= len(han):
            continue
        chunk, nxt = han[:n], han[n]
        if n == 4 and chunk[-1] in _NAME_TAIL:
            continue
        if not _usable(chunk):
            continue
        if nxt in _BREAK or (n == 3 and nxt in _NAME_TAIL):
            return chunk
    return ""


def _from_title(text: str) -> List[str]:
    out: List[str] = []
    for book in _BOOK.findall(text):
        out.append(book)
    for token in _LATIN.findall(text):
        if 2 <= len(token) <= 12:
            out.append(token)
    for part in _SPLIT.split(text):
        part = part.strip("《》\"'（）()·")
        if not part:
            continue
        if 2 <= len(part) <= 12 and _usable(part):
            out.append(part)
        name = _head_name(part)
        if name:
            out.append(name)
    return out


def hot_tags(
    title: str,
    hook: str = "",
    body: str = "",
    source_title: str = "",
    summary: str = "",
    channel: str = "sports",
) -> List[str]:
    head = " ".join((source_title, title, hook))
    blob = " ".join((head, body, summary))
    tags: List[str] = []

    def add(items: Sequence[str]) -> None:
        for item in items:
            tag = _clean_tag(item)
            if _usable(tag) and tag not in tags:
                tags.append(tag)

    add(_from_title(head))
    add(_hit(blob, _NAMES))
    add(_hit(blob, _TEAMS))
    add(_hit(blob, _EVENTS))
    add(_hit(blob, _ACTIONS))
    for find, core in _CLUSTERS:
        keys = find.split()
        hits = _hit(blob, keys)
        if not hits:
            continue
        add(hits)
        named = [c for c in core if c in blob]
        add(named or (core[0],))
    add((_pad_tag(channel),))
    return tags[:MAX_TAGS]


def hashtags_line(tags: Sequence[str]) -> str:
    return " ".join("#" + t for t in tags if t)


def channels_caption(title: str, hook: str, tags: Sequence[str]) -> str:
    head = title.strip()
    extra = (hook or "").strip()
    if extra and extra not in head:
        head = head + "｜" + extra
    line = hashtags_line(tags)
    return (head + "\n\n" + line).strip()
