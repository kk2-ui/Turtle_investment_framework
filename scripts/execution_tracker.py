#!/usr/bin/env python3
"""execution_tracker.py — V10：执行追踪模块。

追踪分章节写作管线的运行指标，输出 structured run_summary.json。

从 Dayu 的 execution_summary_builder.py 裁剪而来。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models import ChapterStatus


@dataclass
class ChapterRecord:
    """单章执行记录。

    Args:
        index: 章节序号。
        title: 章节标题。
        status: 最终状态。
        retry_count: 重试次数。
        audit_passed: 是否通过审计。
        evidence_count: 证据项数量。
        content_chars: 内容字符数。
        elapsed_ms: 耗时（毫秒）。
        error: 错误信息（如有）。
    """

    index: int
    title: str
    status: str
    retry_count: int = 0
    audit_passed: bool = False
    evidence_count: int = 0
    content_chars: int = 0
    elapsed_ms: int = 0
    error: str = ""


@dataclass
class RunSummary:
    """管线运行摘要。

    Args:
        ts_code: 股票代码。
        company_name: 公司名称。
        started_at: 开始时间。
        finished_at: 结束时间。
        total_elapsed_ms: 总耗时。
        chapters: 各章记录列表。
        template: 使用的模板路径。
        audit_enabled: 是否启用了审计。
        max_workers: 并行 worker 数。
    """

    ts_code: str
    company_name: str
    started_at: str
    finished_at: str
    total_elapsed_ms: int
    chapters: list[ChapterRecord] = field(default_factory=list)
    template: str = ""
    audit_enabled: bool = False
    max_workers: int = 4

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.chapters if c.status.lower() == "passed")

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.chapters if c.status.lower() == "failed")

    @property
    def total_evidence(self) -> int:
        return sum(c.evidence_count for c in self.chapters)

    @property
    def total_retries(self) -> int:
        return sum(c.retry_count for c in self.chapters)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts_code": self.ts_code,
            "company_name": self.company_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_elapsed_ms": self.total_elapsed_ms,
            "total_elapsed_s": round(self.total_elapsed_ms / 1000, 1),
            "chapters": [{"index": c.index, "title": c.title, "status": c.status,
                          "retry_count": c.retry_count, "audit_passed": c.audit_passed,
                          "evidence_count": c.evidence_count,
                          "content_chars": c.content_chars,
                          "elapsed_ms": c.elapsed_ms, "error": c.error}
                         for c in self.chapters],
            "summary": {
                "total": len(self.chapters),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "total_evidence": self.total_evidence,
                "total_retries": self.total_retries,
            },
            "config": {
                "template": self.template,
                "audit_enabled": self.audit_enabled,
                "max_workers": self.max_workers,
            },
        }


class ExecutionTracker:
    """执行追踪器。

    在管线运行期间记录各章执行数据，最终生成 run_summary.json。
    """

    def __init__(
        self,
        ts_code: str,
        company_name: str = "",
        template: str = "",
        audit_enabled: bool = False,
        max_workers: int = 4,
    ):
        """初始化追踪器。

        Args:
            ts_code: 股票代码。
            company_name: 公司名称。
            template: 模板路径。
            audit_enabled: 审计是否启用。
            max_workers: 并行 worker 数。
        """
        self.summary = RunSummary(
            ts_code=ts_code,
            company_name=company_name,
            started_at=datetime.now().isoformat(),
            finished_at="",
            total_elapsed_ms=0,
            template=template,
            audit_enabled=audit_enabled,
            max_workers=max_workers,
        )
        self._start_time = time.time()
        self._chapter_timers: dict[int, float] = {}

    def start_chapter(self, index: int):
        """记录章节开始执行的时间。

        Args:
            index: 章节序号。
        """
        self._chapter_timers[index] = time.time()

    def record_chapter(
        self,
        index: int,
        title: str,
        status: ChapterStatus | str,
        retry_count: int = 0,
        audit_passed: bool = False,
        evidence_count: int = 0,
        content_chars: int = 0,
        error: str = "",
    ):
        """记录章节执行结果。

        Args:
            index: 章节序号。
            title: 章节标题。
            status: 最终状态。
            retry_count: 重试次数。
            audit_passed: 审计是否通过。
            evidence_count: 证据项数量。
            content_chars: 内容字符数。
            error: 错误信息。
        """
        start = self._chapter_timers.get(index, self._start_time)
        elapsed = int((time.time() - start) * 1000)

        status_str = status.value if isinstance(status, ChapterStatus) else str(status)

        self.summary.chapters.append(ChapterRecord(
            index=index,
            title=title,
            status=status_str,
            retry_count=retry_count,
            audit_passed=audit_passed,
            evidence_count=evidence_count,
            content_chars=content_chars,
            elapsed_ms=elapsed,
            error=error,
        ))

    def finish(self, output_dir: str) -> str:
        """完成追踪，写入 run_summary.json。

        Args:
            output_dir: 输出目录路径。

        Returns:
            run_summary.json 的文件路径。
        """
        self.summary.finished_at = datetime.now().isoformat()
        self.summary.total_elapsed_ms = int((time.time() - self._start_time) * 1000)

        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, "run_summary.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.summary.to_dict(), f, indent=2, ensure_ascii=False)

        return out_path

    def print_summary(self):
        """打印运行摘要到控制台。"""
        s = self.summary
        print(f"\n{'='*50}")
        print(f"📊 运行摘要: {s.company_name} ({s.ts_code})")
        print(f"{'='*50}")
        print(f"  章节: {s.passed_count}/{len(s.chapters)} 通过, {s.failed_count} 失败")
        print(f"  证据: {s.total_evidence} 项")
        print(f"  重试: {s.total_retries} 次")
        print(f"  耗时: {s.total_elapsed_ms/1000:.1f}s")
        print(f"  配置: template={os.path.basename(s.template)}, audit={s.audit_enabled}, workers={s.max_workers}")
        print(f"{'='*50}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="显示或生成运行摘要")
    ap.add_argument("--show", "-s", help="显示 run_summary.json")
    ap.add_argument("--code", help="股票代码（生成示例摘要）")
    args = ap.parse_args()

    if args.show:
        if not os.path.exists(args.show):
            print(f"ERROR: 文件不存在: {args.show}", file=sys.stderr)
            sys.exit(1)
        with open(args.show, encoding="utf-8") as f:
            data = json.load(f)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.code:
        tracker = ExecutionTracker(ts_code=args.code, company_name=args.code)
        tracker.start_chapter(1)
        tracker.record_chapter(1, "报告元信息", "PASSED", evidence_count=3, content_chars=500)
        tracker.record_chapter(2, "Executive Summary", "PASSED", content_chars=300)
        tracker.finish("/tmp")
        tracker.print_summary()
        sys.exit(0)

    print("Usage: --show run_summary.json | --code CODE")
