from __future__ import annotations

import json
from pathlib import Path

from scripts.decision_compiler import (
    compile_decision_sections,
    initialize_decision_compiler_policy,
)
from scripts.decision_ledger import (
    CANONICAL_METRIC_IDS,
    build_decision_ledger,
    validate_decision_ledger,
)
from scripts.decision_reliability import validate_decision_reliability
from scripts.report_completion import evaluate_pending_valuation_decision_revision
from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract
from scripts.turtle_agent.tools.write_tools import write_decision_manifest
from scripts.valuation_model_gate import (
    build_valuation_model_ledger,
    validate_valuation_model_ledger,
    valuation_fingerprint,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _unresolved_entries() -> list[dict]:
    known_values = {
        "hurdle.ii": (5.5, "percent"),
        "moat.lambda": (0.6, "ratio"),
        "return.required": (10.0, "percent"),
        "moat.decay": (2.0, "percent"),
        "trigger.buy": ("当前价格动作暂不承保", "rule"),
        "trigger.reduce": ("经营事实恶化后重估", "rule"),
        "trigger.exit": ("永久损失否决事实成立", "rule"),
    }
    rows: list[dict] = []
    for metric_id in sorted(CANONICAL_METRIC_IDS):
        value, unit = known_values.get(metric_id, (None, "unresolved"))
        rows.append({
            "entry_id": metric_id + "@base.current",
            "metric_id": metric_id,
            "value": value,
            "unit": unit,
            "scenario": "base",
            "basis": "canonical_or_explicitly_unresolved",
            "as_of": "2026-08-28",
            "version": 1,
            "status": "active",
            "chapters": [],
            "source_ids": ["compute_bundle.json"],
            "affects_action": metric_id.startswith(("valuation.", "margin.", "trigger.", "decision.")),
        })
    return rows


def test_unresolved_valuation_passes_manifest_ledger_model_and_compiler_without_fake_numbers(
    tmp_path: Path,
) -> None:
    _write_json(tmp_path / "analysis_contract.json", {"ts_code": "000001.SZ"})
    manifest = write_decision_manifest(
        output_dir=str(tmp_path),
        qualitative_decision="continue",
        quantitative_decision="unresolved",
        qualitative_rationale="经营判断仍有证据支持",
        quantitative_rationale="当前价格或核心估值输入不可用",
    )["manifest"]
    assert manifest["position_pct"] is None

    entries = _unresolved_entries()
    ledger = build_decision_ledger(
        tmp_path, entries, change_reason="withhold price action while inputs are unavailable", freeze=True
    )
    _write_json(tmp_path / "decision_ledger.json", ledger)
    ledger_validation = validate_decision_ledger(
        ledger, manifest=manifest, enforced=True
    )
    assert ledger_validation["status"] == "PASS", ledger_validation
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "decision_ledger.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "unresolved" in schema["properties"]["decision"]["properties"]["quantitative_decision"]["enum"]
    assert {branch.get("type") for branch in schema["properties"]["decision"]["properties"]["position_pct"]["anyOf"]} == {"number", "null"}

    valuation = build_valuation_model_ledger(
        tmp_path,
        {
            "business_type": "general_operating",
            "asset_intensity": "mixed",
            "valuation_route": "route selected but not numerically settled",
            "route_reasoning": "enterprise evidence remains usable; current price action needs missing inputs",
        },
        [],
        {
            "action": "unresolved",
            "position_pct": None,
            "decision_rule": "do not convert unavailable valuation inputs into Hold or Avoid",
            "divergence_explanation": "enterprise judgment continues independently",
        },
        change_reason="valuation inputs unavailable",
        freeze=True,
    )
    valuation_validation = validate_valuation_model_ledger(
        valuation, output_dir=tmp_path, enforced=True
    )
    assert valuation_validation["status"] == "PASS", valuation_validation
    assert validate_decision_reliability(
        tmp_path, enforced=True, valuation_override=valuation
    )["status"] == "PASS"
    _write_json(tmp_path / "valuation_model.json", valuation)

    _write_json(tmp_path / "compute_bundle.json", {"factor4": {"valuation_status": "UNRESOLVED_VALUATION"}})
    _write_json(tmp_path / "thesis_test.json", {"competitive_tests": [], "thresholds": [], "probability_sets": []})
    _write_json(tmp_path / "claim_evidence.json", {"claims": []})
    _write_json(tmp_path / "insight_ledger.json", {"insights": []})
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    for chapter in range(15):
        (chapters / f"_ch{chapter:02d}.md").write_text(
            f"## Ch{chapter} 测试章节\n\n企业经营判断正文。\n", encoding="utf-8"
        )
    initialize_decision_compiler_policy(
        tmp_path,
        run_id="unresolved-chain",
        enforced=True,
        decision_as_of="2026-08-28",
        max_market_age_days=7,
    )

    compiled = compile_decision_sections(tmp_path)

    assert compiled["written"] is True, compiled
    assert compiled["validation"]["status"] == "PASS", compiled
    for chapter in (0, 14):
        text = (chapters / f"_ch{chapter:02d}.md").read_text(encoding="utf-8")
        assert "当前价格动作暂不承保" in text
        assert "目标仓位 None%" not in text
        assert "None%" not in text


def test_unresolved_contract_and_pending_revision_complete_without_fake_d006(
    tmp_path: Path,
) -> None:
    _write_json(tmp_path / "analysis_contract.json", {"ts_code": "000001.SZ"})
    manifest = write_decision_manifest(
        output_dir=str(tmp_path),
        qualitative_decision="continue",
        quantitative_decision="unresolved",
        qualitative_rationale="企业经营判断继续",
        quantitative_rationale="当前价格或必要估值输入不可用",
    )["manifest"]
    ledger = build_decision_ledger(
        tmp_path,
        _unresolved_entries(),
        change_reason="withhold only the unavailable price action",
        freeze=True,
    )
    _write_json(tmp_path / "decision_ledger.json", ledger)
    valuation = build_valuation_model_ledger(
        tmp_path,
        {
            "business_type": "general_operating",
            "asset_intensity": "mixed",
            "valuation_route": "route known but numerical settlement unavailable",
            "route_reasoning": "enterprise judgment remains separately usable",
        },
        [],
        {
            "action": "unresolved",
            "position_pct": None,
            "decision_rule": "withhold price action until the missing input is observed",
            "divergence_explanation": "no fake Hold, Avoid, range, or D006 value",
        },
        change_reason="valuation input unavailable",
        freeze=True,
    )
    _write_json(tmp_path / "valuation_model.json", valuation)
    _write_json(tmp_path / "valuation_decision_revision_proposal.json", {
        "state": "INTERNAL_SYNTHESIS_REQUIRED",
        "approval_status": "NOT_REQUESTED_AT_VALUATION_STAGE",
        "candidate": valuation,
        "candidate_fingerprint": valuation_fingerprint(valuation),
        "current_decision_ledger_fingerprint": "superseded-by-propagation",
        "proposed_synthesis": valuation["synthesis"],
    })

    contract = read_structured_ledger_contract(str(tmp_path), "valuation")
    assert "action:unresolved" in contract["contract"]["synthesis"]
    assert "position_pct:null" in contract["contract"]["synthesis"]
    result = evaluate_pending_valuation_decision_revision(str(tmp_path))
    assert result["state"] == "RESOLVED", result
    assert result["status"] == "PASS"
