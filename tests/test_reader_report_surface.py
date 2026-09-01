from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reader_report_surface import (
    compile_reader_report_surface,
    known_control_ids,
    validate_reader_report_surface,
)

SLOT = "税费和收取摩擦后的普通股分配为RMB278.417百万元，即约RMB2.784亿元。"


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
    _write(output / "fact_observations.json", {
        "observations": [{
            "observation_id": "OBS:cash.balance",
            "source_fact_ids": ["OBS:cash.source", "annual_report_2025.pdf"],
        }],
    })
    _write(output / "calculation_observations.json", {
        "calculations": [{"calculation_id": "CALC:cash.bridge"}],
    })


def _register_slot(output: Path) -> None:
    valuation = json.loads((output / "valuation_model.json").read_text(encoding="utf-8"))
    valuation["value_bridge_models"] = {
        "reader_slots": [{
            "slot_id": "after_tax_common_distribution",
            "metric": "AFTER_TAX_COMMON_DISTRIBUTION",
            "sentence": SLOT,
        }],
    }
    _write(output / "valuation_model.json", valuation)


def test_projection_keeps_full_narrative_and_numeric_slot_but_not_bindings(
    tmp_path: Path,
) -> None:
    _ledgers(tmp_path)
    slot = SLOT
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

    reader = compile_reader_report_surface(technical, tmp_path)
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
    reader = compile_reader_report_surface(technical, tmp_path)

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


def test_projection_drops_pure_binding_lines_but_keeps_mixed_line_explanation(
    tmp_path: Path,
) -> None:
    _ledgers(tmp_path)
    technical = """## 公司主线

- 证据绑定：OBS:cash.balance
- 证据绑定：stale.binding
- 证据绑定：OBS:cash.balance；该证据显示回款改善尚未转化为可分配现金。
- 证据绑定：annual_report_2025.pdf；来源文件披露了余额口径。
"""

    reader = compile_reader_report_surface(technical, tmp_path)

    assert "证据绑定" not in reader
    assert "OBS:cash.balance" not in reader
    assert "stale.binding" not in reader
    assert "该证据显示回款改善尚未转化为可分配现金。" in reader
    assert "来源文件披露了余额口径。" in reader
    assert reader.count("该证据显示") == 1


def test_known_control_ids_include_fact_and_calculation_registries_without_public_labels(
    tmp_path: Path,
) -> None:
    _ledgers(tmp_path)

    identities = known_control_ids(tmp_path)

    assert {"OBS:cash.balance", "OBS:cash.source", "CALC:cash.bridge"} <= identities
    assert "NAV" not in identities and "EPV" not in identities
    assert "annual_report_2025.pdf" not in identities


@pytest.mark.parametrize("leak", ["OBS:cash.balance", "CALC:cash.bridge"])
def test_surface_validator_blocks_canonical_fact_identity_in_free_reader_prose(
    tmp_path: Path, leak: str,
) -> None:
    _ledgers(tmp_path)
    technical = f"## 公司主线\n\n自由正文重抄了 {leak}。"

    validation = validate_reader_report_surface(technical, technical, tmp_path)

    assert validation["status"] == "BLOCKED"
    assert "reader_surface_canonical_fact_identity_present" in validation["blocking_findings"]


def test_reader_slot_cardinality_is_a_three_artifact_hard_gate(tmp_path: Path) -> None:
    _ledgers(tmp_path)
    _register_slot(tmp_path)
    narrative = f"## 价值结论\n\n{SLOT}"

    valid = validate_reader_report_surface(
        narrative,
        narrative,
        tmp_path,
        technical_artifact_text=narrative,
        executive_text="## 执行摘要\n\n只解释经济结论，不复制模型数值。",
    )
    duplicated_technical = validate_reader_report_surface(
        narrative,
        narrative,
        tmp_path,
        technical_artifact_text=narrative + "\n\n## 技术附录\n\n" + SLOT,
        executive_text="## 执行摘要\n\n只解释经济结论。",
    )
    leaked_executive = validate_reader_report_surface(
        narrative,
        narrative,
        tmp_path,
        technical_artifact_text=narrative,
        executive_text="## 执行摘要\n\n" + SLOT,
    )

    assert valid["status"] == "PASS"
    assert valid["reader_slot_cardinality"] == [{
        "slot_id": "after_tax_common_distribution",
        "reader_count": 1,
        "technical_count": 1,
        "executive_count": 0,
        "status": "PASS",
    }]
    assert duplicated_technical["status"] == "BLOCKED"
    assert any(
        "technical=2" in finding
        for finding in duplicated_technical["blocking_findings"]
    )
    assert leaked_executive["status"] == "BLOCKED"
    assert any(
        "executive=1" in finding
        for finding in leaked_executive["blocking_findings"]
    )


@pytest.mark.parametrize(
    ("surface", "copied_amount"),
    [
        (
            "executive",
            "税费和收取摩擦后的普通股分配为RMB375.800百万元，即约RMB3.758亿元。",
        ),
        (
            "executive",
            "税费和收取摩擦后的普通股分配为 **RMB 278.417 百万元**，"
            "即约 **RMB 2.784 亿元**。",
        ),
        (
            "technical",
            "税费和收取摩擦后的普通股分配为 **RMB 278.417 百万元**，"
            "即约 **RMB 2.784 亿元**。",
        ),
    ],
)
def test_reader_slot_semantic_gate_rejects_wrong_or_reformatted_artifact_copy(
    tmp_path: Path,
    surface: str,
    copied_amount: str,
) -> None:
    _ledgers(tmp_path)
    _register_slot(tmp_path)
    narrative = f"## 价值结论\n\n{SLOT}"

    validation = validate_reader_report_surface(
        narrative,
        narrative,
        tmp_path,
        technical_artifact_text=(
            narrative + "\n\n## 技术附录\n\n" + copied_amount
            if surface == "technical" else narrative
        ),
        executive_text=copied_amount if surface == "executive" else "只解释经济结论。",
    )

    assert validation["status"] == "BLOCKED"
    assert any(
        finding.startswith(f"free_reader_numeric_slot:{surface}_artifact:")
        for finding in validation["blocking_findings"]
    )


def test_reader_slot_semantic_gate_allows_actual_dividend_and_cash_balance(
    tmp_path: Path,
) -> None:
    _ledgers(tmp_path)
    _register_slot(tmp_path)
    narrative = f"## 价值结论\n\n{SLOT}"
    source_facts = (
        "2025年实际派息为RMB278.417百万元；"
        "期末普通现金余额为人民币3.758亿元。"
    )

    validation = validate_reader_report_surface(
        narrative + "\n\n" + source_facts,
        narrative,
        tmp_path,
        technical_artifact_text=narrative + "\n\n" + source_facts,
        executive_text="历史实际派息与普通现金余额仅用于解释资金背景。",
    )

    assert validation["status"] == "PASS"


def test_public_model_labels_and_source_footnotes_are_reader_safe(tmp_path: Path) -> None:
    _ledgers(tmp_path)
    text = (
        "## 价值结论\n\nNAV与EPV用于交叉核验。[^1]\n\n"
        "[^1]: `annual_report_2025.pdf` 与 `ev.sales.pdf` — audited balance sheet"
    )

    validation = validate_reader_report_surface(text, text, tmp_path)

    assert validation["status"] == "PASS"


def test_reader_surface_validation_matches_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    _ledgers(tmp_path)
    technical = "## 公司主线\n\n完整公司事实、机制与结论。"
    reader = compile_reader_report_surface(technical, tmp_path)
    validation = validate_reader_report_surface(reader, technical, tmp_path)
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "reader_report_surface_validation.schema.json"
        ).read_text(encoding="utf-8")
    )

    jsonschema.Draft202012Validator(schema).validate(validation)
