from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hermes_sync.py"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class HermesSyncCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.upstream = self.root / "upstream.git"
        self.consumer = self.root / "consumer"

        self.source.mkdir()
        git(self.source, "init", "-b", "main")
        git(self.source, "config", "user.name", "Test User")
        git(self.source, "config", "user.email", "test@example.com")
        (self.source / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        git(self.source, "add", "tracked.txt")
        git(self.source, "commit", "-m", "baseline")
        self.baseline = git(self.source, "rev-parse", "HEAD")

        git(self.root, "init", "--bare", str(self.upstream))
        git(self.source, "remote", "add", "origin", str(self.upstream))
        git(self.source, "push", "-u", "origin", "main")
        git(self.root, "clone", str(self.upstream), str(self.consumer))

        self.baseline_file = self.consumer / "baseline"
        self.output_dir = self.consumer / "pending"
        self.baseline_file.write_text(f"{self.baseline}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_sync(self, *, check: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("GITHUB_OUTPUT", None)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(self.consumer),
                "--baseline-file",
                str(self.baseline_file),
                "--output-dir",
                str(self.output_dir),
                "--upstream-url",
                str(self.upstream),
            ],
            cwd=REPO_ROOT,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def add_upstream_commit(self) -> str:
        (self.source / "future.txt").write_text("future change\n", encoding="utf-8")
        git(self.source, "add", "future.txt")
        git(self.source, "commit", "-m", "future change")
        git(self.source, "push", "origin", "main")
        return git(self.source, "rev-parse", "HEAD")

    def test_rejects_invalid_baseline(self) -> None:
        self.baseline_file.write_text("not-a-commit\n", encoding="utf-8")

        result = self.run_sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn("40-character lowercase hexadecimal", result.stderr)
        self.assertFalse(self.output_dir.exists())

    def test_no_update_writes_no_pending_artifacts(self) -> None:
        result = self.run_sync(check=True)

        self.assertIn("No Hermes update", result.stdout)
        self.assertFalse(self.output_dir.exists())

    def test_update_writes_report_patch_and_candidate(self) -> None:
        upstream_tip = self.add_upstream_commit()

        result = self.run_sync(check=True)

        self.assertIn("1 new Hermes commit", result.stdout)
        report = (self.output_dir / "REPORT.md").read_text(encoding="utf-8")
        patch = (self.output_dir / "upstream.patch").read_text(encoding="utf-8")
        commits = (self.output_dir / "commits.tsv").read_text(encoding="utf-8")
        changed_files = (self.output_dir / "changed-files.tsv").read_text(encoding="utf-8")
        candidate = (self.output_dir / "candidate-baseline").read_text(encoding="utf-8")

        self.assertIn(self.baseline, report)
        self.assertIn(upstream_tip, report)
        self.assertIn(upstream_tip, commits)
        self.assertIn("future change", commits)
        self.assertIn("future.txt", changed_files)
        self.assertIn("future.txt", patch)
        self.assertEqual(candidate, f"{upstream_tip}\n")
        self.assertEqual(self.baseline_file.read_text(encoding="utf-8"), f"{self.baseline}\n")

    def test_rejects_non_ancestor_baseline(self) -> None:
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        git(unrelated, "init", "-b", "main")
        git(unrelated, "config", "user.name", "Test User")
        git(unrelated, "config", "user.email", "test@example.com")
        (unrelated / "other.txt").write_text("other history\n", encoding="utf-8")
        git(unrelated, "add", "other.txt")
        git(unrelated, "commit", "-m", "unrelated")
        unrelated_sha = git(unrelated, "rev-parse", "HEAD")
        git(self.consumer, "fetch", str(unrelated), "main:refs/heads/unrelated")
        self.baseline_file.write_text(f"{unrelated_sha}\n", encoding="utf-8")

        result = self.run_sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn("is not an ancestor", result.stderr)
        self.assertFalse(self.output_dir.exists())


if __name__ == "__main__":
    unittest.main()
