from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from scripts import cjo_quantitative_investment_overlay as overlay
from scripts import current_company_cjo_admission as current_admission
from scripts import enterprise_judgment_core as core
from scripts import enterprise_judgment_quantitative_adapter as legacy_adapter
from scripts import judgment_generation_handoff as generation_handoff
from scripts.judgment_handoff_receipts import validate_judgment_handoff_read_receipt
from scripts.turtle_agent.tools import read_tools, write_tools
from tests.test_enterprise_judgment_core import (
    _frozen_cjo,
    _judgment_input,
    _ledger,
    _model,
    _review,
    _source_package,
)


def _request(
    cjo: dict,
    *,
    price: float = 35.0,
    normalized_earnings: dict | None = None,
    d4_status: str = "CLOSED",
    cash_access_status: str = "ACCESSIBLE",
    permanent_loss_level: str = "LOW",
    capital_burden_status: str = "CLOSED",
) -> dict:
    normal_direction = cjo["normal_earnings_transmission"]["direction"]
    cash_direction = cjo["owner_cash_transmission"]["direction"]
    accessible_cash = {"low": 100.0, "base": 100.0, "high": 100.0}
    if cash_access_status in {"INACCESSIBLE", "UNKNOWN"}:
        accessible_cash = {"low": 0.0, "base": 0.0, "high": 0.0}
    return {
        "schema_version": overlay.REQUEST_SCHEMA_VERSION,
        "object_class": "CJO_QUANTITATIVE_INVESTMENT_OVERLAY_REQUEST",
        "overlay_id": "OVERLAY:SYNTHETIC:ONE",
        "mode": "SYNTHETIC_OFFLINE",
        "valuation_as_of": "2026-01-06T00:00:00+00:00",
        "cjo_ref": {
            "cjo_id": cjo["cjo_id"],
            "company_id": cjo["company_id"],
            "cutoff_at": cjo["cutoff_at"],
            "method_version": cjo["method_version"],
        },
        "cjo_admission": _synthetic_primary_admission(cjo),
        "financial_ranges": {
            "share_count": 10.0,
            "normalized_earnings": {
                "range": normalized_earnings or {"low": 48.0, "base": 64.0, "high": 80.0},
                "cjo_direction": normal_direction,
                "cjo_trace_ids": ["TRACE:OPERATING"],
            },
            "owner_cash": {
                "range": {"low": 35.0, "base": 50.0, "high": 65.0},
                "d4_status": d4_status,
                "cjo_direction": cash_direction,
                "cjo_trace_ids": ["TRACE:CASH"],
            },
        },
        "asset_identity": {
            "non_cash_common_equity": {"low": 300.0, "base": 320.0, "high": 340.0},
            "book_cash": {"low": 100.0, "base": 100.0, "high": 100.0},
            "accessible_common_cash": accessible_cash,
            "cash_access_status": cash_access_status,
            "capital_burden": {"low": 20.0, "base": 20.0, "high": 20.0},
            "capital_burden_status": capital_burden_status,
            "cjo_trace_ids": ["TRACE:CASH", "TRACE:LOSS"],
        },
        "valuation_method_identities": [
            {"method_id": "METHOD:ASSET", "identity": "ASSET_TO_COMMON_EQUITY"},
            {"method_id": "METHOD:EARNINGS", "identity": "NORMAL_EARNINGS_CAPITALIZATION", "capitalization_rate": 0.10},
            {"method_id": "METHOD:CASH", "identity": "OWNER_CASH_CAPITALIZATION", "capitalization_rate": 0.10},
        ],
        "price_snapshot": {
            "snapshot_id": "PRICE:SYNTHETIC:ONE",
            "source_ref": "SYNTHETIC_INDEPENDENT_PRICE_SNAPSHOT",
            "as_of": "2026-01-05T00:00:00+00:00",
            "market_price": price,
            "independence_status": "INDEPENDENT",
        },
        "return_contract": {
            "horizon_years": 3,
            "required_return": 0.10,
            "annual_distribution": {"low": 5.0, "base": 5.0, "high": 5.0},
        },
        "permanent_loss_assessment": {
            "level": permanent_loss_level,
            "rationale": "Synthetic, bounded permanent-loss assessment.",
            "cjo_trace_ids": ["TRACE:LOSS"],
        },
        "buy_band_policy": {"safety_margin": 0.20},
    }


def _synthetic_primary_admission(cjo: dict) -> dict:
    """A fixture-only persisted admission-shaped artifact for Overlay unit tests.

    The adapter integration tests exercise the real admission compiler.  This
    helper keeps the valuation tests focused on quantitative behavior while
    still proving that an unadmitted Core CJO cannot enter this downstream API.
    """
    review = cjo["independent_review_receipt"]
    return {
        "schema_version": current_admission.FROZEN_RECEIPT_VERSION,
        "admission_id": "CCJOADM:OVERLAY:FIXTURE",
        "status": current_admission.PRIMARY_ADMITTED,
        "cjo_ref": {
            key: cjo[key]
            for key in ("cjo_id", "company_id", "cutoff_at", "method_version", "resolution")
        },
        "candidate_binding": {
            "candidate_id": review["candidate_id"],
            "compiled_at": cjo["compiled_at"],
            "source_package_id": cjo["source_package"]["source_package_id"],
            "primary_binding": {"fixture": "synthetic-only"},
        },
        "independent_review_binding": {
            key: review[key] for key in ("review_id", "reviewer_id", "reviewed_at")
        },
        "authority": {
            "primary_cjo_admitted": True,
            "overlay_read_allowed": True,
            "report_read_allowed": True,
            "publication_authorization": False,
            "investment_authorization": False,
        },
    }


def _write_current_company_admission(path: Path, cjo: dict) -> Path:
    receipt_path = path / "current_company_cjo_admission.json"
    receipt_path.write_text(json.dumps(_synthetic_primary_admission(cjo)), encoding="utf-8")
    return receipt_path


def _no_primary_cjo() -> dict:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package), ledger=_ledger(), source_package=package,
        judgment_input=_judgment_input(resolution="NO_PRIMARY", central=False),
    )
    return core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))


def test_primary_cjo_compiles_to_candidate_only_asset_earnings_cash_overlay() -> None:
    cjo = _frozen_cjo()
    before = deepcopy(cjo)
    request = _request(cjo)
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=request)
    through_adapter = legacy_adapter.compile_cjo_to_quantitative_investment_overlay(
        frozen_cjo=cjo, overlay_request=request,
    )

    assert overlay.validate_investment_overlay(result)["state"] == "VALID"
    assert through_adapter == result
    assert cjo == before
    assert [item["identity"] for item in result["value_identities"]] == [
        "ASSET_TO_COMMON_EQUITY", "NORMAL_EARNINGS_CAPITALIZATION", "OWNER_CASH_CAPITALIZATION",
    ]
    assert result["price_overlay"]["expectation_gap"]["status"] == "EXPECTATION_GAP_UNIQUE_REFERENCE"
    assert result["buy_band"]["state"] == "CONDITIONAL_BUY_BAND"
    assert result["authority"]["overlay_status"] == "CANDIDATE_ONLY"
    assert result["authority"]["may_authorize_trading"] is False


def test_generic_frozen_cjo_cannot_bypass_the_current_company_admission_gate() -> None:
    cjo = _frozen_cjo()
    request = _request(cjo)
    request.pop("cjo_admission")

    validation = overlay.validate_overlay_request(frozen_cjo=cjo, overlay_request=request)

    assert validation["state"] == "INVALID"
    assert "overlay_request.missing:cjo_admission" in validation["findings"]


def test_price_changes_only_overlay_expectation_and_current_buyband_position() -> None:
    cjo = _frozen_cjo()
    before = deepcopy(cjo)
    low = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo, price=30.0))
    high = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo, price=90.0))

    assert cjo == before
    assert low["cjo_ref"] == high["cjo_ref"]
    assert low["financial_ranges"] == high["financial_ranges"]
    assert low["price_overlay"]["expectation_gap"]["value"] != high["price_overlay"]["expectation_gap"]["value"]
    assert low["buy_band"]["current_price_position"] != high["buy_band"]["current_price_position"]


def test_cjo_bound_normal_earnings_range_moves_value_and_research_boundary() -> None:
    cjo = _frozen_cjo()
    lower = overlay.compile_investment_overlay(
        frozen_cjo=cjo,
        overlay_request=_request(cjo, price=85.0, normalized_earnings={"low": 48.0, "base": 64.0, "high": 80.0}),
    )
    higher = overlay.compile_investment_overlay(
        frozen_cjo=cjo,
        overlay_request=_request(cjo, price=85.0, normalized_earnings={"low": 80.0, "base": 96.0, "high": 112.0}),
    )
    lower_earnings = lower["value_identities"][1]["per_share_value"]
    higher_earnings = higher["value_identities"][1]["per_share_value"]

    assert higher_earnings["base"] > lower_earnings["base"]
    assert higher["buy_band"]["research_zone"]["maximum_price"] > lower["buy_band"]["research_zone"]["maximum_price"]


def test_inaccessible_book_cash_cannot_be_added_to_common_equity_or_open_buyband() -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(
        frozen_cjo=cjo,
        overlay_request=_request(cjo, cash_access_status="INACCESSIBLE"),
    )
    asset_value = result["value_identities"][0]["total_common_equity_value"]

    assert result["asset_accessibility"]["book_cash_disclosed"]["base"] == 100.0
    assert result["asset_accessibility"]["accessible_common_cash_included"]["base"] == 0.0
    assert result["asset_accessibility"]["book_cash_directly_added_to_common_equity"] is False
    assert asset_value["base"] == 300.0
    assert result["buy_band"]["conditional_buy_zone"]["state"] == "CLOSED_CASH_ACCESSIBILITY"


def test_d4_open_and_high_permanent_loss_close_or_degrade_buyband() -> None:
    cjo = _frozen_cjo()
    d4_open = overlay.compile_investment_overlay(
        frozen_cjo=cjo, overlay_request=_request(cjo, d4_status="UNRESOLVED"),
    )
    high_risk = overlay.compile_investment_overlay(
        frozen_cjo=cjo, overlay_request=_request(cjo, permanent_loss_level="HIGH"),
    )

    assert d4_open["price_overlay"]["expectation_gap"]["status"] == "EXPECTATION_GAP_UNKNOWN_D4_OPEN"
    assert d4_open["buy_band"]["conditional_buy_zone"]["state"] == "CLOSED_D4_OWNER_CASH"
    assert high_risk["buy_band"]["state"] == "BUY_BAND_CLOSED"
    assert high_risk["buy_band"]["permanent_loss_closure"] is True


@pytest.mark.parametrize("cjo_factory", [_no_primary_cjo, lambda: _frozen_cjo(owner_cash_direction="DETERIORATES")])
def test_no_primary_and_mixed_cannot_enter_the_overlay_lane(cjo_factory) -> None:
    cjo = cjo_factory()
    with pytest.raises(overlay.CJOQuantitativeInvestmentOverlayError, match="current_company_cjo_admission"):
        overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))


def test_multiple_cjo_consistent_identities_return_expectation_gap_unknown() -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo, price=50.0))

    expectation = result["price_overlay"]["expectation_gap"]
    assert expectation["status"] == "EXPECTATION_GAP_UNKNOWN_MULTIPLE_PLAUSIBLE_PARAMETER_SETS"
    assert expectation["value"] is None
    assert {item["identity"] for item in result["price_overlay"]["price_implied_operating_requirements"]} == {
        "NORMAL_EARNINGS_CAPITALIZATION", "OWNER_CASH_CAPITALIZATION",
    }


def test_report_projection_reads_overlay_without_price_snapshot_or_mutation() -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    before = deepcopy(result)
    projection = overlay.build_overlay_report_projection(result)

    assert "market_price" not in json.dumps(projection)
    assert projection["authority"]["report_read_only"] is True
    assert projection["authority"]["may_modify_overlay"] is False
    projection["buy_band"]["state"] = "rewritten locally"
    assert result == before


def test_report_handoff_can_only_read_explicit_overlay(tmp_path: Path) -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    overlay_path = tmp_path / "canonical" / "investment_overlay.json"
    overlay_path.parent.mkdir()
    overlay_path.write_text(json.dumps(result), encoding="utf-8")
    cjo_path = tmp_path / "canonical" / "frozen_cjo.json"
    cjo_path.write_text(json.dumps(cjo), encoding="utf-8")
    admission_path = _write_current_company_admission(overlay_path.parent, cjo)
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "report_id": cjo["company_id"],
        "company_id": cjo["company_id"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "data_as_of": cjo["cutoff_at"],
        "canonical_judgment_refs": {
            "frozen_cjo_ref": str(cjo_path),
            "investment_overlay_ref": str(overlay_path),
            "current_company_cjo_admission_ref": str(admission_path),
        },
    }), encoding="utf-8")

    handoff = generation_handoff.build_judgment_generation_handoff(
        tmp_path, "INVESTMENT_ENRICHMENT", investment_overlay_path=overlay_path,
    )
    validation = generation_handoff.validate_judgment_generation_handoff(handoff, output_dir=tmp_path)

    assert validation["state"] == "READY"
    assert handoff["projection"]["quantitative_overlay"]["authority"]["report_read_only"] is True
    assert handoff["projection"]["quantitative_overlay"]["authority"]["may_modify_overlay"] is False
    assert any(item["role"] == "CJO_QUANTITATIVE_OVERLAY" for item in handoff["source_refs"])


def test_report_contract_binds_cjo_and_overlay_reads_and_stales_them_on_change(tmp_path: Path) -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    cjo_path = canonical / "frozen_cjo.json"
    overlay_path = canonical / "investment_overlay.json"
    cjo_path.write_text(json.dumps(cjo), encoding="utf-8")
    overlay_path.write_text(json.dumps(result), encoding="utf-8")
    admission_path = _write_current_company_admission(canonical, cjo)
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "report_id": cjo["company_id"],
        "company_id": cjo["company_id"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "data_as_of": cjo["cutoff_at"],
        "canonical_judgment_refs": {
            "frozen_cjo_ref": str(cjo_path),
            "investment_overlay_ref": str(overlay_path),
            "current_company_cjo_admission_ref": str(admission_path),
        },
    }), encoding="utf-8")

    synthesis = read_tools.read_judgment_generation_handoff(tmp_path, "JUDGMENT_SYNTHESIS")
    enrichment = read_tools.read_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")

    assert synthesis["read_receipt"]["state"] == "RECORDED"
    assert enrichment["read_receipt"]["state"] == "RECORDED"
    assert validate_judgment_handoff_read_receipt(tmp_path)["state"] == "READY"
    assert validate_judgment_handoff_read_receipt(tmp_path, "INVESTMENT_ENRICHMENT")["state"] == "READY"

    original = cjo_path.stat()
    os.utime(cjo_path, ns=(original.st_atime_ns, original.st_mtime_ns + 1))

    assert "judgment_synthesis_canonical_sources_changed_after_read" in validate_judgment_handoff_read_receipt(
        tmp_path,
    )["findings"]
    assert "investment_enrichment_canonical_sources_changed_after_read" in validate_judgment_handoff_read_receipt(
        tmp_path, "INVESTMENT_ENRICHMENT",
    )["findings"]


def test_cjo_or_overlay_path_cannot_bypass_the_analysis_contract(tmp_path: Path) -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    cjo_path = tmp_path / "frozen_cjo.json"
    overlay_path = tmp_path / "investment_overlay.json"
    cjo_path.write_text(json.dumps(cjo), encoding="utf-8")
    overlay_path.write_text(json.dumps(result), encoding="utf-8")
    admission_path = _write_current_company_admission(tmp_path, cjo)
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "report_id": cjo["company_id"],
        "company_id": cjo["company_id"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "data_as_of": cjo["cutoff_at"],
    }), encoding="utf-8")

    synthesis = generation_handoff.build_judgment_generation_handoff(
        tmp_path, "JUDGMENT_SYNTHESIS", frozen_cjo_path=cjo_path,
    )
    enrichment = generation_handoff.build_judgment_generation_handoff(
        tmp_path, "INVESTMENT_ENRICHMENT", investment_overlay_path=overlay_path,
    )

    assert "frozen_cjo_must_be_bound_in_analysis_contract" in synthesis["readiness"]["invalid_findings"]
    assert "investment_overlay_must_be_bound_in_analysis_contract" in enrichment["readiness"]["invalid_findings"]


def test_investment_report_assembly_requires_a_current_contract_bound_overlay_read(tmp_path: Path) -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    cjo_path = tmp_path / "frozen_cjo.json"
    overlay_path = tmp_path / "investment_overlay.json"
    cjo_path.write_text(json.dumps(cjo), encoding="utf-8")
    overlay_path.write_text(json.dumps(result), encoding="utf-8")
    admission_path = _write_current_company_admission(tmp_path, cjo)
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "report_id": cjo["company_id"],
        "company_id": cjo["company_id"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "data_as_of": cjo["cutoff_at"],
        "canonical_judgment_refs": {
            "frozen_cjo_ref": str(cjo_path),
            "investment_overlay_ref": str(overlay_path),
            "current_company_cjo_admission_ref": str(admission_path),
        },
    }), encoding="utf-8")
    read_tools.read_judgment_generation_handoff(tmp_path, "JUDGMENT_SYNTHESIS")

    with pytest.raises(RuntimeError, match="INVESTMENT_ENRICHMENT read receipt"):
        write_tools.assemble_report(str(tmp_path), "Synthetic", cjo["company_id"])


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("method_version", "METHOD:STALE"), ("resolution", "MIXED")],
)
def test_contract_bound_overlay_must_match_the_full_frozen_cjo_identity(
    tmp_path: Path, field: str, replacement: str,
) -> None:
    cjo = _frozen_cjo()
    result = overlay.compile_investment_overlay(frozen_cjo=cjo, overlay_request=_request(cjo))
    result["cjo_ref"][field] = replacement
    cjo_path = tmp_path / "frozen_cjo.json"
    overlay_path = tmp_path / "investment_overlay.json"
    cjo_path.write_text(json.dumps(cjo), encoding="utf-8")
    overlay_path.write_text(json.dumps(result), encoding="utf-8")
    admission_path = _write_current_company_admission(tmp_path, cjo)
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "report_id": cjo["company_id"],
        "company_id": cjo["company_id"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "data_as_of": cjo["cutoff_at"],
        "canonical_judgment_refs": {
            "frozen_cjo_ref": str(cjo_path),
            "investment_overlay_ref": str(overlay_path),
            "current_company_cjo_admission_ref": str(admission_path),
        },
    }), encoding="utf-8")
    assert read_tools.read_judgment_generation_handoff(
        tmp_path, "JUDGMENT_SYNTHESIS",
    )["readiness"]["state"] == "READY"
    enrichment = read_tools.read_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")

    assert "investment_overlay_invalid:overlay.current_company_cjo_admission_ref_invalid" in enrichment["readiness"]["invalid_findings"]
    assert validate_judgment_handoff_read_receipt(
        tmp_path, "INVESTMENT_ENRICHMENT",
    )["state"] == "BLOCKED"
    with pytest.raises(RuntimeError, match="INVESTMENT_ENRICHMENT read receipt"):
        write_tools.assemble_report(str(tmp_path), "Synthetic", cjo["company_id"])


def test_validator_rejects_training_or_outcome_inputs_and_schema_is_parseable() -> None:
    cjo = _frozen_cjo()
    request = _request(cjo)
    request["forecast"] = {"candidate": "must not be read"}
    validation = overlay.validate_overlay_request(frozen_cjo=cjo, overlay_request=request)
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "cjo_quantitative_investment_overlay_v1.schema.json").read_text(encoding="utf-8")
    )

    assert validation["state"] == "INVALID"
    assert any("forbidden_training_or_outcome_input" in item for item in validation["findings"])
    assert schema["properties"]["schema_version"]["const"] == overlay.SCHEMA_VERSION
