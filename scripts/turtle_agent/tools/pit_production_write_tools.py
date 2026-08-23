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
_ANALYSIS_PURPOSE: str = "INVESTMENT_DECISION"
_HANDOFF_RECEIPT_STATE: dict[str, Any] = {}

_HANDOFF_RECEIPT_SCHEMA_VERSION = "pit-judgment-handoff-receipts.v1"
_HANDOFF_RECEIPT_FILE = "pit_judgment_handoff_receipts.json"
_HANDOFF_VIEWS = ("RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS", "INVESTMENT_ENRICHMENT")
_HANDOFF_READY_STATES = {
    "RESEARCH_AGENDA": {"READY", "READY_WITH_NO_PRIOR"},
    "JUDGMENT_SYNTHESIS": {"READY"},
    "INVESTMENT_ENRICHMENT": {"READY"},
}
_HANDOFF_MUTATION_VIEWS = {
    "write_claim_evidence_ledger": ("JUDGMENT_SYNTHESIS",),
    "write_financial_driver_bridge": ("JUDGMENT_SYNTHESIS",),
    "write_thesis_test_ledger": ("JUDGMENT_SYNTHESIS",),
    "write_insight_ledger": ("JUDGMENT_SYNTHESIS",),
}


def configure_pit_production_writer(
    *, output_dir: str | Path, code: str, run_id: str, pit_runner: Any,
    analysis_purpose: str = "INVESTMENT_DECISION",
) -> None:
    global _OUTPUT_DIR, _CODE, _RUN_ID, _PIT_RUNNER, _ANALYSIS_PURPOSE, _HANDOFF_RECEIPT_STATE
    if analysis_purpose not in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
        raise RuntimeError("PIT production analysis_purpose invalid")
    _OUTPUT_DIR = str(Path(output_dir).expanduser().resolve())
    _CODE = str(code or "").strip()
    _RUN_ID = str(run_id or "").strip()
    _PIT_RUNNER = pit_runner
    _ANALYSIS_PURPOSE = analysis_purpose
    _HANDOFF_RECEIPT_STATE = {
        "schema_version": _HANDOFF_RECEIPT_SCHEMA_VERSION,
        "run_id": _RUN_ID,
        "analysis_purpose": _ANALYSIS_PURPOSE,
        "prerequisite_refresh_generation": 0,
        "view_generations": {view: 0 for view in _HANDOFF_VIEWS},
        "receipts": {},
    }
    _persist_handoff_receipts()


def clear_pit_production_writer() -> None:
    global _OUTPUT_DIR, _CODE, _RUN_ID, _PIT_RUNNER, _ANALYSIS_PURPOSE, _HANDOFF_RECEIPT_STATE
    _OUTPUT_DIR = ""
    _CODE = ""
    _RUN_ID = ""
    _PIT_RUNNER = None
    _ANALYSIS_PURPOSE = "INVESTMENT_DECISION"
    _HANDOFF_RECEIPT_STATE = {}


def _bound_output() -> str:
    if not _OUTPUT_DIR:
        raise RuntimeError("PIT production writer is not configured")
    return _OUTPUT_DIR


def _required_handoff_views(analysis_purpose: str) -> tuple[str, ...]:
    common = ("RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS")
    return common + (("INVESTMENT_ENRICHMENT",) if analysis_purpose == "INVESTMENT_DECISION" else ())


def _persist_handoff_receipts() -> None:
    if not _OUTPUT_DIR or not _HANDOFF_RECEIPT_STATE:
        return
    path = Path(_OUTPUT_DIR) / _HANDOFF_RECEIPT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_HANDOFF_RECEIPT_STATE, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _advance_handoff_generation(
    *views: str, prerequisite_refresh: bool = False,
) -> dict[str, Any]:
    """Invalidate only the handoff reads affected by a deterministic mutation."""
    if not _HANDOFF_RECEIPT_STATE:
        raise RuntimeError("PIT production writer is not configured")
    if prerequisite_refresh:
        _HANDOFF_RECEIPT_STATE["prerequisite_refresh_generation"] += 1
    generations = _HANDOFF_RECEIPT_STATE["view_generations"]
    for view in views:
        if view not in _HANDOFF_VIEWS:
            raise RuntimeError("PIT judgment handoff view invalid: " + str(view))
        generations[view] = int(generations.get(view) or 0) + 1
    _persist_handoff_receipts()
    return {
        "prerequisite_refresh_generation": _HANDOFF_RECEIPT_STATE["prerequisite_refresh_generation"],
        "view_generations": deepcopy(generations),
    }


def _record_handoff_receipt(view: str, handoff: dict[str, Any]) -> dict[str, Any]:
    normalized = str(view or "").upper()
    if normalized not in _HANDOFF_VIEWS:
        raise RuntimeError("PIT judgment handoff view invalid: " + normalized)
    readiness = handoff.get("readiness") if isinstance(handoff.get("readiness"), dict) else {}
    receipt = {
        "view": normalized,
        "readiness_state": str(readiness.get("state") or "MISSING"),
        "prerequisite_refresh_generation": int(
            _HANDOFF_RECEIPT_STATE.get("prerequisite_refresh_generation") or 0
        ),
        "view_generation": int(
            (_HANDOFF_RECEIPT_STATE.get("view_generations") or {}).get(normalized) or 0
        ),
    }
    _HANDOFF_RECEIPT_STATE.setdefault("receipts", {})[normalized] = receipt
    _persist_handoff_receipts()
    return deepcopy(receipt)


def validate_pit_handoff_receipts(
    *, output_dir: str | Path | None = None, analysis_purpose: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Validate that every required view was read after its last relevant refresh."""
    if output_dir is None:
        state = deepcopy(_HANDOFF_RECEIPT_STATE)
    else:
        path = Path(output_dir) / _HANDOFF_RECEIPT_FILE
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        state = loaded if isinstance(loaded, dict) else {}
    purpose = str(analysis_purpose or state.get("analysis_purpose") or "")
    findings: list[str] = []

    def nonnegative_integer(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    if state.get("schema_version") != _HANDOFF_RECEIPT_SCHEMA_VERSION:
        findings.append("handoff_receipt_schema_invalid")
    if run_id is not None and str(state.get("run_id") or "") != str(run_id):
        findings.append("handoff_receipt_run_id_mismatch")
    if purpose not in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
        findings.append("handoff_receipt_analysis_purpose_invalid")
    elif state.get("analysis_purpose") != purpose:
        findings.append("handoff_receipt_analysis_purpose_mismatch")
    refresh_generation_value = nonnegative_integer(state.get("prerequisite_refresh_generation"))
    refresh_generation = refresh_generation_value if refresh_generation_value is not None else -1
    if refresh_generation_value is None:
        findings.append("prerequisite_refresh_generation_invalid")
    elif refresh_generation < 1:
        findings.append("prerequisite_refresh_missing")
    receipts = state.get("receipts") if isinstance(state.get("receipts"), dict) else {}
    raw_view_generations = state.get("view_generations")
    view_generations = raw_view_generations if isinstance(raw_view_generations, dict) else {}
    if not isinstance(raw_view_generations, dict):
        findings.append("handoff_view_generations_missing")
    if purpose in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
        for view in _required_handoff_views(purpose):
            current_view_generation = nonnegative_integer(view_generations.get(view))
            if view not in view_generations:
                findings.append("handoff_view_generation_missing:" + view)
            elif current_view_generation is None:
                findings.append("handoff_view_generation_invalid:" + view)
            receipt = receipts.get(view) if isinstance(receipts.get(view), dict) else {}
            if not receipt:
                findings.append("handoff_receipt_missing:" + view)
                continue
            if receipt.get("readiness_state") not in _HANDOFF_READY_STATES[view]:
                findings.append("handoff_view_not_ready:" + view)
            if receipt.get("view") != view:
                findings.append("handoff_receipt_view_mismatch:" + view)
            receipt_refresh_generation = nonnegative_integer(
                receipt.get("prerequisite_refresh_generation")
            )
            receipt_view_generation = nonnegative_integer(receipt.get("view_generation"))
            if receipt_refresh_generation is None:
                findings.append("handoff_receipt_refresh_generation_invalid:" + view)
            if receipt_view_generation is None:
                findings.append("handoff_receipt_view_generation_invalid:" + view)
            if receipt_refresh_generation != refresh_generation:
                findings.append("handoff_receipt_stale_after_prerequisite_refresh:" + view)
            if receipt_view_generation != current_view_generation:
                findings.append("handoff_receipt_stale_after_view_change:" + view)
    return {
        "state": "READY" if not findings else "BLOCKED",
        "findings": findings,
        "required_views": list(_required_handoff_views(purpose)) if purpose in {
            "INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"
        } else [],
        "prerequisite_refresh_generation": refresh_generation,
        "view_generations": deepcopy(view_generations),
    }


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
    if _ANALYSIS_PURPOSE == "COMPANY_JUDGMENT_ONLY":
        agenda = read_tools.read_judgment_generation_handoff(
            str(output), "RESEARCH_AGENDA",
        )
        result = {
            "state": "REFRESHED",
            "analysis_purpose": _ANALYSIS_PURPOSE,
            "official_evidence_state": (context.get("validation") or {}).get("state"),
            "valuation_route_state": "NOT_APPLICABLE",
            "decisive_question_state": (
                "AVAILABLE"
                if (agenda.get("projection") or {}).get("decisive_questions")
                else "NO_DECISIVE_PLAN_EVIDENCE_ONLY"
            ),
            "judgment_generation_handoff_state": (
                (agenda.get("readiness") or {}).get("state")
            ),
            "industry_prior_state": (
                (agenda.get("readiness") or {}).get("empty_states", {}).get("industry_priors")
            ),
            "calculation_state": "NOT_APPLICABLE",
        }
        result.update(_advance_handoff_generation(prerequisite_refresh=True))
        return result
    archetype = build_company_archetype(output, persist=True)
    route = build_valuation_route(output, archetype, persist=True)
    decisive = refresh_decisive_question_plan(output, run_id=_RUN_ID or None, enforced=True)
    calculations = build_calculation_observations(output, persist=True)
    agenda = read_tools.read_judgment_generation_handoff(
        str(output), "RESEARCH_AGENDA",
    )
    enrichment = read_tools.read_judgment_generation_handoff(
        str(output), "INVESTMENT_ENRICHMENT",
    )
    result = {
        "state": "REFRESHED",
        "official_evidence_state": (context.get("validation") or {}).get("state"),
        "valuation_route_state": (route.get("validation") or {}).get("state"),
        "decisive_question_state": ((decisive.get("plan") or {}).get("validation") or {}).get("state"),
        "calculation_state": (calculations.get("validation") or {}).get("state"),
        "judgment_generation_handoff_state": {
            "research_agenda": (agenda.get("readiness") or {}).get("state"),
            "investment_enrichment": (enrichment.get("readiness") or {}).get("state"),
        },
    }
    result.update(_advance_handoff_generation(prerequisite_refresh=True))
    return result


def _bind(name: str) -> Callable[..., Any]:
    source = getattr(write_tools, name)

    def bound(**kwargs: Any) -> Any:
        if "output_dir" in kwargs:
            raise RuntimeError("PIT production writer does not accept output_dir")
        if name == "write_chapter":
            _validate_source_anchors(kwargs.get("content"))
        if _ANALYSIS_PURPOSE == "COMPANY_JUDGMENT_ONLY" and name in {
            "write_decision_manifest", "write_decision_ledger", "write_valuation_model_ledger",
        }:
            raise RuntimeError("COMPANY_JUDGMENT_ONLY PIT writer 禁止写入决策、仓位或估值对象")
        result = source(output_dir=_bound_output(), **kwargs)
        if name == "verify_official_fact" and result.get("verified") is True:
            result["pit_v3_prerequisites"] = _refresh_pit_v3_prerequisites()
        affected_views = _HANDOFF_MUTATION_VIEWS.get(name, ())
        if affected_views:
            result["pit_handoff_generation"] = _advance_handoff_generation(*affected_views)
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
        result = source(output_dir=_bound_output(), **kwargs)
        if not isinstance(result, dict):
            return result
        if name == "read_judgment_generation_handoff":
            view = str(kwargs.get("view") or "RESEARCH_AGENDA").upper()
            result = deepcopy(result)
            result["pit_handoff_receipt"] = _record_handoff_receipt(view, result)
        elif name == "read_report_contract_pack" and result.get("ok") is True:
            company_judgment_rules = deepcopy(result.get("company_judgment_rules") or [])
            chapters = {
                str(index): {
                    key: deepcopy(value.get(key))
                    for key in ("title", "content", "char_count")
                    if key in value
                }
                for index, value in (result.get("chapters") or {}).items()
                if isinstance(value, dict)
            }
            generation_handoff = (
                result.get("judgment_generation_handoff")
                if isinstance(result.get("judgment_generation_handoff"), dict) else {}
            )
            receipts: dict[str, Any] = {}
            for key, view in (
                ("research_agenda", "RESEARCH_AGENDA"),
                ("investment_enrichment", "INVESTMENT_ENRICHMENT"),
            ):
                handoff = generation_handoff.get(key)
                if isinstance(handoff, dict):
                    receipts[view] = _record_handoff_receipt(view, handoff)
            result = {
                "ok": True,
                "analysis_purpose": _ANALYSIS_PURPOSE,
                "template": result.get("template"),
                "chapter_indexes": deepcopy(result.get("chapter_indexes") or []),
                "chapters": chapters,
                "official_evidence": deepcopy(result.get("official_evidence") or {}),
                "judgment_generation_handoff": deepcopy(generation_handoff),
                "instruction": (
                    "PIT contract pack exposes only repository-static chapter contracts, "
                    "report-local official evidence, and cutoff-safe judgment handoff views."
                ),
                "char_count": sum(
                    int(value.get("char_count") or 0) for value in chapters.values()
                ),
                "pit_handoff_receipts": receipts,
            }
            if _ANALYSIS_PURPOSE == "COMPANY_JUDGMENT_ONLY":
                result["company_judgment_rules"] = company_judgment_rules
        return result

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
    if int(_HANDOFF_RECEIPT_STATE.get("prerequisite_refresh_generation") or 0) < 1:
        prerequisites = _refresh_pit_v3_prerequisites()
    else:
        prerequisites = {
            "state": "ALREADY_REFRESHED",
            "prerequisite_refresh_generation": int(
                _HANDOFF_RECEIPT_STATE.get("prerequisite_refresh_generation") or 0
            ),
        }
    receipt_validation = validate_pit_handoff_receipts(
        analysis_purpose=_ANALYSIS_PURPOSE, run_id=_RUN_ID,
    )
    if receipt_validation.get("state") != "READY":
        raise RuntimeError(
            "PIT report assembly requires current ready judgment handoff receipts: "
            + ", ".join(str(item) for item in receipt_validation.get("findings") or [])
        )
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
    result["pit_judgment_handoff_receipts"] = receipt_validation
    result["analysis_purpose"] = _ANALYSIS_PURPOSE
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
    "write_financial_driver_bridge",
    "write_thesis_test_ledger",
    "write_decisive_question_findings",
    "write_insight_ledger",
    "write_judgment_review",
):
    globals()["pit_" + _name] = _bind(_name)


for _name in (
    "read_report_contract_pack",
    "read_judgment_generation_handoff",
    "read_structured_ledger_contract",
):
    globals()["pit_" + _name] = _bind_contract_read(_name)
