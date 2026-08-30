from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reader_report_surface import (
    compile_reader_report_surface,
    validate_reader_report_surface,
)


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _ledgers(output: Path) -> None:
    _write(output / "insight_ledger.json", {
        "insights": [{
            "insight_id": "insight.cash_decay",
            "claim_id": "claim.core",
            "evidence_ids": ["ev.sales"],
            "decision_entry_ids": ["decision.value"],
        }],
    })
    _write(output / "claim_evidence.json", {
        "claims": [{"claim_id": "claim.core", "evidence_ids": ["ev.sales"]}],
    })
    _write(output / "decision_ledger.json", {
        "entries": [{"entry_id": "decision.value"}],
    })
    _write(output / "valuation_model.json", {
        "models": [{"model_id": "reverse.dcf"}],
    })


def test_projection_keeps_full_narrative_and_numeric_slot_but_not_bindings(
    tmp_path: Path,
) -> None:
    _ledgers(tmp_path)
    slot = "税费和收取摩擦后的普通股分配为RMB278.417百万元，即约RMB2.784亿元。"
    technical = f"""# 测试公司完整报告

## Ch0 投资主线

公司事实、机制和反方形成连续判断。[source: annual.md]

- 洞见引用：[insight: insight.cash_decay]
- 证据绑定：ev.sales

## Ch12 价值与回报

<!-- TURTLE:VALUE_BRIDGE_BLOCK:BEGIN -->
{slot}
<!-- TURTLE:VALUE_BRIDGE_BLOCK:END -->

## Ch14 最终处理

当前处理来自完整公司叙事。[decision: decision.value] [claim: claim.core] [valuation: reverse.dcf]
"""

    reader = compile_reader_report_surface(technical)
    validation = validate_reader_report_surface(reader, technical, tmp_path)

    assert validation["status"] == "PASS"
    assert all(
        heading in reader
        for heading in ("## Ch0 投资主线", "## Ch12 价值与回报", "## Ch14 最终处理")
    )
    assert reader.count(slot) == 1
    for private in (
        "[insight:", "[decision:", "insight.cash_decay", "claim.core",
        "ev.sales", "decision.value", "reverse.dcf", "TURTLE:VALUE_BRIDGE_BLOCK",
    ):
        assert private not in reader
    assert "[insight: insight.cash_decay]" in technical
    assert "[decision: decision.value]" in technical
    assert "[claim: claim.core]" in technical
    assert "[valuation: reverse.dcf]" in technical
    assert "证据绑定：ev.sales" in technical


def test_surface_validator_blocks_a_free_control_id_in_narrative(tmp_path: Path) -> None:
    _ledgers(tmp_path)
    technical = "## 公司主线\n\n这段解释包含自由重抄的 claim.core，不能自动删词。"
    reader = compile_reader_report_surface(technical)

    validation = validate_reader_report_surface(reader, technical, tmp_path)

    assert validation["status"] == "BLOCKED"
    assert "reader_surface_control_id_present:claim.core" in validation["blocking_findings"]


def test_surface_validator_rejects_executive_memo_as_formal_report(tmp_path: Path) -> None:
    _ledgers(tmp_path)
    technical = "## 公司主线\n\n完整公司事实与机制。"
    memo = "# 测试公司投资备忘录\n\n## 结论\n\n只保留摘要。"

    validation = validate_reader_report_surface(memo, technical, tmp_path)

    assert validation["status"] == "BLOCKED"
    assert "reader_artifact_is_executive_memo" in validation["blocking_findings"]
    assert "reader_surface_heading_missing:公司主线" in validation["blocking_findings"]


def test_reader_surface_validation_matches_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    _ledgers(tmp_path)
    technical = "## 公司主线\n\n完整公司事实、机制与结论。"
    reader = compile_reader_report_surface(technical)
    validation = validate_reader_report_surface(reader, technical, tmp_path)
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "reader_report_surface_validation.schema.json"
        ).read_text(encoding="utf-8")
    )

    jsonschema.Draft202012Validator(schema).validate(validation)
