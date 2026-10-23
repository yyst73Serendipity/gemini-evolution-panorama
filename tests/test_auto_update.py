"""
测试 Gemini 自动更新器的候选生成、去重、失败保护和原子替换边界。
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = ROOT / "work" / "update-gemini-panorama.py"
sys.path.insert(0, str(ROOT / "work"))


def load_update_module():
    """从连字符文件名加载自动更新模块。"""
    spec = importlib.util.spec_from_file_location("gemini_auto_update", UPDATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载自动更新模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AutoUpdateTests(unittest.TestCase):
    """验证更新器只发布可信新事实，并在失败时保留正式产物。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_update_module()
        cls.timeline = json.loads((ROOT / "work" / "timeline-data.json").read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.temp_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def checked_at(self) -> datetime:
        """使用当前时间线截止日构造稳定的测试检查时间。"""
        return datetime.fromisoformat(f"{self.timeline['cutoff']}T08:30:00+08:00")

    def existing_events(self) -> list[dict]:
        return copy.deepcopy(self.timeline["events"][:1])

    def candidate(self, *, date: str = "2026-10-20", title: str = "Gemini Example 发布", url: str = "https://blog.google/products/gemini/example") -> dict:
        return self.module.build_candidate_event(
            {
                "date": date,
                "title": title,
                "description": "Google 发布 Gemini Example，并说明新的模型可用范围。",
                "stable_text": "Gemini Example model is generally available.",
                "url": url,
            },
            {
                "name": "google-blog-gemini",
                "label": "Google Blog Gemini 专题",
                "type": "page",
                "url": url,
                "grade": "A",
                "required": False,
                "path_prefixes": ["/products/gemini/"],
                "required_keywords": ["Gemini"],
            },
            "2026-10-22T08:30:00+08:00",
        )

    def temp_paths(self, *, build_script: Path | None = None):
        data_path = self.temp_root / "work" / "timeline-data.json"
        state_path = self.temp_root / "work" / "source-state.json"
        output_path = self.temp_root / "outputs" / "gemini-evolution-panorama.html"
        changelog_path = self.temp_root / "CHANGELOG.md"
        data_path.parent.mkdir(parents=True)
        output_path.parent.mkdir(parents=True)
        data_path.write_text(json.dumps(self.timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {"last_checked_at": "2026-10-22T00:00:00+08:00", "known_urls": [], "page_hashes": {}, "source_health": {}},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        output_path.write_text("<!doctype html><p>old output</p>\n", encoding="utf-8")
        changelog_path.write_text("# 更新日志\n", encoding="utf-8")
        return self.module.UpdatePaths(
            root=self.temp_root,
            timeline=data_path,
            state=state_path,
            output=output_path,
            changelog=changelog_path,
            build_script=build_script or ROOT / "work" / "build-page.py",
        )

    def test_listing_link_is_remembered_before_article_candidate_processing(self) -> None:
        known: set[str] = set()
        link = "https://blog.google/products/gemini/example"

        self.assertTrue(self.module.claim_listing_link(known, link, bootstrap=False))
        self.assertFalse(self.module.claim_listing_link(known, link, bootstrap=False))
        self.assertIn(self.module.listing_link_key(link), known)

    def test_bootstrap_listing_link_is_remembered_without_fetching_article(self) -> None:
        known: set[str] = set()
        link = "https://blog.google/products/gemini/example"

        self.assertFalse(self.module.claim_listing_link(known, link, bootstrap=True))
        self.assertIn(self.module.listing_link_key(link), known)

    def test_merge_rejects_future_and_duplicate_candidates(self) -> None:
        existing = self.existing_events()
        duplicate = copy.deepcopy(existing[0])
        future = self.candidate(date="2026-10-23", title="Gemini Future")
        new = self.candidate()
        merged, accepted = self.module.merge_candidates(
            existing,
            [duplicate, future, new],
            cutoff="2026-10-22",
        )
        self.assertEqual([item["id"] for item in accepted], ["2026-10-20-gemini-example"])
        self.assertEqual(len(merged), len(existing) + 1)

    def test_same_url_duplicate_is_not_added(self) -> None:
        candidate = self.candidate()
        merged, accepted = self.module.merge_candidates([candidate], [copy.deepcopy(candidate)], "2026-10-22")
        self.assertEqual(merged, [candidate])
        self.assertEqual(accepted, [])

    def test_same_fact_with_different_url_adds_source_to_existing_event(self) -> None:
        original = self.candidate(url="https://blog.google/products/gemini/example")
        second = self.candidate(url="https://deepmind.google/models/gemini/example")
        merged, accepted = self.module.merge_candidates([original], [second], "2026-10-22")
        self.assertEqual(accepted, [])
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_more_than_twenty_additions_stops_update(self) -> None:
        candidates = [
            self.candidate(title=f"Gemini Example {index}", url=f"https://blog.google/products/gemini/example-{index}")
            for index in range(21)
        ]
        with self.assertRaisesRegex(ValueError, "20"):
            self.module.merge_candidates([], candidates, "2026-10-22")

    def test_low_confidence_candidate_is_not_publishable(self) -> None:
        with self.assertRaisesRegex(ValueError, "置信度"):
            self.module.build_candidate_event(
                {
                    "date": "2026-10-20",
                    "title": "General Search update",
                    "description": "A general interface update.",
                    "stable_text": "No model relationship.",
                    "url": "https://blog.google/products/search/example",
                },
                {
                    "name": "example",
                    "label": "Google Blog",
                    "type": "page",
                    "url": "https://blog.google/products/search/example",
                    "grade": "A",
                    "required": False,
                    "path_prefixes": ["/products/"],
                    "required_keywords": ["Gemini"],
                },
                "2026-10-22T08:30:00+08:00",
            )

    def test_generated_event_uses_conservative_language(self) -> None:
        event = self.candidate()
        self.assertTrue(event["auto_generated"])
        self.assertEqual(event["verification"], "自动收录")
        self.assertIn("以官方原文为准", event["difference"])
        self.assertIn("不推断", event["significance"])

    def test_timestamp_only_check_does_not_mark_content_changed(self) -> None:
        result = self.module.stage_update(
            paths=self.temp_paths(),
            candidates=[],
            checked_at=self.checked_at(),
        )
        self.assertFalse(result.content_changed)
        self.assertTrue(result.checked_at_changed)
        self.assertEqual(result.changed_paths, ())

    def test_source_health_timestamp_only_change_is_not_content_change(self) -> None:
        paths = self.temp_paths()
        state = json.loads(paths.state.read_text(encoding="utf-8"))
        state["source_health"] = {
            "required": {"ok": True, "final_url": "https://ai.google.dev/gemini-api/docs/changelog", "error": "", "checked_at": "2026-10-22T00:00:00+08:00"}
        }
        paths.state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        next_state = copy.deepcopy(state)
        next_state["last_checked_at"] = "2026-10-22T08:30:00+08:00"
        next_state["source_health"]["required"]["checked_at"] = "2026-10-22T08:30:00+08:00"
        result = self.module.stage_update(
            paths=paths,
            candidates=[],
            checked_at=self.checked_at(),
            next_source_state=next_state,
        )
        self.assertFalse(result.source_state_changed)
        self.assertFalse(result.content_changed)

    def test_build_failure_does_not_replace_formal_files(self) -> None:
        failing_builder = self.temp_root / "fail-builder.py"
        failing_builder.write_text("raise SystemExit(9)\n", encoding="utf-8")
        paths = self.temp_paths(build_script=failing_builder)
        before = {path: path.read_bytes() for path in (paths.timeline, paths.state, paths.output, paths.changelog)}
        with self.assertRaises(Exception):
            self.module.stage_update(
                paths=paths,
                candidates=[self.candidate()],
                checked_at=self.checked_at(),
            )
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_apply_failure_rolls_back_already_replaced_files(self) -> None:
        paths = self.temp_paths()
        result = self.module.stage_update(
            paths=paths,
            candidates=[self.candidate()],
            checked_at=self.checked_at(),
        )
        before = {path: path.read_bytes() for path in (paths.timeline, paths.output, paths.changelog)}
        real_replace = os.replace
        calls = 0

        def flaky_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected replacement failure")
            return real_replace(source, destination)

        with patch.object(self.module.os, "replace", side_effect=flaky_replace):
            with self.assertRaisesRegex(OSError, "injected"):
                self.module.apply_staged_update(result)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_changed_paths_are_restricted_to_publishable_files(self) -> None:
        paths = self.temp_paths()
        result = self.module.stage_update(
            paths=paths,
            candidates=[self.candidate()],
            checked_at=self.checked_at(),
        )
        allowed = {
            "work/timeline-data.json",
            "work/source-state.json",
            "outputs/gemini-evolution-panorama.html",
            "CHANGELOG.md",
        }
        self.assertTrue(set(result.changed_paths).issubset(allowed))

    def test_required_source_policy_only_stops_when_all_required_fail(self) -> None:
        config = {"sources": [{"name": "a", "required": True}, {"name": "b", "required": True}, {"name": "optional", "required": False}]}
        self.module.ensure_required_sources_available(config, {"a": {"ok": True}, "b": {"ok": False}, "optional": {"ok": False}})
        with self.assertRaisesRegex(RuntimeError, "必需来源"):
            self.module.ensure_required_sources_available(config, {"a": {"ok": False}, "b": {"ok": False}, "optional": {"ok": True}})


if __name__ == "__main__":
    unittest.main()
