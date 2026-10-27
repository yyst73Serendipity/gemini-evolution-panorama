"""
测试 Gemini 单文件全景网页的预渲染结构、数据转义和离线约束。
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "work" / "build-page.py"
DATA_PATH = ROOT / "work" / "timeline-data.json"
STATE_PATH = ROOT / "work" / "source-state.json"
OUTPUT_PATH = ROOT / "outputs" / "gemini-evolution-panorama.html"
sys.path.insert(0, str(ROOT / "work"))


def load_build_module():
    """从连字符文件名加载页面构建模块。"""
    spec = importlib.util.spec_from_file_location("gemini_build_page", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载页面构建模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeminiPanoramaPageTests(unittest.TestCase):
    """验证构建器输出完整、可筛选且无需远程资源的静态页面。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--data",
                str(DATA_PATH),
                "--state",
                str(STATE_PATH),
                "--output",
                str(OUTPUT_PATH),
            ],
            cwd=ROOT,
            check=True,
        )
        cls.html = OUTPUT_PATH.read_text(encoding="utf-8")
        cls.module = load_build_module()

    def test_page_is_single_file_and_contains_prerendered_events(self) -> None:
        self.assertIn("<!doctype html>", self.html.lower())
        self.assertNotRegex(
            self.html,
            r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://',
        )
        self.assertEqual(self.html.count('class="event-card"'), len(self.data["events"]))
        self.assertIn("<noscript>", self.html)

    def test_every_event_has_filter_attributes_and_source_links(self) -> None:
        for event in self.data["events"]:
            with self.subTest(event=event["id"]):
                self.assertIn(f'id="event-{event["id"]}"', self.html)
                self.assertIn(f'data-year="{event["date"][:4]}"', self.html)
                self.assertIn(f'data-category="{event["category"]}"', self.html)
                self.assertIn(f'data-lifecycle="{event["lifecycle"]}"', self.html)
                self.assertIn(f'data-importance="{event["importance"]}"', self.html)
                for source in event["sources"]:
                    self.assertIn(source["url"], self.html)

    def test_page_contains_title_cutoff_counts_and_check_times(self) -> None:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        self.assertIn(self.data["title"], self.html)
        self.assertIn(self.data["cutoff"], self.html)
        self.assertIn(str(len(self.data["events"])), self.html)
        self.assertIn(self.data["content_updated_at"], self.html)
        self.assertIn(state["last_checked_at"], self.html)

    def test_year_groups_keep_every_event_year_anchor(self) -> None:
        years = sorted({event["date"][:4] for event in self.data["events"]})
        for year in years:
            with self.subTest(year=year):
                self.assertIn(f'id="year-{year}"', self.html)

    def test_page_has_seven_primary_sections_and_semantic_landmarks(self) -> None:
        section_ids = (
            "timeline",
            "lineage",
            "consumer-products",
            "developer-platforms",
            "subscriptions",
            "research-future",
            "methodology",
        )
        self.assertIn("<main", self.html)
        self.assertIn("<nav", self.html)
        self.assertIn("<article", self.html)
        for section_id in section_ids:
            with self.subTest(section=section_id):
                self.assertRegex(self.html, rf'<section[^>]+id="{section_id}"')

    def test_page_has_language_viewport_print_and_accessibility_basics(self) -> None:
        self.assertIn('lang="zh-CN"', self.html)
        self.assertRegex(self.html, r'<meta[^>]+name="viewport"')
        self.assertIn("@media print", self.html)
        self.assertIn('href="#main-content"', self.html)
        self.assertIn('aria-label="时间线筛选器"', self.html)

    def test_format_event_date_respects_precision(self) -> None:
        self.assertEqual(
            self.module.format_event_date({"date": "2017", "date_precision": "year"}),
            "2017 年",
        )
        self.assertEqual(
            self.module.format_event_date({"date": "2024-02", "date_precision": "month"}),
            "2024 年 2 月",
        )
        self.assertEqual(
            self.module.format_event_date({"date": "2026-10-13", "date_precision": "day"}),
            "2026 年 10 月 13 日",
        )

    def test_event_card_escapes_untrusted_data(self) -> None:
        event = dict(self.data["events"][0])
        event.update(
            {
                "id": 'unsafe"-id',
                "title": "<script>alert(1)</script>",
                "summary": "A & B",
                "families": ["Gemini <X>"],
                "sources": [
                    {
                        "label": "官方 <来源>",
                        "url": "https://blog.google/example?x=1&y=2",
                        "grade": "A",
                        "type": "official-announcement",
                    }
                ],
            }
        )
        card = self.module.build_event_card(event)
        self.assertNotIn("<script>alert(1)</script>", card)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", card)
        self.assertIn("A &amp; B", card)
        self.assertIn("unsafe&quot;-id", card)
        self.assertIn("x=1&amp;y=2", card)

    def test_cli_checked_at_override_does_not_rewrite_timeline_data(self) -> None:
        before = DATA_PATH.read_bytes()
        checked_at = "2026-10-22T12:34:56+08:00"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "page.html"
            subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--data",
                    str(DATA_PATH),
                    "--state",
                    str(STATE_PATH),
                    "--output",
                    str(output),
                    "--checked-at",
                    checked_at,
                ],
                cwd=ROOT,
                check=True,
            )
            self.assertIn(checked_at, output.read_text(encoding="utf-8"))
        self.assertEqual(before, DATA_PATH.read_bytes())

    def test_filter_controls_are_prerendered(self) -> None:
        for control_id in (
            "search-input",
            "year-filter",
            "category-filter",
            "family-filter",
            "lifecycle-filter",
            "reset-filters",
        ):
            with self.subTest(control=control_id):
                self.assertIn(f'id="{control_id}"', self.html)
        self.assertIn('id="no-results"', self.html)
        self.assertIn('class="reset-button" id="reset-filters"', self.html)
        self.assertNotIn('class="year-nav"', self.html)
        self.assertNotIn('id="major-only"', self.html)
        self.assertNotIn('id="result-count"', self.html)

    def test_interaction_controls_and_accessibility_hooks_exist(self) -> None:
        for token in (
            'id="search-input"',
            'id="category-filter"',
            'id="family-filter"',
            'id="lifecycle-filter"',
            'id="theme-toggle"',
            'function applyFilters()',
            'function syncUrlState()',
            'function restoreUrlState()',
            'function setTheme(theme)',
            'function updateReadingProgress()',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)

    def test_visual_accessibility_and_offline_theme_hooks_exist(self) -> None:
        for token in (
            'prefers-reduced-motion',
            ':focus-visible',
            '@media print',
            'href="#main-content"',
            'id="no-results"',
            "localStorage.getItem('gemini-panorama-theme')",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)

    def test_editorial_visual_system_is_embedded_without_legacy_gradient_shell(self) -> None:
        for token in (
            '--paper:',
            '--ink:',
            '--accent-blue:',
            '--category-model:',
            'data-design="editorial"',
            '.timeline-rail',
            '.control-field',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertNotIn('radial-gradient(circle at 8% 0%', self.html)
        self.assertNotIn('--accent: linear-gradient', self.html)

    def test_editorial_timeline_and_material_controls_keep_required_structure(self) -> None:
        self.assertIn('class="timeline timeline-rail"', self.html)
        self.assertIn('class="control control-field"', self.html)
        self.assertIn('class="year-heading"', self.html)
        self.assertIn('class="event-card"', self.html)
        self.assertIn('@media (max-width: 680px)', self.html)
        self.assertIn('.year-group { grid-template-columns: 1fr;', self.html)

    def test_theme_toggle_uses_compact_icon_label_control(self) -> None:
        for token in (
            'class="theme-toggle-icon"',
            'class="theme-toggle-label">主题</span>',
            '.theme-toggle-icon {',
            "themeToggle.querySelector('.theme-toggle-label')",
            'themeToggle.dataset.theme = preference',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertNotIn("themeToggle.textContent = labels[preference]", self.html)

    def test_filter_layout_keeps_compact_year_lifecycle_and_inline_reset(self) -> None:
        for token in (
            '.control-grid { display: grid; grid-template-columns:',
            'class="control control-field compact-filter" for="year-filter"',
            'class="control control-field compact-filter" for="lifecycle-filter"',
            'class="reset-button" id="reset-filters"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertNotIn('class="control-actions"', self.html)
        self.assertNotIn('aria-label="年份导航"', self.html)

    def test_official_sources_use_compact_inline_references(self) -> None:
        for token in (
            '.sources { display: flex; flex-wrap: wrap; align-items: baseline;',
            '.sources a { display: inline-flex; align-items: baseline;',
            '.sources a::before { content: "↗";',
            'border: 0; background: transparent;',
            '.sources a:hover span { color: var(--accent-deep);',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertNotIn('.sources a { display: grid;', self.html)

    def test_filter_controls_share_vertical_height(self) -> None:
        self.assertIn(
            '.control input, .control select { min-width: 0; width: 100%; height: 48px;',
            self.html,
        )
        self.assertIn(
            '.reset-button { align-self: end; display: inline-flex; align-items: center; justify-content: center; height: 48px;',
            self.html,
        )

    def test_theme_toggle_is_explicitly_two_state(self) -> None:
        for token in (
            "const preference = ['light', 'dark'].includes(theme) ? theme : 'light';",
            "const savedTheme = localStorage.getItem('gemini-panorama-theme') || 'light';",
            "const order = ['light', 'dark'];",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertNotIn("'system'", self.html)
        self.assertNotIn('prefers-color-scheme', self.html)
        self.assertNotIn("matchMedia('(prefers-color-scheme: dark)')", self.html)


if __name__ == "__main__":
    unittest.main()
