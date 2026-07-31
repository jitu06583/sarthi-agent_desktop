#!/usr/bin/env python3
"""Generate review artifacts for forward-only Hermes upstream synchronization."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


UPSTREAM_REF = "refs/remotes/hermes-sync/upstream"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class HermesSyncError(RuntimeError):
    """Raised when synchronization cannot proceed safely."""


def run_git(repo: Path, *args: str, capture_bytes: bool = False) -> str | bytes:
    """Run Git in *repo* and return stdout, raising a readable sync error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=not capture_bytes,
            encoding=None if capture_bytes else "utf-8",
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        detail = (stderr or "git command failed").strip()
        raise HermesSyncError(f"git {' '.join(args)} failed: {detail}") from exc
    if capture_bytes:
        return result.stdout
    return result.stdout.strip()


def read_baseline(path: Path) -> str:
    """Read and validate the accepted upstream baseline."""
    try:
        baseline = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise HermesSyncError(f"Unable to read baseline file {path}: {exc}") from exc
    if not SHA_RE.fullmatch(baseline):
        raise HermesSyncError(
            f"Baseline must be a 40-character lowercase hexadecimal commit SHA: {path}"
        )
    return baseline


def set_github_outputs(updated: bool, upstream_sha: str, commit_count: int) -> None:
    """Expose generator state to GitHub Actions when running in a workflow."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"updated={'true' if updated else 'false'}\n")
        handle.write(f"upstream_sha={upstream_sha}\n")
        handle.write(f"commit_count={commit_count}\n")


def _resolve_path(repo: Path, value: Path) -> Path:
    return value if value.is_absolute() else repo / value


def generate(
    repo: Path,
    baseline_file: Path,
    upstream_url: str,
    upstream_branch: str,
    output_dir: Path,
) -> bool:
    """Fetch upstream and generate artifacts when commits follow the baseline."""
    repo = repo.resolve()
    baseline_file = _resolve_path(repo, baseline_file)
    output_dir = _resolve_path(repo, output_dir)
    baseline = read_baseline(baseline_file)

    run_git(
        repo,
        "fetch",
        "--no-tags",
        upstream_url,
        f"+refs/heads/{upstream_branch}:{UPSTREAM_REF}",
    )
    upstream_sha = str(run_git(repo, "rev-parse", UPSTREAM_REF))
    if not SHA_RE.fullmatch(upstream_sha):
        raise HermesSyncError(f"Fetched upstream resolved to an invalid SHA: {upstream_sha}")

    run_git(repo, "cat-file", "-e", f"{baseline}^{{commit}}")

    if output_dir.exists():
        shutil.rmtree(output_dir)

    if baseline == upstream_sha:
        set_github_outputs(False, upstream_sha, 0)
        print(f"No Hermes update: baseline already equals {upstream_sha}")
        return False

    try:
        run_git(repo, "merge-base", "--is-ancestor", baseline, upstream_sha)
    except HermesSyncError as exc:
        raise HermesSyncError(
            f"Accepted baseline {baseline} is not an ancestor of upstream {upstream_sha}; "
            "manual history review is required"
        ) from exc

    commit_count = int(str(run_git(repo, "rev-list", "--count", f"{baseline}..{upstream_sha}")))
    commits = str(
        run_git(
            repo,
            "log",
            "--reverse",
            "--date=iso-strict",
            "--format=%H%x09%aI%x09%an%x09%s",
            f"{baseline}..{upstream_sha}",
        )
    )
    changed_files = str(
        run_git(
            repo,
            "diff",
            "--name-status",
            "--find-renames",
            baseline,
            upstream_sha,
        )
    )
    patch = run_git(
        repo,
        "format-patch",
        "--binary",
        "--full-index",
        "--stdout",
        f"{baseline}..{upstream_sha}",
        capture_bytes=True,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report = (
        "# Pending Hermes Forward Synchronization\n\n"
        f"- Accepted baseline: `{baseline}`\n"
        f"- Upstream candidate: `{upstream_sha}`\n"
        f"- New commits: **{commit_count}**\n"
        f"- Source: `{upstream_url}` (`{upstream_branch}`)\n\n"
        "## Review requirement\n\n"
        "This directory is evidence for a manual Sarthi port. Do not merge the "
        "patch blindly. Preserve Sarthi naming, desktop integration, ACP behavior, "
        "and tests. Advance the accepted baseline only after applicable changes "
        "have been reviewed and validated.\n"
    )
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    (output_dir / "commits.tsv").write_text(
        f"sha\tauthor_date\tauthor\tsubject\n{commits}\n", encoding="utf-8", newline="\n"
    )
    (output_dir / "changed-files.tsv").write_text(
        f"status\tpath\n{changed_files}\n", encoding="utf-8", newline="\n"
    )
    (output_dir / "upstream.patch").write_bytes(bytes(patch))
    (output_dir / "candidate-baseline").write_text(
        f"{upstream_sha}\n", encoding="utf-8", newline="\n"
    )

    set_github_outputs(True, upstream_sha, commit_count)
    noun = "commit" if commit_count == 1 else "commits"
    print(f"Generated review artifacts for {commit_count} new Hermes {noun}: {upstream_sha}")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--baseline-file", type=Path, default=Path(".github/hermes-sync/baseline")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path(".github/hermes-sync/pending")
    )
    parser.add_argument(
        "--upstream-url", default="https://github.com/NousResearch/hermes-agent.git"
    )
    parser.add_argument("--upstream-branch", default="main")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        generate(
            repo=args.repo,
            baseline_file=args.baseline_file,
            upstream_url=args.upstream_url,
            upstream_branch=args.upstream_branch,
            output_dir=args.output_dir,
        )
    except HermesSyncError as exc:
        print(f"Hermes sync error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
