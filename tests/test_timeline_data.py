"""
测试 Gemini 演进时间线的数据契约、官方来源边界和原子写入行为。
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

from timeline_core import (  # noqa: E402
    canonical_source_url,
    event_fingerprint,
    load_timeline,
    validate_timeline,
    write_json_atomic,
)


class TimelineContractTests(unittest.TestCase):
    """验证时间线数据在进入构建和自动更新流程前满足统一约束。"""

    def valid_event(self, event_id: str = "transformer-2017") -> dict:
        """返回一条可独立通过校验的官方事件。"""
        return {
            "id": event_id,
            "date": "2017-06",
            "date_precision": "month",
            "category": "技术基础",
            "families": ["Transformer"],
            "lifecycle": "研究",
            "title": "Transformer 架构提出",
            "summary": "Google 研究团队提出仅依赖注意力机制的 Transformer 架构。",
            "difference": "相比循环和卷积序列模型，核心计算改为自注意力机制。",
            "optimization": "提升并行训练能力，并改善长距离依赖建模。",
            "availability": "研究论文公开。",
            "significance": "奠定 BERT、LaMDA、PaLM 与 Gemini 等模型的技术基础。",
            "importance": "major",
            "predecessors": [],
            "successors": [],
            "sources": [
                {
                    "label": "Attention Is All You Need",
                    "url": "https://research.google/pubs/attention-is-all-you-need/",
                    "grade": "A",
                    "type": "official-paper",
                }
            ],
            "first_seen_at": "2026-10-22T00:00:00+08:00",
            "verified_at": "2026-10-22T00:00:00+08:00",
            "auto_generated": False,
            "verification": "人工核验",
        }

    def valid_data(self) -> dict:
        """返回最小合法顶层数据。"""
        return {
            "schema_version": 1,
            "title": "Gemini / Google AI 产品与模型演进全景",
            "cutoff": "2026-10-22",
            "content_updated_at": "2026-10-22T00:00:00+08:00",
            "events": [self.valid_event()],
        }

    def test_accepts_valid_timeline(self) -> None:
        validate_timeline(self.valid_data(), today=date(2026, 10, 22))

    def test_rejects_event_after_cutoff(self) -> None:
        data = self.valid_data()
        data["events"][0]["date"] = "2026-10-23"
        data["events"][0]["date_precision"] = "day"
        with self.assertRaisesRegex(ValueError, "晚于截止日期"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_non_official_source(self) -> None:
        data = self.valid_data()
        data["events"][0]["sources"][0]["url"] = "https://example.com/gemini"
        with self.assertRaisesRegex(ValueError, "非允许的官方来源"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_duplicate_event_id(self) -> None:
        data = self.valid_data()
        data["events"].append(copy.deepcopy(data["events"][0]))
        with self.assertRaisesRegex(ValueError, "重复事件 ID"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_missing_required_event_field(self) -> None:
        data = self.valid_data()
        del data["events"][0]["difference"]
        with self.assertRaisesRegex(ValueError, "缺少必填字段"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_date_that_conflicts_with_precision(self) -> None:
        data = self.valid_data()
        data["events"][0]["date"] = "2017-06-12"
        data["events"][0]["date_precision"] = "month"
        with self.assertRaisesRegex(ValueError, "日期精度"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_events_not_in_ascending_order(self) -> None:
        data = self.valid_data()
        later = self.valid_event("gemini-2023")
        later["date"] = "2023-12-06"
        later["date_precision"] = "day"
        earlier = self.valid_event("bert-2018")
        earlier["date"] = "2018-10"
        data["events"] = [later, earlier]
        with self.assertRaisesRegex(ValueError, "升序"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_unknown_enumeration_value(self) -> None:
        data = self.valid_data()
        data["events"][0]["category"] = "广告"
        with self.assertRaisesRegex(ValueError, "枚举"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_empty_sources(self) -> None:
        data = self.valid_data()
        data["events"][0]["sources"] = []
        with self.assertRaisesRegex(ValueError, "至少一个来源"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_non_https_source(self) -> None:
        data = self.valid_data()
        data["events"][0]["sources"][0]["url"] = (
            "http://research.google/pubs/attention-is-all-you-need/"
        )
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_missing_relation_target(self) -> None:
        data = self.valid_data()
        data["events"][0]["successors"] = ["missing-event"]
        with self.assertRaisesRegex(ValueError, "引用不存在"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_self_reference(self) -> None:
        data = self.valid_data()
        data["events"][0]["predecessors"] = ["transformer-2017"]
        with self.assertRaisesRegex(ValueError, "自引用"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_duplicate_event_fingerprint(self) -> None:
        data = self.valid_data()
        duplicate = copy.deepcopy(data["events"][0])
        duplicate["id"] = "transformer-duplicate"
        with self.assertRaisesRegex(ValueError, "重复事件指纹"):
            data["events"].append(duplicate)
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_content_update_after_cutoff(self) -> None:
        data = self.valid_data()
        data["content_updated_at"] = "2026-10-23T00:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "内容更新时间晚于截止日期"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_cutoff_after_today(self) -> None:
        data = self.valid_data()
        data["cutoff"] = "2026-10-23"
        with self.assertRaisesRegex(ValueError, "截止日期晚于运行日期"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_rejects_invalid_official_social_metadata(self) -> None:
        data = self.valid_data()
        source = data["events"][0]["sources"][0]
        source.update(
            {
                "url": "https://x.com/GoogleAI/status/123",
                "grade": "A",
                "type": "official-post",
            }
        )
        with self.assertRaisesRegex(ValueError, "官方社交来源"):
            validate_timeline(data, today=date(2026, 10, 22))

    def test_canonical_source_url_removes_tracking_fragment_and_trailing_slash(self) -> None:
        actual = canonical_source_url(
            "https://blog.google/technology/ai/gemini/?utm_source=x&hl=zh-CN#top"
        )
        self.assertEqual(
            actual,
            "https://blog.google/technology/ai/gemini?hl=zh-CN",
        )

    def test_event_fingerprint_ignores_title_spacing_and_source_tracking(self) -> None:
        first = self.valid_event()
        second = copy.deepcopy(first)
        second["title"] = "  Transformer   架构提出 "
        second["sources"][0]["url"] += "?utm_campaign=test"
        self.assertEqual(event_fingerprint(first), event_fingerprint(second))

    def test_atomic_writer_persists_json_and_load_timeline_reads_it(self) -> None:
        payload = self.valid_data()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "nested" / "timeline.json"
            write_json_atomic(output, payload)
            self.assertEqual(load_timeline(output), payload)
            self.assertEqual(list(output.parent.glob("*.tmp")), [])
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                payload,
            )


class InitialCorpusCoverageTests(unittest.TestCase):
    """验证首版人工核验语料覆盖模型、产品、平台和订阅主线。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_timeline(ROOT / "work" / "timeline-data.json")
        cls.events = cls.data["events"]

    def test_representative_milestones_are_covered(self) -> None:
        corpus = " ".join(
            f"{event['title']} {event['summary']} {' '.join(event['families'])}"
            for event in self.events
        )
        expected = (
            "Transformer",
            "BERT",
            "LaMDA",
            "PaLM",
            "PaLM 2",
            "Bard",
            "Gemini 1.0",
            "Gemini 1.5",
            "Gemini 2.0",
            "Gemini 2.5",
            "Gemma",
            "Google AI Studio",
            "Vertex AI",
            "NotebookLM",
            "Project Astra",
            "Gemini Live",
            "Deep Research",
            "Google One AI Premium",
            "Google AI Pro",
            "Google AI Ultra",
            "Gemini Code Assist",
            "Jules",
        )
        for phrase in expected:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, corpus)

    def test_all_major_categories_are_represented(self) -> None:
        represented = {event["category"] for event in self.events}
        self.assertEqual(
            {
                "技术基础",
                "模型",
                "产品",
                "开发者平台",
                "订阅计划",
                "生态集成",
                "研究",
                "安全治理",
                "生命周期",
            },
            represented,
        )

    def test_major_events_have_specific_comparison_optimization_and_significance(self) -> None:
        placeholders = {"暂无", "待补充", "同前代", "持续优化", "重要更新"}
        major_events = [event for event in self.events if event["importance"] == "major"]
        self.assertGreaterEqual(len(major_events), 12)
        for event in major_events:
            for field in ("difference", "optimization", "significance"):
                with self.subTest(event=event["id"], field=field):
                    value = event[field].strip()
                    self.assertGreaterEqual(len(value), 18)
                    self.assertNotIn(value, placeholders)

    def test_every_event_has_a_primary_grade_official_source(self) -> None:
        for event in self.events:
            with self.subTest(event=event["id"]):
                self.assertTrue(
                    any(source["grade"] in {"A", "B"} for source in event["sources"]),
                    "每条事件至少需要一个 A/B 级官方来源",
                )

    def test_latest_verified_model_before_cutoff_is_present(self) -> None:
        corpus = " ".join(event["title"] for event in self.events)
        self.assertIn("Gemini 4 Argon", corpus)


if __name__ == "__main__":
    unittest.main()
