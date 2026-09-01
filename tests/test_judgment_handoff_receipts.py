from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.judgment_handoff_receipts import (
    RECEIPT_FILENAME,
    validate_judgment_handoff_read_receipt,
)
from scripts.turtle_agent.tools import read_tools, write_tools


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _policies(output: Path, run_id: str = "RUN:ordinary:1") -> None:
    for name in (
        "claim_evidence_policy.json",
        "financial_driver_bridge_policy.json",
        "thesis_test_policy.json",
        "insight_policy.json",
    ):
        _write(output / name, {"run_id": run_id, "enforced": True})


def _ready_output(output: Path) -> None:
    _write(output / "analysis_contract.json", {
        "ts_code": "000001.SZ",
        "company_id": "CN:000001",
        "company_name": "测试公司",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2026-06-30T23:59:59+08:00",
    })
    _policies(output)
    ledgers = (
        (
            "claim_evidence.json", "claim_evidence_validation.json",
            {"report_id": "000001.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "claims": []},
        ),
        (
            "financial_driver_bridge.json", "financial_driver_bridge_validation.json",
            {"report_id": "000001.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "drivers": [], "allocation_events": []},
        ),
        (
            "thesis_test.json", "thesis_test_validation.json",
            {
                "report_id": "000001.SZ",
                "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
                "mechanism_chains": [],
                "forward_judgments": [],
                "rival_hypothesis_pairs": [],
                "analogy_transfer_cards": [],
            },
        ),
        (
            "insight_ledger.json", "insight_validation.json",
            {"report_id": "000001.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "insights": []},
        ),
    )
    for ledger, validation, payload in ledgers:
        _write(output / ledger, payload)
        _write(output / validation, {
            "state": "REVIEWABLE",
            "invalid_findings": [],
            "incomplete_findings": [],
        })


def test_missing_synthesis_receipt_blocks_ordinary_assembly(tmp_path: Path) -> None:
    _write(tmp_path / "analysis_contract.json", {
        "ts_code": "000001.SZ",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2026-06-30",
    })
    _policies(tmp_path)

    with pytest.raises(RuntimeError, match="judgment_synthesis_read_receipt_missing"):
        write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")


def test_ready_synthesis_read_persists_a_current_receipt(tmp_path: Path) -> None:
    _ready_output(tmp_path)

    handoff = read_tools.read_judgment_generation_handoff(
        str(tmp_path), "JUDGMENT_SYNTHESIS",
    )

    assert handoff["readiness"]["state"] == "READY"
    assert handoff["read_receipt"]["state"] == "RECORDED"
    assert (tmp_path / RECEIPT_FILENAME).is_file()
    assert validate_judgment_handoff_read_receipt(tmp_path)["state"] == "READY"


def test_non_ready_synthesis_read_cannot_satisfy_gate(tmp_path: Path) -> None:
    _ready_output(tmp_path)
    (tmp_path / "insight_validation.json").unlink()

    handoff = read_tools.read_judgment_generation_handoff(
        str(tmp_path), "JUDGMENT_SYNTHESIS",
    )
    validation = validate_judgment_handoff_read_receipt(tmp_path)

    assert handoff["readiness"]["state"] == "INCOMPLETE"
    assert validation["state"] == "BLOCKED"
    assert "judgment_synthesis_read_was_not_ready" in validation["findings"]


def test_ledger_change_stales_receipt_and_new_read_restores_it(tmp_path: Path) -> None:
    _ready_output(tmp_path)
    read_tools.read_judgment_generation_handoff(str(tmp_path), "JUDGMENT_SYNTHESIS")
    ledger_path = tmp_path / "insight_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["revision"] = "new synthesis generation"
    _write(ledger_path, ledger)

    stale = validate_judgment_handoff_read_receipt(tmp_path)

    assert stale["state"] == "BLOCKED"
    assert "judgment_synthesis_source_changed_after_read:insight_ledger.json" in stale["findings"]
    read_tools.read_judgment_generation_handoff(str(tmp_path), "JUDGMENT_SYNTHESIS")
    assert validate_judgment_handoff_read_receipt(tmp_path)["state"] == "READY"


def test_new_unified_run_stales_receipt_until_synthesis_is_read_again(tmp_path: Path) -> None:
    _ready_output(tmp_path)
    read_tools.read_judgment_generation_handoff(str(tmp_path), "JUDGMENT_SYNTHESIS")
    _policies(tmp_path, run_id="RUN:ordinary:2")

    stale = validate_judgment_handoff_read_receipt(tmp_path)

    assert stale["state"] == "BLOCKED"
    assert "judgment_synthesis_run_changed_after_read" in stale["findings"]
    read_tools.read_judgment_generation_handoff(str(tmp_path), "JUDGMENT_SYNTHESIS")
    assert validate_judgment_handoff_read_receipt(tmp_path)["state"] == "READY"


def test_publication_revalidates_receipt_after_assembly_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module

    _ready_output(tmp_path)
    reader_text = (
        "公司向客户提供核心产品，客户按产品定价购买，因此收入来自持续销售。"
        "收入、利润和经营现金需经周期与维护投入调整。主路径与竞争解释要由同口径客户信号判别。"
        "未来监测单位经济与现金转换；若信号低于冻结阈值则结算并重检。"
        "最强反方是需求下滑形成永久损失。未披露数据保持 UNKNOWN。[source: annual.md]"
    )
    for index in range(15):
        (tmp_path / f"_ch{index:02d}.md").write_text(
            f"## Ch{index} 公司判断\n\n{reader_text}", encoding="utf-8",
        )
    read_tools.read_judgment_generation_handoff(str(tmp_path), "JUDGMENT_SYNTHESIS")
    fake_completion = SimpleNamespace(
        status="COMPLETE",
        to_dict=lambda: {
            "status": "COMPLETE",
            "blocking_findings": [],
            "warning_findings": [],
            "validators": {},
        },
    )
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)

    def mutate_synthesis(*args, **kwargs):
        path = tmp_path / "insight_ledger.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["revision"] = "changed during assembly"
        _write(path, payload)
        return {"passed": True, "issues": [], "warnings": []}

    monkeypatch.setattr(write_tools, "_run_quality_checks", mutate_synthesis)
    snapshot_called = {"value": False}

    def snapshot(*args, **kwargs):
        snapshot_called["value"] = True
        return {"written": True}

    monkeypatch.setattr(calibration_module, "create_publication_snapshot", snapshot)

    with pytest.raises(RuntimeError, match="current JUDGMENT_SYNTHESIS generation"):
        write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")
    assert snapshot_called["value"] is False
