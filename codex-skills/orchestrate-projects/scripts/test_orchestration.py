#!/usr/bin/env python3
"""Integration tests for bootstrap and project-guard behavior."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
import os
import stat
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = SKILL_ROOT / "scripts/bootstrap_project.py"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    result = run(["git", "init", "-b", "main", str(repo)], root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    run(["git", "config", "--local", "user.name", "Guard Test"], repo)
    run(["git", "config", "--local", "user.email", "guard@example.invalid"], repo)
    return repo


class OrchestrationIntegrationTest(unittest.TestCase):

    def test_generic_requires_real_full_command_without_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = init_repo(Path(temp))
            result = run(
                ["python3", str(BOOTSTRAP), "--repo", str(repo), "--name", "Generic", "--type", "generic"],
                repo,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("require --full-command", result.stderr)
            self.assertFalse((repo / "GOALS.md").exists())

    def test_worktree_verify_and_stale_evidence_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = init_repo(Path(temp))
            bootstrap = run(
                [
                    "python3", str(BOOTSTRAP), "--repo", str(repo), "--name", "Smoke", "--type", "generic",
                    "--full-command", "/usr/bin/true",
                ],
                repo,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr)
            shared_env = repo / ".venv"
            shared_env.mkdir()
            (shared_env / "marker").write_text("shared\n", encoding="utf-8")
            (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
            self.assertEqual(0, run(["git", "add", "."], repo).returncode)
            self.assertEqual(0, run(["git", "commit", "-m", "bootstrap"], repo).returncode)
            repository_exclude = Path(run(["git", "rev-parse", "--git-path", "info/exclude"], repo).stdout.strip())
            if not repository_exclude.is_absolute():
                repository_exclude = repo / repository_exclude
            original_exclude_mode = stat.S_IMODE(repository_exclude.stat().st_mode)

            invalid_base = run(["python3", "scripts/project_guard.py", "start", "fix", "bad", "--base", "HEAD"], repo)
            self.assertEqual(2, invalid_base.returncode)
            self.assertIn("base", invalid_base.stderr)

            started = run(["python3", "scripts/project_guard.py", "start", "fix", "smoke"], repo)
            self.assertEqual(0, started.returncode, started.stderr)
            worktree = Path(temp) / "worktrees/repo/fix-smoke"
            self.assertTrue((worktree / ".git").is_file())
            self.assertTrue((worktree / ".venv").is_symlink())
            self.assertEqual((worktree / ".venv").resolve(), shared_env.resolve())
            exclude_path = Path(run(["git", "rev-parse", "--git-path", "info/exclude"], worktree).stdout.strip())
            if not exclude_path.is_absolute():
                exclude_path = worktree / exclude_path
            self.assertEqual(exclude_path.resolve(), (repo / ".git/info/exclude").resolve())
            self.assertIn(".venv", exclude_path.read_text(encoding="utf-8").splitlines())
            self.assertEqual(stat.S_IMODE(exclude_path.stat().st_mode), original_exclude_mode)
            self.assertEqual(0, run(["python3", "scripts/project_guard.py", "preflight"], worktree).returncode)
            self.assertEqual(0, run(["python3", "scripts/project_guard.py", "verify", "full"], worktree).returncode)
            self.assertEqual(0, run(["python3", "scripts/project_guard.py", "merge-check"], worktree).returncode)

            goals = worktree / "GOALS.md"
            goals.write_text(goals.read_text(encoding="utf-8") + "\nNew commit.\n", encoding="utf-8")
            self.assertEqual(0, run(["git", "add", "GOALS.md"], worktree).returncode)
            self.assertEqual(0, run(["git", "commit", "-m", "invalidate evidence"], worktree).returncode)
            stale = run(["python3", "scripts/project_guard.py", "merge-check"], worktree)
            self.assertEqual(2, stale.returncode)
            self.assertIn("证据未绑定", stale.stderr)

    def test_start_failure_cleans_new_worktree_and_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = init_repo(Path(temp))
            bootstrap = run(
                [
                    "python3", str(BOOTSTRAP), "--repo", str(repo), "--name", "Cleanup", "--type", "generic",
                    "--full-command", "/usr/bin/true",
                ],
                repo,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr)
            shared_env = repo / ".venv"
            shared_env.mkdir()
            (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
            self.assertEqual(0, run(["git", "add", "."], repo).returncode)
            self.assertEqual(0, run(["git", "commit", "-m", "bootstrap"], repo).returncode)

            exclude_path = Path(run(["git", "rev-parse", "--git-path", "info/exclude"], repo).stdout.strip())
            if not exclude_path.is_absolute():
                exclude_path = repo / exclude_path
            exclude_path.parent.mkdir(parents=True, exist_ok=True)
            exclude_path.touch(exist_ok=True)
            original_mode = exclude_path.parent.stat().st_mode
            read_only_mode = original_mode & ~0o222
            exclude_path.parent.chmod(read_only_mode)
            try:
                if os.access(exclude_path.parent, os.W_OK):
                    self.skipTest("filesystem does not enforce read-only directory permissions")
                started = run(["python3", "scripts/project_guard.py", "start", "fix", "permission"], repo)
            finally:
                exclude_path.parent.chmod(original_mode)

            self.assertEqual(2, started.returncode)
            self.assertIn("环境准备失败", started.stderr)
            self.assertFalse((Path(temp) / "worktrees/repo/fix-permission").exists())
            self.assertEqual("", run(["git", "branch", "--list", "fix/permission"], repo).stdout.strip())

            exclude_path.write_bytes(b"# valid prefix\n\xff\n")
            bad_encoding = run(["python3", "scripts/project_guard.py", "start", "fix", "bad-encoding"], repo)
            self.assertEqual(2, bad_encoding.returncode)
            self.assertIn("环境准备失败", bad_encoding.stderr)
            self.assertFalse((Path(temp) / "worktrees/repo/fix-bad-encoding").exists())
            self.assertEqual("", run(["git", "branch", "--list", "fix/bad-encoding"], repo).stdout.strip())


if __name__ == "__main__":
    unittest.main()
