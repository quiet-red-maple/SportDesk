# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖腾讯热榜与 Bing 新闻 RSS
[OUTPUT]: 对外提供 NewsItem、CHANNELS、DEFAULT_CHANNEL、list_channels、fetch_hot、find_item、enrich_images
[POS]: news 的采集器；点选时 getSimpleNews 抽正文，HTML 配图兜底
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from agent.news.hashtags import topic_needles

QQ_HOT = "https://i.news.qq.com/web_feed/getHotModuleList"
BING_NEWS = "https://www.bing.com/news/search"
CUSTOM_PREFIX = "q:"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_CHANNEL = "sports"
# id, 中文名, 腾讯 channel_id
CHANNELS: Tuple[Tuple[str, str, str], ...] = (
    ("sports", "体育", "news_news_sports"),
    ("top", "要闻", "news_news_top"),
    ("ent", "娱乐", "news_news_ent"),
    ("tech", "科技", "news_news_tech"),
    ("finance", "财经", "news_news_finance"),
    ("mil", "军事", "news_news_mil"),
    ("world", "国际", "news_news_world"),
    ("game", "游戏", "news_news_game"),
    ("auto", "汽车", "news_news_auto"),
    ("edu", "教育", "news_news_edu"),
)

_BAG: Dict[str, List["NewsItem"]] = {}
_PACK: Dict[str, Tuple[List[str], str]] = {}
_BIGORIG = re.compile(r'"bigOrigUrl"\s*:\s*"(https:[^"\\]+)"')
_P_TAG = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
_CMS_ID = re.compile(r"^20\d{6}[A-Za-z0-9]+$")
_CMS_URL = re.compile(r"/a/(20\d{6}[A-Za-z0-9]+)")
_HTML_TAG = re.compile(r"<[^>]+>")
_SKIP_P = re.compile(r"(发布于|创作者|责任编辑|扫码|下载腾讯|打开腾讯新闻|点击关注)")
_CONTENT_IMG = re.compile(r'(?:src|data-src)="(https://inews\.gtimg\.com/[^"]+)"')


@dataclass
class NewsItem:
    news_id: str
    title: str
    url: str
    published: str
    summary: str
    image_urls: List[str] = field(default_factory=list)
    source: str = "腾讯体育"
    channel: str = DEFAULT_CHANNEL
    article: str = ""


def list_channels() -> List[Dict[str, str]]:
    return [{"id": cid, "name": name} for cid, name, _ in CHANNELS]


def resolve_channel(channel: Optional[str]) -> Tuple[str, str, str]:
    wanted = (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    query = wanted[len(CUSTOM_PREFIX) :].strip() if wanted.startswith(CUSTOM_PREFIX) else wanted
    if wanted.startswith(CUSTOM_PREFIX):
        if not query:
            raise ValueError("请输入类目")
        query = query[:16]
        for cid, name, qq_id in CHANNELS:
            if query == cid or query == name:
                return cid, name, qq_id
        return CUSTOM_PREFIX + query, query, ""
    for row in CHANNELS:
        if row[0] == wanted:
            return row
    raise ValueError("没有这个榜单: " + wanted)


def channel_name(channel: Optional[str]) -> str:
    return resolve_channel(channel)[1]


class _PrefHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        infos = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        infos.sort(key=lambda item: 0 if item[0] == socket.AF_INET else 1)
        err = None
        sock = None
        for family, socktype, proto, _, sockaddr in infos:
            try:
                sock = socket.socket(family, socktype, proto)
                if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(self.timeout)
                sock.connect(sockaddr)
                break
            except OSError as exc:
                err = exc
                if sock:
                    sock.close()
                    sock = None
        else:
            raise err or OSError("无法连接 " + str(self.host))
        self.sock = sock
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        host = self._tunnel_host or self.host
        if self._tunnel_host:
            self._tunnel()
        context = getattr(self, "_context", None) or ssl.create_default_context()
        self.sock = context.wrap_socket(self.sock, server_hostname=host)


class _PrefHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PrefHTTPSConnection, req)


_OPENER = urllib.request.build_opener(_PrefHTTPSHandler())


def _urlopen(req, timeout: int = 8):
    return _OPENER.open(req, timeout=timeout)


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Origin": "https://news.qq.com",
        "Referer": "https://news.qq.com/",
    }


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    last: Optional[Exception] = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=raw, headers=_headers(), method="POST")
        try:
            with _urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(0.35 * (attempt + 1))
    raise last or RuntimeError("热点源无响应")


def _img_key(url: str) -> str:
    m = re.search(r"/(?:news_ls|om_bt|news_bt|newsapp_bt)/([^/?]+)", url)
    if not m:
        return url
    name = m.group(1)
    name = re.sub(r"_\d+x\d+s$", "", name)
    name = re.sub(r"_\d+$", "", name)
    return name


# 分享卡 240×240 像素里烧着「阅读」，拉满竖屏会变成背景字。
_SHARE_CARD = re.compile(r"_(240240|330330)(?:/|$)")


def _upgrade_img(url: str) -> str:
    url = re.sub(r"/641$", "/0", url)
    for src, dst in (
        ("_197130", "_870492"),
        ("_196130", "_870492"),
        ("_150120", "_870492"),
        ("_294195", "_870492"),
        ("_640330", "_870492"),
    ):
        url = url.replace(src, dst)
    return url


def _uniq_imgs(bag: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for url in bag:
        if not url or not str(url).startswith("http") or _SHARE_CARD.search(url):
            continue
        if "_181x181" in url:
            continue
        url = _upgrade_img(url)
        k = _img_key(url)
        if k in seen:
            continue
        seen.add(k)
        out.append(url)
    return out


def _collect_images(item: Dict[str, Any]) -> List[str]:
    pics = item.get("pic_info") or {}
    bag: List[str] = []
    for key in ("big_img", "three_img", "small_img"):
        val = pics.get(key) or []
        if isinstance(val, str):
            val = [val]
        bag.extend(val)
    return _uniq_imgs(bag)


def _decode(raw: bytes) -> str:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://news.qq.com/"})
    with _urlopen(req, timeout=8) as resp:
        return _decode(resp.read())


def _cms_of(url: str, news_id: str = "") -> str:
    if _CMS_ID.match(news_id or ""):
        return news_id
    m = _CMS_URL.search(url or "")
    return m.group(1) if m else ""


def _plain_html(html: str) -> str:
    if not html:
        return ""
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    if len(html) < 24:
        return ""
    html = re.sub(r"</?[Pp][^>]*>|<br\s*/?>", "。", html)
    text = _HTML_TAG.sub("", html.replace("\xa0", " "))
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"。{2,}", "。", text)
    return text.strip(" 。")


def _api_article(cms: str) -> str:
    if not cms:
        return ""
    try:
        data = json.loads(_get_text("https://r.inews.qq.com/getSimpleNews?id=" + cms))
    except Exception:
        return ""
    block = data.get("content")
    text = block.get("text") if isinstance(block, dict) else ""
    return _plain_html(text if isinstance(text, str) else "")


def _article_text(html: str) -> str:
    start = -1
    for mark in ("content-article", "rich_media_content", "article-content"):
        start = html.find(mark)
        if start >= 0:
            break
    chunk = html[start : start + 80000] if start >= 0 else html
    paras: List[str] = []
    total = 0
    for raw in _P_TAG.findall(chunk):
        text = _HTML_TAG.sub("", raw.replace("\xa0", " "))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 12 or _SKIP_P.search(text):
            continue
        if text in paras:
            continue
        paras.append(text)
        total += len(text)
        if total >= 1200:
            break
    out = []
    for p in paras:
        out.append(p if p[-1] in "。！？；" else p + "。")
    return "".join(out)


def _article_pack(url: str, news_id: str = "") -> Tuple[List[str], str]:
    key = url or news_id
    if not key:
        return [], ""
    hit = _PACK.get(key)
    if hit is not None:
        return hit
    imgs: List[str] = []
    html_text = ""
    if url and url.startswith("http"):
        try:
            html = _get_text(url)
            imgs = _article_imgs(html)
            html_text = _article_text(html)
        except Exception:
            pass
    api_text = _api_article(_cms_of(url, news_id)) if len(html_text) < 40 else ""
    article = api_text if len(api_text) >= len(html_text) else html_text
    pack = (imgs, article)
    _PACK[key] = pack
    return pack


def _article_imgs(html: str) -> List[str]:
    bag = [u.replace("\\/", "/") for u in _BIGORIG.findall(html)]
    start = html.find("content-article")
    chunk = html[start : start + 80000] if start >= 0 else html
    for url in _CONTENT_IMG.findall(chunk):
        if "200200" in url or "/om_ls/" in url or "/newsapp_ls/" in url:
            continue
        bag.append(url)
    return _uniq_imgs(bag)


def enrich_images(item: NewsItem, want: int = 5) -> NewsItem:
    extra, article = _article_pack(item.url, item.news_id)
    if article:
        item.article = article
    if extra:
        item.image_urls = extra[:want]
    else:
        item.image_urls = list(item.image_urls)[:want]
    return item


def _summary_of(item: Dict[str, Any]) -> str:
    text = item.get("long_summary") or item.get("desc") or ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_item(raw: Dict[str, Any], channel: str, fallback_source: str) -> Optional[NewsItem]:
    title = (raw.get("title") or "").strip()
    news_id = (raw.get("id") or "").strip()
    if not title or not news_id:
        return None
    link = raw.get("link_info") or {}
    url = link.get("url") or link.get("share_url") or ""
    media = raw.get("media_info") or {}
    source = media.get("chl_name") or media.get("media_name") or fallback_source
    return NewsItem(
        news_id=news_id,
        title=title,
        url=url,
        published=raw.get("publish_time") or "",
        summary=_summary_of(raw),
        image_urls=_collect_images(raw),
        source=source,
        channel=channel,
    )


def _score(item: NewsItem) -> float:
    score = 0.0
    if item.image_urls:
        score += 3
    if item.summary:
        score += 2 + min(len(item.summary), 160) / 80.0
    if item.published.startswith(datetime.now().strftime("%Y-%m-%d")):
        score += 3
    hot = ("逆转", "冲突", "夺冠", "发文", "离职", "争议", "爆", "绝杀", "突发", "回应")
    score += sum(0.6 for w in hot if w in item.title or w in item.summary)
    return score


def _borrow_images(items: List[NewsItem]) -> None:
    def grams(text: str) -> set:
        s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
        return {s[i : i + 2] for i in range(max(0, len(s) - 1))}

    packed = [(it, grams(it.title)) for it in items]
    for it, g in packed:
        if len(it.image_urls) >= 3 or not g:
            continue
        ranked = sorted(packed, key=lambda x: len(g & x[1]), reverse=True)
        for other, other_g in ranked:
            if other is it or len(g & other_g) < 2:
                continue
            for url in other.image_urls:
                if url not in it.image_urls:
                    it.image_urls.append(url)
                if len(it.image_urls) >= 4:
                    break
            if len(it.image_urls) >= 4:
                break


def _overlap_score(item: NewsItem, query: str) -> int:
    title = item.title
    blob = item.title + item.summary
    for word in topic_needles(query):
        if word in title:
            return 200
        if word in blob:
            return 120
    return 0


def _load_board(cid: str, name: str, qq_id: str, limit: int) -> List[NewsItem]:
    items: List[NewsItem] = []
    try:
        data = _post_json(
            QQ_HOT,
            {
                "qimei36": "0_desk_" + cid,
                "base_req": {"from": "pc"},
                "device_id": "0_desk_" + cid,
                "item_count": 20,
                "forward": "2",
                "flush_num": 0,
                "channel_id": qq_id,
            },
        )
        for raw in data.get("data") or []:
            parsed = _parse_item(raw, cid, "腾讯" + name)
            if parsed:
                items.append(parsed)
    except Exception:
        items = []
    if not items:
        try:
            items = _search_web(name, cid, limit)
        except Exception:
            items = []
    if not items:
        raise RuntimeError("热点源暂时连不上，当前网络可能被限制，换 VPN 后再刷新")
    _borrow_images(items)
    items.sort(key=_score, reverse=True)
    picked = items[:limit]
    _BAG[cid] = picked
    return picked


def _scan_boards(query: str, cid: str) -> List[NewsItem]:
    hits: List[NewsItem] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_load_board, ch, name, qq, 16) for ch, name, qq in CHANNELS]
        for fut in as_completed(futs):
            try:
                rows = fut.result()
            except Exception:
                continue
            for it in rows:
                if _overlap_score(it, query):
                    hits.append(replace(it, channel=cid))
    return hits


def _xml_tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _search_web(query: str, cid: str, limit: int) -> List[NewsItem]:
    url = BING_NEWS + "?" + urlencode({"q": query, "format": "RSS"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    root = ET.fromstring(_urlopen(req, timeout=8).read())
    items: List[NewsItem] = []
    for node in root.findall(".//item"):
        fields = {_xml_tag(child): (child.text or "").strip() for child in list(node)}
        title = fields.get("title") or ""
        if not title:
            continue
        img = fields.get("Image") or ""
        if img.startswith("http://"):
            img = "https://" + img[7:]
        if "bing.com/th?" in img and "w=" not in img:
            img += "&w=870&h=492"
        published = fields.get("pubDate") or ""
        try:
            published = parsedate_to_datetime(published).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError):
            pass
        summary = re.sub(r"<[^>]+>", "", fields.get("description") or "")
        news_id = "web:" + hashlib.md5(title.encode("utf-8")).hexdigest()[:16]
        items.append(
            NewsItem(
                news_id=news_id,
                title=title,
                url=fields.get("link") or "",
                published=published,
                summary=summary,
                image_urls=_uniq_imgs([img] if img else []),
                source=fields.get("Source") or "新闻",
                channel=cid,
            )
        )
        if len(items) >= limit:
            break
    return items


def _fetch_search(query: str, cid: str, limit: int) -> List[NewsItem]:
    found: List[NewsItem] = []
    seen = set()

    def take(rows: List[NewsItem]) -> None:
        for it in rows:
            if it.news_id in seen:
                continue
            seen.add(it.news_id)
            found.append(it)

    take(_scan_boards(query, cid))
    if len(found) < limit:
        try:
            take(_search_web(query, cid, limit))
        except Exception:
            pass
    found.sort(key=lambda it: (_overlap_score(it, query), _score(it)), reverse=True)
    picked = found[:limit]
    _borrow_images(picked)
    _BAG[cid] = picked
    return picked


def fetch_hot(limit: int = 16, channel: Optional[str] = None) -> List[NewsItem]:
    cid, name, qq_id = resolve_channel(channel)
    if cid.startswith(CUSTOM_PREFIX):
        return _fetch_search(name, cid, limit)
    return _load_board(cid, name, qq_id, limit)


def find_item(news_id: str, channel: Optional[str] = None) -> Optional[NewsItem]:
    wanted = (news_id or "").strip()
    if not wanted:
        return None
    cid = ""
    if channel:
        try:
            cid = resolve_channel(channel)[0]
        except ValueError:
            cid = channel
    order: List[str] = []
    if cid:
        order.append(cid)
    order.extend(key for key in _BAG if key not in order)
    order.extend(row[0] for row in CHANNELS if row[0] not in order)
    for key in order:
        bag = _BAG.get(key)
        if not bag:
            continue
        for it in bag:
            if it.news_id == wanted:
                return it
    return None
