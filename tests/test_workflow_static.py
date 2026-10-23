"""
静态检查 Gemini 自动更新与 GitHub Pages 工作流的权限、顺序和提交边界。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "update-gemini-panorama.yml"


class WorkflowStaticTests(unittest.TestCase):
    """防止自动化扩大权限、提交范围或遗漏发布产物。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_daily_schedule_and_manual_trigger(self) -> None:
        self.assertIn('cron: "30 0 * * *"', self.workflow)
        self.assertRegex(self.workflow, r"(?m)^\s*workflow_dispatch:\s*$")

    def test_permissions_are_minimal_for_commit_and_pages(self) -> None:
        for permission in ("contents: write", "pages: write", "id-token: write"):
            self.assertIn(permission, self.workflow)
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertIn("group: gemini-panorama-pages", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_runtime_and_verification_steps_exist(self) -> None:
        self.assertRegex(self.workflow, r"python-version:\s*[\"']3\.12[\"']")
        self.assertRegex(self.workflow, r"node-version:\s*[\"']24[\"']")
        for path in (
            "tests/test_timeline_data.py",
            "tests/test_gemini_evolution_panorama.py",
            "tests/test_source_parser.py",
            "tests/test_auto_update.py",
        ):
            self.assertIn(path, self.workflow)
        self.assertIn("node --check /tmp/gemini-panorama-script.js", self.workflow)
        self.assertIn("/tmp/gemini-update-result.json", self.workflow)
        self.assertIn("content_changed", self.workflow)

    def test_commit_scope_is_explicit(self) -> None:
        self.assertNotRegex(self.workflow, r"git add\s+(?:-|--\s+)?[.]\s*(?:$|\n)")
        for path in (
            "work/timeline-data.json",
            "work/source-state.json",
            "outputs/gemini-evolution-panorama.html",
            "CHANGELOG.md",
        ):
            self.assertIn(path, self.workflow)
        self.assertIn("更新: 自动同步 Gemini 官方资料", self.workflow)

    def test_pages_artifact_contains_primary_and_downloadable_entry(self) -> None:
        for token in (
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
            "site/index.html",
            "site/gemini-evolution-panorama.html",
            "site/.nojekyll",
        ):
            self.assertIn(token, self.workflow)

    def test_workflow_step_order_matches_safe_pipeline(self) -> None:
        tokens = (
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/setup-node@v4",
            "python3 work/update-gemini-panorama.py",
            "python3 work/build-page.py",
            "node --check /tmp/gemini-panorama-script.js",
            "python3 -m unittest",
            "site/index.html",
            "git add --",
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
        )
        positions = [self.workflow.index(token) for token in tokens]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
