from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from scripts.run_budget_guard import NoProgressCircuitBreaker, build_run_preflight
from scripts.runtime_governance import BudgetExhausted, RuntimeController, load_runtime_config
from scripts.turtle_agent.agent_loop import AgentConfig
from scripts.turtle_agent.agent_loop import TurtleAgent
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.run import (
    _scheduled_repair_passes,
    _should_use_synthesis_only,
    _structured_frontier_pending,
)


def test_expensive_real_run_requires_explicit_approval(tmp_path: Path) -> None:
    policy = load_runtime_config()["execution_guard"]
    result = build_run_preflight(
        output_dir=tmp_path, max_iterations=80, repair_passes=6,
        repair_max_iterations=40, repair_only=False, dry_run=False,
        approved=False, policy=policy,
    )
    assert result["status"] == "APPROVAL_REQUIRED"
    assert result["estimate"]["max_llm_calls"] == 320
    assert result["reasons"]


def test_approval_is_explicit_but_does_not_remove_hard_limits(tmp_path: Path) -> None:
    policy = load_runtime_config()["execution_guard"]
    result = build_run_preflight(
        output_dir=tmp_path, max_iterations=80, repair_passes=6,
        repair_max_iterations=40, repair_only=False, dry_run=False,
        approved=True, policy=policy,
    )
    assert result["status"] == "APPROVED"
    assert result["limits"]["max_wall_minutes"] == 60


def test_second_real_run_for_same_output_requires_approval(tmp_path: Path) -> None:
    manifests = tmp_path / "run_manifests"
    manifests.mkdir()
    (manifests / "old.json").write_text(json.dumps({"usage": {"calls": 1}}), encoding="utf-8")
    policy = load_runtime_config()["execution_guard"]
    result = build_run_preflight(
        output_dir=tmp_path, max_iterations=1, repair_passes=0,
        repair_max_iterations=1, repair_only=False, dry_run=False,
        approved=False, policy=policy,
    )
    assert result["status"] == "APPROVAL_REQUIRED"
    assert "real_run_already_attempted_for_output" in result["reasons"]


def test_zero_call_validation_closeout_never_requires_paid_run_approval(
    tmp_path: Path,
) -> None:
    manifests = tmp_path / "run_manifests"
    manifests.mkdir()
    (manifests / "old.json").write_text(
        json.dumps({"usage": {"calls": 99}}), encoding="utf-8",
    )
    policy = load_runtime_config()["execution_guard"]

    result = build_run_preflight(
        output_dir=tmp_path, max_iterations=80, repair_passes=0,
        repair_max_iterations=40, repair_only=True, dry_run=False,
        approved=False, policy=policy,
    )

    assert result["status"] == "SAFE"
    assert result["estimate"]["max_llm_calls"] == 0
    assert result["reasons"] == []


def test_no_progress_breaker_trips_after_two_unchanged_passes() -> None:
    guard = NoProgressCircuitBreaker(max_no_progress_passes=2)
    assert not guard.observe(["Ch3 missing evidence"])["tripped"]
    assert not guard.observe(["Ch3   missing evidence"])["tripped"]
    result = guard.observe(["Ch3 missing evidence"])
    assert result["tripped"]
    assert result["resolved_count"] == 0


def test_progress_resets_no_progress_streak() -> None:
    guard = NoProgressCircuitBreaker(max_no_progress_passes=2)
    guard.observe(["A", "B"])
    guard.observe(["A", "B"])
    result = guard.observe(["B"])
    assert result["no_progress_streak"] == 0
    assert result["resolved_count"] == 1


def test_uncached_input_budget_is_fail_closed(tmp_path: Path) -> None:
    controller = RuntimeController(
        output_dir=tmp_path, run_id="r", company_code="c", period="p", mode="unified"
    )
    controller.config["budget"]["max_uncached_input_tokens"] = 1
    with pytest.raises(BudgetExhausted):
        controller.prepare_call(
            model="deepseek-v4-pro", messages=[{"role": "user", "content": "long input"}],
            tools=None, temperature=0.2, max_tokens=1,
        )


def test_wall_clock_budget_is_fail_closed(tmp_path: Path) -> None:
    controller = RuntimeController(
        output_dir=tmp_path, run_id="r", company_code="c", period="p", mode="unified"
    )
    controller.config["execution_guard"]["max_wall_minutes"] = 0.001
    controller._started_monotonic = time.monotonic() - 1
    with pytest.raises(BudgetExhausted):
        controller.prepare_call(
            model="deepseek-v4-pro", messages=[{"role": "user", "content": "x"}],
            tools=None, temperature=0.2, max_tokens=1,
        )


def test_synthesis_only_is_an_explicit_agent_capability() -> None:
    config = AgentConfig(repair_targets=(14, 0), synthesis_only=True)
    assert config.synthesis_only is True


def _write_structured_states(tmp_path: Path, *, valuation: str) -> None:
    states = {
        "claim_evidence_validation.json": "DECISION_READY",
        "valuation_model_validation.json": valuation,
        "decision_reliability_validation.json": (
            "DECISION_READY" if valuation == "DECISION_READY" else "INCOMPLETE"
        ),
        "thesis_test_validation.json": "DECISION_READY",
        "decisive_question_findings_validation.json": "DECISION_READY",
        "insight_validation.json": "DECISION_READY",
    }
    for filename, state in states.items():
        (tmp_path / filename).write_text(
            json.dumps({"state": state}), encoding="utf-8"
        )


def test_pending_structured_frontier_keeps_chapters_frozen(tmp_path: Path) -> None:
    _write_structured_states(tmp_path, valuation="INVALID")
    completion = {
        "blocking_findings": ["Quality hard contract: failure in Ch0,Ch14"]
    }
    assert _should_use_synthesis_only(
        str(tmp_path), (14, 0), binding_only=False, completion=completion
    )


def test_pending_structured_frontier_precedes_derived_chapter_targets(
    tmp_path: Path,
) -> None:
    _write_structured_states(tmp_path, valuation="DECISION_READY")
    (tmp_path / "decisive_question_findings_validation.json").write_text(
        json.dumps({"state": "INVALID"}), encoding="utf-8"
    )
    completion = {
        "blocking_findings": [
            "Decisive questions: INVALID: premise_resolution_invalid",
            "Quality hard contract: failure in Ch12,Ch14,Ch0",
        ]
    }
    assert _should_use_synthesis_only(
        str(tmp_path), (12, 14, 0), binding_only=False, completion=completion
    )


def test_real_chapter_blocker_reopens_prose_only_after_structured_gates_pass(
    tmp_path: Path,
) -> None:
    _write_structured_states(tmp_path, valuation="DECISION_READY")
    completion = {"blocking_findings": ["Chapter depth: failure in Ch14"]}
    assert not _should_use_synthesis_only(
        str(tmp_path), (14, 0), binding_only=False, completion=completion
    )


def test_fresh_build_repairs_real_ordinary_chapters_before_structured_frontier(
    tmp_path: Path,
) -> None:
    _write_structured_states(tmp_path, valuation="INCOMPLETE")
    completion = {
        "blocking_findings": ["Ch4: short_depth:evidence_anchors:6<12"],
        "chapter_results": [{
            "index": 4,
            "blocking_rules": ["short_depth:evidence_anchors:6<12"],
        }],
    }
    assert not _should_use_synthesis_only(
        str(tmp_path), (4,), binding_only=False, completion=completion
    )


def test_report_owned_reliability_failure_reopens_its_chapter(tmp_path: Path) -> None:
    _write_structured_states(tmp_path, valuation="INVALID")
    completion = {"blocking_findings": [
        "Decision reliability: INVALID: "
        "maximum_balance_cannot_be_used_as_average_yield_denominator"
    ]}
    from scripts.turtle_agent.run import _repair_targets_from_completion

    targets = _repair_targets_from_completion(completion)
    assert 8 in targets
    assert not _should_use_synthesis_only(
        str(tmp_path), targets, binding_only=False, completion=completion
    )


def test_report_owned_model_comparison_defect_preempts_derived_quality_targets() -> None:
    from scripts.turtle_agent.run import _repair_targets_for_pass

    completion = {
        "blocking_findings": [
            "Decision reliability: INVALID: "
            "model_comparison:M:DDM:v1:report_overstates_noncomparable_model",
            "Quality hard contract: failure in Ch4,Ch8,Ch11,Ch12,Ch13,Ch14",
        ],
        "chapter_results": [
            {"index": idx, "blocking_rules": ["derived_structured_failure"]}
            for idx in (4, 8, 11, 12, 13, 14)
        ],
    }
    assert _repair_targets_for_pass(completion, 1, 6) == (11, 12, 13)


def test_repair_batches_prioritize_missing_chapters_over_stubborn_residuals() -> None:
    from scripts.turtle_agent.run import _repair_targets_for_pass

    completion = {
        "blocking_findings": [
            "Ch4: short_depth:evidence_anchors:11<12",
            "Ch11: missing_file", "Ch12: missing_file", "Ch13: missing_file",
        ],
        "chapter_results": [
            {"index": 4, "blocking_rules": ["short_depth:evidence_anchors:11<12"]},
            {"index": 11, "blocking_rules": ["missing_file"]},
            {"index": 12, "blocking_rules": ["missing_file"]},
            {"index": 13, "blocking_rules": ["missing_file"]},
        ],
    }
    assert _repair_targets_for_pass(completion, 1, 6) == (11, 12, 13, 4)


def test_fresh_closeout_blockers_reopen_bounded_repair_budget() -> None:
    stale_complete = {"status": "COMPLETE", "blocking_findings": []}
    assert _scheduled_repair_passes(stale_complete, requested=6) == 0

    freshly_revalidated = {
        "status": "INVALID",
        "blocking_findings": ["Claim evidence: INVALID: verified_observation_required"],
    }
    assert _scheduled_repair_passes(freshly_revalidated, requested=6) == 6


def test_synthesis_repair_exposes_only_first_unmet_structured_writer(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps({"state": "INVALID"}), encoding="utf-8"
    )
    (tmp_path / "valuation_model_validation.json").write_text(
        json.dumps({"state": "INVALID"}), encoding="utf-8"
    )
    agent = TurtleAgent(
        llm=object(), tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True
        ),
    )

    names = {
        item["function"]["name"] for item in agent._tool_schemas_for_stage()
    }
    assert "write_decision_manifest" in names
    assert "write_decision_ledger" not in names
    assert "write_claim_evidence_ledger" not in names
    assert "compute_bundle_db" not in names
    assert "run_pre_analysis" not in names

    (tmp_path / "decision_manifest.json").write_text(
        json.dumps({"qualitative_decision": "continue"}), encoding="utf-8"
    )
    (tmp_path / "decision_ledger_validation.json").write_text(
        json.dumps({"state": "INCOMPLETE"}), encoding="utf-8"
    )
    names = {
        item["function"]["name"] for item in agent._tool_schemas_for_stage()
    }
    assert "write_decision_manifest" not in names
    assert "write_decision_ledger" in names
    assert "write_claim_evidence_ledger" not in names

    (tmp_path / "decision_ledger_validation.json").write_text(
        json.dumps({
            "state": "INCOMPLETE",
            "invalid_findings": [],
            "incomplete_findings": [
                "enforced_ledger_not_frozen",
                "decision_reference_missing:Ch0:D001",
                "decision_reference_missing:Ch14:D001",
            ],
            "required_metric_ids": ["market.price.current"],
            "active_metric_ids": ["market.price.current"],
        }),
        encoding="utf-8",
    )
    names = {
        item["function"]["name"] for item in agent._tool_schemas_for_stage()
    }
    assert "write_claim_evidence_ledger" in names
    assert "write_valuation_model_ledger" not in names

    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    names = {
        item["function"]["name"] for item in agent._tool_schemas_for_stage()
    }
    assert "write_claim_evidence_ledger" not in names
    assert "write_valuation_model_ledger" in names


def test_valuation_frontier_hides_off_target_read_and_compute_tools(tmp_path: Path) -> None:
    (tmp_path / "decision_manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "decision_ledger_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    registry = ToolRegistry()
    for name in (
        "write_valuation_model_ledger", "read_structured_ledger_contract",
        "read_valuation_route", "read_evidence_context", "read_section",
        "compute_aa", "compute_gg", "read_chapter", "read_report_contract_pack",
        "web_search", "compute_bundle_db", "write_chapter",
    ):
        registry.register(name, lambda **kwargs: kwargs, parameters={})
    agent = TurtleAgent(
        llm=object(), tools=registry,
        config=AgentConfig(
            output_dir=str(tmp_path), repair_targets=(14, 0), synthesis_only=True,
        ),
    )
    names = {item["function"]["name"] for item in agent._tool_schemas_for_stage()}
    assert "write_valuation_model_ledger" in names
    assert "read_structured_ledger_contract" in names
    assert "compute_gg" in names
    assert "read_chapter" not in names
    assert "read_report_contract_pack" not in names
    assert "web_search" not in names
    assert "compute_bundle_db" not in names
    assert "write_chapter" not in names


def test_prose_repair_hides_compute_bundle_mutators(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for name in ("write_chapter", "compute_bundle_db", "run_pre_analysis", "read_section"):
        registry.register(name, lambda **kwargs: kwargs, parameters={})
    agent = TurtleAgent(
        llm=object(), tools=registry,
        config=AgentConfig(output_dir=str(tmp_path), repair_targets=(13,)),
    )

    names = {item["function"]["name"] for item in agent._tool_schemas_for_stage()}
    assert "write_chapter" in names
    assert "read_section" in names
    assert "compute_bundle_db" not in names
    assert "run_pre_analysis" not in names


def test_reviewable_claim_ledger_advances_until_derived_chapters_exist(
    tmp_path: Path,
) -> None:
    (tmp_path / "decision_manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "decision_ledger_validation.json").write_text(
        json.dumps({"state": "DECISION_READY"}), encoding="utf-8"
    )
    claim_validation = {
        "state": "INCOMPLETE",
        "invalid_findings": [],
        "incomplete_findings": [
            "claim_reference_missing:Ch0:CLM:a",
            "claim_reference_missing:Ch14:CLM:a",
        ],
        "required_chapters": [0, 14],
        "covered_chapters": [0, 14],
    }
    (tmp_path / "claim_evidence_validation.json").write_text(
        json.dumps(claim_validation), encoding="utf-8"
    )
    (tmp_path / "valuation_model_validation.json").write_text(
        json.dumps({"state": "INVALID"}), encoding="utf-8"
    )
    agent = TurtleAgent(
        llm=object(), tools=ToolRegistry(),
        config=AgentConfig(output_dir=str(tmp_path), synthesis_only=True),
    )
    assert agent._structured_repair_frontier()[0] == "write_valuation_model_ledger"
    assert _structured_frontier_pending(str(tmp_path))

    for chapter in (0, 14):
        path = tmp_path / "chapters" / f"_ch{chapter:02d}.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"## Ch{chapter}", encoding="utf-8")
    assert agent._structured_repair_frontier()[0] == "write_claim_evidence_ledger"
