from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.decision_compiler import (
    PROTECTED_CHAPTERS,
    approve_decision_diff,
    compile_decision_sections,
    evaluate_output_decision_compiler,
    initialize_decision_compiler_policy,
    migrate_canonical_decision_summaries,
    migrate_legacy_decision_values,
    migrate_manifest_action_conflicts,
    select_canonical_entries,
    validate_chapter_decision_bindings,
)
from scripts.decision_ledger import CANONICAL_METRIC_IDS, build_decision_ledger, ledger_fingerprint
from scripts.turtle_agent.tools.write_tools import assemble_report, write_chapter, write_decision_manifest


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


def _entries() -> list[dict]:
    result = []
    for metric_id in sorted(CANONICAL_METRIC_IDS):
        value, unit = VALUES[metric_id]
        entry = {
            "entry_id": metric_id + "@base.current", "metric_id": metric_id,
            "value": value, "unit": unit, "scenario": "base", "basis": "canonical",
            "as_of": "2026-08-02", "version": 1, "status": "active",
            "chapters": [], "source_ids": ["compute_bundle.json"],
            "affects_action": metric_id.startswith(("valuation.", "margin.", "trigger.", "decision.")),
        }
        if metric_id == "trigger.buy":
            entry["rationale"] = "only buy when the combined return margin is nonnegative"
        if metric_id == "decision.position.recommended":
            entry["rationale"] = "existing holder position; new investor waits for buy trigger"
        result.append(entry)
    return result


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture(output: Path, *, action: str = "hold", entries: list[dict] | None = None) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    manifest = write_decision_manifest(
        output_dir=str(output), qualitative_decision="continue",
        quantitative_decision=action, position_pct=5.0,
    )["manifest"]
    values = entries or _entries()
    ledger = build_decision_ledger(output, values, change_reason="initial analysis", freeze=True)
    _write_json(output / "decision_ledger.json", ledger)
    _write_json(output / "valuation_model.json", {"schema_version": "valuation-model.v1", "models": [{"model_id": "M-bear"}]})
    _write_json(output / "thesis_test.json", {"schema_version": "thesis-test.v1", "competitive_tests": [], "thresholds": [], "probability_sets": []})
    _write_json(output / "claim_evidence.json", {
        "schema_version": "claim-evidence.v1",
        "claims": [{"claim_id": "C-final", "decision_entry_ids": ["valuation.v_final@base.current"]}],
    })
    _write_json(output / "insight_ledger.json", {"schema_version": "insight-ledger.v1", "fixture": True})
    chapters = output / "chapters"
    chapters.mkdir()
    for chapter in range(15):
        (chapters / f"_ch{chapter:02d}.md").write_text(
            f"## Ch{chapter} 测试章节\n\n这里保留用于解释事实、机制与反证的正文。\n",
            encoding="utf-8",
        )
    initialize_decision_compiler_policy(
        output, run_id="run-stage26", enforced=True,
        decision_as_of="2026-08-04", max_market_age_days=7,
    )
    assert manifest["quantitative_decision"] == action
    return values


def test_compiles_five_byte_stable_protected_blocks(tmp_path: Path) -> None:
    _fixture(tmp_path)
    first = compile_decision_sections(tmp_path)
    first_bytes = {
        chapter: (tmp_path / "chapters" / f"_ch{chapter:02d}.md").read_bytes()
        for chapter in PROTECTED_CHAPTERS
    }
    second = compile_decision_sections(tmp_path)

    assert first["written"] is True
    assert first["validation"]["state"] == "DECISION_READY"
    assert second["idempotent"] is True
    assert second["changed_chapters"] == []
    for chapter, original in first_bytes.items():
        current = tmp_path / "chapters" / f"_ch{chapter:02d}.md"
        assert current.read_bytes() == original
        assert current.read_text(encoding="utf-8").count(
            f"TURTLE:DECISION_BLOCK:Ch{chapter}:BEGIN"
        ) == 1
        assert "[source: compute_bundle.json]" in current.read_text(encoding="utf-8")


def test_tamper_remove_and_duplicate_are_invalid(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    path = tmp_path / "chapters" / "_ch14.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("Canonical final decision", "Tampered decision"), encoding="utf-8")
    assert compile_decision_sections(tmp_path)["state"] == "INVALID"

    path.write_text(original.replace("<!-- TURTLE:DECISION_BLOCK:Ch14:END -->", ""), encoding="utf-8")
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"

    path.write_text(original + "\n" + original[original.index("<!-- TURTLE:"):], encoding="utf-8")
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"


def test_chapter_rewrite_preserves_compiler_owned_bytes(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    path = tmp_path / "chapters" / "_ch14.md"
    marker = "<!-- TURTLE:DECISION_BLOCK:Ch14:BEGIN"
    before = path.read_text(encoding="utf-8")
    protected = before[before.index(marker):before.index("<!-- TURTLE:DECISION_BLOCK:Ch14:END -->") + len("<!-- TURTLE:DECISION_BLOCK:Ch14:END -->")]

    write_chapter(
        output_dir=str(tmp_path), chapter_index=14, title="重写",
        content="## Ch14 最终结论\n\n新的解释性正文只讨论机制、反证与边界。\n",
        force_rewrite=True,
    )
    assert protected in path.read_text(encoding="utf-8")


def test_unbound_old_final_value_is_invalid_but_bound_scenario_is_allowed(tmp_path: Path) -> None:
    entries = _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    ch12 = tmp_path / "chapters" / "_ch12.md"
    ch12.write_text(ch12.read_text(encoding="utf-8") + "\n旧稿 V_final=70.4 元。\n", encoding="utf-8")
    failed = evaluate_output_decision_compiler(tmp_path)
    assert failed["state"] == "INVALID"
    assert any("free_critical_value:Ch12" in item for item in failed["invalid_findings"])

    # A genuine, explicitly identified scenario remains legal.
    bear = deepcopy(next(item for item in entries if item["metric_id"] == "valuation.v_final"))
    bear.update({"entry_id": "valuation.v_final@bear.current", "scenario": "bear", "value": 42.99})
    clean = tmp_path / "scenario"
    _fixture(clean, entries=entries + [bear])
    compile_decision_sections(clean)
    path = clean / "chapters" / "_ch12.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n压力情景 V_final=42.99 元 [decision: valuation.v_final@bear.current]。\n", encoding="utf-8")
    assert evaluate_output_decision_compiler(clean)["state"] == "DECISION_READY"

    # A sensitivity output may use the valuation ledger instead of pretending
    # to be a second final-decision entry.
    path.write_text(path.read_text(encoding="utf-8") + "\n压力测试 V_final=35.0 元 [valuation: M-bear]。\n", encoding="utf-8")
    assert evaluate_output_decision_compiler(clean)["state"] == "DECISION_READY"
    path.write_text(path.read_text(encoding="utf-8") + "\nV_final=总价值496.8亿元 [claim: C-final]。\n", encoding="utf-8")
    assert evaluate_output_decision_compiler(clean)["state"] == "DECISION_READY"


def test_chapter_write_returns_immediate_canonical_binding_failure(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    result = write_chapter(
        output_dir=str(tmp_path), chapter_index=12, title="估值更新",
        content=(
            "## Ch12 内在价值合成与裁决\n\n"
            "研究更新后仍采用 V_final=49.68 元，但这里故意遗漏canonical绑定。\n"
            "补充机制、反证、适用条件和敏感性说明，确保本测试不是空章节。\n"
        ),
        force_rewrite=True,
    )
    assert result["decision_binding_validation"]["state"] == "INVALID"
    assert result["passed"] is False
    assert any(
        "free_critical_value:Ch12" in item
        for item in result["decision_binding_validation"]["invalid_findings"]
    )
    assert validate_chapter_decision_bindings(tmp_path, 12)["state"] == "INVALID"


def test_chapter_binding_rejects_decision_id_attached_to_wrong_value(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    path = tmp_path / "chapters" / "_ch12.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\nGG_base=7.4% [decision: hurdle.ii@base.current]。\n",
        encoding="utf-8",
    )
    result = validate_chapter_decision_bindings(tmp_path, 12)
    assert result["state"] == "INVALID"
    assert any(
        "decision_value_mismatch:Ch12" in item
        for item in result["invalid_findings"]
    )


def test_combined_required_return_plus_decay_is_not_second_decay_identity(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    path = tmp_path / "chapters" / "_ch12.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n回报safety_margin仍为负：R_total 7.7% vs r*+decay=13.2%。\n",
        encoding="utf-8",
    )
    result = evaluate_output_decision_compiler(tmp_path)
    assert result["state"] == "DECISION_READY"


def test_noncanonical_scenario_price_cannot_be_labeled_buyable(tmp_path: Path) -> None:
    _fixture(tmp_path)
    compile_decision_sections(tmp_path)
    path = tmp_path / "chapters" / "_ch13.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n| 40.00 RMB | 可买（估值情景价） | [valuation: M-bear] |\n",
        encoding="utf-8",
    )
    result = evaluate_output_decision_compiler(tmp_path)
    assert result["state"] == "INVALID"
    assert any(
        item.startswith("noncanonical_action_price:Ch13")
        for item in result["invalid_findings"]
    )

def test_ambiguous_selection_and_inconsistent_action_stop_before_mutation(tmp_path: Path) -> None:
    entries = _entries()
    duplicate = deepcopy(next(item for item in entries if item["metric_id"] == "valuation.v_final"))
    duplicate.update({"entry_id": "valuation.v_final@base.other", "basis": "other", "value": 52.0})
    selected, findings = select_canonical_entries({"entries": entries + [duplicate]})
    assert "valuation.v_final" in selected  # canonical-basis entry wins deterministically
    duplicate["basis"] = "canonical"
    selected, findings = select_canonical_entries({"entries": entries + [duplicate]})
    assert "canonical_entry_ambiguous:valuation.v_final" in findings

    trigger_entries = _entries()
    reduce_entry = next(item for item in trigger_entries if item["metric_id"] == "trigger.reduce")
    reduce_entry["scenario"] = "pessimistic"
    selected, findings = select_canonical_entries({"entries": trigger_entries})
    assert selected["trigger.reduce"]["entry_id"] == reduce_entry["entry_id"]
    assert findings == []

    buy_entries = _entries()
    margin = next(item for item in buy_entries if item["metric_id"] == "margin.return")
    margin["value"] = -2.2
    _fixture(tmp_path, action="buy", entries=buy_entries)
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert "buy_without_nonnegative_return_margin" in result["invalid_findings"]
    assert "TURTLE:DECISION_BLOCK" not in (tmp_path / "chapters" / "_ch00.md").read_text(encoding="utf-8")


def test_stale_market_price_blocks_price_sensitive_decision(tmp_path: Path) -> None:
    entries = _entries()
    market = next(item for item in entries if item["metric_id"] == "market.price.current")
    market["as_of"] = "2026-07-01"
    _fixture(tmp_path, entries=entries)
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert any(item.startswith("stale_market_price:age_days=34") for item in result["invalid_findings"])


def test_same_valuation_symbol_cannot_mean_two_different_values(tmp_path: Path) -> None:
    _fixture(tmp_path)
    ch12 = tmp_path / "chapters" / "_ch12.md"
    ch14 = tmp_path / "chapters" / "_ch14.md"
    ch12.write_text(ch12.read_text(encoding="utf-8") + "\nV_cash = 605M。\n", encoding="utf-8")
    ch14.write_text(ch14.read_text(encoding="utf-8") + "\n| V_cash | 1,695M | 净现金 |\n", encoding="utf-8")
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert any(item.startswith("metric_identity_conflict:valuation.v_cash:") for item in result["invalid_findings"])


def test_buy_trigger_must_resolve_active_combined_return_hurdle(tmp_path: Path) -> None:
    entries = _entries()
    trigger = next(item for item in entries if item["metric_id"] == "trigger.buy")
    trigger.pop("rationale", None)
    _fixture(tmp_path, entries=entries)
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert "buy_trigger_ignores_active_return_hurdle" in result["invalid_findings"]


def test_positive_position_above_unmet_buy_price_requires_existing_holder_scope(tmp_path: Path) -> None:
    entries = _entries()
    position = next(item for item in entries if item["metric_id"] == "decision.position.recommended")
    position.pop("rationale", None)
    _fixture(tmp_path, entries=entries)
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert "positive_position_above_buy_trigger_without_existing_holder_scope" in result["invalid_findings"]


def test_policy_compatibility_and_schemas(tmp_path: Path) -> None:
    assert evaluate_output_decision_compiler(tmp_path)["state"] == "SKIP"
    initialize_decision_compiler_policy(tmp_path, run_id="new-run", enforced=True)
    assert evaluate_output_decision_compiler(tmp_path)["state"] == "INCOMPLETE"
    root = Path(__file__).resolve().parents[1]
    for name in ("decision_compilation.schema.json", "decision_compiler_policy.schema.json"):
        schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["required"]


def test_assembly_automatically_invokes_compiler(tmp_path: Path) -> None:
    _fixture(tmp_path)
    result = assemble_report(
        output_dir=str(tmp_path), company_name="编译器测试公司",
        ts_code="TEST.SZ", validation_only=True,
    )
    assert (tmp_path / "decision_compilation.json").is_file()
    assert "TURTLE:DECISION_BLOCK:Ch14:BEGIN" in (
        tmp_path / "chapters" / "_ch14.md"
    ).read_text(encoding="utf-8")
    assert result["decision_compiler"]["written"] is True


def test_action_changing_diff_requires_approval(tmp_path: Path) -> None:
    _fixture(tmp_path)
    ledger = json.loads((tmp_path / "decision_ledger.json").read_text(encoding="utf-8"))
    _write_json(tmp_path / "decision_diff.json", {
        "schema_version": "decision-diff.v1", "status": "APPLIED",
        "changes_action": True, "approval_status": "PENDING",
        "new_fingerprint": ledger_fingerprint(ledger),
    })
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["decision_diff_approval_pending"]
    assert "TURTLE:DECISION_BLOCK" not in (tmp_path / "chapters" / "_ch00.md").read_text(encoding="utf-8")

    rejected = approve_decision_diff(tmp_path, approved_by="", rationale="", evidence_ids=[])
    assert rejected["written"] is False
    approved = approve_decision_diff(
        tmp_path, approved_by="research-reviewer", rationale="new filing changed cash-flow base",
        evidence_ids=["annual_report:p42"],
    )
    assert approved["diff"]["approval_status"] == "APPROVED"
    assert compile_decision_sections(tmp_path)["validation"]["state"] == "DECISION_READY"


def test_manifest_revaluation_rule_blocks_and_migrates_stale_direct_exit(tmp_path: Path) -> None:
    _fixture(tmp_path)
    manifest = json.loads((tmp_path / "decision_manifest.json").read_text())
    manifest["exit_conditions"] = ["大股东减持>5%→重估"]
    _write_json(tmp_path / "decision_manifest.json", manifest)
    chapter = tmp_path / "chapters" / "_ch09.md"
    chapter.write_text(
        "## Ch9 风险\n\n| 大股东减持 | >5% | 立即平仓 |\n",
        encoding="utf-8",
    )

    blocked = compile_decision_sections(tmp_path)
    assert blocked["state"] == "INVALID"
    assert any("stale_action_conflict:Ch9" in item for item in blocked["invalid_findings"])

    preview = migrate_manifest_action_conflicts(tmp_path, apply=False)
    assert preview["state"] == "MIGRATED"
    assert "立即平仓" in chapter.read_text(encoding="utf-8")
    applied = migrate_manifest_action_conflicts(tmp_path, apply=True)
    assert applied["changed_lines"]
    assert "触发重估" in chapter.read_text(encoding="utf-8")
    assert not any(
        "stale_action_conflict" in item
        for item in compile_decision_sections(tmp_path).get("invalid_findings", [])
    )


def test_manifest_revaluation_rule_does_not_weaken_conditional_exit(tmp_path: Path) -> None:
    _fixture(tmp_path)
    manifest = json.loads((tmp_path / "decision_manifest.json").read_text())
    manifest["exit_conditions"] = [">100M非主业收购→先重估，仅在V_final<市价时退出"]
    _write_json(tmp_path / "decision_manifest.json", manifest)
    chapter = tmp_path / "chapters" / "_ch09.md"
    original = "## Ch9 风险\n\n非主业收购先重估，只有重估后V_final<市价才退出。\n"
    chapter.write_text(original, encoding="utf-8")
    assert migrate_manifest_action_conflicts(tmp_path, apply=False)["state"] == "NO_CHANGE"
    assert chapter.read_text(encoding="utf-8") == original


def test_canonical_summary_migration_rewrites_only_labeled_rows(tmp_path: Path) -> None:
    _fixture(tmp_path)
    chapter = tmp_path / "chapters" / "_ch00.md"
    chapter.write_text(
        "## Ch0 摘要\n\n| 建议仓位 | 2-3% | 旧口径 |\n\n自由分析中的仓位讨论不自动改写。\n",
        encoding="utf-8",
    )
    preview = migrate_canonical_decision_summaries(tmp_path, apply=False)
    assert len(preview["changed_lines"]) == 1
    assert "2-3%" in chapter.read_text(encoding="utf-8")
    applied = migrate_canonical_decision_summaries(tmp_path, apply=True)
    assert applied["changed_lines"][0]["metric_id"] == "decision.position.recommended"
    text = chapter.read_text(encoding="utf-8")
    assert "| 建议仓位 | 5% |" in text
    assert "[decision: decision.position.recommended@base.current]" in text
    assert "自由分析中的仓位讨论不自动改写" in text


def test_legacy_migration_binds_known_values_and_never_guesses(tmp_path: Path) -> None:
    entries = _fixture(tmp_path)
    old = deepcopy(next(item for item in entries if item["metric_id"] == "valuation.v_final"))
    old.update({
        "entry_id": "valuation.v_final@old", "value": 70.4, "status": "deprecated",
        "as_of": "2025-12-31", "deprecation_reason": "old draft",
        "superseded_by": "valuation.v_final@base.current",
    })
    ledger = build_decision_ledger(tmp_path, entries + [old], change_reason="migration", freeze=True)
    _write_json(tmp_path / "decision_ledger.json", ledger)
    path = tmp_path / "chapters" / "_ch12.md"
    path.write_text(
        "## Ch12 估值\n\nV_final=49.68 元。\n\n旧版 V_final=70.4 元。\n\n另一份 V_final=42.99 元。\n",
        encoding="utf-8",
    )

    preview = migrate_legacy_decision_values(tmp_path, apply=False)
    assert preview["state"] == "INCOMPLETE"
    assert "[decision:" not in path.read_text(encoding="utf-8")
    applied = migrate_legacy_decision_values(tmp_path, apply=True)
    text = path.read_text(encoding="utf-8")
    assert "[decision: valuation.v_final@base.current]" in text
    assert "[decision: valuation.v_final@old]（已废弃口径，不参与最终决策）" in text
    assert "V_final=42.99 元。[decision:" not in text
    assert len(applied["unresolved_lines"]) == 1


def test_compiler_rejects_duplicate_block_with_non_hash_fingerprint(tmp_path: Path) -> None:
    _fixture(tmp_path)
    first = compile_decision_sections(tmp_path)
    assert first["validation"]["state"] == "DECISION_READY"
    path = tmp_path / "chapters" / "_ch12.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n<!-- TURTLE:DECISION_BLOCK:Ch12:BEGIN fingerprint=pending_recompile -->\n"
          "stale block\n<!-- TURTLE:DECISION_BLOCK:Ch12:END -->\n",
        encoding="utf-8",
    )
    result = compile_decision_sections(tmp_path)
    assert result["state"] == "INVALID"
    assert "protected_block_duplicate:Ch12" in result["invalid_findings"]


def test_compiler_uses_entry_display_label(tmp_path: Path) -> None:
    entries = _entries()
    next(item for item in entries if item["metric_id"] == "trigger.exit")[
        "display_label"
    ] = "基本面退出阈值"
    _fixture(tmp_path, entries=entries)
    result = compile_decision_sections(tmp_path)
    assert result["validation"]["state"] == "DECISION_READY"
    assert "基本面退出阈值" in (
        tmp_path / "chapters" / "_ch13.md"
    ).read_text(encoding="utf-8")
