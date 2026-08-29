import json
from pathlib import Path

from scripts.turtle_agent.agent_loop import (
    AgentConfig,
    TurtleAgent,
    _template_sections_for_targets,
)
from scripts.turtle_agent.llm_client import LlmResponse, ToolCall
from scripts.turtle_agent.run import (
    _explicit_repair_targets_for_pass,
    _is_binding_only_repair,
    _load_golden_report_review_return,
    _repair_iteration_budget,
    _repair_targets_for_pass,
    _repair_targets_from_completion,
    _requires_zero_pass_revalidation,
    _refresh_completion_after_incomplete_source_pass,
    _structured_context_stop_reason,
)
from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.decision_ledger import (
    bind_decision_references,
    repair_chapter_decision_references,
)


class _DummyLlm:
    model = "dummy"


class _FailingLlm:
    model = "dummy"

    def set_runtime_task(self, task_type: str) -> None:
        pass

    def chat(self, *args, **kwargs):
        raise RuntimeError("provider connection failed")


def _review_return(*, root_cause: str, guidance: str = "") -> dict:
    return {
        "schema_version": "golden-report-review-return.v1",
        "review_id": "REVIEW-1",
        "report_id": "REPORT-1",
        "candidate_ref": "reports/candidate.md",
        "reviewer_id": "REVIEWER-1",
        "reviewed_at": "2026-08-29T00:00:00Z",
        "findings": [{
            "finding_id": "F-1",
            "root_cause_classes": [root_cause],
            "materiality": "MATERIAL",
            "economic_impact": "The issue can change normalized owner cash and value.",
            "affected_claims": ["cash accessibility changes value"],
            "missing_facts": ["subsidiary remittance evidence"],
            "prohibited_assumptions": ["do not assume all cash is distributable"],
            "executable_remediation": ["repair the owning reusable component"],
            "acceptance_criteria": ["the owning component passes with evidence"],
            "affected_chapters": [12],
            "remediation_status": "OPEN",
            "acceptance_evidence_refs": [],
            "reader_guidance": guidance,
        }],
    }


def test_zero_pass_repair_always_revalidates_instead_of_reading_stale_completion() -> None:
    assert _requires_zero_pass_revalidation(
        repair_only=True, requested_repairs=0, explicit_repairs=(),
    ) is True
    assert _requires_zero_pass_revalidation(
        repair_only=True, requested_repairs=1, explicit_repairs=(),
    ) is False
    assert _requires_zero_pass_revalidation(
        repair_only=True, requested_repairs=0, explicit_repairs=(12,),
    ) is False
    assert _requires_zero_pass_revalidation(
        repair_only=False, requested_repairs=0, explicit_repairs=(),
    ) is False


def test_structured_context_stop_is_nonempty_only_after_tool_breaker() -> None:
    class _Agent:
        _structured_no_progress_error = "structured tool repeated"

    assert _structured_context_stop_reason(_Agent()) == "structured tool repeated"
    assert _structured_context_stop_reason(object()) == ""


def test_repair_targets_use_blocked_chapters_in_report_order() -> None:
    completion = {
        "chapter_results": [
            {"index": 0, "blocking_rules": ["audit_failed"]},
            {"index": 1, "blocking_rules": []},
            {"index": 12, "blocking_rules": ["short:90<120"]},
            {"index": 6, "blocking_rules": ["audit_failed"]},
        ]
    }

    assert _repair_targets_from_completion(completion) == (6, 12, 0)


def test_llm_failure_is_raised_before_assembly_or_source_depth_masking(tmp_path: Path) -> None:
    contract = tmp_path / "analysis_contract.json"
    contract.write_text(json.dumps({"ts_code": "000001.SZ"}), encoding="utf-8")
    agent = TurtleAgent(
        llm=_FailingLlm(),  # type: ignore[arg-type]
        tools=ToolRegistry(),
        config=AgentConfig(
            code="000001.SZ", contract_path=str(contract), output_dir=str(tmp_path),
            max_iterations=1, repair_targets=(14, 0), source_deepening=True,
            synthesis_only=True,
        ),
    )
    import pytest
    with pytest.raises(RuntimeError, match="禁止用后续完成契约掩盖原始错误"):
        agent.analyze()
    assert not (tmp_path / "completion_report.json").exists()


def test_repair_targets_support_legacy_blocking_findings() -> None:
    completion = {"blocking_findings": ["Ch11: audit_failed", "Ch2: short:70<80"]}

    assert _repair_targets_from_completion(completion) == (2, 11)


def test_open_upstream_review_return_does_not_trigger_chapter_repair() -> None:
    completion = {
        "chapter_results": [{"index": 12, "blocking_rules": ["audit_failed"]}],
        "golden_report_review_return": _review_return(root_cause="MODEL"),
    }

    assert _repair_targets_from_completion(completion) == ()


def test_pure_writing_review_return_routes_only_declared_reader_chapter() -> None:
    completion = {
        "golden_report_review_return": _review_return(
            root_cause="WRITING",
            guidance="Explain the cash-access range once in investor language.",
        ),
    }

    assert _repair_targets_from_completion(completion) == (12,)


def test_review_return_file_enters_the_same_routing_path_used_by_repair_only(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "review-return.json"
    review_path.write_text(
        json.dumps(_review_return(
            root_cause="WRITING",
            guidance="State the accepted cash-access consequence once.",
        )),
        encoding="utf-8",
    )

    loaded = _load_golden_report_review_return(str(review_path))
    completion = {
        "status": "COMPLETE",
        "golden_report_review_return": loaded,
    }

    assert loaded["candidate_ref"] == "reports/candidate.md"
    assert _repair_targets_from_completion(completion) == (12,)


def test_repair_prompt_uses_clean_reader_brief_not_raw_completion_findings(tmp_path: Path) -> None:
    (tmp_path / "completion_report.json").write_text(json.dumps({
        "blocking_findings": [
            "DATA_COVERAGE: acquisition_schema_missing",
            "Quality: P_LONG PRIMARY_ROUTE_UNKNOWN",
        ],
    }), encoding="utf-8")
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(
            output_dir=str(tmp_path),
            repair_targets=(12,),
            reader_repair_brief=[
                {
                    "instruction": "说明现金可达性不确定时，内在价值区间和行动门槛如何变化。",
                },
                {
                    "instruction": "保留已有估值结论，删除重复的内部过程说明。",
                },
            ],
        ),
    )

    prompt = agent._build_resume_hint()

    assert "现金可达性不确定" in prompt
    assert "删除重复的内部过程说明" in prompt
    assert "DATA_COVERAGE" not in prompt
    assert "P_LONG" not in prompt
    assert "PRIMARY_ROUTE_UNKNOWN" not in prompt
    assert "blocking_findings" not in prompt
    assert "audit_failed" not in prompt


def test_reader_repair_tool_surface_cannot_mutate_models_or_research(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for name in (
        "list_documents", "read_report_contract_pack", "read_chapter",
        "audit_chapter", "write_chapter", "write_valuation_model_ledger",
        "web_search", "assemble_report",
    ):
        registry.register(name, lambda **kwargs: {}, parameters={})
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(
            output_dir=str(tmp_path),
            repair_targets=(0, 12, 14),
            reader_repair_brief=[{
                "instruction": "Explain the accepted value range in investor language.",
            }],
        ),
    )

    offered = {
        str(item.get("function", {}).get("name") or "")
        for item in agent._tool_schemas_for_stage()
    }

    assert offered == {
        "list_documents", "read_report_contract_pack", "read_chapter",
        "audit_chapter", "write_chapter",
    }


def test_decision_ledger_failure_routes_only_decision_chapters() -> None:
    completion = {
        "blocking_findings": [
            "Decision ledger: INVALID: unexplained_conflict:valuation.v_final:Ch12:Ch14"
        ]
    }

    assert _repair_targets_from_completion(completion) == (12, 14, 0)


def test_binding_only_repair_requires_only_decision_identity_blockers() -> None:
    assert _is_binding_only_repair({"blocking_findings": [
        "Decision ledger: INVALID: decision_value_mismatch:L64:D005",
        "Decision compiler: INVALID: free_critical_value:Ch12:L22:valuation.v_final",
        "Quality hard contract: failure in Ch12",
    ]}) is True
    assert _is_binding_only_repair({"blocking_findings": [
        "Decision compiler: INVALID: free_critical_value:Ch12:L22:valuation.v_final",
        "Ch12: audit_failed",
    ]}) is False


def test_binding_contract_exposes_values_and_exact_failures(tmp_path: Path) -> None:
    (tmp_path / "decision_ledger.json").write_text(json.dumps({"entries": [{
        "entry_id": "D006", "metric_id": "valuation.v_final", "value": 41.7,
        "unit": "RMB/share", "status": "active", "chapters": [0, 12, 14],
    }]}), encoding="utf-8")
    (tmp_path / "decision_compiler_validation.json").write_text(json.dumps({
        "state": "INVALID", "invalid_findings": ["free_critical_value:Ch12:L22:valuation.v_final"],
    }), encoding="utf-8")
    result = read_structured_ledger_contract(str(tmp_path), ledger="decision_binding")
    assert result["ok"] is True
    assert result["active_entries"][0]["value"] == 41.7
    assert result["decision_compiler_validation"]["state"] == "INVALID"


def test_binding_only_agent_offers_no_research_or_ledger_mutation_tools(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for name in ("read_chapter", "read_section", "write_chapter", "write_decision_ledger"):
        registry.register(name, lambda **kwargs: {}, parameters={})
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(
            output_dir=str(tmp_path), repair_targets=(12,), binding_only=True,
            source_deepening=True, synthesis_only=True,
        ),
    )
    offered = {
        str(item.get("function", {}).get("name") or "")
        for item in agent._tool_schemas_for_stage()
    }
    assert offered == {"read_chapter", "write_chapter"}
    assert agent._config.source_deepening is False
    assert agent._config.synthesis_only is False


def test_binding_schema_narrowing_does_not_mutate_shared_registry(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "read_structured_ledger_contract", lambda **kwargs: {},
        parameters={"ledger": {"type": "string", "enum": ["decision_binding", "claim"]}},
    )
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(output_dir=str(tmp_path), repair_targets=(12,), binding_only=True),
    )
    narrowed = agent._tool_schemas_for_stage()[0]
    original = registry.get_schemas()[0]
    assert narrowed["function"]["parameters"]["properties"]["ledger"]["enum"] == ["decision_binding"]
    assert original["function"]["parameters"]["properties"]["ledger"]["enum"] == ["decision_binding", "claim"]


def test_binding_only_rejects_non_binding_ledger_argument(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "read_structured_ledger_contract",
        lambda **kwargs: calls.append(kwargs) or {},
        parameters={"ledger": {"type": "string"}},
    )
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(output_dir=str(tmp_path), repair_targets=(12,), binding_only=True),
    )
    agent._last_offered_tool_names = {"read_structured_ledger_contract"}
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="wrong-ledger", name="read_structured_ledger_contract",
        arguments={"ledger": "claim"},
    )]))
    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["requested_ledger"] == "claim"


def test_binding_only_loop_stops_as_soon_as_all_targets_pass(tmp_path: Path) -> None:
    class _OneWriteLlm:
        model = "dummy"

        def __init__(self):
            self.calls = 0

        def chat(self, *args, **kwargs):
            self.calls += 1
            return LlmResponse(
                tool_calls=[ToolCall(
                    id="write-once", name="write_chapter",
                    arguments={"chapter_index": 12, "content": "## Ch12\n\nbody"},
                )],
                usage={"input": 1, "output": 1},
            )

    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: {
            "chapter_index": 12,
            "audit": {"passed": True, "verdict": "pass"},
            "depth": {"status": "PASS", "failures": []},
            "passed": True,
            "decision_binding_validation": {"state": "DECISION_READY"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    llm = _OneWriteLlm()
    agent = TurtleAgent(
        llm,  # type: ignore[arg-type]
        registry,
        AgentConfig(
            output_dir=str(tmp_path), repair_targets=(12,), binding_only=True,
            max_iterations=10,
        ),
    )
    agent._run_loop()
    assert llm.calls == 1
    assert agent._passed_chapters == {12}


def test_binding_only_analyze_never_reinitializes_research_execution(tmp_path: Path) -> None:
    class _ProbeAgent(TurtleAgent):
        initialized = 0

        def _load_context(self):
            self._context = {}

        def _initialize_research_execution(self):
            self.initialized += 1

        def _build_system_prompt(self):
            return "system"

        def _run_loop(self):
            return None

        def _assemble_report(self):
            return str(tmp_path / "draft.md")

    agent = _ProbeAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), repair_targets=(12,), binding_only=True),
    )
    agent.analyze()
    assert agent.initialized == 0
    assert not (tmp_path / "research_execution.json").exists()


def test_quality_data_audit_routes_to_quantitative_and_synthesis_chapters() -> None:
    completion = {"blocking_findings": ["Quality: data_point_audit"]}

    assert _repair_targets_from_completion(completion) == (10, 11, 12, 13, 14, 0)


def test_quality_hard_contract_routes_named_failed_chapters() -> None:
    completion = {"blocking_findings": ["Quality hard contract: failure in Ch0,Ch6,Ch8,Ch9"]}
    assert _repair_targets_from_completion(completion) == (6, 8, 9, 0)


def test_dividend_identity_and_decision_blockers_route_to_owner_chapters() -> None:
    completion = {
        "blocking_findings": [
            "Quality: dividend_identity: chapters=Ch6,Ch8,Ch11",
            "Decision: Ch0/Ch14/manifest mismatch (Hold Review)",
        ]
    }

    assert _repair_targets_from_completion(completion) == (6, 8, 11, 14, 0)


def test_two_repair_passes_split_qualitative_and_quantitative_contexts() -> None:
    completion = {
        "chapter_results": [
            {"index": idx, "blocking_rules": ["audit_failed"]}
            for idx in (0, 2, 6, 10, 12, 14)
        ]
    }

    assert _repair_targets_for_pass(completion, 1, 2) == (2, 6)
    assert _repair_targets_for_pass(completion, 2, 2) == (10, 12, 14, 0)


def test_five_repair_passes_use_bounded_dynamic_batches() -> None:
    completion = {
        "chapter_results": [
            {"index": idx, "blocking_rules": ["audit_failed"]}
            for idx in range(15)
        ]
    }

    assert _repair_targets_for_pass(completion, 1, 5) == (1, 2, 3, 4)
    assert _repair_targets_for_pass(completion, 4, 5) == (1, 2, 3, 4)
    assert _repair_targets_for_pass(completion, 5, 5) == (14, 0)


def test_missing_structured_ledgers_route_to_synthesis_not_whole_report() -> None:
    completion = {"blocking_findings": [
        "Claim evidence: INCOMPLETE: claim_evidence_missing",
        "Valuation model: INCOMPLETE: valuation_model_missing",
        "Insight ledger: INCOMPLETE: insight_ledger_missing",
    ]}

    assert _repair_targets_from_completion(completion) == (14, 0)


def test_explicit_deepening_targets_split_without_blocked_completion() -> None:
    targets = tuple(range(15))

    assert _explicit_repair_targets_for_pass(targets, 1, 2) == tuple(range(1, 10))
    assert _explicit_repair_targets_for_pass(targets, 2, 2) == (10, 11, 12, 13, 14, 0)

    assert _explicit_repair_targets_for_pass(targets, 1, 5) == (1, 2, 3, 4)
    assert _explicit_repair_targets_for_pass(targets, 4, 5) == (13,)
    assert _explicit_repair_targets_for_pass(targets, 5, 5) == (14, 0)


def test_write_chapter_recovers_missing_index_from_heading(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: calls.append(kwargs) or {
            "chapter_index": kwargs["chapter_index"],
            "audit": {"passed": True},
            "depth": {"status": "PASS"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(output_dir=str(tmp_path), repair_targets=(14,)),
    )
    agent._chapter_contract_reads.add(14)

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="missing-index",
        name="write_chapter",
        arguments={"content": "## Ch14 综合决策\n\n结论。"},
    )]))

    assert calls[0]["chapter_index"] == 14


def test_incomplete_source_pass_refreshes_completion_without_publishing(tmp_path: Path, monkeypatch) -> None:
    import scripts.report_completion as completion_module
    chapters = tmp_path / "chapters"; chapters.mkdir()
    (chapters / "_ch01.md").write_text("## Ch1 事实\n\n第一章", encoding="utf-8")
    (chapters / "_ch03.md").write_text("## Ch3 机制\n\n第三章", encoding="utf-8")
    captured = {}

    class Result:
        def to_dict(self):
            return {"status": "INCOMPLETE", "blocking_findings": ["Ch3: audit_failed"]}

    def fake_evaluate(report_text, output_dir):
        captured["report_text"] = report_text; captured["output_dir"] = output_dir
        return Result()

    monkeypatch.setattr(completion_module, "evaluate_report_completion", fake_evaluate)
    result = _refresh_completion_after_incomplete_source_pass(str(tmp_path))
    assert result["status"] == "INCOMPLETE"
    assert "## Ch1" in captured["report_text"] and "## Ch3" in captured["report_text"]
    assert not (tmp_path / "reports").exists()


def test_canonical_decision_binding_is_deterministic_clerical_work(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"; chapters.mkdir()
    path = chapters / "_ch00.md"
    path.write_text("## Ch0 投资要点\n\n当前价2.02 HKD；V_final=2.80 HKD。\n", encoding="utf-8")
    payload = {"entries": [
        {"entry_id": "D001", "metric_id": "market.price.current", "value": 2.02, "unit": "HKD", "status": "active", "chapters": [0]},
        {"entry_id": "D006", "metric_id": "valuation.v_final", "value": 2.80, "unit": "HKD", "status": "active", "chapters": [0]},
    ]}
    first = bind_decision_references(tmp_path, payload)
    second = bind_decision_references(tmp_path, payload)
    text = path.read_text(encoding="utf-8")
    assert first["anchors_inserted"] == 2
    assert second["anchors_inserted"] == 0
    assert "[decision: D001]" in text and "[decision: D006]" in text


def test_deterministic_binding_repair_removes_false_id_without_changing_values(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"; chapters.mkdir()
    path = chapters / "_ch12.md"
    path.write_text(
        "## Ch12 估值\n\nGG_base=7.4% [decision: D005]，结论保持不变。\n",
        encoding="utf-8",
    )
    payload = {"entries": [
        {"entry_id": "D002", "metric_id": "return.gg.base", "value": 7.4,
         "unit": "pct", "status": "active", "chapters": [12]},
        {"entry_id": "D005", "metric_id": "hurdle.ii", "value": 4.5,
         "unit": "pct", "status": "active", "chapters": [12]},
    ]}
    result = repair_chapter_decision_references(tmp_path, payload, chapters=(12,))
    text_value = path.read_text(encoding="utf-8")
    assert result["removed_invalid_anchors"] == 1
    assert "GG_base=7.4%，结论保持不变。 [decision: D002]" in text_value
    assert "| hurdle.ii | 4.5 pct | [decision: D005] |" in text_value
    assert result["passed"] is True


def test_source_deepening_blocks_write_until_primary_reads(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: calls.append(kwargs) or {"chapter_index": kwargs["chapter_index"]},
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(
            output_dir=str(tmp_path),
            repair_targets=(1, 2),
            source_deepening=True,
        ),
    )

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="premature-write",
        name="write_chapter",
        arguments={"chapter_index": 1, "content": "正文"},
    )]))

    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["source_research_required"] is True
    assert any("未实际读取 MDA" in item for item in payload["value"]["missing"])


def test_source_blocked_draft_is_replayed_after_reads_without_regeneration(tmp_path: Path) -> None:
    writes: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: writes.append(kwargs) or {
            "chapter_index": kwargs["chapter_index"],
            "audit": {"passed": True, "verdict": "pass"},
            "decision_binding_validation": {"state": "REVIEWABLE"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        _DummyLlm(), registry,  # type: ignore[arg-type]
        AgentConfig(
            output_dir=str(tmp_path), repair_targets=(13,), source_deepening=True,
        ),
    )
    agent._chapter_contract_reads.add(13)
    draft = {"chapter_index": 13, "content": "## Ch13\n\n昂贵但完整的候选正文。"}
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="blocked", name="write_chapter", arguments=draft,
    )]))
    assert writes == []
    assert agent._pending_source_blocked_writes[13]["content"] == draft["content"]

    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [13]},
        {"tool": "read_section", "section": "NOTES", "year": 2024,
         "gate_eligible": True, "research_for_chapters": [13]},
    ]
    agent._handle_tool_calls(LlmResponse(tool_calls=[]))

    assert len(writes) == 1
    assert writes[0]["content"] == draft["content"]
    assert 13 not in agent._pending_source_blocked_writes


def test_research_execution_ledger_records_actual_reads_not_prose(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(
            output_dir=str(tmp_path),
            pass_name="source_deepening_quant",
            repair_targets=(11, 12),
            source_deepening=True,
        ),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025, "research_for_chapters": [11], "attribution": "explicit"},
        {"tool": "read_section", "section": "NOTES", "year": 2024, "research_for_chapters": [11], "attribution": "explicit"},
        {"tool": "search_report", "query": "少数股东", "year": 2025, "research_for_chapters": [11], "attribution": "explicit"},
        {"tool": "web_search", "query": "行业竞争", "research_for_chapters": [11], "attribution": "explicit"},
        {"tool": "web_fetch", "url": "https://example.com/research", "research_for_chapters": [11], "attribution": "explicit"},
    ]

    agent._persist_research_execution(11)
    payload = json.loads((tmp_path / "research_execution.json").read_text(encoding="utf-8"))
    entry = payload["chapters"]["11"]

    assert entry["enforced"] is True
    assert entry["actual_read_sections"] == ["NOTES", "STMT"]
    assert entry["missing_sections"] == []
    assert entry["fiscal_years"] == [2024, 2025]
    assert entry["tool_counts"]["web_fetch"] == 1


def test_source_requirements_are_chapter_specific(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025, "research_for_chapters": [11]},
        {"tool": "read_section", "section": "NOTES", "year": 2024, "research_for_chapters": [11]},
    ]

    assert agent._source_research_missing(11) == []

    agent._source_research_calls = [
        {"tool": "read_section", "section": "MDA", "year": 2025, "research_for_chapters": [2]},
        {"tool": "read_section", "section": "SEG", "year": 2024, "research_for_chapters": [2]},
    ]
    missing = agent._source_research_missing(2)
    assert any("web_search" in item for item in missing)
    assert any("web_fetch" in item for item in missing)


def test_source_calls_cannot_leak_across_chapters(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "MDA", "year": 2025, "research_for_chapters": [2]},
        {"tool": "read_section", "section": "SEG", "year": 2024, "research_for_chapters": [2]},
        {"tool": "web_search", "query": "行业竞争", "research_for_chapters": [2]},
        {"tool": "web_search", "query": "行业规模", "research_for_chapters": [2]},
        {"tool": "web_fetch", "url": "https://example.com/industry", "research_for_chapters": [2]},
    ]

    assert agent._source_research_missing(2) == []
    ch8_missing = agent._source_research_missing(8)
    assert any("web_search" in item for item in ch8_missing)
    assert any("未实际读取 GOV" in item for item in ch8_missing)


def test_explicit_multi_chapter_source_sharing_is_auditable(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "MDA", "year": 2025, "research_for_chapters": [2]},
        {"tool": "read_section", "section": "SEG", "year": 2024, "research_for_chapters": [2]},
        {"tool": "web_search", "query": "竞争治理", "research_for_chapters": [2, 8]},
        {"tool": "web_search", "query": "行业接班", "research_for_chapters": [2, 8]},
        {"tool": "web_fetch", "url": "https://example.com/shared", "research_for_chapters": [2, 8]},
    ]

    missing = agent._source_research_missing(8)
    assert not any("web_search" in item for item in missing)
    assert not any("web_fetch" in item for item in missing)
    assert any("未实际读取 GOV" in item for item in missing)


def test_low_authority_social_fetch_cannot_satisfy_external_body_gate(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "MDA", "year": 2025, "research_for_chapters": [2]},
        {"tool": "read_section", "section": "SEG", "year": 2024, "research_for_chapters": [2]},
        {"tool": "web_search", "query": "行业竞争", "research_for_chapters": [2]},
        {"tool": "web_search", "query": "行业规模", "research_for_chapters": [2]},
        {
            "tool": "web_fetch",
            "url": "https://mp.weixin.qq.com/s/abc",
            "source_authority": "LOW",
            "gate_eligible": False,
            "research_for_chapters": [2],
        },
    ]

    assert any("web_fetch合格结果或真实不可用尝试 0/1" in item for item in agent._source_research_missing(2))


def test_unrelated_fiscal_year_does_not_satisfy_chapter_year_gate(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025, "research_for_chapters": [6]},
        {"tool": "read_section", "section": "NOTES", "year": 2025, "research_for_chapters": [6]},
        {"tool": "read_section", "section": "MDA", "year": 2024, "research_for_chapters": [2]},
    ]

    assert any("年报原文覆盖财年 1/2" in item for item in agent._source_research_missing(6))


def test_single_available_annual_report_requires_one_year_not_an_impossible_second_year(
    tmp_path: Path,
) -> None:
    (tmp_path / "2025_年报.md").write_text("官方年报正文", encoding="utf-8")
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [11]},
        {"tool": "read_section", "section": "NOTES", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [11]},
    ]

    assert agent._source_research_missing(11) == []


def test_failed_section_attempt_can_be_localized_but_all_failed_reads_still_block(
    tmp_path: Path,
) -> None:
    (tmp_path / "2025_年报.md").write_text("官方年报正文", encoding="utf-8")
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [6]},
        {"tool": "read_section", "section": "NOTES", "year": 2025,
         "gate_eligible": False, "error": "section boundary unavailable",
         "research_for_chapters": [6]},
    ]
    assert agent._source_research_missing(6) == []

    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": False, "error": "extract failed", "research_for_chapters": [6]},
        {"tool": "read_section", "section": "NOTES", "year": 2025,
         "gate_eligible": False, "error": "extract failed", "research_for_chapters": [6]},
    ]
    missing = agent._source_research_missing(6)
    assert any("年报原文覆盖财年 0/1" in item for item in missing)
    assert any("未实际读取 STMT" in item for item in missing)


def test_true_external_source_failure_is_not_a_permanent_chapter_stop(tmp_path: Path) -> None:
    (tmp_path / "2025_年报.md").write_text("官方年报正文", encoding="utf-8")
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    for section in ("MDA", "SEG"):
        agent._record_source_research(
            "read_section",
            {"section": section, "year": 2025, "research_for_chapters": [2]},
            {"value": {"text": "official report body", "char_count": 20}},
        )
    agent._record_source_research(
        "web_search",
        {"query": "行业竞争", "research_for_chapters": [2]},
        {"value": {"error": "all_search_providers_failed", "results": []}},
    )
    agent._record_source_research(
        "web_fetch",
        {"url": "https://official.example", "research_for_chapters": [2]},
        {"value": {"error": "provider unavailable", "text": "", "char_count": 0}},
    )

    assert len(agent._source_research_calls) == 4
    assert all(not item["gate_eligible"] for item in agent._source_research_calls[2:])
    assert agent._source_research_missing(2) == []
    agent._persist_research_execution(2)
    entry = json.loads(
        (tmp_path / "research_execution.json").read_text(encoding="utf-8")
    )["chapters"]["2"]
    assert entry["required_fiscal_year_count"] == 1
    assert entry["attempted_unavailable_tools"] == ["web_fetch", "web_search"]


def test_failed_notes_read_can_use_two_year_official_report_search_fallback(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [13]},
        {"tool": "read_section", "section": "STMT", "year": 2024,
         "gate_eligible": True, "research_for_chapters": [13]},
        {"tool": "read_section", "section": "NOTES", "year": 2025,
         "gate_eligible": False, "research_for_chapters": [13]},
        {"tool": "search_report", "year": 2025, "gate_eligible": True,
         "document_id": "DOC:2025", "verification_eligible": True,
         "research_for_chapters": [13]},
        {"tool": "search_report", "year": 2024, "gate_eligible": True,
         "document_id": "DOC:2024", "verification_eligible": True,
         "research_for_chapters": [13]},
    ]

    assert agent._source_research_missing(13) == []
    agent._persist_research_execution(13)
    entry = json.loads((tmp_path / "research_execution.json").read_text(encoding="utf-8"))["chapters"]["13"]
    assert entry["search_fallback_sections"] == ["NOTES"]
    assert entry["missing_sections"] == []


def test_failed_notes_extractor_is_localized_when_other_official_body_is_available(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), source_deepening=True),
    )
    base = [
        {"tool": "read_section", "section": "STMT", "year": 2025,
         "gate_eligible": True, "research_for_chapters": [13]},
        {"tool": "read_section", "section": "STMT", "year": 2024,
         "gate_eligible": True, "research_for_chapters": [13]},
        {"tool": "search_report", "year": 2025, "gate_eligible": True,
         "document_id": "DOC:2025", "verification_eligible": True,
         "research_for_chapters": [13]},
        {"tool": "search_report", "year": 2025, "gate_eligible": True,
         "document_id": "DOC:2025", "verification_eligible": True,
         "research_for_chapters": [13]},
    ]
    agent._source_research_calls = base
    assert any("未实际读取 NOTES" in item for item in agent._source_research_missing(13))
    agent._source_research_calls = base + [
        {"tool": "read_section", "section": "NOTES", "year": 2025,
         "gate_eligible": False, "research_for_chapters": [13]},
    ]
    assert agent._source_research_missing(13) == []
    agent._persist_research_execution(13)
    entry = json.loads((tmp_path / "research_execution.json").read_text(encoding="utf-8"))["chapters"]["13"]
    assert entry["locally_unavailable_sections"] == ["NOTES"]
    assert entry["coverage_warnings"]


def test_persisted_research_execution_excludes_unrelated_calls(tmp_path: Path) -> None:
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(output_dir=str(tmp_path), run_id="run-1", source_deepening=True),
    )
    agent._source_research_calls = [
        {"tool": "read_section", "section": "GOV", "year": 2025, "research_for_chapters": [8], "attribution": "explicit"},
        {"tool": "read_section", "section": "NOTES", "year": 2024, "research_for_chapters": [8], "attribution": "explicit"},
        {"tool": "web_search", "query": "接班", "research_for_chapters": [8], "attribution": "explicit"},
        {"tool": "web_search", "query": "激励", "research_for_chapters": [8], "attribution": "explicit"},
        {"tool": "web_fetch", "url": "https://example.com/gov", "research_for_chapters": [8], "attribution": "explicit"},
        {"tool": "web_search", "query": "行业规模", "research_for_chapters": [2], "attribution": "explicit"},
    ]

    agent._persist_research_execution(8)
    entry = json.loads((tmp_path / "research_execution.json").read_text(encoding="utf-8"))["chapters"]["8"]
    assert entry["tool_counts"]["web_search"] == 2
    assert entry["search_queries"] == ["接班", "激励"]
    assert entry["attribution_modes"] == ["explicit"]


def test_new_pipeline_run_resets_stale_research_ledger(tmp_path: Path) -> None:
    stale = {
        "version": 2,
        "run_id": "old-run",
        "enforced": True,
        "expected_chapters": [1],
        "chapters": {"1": {"enforced": True, "missing_sections": []}},
    }
    (tmp_path / "research_execution.json").write_text(json.dumps(stale), encoding="utf-8")
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        ToolRegistry(),
        AgentConfig(
            output_dir=str(tmp_path),
            run_id="new-run",
            repair_targets=(2,),
            source_deepening=True,
        ),
    )

    agent._initialize_research_execution()
    payload = json.loads((tmp_path / "research_execution.json").read_text(encoding="utf-8"))

    assert payload["run_id"] == "new-run"
    assert payload["expected_chapters"] == [2]
    assert payload["chapters"] == {}


def test_registered_lowercase_web_search_executes_locally(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "web_search",
        lambda **kwargs: calls.append(kwargs) or {
            "results": [{"title": "官方资料", "url": "https://example.com", "snippet": "事实"}],
            "source": "web_search",
        },
        parameters={"query": {"type": "string"}},
    )
    agent = TurtleAgent(_DummyLlm(), registry, AgentConfig(output_dir=str(tmp_path)))  # type: ignore[arg-type]

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="web",
        name="web_search",
        arguments={"query": "格力 渠道"},
    )]))

    assert calls == [{"query": "格力 渠道"}]
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["results"][0]["url"] == "https://example.com"


def test_source_deepening_cannot_assemble_before_every_target_passes(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "assemble_report",
        lambda **kwargs: calls.append(kwargs) or {"tool_name": "assemble_report"},
        parameters={},
    )
    agent = TurtleAgent(
        _DummyLlm(),  # type: ignore[arg-type]
        registry,
        AgentConfig(
            output_dir=str(tmp_path),
            repair_targets=(1, 2, 3),
            source_deepening=True,
        ),
    )
    agent._passed_chapters.update({1, 3})

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="early-assemble",
        name="assemble_report",
        arguments={},
    )]))

    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_synthesis_frozen"] is True


def test_short_writes_consume_per_pass_budget(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()

    def _write_chapter(**kwargs):
        calls.append(kwargs)
        return {"chapter_index": kwargs["chapter_index"], "short_content": True}

    registry.register(
        "write_chapter",
        _write_chapter,
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            code="TEST",
            output_dir=str(tmp_path),
            max_chapter_attempts_per_pass=2,
        ),
    )

    for idx in range(3):
        response = LlmResponse(
            tool_calls=[
                ToolCall(
                    id=f"call-{idx}",
                    name="write_chapter",
                    arguments={"chapter_index": 1, "content": "short"},
                )
            ]
        )
        agent._handle_tool_calls(response)

    assert len(calls) == 2
    assert agent._chapter_write_counts == {1: 2}
    final_payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert final_payload["value"]["attempt_budget_exhausted"] is True


def test_repair_config_carries_fresh_context_targets() -> None:
    config = AgentConfig(pass_name="repair-1", repair_targets=(2, 6, 12))

    assert config.pass_name == "repair-1"
    assert config.repair_targets == (2, 6, 12)
    assert config.max_chapter_attempts_per_pass == 2


def test_repair_iteration_budget_scales_with_target_scope() -> None:
    assert _repair_iteration_budget((11,), 40) == 11
    assert _repair_iteration_budget((2, 6, 11), 40) == 21
    assert _repair_iteration_budget(tuple(range(10)), 40) == 40
    assert _repair_iteration_budget((11, 12, 13, 14, 0), 100) == 61


def test_agent_run_metrics_track_tokens_and_first_attempts(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: {
            "chapter_index": kwargs["chapter_index"],
            "char_count": 4000,
            "depth": {"status": "PASS", "failures": []},
            "audit": {"passed": True, "verdict": "pass"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(output_dir=str(tmp_path)),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="write",
        name="write_chapter",
        arguments={"chapter_index": 3, "content": "content"},
    )]))
    agent._usage.update({"calls": 1, "input_tokens": 100, "output_tokens": 20})

    metrics = agent.run_metrics()

    assert metrics["usage"]["input_tokens"] == 100
    assert metrics["first_attempt_passed"] == 1
    assert metrics["first_attempt_hit_rate"] == 1.0
    assert metrics["rewrite_attempts"] == 0


def test_repair_pass_hard_freezes_non_target_chapters(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()

    def _write_chapter(**kwargs):
        calls.append(kwargs)
        return {"chapter_index": kwargs["chapter_index"]}

    registry.register(
        "write_chapter",
        _write_chapter,
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(output_dir=str(tmp_path), repair_targets=(2, 4, 5)),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="frozen",
        name="write_chapter",
        arguments={"chapter_index": 0, "content": "must not write"},
    )]))

    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["target_frozen"] is True


def test_non_decision_repair_hard_freezes_all_structured_synthesis(tmp_path: Path) -> None:
    for tool_name in (
        "write_decision_manifest", "write_decision_ledger",
        "write_claim_evidence_ledger", "write_valuation_model_ledger",
        "write_thesis_test_ledger", "write_decisive_question_findings",
        "write_insight_ledger", "write_judgment_review",
        "plan_judgment_research", "assemble_report",
    ):
        calls: list[dict] = []
        registry = ToolRegistry()
        registry.register(
            tool_name,
            lambda **kwargs: calls.append(kwargs) or {},
            parameters={},
        )
        agent = TurtleAgent(
            llm=_DummyLlm(),  # type: ignore[arg-type]
            tools=registry,
            config=AgentConfig(output_dir=str(tmp_path), repair_targets=(6, 8, 11)),
        )
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id="decision-frozen",
            name=tool_name,
            arguments={},
        )]))

        assert calls == []
        payload = json.loads(agent._messages[-1]["content"][0]["content"])
        assert payload["value"]["structured_synthesis_frozen"] is True


def test_synthesis_only_hard_freezes_chapter_writes(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_chapter", lambda **kwargs: calls.append(kwargs) or {},
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="synthesis-no-rewrite", name="write_chapter",
        arguments={"chapter_index": 14, "content": "attempted rewrite"},
    )]))
    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["synthesis_only"] is True


def test_identical_structured_rejection_twice_halts_paid_pass(tmp_path: Path) -> None:
    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    registry = ToolRegistry()
    registry.register(
        "write_valuation_model_ledger",
        lambda **kwargs: {
            "written": False,
            "validation": {
                "state": "INVALID",
                "invalid_findings": ["bridge_mismatch"],
                "incomplete_findings": ["valuation_reference_missing:Ch12:model"],
            },
        },
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    for call_id in ("reject-1", "reject-2"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id, name="write_valuation_model_ledger", arguments={},
        )]))
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_no_progress"] is True
    assert agent._assembled_this_pass is True
    assert "连续两次" in agent._structured_no_progress_error


def test_identical_decisive_findings_rejection_twice_halts_paid_pass(tmp_path: Path) -> None:
    for name in ("claim_evidence", "valuation_model", "thesis_test"):
        (tmp_path / f"{name}_validation.json").write_text(
            json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
        )
    registry = ToolRegistry()
    registry.register(
        "write_decisive_question_findings",
        lambda **kwargs: {
            "written": False,
            "validation": {
                "state": "INVALID",
                "invalid_findings": ["DQ:sample:decision_changed_not_boolean"],
                "incomplete_findings": [],
            },
        },
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    for call_id in ("decisive-reject-1", "decisive-reject-2"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id, name="write_decisive_question_findings", arguments={},
        )]))
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_no_progress"] is True
    assert "write_decisive_question_findings" in agent._structured_no_progress_error


def test_successful_initial_structured_frontier_stops_before_downstream(tmp_path: Path) -> None:
    (tmp_path / "decision_manifest.json").write_text(
        json.dumps({"decision_id": "DEC:test"}), encoding="utf-8"
    )
    for name in (
        "decision_ledger", "claim_evidence", "valuation_model",
        "decision_reliability", "financial_driver_bridge", "thesis_test",
    ):
        (tmp_path / f"{name}_validation.json").write_text(
            json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
        )
    (tmp_path / "decisive_question_findings_validation.json").write_text(
        json.dumps({"state": "INVALID"}), encoding="utf-8"
    )
    registry = ToolRegistry()
    registry.register(
        "write_decisive_question_findings",
        lambda **kwargs: {
            "written": True,
            "validation": {"state": "DECISION_READY", "invalid_findings": [], "incomplete_findings": []},
        },
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(), tools=registry,  # type: ignore[arg-type]
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="decisive-pass", name="write_decisive_question_findings", arguments={},
    )]))

    assert agent._initial_structured_frontier == "write_decisive_question_findings"
    assert agent._structured_frontier_completed is True
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["frontier_completed"] is True


def test_identical_judgment_rejection_twice_halts_paid_pass(tmp_path: Path) -> None:
    (tmp_path / "insight_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    registry = ToolRegistry()
    registry.register(
        "write_judgment_review",
        lambda **kwargs: {
            "written": False,
            "validation": {
                "state": "INVALID",
                "invalid_findings": ["dimension_assessments:question_selection:state_invalid"],
                "incomplete_findings": [],
            },
        },
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    for call_id in ("judgment-reject-1", "judgment-reject-2"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id, name="write_judgment_review", arguments={},
        )]))
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_no_progress"] is True
    assert "write_judgment_review" in agent._structured_no_progress_error


def test_identical_judgment_task_completion_rejection_halts_paid_pass(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "complete_judgment_research_task",
        lambda **kwargs: {"completed": False, "error": "task_not_active"},
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    for call_id in ("task-complete-reject-1", "task-complete-reject-2"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id, name="complete_judgment_research_task", arguments={},
        )]))
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_no_progress"] is True
    assert "complete_judgment_research_task" in agent._structured_no_progress_error


def test_chapter_binding_failure_cannot_mark_repair_target_passed(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: {
            "path": str(tmp_path / "chapters" / "_ch12.md"),
            "chapter_index": 12,
            "char_count": 1200,
            "audit": {"passed": True, "verdict": "pass"},
            "depth": {"status": "PASS", "failures": []},
            "passed": False,
            "error": "canonical binding failed",
            "decision_binding_validation": {
                "state": "INVALID",
                "invalid_findings": ["free_critical_value:Ch12:L22:valuation.v_final"],
            },
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(output_dir=str(tmp_path), repair_targets=(12,)),
    )
    agent._chapter_contract_reads.add(12)
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="binding-failed", name="write_chapter",
        arguments={"chapter_index": 12, "content": "## Ch12\n\nbody"},
    )]))
    assert 12 not in agent._passed_chapters
    assert agent._chapter_attempt_log[-1]["passed"] is False
    assert agent._chapter_attempt_log[-1]["decision_binding_state"] == "INVALID"


def test_structured_dependency_guard_prevents_skipping_incomplete_claim_ledger(tmp_path: Path) -> None:
    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps({"state": "INCOMPLETE"}), encoding="utf-8"
    )
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_valuation_model_ledger",
        lambda **kwargs: calls.append(kwargs) or {"written": True},
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="out-of-order", name="write_valuation_model_ledger", arguments={},
    )]))
    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["structured_dependency_guard"] is True
    assert payload["value"]["unmet_prerequisites"] == ["claim_evidence_validation.json:INCOMPLETE"]


def test_structured_dependency_allows_claims_waiting_only_for_derived_chapters(tmp_path: Path) -> None:
    (tmp_path / "claim_evidence_validation.json").write_text(json.dumps({
        "state": "INCOMPLETE", "invalid_findings": [],
        "incomplete_findings": [
            "claim_reference_missing:Ch0:CLM:a",
            "claim_reference_missing:Ch14:CLM:a",
        ],
        "required_chapters": [0, 14], "covered_chapters": [0, 14],
    }), encoding="utf-8")
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_valuation_model_ledger",
        lambda **kwargs: calls.append(kwargs) or {
            "written": True,
            "validation": {"state": "DECISION_READY"},
        },
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(), tools=registry,  # type: ignore[arg-type]
        config=AgentConfig(output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="valuation-after-provisional-claims",
        name="write_valuation_model_ledger", arguments={},
    )]))
    assert len(calls) == 1


def test_insight_dependency_uses_findings_gate_not_question_plan_gate(tmp_path: Path) -> None:
    (tmp_path / "thesis_test_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    (tmp_path / "decisive_question_validation.json").write_text(
        json.dumps({"state": "REVIEWABLE"}), encoding="utf-8"
    )
    (tmp_path / "decisive_question_findings_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_insight_ledger",
        lambda **kwargs: calls.append(kwargs) or {"written": True},
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="insight-after-findings", name="write_insight_ledger", arguments={},
    )]))
    assert len(calls) == 1
    assert calls[0]["output_dir"] == str(tmp_path)


def test_insight_dependency_blocks_when_findings_gate_is_missing(tmp_path: Path) -> None:
    (tmp_path / "thesis_test_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    (tmp_path / "decisive_question_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_insight_ledger",
        lambda **kwargs: calls.append(kwargs) or {"written": True},
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="insight-without-findings", name="write_insight_ledger", arguments={},
    )]))
    assert calls == []
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["unmet_prerequisites"] == [
        "decisive_question_findings_validation.json:MISSING"
    ]


def test_successful_assemble_marks_pass_terminal(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "assemble_report",
        lambda **kwargs: {"tool_name": "assemble_report", "completion": {"status": "BLOCKED"}},
        parameters={},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(output_dir=str(tmp_path)),
    )
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="assemble",
        name="assemble_report",
        arguments={},
    )]))

    assert agent._assembled_this_pass is True


def test_repair_prompt_keeps_only_target_chapter_contracts() -> None:
    template = """# V13
## 投资要点概览
overview rules
## 行业吸引力与公司位置
industry rules
## 经营表现与核心驱动
operation rules
## 综合决策
decision rules
"""

    selected = _template_sections_for_targets(template, (2, 0))

    assert "## 行业吸引力与公司位置" in selected
    assert "industry rules" in selected
    assert "## 投资要点概览" in selected
    assert "overview rules" in selected
    assert "经营表现与核心驱动" not in selected
    assert "综合决策" not in selected


def test_force_rewrite_is_available_but_optional_in_tool_schema() -> None:
    registry = ToolRegistry()
    registry.auto_discover("scripts.turtle_agent.tools.write_tools")
    schema = next(
        item["function"]["parameters"]
        for item in registry.get_schemas()
        if item["function"]["name"] == "write_chapter"
    )

    assert "force_rewrite" in schema["properties"]
    assert "force_rewrite" not in schema["required"]


def test_v13_chapter_depth_identity_has_one_source_of_truth() -> None:
    from scripts.chapter_depth import QUANTITATIVE_CHAPTER_INDEXES, depth_requirements

    assert QUANTITATIVE_CHAPTER_INDEXES == {10, 11, 12, 13, 14}
    assert depth_requirements(9)["min_substantive_chars"] == 10
    assert depth_requirements(10)["min_substantive_chars"] == 10
    assert depth_requirements(14)["min_derivation_lines"] == 0
    assert depth_requirements(10, data_rich=True) == depth_requirements(10)


def test_av_method_accepts_summary_before_full_incremental_formula() -> None:
    from scripts.turtle_agent.tools.write_tools import _audit_content

    filler = "\n".join(f"补充分析行 {idx}" for idx in range(35))
    content = f"""## Ch12 内在价值合成与裁决
综合派 V_final；V_cash；回报安全边际。
AV_going = 1,538M（摘要值）。
货币资金、应收账款、存货、固定资产均已逐行重估。
{filler}
归母净资产(账面)=1,421M 为基地。
AV_going = 归母净资产(账面) − 账面虚项 + Σ有形重置增量 + 表外无形重建
"""

    audit = _audit_content(content, chapter_index=12)
    rules = {item["rule"] for item in audit.get("violations", [])}
    assert "GRAHAM_AV_METHOD" not in rules


def test_p_base_gg_equals_ii_label_is_not_classified_as_gg() -> None:
    from scripts.report_audit import extract_data_points

    points = extract_data_points("| P_base（GG=II 公允价） | 2.28 HKD | source |")

    assert points[0]["inferred_field"] == "P_BASE"
