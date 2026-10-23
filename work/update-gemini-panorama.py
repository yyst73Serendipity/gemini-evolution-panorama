"""
从 Google 官方来源发现可信候选，安全合并时间线并以可回滚方式替换发布产物。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from source_parser import (
    classify_candidate,
    parse_page_metadata,
    parse_release_notes,
    stable_page_text,
)
from timeline_core import (
    ALLOWED_HOSTS,
    canonical_source_url,
    event_fingerprint,
    load_timeline,
    validate_timeline,
    write_json_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "work" / "source-config.json"
DEFAULT_TIMELINE = ROOT / "work" / "timeline-data.json"
DEFAULT_STATE = ROOT / "work" / "source-state.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "gemini-evolution-panorama.html"
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
DEFAULT_BUILD_SCRIPT = ROOT / "work" / "build-page.py"
PUBLISHABLE_PATHS = (
    "work/timeline-data.json",
    "work/source-state.json",
    "outputs/gemini-evolution-panorama.html",
    "CHANGELOG.md",
)


@dataclass(frozen=True)
class UpdatePaths:
    """定义更新器允许读取和替换的正式文件。"""

    root: Path
    timeline: Path
    state: Path
    output: Path
    changelog: Path
    build_script: Path


@dataclass(frozen=True)
class UpdateResult:
    """记录一次暂存更新的结果及其待替换文件。"""

    additions: int
    source_state_changed: bool
    content_changed: bool
    checked_at_changed: bool
    changed_paths: tuple[str, ...]
    checked_at: str
    staged_root: str | None = None
    replacements: tuple[tuple[str, str], ...] = ()


class _LinkParser(HTMLParser):
    """从官方列表页提取链接，不执行脚本。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def _iso_checked_at(checked_at: datetime) -> str:
    """规范化带时区的检查时间。"""
    if checked_at.tzinfo is None:
        raise ValueError("checked_at 必须包含时区")
    return checked_at.isoformat(timespec="seconds")


def _slugify(value: str) -> str:
    """把事件标题转换为稳定、短小的 ASCII ID 片段。"""
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    slug = "-".join(tokens[:8]).strip("-")
    return slug or "google-ai-update"


def _fact_key(event: dict) -> tuple[str, str, str, str]:
    """忽略来源 URL，按同一事实的稳定字段识别多来源事件。"""
    return (
        event["date"],
        " ".join(event["title"].split()).casefold(),
        event["category"],
        event["lifecycle"],
    )


def fetch_text(url: str, user_agent: str, timeout: int = 30) -> tuple[str, str]:
    """只读抓取 HTTPS 页面，返回解码正文和最终规范 URL。"""
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urlopen(request, timeout=timeout) as response:
        final_url = canonical_source_url(response.geturl())
        parsed = urlsplit(final_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError(f"重定向到了非允许官方来源: {final_url}")
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read()
    try:
        return payload.decode(charset), final_url
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace"), final_url


def build_candidate_event(metadata: dict, source: dict, checked_at: str) -> dict:
    """把明确日期、官方来源和高置信分类转换为保守的完整事件。"""
    date = str(metadata.get("date", "")).strip()
    title = " ".join(str(metadata.get("title", "")).split())
    url = canonical_source_url(str(metadata.get("url") or source.get("url") or ""))
    parsed = urlsplit(url)
    if not date or not title:
        raise ValueError("自动候选必须包含明确日期和标题")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("自动候选日期必须精确到日")
    if source.get("grade") not in {"A", "B"} or parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("自动候选必须来自 A/B 级 HTTPS 官方来源")

    description = " ".join(str(metadata.get("description") or metadata.get("summary") or "").split())
    stable_text = " ".join(str(metadata.get("stable_text") or "").split())
    classification = classify_candidate(" ".join((title, description, stable_text)))
    if classification["confidence"] != "high":
        raise ValueError("候选置信度不足，不能自动发布")

    summary = description or stable_text[:420] or f"Google 官方发布了 {title} 的更新信息。"
    event_id = f"{date}-{_slugify(title)}"
    return {
        "id": event_id,
        "date": date,
        "date_precision": "day",
        "category": classification["category"],
        "families": classification["families"] or ["Gemini"],
        "lifecycle": classification["lifecycle"],
        "title": title,
        "summary": summary[:600],
        "difference": "相较此前公开状态，Google 官方新增或更新了该模型、产品或平台信息；具体差异以官方原文为准。",
        "optimization": "优化重点以官方公布的能力、效率、可用范围或开发者工作流说明为准。",
        "availability": "可用范围、地区、套餐和接口状态以对应 Google 官方页面为准。",
        "significance": "该条目用于标记 Google AI 官方演进中的新节点，不推断官方未公布的性能或商业指标。",
        "importance": "standard",
        "predecessors": [],
        "successors": [],
        "sources": [
            {
                "label": source["label"],
                "url": url,
                "grade": source["grade"],
                "type": "official-release-notes" if source.get("type") == "release_notes" else "official-announcement",
            }
        ],
        "first_seen_at": checked_at,
        "verified_at": checked_at,
        "auto_generated": True,
        "verification": "自动收录",
    }


def merge_candidates(
    existing: list[dict],
    candidates: list[dict],
    cutoff: str,
    max_additions: int = 20,
) -> tuple[list[dict], list[dict]]:
    """去重、合并多来源并限制单次新增数量。"""
    merged = copy.deepcopy(existing)
    accepted: list[dict] = []
    ids = {event["id"] for event in merged}
    fingerprints = {event_fingerprint(event) for event in merged}
    urls = {
        canonical_source_url(source["url"])
        for event in merged
        for source in event["sources"]
    }
    facts = {_fact_key(event): event for event in merged}

    for raw_candidate in candidates:
        candidate = copy.deepcopy(raw_candidate)
        if candidate.get("date", "") > cutoff:
            continue
        if candidate.get("_confidence") == "low":
            continue
        candidate_urls = [canonical_source_url(source["url"]) for source in candidate.get("sources", [])]
        if not candidate_urls or any(url in urls for url in candidate_urls):
            continue
        fact = _fact_key(candidate)
        if fact in facts:
            target = facts[fact]
            known = {canonical_source_url(source["url"]) for source in target["sources"]}
            for source in candidate["sources"]:
                canonical = canonical_source_url(source["url"])
                if canonical not in known:
                    target["sources"].append(source)
                    known.add(canonical)
                    urls.add(canonical)
            continue
        fingerprint = event_fingerprint(candidate)
        if fingerprint in fingerprints:
            continue
        base_id = candidate["id"]
        suffix = 2
        while candidate["id"] in ids:
            candidate["id"] = f"{base_id}-{suffix}"
            suffix += 1
        accepted.append(candidate)
        if len(accepted) > max_additions:
            raise ValueError(f"单次自动新增超过 {max_additions} 条，已停止更新")
        merged.append(candidate)
        ids.add(candidate["id"])
        fingerprints.add(fingerprint)
        urls.update(candidate_urls)
        facts[fact] = candidate

    merged.sort(key=lambda event: (event["date"], event["id"]))
    return merged, accepted


def ensure_required_sources_available(config: dict, source_health: dict) -> None:
    """只有全部必需来源都失败时才终止，可选源失败不阻塞发布。"""
    required = [source["name"] for source in config["sources"] if source.get("required")]
    if required and not any(source_health.get(name, {}).get("ok") for name in required):
        raise RuntimeError("全部必需来源均不可用，已停止自动更新")


def _comparable_source_state(state: dict) -> dict:
    """移除纯检查时间，只比较会影响事实发现和来源健康的状态。"""
    comparable = copy.deepcopy(state)
    comparable.pop("last_checked_at", None)
    for health in comparable.get("source_health", {}).values():
        if isinstance(health, dict):
            health.pop("checked_at", None)
    return comparable


def _relative_path(paths: UpdatePaths, path: Path) -> str:
    """返回用于工作流受限提交的仓库相对路径。"""
    return path.relative_to(paths.root).as_posix()


def _write_text_atomic(path: Path, text: str) -> None:
    """在同目录完整写入文本后原子替换。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _updated_changelog(text: str, additions: int, source_state_changed: bool, checked_at: str) -> str:
    """追加一次自动同步记录，不改写既有日志。"""
    date = checked_at[:10]
    details = f"自动同步 Google 官方资料，新增 {additions} 条事件"
    if source_state_changed:
        details += "，并更新来源状态"
    line = f"- {details}。"
    heading = f"## {date}"
    if heading in text:
        return text.rstrip() + "\n" + line + "\n"
    return text.rstrip() + f"\n\n{heading}\n\n{line}\n"


def _validate_built_page(path: Path, expected_events: int) -> None:
    """验证暂存 HTML 完整、事件数一致且没有远程运行时资源。"""
    html = path.read_text(encoding="utf-8")
    if "<!doctype html>" not in html.lower():
        raise ValueError("构建产物缺少 doctype")
    if html.count('class="event-card"') != expected_events:
        raise ValueError("构建产物事件数量不一致")
    if re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://', html, re.I):
        raise ValueError("构建产物包含远程运行时资源")


def stage_update(
    paths: UpdatePaths,
    candidates: list[dict],
    checked_at: datetime,
    next_source_state: dict | None = None,
) -> UpdateResult:
    """在仓库内临时目录完成校验和构建，不直接修改正式文件。"""
    checked_iso = _iso_checked_at(checked_at)
    timeline = load_timeline(paths.timeline)
    state = json.loads(paths.state.read_text(encoding="utf-8"))
    checked_at_changed = state.get("last_checked_at") != checked_iso
    effective_cutoff = max(timeline["cutoff"], checked_at.date().isoformat())
    merged, accepted = merge_candidates(timeline["events"], candidates, effective_cutoff)
    timeline_changed = merged != timeline["events"]

    desired_state = copy.deepcopy(next_source_state if next_source_state is not None else state)
    state_comparable = _comparable_source_state(state)
    desired_comparable = _comparable_source_state(desired_state)
    source_state_changed = desired_comparable != state_comparable
    content_changed = timeline_changed or source_state_changed
    if not content_changed:
        return UpdateResult(0, False, False, checked_at_changed, (), checked_iso)

    if timeline_changed:
        timeline["events"] = merged
        timeline["cutoff"] = effective_cutoff
        timeline["content_updated_at"] = checked_iso
    desired_state["last_checked_at"] = checked_iso
    desired_state.setdefault("known_urls", [])
    desired_state.setdefault("page_hashes", {})
    desired_state.setdefault("source_health", {})
    validate_timeline(timeline, today=checked_at.date())

    staged_root = Path(tempfile.mkdtemp(prefix=".gemini-update-", dir=paths.root))
    staged_timeline = staged_root / "work" / "timeline-data.json"
    staged_state = staged_root / "work" / "source-state.json"
    staged_output = staged_root / "outputs" / "gemini-evolution-panorama.html"
    staged_changelog = staged_root / "CHANGELOG.md"
    staged_timeline.parent.mkdir(parents=True, exist_ok=True)
    staged_output.parent.mkdir(parents=True, exist_ok=True)

    try:
        write_json_atomic(staged_timeline, timeline)
        write_json_atomic(staged_state, desired_state)
        changelog = _updated_changelog(
            paths.changelog.read_text(encoding="utf-8"),
            len(accepted),
            source_state_changed,
            checked_iso,
        )
        _write_text_atomic(staged_changelog, changelog)
        subprocess.run(
            [
                sys.executable,
                str(paths.build_script),
                "--data",
                str(staged_timeline),
                "--state",
                str(staged_state),
                "--output",
                str(staged_output),
                "--checked-at",
                checked_iso,
            ],
            cwd=paths.root,
            check=True,
            capture_output=True,
            text=True,
        )
        _validate_built_page(staged_output, len(merged))

        pairs = (
            (staged_timeline, paths.timeline),
            (staged_state, paths.state),
            (staged_output, paths.output),
            (staged_changelog, paths.changelog),
        )
        replacements: list[tuple[str, str]] = []
        changed_paths: list[str] = []
        for staged, formal in pairs:
            if formal.exists() and staged.read_bytes() == formal.read_bytes():
                continue
            relative = _relative_path(paths, formal)
            if relative not in PUBLISHABLE_PATHS:
                raise ValueError(f"更新器试图修改未授权文件: {relative}")
            replacements.append((str(staged), str(formal)))
            changed_paths.append(relative)
        return UpdateResult(
            len(accepted),
            source_state_changed,
            True,
            checked_at_changed,
            tuple(changed_paths),
            checked_iso,
            str(staged_root),
            tuple(replacements),
        )
    except Exception:
        shutil.rmtree(staged_root, ignore_errors=True)
        raise


def apply_staged_update(result: UpdateResult) -> None:
    """原子替换暂存文件；任一步失败时恢复所有已替换文件。"""
    if not result.content_changed or not result.staged_root:
        return
    staged_root = Path(result.staged_root)
    backup_root = staged_root / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    replaced: list[tuple[Path, Path | None]] = []
    try:
        for index, (staged_text, formal_text) in enumerate(result.replacements):
            staged = Path(staged_text)
            formal = Path(formal_text)
            backup: Path | None = None
            if formal.exists():
                backup = backup_root / f"{index}-{formal.name}"
                shutil.copy2(formal, backup)
            formal.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, formal)
            replaced.append((formal, backup))
    except Exception:
        for formal, backup in reversed(replaced):
            if backup is not None and backup.exists():
                os.replace(backup, formal)
            elif formal.exists():
                formal.unlink()
        raise
    finally:
        shutil.rmtree(staged_root, ignore_errors=True)


def _extract_listing_links(text: str, base_url: str, source: dict) -> list[str]:
    """从列表页提取同一官方域名且匹配路径前缀的链接。"""
    parser = _LinkParser()
    parser.feed(text)
    allowed_prefixes = tuple(source.get("path_prefixes") or ["/"])
    links: list[str] = []
    for href in parser.links:
        absolute = canonical_source_url(urljoin(base_url, href))
        parsed = urlsplit(absolute)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            continue
        if not parsed.path.startswith(allowed_prefixes):
            continue
        if absolute not in links:
            links.append(absolute)
    return links


def _candidate_key(item: dict) -> str:
    """生成来源状态中用于识别已见候选的键。"""
    raw = "\x1f".join((canonical_source_url(item["url"]), item.get("date", ""), " ".join(item.get("title", "").split()).casefold()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def listing_link_key(link: str) -> str:
    """生成列表页文章 URL 的稳定已见键。"""
    return hashlib.sha256(canonical_source_url(link).encode("utf-8")).hexdigest()


def claim_listing_link(known: set[str], link: str, bootstrap: bool) -> bool:
    """立即记录列表页链接，并返回本次是否需要抓取文章。"""
    key = listing_link_key(link)
    is_new = key not in known
    known.add(key)
    return not bootstrap and is_new


def collect_official_updates(
    config: dict,
    state: dict,
    checked_at: datetime,
    bootstrap: bool = False,
    fetcher: Callable[[str, str, int], tuple[str, str]] = fetch_text,
) -> tuple[list[dict], dict]:
    """抓取来源、发现新条目，并返回候选和下一份来源状态。"""
    checked_iso = _iso_checked_at(checked_at)
    next_state = copy.deepcopy(state)
    known = set(next_state.get("known_urls", []))
    hashes = dict(next_state.get("page_hashes", {}))
    health: dict[str, dict] = {}
    candidates: list[dict] = []
    user_agent = config["user_agent"]
    timeout = int(config.get("timeout_seconds", 30))

    for source in config["sources"]:
        name = source["name"]
        try:
            text, final_url = fetcher(source["url"], user_agent, timeout)
            stable = stable_page_text(text)
            page_hash = hashlib.sha256(stable.encode("utf-8")).hexdigest()
            hashes[name] = page_hash
            discovered: list[dict] = []
            if source["type"] == "release_notes":
                discovered = parse_release_notes(text, final_url)
            elif source["type"] == "listing":
                links = _extract_listing_links(text, final_url, source)
                for link in links:
                    if not claim_listing_link(known, link, bootstrap):
                        continue
                    article_text, article_url = fetcher(link, user_agent, timeout)
                    metadata = parse_page_metadata(article_text, article_url)
                    metadata["stable_text"] = stable_page_text(article_text)
                    discovered.append(metadata)
            else:
                metadata = parse_page_metadata(text, final_url)
                metadata["stable_text"] = stable
                discovered = [metadata]

            for item in discovered:
                if not item.get("title") or not item.get("url"):
                    continue
                key = _candidate_key(item)
                is_new = key not in known
                known.add(key)
                if bootstrap or not is_new or not item.get("date"):
                    continue
                try:
                    candidates.append(build_candidate_event(item, source, checked_iso))
                except ValueError:
                    continue
            health[name] = {"ok": True, "final_url": final_url, "error": "", "checked_at": checked_iso}
        except Exception as error:
            health[name] = {"ok": False, "final_url": "", "error": f"{type(error).__name__}: {error}", "checked_at": checked_iso}

    ensure_required_sources_available(config, health)
    next_state["known_urls"] = sorted(known)
    next_state["page_hashes"] = hashes
    next_state["source_health"] = health
    return candidates, next_state


def _result_payload(result: UpdateResult, bootstrap: bool) -> dict:
    """生成供 GitHub Actions 判定的稳定结果 JSON。"""
    payload = asdict(result)
    payload.pop("staged_root", None)
    payload.pop("replacements", None)
    payload["bootstrap"] = bootstrap
    return payload


def parse_args() -> argparse.Namespace:
    """解析自动更新命令行参数。"""
    parser = argparse.ArgumentParser(description="自动检查并更新 Gemini 演进全景")
    parser.add_argument("--bootstrap", action="store_true", help="只建立来源基线，不新增事件")
    parser.add_argument("--result-path", type=Path, default=Path("/tmp/gemini-update-result.json"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    """执行实网检查、暂存验证、正式替换并输出机器可读结果。"""
    args = parse_args()
    checked_at = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    state = json.loads(DEFAULT_STATE.read_text(encoding="utf-8"))
    candidates, next_state = collect_official_updates(config, state, checked_at, bootstrap=args.bootstrap)
    if args.bootstrap:
        candidates = []
    paths = UpdatePaths(ROOT, DEFAULT_TIMELINE, DEFAULT_STATE, DEFAULT_OUTPUT, DEFAULT_CHANGELOG, DEFAULT_BUILD_SCRIPT)
    result = stage_update(paths, candidates, checked_at, next_source_state=next_state)
    apply_staged_update(result)
    args.result_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(args.result_path, json.dumps(_result_payload(result, args.bootstrap), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(_result_payload(result, args.bootstrap), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
