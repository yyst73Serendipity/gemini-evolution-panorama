"""
提供 Gemini 演进时间线的数据读取、契约校验、去重指纹和原子写入能力。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CATEGORIES = {
    "技术基础",
    "模型",
    "产品",
    "开发者平台",
    "订阅计划",
    "生态集成",
    "研究",
    "安全治理",
    "生命周期",
}
LIFECYCLES = {"研究", "预览", "发布", "升级", "更名", "降价", "迁移", "弃用"}
IMPORTANCE_LEVELS = {"major", "standard"}
VERIFICATION_LEVELS = {"人工核验", "自动收录", "官方社交补充"}
DATE_PRECISIONS = {"day", "month", "year"}
ALLOWED_HOSTS = {
    "research.google",
    "ai.google",
    "ai.google.dev",
    "blog.google",
    "deepmind.google",
    "developers.googleblog.com",
    "cloud.google.com",
    "docs.cloud.google.com",
    "workspaceupdates.googleblog.com",
    "support.google.com",
    "one.google.com",
    "gemini.google.com",
    "android.com",
    "blog.google.com",
    "chromium.org",
    "x.com",
    "twitter.com",
}
EVENT_REQUIRED = {
    "id",
    "date",
    "date_precision",
    "category",
    "families",
    "lifecycle",
    "title",
    "summary",
    "difference",
    "optimization",
    "availability",
    "significance",
    "importance",
    "predecessors",
    "successors",
    "sources",
    "first_seen_at",
    "verified_at",
    "auto_generated",
    "verification",
}
SOURCE_REQUIRED = {"label", "url", "grade", "type"}
TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
}


def load_timeline(path: Path) -> dict:
    """读取 UTF-8 JSON 时间线文件并返回字典。"""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("时间线顶层必须是对象")
    return payload


def canonical_source_url(url: str) -> str:
    """移除来源 URL 中的片段、追踪参数和多余尾斜杠。"""
    parsed = urlsplit(url.strip())
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    meaningful_query = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    )
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(meaningful_query, doseq=True),
            "",
        )
    )


def event_fingerprint(event: dict) -> str:
    """根据稳定事实字段生成事件去重指纹。"""
    normalized_title = " ".join(str(event["title"]).split()).casefold()
    primary_source = canonical_source_url(event["sources"][0]["url"])
    raw = "\x1f".join(
        (
            str(event["date"]),
            normalized_title,
            str(event["category"]),
            str(event["lifecycle"]),
            primary_source,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_iso_datetime(value: str, field_name: str) -> datetime:
    """解析带时区的 ISO 时间，拒绝无法审计的本地裸时间。"""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} 不是合法 ISO 时间") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} 必须包含时区")
    return parsed


def _parse_event_date(value: str, precision: str) -> date:
    """按声明精度解析日期，并阻止用补零日期伪装未知精度。"""
    patterns = {
        "year": (r"^\d{4}$", "%Y"),
        "month": (r"^\d{4}-\d{2}$", "%Y-%m"),
        "day": (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    }
    if precision not in DATE_PRECISIONS:
        raise ValueError(f"日期精度枚举无效: {precision}")
    pattern, format_string = patterns[precision]
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError(f"日期精度与日期格式不一致: {value} / {precision}")
    try:
        parsed = datetime.strptime(value, format_string)
    except ValueError as error:
        raise ValueError(f"日期格式无效: {value}") from error
    return parsed.date().replace(
        month=parsed.month if precision != "year" else 1,
        day=parsed.day if precision == "day" else 1,
    )


def _validate_source(source: Any, event: dict) -> None:
    """校验单个来源为允许的 HTTPS 官方页面。"""
    if not isinstance(source, dict):
        raise ValueError(f"事件 {event['id']} 的来源必须是对象")
    missing = SOURCE_REQUIRED - source.keys()
    if missing:
        raise ValueError(f"事件 {event['id']} 的来源缺少必填字段: {sorted(missing)}")
    url = source["url"]
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"事件 {event['id']} 的来源必须使用 HTTPS")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"事件 {event['id']} 使用了非允许的官方来源: {host}")
    if source["grade"] not in {"A", "B", "C"}:
        raise ValueError(f"事件 {event['id']} 的来源等级枚举无效")

    # 社交平台只能作为明确标记的人工补充，避免进入自动事实主链路。
    if host in {"x.com", "twitter.com"}:
        if (
            source["grade"] != "C"
            or source["type"] != "official-social"
            or event["verification"] != "官方社交补充"
        ):
            raise ValueError(f"事件 {event['id']} 的官方社交来源标记无效")


def validate_timeline(data: dict, today: date | None = None) -> None:
    """校验顶层元数据、事件字段、官方来源、日期边界和引用关系。"""
    required_top_level = {"schema_version", "title", "cutoff", "content_updated_at", "events"}
    missing_top_level = required_top_level - data.keys()
    if missing_top_level:
        raise ValueError(f"时间线缺少必填字段: {sorted(missing_top_level)}")
    if data["schema_version"] != 1:
        raise ValueError("schema_version 枚举无效")
    if not isinstance(data["events"], list):
        raise ValueError("events 必须是数组")

    try:
        cutoff = date.fromisoformat(data["cutoff"])
    except (TypeError, ValueError) as error:
        raise ValueError("cutoff 必须是 YYYY-MM-DD") from error
    if cutoff > (today or date.today()):
        raise ValueError("截止日期晚于运行日期")
    content_updated_at = _parse_iso_datetime(data["content_updated_at"], "content_updated_at")
    if content_updated_at.date() > cutoff:
        raise ValueError("内容更新时间晚于截止日期")

    event_ids: set[str] = set()
    fingerprints: set[str] = set()
    parsed_dates: list[date] = []
    for index, event in enumerate(data["events"]):
        if not isinstance(event, dict):
            raise ValueError(f"第 {index + 1} 条事件必须是对象")
        missing = EVENT_REQUIRED - event.keys()
        if missing:
            raise ValueError(f"事件缺少必填字段: {sorted(missing)}")
        event_id = event["id"]
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("事件 ID 不能为空")
        if event_id in event_ids:
            raise ValueError(f"重复事件 ID: {event_id}")
        event_ids.add(event_id)

        if event["category"] not in CATEGORIES:
            raise ValueError(f"事件 {event_id} 的类别枚举无效")
        if event["lifecycle"] not in LIFECYCLES:
            raise ValueError(f"事件 {event_id} 的生命周期枚举无效")
        if event["importance"] not in IMPORTANCE_LEVELS:
            raise ValueError(f"事件 {event_id} 的重要级别枚举无效")
        if event["verification"] not in VERIFICATION_LEVELS:
            raise ValueError(f"事件 {event_id} 的核验级别枚举无效")
        if not isinstance(event["families"], list) or not event["families"]:
            raise ValueError(f"事件 {event_id} 至少需要一个产品线")
        if not isinstance(event["predecessors"], list) or not isinstance(event["successors"], list):
            raise ValueError(f"事件 {event_id} 的前序和后续必须是数组")
        if not isinstance(event["auto_generated"], bool):
            raise ValueError(f"事件 {event_id} 的 auto_generated 必须是布尔值")
        for field in (
            "title",
            "summary",
            "difference",
            "optimization",
            "availability",
            "significance",
        ):
            if not isinstance(event[field], str) or not event[field].strip():
                raise ValueError(f"事件 {event_id} 的 {field} 不能为空")

        parsed_event_date = _parse_event_date(event["date"], event["date_precision"])
        if parsed_event_date > cutoff:
            raise ValueError(f"事件 {event_id} 晚于截止日期")
        parsed_dates.append(parsed_event_date)
        _parse_iso_datetime(event["first_seen_at"], f"事件 {event_id} first_seen_at")
        _parse_iso_datetime(event["verified_at"], f"事件 {event_id} verified_at")

        if not isinstance(event["sources"], list) or not event["sources"]:
            raise ValueError(f"事件 {event_id} 至少一个来源")
        for source in event["sources"]:
            _validate_source(source, event)

        fingerprint = event_fingerprint(event)
        if fingerprint in fingerprints:
            raise ValueError(f"重复事件指纹: {event_id}")
        fingerprints.add(fingerprint)

    if parsed_dates != sorted(parsed_dates):
        raise ValueError("事件必须按日期升序排列")

    # 分两遍校验引用，使事件可以引用时间线上稍后出现的节点。
    for event in data["events"]:
        event_id = event["id"]
        references = event["predecessors"] + event["successors"]
        if event_id in references:
            raise ValueError(f"事件 {event_id} 不能自引用")
        missing_references = sorted(set(references) - event_ids)
        if missing_references:
            raise ValueError(f"事件 {event_id} 引用不存在: {missing_references}")


def write_json_atomic(path: Path, payload: dict) -> None:
    """在目标目录完整落盘后原子替换 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
