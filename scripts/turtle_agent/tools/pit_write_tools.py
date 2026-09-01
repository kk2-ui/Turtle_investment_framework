"""Restricted report writer for one point-in-time research run.

The writer has no path parameter and is configured by the runner before an
agent starts.  A report can cite only source IDs that were actually admitted
and read through the ``PITSourcePackage`` boundary in the same run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.phase10_pit_runner import PITSourcePackage


_WRITER: "PITReportWriter | None" = None


@dataclass
class PITReportWriter:
    """Single-report sink confined to a fresh PIT output directory."""

    runner: PITSourcePackage
    output_dir: Path
    case_id: str
    experiment_id: str
    report_path: Path | None = None
    source_ids: list[str] | None = None
    section_markers: list[str] | None = None

    def __post_init__(self) -> None:
        self.output_dir = self.output_dir.expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _read_source_ids(self) -> set[str]:
        return {
            str(event.get("source_id") or "")
            for event in self.runner.attestation().get("read_audit", [])
            if event.get("allowed") is True and event.get("kind") == "SOURCE"
        }

    def _has_read_framework(self) -> bool:
        return any(
            event.get("allowed") is True and event.get("kind") == "FRAMEWORK"
            for event in self.runner.attestation().get("read_audit", [])
        )

    def write(
        self,
        report_markdown: str,
        source_ids: list[str],
        section_markers: list[str],
    ) -> dict[str, Any]:
        if self.report_path is not None:
            return {"written": False, "error": "pit_report_already_written"}
        body = str(report_markdown or "").strip()
        if len(body) < 240:
            return {"written": False, "error": "pit_report_too_short"}
        if not body.startswith("#"):
            return {"written": False, "error": "pit_report_requires_markdown_title"}
        if not self._has_read_framework():
            return {"written": False, "error": "pit_report_requires_framework_read"}
        normalized_sources = [str(item or "").strip() for item in source_ids]
        if not normalized_sources or any(not item for item in normalized_sources):
            return {"written": False, "error": "pit_report_requires_source_ids"}
        if len(set(normalized_sources)) != len(normalized_sources):
            return {"written": False, "error": "pit_report_source_ids_must_be_unique"}
        actually_read = self._read_source_ids()
        missing_reads = [item for item in normalized_sources if item not in actually_read]
        if missing_reads:
            return {
                "written": False,
                "error": "pit_report_source_not_read",
                "source_ids": missing_reads,
            }
        anchors = [item.strip() for item in re.findall(r"\[source:\s*([^\]]+)\]", body)]
        if "[source:" in body and len(anchors) != body.count("[source:"):
            return {"written": False, "error": "pit_report_source_anchor_invalid"}
        declared = set(normalized_sources)
        anchored = set(anchors)
        missing_anchors = sorted(declared - anchored)
        if missing_anchors:
            return {
                "written": False,
                "error": "pit_report_source_anchor_missing",
                "source_ids": missing_anchors,
            }
        undeclared_anchors = sorted(anchored - declared)
        if undeclared_anchors:
            return {
                "written": False,
                "error": "pit_report_source_anchor_not_declared",
                "source_ids": undeclared_anchors,
            }
        markers = [str(item or "").strip() for item in section_markers]
        required_markers = {
            "## Point-in-time scope",
            "## Evidence",
            "## Business and financial implications",
            "## Unknowns and monitoring",
        }
        if set(markers) != required_markers or not required_markers.issubset(set(body.splitlines())):
            return {"written": False, "error": "pit_report_required_sections_missing"}
        path = self.output_dir / "pit_writer_report.md"
        path.write_text(body + "\n", encoding="utf-8")
        self.report_path = path
        self.source_ids = normalized_sources
        self.section_markers = markers
        return {
            "written": True,
            "report_path": str(path),
            "source_ids": list(normalized_sources),
            "section_markers": list(markers),
            "case_id": self.case_id,
            "experiment_id": self.experiment_id,
        }

    def attestation(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.report_path is not None else "INCOMPLETE",
            "report_path": str(self.report_path) if self.report_path else "",
            "source_ids": list(self.source_ids or []),
            "section_markers": list(self.section_markers or []),
            "case_id": self.case_id,
            "experiment_id": self.experiment_id,
        }


def configure_pit_writer(
    runner: PITSourcePackage,
    *,
    output_dir: str | Path,
    case_id: str,
    experiment_id: str,
) -> None:
    """Bind one fresh output sink to the active PIT source package."""
    global _WRITER
    _WRITER = PITReportWriter(
        runner=runner,
        output_dir=Path(output_dir),
        case_id=case_id,
        experiment_id=experiment_id,
    )


def clear_pit_writer() -> None:
    """Drop process-local writer state between runs and tests."""
    global _WRITER
    _WRITER = None


def pit_writer_attestation() -> dict[str, Any]:
    """Return the write-side outcome without exposing a mutable path API."""
    if _WRITER is None:
        return {"status": "INCOMPLETE", "error": "pit_writer_not_configured"}
    return _WRITER.attestation()


def pit_write_report(
    report_markdown: str = "",
    source_ids: list[str] | None = None,
    section_markers: list[str] | None = None,
) -> dict[str, Any]:
    """Write the one PIT Markdown draft after its cited sources were read."""
    if _WRITER is None:
        return {"written": False, "error": "pit_writer_not_configured"}
    return _WRITER.write(
        report_markdown,
        list(source_ids or []),
        list(section_markers or []),
    )


pit_write_report._tool_meta = {
    "name": "pit_write_report",
    "description": (
        "写入本次PIT唯一Markdown草案。只能引用本运行已实际读取的source_id；"
        "没有文件路径、URL、结算或普通输出目录参数。"
    ),
    "parameters": {
        "report_markdown": {"type": "string", "description": "完整Markdown草案"},
        "source_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "正文中以[source: source_id]锚定且已读取的来源",
        },
        "section_markers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "四个必需PIT章节标题",
        },
    },
}  # type: ignore[attr-defined]
