#!/usr/bin/env python3
"""Install long-project governance files without overwriting by default."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import shutil
import subprocess
from pathlib import Path


def render(source: Path, target: Path, values: dict[str, str], force: bool) -> None:
    if target.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {target}")
    text = source.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--type", choices=["python", "android", "generic"], default="generic")
    parser.add_argument("--objective", default="维护一个目标明确、证据可复核且可持续演进的项目。")
    parser.add_argument("--full-command", help="generic 项目的真实 full 验证命令（作为一个带引号的字符串）")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    root_result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if root_result.returncode:
        raise SystemExit("--repo must be a Git repository")
    if Path(root_result.stdout.strip()).resolve() != repo:
        raise SystemExit("--repo must be the Git repository root")
    if args.type == "generic" and not args.full_command:
        raise SystemExit("generic projects require --full-command with a real test command")
    generic_full_command = shlex.split(args.full_command) if args.full_command else None

    skill = Path(__file__).resolve().parents[1]
    assets = skill / "assets"
    guard_rel = Path("tools/project_guard.py") if args.type == "android" else Path("scripts/project_guard.py")
    python = ".venv/bin/python" if args.type == "python" and (repo / ".venv/bin/python").exists() else "python3"
    blockers = "盘点现有工作树与远端保护状态后更新。"
    values = {
        "PROJECT_NAME": args.name,
        "DATE": dt.date.today().isoformat(),
        "OBJECTIVE": args.objective,
        "BLOCKERS": blockers,
        "PYTHON": python,
        "GUARD_PATH": str(guard_rel),
    }

    targets = [
        repo / "GOALS.md",
        repo / "progress-dashboard.html",
        repo / "docs/DEVELOPMENT_STANDARD.md",
        repo / ".project/.gitignore",
        repo / ".githooks/pre-commit",
        repo / ".githooks/pre-push",
        repo / guard_rel,
        repo / ".project-governance.json",
    ]
    existing = [str(path) for path in targets if path.exists()]
    if existing and not args.force:
        raise SystemExit("refusing to overwrite: " + ", ".join(existing))

    render(assets / "GOALS.template.md", repo / "GOALS.md", values, args.force)
    render(assets / "progress-dashboard.template", repo / "progress-dashboard.html", values, args.force)
    render(skill / "references/development-standard.md", repo / "docs/DEVELOPMENT_STANDARD.md", values, args.force)
    project_ignore = repo / ".project/.gitignore"
    project_ignore.parent.mkdir(parents=True, exist_ok=True)
    project_ignore.write_text("evidence/\n", encoding="utf-8")
    root_ignore = repo / ".gitignore"
    ignore_text = root_ignore.read_text(encoding="utf-8") if root_ignore.exists() else ""
    dashboard_exception = "!progress-dashboard.html"
    if dashboard_exception not in ignore_text.splitlines():
        separator = "" if not ignore_text or ignore_text.endswith("\n") else "\n"
        root_ignore.write_text(ignore_text + separator + dashboard_exception + "\n", encoding="utf-8")
    render(assets / "pre-commit.template", repo / ".githooks/pre-commit", values, args.force)
    render(assets / "pre-push.template", repo / ".githooks/pre-push", values, args.force)
    (repo / guard_rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(assets / "project_guard.py", repo / guard_rel)

    profiles = {
        "android": {
            "docs": [["python3", str(guard_rel), "self-test"]],
            "fast": [["./gradlew", ":app:testDebugUnitTest"]],
            "full": [["./gradlew", ":app:testDebugUnitTest", ":app:lintDebug", ":app:assembleDebug"]],
        },
        "python": {
            "docs": [[python, str(guard_rel), "self-test"]],
            "fast": [[python, "-m", "pytest", "-q"]],
            "full": [[python, "-m", "pytest", "-q"]],
        },
        "generic": {
            "docs": [["python3", str(guard_rel), "self-test"]],
            "fast": [generic_full_command],
            "full": [generic_full_command],
        },
    }[args.type]
    config = {
        "schema_version": 1,
        "project_name": args.name,
        "protected_branches": ["main", "master"],
        "branch_prefixes": ["feat", "fix", "docs", "refactor", "test", "chore", "hotfix"],
        "worktree_root": "../worktrees",
        "profile_order": ["docs", "fast", "full"],
        "required_profile": "full",
        "profiles": profiles,
    }
    config_path = repo / ".project-governance.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for executable in [repo / guard_rel, repo / ".githooks/pre-commit", repo / ".githooks/pre-push"]:
        executable.chmod(executable.stat().st_mode | 0o111)
    print(f"Installed governance in {repo}; inspect profiles before enabling hooks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
