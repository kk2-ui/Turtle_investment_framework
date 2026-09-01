#!/usr/bin/env python3
"""Create the metadata-only diagnostic settlement for a PIT engineering case.

The initial record deliberately contains no post-cutoff body facts, market
prices, corporate actions, or cash flows.  It settles report coverage from the
frozen independent review while keeping operating and return outcomes explicit
as not calculable until targeted official documents are actually read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.historical_backtest import SETTLEMENT_SCHEMA_VERSION, validate_case, validate_settlement


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


def build_settlement(*, case: dict[str, Any], inventory: dict[str, Any], settlement_as_of: str) -> dict[str, Any]:
    case_result = validate_case(case, allow_test_fixtures=False)
    freeze = case.get("report_freeze") if isinstance(case.get("report_freeze"), dict) else {}
    engineering_quality_failure = (
        freeze.get("mode") == "PIT_ENGINEERING"
        and freeze.get("report_status") == "FROZEN_WITH_QUALITY_FAILURE"
        and not case_result["invalid_findings"]
    )
    if case_result["state"] != "REVIEWABLE" and not engineering_quality_failure:
        raise ValueError("case must be reviewable before a diagnostic settlement is created")
    if ((case.get("report_freeze") or {}).get("mode")) != "PIT_ENGINEERING":
        raise ValueError("this builder only supports PIT_ENGINEERING cases")
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    if not records or len(records) != inventory.get("record_count"):
        raise ValueError("a complete official metadata inventory is required")
    actual_sources = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("inventory record must be an object")
        actual_sources.append({
            "source_id": record.get("source_id"),
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "official": True,
            "published_at": record.get("published_at"),
            "source_version": record.get("source_version"),
            "data_as_of": record.get("data_as_of"),
            "source_access_status": "METADATA_ONLY_BODY_NOT_READ",
        })
    freeze = case.get("report_freeze") or {}
    review = freeze.get("independent_review") or {}
    claim_reviews = review.get("claim_reviews") if isinstance(review.get("claim_reviews"), list) else []
    claims = ((case.get("calibration_ledger") or {}).get("claims")) or []
    claim_settlements = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("frozen claim must be an object")
        disposition = claim.get("frozen_disposition")
        claim_settlements.append({
            "claim_id": claim.get("claim_id"),
            "frozen_disposition": disposition,
            "status": "UNRESOLVED_AS_OF_SETTLEMENT" if disposition == "UNKNOWN" else "NOT_CALCULABLE",
            "observation_ids": [],
        })
    base_currency = ((case.get("taxes_fees_fx") or {}).get("base_currency"))
    return {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": "HBTSET:" + str(case.get("case_id") or "").removeprefix("HBTCASE:") + ":METADATA_DIAGNOSTIC",
        "experiment_id": case.get("experiment_id"),
        "case_id": case.get("case_id"),
        "freeze_id": freeze.get("freeze_id"),
        "settlement_as_of": settlement_as_of,
        "actual_sources": actual_sources,
        "operating_source_timeline": {
            "enumeration_status": "COMPLETE",
            "source_ids": [source.get("source_id") for source in actual_sources],
        },
        "actual_outcomes": {
            "currency": base_currency,
            "cash_flows": [],
            "operating_observations": [],
        },
        "report_coverage": {
            "status": "PASS",
            "review_id": review.get("review_id"),
            "claim_reviews": [{
                "claim_id": item.get("claim_id"),
                "disposition": item.get("disposition"),
                "source_ids": item.get("source_ids"),
            } for item in claim_reviews if isinstance(item, dict)],
            "supported_claim_count": sum(1 for item in claim_reviews if item.get("disposition") == "SUPPORTED"),
            "unsupported_claim_count": sum(1 for item in claim_reviews if item.get("disposition") == "UNSUPPORTED"),
            "unknowns_preserved": all(
                item.get("disposition") == "UNKNOWN_PRESERVED"
                for item in claim_reviews if isinstance(item, dict)
                and any(claim.get("claim_id") == item.get("claim_id") and claim.get("frozen_disposition") == "UNKNOWN" for claim in claims if isinstance(claim, dict))
            ),
            "notes": ["Coverage is replayed from the frozen independent review; it is not a return score."],
        },
        "model_forecast_error": {
            "status": "NOT_CALCULABLE",
            "claim_settlements": claim_settlements,
            "metrics": [],
            "notes": ["Only official announcement metadata has been acquired; no body fact is treated as an actual observation."],
        },
        "investment_return_outcome": {
            "status": "NOT_CALCULABLE",
            "action": "UNKNOWN",
            "frozen_action": "UNKNOWN",
            "frozen_price_identity": "UNKNOWN",
            "total_return": None,
            "benchmark_return": None,
            "currency": base_currency,
            "notes": ["No investment action, official raw price series, corporate-action treatment, or benchmark series is frozen."],
            "execution": {
                "execution_rule": "No investment action was frozen in the PIT engineering case.",
                "fill_status": "NOT_APPLICABLE",
                "entry": {"date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
                "exit": {"status": "NOT_APPLICABLE", "date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
            },
            "cash_flow_ledger": [],
            "corporate_actions": [],
            "taxes_fees_fx": case.get("taxes_fees_fx"),
            "benchmark_identity": {
                "benchmark_id": "UNAVAILABLE",
                "market": "CN",
                "currency": base_currency,
                "return_basis": "PRICE_RETURN",
                "calculation_rule": "No official CSI 300 series has been acquired.",
                "source_ids": [],
            },
        },
        "status": "INCOMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--settlement-as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = _load_json(args.case.resolve())
    inventory = _load_json(args.inventory.resolve())
    settlement = build_settlement(case=case, inventory=inventory, settlement_as_of=args.settlement_as_of)
    result = validate_settlement(settlement, case=case, allow_test_fixtures=False)
    if result["invalid_findings"] or result["state"] != "INCOMPLETE":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    output = args.output.resolve()
    _relative(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(settlement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": _relative(output),
        "report_coverage": settlement["report_coverage"]["status"],
        "model_forecast_error": settlement["model_forecast_error"]["status"],
        "investment_return_outcome": settlement["investment_return_outcome"]["status"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
