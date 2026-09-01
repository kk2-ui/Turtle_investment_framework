#!/usr/bin/env python3
"""Turn a complete official announcement inventory into a small settlement read plan.

This tool deliberately handles metadata only.  It does not open announcement
bodies, download PDFs, create price series, or infer actual operating facts.
Those happen only after the frozen case and this selection plan are recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.historical_backtest import validate_case
from scripts.phase10_acquisition import build_post_cutoff_reading_queue


PRIMARY_TITLE_TERMS = {
    "ORDINARY_CASH": ("2020年半年度报告", "2020年第三季度报告", "闲置募集资金"),
    "GOV_RECEIVABLES": ("2020年半年度报告", "2020年第三季度报告", "项目代建合作"),
    "DEBT_REFINANCING": ("部分债务未能如期偿还", "部分债务违约"),
    "GUARANTEE_RECOVERY": ("提供担保的进展情况", "为参股公司提供担保", "累计新增借款", "关联交易"),
}
CORPORATE_ACTION_TERMS = ("权益分派实施", "利润分配实施", "配股", "重整", "退市", "合并", "停牌", "复牌")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError as exc:
        raise ValueError(f"path must be inside repository: {path}") from exc


def _date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _primary_matches(title: str, terms: tuple[str, ...]) -> bool:
    return any(term in title for term in terms) and "摘要" not in title and "正文" not in title


def _matches(title: str, terms: tuple[str, ...]) -> bool:
    return any(term in title for term in terms)


def build_settlement_inventory(
    *, case: dict[str, Any], inventory: dict[str, Any], inventory_path: Path, window_end: str,
) -> dict[str, Any]:
    case_result = validate_case(case, allow_test_fixtures=False)
    freeze = case.get("report_freeze") if isinstance(case.get("report_freeze"), dict) else {}
    engineering_quality_failure = (
        freeze.get("mode") == "PIT_ENGINEERING"
        and freeze.get("report_status") == "FROZEN_WITH_QUALITY_FAILURE"
        and not case_result["invalid_findings"]
    )
    if case_result["state"] != "REVIEWABLE" and not engineering_quality_failure:
        raise ValueError("frozen case must be reviewable before opening the settlement window")
    cutoff = str(case.get("simulation_cutoff") or "")[:10]
    start = _date(cutoff) + timedelta(days=1)
    end = _date(window_end)
    if start > end:
        raise ValueError("settlement window is empty")
    if inventory.get("provider") != "SSE" or str(inventory.get("company_code") or "") != str(case.get("company_code") or "").split(".")[0]:
        raise ValueError("inventory is not the frozen case's SSE company inventory")
    if inventory.get("begin_date") != start.isoformat() or inventory.get("end_date") != end.isoformat():
        raise ValueError("inventory dates do not match the settlement window")
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    if len(records) != inventory.get("record_count"):
        raise ValueError("inventory record count does not reconcile")
    seen_ids: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("inventory record must be an object")
        source_id = str(item.get("source_id") or "")
        title = str(item.get("title") or "")
        published_at = str(item.get("published_at") or "")
        if not source_id or not title or source_id in seen_ids:
            raise ValueError("inventory has a missing or duplicate source identity")
        seen_ids.add(source_id)
        published = _date(published_at)
        if not start <= published <= end:
            raise ValueError("inventory includes a source outside its registered window")
        normalized.append({
            "source_id": source_id,
            "source_version": str(item.get("source_version") or ""),
            "title": title,
            "published_at": published_at,
            "url": str(item.get("url") or ""),
        })
    reading_queue = build_post_cutoff_reading_queue(inventory)
    queue_by_id = {
        str(record.get("source_id") or ""): record
        for record in reading_queue["records"] if isinstance(record, dict)
    }
    claims = (case.get("calibration_ledger") or {}).get("claims") or []
    claim_plan = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        key = next((key for key in PRIMARY_TITLE_TERMS if claim_id.endswith(key)), None)
        primary_terms = PRIMARY_TITLE_TERMS.get(key, ())
        candidate_ids = [
            record["source_id"] for record in normalized
            if claim_id in (queue_by_id.get(record["source_id"], {}).get("candidate_claim_ids") or [])
        ]
        primary_ids = [
            record["source_id"] for record in normalized
            if record["source_id"] in candidate_ids and _primary_matches(record["title"], primary_terms)
        ]
        matched_terms = sorted({
            term
            for source_id in candidate_ids
            for term in (queue_by_id.get(source_id, {}).get("matched_terms", {}).get(claim_id) or [])
        })
        claim_plan.append({
            "claim_id": claim_id,
            "observable_metric": ((claim.get("observable_outcome") or {}).get("metric")),
            "selection_terms": matched_terms,
            "primary_title_terms": list(primary_terms),
            "primary_source_ids": primary_ids,
            "discovery_source_ids": [source_id for source_id in candidate_ids if source_id not in set(primary_ids)],
            "body_acquisition_status": "NOT_STARTED",
        })
    corporate_action_ids = [
        record["source_id"] for record in normalized
        if any(term in record["title"] for term in CORPORATE_ACTION_TERMS)
    ]
    return {
        "schema_version": "phase10-settlement-inventory.v1",
        "status": "COMPLETE_METADATA_INVENTORY_BODY_ACQUISITION_PENDING",
        "case_id": case.get("case_id"),
        "experiment_id": case.get("experiment_id"),
        "freeze_id": ((case.get("report_freeze") or {}).get("freeze_id")),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "official_inventory": {
            "provider": "SSE",
            "inventory_path": _relative(inventory_path),
            "record_count": len(normalized),
            "source_ids": [record["source_id"] for record in normalized],
        },
        "claim_read_plan": claim_plan,
        "corporate_action_read_plan": {
            "selection_terms": list(CORPORATE_ACTION_TERMS),
            "candidate_source_ids": corporate_action_ids,
            "body_acquisition_status": "NOT_STARTED",
        },
        "market_data_plan": {
            "stock_price": "NOT_ACQUIRED: official unadjusted daily OHLC and trading-status series required after action plan is closed.",
            "benchmark": "NOT_ACQUIRED: official CSI 300 daily series and return-basis selection required.",
        },
        "body_acquisition_rule": "Open only primary official documents first. Use the discovery list only when a primary read leaves a frozen observable unresolved; preserve initial disclosure identity and keep non-comparable facts unresolved.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = _load_json(args.case.resolve())
    inventory = _load_json(args.inventory.resolve())
    payload = build_settlement_inventory(
        case=case,
        inventory=inventory,
        inventory_path=args.inventory.resolve(),
        window_end=args.window_end,
    )
    output = args.output.resolve()
    _relative(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": _relative(output),
        "record_count": payload["official_inventory"]["record_count"],
        "claim_primary_counts": {item["claim_id"]: len(item["primary_source_ids"]) for item in payload["claim_read_plan"]},
        "corporate_action_candidate_count": len(payload["corporate_action_read_plan"]["candidate_source_ids"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
