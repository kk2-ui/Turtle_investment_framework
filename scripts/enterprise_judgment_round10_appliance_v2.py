#!/usr/bin/env python3
"""Round 10 appliance batch: blind, field-local method-review candidates.

This is a narrow batch adapter.  It freezes a common fact budget, distinct
baseline/enhanced resolution rules, and field-local outcome contracts for the
three predeclared appliance companies.  It deliberately does *not* accept a
method result: it can emit only an independent-review candidate after a
mechanical settlement has been supplied by the existing acquisition and
settlement modules.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
from typing import Any


SCHEMA_VERSION = "enterprise-judgment-round10-appliance-v2.v1"
METHOD_EPOCH_ID = "EPOCH:CN-APPLIANCE:ROUND10:EIGHT-DIMENSION:V2"
CUTOFF_AT = "2018-09-30T23:59:59+08:00"
FROZEN_AT = "2018-10-01T09:00:00+08:00"
OUTCOME_WINDOW = {
    "period_start": "2019-01-01T00:00:00+08:00",
    "period_end": "2019-12-31T23:59:59+08:00",
    "fiscal_period": "FY2019_STRICT_POST_CUTOFF",
    "settlement_due_at": "2020-06-30T23:59:59+08:00",
}
RIGHTS = {
    "method_transfer": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "buy_band": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}
ENTERPRISE_SETTLEMENT_RIGHTS = {
    "directional_learning": "NOT_AUTHORIZED",
    "enterprise_learning": "NOT_AUTHORIZED",
    "comparative": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}
DIMENSIONS = (
    "INITIAL_CONDITIONS_AND_BOUNDARY",
    "IMPLEMENTED_MANAGEMENT_ACTION",
    "EXECUTION_CAPABILITY",
    "CUSTOMER_AND_COMPETITION_RESPONSE",
    "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_AND_CAPITAL",
    "ADAPTATION_AND_PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION",
)
FIELD_KINDS = {
    "REVENUE": "CONSOLIDATED_REVENUE_RMB",
    "OPERATING_CASH_FLOW": "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
    "TOTAL_ASSETS": "CONSOLIDATED_TOTAL_ASSETS_RMB",
    "PRODUCT_REVENUE": "PRODUCT_REVENUE_RMB",
}
ROSTER = (
    {
        "company_id": "CN:002035",
        "issuer_id": "ISSUER:CN:002035",
        "security_code": "002035",
        "company_name": "华帝股份",
        "arena_id": "ARENA:CN:KITCHEN_APPLIANCE:GAS_AND_COOKING",
        "arena_statement": "燃气灶具、吸油烟机及厨房电器；不作为其他两家公司的同行对照。",
    },
    {
        "company_id": "CN:002508",
        "issuer_id": "ISSUER:CN:002508",
        "security_code": "002508",
        "company_name": "老板电器",
        "arena_id": "ARENA:CN:KITCHEN_APPLIANCE:PREMIUM_CHANNEL",
        "arena_statement": "高端厨房电器与渠道系统；不作为其他两家公司的同行对照。",
    },
    {
        "company_id": "CN:002677",
        "issuer_id": "ISSUER:CN:002677",
        "security_code": "002677",
        "company_name": "浙江美大",
        "arena_id": "ARENA:CN:INTEGRATED_STOVE:PRODUCT_SYSTEM",
        "arena_statement": "集成灶产品系统；不作为其他两家公司的同行对照。",
    },
)


class Round10ValidationError(ValueError):
    """A Round 10 pre-outcome or review-candidate object is invalid."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _company(company_id: str) -> dict[str, str]:
    for row in ROSTER:
        if row["company_id"] == company_id:
            return deepcopy(row)
    raise Round10ValidationError("round10_company_not_in_predeclared_roster")


def _scalar_or_declared_typed_object(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return not isinstance(value, float) or math.isfinite(value)
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        return False
    return value["type"] in {"LOCAL_UNKNOWN", "CONSERVATIVE_RANGE", "EVIDENCE_REQUIREMENT"} and _scalar_or_declared_typed_object(value["value"])


def build_method_epoch() -> dict[str, Any]:
    """Freeze the V2 rules without claiming any method acceptance."""
    return {
        "schema_version": "enterprise-judgment-round10-method-epoch.v2",
        "epoch_id": METHOD_EPOCH_ID,
        "frozen_at": FROZEN_AT,
        "baseline_resolution_rule": {
            "rule_id": "R10:BASELINE:ISSUER_FINANCIAL_TREND",
            "inputs": ["REVENUE", "OPERATING_CASH_FLOW"],
            "output": "OPERATING_TRAJECTORY_CONTINUE_OR_ESCALATE",
            "prohibited_inference": "Issuer revenue and cash do not prove customer response, management effect, unit economics or owner cash.",
        },
        "enhanced_resolution_rule": {
            "rule_id": "R10:ENHANCED:EIGHT_DIMENSION_BOUNDARY_FIRST",
            "dimensions": list(DIMENSIONS),
            "output": "EIGHT_DIMENSION_TREATMENT_CANDIDATE",
            "prohibited_inference": "No dimension count, completeness count or UNKNOWN count is a method advantage.",
        },
        "treatment_deltas": [{
            "treatment_delta_id": "R10:DELTA:ISSUER_CASH_NOT_OWNER_CASH",
            "baseline_treatment": "CONTINUE_OPERATING_UNDERWRITING",
            "enhanced_treatment": "REQUIRE_OWNER_CASH_AND_BOUNDARY_EVIDENCE",
            "explanatory_dimensions": [
                "WORKING_CAPITAL_CASH_AND_CAPITAL",
                "ADAPTATION_AND_PERMANENT_LOSS",
                "STRONGEST_ALTERNATIVE_EXPLANATION",
            ],
            "method_advantage_count": 1,
            "status": "PRE_OUTCOME_RULE_ONLY",
        }],
        "review_gate": {
            "code_only_output": "INDEPENDENT_REVIEW_CANDIDATE_ONLY",
            "permitted_utility_conditions": [
                "ENHANCED_MATERIALLY_CHANGES_PREDECLARED_TREATMENT",
                "BASELINE_DIRECTIONAL_ERROR_AVOIDED_BY_ENHANCED_PREDECLARED_RULE",
            ],
            "not_sufficient": [
                "MORE_EXPLANATION", "MORE_DIMENSIONS", "MORE_UNKNOWN", "MORE_COVERAGE",
            ],
        },
        "object_class": "ROUND10_METHOD_EPOCH",
        "claim_class": "PRE_OUTCOME_REVIEW_RULES_ONLY",
        "allowed_outputs": ["PREOUTCOME_BATCH_FREEZE", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def validate_method_epoch(epoch: Any) -> dict[str, Any]:
    item = _mapping(epoch)
    findings: list[str] = []
    expected = build_method_epoch()
    if set(item) != set(expected):
        findings.append("method_epoch_closed_shape_required")
        return {"valid": False, "findings": findings}
    if item.get("schema_version") != expected["schema_version"] or item.get("epoch_id") != METHOD_EPOCH_ID:
        findings.append("method_epoch_identity_invalid")
    if _instant(item.get("frozen_at")) is None:
        findings.append("method_epoch_frozen_at_must_be_timezone_aware")
    if item.get("baseline_resolution_rule") != expected["baseline_resolution_rule"]:
        findings.append("method_epoch_baseline_rule_must_equal_frozen_rule")
    if item.get("enhanced_resolution_rule") != expected["enhanced_resolution_rule"]:
        findings.append("method_epoch_enhanced_rule_must_equal_frozen_rule")
    deltas = _items(item.get("treatment_deltas"))
    ids = [delta.get("treatment_delta_id") for delta in deltas if isinstance(delta, dict)]
    if deltas != expected["treatment_deltas"] or len(ids) != len(set(ids)):
        findings.append("method_epoch_treatment_deltas_must_equal_frozen_unique_set")
    elif any(delta["method_advantage_count"] != 1 for delta in deltas):
        findings.append("method_epoch_each_treatment_delta_can_count_once")
    if item.get("review_gate") != expected["review_gate"]:
        findings.append("method_epoch_review_gate_must_equal_frozen_rule")
    if item.get("object_class") != expected["object_class"] or item.get("claim_class") != expected["claim_class"]:
        findings.append("method_epoch_object_identity_invalid")
    if item.get("allowed_outputs") != expected["allowed_outputs"] or item.get("rights") != RIGHTS:
        findings.append("method_epoch_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings, "epoch": deepcopy(item) if not findings else None}


def _flow_clock() -> dict[str, Any]:
    return {"clock_kind": "FLOW_PERIOD", "flow_period": {"period_start": "2019-01-01", "period_end": "2019-12-31", "fiscal_period": "FY2019"}}


def _balance_clock() -> dict[str, Any]:
    return {"clock_kind": "BALANCE_AS_OF", "balance_as_of": {"as_of": "2019-12-31", "fiscal_period": "FY2019"}}


def _boundary(company: dict[str, str]) -> dict[str, str]:
    return {
        "responsibility_unit_id": f"ISSUER_CONSOLIDATED:{company['company_id']}",
        "perimeter_id": f"PERIMETER:{company['company_id']}:LISTED_CONSOLIDATED",
        "arena_id": company["arena_id"],
        "scope_requirement": "Listed-consolidated issuer result; it is not a product-arena, customer-preference, action-effect or ordinary-share-owner-cash conclusion.",
    }


def _raw(company: dict[str, str], name: str, *, unit: str, clock: dict[str, Any], table: str, line: str) -> dict[str, Any]:
    period_column = _mapping(clock.get("flow_period") or clock.get("balance_as_of")).get("fiscal_period")
    return {
        "field_id": f"FIELD:{company['security_code']}:FY2019:{name}",
        "role": "OUTCOME",
        "unit": unit,
        "measurement_clock": deepcopy(clock),
        "locator": {"table_or_note": table, "line_item": line, "period_column": period_column},
    }


def _cell(company: dict[str, str], *, name: str, layer: str, clock: dict[str, Any], table: str, line: str, baseline_field_id: str, decrease: float, increase: float) -> dict[str, Any]:
    raw = _raw(company, name, unit="RMB", clock=clock, table=table, line=line)
    return {
        "cell_id": f"CELL:R10:{company['security_code']}:FY2019:{name}",
        "thread_id": f"THREAD:R10:{company['security_code']}:ISSUER_BOUNDARY",
        "layer": layer,
        "outcome_period": deepcopy({key: value for key, value in OUTCOME_WINDOW.items() if key != "settlement_due_at"}),
        "measurement_clock": deepcopy(clock),
        "responsibility_boundary": _boundary(company),
        "field_identity": {
            "outcome_field_id": raw["field_id"], "baseline_field_id": baseline_field_id,
            "statement_scope": "FY2019_STRICT_POST_CUTOFF", "table_or_note": table,
            "line_item": line, "field_kind": "AUDITED_OR_RECOMPUTABLE_ANNUAL_REPORT_LINE_ITEM",
        },
        "unit": {"kind": "VALUE", "currency": "RMB", "scale": "1"},
        "raw_input_fields": [raw],
        "formula": {
            "operator": "RAW_VALUE", "input_field_ids": [raw["field_id"]], "expression": raw["field_id"],
            "unit_conversions": [{"field_id": raw["field_id"], "from_unit": "RMB", "to_unit": "RMB", "scale": "1"}],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        "label_rule": {"type": "ABSOLUTE_CHANGE_BAND", "decrease_lte": decrease, "increase_gte": increase, "ordered_labels": ["MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE", "OBSERVED_INCREASE", "UNKNOWN"]},
        "conflict_rule": {"multiple_values": "MEASUREMENT_MISMATCH", "boundary_conflict": "MEASUREMENT_MISMATCH", "period_conflict": "MEASUREMENT_MISMATCH"},
        "unknown_rule": {"conditions": ["contracted annual line item absent from the authorised report"], "label": "UNKNOWN"},
        "mismatch_rule": {"conditions": ["scope, statement, period, unit, row identity or source version mismatch"], "label": "MEASUREMENT_MISMATCH", "propagation": "LOCAL_ONLY", "dependent_cell_ids": []},
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": "This issuer line item cannot on its own establish customer response, management-action effect, unit economics or ordinary-share owner cash.",
    }


def build_measurement_contract(company_id: str, *, baseline_values: dict[str, float], outcome_route: dict[str, str]) -> dict[str, Any]:
    """Build a V3 contract with three independently settleable annual fields."""
    company = _company(company_id)
    required_baseline = {"REVENUE", "OPERATING_CASH_FLOW", "TOTAL_ASSETS"}
    if set(baseline_values) != required_baseline or any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) for value in baseline_values.values()):
        raise Round10ValidationError("round10_baseline_values_must_cover_three_finite_fields")
    if set(outcome_route) != {"source_id", "official_url", "authorization_receipt_id"}:
        raise Round10ValidationError("round10_outcome_route_identity_invalid")
    cells = [
        _cell(company, name="REVENUE", layer="SALES_VOLUME", clock=_flow_clock(), table="consolidated income statement", line="operating revenue", baseline_field_id=f"FIELD:{company['security_code']}:FY2017:REVENUE", decrease=baseline_values["REVENUE"] * .9, increase=baseline_values["REVENUE"] * 1.1),
        _cell(company, name="OPERATING_CASH_FLOW", layer="CASH", clock=_flow_clock(), table="consolidated cash-flow statement", line="net cash flows from operating activities", baseline_field_id=f"FIELD:{company['security_code']}:FY2017:OPERATING_CASH_FLOW", decrease=baseline_values["OPERATING_CASH_FLOW"] * .8, increase=baseline_values["OPERATING_CASH_FLOW"] * 1.2),
        _cell(company, name="TOTAL_ASSETS", layer="FINANCING", clock=_balance_clock(), table="consolidated balance sheet", line="total assets", baseline_field_id=f"FIELD:{company['security_code']}:FY2017:TOTAL_ASSETS", decrease=baseline_values["TOTAL_ASSETS"] * .85, increase=baseline_values["TOTAL_ASSETS"] * 1.15),
    ]
    return {
        "schema_version": "enterprise-outcome-measurement-contract.v3",
        "contract_set_id": f"OMC:R10:{company['security_code']}:20180930:FY2019:V2",
        "package_ref": f"R10PKG:{company['security_code']}:20180930:V2",
        "company_id": company_id,
        "cutoff_at": CUTOFF_AT,
        "outcome_window": deepcopy(OUTCOME_WINDOW),
        "source_access": {
            "source_id": outcome_route["source_id"], "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT", "official_url": outcome_route["official_url"],
            "published_after_cutoff": True, "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT", "custodian_access": "OUTCOME_ONLY",
            "issuer_id": company["issuer_id"], "report_period_end": "2019-12-31", "availability_precision": "DATE_ONLY",
            "source_available_at": None, "source_available_date": "2020-04-30", "authorization_receipt_id": outcome_route["authorization_receipt_id"],
        },
        "atomic_cells": cells,
        "thread_combination_rules": [{
            "rule_id": f"R10:COMBINATION:{company['security_code']}:ISSUER_FINANCIAL_CONTEXT",
            "thread_id": cells[0]["thread_id"], "input_cell_ids": [cell["cell_id"] for cell in cells],
            "evaluation_order": [cell["cell_id"] for cell in cells],
            "rule": "Use each field only as issuer-boundary context; unavailable siblings remain local.",
            "conflict_rule": "No customer, action, unit-economics or owner-cash conclusion follows from this group.",
            "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
        }],
        "freeze_state": "PRE_OUTCOME_FROZEN", "contract_frozen_at": FROZEN_AT,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
        "rights": deepcopy(ENTERPRISE_SETTLEMENT_RIGHTS), "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }


def _minimal_metric_id(metric: str) -> str:
    return {
        "REVENUE": "ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB",
        "OPERATING_CASH_FLOW": "ISSUER_CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
        "TOTAL_ASSETS": "ISSUER_CONSOLIDATED_TOTAL_ASSETS_RMB",
    }[metric]


def _minimal_prediction_direction(metric: str) -> str:
    # This is the common simple trend baseline.  The enhanced method changes
    # the investment treatment around boundary/owner cash, not the signed
    # accounting observation itself.
    return {"REVENUE": "INCREASE", "OPERATING_CASH_FLOW": "STABLE", "TOTAL_ASSETS": "STABLE"}[metric]


def build_minimal_field_chains(*, company_id: str, source_packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Project one immutable V2 Minimal chain per frozen accounting field.

    This deliberately reuses the existing route-aware Minimal lane rather
    than creating a Round10 outcome reader or a second settlement engine.
    The batch wrapper only groups three independent field contracts so a
    mismatch in one can never suppress the other two.
    """
    try:
        from scripts import minimal_historical_episode as minimal
    except ModuleNotFoundError:  # pragma: no cover
        import minimal_historical_episode as minimal
    company = _company(company_id)
    fields = _mapping(source_packet).get("baseline_fields")
    route = _mapping(source_packet).get("value_free_outcome_route")
    if not isinstance(fields, dict) or set(fields) != {"REVENUE", "OPERATING_CASH_FLOW", "TOTAL_ASSETS"}:
        raise Round10ValidationError("round10_source_packet_requires_three_baseline_fields")
    if not isinstance(route, dict) or set(route) != {"organization_id", "security_code"}:
        raise Round10ValidationError("round10_source_packet_requires_value_free_route_identity")
    if route["security_code"] != company["security_code"] or not _text(route["organization_id"]):
        raise Round10ValidationError("round10_source_packet_route_identity_mismatch")
    chains: list[dict[str, Any]] = []
    for metric, field_value in fields.items():
        field = _mapping(field_value)
        required = {"source_id", "source_url", "published_at", "field_ref", "numeric_value", "exact_quote", "statement", "scope_note"}
        if set(field) != required:
            raise Round10ValidationError(f"round10_source_field_shape_invalid:{metric}")
        if not isinstance(field["numeric_value"], (int, float)) or isinstance(field["numeric_value"], bool) or not math.isfinite(float(field["numeric_value"])):
            raise Round10ValidationError(f"round10_source_field_numeric_value_invalid:{metric}")
        metric_id = _minimal_metric_id(metric)
        prefix = f"R10:{company['security_code']}:{metric}:FY2019"
        roles = {
            "forecaster_id": f"ROLE:{prefix}:FORECASTER",
            "custodian_id": f"ROLE:{prefix}:INDEPENDENT_CUSTODIAN",
        }
        decision = {
            "schema_version": minimal.DECISION_CONTRACT_SCHEMA_VERSION,
            "decision_contract_id": f"MHE:DECISION:{prefix}:V2", "decision_contract_version": 1,
            "company_id": company_id, "issuer_id": company["issuer_id"], "cutoff_at": CUTOFF_AT,
            "metric_id": metric_id, "window_id": "ONE_YEAR", "decision_purpose": minimal.DECISION_PURPOSE,
            "roles": roles, "object_class": "MINIMAL_HISTORICAL_DECISION_CONTRACT",
            "claim_class": "ONE_METRIC_DIRECTIONAL_DECISION_SCOPE", "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
            "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }
        decision_ref = {"decision_contract_id": decision["decision_contract_id"], "decision_contract_version": 1}
        technical_route_identity = {
            "schema_version": minimal.TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION,
            "technical_route_identity_id": f"MHE:ROUTE:{prefix}:V2", "technical_route_identity_version": 1,
            "decision_contract_ref": decision_ref, "company_id": company_id, "issuer_id": company["issuer_id"],
            "security_code": company["security_code"], "organization_id": route["organization_id"],
            "resolver_endpoint": minimal.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT,
            "resolver_version": minimal.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION, "observed_at": FROZEN_AT,
            "object_class": "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY", "claim_class": "TECHNICAL_ROUTE_IDENTITY",
            "allowed_outputs": list(minimal.ALLOWED_OUTPUTS), "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }
        contract = {
            "schema_version": minimal.MEASUREMENT_CONTRACT_SCHEMA_VERSION,
            "measurement_contract_id": f"MHE:CONTRACT:{prefix}:V2", "measurement_contract_version": 2,
            "company_id": company_id, "issuer_id": company["issuer_id"], "cutoff_at": CUTOFF_AT,
            "metric_id": metric_id, "window_id": "ONE_YEAR", "decision_contract_ref": decision_ref,
            "outcome_period_end": "2019-12-31", "responsibility_boundary": f"LISTED_ISSUER_CONSOLIDATED:{company['security_code']}",
            "unit": "RMB", "settlement_tolerance": 0.0,
            "technical_route_identity_ref": {"technical_route_identity_id": technical_route_identity["technical_route_identity_id"], "technical_route_identity_version": 1},
            "outcome_acquisition_route": {
                "provider": minimal.CNINFO_OUTCOME_ROUTE_PROVIDER, "provider_version": minimal.CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION,
                "security_code": company["security_code"], "organization_id": route["organization_id"],
                "tab_name": minimal.CNINFO_OUTCOME_ROUTE_TAB, "announcement_category": minimal.CNINFO_OUTCOME_ROUTE_CATEGORY,
                "begin_date": "2020-01-01", "end_date": "2020-06-30", "page_size": 30,
                "static_pdf_url_policy": minimal.CNINFO_OUTCOME_ROUTE_URL_POLICY,
                "annual_report_version_policy": minimal.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
            },
            "roles": roles, "object_class": "MINIMAL_HISTORICAL_MEASUREMENT_CONTRACT",
            "claim_class": "ONE_METRIC_PRE_OUTCOME_SCOPE", "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
            "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }
        contract_ref = {"measurement_contract_id": contract["measurement_contract_id"], "measurement_contract_version": 2}
        evidence = {
            "schema_version": minimal.STATIC_EVIDENCE_SCHEMA_VERSION,
            "evidence_receipt_id": f"MHE:EVIDENCE:{prefix}:V2", "evidence_receipt_version": 1,
            "measurement_contract_ref": contract_ref, "company_id": company_id, "issuer_id": company["issuer_id"],
            "cutoff_at": CUTOFF_AT, "metric_id": metric_id, "window_id": "ONE_YEAR",
            "curator_id": str(source_packet["curator_id"]),
            "source": {
                "source_id": field["source_id"], "source_url": field["source_url"], "source_type": minimal.OFFICIAL_STATIC_FILING,
                "published_at": field["published_at"], "issuer_id": company["issuer_id"], "metric_id": metric_id,
                "responsibility_boundary": contract["responsibility_boundary"], "unit": "RMB", "field_ref": field["field_ref"],
                "numeric_value": float(field["numeric_value"]),
            },
            "object_class": "MINIMAL_HISTORICAL_STATIC_EVIDENCE", "claim_class": "CUTOFF_VISIBLE_OFFICIAL_FIELD",
            "allowed_outputs": list(minimal.ALLOWED_OUTPUTS), "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }
        prediction = {
            "schema_version": minimal.PREDICTION_SCHEMA_VERSION,
            "prediction_id": f"MHE:PREDICTION:{prefix}:V2", "measurement_contract_ref": contract_ref,
            "evidence_receipt_ref": {"evidence_receipt_id": evidence["evidence_receipt_id"], "evidence_receipt_version": 1},
            "company_id": company_id, "issuer_id": company["issuer_id"], "cutoff_at": CUTOFF_AT,
            "metric_id": metric_id, "window_id": "ONE_YEAR", "forecaster_id": roles["forecaster_id"],
            "predicted_direction": _minimal_prediction_direction(metric), "object_class": "MINIMAL_HISTORICAL_PREDICTION",
            "claim_class": "ONE_METRIC_DIRECTIONAL_PREDICTION", "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
            "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }
        chains.append({
            "metric": metric, "exact_quote": field["exact_quote"], "statement": field["statement"], "scope_note": field["scope_note"],
            "decision_contract": decision, "technical_route_identity": technical_route_identity,
            "measurement_contract": contract, "static_evidence": evidence, "prediction": prediction,
        })
    return chains


def build_real_source_packets() -> list[dict[str, Any]]:
    """Return the three independent, cutoff-before curator projections.

    These rows retain only the facts needed to freeze Round10.  They do not
    include a FY2019 announcement identity, result value, label, price, peer,
    or comparative conclusion.  Exact quotations remain in the independent
    curator artifacts referenced by each `source_packet_id`.
    """
    return [
        {
            "source_packet_id": "ROUND10-CN002035-PREOUTCOME-CURATOR-V1", "company_id": "CN:002035", "cutoff_at": CUTOFF_AT,
            "curator_id": "ROLE:ROUND10:CN002035:INDEPENDENT_PREOUTCOME_CURATOR", "outcome_content_read": False,
            "fact_locators": ["CNINFO:1204805433:PDF p.81", "CNINFO:1204805433:PDF p.86", "CNINFO:1204805433:PDF p.77", "CNINFO:1204805433:PDF p.27", "CNINFO:1204805433:PDF p.26", "CNINFO:1204805433:PDF p.44"],
            "baseline_fields": {
                "REVENUE": {"source_id": "CNINFO:1204805433", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-27/1204805433.PDF", "published_at": "2018-04-27", "field_ref": "PDF p.81", "numeric_value": 5730696745.31, "exact_quote": "一、营业总收入 5,730,696,745.31 4,395,036,328.15；其中：营业收入 5,730,696,745.31 4,395,036,328.15", "statement": "CONSOLIDATED_INCOME_STATEMENT", "scope_note": "Reported consolidated FY2017 income statement; FY2017 scope changes require local outcome-period confirmation."},
                "OPERATING_CASH_FLOW": {"source_id": "CNINFO:1204805433", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-27/1204805433.PDF", "published_at": "2018-04-27", "field_ref": "PDF p.86", "numeric_value": 368534466.66, "exact_quote": "经营活动产生的现金流量净额 368,534,466.66 818,413,634.83", "statement": "CONSOLIDATED_CASH_FLOW_STATEMENT", "scope_note": "Issuer operating cash only; it cannot be promoted to ordinary-share owner cash."},
                "TOTAL_ASSETS": {"source_id": "CNINFO:1204805433", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-27/1204805433.PDF", "published_at": "2018-04-27", "field_ref": "PDF p.77", "numeric_value": 4210485308.94, "exact_quote": "资产总计 4,210,485,308.94 3,593,298,595.69", "statement": "CONSOLIDATED_BALANCE_SHEET", "scope_note": "Point-in-time consolidated assets; not a standalone unit-economics or capital-allocation conclusion."},
            },
            "implemented_action": {"status": "OBSERVED_PRE_CUTOFF", "source_locator": "CNINFO:1204805433:PDF p.27"},
            "value_free_outcome_route": {"security_code": "002035", "organization_id": "gssz0002035"},
        },
        {
            "source_packet_id": "ROUND10-CN002508-PREOUTCOME-CURATOR-V1", "company_id": "CN:002508", "cutoff_at": CUTOFF_AT,
            "curator_id": "ROLE:ROUND10:CN002508:INDEPENDENT_PREOUTCOME_CURATOR", "outcome_content_read": False,
            "fact_locators": ["CNINFO:1204595205:PDF p.63", "CNINFO:1204595205:PDF p.67", "CNINFO:1204595205:PDF p.58", "CNINFO:1204595205:PDF p.12"],
            "baseline_fields": {
                "REVENUE": {"source_id": "CNINFO:1204595205", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-10/1204595205.PDF", "published_at": "2018-04-10", "field_ref": "PDF p.63", "numeric_value": 7017397057.99, "exact_quote": "一、营业总收入 7,017,397,057.99 5,794,897,867.13；其中：营业收入 7,017,397,057.99 5,794,897,867.13", "statement": "CONSOLIDATED_INCOME_STATEMENT", "scope_note": "Reported consolidated income statement; re-statement status remains local UNKNOWN until the outcome version is resolved."},
                "OPERATING_CASH_FLOW": {"source_id": "CNINFO:1204595205", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-10/1204595205.PDF", "published_at": "2018-04-10", "field_ref": "PDF p.67", "numeric_value": 1256125454.23, "exact_quote": "经营活动产生的现金流量净额 1,256,125,454.23 1,545,448,492.32", "statement": "CONSOLIDATED_CASH_FLOW_STATEMENT", "scope_note": "Issuer operating cash only; it cannot be promoted to ordinary-share owner cash."},
                "TOTAL_ASSETS": {"source_id": "CNINFO:1204595205", "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-10/1204595205.PDF", "published_at": "2018-04-10", "field_ref": "PDF p.58", "numeric_value": 7926615151.63, "exact_quote": "资产总计 7,926,615,151.63 6,415,202,506.51", "statement": "CONSOLIDATED_BALANCE_SHEET", "scope_note": "Point-in-time consolidated assets; not a standalone unit-economics or capital-allocation conclusion."},
            },
            "implemented_action": {"status": "OBSERVED_PRE_CUTOFF", "source_locator": "CNINFO:1204595205:PDF p.12"},
            "value_free_outcome_route": {"security_code": "002508", "organization_id": "9900015938"},
        },
        {
            "source_packet_id": "ROUND10-CN002677-PREOUTCOME-CURATOR-V1", "company_id": "CN:002677", "cutoff_at": CUTOFF_AT,
            "curator_id": "ROLE:ROUND10:CN002677:INDEPENDENT_PREOUTCOME_CURATOR", "outcome_content_read": False,
            "fact_locators": ["CNINFO:1204441828:PDF p.63", "CNINFO:1204441828:PDF p.68", "CNINFO:1204441828:PDF p.59", "CNINFO:1204441828:PDF p.12", "CNINFO:1204441828:PDF p.9", "CNINFO:1204441828:PDF p.55"],
            "baseline_fields": {
                "REVENUE": {"source_id": "CNINFO:1204441828", "source_url": "https://static.cninfo.com.cn/finalpage/2018-03-01/1204441828.PDF", "published_at": "2018-03-01", "field_ref": "PDF p.63", "numeric_value": 1026358726.69, "exact_quote": "其中：营业收入 1,026,358,726.69", "statement": "CONSOLIDATED_INCOME_STATEMENT", "scope_note": "Reported consolidated income statement; it is not integrated-stove end-customer demand."},
                "OPERATING_CASH_FLOW": {"source_id": "CNINFO:1204441828", "source_url": "https://static.cninfo.com.cn/finalpage/2018-03-01/1204441828.PDF", "published_at": "2018-03-01", "field_ref": "PDF p.68", "numeric_value": 448060977.53, "exact_quote": "经营活动产生的现金流量净额 448,060,977.53", "statement": "CONSOLIDATED_CASH_FLOW_STATEMENT", "scope_note": "Issuer operating cash only; it cannot be promoted to ordinary-share owner cash."},
                "TOTAL_ASSETS": {"source_id": "CNINFO:1204441828", "source_url": "https://static.cninfo.com.cn/finalpage/2018-03-01/1204441828.PDF", "published_at": "2018-03-01", "field_ref": "PDF p.59", "numeric_value": 1675684054.70, "exact_quote": "资产总计 1,675,684,054.70", "statement": "CONSOLIDATED_BALANCE_SHEET", "scope_note": "Point-in-time consolidated assets; not a standalone unit-economics or capital-allocation conclusion."},
            },
            "implemented_action": {"status": "OBSERVED_PRE_CUTOFF", "source_locator": "CNINFO:1204441828:PDF p.12"},
            "value_free_outcome_route": {"security_code": "002677", "organization_id": "9900022709"},
        },
    ]


def build_real_preoutcome_batch() -> dict[str, Any]:
    return build_batch_freeze([
        build_company_preoutcome_package(company_id=packet["company_id"], source_packet=packet)
        for packet in build_real_source_packets()
    ])


def _dimension_claims(company: dict[str, str], *, source_packet: dict[str, Any]) -> list[dict[str, Any]]:
    action = _mapping(source_packet.get("implemented_action"))
    action_status = action.get("status", "UNKNOWN")
    action_locator = action.get("source_locator") if action_status == "OBSERVED_PRE_CUTOFF" else None
    standard = {"type": "LOCAL_UNKNOWN", "value": "No cutoff-before source uniquely supports this dimension."}
    rows: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        claim: Any = standard
        if dimension == "INITIAL_CONDITIONS_AND_BOUNDARY":
            claim = "Listed-consolidated issuer boundary and product arena are distinct; issuer totals cannot be promoted to product-arena economics."
        elif dimension == "IMPLEMENTED_MANAGEMENT_ACTION" and action_locator:
            claim = "A cutoff-before disclosed action is recorded as implemented; its result remains unproved."
        elif dimension == "STRONGEST_ALTERNATIVE_EXPLANATION":
            claim = "Category conditions, mix, scope and distribution changes may explain issuer financial movement without action credit."
        rows.append({"dimension_id": dimension, "judgment": claim, "evidence_locator_refs": [action_locator] if action_locator and dimension == "IMPLEMENTED_MANAGEMENT_ACTION" else list(source_packet["fact_locators"])})
    return rows


def build_company_preoutcome_package(*, company_id: str, source_packet: dict[str, Any]) -> dict[str, Any]:
    company = _company(company_id)
    if source_packet.get("company_id") != company_id or source_packet.get("cutoff_at") != CUTOFF_AT:
        raise Round10ValidationError("round10_source_packet_company_or_cutoff_mismatch")
    if source_packet.get("outcome_content_read") is not False:
        raise Round10ValidationError("round10_preoutcome_source_packet_cannot_include_outcome_content")
    # Outcome-source identity intentionally is *not* an input here.  The
    # established Minimal V2 contract freezes only its value-free route and
    # later lets the independent custodian select the annual-report version.
    minimal_chains = build_minimal_field_chains(company_id=company_id, source_packet=source_packet)
    evidence_budget = {"evidence_budget_id": f"BUDGET:R10:{company['security_code']}:FY2017", "source_packet_ref": source_packet["source_packet_id"], "locator_refs": list(source_packet["fact_locators"])}
    baseline = {
        "method_id": "R10:FAIR_BASELINE:ISSUER_FINANCIAL_TREND", "resolution_rule_ref": build_method_epoch()["baseline_resolution_rule"]["rule_id"],
        "evidence_budget": deepcopy(evidence_budget), "treatment": "CONTINUE_OPERATING_UNDERWRITING", "claims": [
            {"claim_id": "BASELINE:ISSUER_FINANCIAL_CONTEXT", "judgment": "Issuer revenue and operating cash create a financial context only.", "evidence_locator_refs": list(source_packet["fact_locators"])},
        ],
    }
    enhanced = {
        "method_id": "R10:CUMULATIVE_ENHANCED:EIGHT_DIMENSION", "resolution_rule_ref": build_method_epoch()["enhanced_resolution_rule"]["rule_id"],
        "evidence_budget": deepcopy(evidence_budget), "treatment": "REQUIRE_OWNER_CASH_AND_BOUNDARY_EVIDENCE",
        "claims": _dimension_claims(company, source_packet=source_packet),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": f"R10PKG:{company['security_code']}:20180930:V2", "company": company,
        "cutoff_at": CUTOFF_AT, "method_epoch_ref": METHOD_EPOCH_ID, "source_packet": deepcopy(source_packet),
        "decision_contract": {"contract_id": f"DC:R10:{company['security_code']}:20180930:V2", "company_id": company_id, "cutoff_at": CUTOFF_AT, "purpose": "HISTORICAL_TRAINING", "outcome_access": "NONE"},
        "baseline": baseline, "enhanced": enhanced, "minimal_field_chains": minimal_chains,
        "observation_clocks": {"execution": "FY2019_EVENT_WINDOW", "customer_competition": "FY2019_FLOW_WINDOW", "cash_capital": "FY2019_FLOW_AND_BALANCE_WINDOW"},
        "strongest_alternative_explanation": "Category, mix, scope and channel conditions may reproduce issuer financial movement without establishing action effectiveness.",
        "freeze_state": "PRE_OUTCOME_FROZEN", "frozen_at": FROZEN_AT,
        "outcome_content_read": False, "object_class": "ROUND10_COMPANY_PREOUTCOME_PACKAGE", "claim_class": "SAME_FACT_BUDGET_BASELINE_ENHANCED", "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"], "rights": deepcopy(RIGHTS),
    }


def validate_company_preoutcome_package(package: Any) -> dict[str, Any]:
    item = _mapping(package)
    findings: list[str] = []
    company = _mapping(item.get("company"))
    try:
        expected_company = _company(company.get("company_id", ""))
    except Round10ValidationError:
        findings.append("round10_package_company_not_in_roster")
        expected_company = None
    if item.get("schema_version") != SCHEMA_VERSION or item.get("cutoff_at") != CUTOFF_AT or item.get("method_epoch_ref") != METHOD_EPOCH_ID:
        findings.append("round10_package_identity_invalid")
    if expected_company is not None and company != expected_company:
        findings.append("round10_package_company_identity_must_match_roster")
    if item.get("outcome_content_read") is not False or item.get("freeze_state") != "PRE_OUTCOME_FROZEN" or _instant(item.get("frozen_at")) is None:
        findings.append("round10_package_must_remain_preoutcome_frozen")
    source = _mapping(item.get("source_packet"))
    if source.get("company_id") != company.get("company_id") or source.get("cutoff_at") != CUTOFF_AT or source.get("outcome_content_read") is not False:
        findings.append("round10_package_source_packet_invalid")
    locators = source.get("fact_locators")
    if not isinstance(locators, list) or not locators or any(not _text(value) for value in locators):
        findings.append("round10_package_fact_locators_required")
    baseline, enhanced = _mapping(item.get("baseline")), _mapping(item.get("enhanced"))
    if baseline.get("evidence_budget") != enhanced.get("evidence_budget"):
        findings.append("round10_methods_must_use_same_fact_budget")
    if baseline.get("treatment") == enhanced.get("treatment"):
        findings.append("round10_predeclared_treatment_delta_required")
    enhanced_claims = _items(enhanced.get("claims"))
    if [claim.get("dimension_id") for claim in enhanced_claims if isinstance(claim, dict)] != list(DIMENSIONS):
        findings.append("round10_enhanced_must_cover_eight_dimensions_in_order")
    if any(not _scalar_or_declared_typed_object(_mapping(claim).get("judgment")) for claim in enhanced_claims):
        findings.append("round10_dimension_judgments_must_be_scalar_or_declared_typed")
    try:
        from scripts import minimal_historical_episode as minimal
    except ModuleNotFoundError:  # pragma: no cover
        import minimal_historical_episode as minimal
    chains = _items(item.get("minimal_field_chains"))
    if [chain.get("metric") for chain in chains if isinstance(chain, dict)] != ["REVENUE", "OPERATING_CASH_FLOW", "TOTAL_ASSETS"]:
        findings.append("round10_package_requires_three_ordered_minimal_field_chains")
    for index, raw_chain in enumerate(chains):
        chain = _mapping(raw_chain)
        decision = chain.get("decision_contract")
        route_identity = chain.get("technical_route_identity")
        contract = chain.get("measurement_contract")
        evidence = chain.get("static_evidence")
        prediction = chain.get("prediction")
        decision_result = minimal.validate_decision_contract(decision)
        findings.extend(f"minimal_chains[{index}].decision:" + finding for finding in decision_result["findings"])
        route_result = minimal.validate_technical_route_identity(route_identity, decision_contract=decision)
        findings.extend(f"minimal_chains[{index}].route:" + finding for finding in route_result["findings"])
        contract_result = minimal.validate_measurement_contract(contract, decision_contract=decision, technical_route_identity=route_identity)
        findings.extend(f"minimal_chains[{index}].contract:" + finding for finding in contract_result["findings"])
        evidence_result = minimal.validate_static_evidence(evidence, measurement_contract=contract)
        findings.extend(f"minimal_chains[{index}].evidence:" + finding for finding in evidence_result["findings"])
        prediction_result = minimal.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)
        findings.extend(f"minimal_chains[{index}].prediction:" + finding for finding in prediction_result["findings"])
        if _mapping(contract).get("company_id") != company.get("company_id"):
            findings.append(f"minimal_chains[{index}].company_must_match_package")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != ["OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"]:
        findings.append("round10_package_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings, "package": deepcopy(item) if not findings else None}


def build_batch_freeze(packages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "enterprise-judgment-round10-batch-freeze.v2", "batch_id": "R10:BATCH:CN_APPLIANCE:20180930:V2",
        "method_epoch": build_method_epoch(), "roster_company_ids": [row["company_id"] for row in ROSTER],
        "company_packages": deepcopy(packages), "frozen_at": FROZEN_AT,
        "outcome_content_read": False, "object_class": "ROUND10_IMMUTABLE_BATCH_ROSTER", "claim_class": "PRE_OUTCOME_MULTI_COMPANY_METHOD_REVIEW", "allowed_outputs": ["PREOUTCOME_COMMIT", "OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE"], "rights": deepcopy(RIGHTS),
    }


def validate_batch_freeze(batch: Any) -> dict[str, Any]:
    item = _mapping(batch)
    findings: list[str] = []
    epoch_result = validate_method_epoch(item.get("method_epoch"))
    findings.extend("epoch:" + finding for finding in epoch_result["findings"])
    packages = _items(item.get("company_packages"))
    ids = [(_mapping(package).get("company") or {}).get("company_id") for package in packages]
    expected_ids = [row["company_id"] for row in ROSTER]
    if item.get("schema_version") != "enterprise-judgment-round10-batch-freeze.v2" or item.get("batch_id") != "R10:BATCH:CN_APPLIANCE:20180930:V2":
        findings.append("round10_batch_identity_invalid")
    if item.get("roster_company_ids") != expected_ids or ids != expected_ids:
        findings.append("round10_batch_roster_must_preserve_predeclared_order")
    if len({(_mapping(package).get("company") or {}).get("arena_id") for package in packages}) != len(expected_ids):
        findings.append("round10_batch_company_arenas_must_remain_distinct")
    for index, package in enumerate(packages):
        result = validate_company_preoutcome_package(package)
        findings.extend(f"company_packages[{index}]:" + finding for finding in result["findings"])
    if item.get("outcome_content_read") is not False or _instant(item.get("frozen_at")) is None:
        findings.append("round10_batch_must_remain_preoutcome")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != ["PREOUTCOME_COMMIT", "OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE"]:
        findings.append("round10_batch_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings, "batch": deepcopy(item) if not findings else None}


def build_review_candidate(*, batch: dict[str, Any], settlements: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a review candidate only; an external reviewer owns acceptance."""
    batch_result = validate_batch_freeze(batch)
    if not batch_result["valid"]:
        raise Round10ValidationError("round10_batch_invalid: " + "; ".join(batch_result["findings"]))
    expected_ids = batch["roster_company_ids"]
    by_company = {item.get("company_id"): item for item in settlements if isinstance(item, dict)}
    if set(by_company) != set(expected_ids) or len(settlements) != len(expected_ids):
        raise Round10ValidationError("round10_review_candidate_requires_each_roster_settlement_once")
    comparisons: list[dict[str, Any]] = []
    delta_id = build_method_epoch()["treatment_deltas"][0]["treatment_delta_id"]
    for package in batch["company_packages"]:
        company_id = package["company"]["company_id"]
        settlement = by_company[company_id]
        cells = _items(settlement.get("cell_results"))
        observed = {row.get("cell_id"): row.get("label") for row in cells if isinstance(row, dict)}
        revenue = observed.get(f"CELL:R10:{package['company']['security_code']}:FY2019:REVENUE")
        cash = observed.get(f"CELL:R10:{package['company']['security_code']}:FY2019:OPERATING_CASH_FLOW")
        baseline = "NOT_DIAGNOSTIC" if revenue not in {"OBSERVED_INCREASE", "OBSERVED_DECREASE", "OBSERVED_STABLE"} or cash not in {"OBSERVED_INCREASE", "OBSERVED_DECREASE", "OBSERVED_STABLE"} else "CONTINUE_OPERATING_UNDERWRITING"
        enhanced = "REQUIRE_OWNER_CASH_AND_BOUNDARY_EVIDENCE" if baseline == "CONTINUE_OPERATING_UNDERWRITING" else "NOT_DIAGNOSTIC"
        comparisons.append({
            "company_id": company_id, "settlement_ref": settlement.get("settlement_id"), "baseline_treatment": baseline, "enhanced_treatment": enhanced,
            "treatment_delta_id": delta_id if baseline != enhanced else None,
            "method_advantage_count": 1 if baseline != enhanced else 0,
            "candidate_basis": "Different treatment is an external-review candidate, not a method win; reviewer must establish material investment treatment change or a prevented directional error.",
        })
    return {
        "schema_version": "enterprise-judgment-round10-review-candidate.v2", "review_candidate_id": "R10:REVIEW-CANDIDATE:CN_APPLIANCE:20180930:V2",
        "batch_ref": batch["batch_id"], "settlement_refs": [item["settlement_ref"] for item in comparisons], "comparisons": comparisons,
        "automatic_status": "INDEPENDENT_REVIEW_REQUIRED", "automatic_completion": False,
        "object_class": "ROUND10_METHOD_UTILITY_REVIEW_CANDIDATE", "claim_class": "NO_AUTOMATIC_METHOD_ADVANTAGE", "allowed_outputs": ["EXTERNAL_REVIEW_ONLY", "RESEARCH_AGENDA"], "rights": deepcopy(RIGHTS),
    }


def validate_external_review(review: Any, *, candidate: dict[str, Any]) -> dict[str, Any]:
    item = _mapping(review)
    findings: list[str] = []
    if item.get("review_candidate_ref") != candidate.get("review_candidate_id"):
        findings.append("round10_review_candidate_ref_mismatch")
    if not _text(item.get("reviewer_id")):
        findings.append("round10_independent_reviewer_required")
    if item.get("review_status") not in {"NO_MATERIAL_UTILITY", "MATERIAL_UTILITY_CONFIRMED"}:
        findings.append("round10_review_status_invalid")
    accepted = _items(item.get("accepted_treatment_delta_ids"))
    candidate_deltas = {row.get("treatment_delta_id") for row in _items(candidate.get("comparisons")) if row.get("treatment_delta_id")}
    if item.get("review_status") == "NO_MATERIAL_UTILITY" and accepted:
        findings.append("round10_no_material_utility_cannot_accept_delta")
    if item.get("review_status") == "MATERIAL_UTILITY_CONFIRMED":
        if len(accepted) != 1 or accepted[0] not in candidate_deltas:
            findings.append("round10_material_utility_requires_one_candidate_delta")
        if item.get("utility_basis") not in {"MATERIAL_TREATMENT_CHANGE", "PREVENTED_DIRECTIONAL_ERROR"}:
            findings.append("round10_material_utility_requires_permitted_basis")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != ["RESEARCH_AGENDA"]:
        findings.append("round10_review_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings, "review": deepcopy(item) if not findings else None}
