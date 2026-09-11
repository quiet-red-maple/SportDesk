# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 NewsItem、MAX_BODY_CHARS、hashtags
[OUTPUT]: 对外提供 Script 与 to_script，含从原文抽出的视频号热词
[POS]: news 的文案刀；口播抽本文数字/福利/比分，不把标题截成一句就交差
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from agent.news.fetch import NewsItem
from agent.news.hashtags import channels_caption, hashtags_line, hot_tags
from agent.style import MAX_BODY_CHARS, MAX_HOOK_CHARS, MAX_TITLE_CHARS


@dataclass
class Script:
    news_id: str
    source_title: str
    title: str
    hook: str
    body: str
    image_urls: List[str] = field(default_factory=list)
    source: str = ""
    url: str = ""
    hashtags: List[str] = field(default_factory=list)
    hashtags_line: str = ""
    channels_caption: str = ""


_FILLER = re.compile(r"^(最新消息|刚刚|快讯|独家|突发)[：:]")
_JUNK = re.compile(r"(虎扑\d*月?\d*日讯|记者\S{1,6}报道|本文来自\S+)")
_SPORT = re.compile(r"(战胜|击败|逆转|绝杀|夺冠|晋级|出局|大胜|惨败|破门|绝平)")
_ACT = re.compile(
    r"(战胜|击败|逆转|绝杀|夺冠|宣布|确认|回应|当选|获刑|去世|签约|晋级|出局|"
    r"大胜|惨败|破门|绝平|升至|跌至|获奖|立案|起诉|发布|救出|起火|营救|险胜|罢免|"
    r"领取|上线|限时|免费|发放|开放|更新|白嫖|买断|折扣)"
)
_MEAT = re.compile(
    r"\d|(点券|夺宝|皮肤|福利|限时|免费|白嫖|买断|比分|登录|领取|碎片|积分)"
)
_WEAK = re.compile(r"(解读|玩梗|比肩|盘点|一文看懂|社评|深度|评论)")
_SKIP_SENT = re.compile(r"^(有人说|无数人|还有人|据悉|本文)|工作人员没有|没有官方确认")
_FLUFF = re.compile(
    r"((?:美网)?第\d+轮的一场焦点之战当中，?|像是打通了任督二脉|出人意料地|据悉|"
    r"几乎复制了[^，。]{0,24}|"
    r"无数人对这支球队很失望)"
)
_FUNC = (
    "情况", "当中", "其中", "一场", "焦点", "之战", "几乎", "复制", "上演",
    "连赢", "落后", "官方", "目前", "没有", "工作人员", "职务", "信息",
    "得主", "冠军", "大满贯", "选手", "球员", "实施", "附加", "不是", "而是",
)
_CLAUSE = re.compile(r"[！？。／/]")


def _clean(text: str) -> str:
    text = _JUNK.sub("", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _pool(item: NewsItem) -> str:
    art = _clean(item.article)
    if len(art) >= 40:
        return art
    return art or _clean(item.summary) or _clean(item.title)


def _clauses(text: str) -> List[str]:
    return [p.strip() for p in _CLAUSE.split(text) if len(p.strip()) >= 6]


def _sents(text: str) -> List[str]:
    out: List[str] = []
    for s in re.split(r"[。！？]", text):
        s = s.strip("　 \t「」\"'")
        if len(s) >= 8:
            out.append(s)
    return out


def _thin(s: str) -> str:
    s = _FLUFF.sub("", s)
    s = re.sub(r"，{2,}", "，", s)
    s = re.sub(r"的，", "，", s)
    return s.strip("，；、 ")


def _facts(pool: str) -> List[str]:
    sents = []
    for s in _sents(pool)[:12]:
        if _SKIP_SENT.search(s) or _WEAK.search(s):
            continue
        t = _thin(s)
        if len(t) >= 8:
            sents.append(t)
    hard = [s for s in sents if _MEAT.search(s) or _ACT.search(s)]
    picked = hard or sents
    out: List[str] = []
    for s in picked:
        if s not in out:
            out.append(s)
        if len(out) >= 4:
            break
    return out


def _name_in(chunk: str, title: str) -> str:
    names = re.findall(r"[\u4e00-\u9fff]{2,4}|[A-Za-z][A-Za-z0-9\-]{1,12}", chunk)
    hit = [n.strip() for n in names if n.strip() in title]
    if hit:
        return max(hit, key=len)
    for n in reversed(names):
        n = n.strip()
        if n and n not in _FUNC:
            return n
    return ""


def _fit(s: str, limit: int) -> str:
    s = _thin(s).strip()
    if len(s) <= limit:
        return s
    win = s[:limit]
    for mark in "，、； ":
        i = win.rfind(mark)
        if i >= 6:
            return win[:i].rstrip("，、； ")
    win = re.sub(r"[\dA-Za-z]+$", "", win)
    return win.rstrip("，、的以在")


def _headline(s: str, title: str, n: int = MAX_TITLE_CHARS) -> str:
    m = _SPORT.search(s)
    if not m:
        return ""
    subj = _name_in(re.sub(r"(直落两盘|以?\d+比\d+|的)$", "", s[: m.start()]), title)
    rest = s[m.end() :].lstrip("了")
    obj = _name_in(rest[:12], title) or _name_in(rest[:36], title) or _name_in(rest[:36], s)
    out = (subj + m.group(0) + obj).replace(" ", "")
    if len(out) < 4:
        return ""
    return out if len(out) <= n else _fit(out, n)


def _first_clause(title: str) -> str:
    core = _FILLER.sub("", title).strip()
    core = re.sub(r"[（(][^）)]*[）)]", "", core).strip()
    m = re.match(r"^([^：:]{1,6})[：:](.+)$", core)
    if m and re.search(r"(解读|快讯|名记|社评|独家|刚刚)", m.group(1)):
        core = m.group(2).strip()
    bits = _clauses(core) or [core]
    clause = bits[0]
    if len(clause) > MAX_TITLE_CHARS:
        words = [w for w in re.split(r"\s+", clause) if w]
        if words and 4 <= len(words[0]) <= MAX_TITLE_CHARS:
            return words[0]
    return clause


def _punch_title(title: str, facts: List[str]) -> str:
    clause = _first_clause(title)
    if 4 <= len(clause) <= MAX_TITLE_CHARS:
        return clause
    for seed in facts:
        head = _headline(seed, title)
        if head:
            return head
    return _headline(clause, title) or _fit(clause or title, MAX_TITLE_CHARS)


def _punch_hook(title_s: str, facts: List[str], origin: str) -> str:
    blob = "。".join(facts)
    for pat in (r"\d+比\d+", r"0-\d落后", r"连赢\d+局", r"第\d+次"):
        m = re.search(pat, blob)
        if not m:
            continue
        left = max(blob.rfind("。", 0, m.start()), blob.rfind("，", 0, m.start()))
        start = left + 1
        rights = [blob.find(x, m.end()) for x in "。，"]
        rights = [x for x in rights if x >= 0]
        end = min(rights) if rights else len(blob)
        phrase = _thin(blob[start:end])
        if len(phrase) < 4:
            phrase = _thin(blob[m.start():end])
        hit = _fit(phrase, MAX_HOOK_CHARS)
        if hit and hit != title_s:
            return hit
    for s in facts:
        t = _fit(s, MAX_HOOK_CHARS)
        if t and t != title_s and not t.startswith(title_s):
            return t
    for bit in _clauses(origin):
        if bit != title_s and title_s not in bit:
            return _fit(bit, MAX_HOOK_CHARS)
    return _fit(facts[0] if facts else origin, MAX_HOOK_CHARS)


def _punch_body(facts: List[str], origin: str) -> str:
    used: List[str] = []
    seeds = facts or _clauses(origin) or [_clean(origin)]
    for s in seeds:
        text = "。".join(used + [s]) + "。"
        if len(text) > MAX_BODY_CHARS and used:
            break
        used.append(s)
        if len(used) >= 3:
            break
    text = "。".join(used) + "。"
    if len(text) > MAX_BODY_CHARS:
        text = _fit(text.rstrip("。"), MAX_BODY_CHARS)
        if text and text[-1] not in "。！？":
            text += "。"
    return text


def to_script(item: NewsItem, title: Optional[str] = None, hook: Optional[str] = None, body: Optional[str] = None) -> Script:
    facts = _facts(_pool(item))
    punched = _punch_title(item.title, facts)
    title_s = (title or punched).strip()
    hook_s = (hook or _punch_hook(title_s, facts, item.title)).strip()
    body_s = (body or _punch_body(facts, item.title)).strip()
    tags = hot_tags(
        title_s,
        hook_s,
        body_s,
        source_title=item.title,
        summary=item.article or item.summary,
        channel=item.channel,
    )
    return Script(
        news_id=item.news_id,
        source_title=item.title,
        title=title_s,
        hook=hook_s,
        body=body_s,
        image_urls=list(item.image_urls),
        source=item.source,
        url=item.url,
        hashtags=tags,
        hashtags_line=hashtags_line(tags),
        channels_caption=channels_caption(title_s, hook_s, tags),
    )
