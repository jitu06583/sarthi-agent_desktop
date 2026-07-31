from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hermes-forward-sync.yml"
VALIDATION_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hermes-sync-validation.yml"
BASELINE = REPO_ROOT / ".github" / "hermes-sync" / "baseline"


class HermesSyncWorkflowContractTests(unittest.TestCase):
    def workflow_text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_has_manual_and_daily_triggers(self) -> None:
        text = self.workflow_text()

        self.assertIn("schedule:", text)
        self.assertIn('cron: "17 4 * * *"', text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("group: hermes-forward-sync", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_workflow_uses_minimum_write_permissions(self) -> None:
        text = self.workflow_text()

        self.assertRegex(text, r"permissions:\s+contents: write\s+pull-requests: write")
        self.assertNotIn("write-all", text)
        self.assertNotIn("pull_request_target", text)

    def test_workflow_skips_when_sync_pr_is_open(self) -> None:
        text = self.workflow_text()

        self.assertIn("gh pr list", text)
        self.assertIn("automation/hermes-forward-sync", text)
        self.assertIn("open_pr", text)
        self.assertRegex(text, r"if: steps\.existing\.outputs\.open_pr != 'true'")
        self.assertIn("set -euo pipefail", text)
        self.assertIn('open_count="$(gh pr list', text)
        self.assertIn('if [[ "$open_count" == "0" ]]', text)

    def test_workflow_creates_draft_pr_without_auto_merge(self) -> None:
        text = self.workflow_text()

        self.assertIn("gh pr create", text)
        self.assertIn("--draft", text)
        self.assertIn("steps.sync.outputs.updated == 'true'", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotRegex(text, r"(?m)^\s*auto-merge:")
        self.assertNotIn("candidate-baseline .github/hermes-sync/baseline", text)

    def test_manual_dispatch_always_checks_out_main(self) -> None:
        text = self.workflow_text()

        self.assertRegex(text, r"uses: actions/checkout@v4\s+with:\s+ref: main\s+fetch-depth: 0")

    def test_pull_request_validation_workflow_runs_focused_tests(self) -> None:
        text = VALIDATION_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request:", text)
        self.assertIn("name: Hermes Sync Validation", text)
        self.assertIn("python -m unittest discover", text)
        self.assertIn("python -m py_compile", text)
        self.assertNotIn("contents: write", text)

    def test_baseline_is_full_sha(self) -> None:
        baseline = BASELINE.read_text(encoding="utf-8")

        self.assertRegex(baseline, r"^[0-9a-f]{40}\n$")


if __name__ == "__main__":
    unittest.main()
