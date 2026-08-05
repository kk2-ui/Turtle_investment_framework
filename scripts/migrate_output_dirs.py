#!/usr/bin/env python3
"""migrate_output_dirs.py — 将旧版 output/ 目录结构迁移至 v13 子目录布局。

迁移规则（每只股票目录）：
  _ch*.md              → chapters/
  *_分析报告*.md        → reports/
  *_分析报告*.html      → reports/
  _run_*.log           → _logs/
  *.bak                → _logs/
  _d*_backup/          → _logs/（整目录移动）

不动（intentionally skipped）：
  *.json               — 被多处脚本引用，路径风险高
  *.pdf / *.xls*       — 年报原件
  *_年报*.md           — 年报摘要
  history/             — 已归档报告
  chapters/ reports/ _logs/  — 目标目录本身

用法：
  python scripts/migrate_output_dirs.py              # dry-run（只打印）
  python scripts/migrate_output_dirs.py --apply      # 真正执行
  python scripts/migrate_output_dirs.py --stock 00506.HK  # 仅处理一只
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

_FRAMEWORK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")

# ── 常量（与 _version.py 保持一致）───────────────────────────────
try:
    _scripts = os.path.join(_FRAMEWORK_DIR, "scripts")
    if _scripts not in sys.path:
        sys.path.insert(0, _scripts)
    from turtle_agent._version import CHAPTERS_SUBDIR, REPORTS_SUBDIR
except ImportError:
    CHAPTERS_SUBDIR = "chapters"
    REPORTS_SUBDIR  = "reports"

LOGS_SUBDIR = "_logs"

# ── 跳过目标目录本身以及不需要处理的目录 ─────────────────────────
_SKIP_DIRS = {"history", CHAPTERS_SUBDIR, REPORTS_SUBDIR, LOGS_SUBDIR}


def _is_chapter(name: str) -> bool:
    return name.startswith("_ch") and name.endswith(".md")


def _is_report(name: str) -> bool:
    return "分析报告" in name and name.endswith((".md", ".html"))


def _is_log(name: str) -> bool:
    return (name.startswith("_run_") and name.endswith(".log")) or name.endswith(".bak")


def _is_backup_dir(name: str) -> bool:
    return name.startswith("_d") and name.endswith("_backup") and "_backup" in name


def _classify(name: str) -> str | None:
    """返回目标子目录名，或 None 表示不移动。"""
    if _is_chapter(name):   return CHAPTERS_SUBDIR
    if _is_report(name):    return REPORTS_SUBDIR
    if _is_log(name):       return LOGS_SUBDIR
    return None


def migrate_stock_dir(stock_path: str, apply: bool) -> list[str]:
    """迁移单个股票目录，返回操作列表（用于打印）。"""
    ops: list[str] = []

    # ── 文件 ─────────────────────────────────────────────────
    for fname in os.listdir(stock_path):
        src = os.path.join(stock_path, fname)
        if os.path.isdir(src):
            continue  # 目录单独处理
        target_sub = _classify(fname)
        if target_sub is None:
            continue
        dst_dir = os.path.join(stock_path, target_sub)
        dst = os.path.join(dst_dir, fname)
        if os.path.exists(dst):
            ops.append(f"  SKIP   (already exists) {target_sub}/{fname}")
            continue
        ops.append(f"  MOVE   {fname}  →  {target_sub}/{fname}")
        if apply:
            os.makedirs(dst_dir, exist_ok=True)
            shutil.move(src, dst)

    # ── _d*_backup/ 目录 → _logs/ ───────────────────────────
    for dname in os.listdir(stock_path):
        src = os.path.join(stock_path, dname)
        if not os.path.isdir(src):
            continue
        if dname in _SKIP_DIRS:
            continue
        if not _is_backup_dir(dname):
            continue
        dst_dir = os.path.join(stock_path, LOGS_SUBDIR)
        dst = os.path.join(dst_dir, dname)
        if os.path.exists(dst):
            ops.append(f"  SKIP   (already exists) {LOGS_SUBDIR}/{dname}/")
            continue
        ops.append(f"  MOVEDIR {dname}/  →  {LOGS_SUBDIR}/{dname}/")
        if apply:
            os.makedirs(dst_dir, exist_ok=True)
            shutil.move(src, dst)

    return ops


def run(output_dir: str, apply: bool, stock_filter: str | None) -> None:
    if not os.path.isdir(output_dir):
        print(f"[错误] output 目录不存在: {output_dir}")
        sys.exit(1)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[migrate_output_dirs] 模式: {mode}  output: {output_dir}")
    if not apply:
        print("  (加 --apply 以真正执行移动操作)\n")

    total_ops = 0
    for stock_dir in sorted(os.listdir(output_dir)):
        stock_path = os.path.join(output_dir, stock_dir)
        if not os.path.isdir(stock_path):
            continue
        if stock_filter:
            # 支持 "00506" 或 "00506.HK" 两种写法
            code_norm = stock_filter.replace(".", "_").split("_")[0]
            if not stock_dir.startswith(code_norm):
                continue

        ops = migrate_stock_dir(stock_path, apply=apply)
        if ops:
            print(f"\n📁 {stock_dir}/")
            for op in ops:
                print(op)
            total_ops += len(ops)

    print(f"\n{'✅ 完成' if apply else '📋 预览完毕'}，共 {total_ops} 项操作。")
    if not apply and total_ops:
        print("运行 --apply 以执行上述移动。")


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移 output/ 目录至 v13 子目录布局")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认仅 dry-run）")
    parser.add_argument("--output", default=_OUTPUT_DIR, help="output 根目录")
    parser.add_argument("--stock", default=None, help="仅处理指定股票（如 00506 或 00506.HK）")
    args = parser.parse_args()
    run(args.output, apply=args.apply, stock_filter=args.stock)


if __name__ == "__main__":
    main()
