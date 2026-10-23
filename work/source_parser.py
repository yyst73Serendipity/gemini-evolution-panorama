"""
解析 Google 官方 Feed、Sitemap、HTML 元数据、发布说明和稳定正文，并分类更新候选。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urlsplit
from xml.etree import ElementTree

from timeline_core import ALLOWED_HOSTS, canonical_source_url

_BLOCK_TAGS = {"article", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "main", "p", "section", "time"}
_SKIP_TAGS = {"footer", "nav", "script", "style", "svg", "template", "noscript"}
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
_NOISE_TOKENS = {"cookie", "consent", "breadcrumb", "navigation", "newsletter", "social-share", "site-header", "site-footer"}
_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def _local_name(tag: str) -> str:
    """移除 XML 命名空间前缀。"""
    return tag.rsplit("}", 1)[-1].lower()


def _compact(value: str | None) -> str:
    """折叠空白，便于稳定比较和输出。"""
    return " ".join((value or "").split())


def _official_url(url: str) -> str:
    """验证并规范化允许的 Google 官方 HTTPS URL。"""
    canonical = canonical_source_url(url)
    parsed = urlsplit(canonical)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"非允许的 Google 官方来源: {url}")
    return canonical


def _parse_date(value: str | None) -> str | None:
    """把明确的 ISO、RFC 2822 或英文日期转换为 YYYY-MM-DD。"""
    cleaned = _compact(value)
    if not cleaned:
        return None
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", cleaned)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(1), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(cleaned).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    for pattern in _DATE_PATTERNS[1:]:
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _child_text(element: ElementTree.Element, names: Iterable[str]) -> str:
    """读取 XML 节点的首个指定子元素文本。"""
    wanted = set(names)
    for child in element:
        if _local_name(child.tag) in wanted:
            return _compact("".join(child.itertext()))
    return ""


def parse_feed(text: str) -> list[dict]:
    """解析 RSS 或 Atom，保留明确发布日期和官方链接。"""
    root = ElementTree.fromstring(text)
    root_name = _local_name(root.tag)
    entries = [node for node in root.iter() if _local_name(node.tag) in {"entry", "item"}]
    if root_name not in {"feed", "rss", "rdf"} and not entries:
        raise ValueError("不是可识别的 RSS 或 Atom 文档")

    items: list[dict] = []
    for entry in entries:
        title = _child_text(entry, {"title"})
        summary = _child_text(entry, {"summary", "description", "content"})
        published = _child_text(entry, {"published", "pubdate", "issued", "date", "updated"})
        url = ""
        for child in entry:
            if _local_name(child.tag) != "link":
                continue
            relation = child.attrib.get("rel", "alternate")
            candidate = child.attrib.get("href") or _compact(child.text)
            if candidate and relation in {"alternate", ""}:
                url = candidate
                break
        if not url:
            url = _child_text(entry, {"guid"})
        if not title or not url:
            continue
        try:
            canonical = _official_url(url)
        except ValueError:
            continue
        item = {"title": title, "url": canonical, "summary": summary}
        parsed_date = _parse_date(published)
        if parsed_date:
            item["date"] = parsed_date
        items.append(item)
    return items


def parse_sitemap(text: str) -> list[dict]:
    """解析 Sitemap；lastmod 仅作为变更线索，不冒充发布日期。"""
    root = ElementTree.fromstring(text)
    items: list[dict] = []
    for node in root.iter():
        if _local_name(node.tag) != "url":
            continue
        location = _child_text(node, {"loc"})
        if not location:
            continue
        try:
            canonical = _official_url(location)
        except ValueError:
            continue
        item = {"url": canonical}
        lastmod = _child_text(node, {"lastmod"})
        if lastmod:
            item["lastmod"] = lastmod
        items.append(item)
    return items


class _PageParser(HTMLParser):
    """收集 HTML 元数据、JSON-LD、时间和可稳定比较的正文行。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.times: list[str] = []
        self.json_ld: list[Any] = []
        self.lines: list[str] = []
        self._stack: list[tuple[str, bool]] = []
        self._skip_depth = 0
        self._in_title = False
        self._json_ld_depth = 0
        self._json_parts: list[str] = []
        self._line_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}
        signature = f"{attributes.get('id', '')} {attributes.get('class', '')}".casefold()
        noisy = lowered in _SKIP_TAGS or any(token in signature for token in _NOISE_TOKENS)
        inherited_skip = self._skip_depth > 0
        skipped = noisy or inherited_skip
        if lowered not in _VOID_TAGS:
            self._stack.append((lowered, skipped))
            if skipped:
                self._skip_depth += 1

        if lowered == "title":
            self._in_title = True
        if lowered == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
                or ""
            ).casefold()
            content = _compact(attributes.get("content"))
            if key and content:
                self.meta[key] = content
        if lowered == "time" and attributes.get("datetime"):
            self.times.append(attributes["datetime"])
        if lowered == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._json_ld_depth = len(self._stack)
            self._json_parts = []
        if lowered in _BLOCK_TAGS and self._line_parts:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in _BLOCK_TAGS:
            self._flush_line()
        if lowered == "title":
            self._in_title = False
        if lowered == "script" and self._json_ld_depth:
            raw = "".join(self._json_parts).strip()
            if raw:
                try:
                    self.json_ld.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            self._json_ld_depth = 0
            self._json_parts = []

        match_index = next(
            (index for index in range(len(self._stack) - 1, -1, -1) if self._stack[index][0] == lowered),
            None,
        )
        if match_index is None:
            return
        removed = self._stack[match_index:]
        del self._stack[match_index:]
        skipped_count = sum(1 for _, skipped in removed if skipped)
        self._skip_depth = max(0, self._skip_depth - skipped_count)

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_parts.append(data)
        compact = _compact(data)
        if not compact:
            return
        if self._in_title:
            self.title_parts.append(compact)
        if self._skip_depth == 0:
            self._line_parts.append(compact)

    def close(self) -> None:
        super().close()
        self._flush_line()

    def _flush_line(self) -> None:
        line = _compact(" ".join(self._line_parts))
        if line and re.fullmatch(r"\d{12,}", line) is None:
            self.lines.append(line)
        self._line_parts = []


def _parse_html(text: str) -> _PageParser:
    """解析一份 HTML 并返回收集器。"""
    parser = _PageParser()
    parser.feed(text)
    parser.close()
    return parser


def _json_ld_objects(value: Any) -> Iterable[dict]:
    """递归展开 JSON-LD 对象、数组和 @graph。"""
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph is not None:
            yield from _json_ld_objects(graph)
    elif isinstance(value, list):
        for item in value:
            yield from _json_ld_objects(item)


def stable_page_text(text: str) -> str:
    """移除导航、脚本、页脚和 Cookie 噪声，返回稳定正文文本。"""
    parser = _parse_html(text)
    return "\n".join(dict.fromkeys(parser.lines))


def parse_page_metadata(text: str, url: str) -> dict:
    """提取官方 HTML 页面的规范 URL、标题、摘要、发布日期和稳定正文。"""
    canonical = _official_url(url)
    parser = _parse_html(text)
    objects = [item for raw in parser.json_ld for item in _json_ld_objects(raw)]

    json_title = next(
        (_compact(item.get("headline") or item.get("name")) for item in objects if item.get("headline") or item.get("name")),
        "",
    )
    title = json_title or parser.meta.get("og:title") or parser.meta.get("twitter:title") or _compact(" ".join(parser.title_parts))
    description = (
        parser.meta.get("og:description")
        or parser.meta.get("description")
        or parser.meta.get("twitter:description")
        or ""
    )
    date_candidates = [item.get("datePublished") for item in objects if item.get("datePublished")]
    date_candidates.extend(
        parser.meta.get(key)
        for key in ("article:published_time", "datepublished", "date", "publishdate")
        if parser.meta.get(key)
    )
    date_candidates.extend(parser.times)

    metadata = {
        "url": canonical,
        "title": title,
        "description": description,
        "stable_text": "\n".join(dict.fromkeys(parser.lines)),
    }
    for candidate in date_candidates:
        parsed_date = _parse_date(str(candidate))
        if parsed_date:
            metadata["date"] = parsed_date
            break
    return metadata


def parse_release_notes(text: str, url: str) -> list[dict]:
    """按明确日期标题拆分官方发布说明，避免用页面修改时间推断发布日期。"""
    canonical = _official_url(url)
    parser = _parse_html(text)
    items: list[dict] = []
    current_date: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_date and current_lines:
            summary = _compact(" ".join(current_lines))
            if summary:
                items.append(
                    {
                        "date": current_date,
                        "title": current_lines[0][:180],
                        "summary": summary[:1200],
                        "url": canonical,
                    }
                )

    for line in parser.lines:
        parsed_date = _parse_date(line)
        is_date_heading = parsed_date is not None and len(line) <= 48
        if is_date_heading:
            flush()
            current_date = parsed_date
            current_lines = []
        elif current_date:
            current_lines.append(line)
    flush()
    return items


def classify_candidate(text: str) -> dict:
    """按明确关键词分类 Gemini 相关候选，并返回可审计命中项。"""
    normalized = _compact(text).casefold()
    family_keywords = (
        ("Google AI Studio", ("google ai studio",)),
        ("Google AI Ultra", ("google ai ultra",)),
        ("Google AI Pro", ("google ai pro",)),
        ("Google One AI Premium", ("google one ai premium",)),
        ("Gemini Code Assist", ("gemini code assist",)),
        ("Gemini CLI", ("gemini cli",)),
        ("NotebookLM", ("notebooklm",)),
        ("Project Astra", ("project astra",)),
        ("Vertex AI", ("vertex ai",)),
        ("Jules", ("jules",)),
        ("Gemma", ("gemma",)),
        ("Bard", ("bard",)),
        ("Gemini", ("gemini",)),
    )
    families = [family for family, keywords in family_keywords if any(keyword in normalized for keyword in keywords)]
    matched_keywords = [keyword for _, keywords in family_keywords for keyword in keywords if keyword in normalized]
    if not matched_keywords:
        return {
            "category": "产品",
            "families": [],
            "lifecycle": "升级",
            "confidence": "low",
            "matched_keywords": [],
        }

    lifecycle = "升级"
    if any(keyword in normalized for keyword in ("deprecat", "shut down", "shutdown", "retire", "sunset", "弃用", "停止服务")):
        category = "生命周期"
        lifecycle = "弃用"
    elif any(keyword in normalized for keyword in ("subscription", "plan", "pricing", "price", "订阅", "套餐")) and any(
        family.startswith("Google AI") or family == "Google One AI Premium" for family in families
    ):
        category = "订阅计划"
    elif any(keyword in normalized for keyword in ("api", "developer", "vertex ai", "ai studio", "code assist", "jules", "cli", "sdk")):
        category = "开发者平台"
    elif "bard" in normalized or "notebooklm" in normalized or any(
        keyword in normalized for keyword in ("app", "audio overview", "live", "canvas", "deep research")
    ):
        category = "产品"
    elif any(keyword in normalized for keyword in ("model", "gemma", "context window", "multimodal", "reasoning")):
        category = "模型"
    else:
        category = "产品"

    confidence = "high" if any(keyword in normalized for keyword in ("gemini", "gemma", "bard", "notebooklm")) else "medium"
    return {
        "category": category,
        "families": families,
        "lifecycle": lifecycle,
        "confidence": confidence,
        "matched_keywords": sorted(set(matched_keywords)),
    }
