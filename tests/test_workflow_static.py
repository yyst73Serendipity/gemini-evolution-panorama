"""
静态检查 Gemini 官方资料更新与 GitHub Pages 发布工作流的权限、职责和步骤顺序。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE_WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "update-gemini-panorama.yml"
)
DEPLOY_WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "deploy-gemini-pages.yml"
)


class UpdateWorkflowStaticTests(unittest.TestCase):
    """防止官方资料更新工作流扩大职责、权限或提交范围。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = UPDATE_WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_only_daily_schedule_and_manual_trigger_are_enabled(self) -> None:
        self.assertIn('cron: "30 0 * * *"', self.workflow)
        self.assertRegex(self.workflow, r"(?m)^\s{2}workflow_dispatch:\s*$")
        self.assertNotRegex(self.workflow, r"(?m)^\s{2}push:\s*$")

    def test_update_job_has_only_contents_write_permission(self) -> None:
        update_job = self.workflow.split("  deploy-pages:", maxsplit=1)[0]
        self.assertIn("contents: write", update_job)
        self.assertNotIn("pages: write", update_job)
        self.assertNotIn("id-token: write", update_job)
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertIn("group: gemini-panorama-update", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_runtime_and_verification_steps_exist(self) -> None:
        self.assertRegex(self.workflow, r"python-version:\s*[\"']3\.12[\"']")
        self.assertRegex(self.workflow, r"node-version:\s*[\"']24[\"']")
        for path in (
            "tests/test_timeline_data.py",
            "tests/test_gemini_evolution_panorama.py",
            "tests/test_source_parser.py",
            "tests/test_auto_update.py",
            "tests/test_workflow_static.py",
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

    def test_update_job_exposes_checked_at_output(self) -> None:
        self.assertRegex(
            self.workflow,
            r"(?s)outputs:\s+checked_at:\s*\$\{\{\s*steps\.update-result\.outputs\.checked_at\s*\}\}",
        )

    def test_deploy_is_delegated_to_reusable_workflow(self) -> None:
        self.assertIn("uses: ./.github/workflows/deploy-gemini-pages.yml", self.workflow)
        self.assertRegex(
            self.workflow,
            r"checked_at:\s*\$\{\{\s*needs\.update\.outputs\.checked_at\s*\}\}",
        )
        for token in (
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
            "site/index.html",
        ):
            self.assertNotIn(token, self.workflow)

    def test_update_step_order_matches_safe_pipeline(self) -> None:
        tokens = (
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/setup-node@v4",
            "python3 work/update-gemini-panorama.py",
            "python3 work/build-page.py",
            "node --check /tmp/gemini-panorama-script.js",
            "python3 -m unittest",
            "id: update-result",
            "git add --",
            "uses: ./.github/workflows/deploy-gemini-pages.yml",
        )
        positions = [self.workflow.index(token) for token in tokens]
        self.assertEqual(positions, sorted(positions))


class DeployWorkflowStaticTests(unittest.TestCase):
    """保证独立发布工作流只构建、验证并部署 Pages。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = DEPLOY_WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_main_push_manual_and_reusable_triggers_exist(self) -> None:
        self.assertRegex(
            self.workflow,
            r"(?s)push:\s+branches:\s+- main",
        )
        self.assertRegex(self.workflow, r"(?m)^\s{2}workflow_dispatch:\s*$")
        self.assertRegex(self.workflow, r"(?m)^\s{2}workflow_call:\s*$")

    def test_checked_at_is_an_optional_string_input(self) -> None:
        self.assertRegex(
            self.workflow,
            r"(?s)workflow_call:\s+inputs:\s+checked_at:\s+required:\s+false\s+type:\s+string",
        )
        self.assertIn("CHECKED_AT: ${{ inputs.checked_at }}", self.workflow)
        self.assertIn('--checked-at "$CHECKED_AT"', self.workflow)

    def test_permissions_are_minimal_for_pages(self) -> None:
        for permission in ("contents: read", "pages: write", "id-token: write"):
            self.assertIn(permission, self.workflow)
        for permission in ("contents: write", "pull-requests: write", "actions: write"):
            self.assertNotIn(permission, self.workflow)
        self.assertIn("group: gemini-panorama-pages", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_update_and_git_write_commands_are_absent(self) -> None:
        for token in (
            "update-gemini-panorama.py",
            "git add",
            "git commit",
            "git push",
            "更新: 自动同步 Gemini 官方资料",
        ):
            self.assertNotIn(token, self.workflow)

    def test_runtime_build_and_full_verification_exist(self) -> None:
        self.assertRegex(self.workflow, r"python-version:\s*[\"']3\.12[\"']")
        self.assertRegex(self.workflow, r"node-version:\s*[\"']24[\"']")
        self.assertIn("python3 work/build-page.py", self.workflow)
        self.assertIn("node --check /tmp/gemini-panorama-script.js", self.workflow)
        self.assertIn("python3 -m unittest", self.workflow)
        for path in (
            "tests/test_timeline_data.py",
            "tests/test_gemini_evolution_panorama.py",
            "tests/test_source_parser.py",
            "tests/test_auto_update.py",
            "tests/test_workflow_static.py",
        ):
            self.assertIn(path, self.workflow)

    def test_pages_artifact_contains_both_entries_and_nojekyll(self) -> None:
        for token in (
            "site/index.html",
            "site/gemini-evolution-panorama.html",
            "site/.nojekyll",
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
        ):
            self.assertIn(token, self.workflow)

    def test_deploy_step_order_matches_safe_pipeline(self) -> None:
        tokens = (
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/setup-node@v4",
            "python3 work/build-page.py",
            "node --check /tmp/gemini-panorama-script.js",
            "python3 -m unittest",
            "site/gemini-evolution-panorama.html",
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
        )
        positions = [self.workflow.index(token) for token in tokens]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
