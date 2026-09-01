from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.decision_ledger import (
    CANONICAL_METRIC_IDS,
    _line_supports_entry,
    build_decision_ledger,
    evaluate_output_decision_ledger,
    initialize_decision_ledger_policy,
    persist_decision_ledger,
    preview_decision_revision,
    promote_reviewable_decision_ledger,
    validate_decision_ledger,
)
from scripts.report_completion import evaluate_report_completion
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.write_tools import write_decision_manifest


VALUES = {
    "market.price.current": (37.34, "RMB/share"),
    "return.gg.base": (7.4, "percent"),
    "return.gg.fcfe": (10.9, "percent"),
    "return.gg.normalized": (7.4, "percent"),
    "hurdle.ii": (4.5, "percent"),
    "valuation.v_final": (49.68, "RMB/share"),
    "moat.lambda": (0.475, "ratio"),
    "return.required": (10.0, "percent"),
    "moat.decay": (3.2, "percent"),
    "margin.price": (24.8, "percent"),
    "margin.return": (-3.3, "pp"),
    "decision.position.recommended": (5.0, "percent"),
    "trigger.buy": ("price<=34.8", "rule"),
    "trigger.reduce": ("gross_margin<30", "rule"),
    "trigger.exit": ("audit_opinion_changes", "rule"),
}


def _write_manifest(output: Path) -> dict:
    result = write_decision_manifest(
        output_dir=str(output),
        qualitative_decision="continue",
        quantitative_decision="hold",
        position_pct=5.0,
    )
    return result["manifest"]


def _entries(*, chapters: list[int] | None = None) -> list[dict]:
    result = []
    for metric_id in sorted(CANONICAL_METRIC_IDS):
        value, unit = VALUES[metric_id]
        result.append({
            "entry_id": metric_id + "@base.current",
            "metric_id": metric_id,
            "value": value,
            "unit": unit,
            "scenario": "base",
            "basis": "canonical",
            "as_of": "2026-08-02",
            "version": 1,
            "status": "active",
            "chapters": list(chapters or []),
            "source_ids": ["compute_bundle.json"],
            "affects_action": metric_id in {
                "valuation.v_final",
                "return.required",
                "moat.decay",
                "margin.price",
                "margin.return",
                "decision.position.recommended",
                "trigger.buy",
                "trigger.reduce",
                "trigger.exit",
            },
        })
    return result


def _ledger(output: Path, entries: list[dict] | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    _write_manifest(output)
    return build_decision_ledger(
        output,
        entries or _entries(),
        change_reason="initial analysis",
        freeze=True,
    )


def _bound_report(entries: list[dict]) -> str:
    labels = {
        "market.price.current": "当前价",
        "return.gg.base": "GG(AA口径)",
        "return.gg.fcfe": "GG(FCFE口径)",
        "return.gg.normalized": "GG(Normalized口径)",
        "hurdle.ii": "II=",
        "valuation.v_final": "V_final=",
        "moat.lambda": "λ=",
        "return.required": "要求回报率",
        "moat.decay": "护城河衰减",
        "margin.price": "价格安全边际",
        "margin.return": "回报安全边际",
        "decision.position.recommended": "建议仓位",
        "trigger.buy": "首次买入条件",
        "trigger.reduce": "减仓触发",
        "trigger.exit": "退出条件",
    }
    lines = ["## Ch0 投资要点概览"]
    for entry in entries:
        lines.append(
            f"{labels[entry['metric_id']]} {entry['value']} {entry['unit']} "
            f"[decision: {entry['entry_id']}]"
        )
    return "\n".join(lines)


def test_v3_schema_files_and_valid_fixture(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (
        "decision_ledger.schema.json",
        "claim_evidence.schema.json",
        "competitive_explanation.schema.json",
    ):
        schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema["required"]

    payload = _ledger(tmp_path)
    result = validate_decision_ledger(payload, manifest=_write_manifest(tmp_path), enforced=True)

    assert result["state"] == "DECISION_READY"
    assert result["invalid_findings"] == []
    assert result["incomplete_findings"] == []


def test_invalid_fixture_rejects_unknown_metric_and_missing_identity(tmp_path: Path) -> None:
    payload = _ledger(tmp_path)
    payload["entries"][0]["metric_id"] = "invented.metric"
    payload["entries"][0]["basis"] = ""

    result = validate_decision_ledger(payload, manifest=_write_manifest(tmp_path), enforced=True)

    assert result["state"] == "INVALID"
    assert "unknown_metric_id:invented.metric" in result["invalid_findings"]
    assert any("basis_missing" in item for item in result["invalid_findings"])


def test_unexplained_same_identity_conflict_is_invalid(tmp_path: Path) -> None:
    entries = _entries()
    conflicting = deepcopy(next(item for item in entries if item["metric_id"] == "valuation.v_final"))
    conflicting["entry_id"] = "valuation.v_final@conflicting.current"
    conflicting["value"] = 70.4
    entries.append(conflicting)
    payload = _ledger(tmp_path, entries)

    result = validate_decision_ledger(payload, manifest=_write_manifest(tmp_path), enforced=True)

    assert result["state"] == "INVALID"
    assert any("unexplained_conflict:valuation.v_final" in item for item in result["invalid_findings"])


def test_explicit_scenario_date_and_basis_differences_are_allowed(tmp_path: Path) -> None:
    entries = _entries()
    base = next(item for item in entries if item["metric_id"] == "valuation.v_final")
    bear = deepcopy(base)
    bear.update({
        "entry_id": "valuation.v_final@bear.current",
        "value": 42.99,
        "scenario": "bear",
    })
    historical = deepcopy(base)
    historical.update({
        "entry_id": "valuation.v_final@base.previous",
        "value": 70.4,
        "as_of": "2025-12-31",
        "version": 2,
    })
    epv = deepcopy(base)
    epv.update({
        "entry_id": "valuation.v_final@epv.current",
        "value": 45.0,
        "basis": "epv_only",
    })
    payload = _ledger(tmp_path, entries + [bear, historical, epv])

    result = validate_decision_ledger(payload, manifest=_write_manifest(tmp_path), enforced=True)

    assert result["state"] == "DECISION_READY"


def test_deprecated_value_does_not_pollute_active_decision(tmp_path: Path) -> None:
    entries = _entries()
    active = next(item for item in entries if item["metric_id"] == "return.required")
    old = deepcopy(active)
    old.update({
        "entry_id": "return.required@old.current",
        "value": 7.5,
        "status": "deprecated",
        "deprecation_reason": "old discount-rate convention",
        "superseded_by": active["entry_id"],
    })
    payload = _ledger(tmp_path, entries + [old])

    result = validate_decision_ledger(payload, manifest=_write_manifest(tmp_path), enforced=True)

    assert result["state"] == "DECISION_READY"


def test_report_references_bind_values_and_detect_mismatch(tmp_path: Path) -> None:
    entries = _entries(chapters=[0])
    payload = _ledger(tmp_path, entries)
    report = _bound_report(entries)

    passed = validate_decision_ledger(
        payload,
        report_text=report,
        manifest=_write_manifest(tmp_path),
        enforced=True,
    )
    assert passed["state"] == "DECISION_READY"

    mismatched = report.replace(
        "V_final= 49.68",
        "V_final= 70.4",
    )
    failed = validate_decision_ledger(
        payload,
        report_text=mismatched,
        manifest=_write_manifest(tmp_path),
        enforced=True,
    )
    assert failed["state"] == "INVALID"
    assert any("decision_value_mismatch" in item for item in failed["invalid_findings"])


def test_decision_revision_preview_never_writes_partial_manifest_or_ledger(tmp_path: Path) -> None:
    initial = _ledger(tmp_path, _entries(chapters=[0]))
    assert persist_decision_ledger(tmp_path, initial)["written"] is True
    manifest_before = (tmp_path / "decision_manifest.json").read_bytes()
    ledger_before = (tmp_path / "decision_ledger.json").read_bytes()
    proposed_manifest = dict(_write_manifest(tmp_path))
    proposed_manifest.update({
        "quantitative_decision": "avoid", "position_pct": 0.0,
        "unified_decision": "avoid", "display_label": "好公司太贵",
        "decision_family": "Avoid",
    })
    entries = _entries(chapters=[0])
    next(item for item in entries if item["metric_id"] == "valuation.v_final")["value"] = 42.99
    preview = preview_decision_revision(
        tmp_path, manifest=proposed_manifest, entries=entries,
        change_reason="candidate action revision",
        report_text=_bound_report(_entries(chapters=[0])),
    )
    assert preview["canonical_files_written"] is False
    assert preview["state"] == "CONTENT_PROPAGATION_REQUIRED"
    assert preview["diff"]["changes_action"] is True
    assert any("decision_value_mismatch" in item for item in preview["validation"]["invalid_findings"])
    assert (tmp_path / "decision_manifest.json").read_bytes() == manifest_before
    assert (tmp_path / "decision_ledger.json").read_bytes() == ledger_before


def test_unbound_critical_claim_is_incomplete(tmp_path: Path) -> None:
    entries = _entries()
    payload = _ledger(tmp_path, entries)
    report = "## Ch12 估值\nV_final=49.68元，但另一章未绑定canonical ID。"

    result = validate_decision_ledger(
        payload,
        report_text=report,
        manifest=_write_manifest(tmp_path),
        enforced=True,
    )

    assert result["state"] == "INCOMPLETE"
    assert any("unbound_critical_claim" in item for item in result["incomplete_findings"])


def test_frozen_ledger_rejects_local_drift_and_persists_diff(tmp_path: Path) -> None:
    initial = _ledger(tmp_path)
    first = persist_decision_ledger(tmp_path, initial)
    assert first["written"] is True

    changed_entries = _entries()
    next(item for item in changed_entries if item["metric_id"] == "valuation.v_final")["value"] = 42.99
    attempted = build_decision_ledger(
        tmp_path,
        changed_entries,
        change_reason="local repair attempted to change valuation",
        freeze=True,
    )
    rejected = persist_decision_ledger(tmp_path, attempted)

    assert rejected["written"] is False
    assert rejected["decision_frozen"] is True
    persisted = json.loads((tmp_path / "decision_ledger.json").read_text(encoding="utf-8"))
    v_final = next(item for item in persisted["entries"] if item["metric_id"] == "valuation.v_final")
    assert v_final["value"] == 49.68
    diff = json.loads((tmp_path / "decision_diff.json").read_text(encoding="utf-8"))
    assert diff["status"] == "REJECTED_FROZEN"
    assert diff["changes_action"] is True


def test_frozen_ledger_allows_idempotent_rewrite_without_mutation(tmp_path: Path) -> None:
    initial = _ledger(tmp_path)
    assert persist_decision_ledger(tmp_path, initial)["written"] is True
    before = (tmp_path / "decision_ledger.json").read_text(encoding="utf-8")

    same = _ledger(tmp_path)
    result = persist_decision_ledger(tmp_path, same)

    assert result["written"] is True
    assert result["diff"]["status"] == "NO_CHANGE"
    assert (tmp_path / "decision_ledger.json").read_text(encoding="utf-8") == before


def test_enforced_incomplete_ledger_cannot_be_frozen(tmp_path: Path) -> None:
    initialize_decision_ledger_policy(tmp_path, run_id="new-run", enforced=True)
    entries = _entries()
    entries.pop()
    payload = _ledger(tmp_path, entries)

    result = persist_decision_ledger(tmp_path, payload)

    assert result["written"] is False
    assert result["validation"]["state"] == "INCOMPLETE"
    assert not (tmp_path / "decision_ledger.json").exists()


def test_frozen_ledger_also_rejects_manifest_drift(tmp_path: Path) -> None:
    payload = _ledger(tmp_path)
    assert persist_decision_ledger(tmp_path, payload)["written"] is True

    result = write_decision_manifest(
        output_dir=str(tmp_path),
        qualitative_decision="continue",
        quantitative_decision="buy",
        position_pct=8.0,
    )

    assert result["written"] is False
    assert result["decision_frozen"] is True
    manifest = json.loads((tmp_path / "decision_manifest.json").read_text(encoding="utf-8"))
    assert manifest["quantitative_decision"] == "hold"
    assert manifest["position_pct"] == 5.0


def test_new_unified_policy_requires_ledger_and_maps_completion_state(tmp_path: Path) -> None:
    initialize_decision_ledger_policy(tmp_path, run_id="new-unified-run", enforced=True)

    validation = evaluate_output_decision_ledger(tmp_path, persist=False)
    completion = evaluate_report_completion("draft", str(tmp_path))

    assert validation["state"] == "INCOMPLETE"
    assert validation["incomplete_findings"] == ["decision_ledger_missing"]
    assert completion.status == "INCOMPLETE"
    assert completion.validators["decision_ledger"]["state"] == "INCOMPLETE"


def test_invalid_ledger_maps_completion_to_invalid(tmp_path: Path) -> None:
    initialize_decision_ledger_policy(tmp_path, run_id="new-unified-run", enforced=True)
    payload = _ledger(tmp_path)
    payload["entries"][0]["metric_id"] = "invented.metric"
    (tmp_path / "decision_ledger.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    completion = evaluate_report_completion("draft", str(tmp_path))

    assert completion.status == "INVALID"
    assert completion.validators["decision_ledger"]["state"] == "INVALID"


def test_ch0_ch14_manifest_and_ledger_can_reach_complete(
    tmp_path: Path, monkeypatch
) -> None:
    import scripts.absolute_quality_scorecard as absolute_quality_scorecard
    import scripts.legacy_reference_regression as legacy_reference_regression
    import scripts.report_completion as report_completion

    manifest = _write_manifest(tmp_path)
    entries = _entries(chapters=[0, 14])
    bound = _bound_report(entries).split("\n", 1)[1]
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    for idx in range(15):
        if idx in {0, 14}:
            text = f"## Ch{idx} 标题\nCautious Watch\n{bound}"
        elif idx == 11:
            text = "## Ch11 标题\n参数 方法 AA 公式 情景 M HH 敏感 压力 AP 少数股东 λ 治理折价"
        else:
            text = f"## Ch{idx} 标题\n有效内容"
        (chapters / f"_ch{idx:02d}.md").write_text(text, encoding="utf-8")
    audit = {
        "chapters": {
            str(idx): {"final": {"passed": True, "verdict": "pass"}}
            for idx in range(15)
        }
    }
    (tmp_path / "chapter_audit_ledger.json").write_text(
        json.dumps(audit), encoding="utf-8"
    )
    initialize_decision_ledger_policy(tmp_path, run_id="valid-run", enforced=True)
    payload = build_decision_ledger(
        tmp_path, entries, change_reason="initial analysis", freeze=True
    )
    report = "\n\n".join(
        (chapters / f"_ch{idx:02d}.md").read_text(encoding="utf-8")
        for idx in range(15)
    )
    assert persist_decision_ledger(tmp_path, payload, report_text=report)["written"] is True

    monkeypatch.setattr(
        report_completion,
        "analyze_chapter_depth",
        lambda text, idx, data_rich=False: {"status": "PASS", "failures": []},
    )
    monkeypatch.setattr(
        legacy_reference_regression,
        "evaluate_from_config",
        lambda output_dir: {"status": "SKIP"},
    )
    monkeypatch.setattr(
        absolute_quality_scorecard,
        "evaluate_absolute_quality",
        lambda output_dir: {"status": "PASS", "failed_chapters": [], "warning_chapters": []},
    )

    completion = evaluate_report_completion(report, str(tmp_path))

    assert manifest["display_label"] in report
    assert completion.status == "COMPLETE"
    assert completion.validators["decision_ledger"]["state"] == "DECISION_READY"


def test_old_output_without_v3_policy_remains_compatible(tmp_path: Path) -> None:
    result = evaluate_output_decision_ledger(tmp_path, persist=False)

    assert result["state"] == "SKIP"
    assert result["status"] == "SKIP"


def test_write_decision_ledger_is_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    assert "write_decision_ledger" in registry.list_tools()
    schema = next(
        item["function"]["parameters"]
        for item in registry.get_schemas()
        if item["function"]["name"] == "write_decision_ledger"
    )
    assert "entries" in schema["properties"]
    assert "change_reason" in schema["required"]


def test_metric_heading_and_sensitivity_case_do_not_require_canonical_binding(
    tmp_path: Path,
) -> None:
    entries = _entries()
    payload = _ledger(tmp_path, entries)
    report = "\n".join((
        "## Ch12 估值",
        "### V_final 合成方法",
        "若 r* 降至 9%，替代情景估值会提高。",
        _bound_report(entries),
    ))

    result = validate_decision_ledger(
        payload,
        report_text=report,
        manifest=_write_manifest(tmp_path),
        enforced=True,
    )

    assert not any(
        item.startswith("unbound_critical_claim")
        for item in result["incomplete_findings"]
    )


def test_reviewable_ledger_promotes_only_after_all_other_checks_pass(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    initialize_decision_ledger_policy(tmp_path, run_id="promotion", enforced=True)
    entries = _entries(chapters=[0])
    report = _bound_report(entries)
    payload = build_decision_ledger(
        tmp_path, entries, change_reason="staged draft", freeze=False
    )
    assert persist_decision_ledger(tmp_path, payload, report_text=report)["written"]

    result = promote_reviewable_decision_ledger(tmp_path, report_text=report)

    assert result["promoted"] is True
    final = evaluate_output_decision_ledger(
        tmp_path, report_text=report, persist=False
    )
    assert final["state"] == "DECISION_READY"


def test_entry_value_support_accepts_percent_fraction_and_signed_decay() -> None:
    assert _line_supports_entry(
        "EPV=120/0.10=1,200M [decision: D008]",
        {"metric_id": "return.required", "value": 10.0, "unit": "percent"},
    )
    assert _line_supports_entry(
        "护城河衰减（-3.2%） [decision: D009]",
        {"metric_id": "moat.decay", "value": 3.2, "unit": "percent"},
    )
    assert not _line_supports_entry(
        "要求回报率为8%",
        {"metric_id": "return.required", "value": 10.0, "unit": "percent"},
    )


def test_trigger_metric_cannot_deny_its_own_action_semantics(tmp_path: Path) -> None:
    entries = _entries()
    exit_entry = next(item for item in entries if item["metric_id"] == "trigger.exit")
    exit_entry["rationale"] = "1.24只是压力参考，不是退出条件"
    payload = _ledger(tmp_path, entries)
    result = validate_decision_ledger(
        payload, report_text=_bound_report(entries),
        manifest=_write_manifest(tmp_path), enforced=True,
    )
    assert any(
        item.endswith("exit_trigger_semantics_contradict_metric")
        for item in result["invalid_findings"]
    )


def test_downside_reduce_price_cannot_sit_above_only_buy_price(tmp_path: Path) -> None:
    entries = _entries()
    buy = next(item for item in entries if item["metric_id"] == "trigger.buy")
    reduce = next(item for item in entries if item["metric_id"] == "trigger.reduce")
    buy.update({"value": 2.42, "unit": "HKD", "basis": "price must be at or below entry line"})
    reduce.update({"value": 2.64, "unit": "HKD", "basis": "股价跌破该价止损"})
    payload = _ledger(tmp_path, entries)

    result = validate_decision_ledger(
        payload, manifest=_write_manifest(tmp_path), enforced=True,
    )

    assert any(
        item.startswith("downside_reduce_price_above_buy_price")
        for item in result["invalid_findings"]
    )


def test_take_profit_reduce_price_may_sit_above_buy_price(tmp_path: Path) -> None:
    entries = _entries()
    buy = next(item for item in entries if item["metric_id"] == "trigger.buy")
    reduce = next(item for item in entries if item["metric_id"] == "trigger.reduce")
    buy.update({"value": 2.42, "unit": "HKD", "basis": "price must be at or below entry line"})
    reduce.update({"value": 4.58, "unit": "HKD", "basis": "股价高于盈利能力上界时获利减仓"})
    payload = _ledger(tmp_path, entries)

    result = validate_decision_ledger(
        payload, manifest=_write_manifest(tmp_path), enforced=True,
    )

    assert not any(
        item.startswith("downside_reduce_price_above_buy_price")
        for item in result["invalid_findings"]
    )
