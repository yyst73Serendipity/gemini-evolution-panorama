"""
把 Gemini 结构化时间线构建为可离线阅读的单文件 HTML 全景网页。
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Iterable

from timeline_core import load_timeline, validate_timeline

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "work" / "timeline-data.json"
DEFAULT_STATE = ROOT / "work" / "source-state.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "gemini-evolution-panorama.html"


def esc(value: object) -> str:
    """把动态值转义为可安全写入 HTML 属性或正文的文本。"""
    return escape(str(value), quote=True)


def format_event_date(event: dict) -> str:
    """根据事件声明的日期精度生成中文日期。"""
    parts = event["date"].split("-")
    precision = event["date_precision"]
    if precision == "year":
        return f"{parts[0]} 年"
    if precision == "month":
        return f"{parts[0]} 年 {int(parts[1])} 月"
    return f"{parts[0]} 年 {int(parts[1])} 月 {int(parts[2])} 日"


def _relation_links(ids: Iterable[str], label: str) -> str:
    """把前后继 ID 渲染为页面内关系链接。"""
    links = "".join(
        f'<a class="relation-link" href="#event-{esc(event_id)}">{esc(event_id)}</a>'
        for event_id in ids
    )
    if not links:
        return ""
    return f'<div class="relations"><strong>{esc(label)}</strong>{links}</div>'


def build_event_card(event: dict) -> str:
    """把一条已校验事件渲染成可搜索、可筛选的静态档案卡。"""
    source_links = "".join(
        (
            f'<a href="{esc(source["url"])}" target="_blank" rel="noreferrer">'
            f'<span>{esc(source["label"])}</span>'
            f'<small>{esc(source["grade"])} · {esc(source["type"])}</small></a>'
        )
        for source in event["sources"]
    )
    family_badges = "".join(
        f'<span class="badge family-badge">{esc(family)}</span>' for family in event["families"]
    )
    search_text = " ".join(
        [
            event["title"],
            event["summary"],
            event["difference"],
            event["optimization"],
            event["availability"],
            event["significance"],
            event["category"],
            event["lifecycle"],
            *event["families"],
        ]
    ).casefold()
    verification = "自动收录，待人工复核" if event["auto_generated"] else event["verification"]
    predecessor_links = _relation_links(event["predecessors"], "前序")
    successor_links = _relation_links(event["successors"], "后续")
    major_mark = '<span class="major-mark" aria-label="重大节点">重点</span>' if event["importance"] == "major" else ""

    return (
        f'<article class="event-card" id="event-{esc(event["id"])}" '
        f'data-year="{esc(event["date"][:4])}" '
        f'data-category="{esc(event["category"])}" '
        f'data-family="{esc("|".join(event["families"]))}" '
        f'data-lifecycle="{esc(event["lifecycle"])}" '
        f'data-importance="{esc(event["importance"])}" '
        f'data-search="{esc(search_text)}">'
        '<div class="event-rail" aria-hidden="true"><span></span></div>'
        '<div class="event-content">'
        '<header class="event-header">'
        '<div class="event-meta">'
        f'<time datetime="{esc(event["date"])}">{esc(format_event_date(event))}</time>'
        f'<span class="badge category-badge">{esc(event["category"])}</span>'
        f'<span class="badge lifecycle-badge">{esc(event["lifecycle"])}</span>{major_mark}'
        '</div>'
        f'<h3><a href="#event-{esc(event["id"])}">{esc(event["title"])}</a></h3>'
        f'<p class="event-summary">{esc(event["summary"])}</p>'
        f'<div class="family-list">{family_badges}</div>'
        '</header>'
        '<details class="event-details">'
        '<summary>查看差异、优化与影响</summary>'
        '<div class="detail-grid">'
        f'<section><h4>与前序相比</h4><p>{esc(event["difference"])}</p></section>'
        f'<section><h4>优化重点</h4><p>{esc(event["optimization"])}</p></section>'
        f'<section><h4>可用范围</h4><p>{esc(event["availability"])}</p></section>'
        f'<section><h4>为什么重要</h4><p>{esc(event["significance"])}</p></section>'
        '</div>'
        f'<div class="relation-row">{predecessor_links}{successor_links}</div>'
        '</details>'
        '<footer class="event-footer">'
        f'<div class="sources"><strong>官方来源</strong>{source_links}</div>'
        f'<span class="verification">{esc(verification)} · 核验于 {esc(event["verified_at"])}</span>'
        '</footer>'
        '</div></article>'
    )


def _option_list(values: Iterable[str], all_label: str) -> str:
    """生成筛选下拉选项。"""
    options = [f'<option value="">{esc(all_label)}</option>']
    options.extend(f'<option value="{esc(value)}">{esc(value)}</option>' for value in values)
    return "".join(options)


def _summary_items(events: Iterable[dict], limit: int = 8) -> str:
    """生成章节摘要列表，避免重复渲染完整事件卡。"""
    selected = list(events)[-limit:]
    if not selected:
        return '<p class="empty-copy">当前数据集中暂无对应节点。</p>'
    return "".join(
        (
            '<li>'
            f'<a href="#event-{esc(event["id"])}">{esc(event["title"])}</a>'
            f'<span>{esc(format_event_date(event))} · {esc(event["lifecycle"])}</span>'
            '</li>'
        )
        for event in selected
    )


def _stat_cards(data: dict) -> str:
    """生成首屏统计卡。"""
    events = data["events"]
    years = sorted({event["date"][:4] for event in events})
    major_count = sum(event["importance"] == "major" for event in events)
    source_count = len({source["url"] for event in events for source in event["sources"]})
    stats = (
        ("时间跨度", f"{years[0]}—{years[-1]}", "从技术前史到当前核验日"),
        ("事件档案", str(len(events)), f"其中 {major_count} 个重大节点"),
        ("官方来源", str(source_count), "仅采用 Google 第一方资料"),
        ("内容类别", str(len({event['category'] for event in events})), "模型、产品、平台与治理"),
    )
    return "".join(
        (
            '<article class="stat-card">'
            f'<span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small>'
            '</article>'
        )
        for label, value, note in stats
    )


def build_page(data: dict) -> str:
    """把已校验的时间线数据构建为完整单文件 HTML。"""
    events = data["events"]
    years = sorted({event["date"][:4] for event in events})
    categories = sorted({event["category"] for event in events})
    families = sorted({family for event in events for family in event["families"]})
    lifecycles = sorted({event["lifecycle"] for event in events})
    counts = Counter(event["category"] for event in events)
    checked_at = data.get("_last_checked_at", "未记录")

    by_year: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_year[event["date"][:4]].append(event)

    year_navigation = "".join(
        f'<a href="#year-{esc(year)}" data-year-jump="{esc(year)}">{esc(year)}</a>' for year in years
    )
    timeline_groups = "".join(
        (
            f'<section class="year-group" id="year-{esc(year)}" data-year-group="{esc(year)}">'
            f'<header class="year-heading"><span>{esc(year)}</span>'
            f'<p>{len(by_year[year])} 个节点</p></header>'
            f'<div class="year-events">{"".join(build_event_card(event) for event in by_year[year])}</div>'
            '</section>'
        )
        for year in years
    )
    category_chips = "".join(
        f'<button type="button" class="category-chip" data-category-shortcut="{esc(category)}">'
        f'{esc(category)}<span>{counts[category]}</span></button>'
        for category in categories
    )

    model_events = [event for event in events if event["category"] == "模型"]
    consumer_events = [
        event
        for event in events
        if event["category"] == "产品"
        or any(name in "|".join(event["families"]) for name in ("Bard", "Gemini App", "NotebookLM"))
    ]
    developer_events = [
        event for event in events if event["category"] in {"开发者平台", "生态集成", "生命周期"}
    ]
    subscription_events = [event for event in events if event["category"] == "订阅计划"]
    research_events = [
        event for event in events if event["category"] in {"技术基础", "研究", "安全治理"}
    ]

    style = """
:root {
  color-scheme: light;
  --bg: #f4f6fb;
  --surface: rgba(255, 255, 255, .88);
  --surface-solid: #fff;
  --surface-2: #edf1fa;
  --text: #172033;
  --muted: #64708a;
  --line: #d9dfec;
  --blue: #1769e0;
  --purple: #7655dc;
  --cyan: #11a9b7;
  --accent: linear-gradient(120deg, #1769e0, #7655dc 55%, #11a9b7);
  --shadow: 0 18px 50px rgba(37, 55, 91, .10);
  --radius: 22px;
  --max: 1180px;
}
html[data-theme="dark"] {
  color-scheme: dark;
  --bg: #080d18;
  --surface: rgba(18, 25, 43, .88);
  --surface-solid: #12192b;
  --surface-2: #192238;
  --text: #eef3ff;
  --muted: #a6b2cb;
  --line: #2b3753;
  --blue: #72a7ff;
  --purple: #ad8cff;
  --cyan: #54d7df;
  --shadow: 0 22px 60px rgba(0, 0, 0, .32);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 100px; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 8% 0%, color-mix(in srgb, var(--blue) 15%, transparent), transparent 28rem),
    radial-gradient(circle at 95% 10%, color-mix(in srgb, var(--purple) 15%, transparent), transparent 30rem),
    var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  line-height: 1.7;
}
a { color: inherit; }
button, input, select { font: inherit; }
button, select { cursor: pointer; }
.skip-link { position: fixed; left: 12px; top: -70px; z-index: 99; padding: 10px 16px; background: var(--text); color: var(--bg); border-radius: 10px; }
.skip-link:focus { top: 12px; }
.reading-progress { position: fixed; inset: 0 0 auto; z-index: 90; height: 3px; background: transparent; }
.reading-progress span { display: block; width: 0; height: 100%; background: var(--accent); }
.site-header { position: sticky; top: 0; z-index: 50; border-bottom: 1px solid color-mix(in srgb, var(--line) 80%, transparent); background: color-mix(in srgb, var(--bg) 84%, transparent); backdrop-filter: blur(18px); }
.header-inner { max-width: var(--max); margin: auto; min-height: 70px; padding: 12px 24px; display: flex; align-items: center; gap: 24px; }
.brand { display: inline-flex; align-items: center; gap: 12px; text-decoration: none; font-weight: 760; letter-spacing: -.02em; white-space: nowrap; }
.brand-mark { width: 28px; height: 28px; border-radius: 9px; background: var(--accent); transform: rotate(10deg); box-shadow: 0 8px 24px color-mix(in srgb, var(--purple) 35%, transparent); }
.section-nav { display: flex; gap: 18px; overflow-x: auto; margin-left: auto; scrollbar-width: none; }
.section-nav a { color: var(--muted); text-decoration: none; white-space: nowrap; font-size: 14px; }
.section-nav a:hover { color: var(--text); }
.theme-toggle { border: 1px solid var(--line); background: var(--surface); color: var(--text); border-radius: 999px; padding: 7px 12px; white-space: nowrap; }
.hero { max-width: var(--max); margin: auto; padding: 86px 24px 42px; }
.eyebrow { display: inline-flex; gap: 9px; align-items: center; color: var(--blue); font-size: 13px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
.eyebrow::before { content: ""; width: 34px; height: 2px; background: var(--accent); }
.hero h1 { max-width: 980px; margin: 18px 0; font-size: clamp(42px, 8vw, 92px); line-height: .98; letter-spacing: -.065em; }
.gradient-text { background: var(--accent); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero-lead { max-width: 760px; margin: 0; color: var(--muted); font-size: clamp(17px, 2vw, 21px); }
.audit-strip { margin-top: 28px; display: flex; flex-wrap: wrap; gap: 10px 22px; color: var(--muted); font-size: 13px; }
.audit-strip strong { color: var(--text); }
.stats-grid { margin-top: 38px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.stat-card { padding: 20px; border: 1px solid var(--line); border-radius: 18px; background: var(--surface); box-shadow: var(--shadow); }
.stat-card span, .stat-card small { display: block; color: var(--muted); }
.stat-card strong { display: block; margin: 7px 0 5px; font-size: 30px; letter-spacing: -.04em; }
.category-shortcuts { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.category-chip { border: 1px solid var(--line); border-radius: 999px; padding: 8px 13px; background: var(--surface); color: var(--text); }
.category-chip span { margin-left: 7px; color: var(--muted); }
main { max-width: var(--max); margin: auto; padding: 18px 24px 90px; }
.primary-section { margin-top: 70px; }
.section-heading { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, 520px); gap: 28px; align-items: end; margin-bottom: 24px; }
.section-kicker { color: var(--purple); font-size: 12px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.section-heading h2 { margin: 6px 0 0; font-size: clamp(30px, 4vw, 52px); line-height: 1.08; letter-spacing: -.045em; }
.section-heading p { margin: 0; color: var(--muted); }
.controls { position: sticky; top: 83px; z-index: 35; padding: 16px; border: 1px solid var(--line); border-radius: 20px; background: color-mix(in srgb, var(--surface-solid) 92%, transparent); backdrop-filter: blur(18px); box-shadow: var(--shadow); }
.control-grid { display: grid; grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(130px, 1fr)); gap: 10px; }
.control { display: grid; gap: 5px; color: var(--muted); font-size: 12px; }
.control input, .control select { min-width: 0; width: 100%; border: 1px solid var(--line); border-radius: 12px; background: var(--surface-2); color: var(--text); padding: 10px 12px; }
.control-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; }
.checkbox-control { display: inline-flex; gap: 8px; align-items: center; color: var(--text); font-size: 14px; }
.reset-button { border: 0; background: transparent; color: var(--blue); padding: 6px; }
.year-nav { display: flex; gap: 8px; overflow-x: auto; padding: 15px 2px 2px; scrollbar-width: thin; }
.year-nav a { flex: 0 0 auto; text-decoration: none; color: var(--muted); border: 1px solid var(--line); background: var(--surface-2); border-radius: 999px; padding: 5px 10px; font-size: 13px; }
.timeline { margin-top: 34px; }
.year-group { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 26px; margin: 0 0 54px; }
.year-heading { position: sticky; top: 190px; align-self: start; }
.year-heading span { font-size: 32px; font-weight: 820; letter-spacing: -.05em; }
.year-heading p { margin: 2px 0; color: var(--muted); font-size: 13px; }
.year-events { display: grid; gap: 18px; }
.event-card { position: relative; display: grid; grid-template-columns: 24px minmax(0, 1fr); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); overflow: clip; }
.event-card[hidden] { display: none; }
.event-rail { display: flex; justify-content: center; background: color-mix(in srgb, var(--surface-2) 78%, transparent); }
.event-rail::before { content: ""; width: 2px; background: var(--accent); opacity: .55; }
.event-rail span { position: absolute; top: 28px; left: 7px; width: 10px; height: 10px; border: 2px solid var(--surface-solid); border-radius: 50%; background: var(--purple); box-shadow: 0 0 0 4px color-mix(in srgb, var(--purple) 20%, transparent); }
.event-content { min-width: 0; padding: 24px 26px; }
.event-meta, .family-list { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
.event-meta time { margin-right: 4px; color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.badge, .major-mark { display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); background: var(--surface-2); font-size: 11px; }
.major-mark { border-color: color-mix(in srgb, var(--purple) 42%, var(--line)); color: var(--purple); }
.event-header h3 { margin: 14px 0 8px; font-size: clamp(22px, 3vw, 31px); line-height: 1.2; letter-spacing: -.035em; }
.event-header h3 a { text-decoration: none; }
.event-header h3 a:hover { color: var(--blue); }
.event-summary { margin: 0; color: var(--muted); font-size: 16px; }
.family-list { margin-top: 14px; }
.family-badge { color: var(--text); background: transparent; }
.event-details { margin-top: 18px; border-top: 1px solid var(--line); }
.event-details summary { padding: 15px 0 4px; color: var(--blue); font-weight: 700; cursor: pointer; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 18px; padding: 12px 0; }
.detail-grid section { padding: 14px; border-radius: 14px; background: var(--surface-2); }
.detail-grid h4 { margin: 0 0 5px; font-size: 13px; }
.detail-grid p { margin: 0; color: var(--muted); font-size: 14px; }
.relation-row { display: flex; flex-wrap: wrap; gap: 10px 18px; }
.relations { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; color: var(--muted); font-size: 12px; }
.relation-link { color: var(--blue); text-decoration: none; }
.event-footer { margin-top: 16px; display: grid; gap: 13px; }
.sources { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; }
.sources > strong { padding: 8px 2px; font-size: 12px; }
.sources a { display: grid; text-decoration: none; border: 1px solid var(--line); border-radius: 11px; padding: 7px 10px; background: var(--surface-2); font-size: 12px; }
.sources a span { color: var(--blue); }
.sources a small, .verification { color: var(--muted); font-size: 10px; }
.verification { text-align: right; }
.no-results { margin: 28px 0; padding: 28px; border: 1px dashed var(--line); border-radius: 18px; color: var(--muted); text-align: center; }
.no-results[hidden] { display: none; }
.archive-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.archive-panel { padding: 24px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.archive-panel h3 { margin: 0 0 8px; font-size: 22px; }
.archive-panel > p { margin: 0 0 15px; color: var(--muted); }
.summary-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
.summary-list li { display: grid; gap: 2px; padding: 10px 0; border-top: 1px solid var(--line); }
.summary-list a { font-weight: 680; text-decoration: none; }
.summary-list span { color: var(--muted); font-size: 12px; }
.method-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.method-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: var(--surface); }
.method-card h3 { margin-top: 0; }
.method-card p { color: var(--muted); }
.method-card a { color: var(--blue); }
.site-footer { max-width: var(--max); margin: auto; padding: 28px 24px 60px; color: var(--muted); border-top: 1px solid var(--line); }
@media (prefers-color-scheme: dark) {
  html:not([data-theme]) { color-scheme: dark; }
}
:focus-visible { outline: 3px solid var(--cyan); outline-offset: 3px; }
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
@media (max-width: 920px) {
  .stats-grid { grid-template-columns: 1fr 1fr; }
  .control-grid { grid-template-columns: 1fr 1fr; }
  .control:first-child { grid-column: 1 / -1; }
  .section-heading { grid-template-columns: 1fr; }
  .archive-grid, .method-grid { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .header-inner { padding-inline: 16px; }
  .section-nav { display: none; }
  .theme-toggle { margin-left: auto; }
  .hero { padding: 58px 16px 28px; }
  .hero h1 { font-size: clamp(42px, 15vw, 66px); }
  main { padding-inline: 16px; }
  .stats-grid, .control-grid, .detail-grid { grid-template-columns: 1fr; }
  .controls { position: relative; top: auto; }
  .year-group { grid-template-columns: 1fr; gap: 10px; }
  .year-heading { position: static; display: flex; align-items: baseline; gap: 10px; }
  .event-content { padding: 20px 18px; }
  .verification { text-align: left; }
}
@media print {
  :root { --bg: #fff; --surface: #fff; --surface-solid: #fff; --surface-2: #fff; --text: #000; --muted: #333; --line: #bbb; }
  body { background: #fff; font-size: 10pt; }
  .site-header, .controls, .theme-toggle, .reading-progress, .skip-link { display: none !important; }
  .hero { padding: 20px 0; }
  .hero h1 { font-size: 34pt; }
  main, .hero, .site-footer { max-width: none; padding-left: 0; padding-right: 0; }
  .stats-grid { grid-template-columns: repeat(4, 1fr); }
  .event-card { box-shadow: none; break-inside: avoid; }
  .event-details > div { display: block !important; }
  .primary-section { break-before: page; }
  a { text-decoration: none; }
}
"""

    script = """
(() => {
  const root = document.documentElement;
  const cards = [...document.querySelectorAll('.event-card')];
  const groups = [...document.querySelectorAll('[data-year-group]')];
  const controls = {
    search: document.querySelector('#search-input'),
    year: document.querySelector('#year-filter'),
    category: document.querySelector('#category-filter'),
    family: document.querySelector('#family-filter'),
    lifecycle: document.querySelector('#lifecycle-filter'),
    major: document.querySelector('#major-only')
  };
  const noResults = document.querySelector('#no-results');
  const resultCount = document.querySelector('#result-count');
  const themeToggle = document.querySelector('#theme-toggle');
  const progress = document.querySelector('#reading-progress');

  function setTheme(theme) {
    const preference = ['light', 'dark', 'system'].includes(theme) ? theme : 'system';
    const resolved = preference === 'system'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : preference;
    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    const labels = { system: '主题：跟随系统', light: '主题：浅色', dark: '主题：深色' };
    themeToggle.textContent = labels[preference];
    themeToggle.setAttribute('aria-label', `${labels[preference]}，点击切换`);
  }

  function syncUrlState() {
    const params = new URLSearchParams();
    if (controls.search.value.trim()) params.set('q', controls.search.value.trim());
    if (controls.year.value) params.set('year', controls.year.value);
    if (controls.category.value) params.set('category', controls.category.value);
    if (controls.family.value) params.set('family', controls.family.value);
    if (controls.lifecycle.value) params.set('lifecycle', controls.lifecycle.value);
    if (controls.major.checked) params.set('major', '1');
    const query = params.toString();
    history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}${location.hash}`);
  }

  function restoreUrlState() {
    const initial = new URLSearchParams(location.search);
    controls.search.value = initial.get('q') || '';
    controls.year.value = initial.get('year') || '';
    controls.category.value = initial.get('category') || '';
    controls.family.value = initial.get('family') || '';
    controls.lifecycle.value = initial.get('lifecycle') || '';
    controls.major.checked = initial.get('major') === '1';
  }

  function applyFilters() {
    const query = controls.search.value.trim().toLocaleLowerCase('zh-CN');
    let visible = 0;
    cards.forEach((card) => {
      const matches = (!query || card.dataset.search.includes(query))
        && (!controls.year.value || card.dataset.year === controls.year.value)
        && (!controls.category.value || card.dataset.category === controls.category.value)
        && (!controls.family.value || card.dataset.family.split('|').includes(controls.family.value))
        && (!controls.lifecycle.value || card.dataset.lifecycle === controls.lifecycle.value)
        && (!controls.major.checked || card.dataset.importance === 'major');
      card.hidden = !matches;
      if (matches) visible += 1;
    });
    groups.forEach((group) => {
      group.hidden = !group.querySelector('.event-card:not([hidden])');
    });
    noResults.hidden = visible !== 0;
    resultCount.textContent = `显示 ${visible} / ${cards.length} 条事件`;
    syncUrlState();
  }

  function updateReadingProgress() {
    const range = document.documentElement.scrollHeight - innerHeight;
    progress.style.width = `${range > 0 ? Math.min(100, scrollY / range * 100) : 0}%`;
  }

  const savedTheme = localStorage.getItem('gemini-panorama-theme') || 'system';
  setTheme(savedTheme);
  themeToggle.addEventListener('click', () => {
    const order = ['system', 'light', 'dark'];
    const current = root.dataset.themePreference || 'system';
    const next = order[(order.indexOf(current) + 1) % order.length];
    localStorage.setItem('gemini-panorama-theme', next);
    setTheme(next);
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (root.dataset.themePreference === 'system') setTheme('system');
  });

  Object.values(controls).forEach((control) => control.addEventListener('input', applyFilters));
  document.querySelector('#reset-filters').addEventListener('click', () => {
    controls.search.value = '';
    controls.year.value = '';
    controls.category.value = '';
    controls.family.value = '';
    controls.lifecycle.value = '';
    controls.major.checked = false;
    applyFilters();
  });
  document.querySelectorAll('[data-category-shortcut]').forEach((button) => {
    button.addEventListener('click', () => {
      controls.category.value = button.dataset.categoryShortcut;
      document.querySelector('#timeline').scrollIntoView();
      applyFilters();
    });
  });

  restoreUrlState();
  applyFilters();
  addEventListener('scroll', updateReadingProgress, { passive: true });
  updateReadingProgress();
})();
"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Gemini 与 Google AI 从 Transformer 到当前模型、产品、平台和订阅计划的官方来源演进档案。">
  <title>{esc(data['title'])}</title>
  <style>{style}</style>
</head>
<body>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <div class="reading-progress" aria-hidden="true"><span id="reading-progress"></span></div>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#top"><span class="brand-mark" aria-hidden="true"></span><span>Gemini 演进全景</span></a>
      <nav class="section-nav" aria-label="主要章节">
        <a href="#timeline">时间线</a><a href="#lineage">模型谱系</a><a href="#consumer-products">消费产品</a>
        <a href="#developer-platforms">开发平台</a><a href="#subscriptions">订阅</a><a href="#methodology">方法</a>
      </nav>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="切换页面主题">切换深色</button>
    </div>
  </header>

  <div id="top"></div>
  <section class="hero" aria-labelledby="page-title">
    <span class="eyebrow">Google AI archive · official sources only</span>
    <h1 id="page-title"><span class="gradient-text">2017—{esc(data['cutoff'][:4])}</span><br>产品与模型演进全景</h1>
    <p class="hero-lead">从 Transformer、BERT、LaMDA 与 PaLM，沿着 Gemini、Gemma、Bard、NotebookLM、开发者平台和订阅计划，查看每次关键更新、前后差异、优化重点与官方证据。</p>
    <div class="audit-strip">
      <span>资料核验截止 <strong>{esc(data['cutoff'])}</strong></span>
      <span>内容更新时间 <strong>{esc(data['content_updated_at'])}</strong></span>
      <span>最近自动检查 <strong>{esc(checked_at)}</strong></span>
    </div>
    <div class="stats-grid">{_stat_cards(data)}</div>
    <div class="category-shortcuts" aria-label="按类别快速筛选">{category_chips}</div>
  </section>

  <main id="main-content">
    <section class="primary-section" id="timeline" aria-labelledby="timeline-title">
      <div class="section-heading">
        <div><span class="section-kicker">01 · Timeline</span><h2 id="timeline-title">演进总时间线</h2></div>
        <p>每张档案卡都区分公告日期、生命周期、与前序相比、优化重点、可用范围和意义。筛选状态会保存在 URL 中。</p>
      </div>
      <div class="controls" role="search" aria-label="时间线筛选器">
        <div class="control-grid">
          <label class="control" for="search-input">关键词<input id="search-input" type="search" placeholder="搜索模型、产品、能力或来源"></label>
          <label class="control" for="year-filter">年份<select id="year-filter">{_option_list(years, '全部年份')}</select></label>
          <label class="control" for="category-filter">类别<select id="category-filter">{_option_list(categories, '全部类别')}</select></label>
          <label class="control" for="family-filter">产品线<select id="family-filter">{_option_list(families, '全部产品线')}</select></label>
          <label class="control" for="lifecycle-filter">生命周期<select id="lifecycle-filter">{_option_list(lifecycles, '全部状态')}</select></label>
        </div>
        <div class="control-actions">
          <label class="checkbox-control" for="major-only"><input id="major-only" type="checkbox">仅看重大节点</label>
          <span id="result-count" aria-live="polite">显示 {len(events)} / {len(events)} 条事件</span>
          <button class="reset-button" id="reset-filters" type="button">重置筛选</button>
        </div>
        <nav class="year-nav" aria-label="年份导航">{year_navigation}</nav>
      </div>
      <noscript><p class="no-results">JavaScript 已禁用：全部事件仍已预渲染，可以使用浏览器查找和年份锚点阅读。</p></noscript>
      <div class="timeline">{timeline_groups}</div>
      <p class="no-results" id="no-results" hidden>没有符合当前筛选条件的事件，请调整关键词或筛选项。</p>
    </section>

    <section class="primary-section" id="lineage" aria-labelledby="lineage-title">
      <div class="section-heading"><div><span class="section-kicker">02 · Lineage</span><h2 id="lineage-title">模型谱系</h2></div><p>用重大模型节点串起从 Transformer 到 Gemini 4、从 Gemma 开放模型到本地智能体的两条主线。</p></div>
      <div class="archive-grid">
        <article class="archive-panel"><h3>Gemini 核心代际</h3><p>研究基础、原生多模态、长上下文、思考模型、代理工作流与前沿安全。</p><ul class="summary-list">{_summary_items([event for event in model_events if 'Gemini' in '|'.join(event['families'])], 12)}</ul></article>
        <article class="archive-panel"><h3>Gemma 开放模型</h3><p>从轻量开放权重模型，扩展到本地多模态、设备端推理与智能体工作流。</p><ul class="summary-list">{_summary_items([event for event in model_events if 'Gemma' in '|'.join(event['families'])], 8)}</ul></article>
      </div>
    </section>

    <section class="primary-section" id="consumer-products" aria-labelledby="consumer-title">
      <div class="section-heading"><div><span class="section-kicker">03 · Products</span><h2 id="consumer-title">消费级产品</h2></div><p>Bard 如何变成 Gemini App，以及 Live、Canvas、Deep Research、NotebookLM 等能力如何形成产品矩阵。</p></div>
      <div class="archive-panel"><ul class="summary-list">{_summary_items(consumer_events, 12)}</ul></div>
    </section>

    <section class="primary-section" id="developer-platforms" aria-labelledby="developer-title">
      <div class="section-heading"><div><span class="section-kicker">04 · Platforms</span><h2 id="developer-title">开发者与企业平台</h2></div><p>追踪 Gemini API、Google AI Studio、Vertex AI、Code Assist、Jules、Gemini CLI 和模型生命周期。</p></div>
      <div class="archive-panel"><ul class="summary-list">{_summary_items(developer_events, 14)}</ul></div>
    </section>

    <section class="primary-section" id="subscriptions" aria-labelledby="subscriptions-title">
      <div class="section-heading"><div><span class="section-kicker">05 · Plans</span><h2 id="subscriptions-title">订阅计划</h2></div><p>区分 Google One AI Premium、Google AI Pro 与 Google AI Ultra 的命名和层级演进；实时价格与地区以官方计划页为准。</p></div>
      <div class="archive-panel"><ul class="summary-list">{_summary_items(subscription_events, 10)}</ul></div>
    </section>

    <section class="primary-section" id="research-future" aria-labelledby="research-title">
      <div class="section-heading"><div><span class="section-kicker">06 · Research & safety</span><h2 id="research-title">研究、安全与未来产品</h2></div><p>研究演示只有在影响后续 Gemini 主线时才收录；“未来”指当时的实验路径，不包含截止日后的预测。</p></div>
      <div class="archive-panel"><ul class="summary-list">{_summary_items(research_events, 12)}</ul></div>
    </section>

    <section class="primary-section" id="methodology" aria-labelledby="methodology-title">
      <div class="section-heading"><div><span class="section-kicker">07 · Method</span><h2 id="methodology-title">来源与方法</h2></div><p>准确性高于更新频率。动态页面、搜索摘要和 sitemap 修改时间不单独作为历史发布日期。</p></div>
      <div class="method-grid">
        <article class="method-card"><h3>官方来源优先</h3><p>只采用 Google Research、Google DeepMind、Google Blog、Google for Developers、Google Cloud、Google One 等第一方页面。</p></article>
        <article class="method-card"><h3>状态严格区分</h3><p>研究、预览、稳定发布、升级、迁移和弃用分别记录；同一能力的重要生命周期节点可以拆成多张卡。</p></article>
        <article class="method-card"><h3>保守表达</h3><p>官方未公布的参数、基准、价格、地区或日期不推断。X/Twitter 只用于人工发现，不进入自动抓取主链路。</p></article>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <p>{esc(data['title'])} · 共 {len(events)} 条事件 · 核验截止 {esc(data['cutoff'])}</p>
    <p>本页面可离线保存和打印；所有外链仅在主动打开官方来源时访问网络。</p>
  </footer>
  <script>{script}</script>
</body>
</html>
"""


def write_page(output_path: Path, html_text: str) -> None:
    """完整写入临时文件并原子替换正式 HTML。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(html_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _load_state(path: Path) -> dict:
    """读取来源检查状态，缺少顶层对象时直接报错。"""
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError("来源状态顶层必须是对象")
    return state


def parse_args() -> argparse.Namespace:
    """解析构建器命令行参数。"""
    parser = argparse.ArgumentParser(description="构建 Gemini 演进全景单文件网页")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="时间线 JSON 路径")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="来源检查状态 JSON 路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出 HTML 路径")
    parser.add_argument("--checked-at", help="仅覆盖页面显示的最近检查时间，不回写数据")
    return parser.parse_args()


def main() -> None:
    """校验数据、合并只读构建状态并生成页面。"""
    args = parse_args()
    data = load_timeline(args.data)
    validate_timeline(data)
    state = _load_state(args.state)
    render_data = dict(data)
    render_data["_last_checked_at"] = args.checked_at or state.get("last_checked_at", "未记录")
    write_page(args.output, build_page(render_data))


if __name__ == "__main__":
    main()
