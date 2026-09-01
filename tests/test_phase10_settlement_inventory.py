from __future__ import annotations

from pathlib import Path

from scripts import phase10_settlement_inventory


def test_settlement_inventory_keeps_metadata_only_corporate_action_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        phase10_settlement_inventory,
        "validate_case",
        lambda *_args, **_kwargs: {"state": "INCOMPLETE", "invalid_findings": []},
    )
    case = {
        "company_code": "600340.SH",
        "simulation_cutoff": "2020-04-27T18:00:00+08:00",
        "report_freeze": {
            "mode": "PIT_ENGINEERING",
            "report_status": "FROZEN_WITH_QUALITY_FAILURE",
            "freeze_id": "HBTFRZ:TEST",
        },
        "calibration_ledger": {
            "claims": [{"claim_id": "HBTCLM:600340:P10B:ORDINARY_CASH", "observable_outcome": {"metric": "cash"}}],
        },
    }
    inventory = {
        "provider": "SSE",
        "endpoint": "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
        "company_code": "600340",
        "begin_date": "2020-04-28",
        "end_date": "2021-04-27",
        "record_count": 2,
        "records": [
            {
                "source_id": "SSE:600340:ANN:INTERIM",
                "source_version": "2020-08-30:1",
                "title": "2020年半年度报告",
                "published_at": "2020-08-30",
                "url": "https://example.invalid/interim.pdf",
            },
            {
                "source_id": "SSE:600340:ANN:DIVIDEND",
                "source_version": "2021-04-20:1",
                "title": "2020年年度权益分派实施公告",
                "published_at": "2021-04-20",
                "url": "https://example.invalid/dividend.pdf",
            },
        ],
    }

    result = phase10_settlement_inventory.build_settlement_inventory(
        case=case,
        inventory=inventory,
        inventory_path=Path(phase10_settlement_inventory.ROOT) / "config" / "test-inventory.json",
        window_end="2021-04-27",
    )

    assert result["official_inventory"]["record_count"] == 2
    assert result["claim_read_plan"][0]["primary_source_ids"] == ["SSE:600340:ANN:INTERIM"]
    assert result["corporate_action_read_plan"]["candidate_source_ids"] == ["SSE:600340:ANN:DIVIDEND"]
    assert result["corporate_action_read_plan"]["body_acquisition_status"] == "NOT_STARTED"
