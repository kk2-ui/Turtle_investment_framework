#!/usr/bin/env python3
"""batch_analyze.py — 年糕投资系统 批量分析脚本 (Phase 2.1)

从 portfolio.db watchlist 读取待分析股票，逐个调用 --unified。
支持断点续跑、进度追踪、失败重试。

Usage:
  python scripts/batch_analyze.py                    # 分析所有持仓未分析的
  python scripts/batch_analyze.py --all              # 分析所有关注股票
  python scripts/batch_analyze.py --stale            # 分析超30天未更新的
  python scripts/batch_analyze.py --code 00506.HK    # 分析单只
  python scripts/batch_analyze.py --dry-run          # 预览模式
  python scripts/batch_analyze.py --skip-existing    # 跳过已有分析的
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(_FRAMEWORK_DIR, "scripts")
sys.path.insert(0, _SCRIPTS_DIR)


def get_queue(all_stocks: bool = False, stale_only: bool = False,
              unanalyzed_only: bool = True, codes: list[str] | None = None,
              skip_existing: bool = True) -> list[dict[str, Any]]:
    """构建分析队列。"""
    from portfolio_db import get_db

    if codes:
        queue = [{"ts_code": c, "name": c, "reason": "手动指定"} for c in codes]
        return queue

    db = get_db()
    queue = []

    if unanalyzed_only and not all_stocks:
        # 持仓但未分析
        rows = db.execute("""
            SELECT w.ts_code, w.name FROM watchlist w
            WHERE w.current_hold > 0 AND w.ts_code NOT IN (SELECT ts_code FROM analysis)
            ORDER BY w.current_hold DESC
        """).fetchall()
        for r in rows:
            queue.append({"ts_code": r["ts_code"], "name": r["name"], "reason": "持仓未分析"})

    if all_stocks:
        rows = db.execute("""
            SELECT w.ts_code, w.name FROM watchlist w
            WHERE w.in_invest = 1
            ORDER BY w.current_hold DESC
        """).fetchall()
        for r in rows:
            ts = r["ts_code"]
            if skip_existing:
                ex = db.execute("SELECT 1 FROM analysis WHERE ts_code=?", (ts,)).fetchone()
                if ex: continue
            if not any(q["ts_code"] == ts for q in queue):
                queue.append({"ts_code": ts, "name": r["name"], "reason": "全部关注"})

    if stale_only:
        rows = db.execute("""
            SELECT a.ts_code, w.name FROM analysis a
            LEFT JOIN watchlist w ON a.ts_code = w.ts_code
            WHERE a.gg_ok = 1 AND a.analyzed_at < datetime('now', '-30 days')
            ORDER BY a.analyzed_at
        """).fetchall()
        for r in rows:
            ts = r["ts_code"]
            if not any(q["ts_code"] == ts for q in queue):
                queue.append({"ts_code": ts, "name": r["name"] or ts, "reason": "超30天未更新"})

    db.close()
    return queue


def run_batch(queue: list[dict], dry_run: bool = False) -> dict[str, Any]:
    """执行批量分析。"""
    total = len(queue)
    if total == 0:
        print("✅ 无待分析股票")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    print(f"\n{'='*60}")
    print(f"🏮 年糕批量分析 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   共 {total} 只待分析")
    if dry_run:
        print("   🔍 预览模式 — 不实际执行")
    print(f"{'='*60}\n")

    if dry_run:
        for i, q in enumerate(queue):
            print(f"  [{i+1}/{total}] {q['ts_code']:12s} {q['name'] or '?':10s} ({q['reason']})")
        return {"total": total, "success": 0, "failed": 0, "skipped": 0, "dry_run": True}

    success, failed, skipped = 0, 0, 0
    start_time = time.time()
    run_py = os.path.join(_SCRIPTS_DIR, "turtle_agent", "run.py")

    for i, q in enumerate(queue):
        ts = q["ts_code"]
        name = q.get("name", ts)
        reason = q.get("reason", "")
        elapsed_total = time.time() - start_time
        eta = (elapsed_total / (i + 1)) * (total - i - 1) if i > 0 else 0

        print(f"\n── [{i+1}/{total}] {ts} {name} ({reason}) "
              f"[{_fmt_time(elapsed_total)} / ETA {_fmt_time(eta)}] ──")

        try:
            result = subprocess.run(
                [sys.executable, run_py, "--code", ts, "--unified"],
                cwd=_FRAMEWORK_DIR,
                capture_output=False,
                timeout=3600,  # 1 hour max per stock
            )
            if result.returncode == 0:
                success += 1
                print(f"  ✅ {ts} 分析完成")
            else:
                failed += 1
                print(f"  ❌ {ts} 失败 (exit={result.returncode})")
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"  ⏰ {ts} 超时(>1h)")
        except KeyboardInterrupt:
            print(f"\n⏸️ 用户中断。已完成: {success} 失败: {failed} 剩余: {total - i}")
            break
        except Exception as e:
            failed += 1
            print(f"  ❌ {ts} 异常: {e}")

    total_elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏮 批量分析完成 · {_fmt_time(total_elapsed)}")
    print(f"   ✅ 成功: {success}  ❌ 失败: {failed}  ⏭️ 跳过: {skipped}")
    print(f"{'='*60}")

    return {"total": total, "success": success, "failed": failed, "skipped": skipped}


def _fmt_time(seconds: float) -> str:
    if seconds < 60: return f"{seconds:.0f}s"
    if seconds < 3600: return f"{seconds/60:.0f}m{seconds%60:.0f}s"
    return f"{seconds/3600:.0f}h{(seconds%3600)/60:.0f}m"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="年糕批量分析")
    ap.add_argument("--all", action="store_true", help="分析所有关注股票")
    ap.add_argument("--stale", action="store_true", help="仅分析超30天未更新的")
    ap.add_argument("--code", nargs="*", help="手动指定股票代码")
    ap.add_argument("--dry-run", action="store_true", help="预览模式，不实际执行")
    ap.add_argument("--no-skip", action="store_true", help="不跳过已有分析的股票")
    args = ap.parse_args()

    unanalyzed_only = not args.all and not args.stale and not args.code

    queue = get_queue(
        all_stocks=args.all,
        stale_only=args.stale,
        unanalyzed_only=unanalyzed_only,
        codes=args.code,
        skip_existing=not args.no_skip,
    )

    result = run_batch(queue, dry_run=args.dry_run)
    sys.exit(0 if result.get("failed", 0) == 0 else 1)


if __name__ == "__main__":
    main()
