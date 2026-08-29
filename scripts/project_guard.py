#!/usr/bin/env python3
"""Local worktree, branch, verification-evidence, and merge-readiness gate."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import subprocess
import sys
from pathlib import Path


CONFIG_NAME = ".project-governance.json"
EVIDENCE_PATH = Path(".project/evidence/latest.json")


def run(command: list[str], cwd: Path, *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    expanded: list[str] = []
    for value in command:
        if any(token in value for token in "*?["):
            matches = sorted(glob.glob(str(cwd / value)))
            if not matches:
                raise RuntimeError(f"命令通配符没有匹配文件：{value}")
            expanded.extend(str(Path(match).relative_to(cwd)) for match in matches)
        else:
            expanded.append(value)
    return subprocess.run(expanded, cwd=cwd, text=True, capture_output=capture, check=False)


def git(root: Path, *args: str, check: bool = True) -> str:
    result = run(["git", *args], root)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def find_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    if result.returncode != 0:
        raise RuntimeError("当前目录不在 Git 仓库中")
    return Path(result.stdout.strip()).resolve()


def load_config(root: Path) -> dict:
    path = root / CONFIG_NAME
    if not path.exists():
        raise RuntimeError(f"缺少 {CONFIG_NAME}")
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"project_name", "protected_branches", "branch_prefixes", "profiles", "required_profile"}
    missing = sorted(required - config.keys())
    if missing:
        raise RuntimeError(f"治理配置缺少字段：{', '.join(missing)}")
    if config["required_profile"] not in config["profiles"]:
        raise RuntimeError("required_profile 不存在于 profiles")
    return config


def branch(root: Path) -> str:
    value = git(root, "branch", "--show-current")
    if not value:
        raise RuntimeError("不允许 detached HEAD 开发")
    return value


def is_dirty(root: Path) -> bool:
    return bool(git(root, "status", "--porcelain"))


def ensure_minimum_base(root: Path, config: dict, revision: str) -> str | None:
    required = str(config.get("minimum_base_commit", "")).strip()
    if not required:
        return None
    resolved = git(root, "rev-parse", "--verify", f"{required}^{{commit}}", check=False)
    if not resolved:
        raise RuntimeError(f"治理配置引用了不存在的 minimum_base_commit：{required}")
    result = run(["git", "merge-base", "--is-ancestor", resolved, revision], root)
    if result.returncode != 0:
        reason = str(config.get("minimum_base_reason", "统一项目基线")).strip()
        raise RuntimeError(
            f"{revision} 未继承要求的基线 {resolved[:12]}（{reason}）；"
            "请把增量迁移到从当前 main 创建的新 linked worktree"
        )
    return resolved


def ensure_feature_context(root: Path, config: dict, *, allow_dirty: bool) -> str:
    current = branch(root)
    if current in config["protected_branches"]:
        raise RuntimeError(f"禁止直接在受保护分支 {current} 开发或提交")
    if not any(current.startswith(f"{prefix}/") for prefix in config["branch_prefixes"]):
        allowed = ", ".join(f"{prefix}/" for prefix in config["branch_prefixes"])
        raise RuntimeError(f"分支名不合规；必须使用：{allowed}")
    if not (root / ".git").is_file():
        raise RuntimeError("当前不是 linked worktree；请用 project_guard.py start 创建独立工作区")
    ensure_minimum_base(root, config, "HEAD")
    if not allow_dirty and is_dirty(root):
        raise RuntimeError("验证或合入检查要求工作树干净；请先提交当前改动")
    return current


def evidence_file(root: Path) -> Path:
    return root / EVIDENCE_PATH


def write_evidence(root: Path, payload: dict) -> None:
    path = evidence_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def cmd_self_test(root: Path, config: dict, _args: argparse.Namespace) -> int:
    git(root, "rev-parse", "--git-dir")
    for name, commands in config["profiles"].items():
        if not isinstance(commands, list) or not all(isinstance(item, list) and item for item in commands):
            raise RuntimeError(f"验证档 {name} 必须是非空命令数组的列表")
    print(f"OK: {config['project_name']} 治理配置有效")
    return 0


def cmd_preflight(root: Path, config: dict, args: argparse.Namespace) -> int:
    current = ensure_feature_context(root, config, allow_dirty=args.allow_dirty)
    print(f"OK: {current} 位于独立 worktree")
    return 0


def cmd_start(root: Path, config: dict, args: argparse.Namespace) -> int:
    current = branch(root)
    if current not in config["protected_branches"]:
        raise RuntimeError("请从主工作区的受保护分支启动新 worktree")
    if is_dirty(root):
        raise RuntimeError("主工作区存在未提交改动；先完成基线审计或建立安全快照")
    if args.kind not in config["branch_prefixes"]:
        raise RuntimeError(f"不允许的分支类型：{args.kind}")
    if args.base not in config["protected_branches"]:
        raise RuntimeError("新 worktree 的 base 必须是受保护集成分支")
    base_commit = git(root, "rev-parse", "--verify", args.base)
    ensure_minimum_base(root, config, args.base)
    slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
    if not slug:
        raise RuntimeError("slug 必须包含字母、数字或连字符")
    new_branch = f"{args.kind}/{slug}"
    worktree_base = (root / config.get("worktree_root", "../worktrees")).resolve()
    destination = worktree_base / root.name / new_branch.replace("/", "-")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = run(["git", "worktree", "add", "-b", new_branch, str(destination), args.base], root, capture=False)
    if result.returncode != 0:
        return result.returncode
    shared_python_env = root / ".venv"
    worktree_python_env = destination / ".venv"
    if shared_python_env.is_dir() and not worktree_python_env.exists():
        temp_exclude = None
        try:
            worktree_python_env.symlink_to(shared_python_env, target_is_directory=True)
            repository_exclude = Path(git(destination, "rev-parse", "--git-path", "info/exclude"))
            if not repository_exclude.is_absolute():
                repository_exclude = destination / repository_exclude
            existing_excludes = repository_exclude.read_text(encoding="utf-8") if repository_exclude.exists() else ""
            if ".venv" not in existing_excludes.splitlines():
                repository_exclude.parent.mkdir(parents=True, exist_ok=True)
                separator = "" if not existing_excludes or existing_excludes.endswith("\n") else "\n"
                temp_exclude = repository_exclude.with_suffix(".tmp")
                temp_exclude.write_text(existing_excludes + separator + ".venv\n", encoding="utf-8")
                if repository_exclude.exists():
                    temp_exclude.chmod(repository_exclude.stat().st_mode & 0o777)
                temp_exclude.replace(repository_exclude)
            print(f"linked-env=.venv -> {shared_python_env}")
        except (OSError, RuntimeError, UnicodeError) as exc:
            if temp_exclude is not None and temp_exclude.exists():
                try:
                    temp_exclude.unlink()
                except OSError:
                    pass
            cleanup = run(["git", "worktree", "remove", "--force", str(destination)], root)
            branch_cleanup = run(["git", "branch", "-D", new_branch], root)
            cleanup_note = ""
            if cleanup.returncode or branch_cleanup.returncode:
                cleanup_note = "; 清理失败，请检查新建 worktree/分支"
            raise RuntimeError(f"新 worktree 环境准备失败：{exc}{cleanup_note}") from exc
    print(f"base={args.base}@{base_commit[:12]}")
    print(destination)
    return 0


def cmd_verify(root: Path, config: dict, args: argparse.Namespace) -> int:
    current = ensure_feature_context(root, config, allow_dirty=False)
    commands = config["profiles"].get(args.profile)
    if commands is None:
        raise RuntimeError(f"未知验证档：{args.profile}")
    payload = {
        "schema_version": 1,
        "project": config["project_name"],
        "branch": current,
        "commit": git(root, "rev-parse", "HEAD"),
        "base_branch": next((name for name in config["protected_branches"] if git(root, "rev-parse", "--verify", name, check=False)), None),
        "minimum_base_commit": ensure_minimum_base(root, config, "HEAD"),
        "profile": args.profile,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commands": [],
        "success": False,
    }
    for command in commands:
        started = dt.datetime.now(dt.timezone.utc)
        print(f"$ {' '.join(command)}", flush=True)
        result = run(command, root, capture=False)
        payload["commands"].append({
            "command": command,
            "exit_code": result.returncode,
            "duration_seconds": round((dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 3),
        })
        if result.returncode != 0:
            payload["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            write_evidence(root, payload)
            return result.returncode
    payload["success"] = True
    payload["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write_evidence(root, payload)
    print(f"OK: 验证证据已绑定 {payload['commit'][:12]}")
    return 0


def cmd_merge_check(root: Path, config: dict, _args: argparse.Namespace) -> int:
    current = ensure_feature_context(root, config, allow_dirty=False)
    path = evidence_file(root)
    if not path.exists():
        raise RuntimeError("缺少验证证据；先运行 verify")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    head = git(root, "rev-parse", "HEAD")
    if not evidence.get("success") or evidence.get("commit") != head or evidence.get("branch") != current:
        raise RuntimeError("验证失败或证据未绑定当前分支的当前 commit")
    order = config.get("profile_order", list(config["profiles"]))
    required = config["required_profile"]
    actual = evidence.get("profile")
    if actual not in order or order.index(actual) < order.index(required):
        raise RuntimeError(f"合入 main 至少需要 {required} 验证档，当前为 {actual}")
    print(f"READY: {current}@{head[:12]} 已具备合入证据")
    return 0


def cmd_baseline_check(root: Path, config: dict, args: argparse.Namespace) -> int:
    required = ensure_minimum_base(root, config, args.revision)
    if required is None:
        print("OK: 当前项目未配置 minimum_base_commit")
    else:
        resolved = git(root, "rev-parse", "--verify", args.revision)
        print(f"OK: {args.revision}@{resolved[:12]} 已继承统一基线 {required[:12]}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--allow-dirty", action="store_true")
    start = sub.add_parser("start")
    start.add_argument("kind")
    start.add_argument("slug")
    start.add_argument("--base", default="main")
    verify = sub.add_parser("verify")
    verify.add_argument("profile")
    sub.add_parser("merge-check")
    baseline_check = sub.add_parser("baseline-check")
    baseline_check.add_argument("revision", nargs="?", default="HEAD")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        root = find_root()
        config = load_config(root)
        handlers = {
            "self-test": cmd_self_test,
            "preflight": cmd_preflight,
            "start": cmd_start,
            "verify": cmd_verify,
            "merge-check": cmd_merge_check,
            "baseline-check": cmd_baseline_check,
        }
        return handlers[args.command](root, config, args)
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
