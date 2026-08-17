"""Output-bound V3 write facade for a PIT production-freeze run.

The ordinary write tools are useful validators, but their public API accepts
an ``output_dir``.  A point-in-time writer must never select a directory, so
this facade binds each supported tool to the fresh run output before exposing
it to the model.  It intentionally exposes no filesystem, Web, market-data,
or ordinary read entrypoint.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Callable

from turtle_agent.tools import read_tools, write_tools


_OUTPUT_DIR: str = ""
_CODE: str = ""
_RUN_ID: str = ""
_PIT_RUNNER: Any = None


def configure_pit_production_writer(
    *, output_dir: str | Path, code: str, run_id: str, pit_runner: Any,
) -> None:
    global _OUTPUT_DIR, _CODE, _RUN_ID, _PIT_RUNNER
    _OUTPUT_DIR = str(Path(output_dir).expanduser().resolve())
    _CODE = str(code or "").strip()
    _RUN_ID = str(run_id or "").strip()
    _PIT_RUNNER = pit_runner


def clear_pit_production_writer() -> None:
    global _OUTPUT_DIR, _CODE, _RUN_ID, _PIT_RUNNER
    _OUTPUT_DIR = ""
    _CODE = ""
    _RUN_ID = ""
    _PIT_RUNNER = None


def _bound_output() -> str:
    if not _OUTPUT_DIR:
        raise RuntimeError("PIT production writer is not configured")
    return _OUTPUT_DIR


def _read_source_ids() -> set[str]:
    if _PIT_RUNNER is None:
        raise RuntimeError("PIT production writer is not bound to a source runner")
    attestation = _PIT_RUNNER.attestation()
    return {
        str(event.get("source_id") or "").strip()
        for event in attestation.get("read_audit", [])
        if event.get("allowed") is True and event.get("kind") == "SOURCE" and event.get("source_id")
    }


def _validate_source_anchors(content: Any) -> set[str]:
    anchors = {
        source_id.strip()
        for item in re.findall(
            r"\[(?:table-)?source:\s*([^\]]+)\]", str(content or ""), flags=re.IGNORECASE,
        )
        for source_id in item.split("|")
        if source_id.strip()
    }
    unexpected = sorted(anchors - _read_source_ids())
    if unexpected:
        raise RuntimeError(
            "PIT章节包含未在本次运行实际读取的 source anchor: " + ", ".join(unexpected)
        )
    return anchors


def _chapter_source_anchor_ids() -> set[str]:
    chapters = Path(_bound_output()) / write_tools.CHAPTERS_SUBDIR
    anchors: set[str] = set()
    for path in sorted(chapters.glob("_ch*.md")):
        anchors.update(_validate_source_anchors(path.read_text(encoding="utf-8")))
    return anchors


def production_source_anchor_ids() -> list[str]:
    """Return the exact source anchors in the current production chapters."""
    return sorted(_chapter_source_anchor_ids())


def _refresh_pit_v3_prerequisites() -> dict[str, Any]:
    """Refresh only deterministic V3 prerequisites from admitted report-local evidence.

    The ordinary pipeline prepares these artifacts before invoking its writer.
    PIT documents do not exist in the report workspace until an allowed source
    was read, and verified facts arrive one at a time.  Rebuilding from the
    existing PIT document manifest keeps that normal ordering without scanning
    the source package or reaching any ordinary data, price, Web, or database
    entrypoint.
    """
    output = Path(_bound_output())
    manifest_path = output / "document_manifest.json"
    facts_path = output / "fact_observations.json"
    if not manifest_path.is_file() or not facts_path.is_file():
        return {"state": "WAITING_FOR_VERIFIED_PIT_FACT"}
    try:
        from scripts.build_report_context import build_verified_context
        from scripts.valuation_routing import build_company_archetype, build_valuation_route
        from scripts.decisive_question import refresh_decisive_question_plan
        from scripts.computation_evidence import build_calculation_observations
    except ModuleNotFoundError:
        from build_report_context import build_verified_context
        from valuation_routing import build_company_archetype, build_valuation_route
        from decisive_question import refresh_decisive_question_plan
        from computation_evidence import build_calculation_observations
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    context = build_verified_context(output, manifest, facts, persist=True)
    archetype = build_company_archetype(output, persist=True)
    route = build_valuation_route(output, archetype, persist=True)
    decisive = refresh_decisive_question_plan(output, run_id=_RUN_ID or None, enforced=True)
    calculations = build_calculation_observations(output, persist=True)
    return {
        "state": "REFRESHED",
        "official_evidence_state": (context.get("validation") or {}).get("state"),
        "valuation_route_state": (route.get("validation") or {}).get("state"),
        "decisive_question_state": ((decisive.get("plan") or {}).get("validation") or {}).get("state"),
        "calculation_state": (calculations.get("validation") or {}).get("state"),
    }


def _bind(name: str) -> Callable[..., Any]:
    source = getattr(write_tools, name)

    def bound(**kwargs: Any) -> Any:
        if "output_dir" in kwargs:
            raise RuntimeError("PIT production writer does not accept output_dir")
        if name == "write_chapter":
            _validate_source_anchors(kwargs.get("content"))
        result = source(output_dir=_bound_output(), **kwargs)
        if name == "verify_official_fact" and result.get("verified") is True:
            result["pit_v3_prerequisites"] = _refresh_pit_v3_prerequisites()
        return result

    meta = deepcopy(getattr(source, "_tool_meta"))
    meta["name"] = "pit_" + name
    meta["parameters"].pop("output_dir", None)
    bound.__name__ = "pit_" + name
    bound.__doc__ = source.__doc__
    bound._tool_meta = meta  # type: ignore[attr-defined]
    return bound


def _bind_contract_read(name: str) -> Callable[..., Any]:
    source = getattr(read_tools, name)

    def bound(**kwargs: Any) -> Any:
        if "output_dir" in kwargs:
            raise RuntimeError("PIT production reader does not accept output_dir")
        if name == "read_report_contract_pack":
            if "template_path" in kwargs:
                raise RuntimeError("PIT production reader does not accept template_path")
            # This is a fixed repository framework contract, not a model-chosen file.
            kwargs["template_path"] = "templates/report_template_v12.md"
        return source(output_dir=_bound_output(), **kwargs)

    meta = deepcopy(getattr(source, "_tool_meta"))
    meta["name"] = "pit_" + name
    meta["parameters"].pop("output_dir", None)
    if name == "read_report_contract_pack":
        meta["parameters"].pop("template_path", None)
    bound.__name__ = "pit_" + name
    bound.__doc__ = source.__doc__
    bound._tool_meta = meta  # type: ignore[attr-defined]
    return bound


def pit_assemble_report(*, company_name: str = "") -> dict[str, Any]:
    """Assemble only through the production report exit, never validation-only."""
    if not _CODE:
        raise RuntimeError("PIT production writer is not configured")
    source_anchors = _chapter_source_anchor_ids()
    if not source_anchors:
        raise RuntimeError("PIT production report requires at least one source anchor from an actual read")
    prerequisites = _refresh_pit_v3_prerequisites()
    result = write_tools.assemble_report(
        output_dir=_bound_output(),
        company_name=str(company_name or _CODE),
        ts_code=_CODE,
        validation_only=False,
    )
    report_path = Path(str(result.get("path") or ""))
    if report_path.is_file():
        result["pit_source_anchor_ids"] = sorted(source_anchors)
    result["pit_v3_prerequisites"] = prerequisites
    return result


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


for _name in (
    "read_report_contract_pack",
    "read_structured_ledger_contract",
):
    globals()["pit_" + _name] = _bind_contract_read(_name)
