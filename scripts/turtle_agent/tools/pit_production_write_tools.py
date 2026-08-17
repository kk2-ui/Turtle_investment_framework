"""Output-bound V3 write facade for a PIT production-freeze run.

The ordinary write tools are useful validators, but their public API accepts
an ``output_dir``.  A point-in-time writer must never select a directory, so
this facade binds each supported tool to the fresh run output before exposing
it to the model.  It intentionally exposes no filesystem, Web, market-data,
or ordinary read entrypoint.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from turtle_agent.tools import write_tools


_OUTPUT_DIR: str = ""
_CODE: str = ""


def configure_pit_production_writer(*, output_dir: str | Path, code: str) -> None:
    global _OUTPUT_DIR, _CODE
    _OUTPUT_DIR = str(Path(output_dir).expanduser().resolve())
    _CODE = str(code or "").strip()


def clear_pit_production_writer() -> None:
    global _OUTPUT_DIR, _CODE
    _OUTPUT_DIR = ""
    _CODE = ""


def _bound_output() -> str:
    if not _OUTPUT_DIR:
        raise RuntimeError("PIT production writer is not configured")
    return _OUTPUT_DIR


def _bind(name: str) -> Callable[..., Any]:
    source = getattr(write_tools, name)

    def bound(**kwargs: Any) -> Any:
        if "output_dir" in kwargs:
            raise RuntimeError("PIT production writer does not accept output_dir")
        return source(output_dir=_bound_output(), **kwargs)

    meta = deepcopy(getattr(source, "_tool_meta"))
    meta["name"] = "pit_" + name
    meta["parameters"].pop("output_dir", None)
    bound.__name__ = "pit_" + name
    bound.__doc__ = source.__doc__
    bound._tool_meta = meta  # type: ignore[attr-defined]
    return bound


def pit_assemble_report(*, company_name: str = "") -> dict[str, Any]:
    """Assemble only through the production report exit, never validation-only."""
    if not _CODE:
        raise RuntimeError("PIT production writer is not configured")
    return write_tools.assemble_report(
        output_dir=_bound_output(),
        company_name=str(company_name or _CODE),
        ts_code=_CODE,
        validation_only=False,
    )


pit_assemble_report._tool_meta = {
    "name": "pit_assemble_report",
    "description": "组装PIT完整报告并执行既有完成契约、V3和发布快照；禁止validation-only和任意输出路径。",
    "parameters": {"company_name": {"type": "string", "optional": True}},
}  # type: ignore[attr-defined]


for _name in (
    "verify_official_fact",
    "write_chapter",
    "read_chapter",
    "audit_chapter",
    "write_decision_manifest",
    "write_decision_ledger",
    "write_claim_evidence_ledger",
    "write_valuation_model_ledger",
    "write_thesis_test_ledger",
    "write_decisive_question_findings",
    "write_insight_ledger",
    "write_judgment_review",
):
    globals()["pit_" + _name] = _bind(_name)

