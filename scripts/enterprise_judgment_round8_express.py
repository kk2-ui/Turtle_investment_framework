#!/usr/bin/env python3
"""Round 8 real cross-industry training for Chinese franchised express delivery."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode_module
    from scripts import enterprise_judgment_multidimensional_training as multidimensional
    from scripts import enterprise_judgment_reconstruction as reconstruction
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import judgment_decision_utility as decision_utility
    from scripts import outcome_measurement_acquisition as measurement_acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_episode as episode_module
    import enterprise_judgment_multidimensional_training as multidimensional
    import enterprise_judgment_reconstruction as reconstruction
    import enterprise_judgment_training_control_plane as enterprise_control
    import judgment_decision_utility as decision_utility
    import outcome_measurement_acquisition as measurement_acquisition
    import outcome_measurement_settlement_adapter as settlement_adapter


PACKAGE_ID = "R8:CN:FRANCHISE_EXPRESS:CN002120:20190501:V1"
FROZEN_AT = "2019-05-01T12:00:00+08:00"
BASELINE_METHOD_ID = "METHOD:ISSUER_SCALE_TREND_BASELINE:V1"
ENHANCED_METHOD_ID = "METHOD:CUMULATIVE_ENTERPRISE_JUDGMENT_CHAIN:V2"
MEASUREMENT_CONTRACT_ID = "OMC:CN002120:20190501:MULTIDIMENSIONAL:V3"
OUTCOME_SOURCE_ID = "CNINFO:002120:ANN:20200430:1207682788"
OUTCOME_SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2020-04-30/1207682788.PDF"
OUTCOME_AUTHORIZATION_ID = "OUTCOME-AUTH:R8:CN002120:FY2019:V1"
OUTCOME_SETTLEMENT_ID = "R8SETTLE:CN002120:20190501:FY2019:V1"
UTILITY_EVALUATION_ID = "UTILITY:EVAL:CN002120:20190501:ROUND8:V3"
INDEPENDENT_REVIEWER_ID = "ROLE:ROUND8:INDEPENDENT_UTILITY_REVIEWER"
METHOD_CONCLUSION = "REAL_FEEDBACK_COMPLETED_NO_MATERIAL_METHOD_ADVANTAGE_PROVED"
RIGHTS = deepcopy(multidimensional.PREOUTCOME_RIGHTS)
MEASUREMENT_RIGHTS = {
    key: value for key, value in RIGHTS.items() if key != "method_transfer"
}
DIMENSIONS = list(decision_utility.DIMENSIONS)

LOCATORS_BY_DIMENSION = {
    "INITIAL_CONDITIONS": [
        "LOC:002120:FY2018:BUSINESS_MODEL",
        "LOC:002120:FY2018:INDUSTRY_VOLUME_CONCENTRATION",
    ],
    "IMPLEMENTED_MANAGEMENT_ACTION": ["LOC:002120:FY2018:IMPLEMENTED_ACTIONS"],
    "EXECUTION": [
        "LOC:002120:FY2018:IMPLEMENTED_ACTIONS",
        "LOC:002120:FY2018:NETWORK_SCALE",
    ],
    "CUSTOMER_COMPETITION_RESPONSE": ["LOC:002120:FY2018:CUSTOMER_RESPONSE"],
    "UNIT_ECONOMICS": ["LOC:002120:FY2018:UNIT_ECONOMICS"],
    "WORKING_CAPITAL_CASH_CAPITAL": ["LOC:002120:FY2018:CASH_CAPITAL"],
    "ADAPTATION_PERMANENT_LOSS": [
        "LOC:002120:FY2018:NETWORK_SCALE",
        "LOC:002120:FY2018:FRANCHISE_GOVERNANCE",
    ],
    "STRONGEST_ALTERNATIVE_EXPLANATION": [
        "LOC:002120:FY2018:INDUSTRY_VOLUME_CONCENTRATION",
    ],
}

CELL = {
    "INDUSTRY_PARCEL_GROWTH": "CELL:002120:FY2019:INDUSTRY_PARCEL_GROWTH",
    "ISSUER_PARCEL_GROWTH": "CELL:002120:FY2019:ISSUER_PARCEL_GROWTH",
    "ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD": "CELL:002120:FY2019:ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD",
    "MARKET_SHARE_CHANGE": "CELL:002120:FY2019:MARKET_SHARE_CHANGE",
    "COMPLAINT_RATE_CHANGE": "CELL:002120:FY2019:COMPLAINT_RATE_CHANGE",
    "NETWORK_SCALE_EVENT": "CELL:002120:FY2019:NETWORK_SCALE_EVENT",
    "AUTOMATION_SERVICE_EVENT": "CELL:002120:FY2019:AUTOMATION_SERVICE_EVENT",
    "EXPRESS_REVENUE_PER_PARCEL": "CELL:002120:FY2019:EXPRESS_REVENUE_PER_PARCEL",
    "PARCEL_COST": "CELL:002120:FY2019:PARCEL_COST",
    "EXPRESS_GROSS_MARGIN": "CELL:002120:FY2019:EXPRESS_GROSS_MARGIN",
    "OPERATING_CASH_FLOW": "CELL:002120:FY2019:OPERATING_CASH_FLOW",
    "CASH_CAPEX": "CELL:002120:FY2019:CASH_CAPEX",
    "OCF_TO_CASH_CAPEX": "CELL:002120:FY2019:OCF_TO_CASH_CAPEX",
    "ASSET_LIABILITY_RATIO": "CELL:002120:FY2019:ASSET_LIABILITY_RATIO",
    "FRANCHISE_NETWORK_ADVERSE_EVENT": "CELL:002120:FY2019:FRANCHISE_NETWORK_ADVERSE_EVENT",
}

CELL_DIMENSIONS = {
    CELL["INDUSTRY_PARCEL_GROWTH"]: "CUSTOMER",
    CELL["ISSUER_PARCEL_GROWTH"]: "OPERATIONS",
    CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"]: "COMPETITION",
    CELL["MARKET_SHARE_CHANGE"]: "COMPETITION",
    CELL["COMPLAINT_RATE_CHANGE"]: "CUSTOMER",
    CELL["NETWORK_SCALE_EVENT"]: "OPERATIONS",
    CELL["AUTOMATION_SERVICE_EVENT"]: "OPERATIONS",
    CELL["EXPRESS_REVENUE_PER_PARCEL"]: "CUSTOMER",
    CELL["PARCEL_COST"]: "OPERATIONS",
    CELL["EXPRESS_GROSS_MARGIN"]: "OPERATIONS",
    CELL["OPERATING_CASH_FLOW"]: "CASH",
    CELL["CASH_CAPEX"]: "CAPITAL_RETURN",
    CELL["OCF_TO_CASH_CAPEX"]: "CAPITAL_RETURN",
    CELL["ASSET_LIABILITY_RATIO"]: "LEVERAGE",
    CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"]: "PERMANENT_LOSS",
}

DEPENDENCIES = {
    "INITIAL_CONDITIONS": [CELL["INDUSTRY_PARCEL_GROWTH"], CELL["ISSUER_PARCEL_GROWTH"]],
    "IMPLEMENTED_MANAGEMENT_ACTION": [CELL["AUTOMATION_SERVICE_EVENT"]],
    "EXECUTION": [CELL["NETWORK_SCALE_EVENT"], CELL["AUTOMATION_SERVICE_EVENT"], CELL["PARCEL_COST"]],
    "CUSTOMER_COMPETITION_RESPONSE": [
        CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
        CELL["MARKET_SHARE_CHANGE"],
        CELL["COMPLAINT_RATE_CHANGE"],
    ],
    "UNIT_ECONOMICS": [
        CELL["EXPRESS_REVENUE_PER_PARCEL"],
        CELL["PARCEL_COST"],
        CELL["EXPRESS_GROSS_MARGIN"],
    ],
    "WORKING_CAPITAL_CASH_CAPITAL": [
        CELL["OPERATING_CASH_FLOW"],
        CELL["CASH_CAPEX"],
        CELL["OCF_TO_CASH_CAPEX"],
    ],
    "ADAPTATION_PERMANENT_LOSS": [
        CELL["NETWORK_SCALE_EVENT"],
        CELL["ASSET_LIABILITY_RATIO"],
        CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"],
    ],
    "STRONGEST_ALTERNATIVE_EXPLANATION": [
        CELL["INDUSTRY_PARCEL_GROWTH"],
        CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
        CELL["EXPRESS_REVENUE_PER_PARCEL"],
    ],
}

DOMAINS = {
    "INITIAL_CONDITIONS": "LIFECYCLE",
    "IMPLEMENTED_MANAGEMENT_ACTION": "ORGANIZATION",
    "EXECUTION": "OPERATIONS",
    "CUSTOMER_COMPETITION_RESPONSE": "CUSTOMER",
    "UNIT_ECONOMICS": "COMPETITION",
    "WORKING_CAPITAL_CASH_CAPITAL": "CASH",
    "ADAPTATION_PERMANENT_LOSS": "PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION": "COMPETITION",
}

QUESTIONS = [
    {
        "question_id": "Q:R8:CONDITIONS_AND_RIVAL",
        "role": "SUPPORTING",
        "question": "Which industry conditions and alternative explanation can reproduce the visible scale trend?",
        "dimensions": ["INITIAL_CONDITIONS", "STRONGEST_ALTERNATIVE_EXPLANATION"],
    },
    {
        "question_id": "Q:R8:ACTION_AND_EXECUTION",
        "role": "SUPPORTING",
        "question": "Which management actions were implemented and what would count as execution rather than deployment?",
        "dimensions": ["IMPLEMENTED_MANAGEMENT_ACTION", "EXECUTION"],
    },
    {
        "question_id": "Q:R8:CUSTOMER_AND_UNIT_ECONOMICS",
        "role": "PRIMARY",
        "question": "Did the network convert growth into customer response and sustainable unit economics rather than price-led volume?",
        "dimensions": ["CUSTOMER_COMPETITION_RESPONSE", "UNIT_ECONOMICS"],
    },
    {
        "question_id": "Q:R8:CASH_AND_PERMANENT_LOSS",
        "role": "SUPPORTING",
        "question": "Could headquarters fund network requirements while preserving franchise resilience and ordinary-share loss protection?",
        "dimensions": ["WORKING_CAPITAL_CASH_CAPITAL", "ADAPTATION_PERMANENT_LOSS"],
    },
]

BASELINE_STATEMENTS = {
    "INITIAL_CONDITIONS": "A rapidly growing, concentrating national parcel market and a large self-operated hub network supported an issuer-scale growth reading.",
    "IMPLEMENTED_MANAGEMENT_ACTION": "Management disclosed implemented automation, route optimization, transport conversion and franchisee-enablement work during FY2018.",
    "EXECUTION": "Higher parcel volume, market share and network scale were treated as provisional signs that the disclosed operating program was executing.",
    "CUSTOMER_COMPETITION_RESPONSE": "Parcel growth, share and complaint-rate direction suggested customer and competitive progress, but did not isolate price or platform demand.",
    "UNIT_ECONOMICS": "Reported express revenue, gross margin and parcel cost provided a consolidated trend view of network economics.",
    "WORKING_CAPITAL_CASH_CAPITAL": "Consolidated operating cash and long-lived-asset spending showed funding capacity, but did not identify owner cash or franchisee cash economics.",
    "ADAPTATION_PERMANENT_LOSS": "Network scale and franchise support reduced some continuity concerns, while franchisee health and irreversible loss remained unknown.",
    "STRONGEST_ALTERNATIVE_EXPLANATION": "National parcel demand and industry concentration could explain much of the visible issuer growth without company-specific advantage.",
}

ENHANCED_STATEMENTS = {
    "INITIAL_CONDITIONS": "The issuer sat between national platform-driven demand, self-operated hub capital and a franchised service edge whose economics could diverge from headquarters.",
    "IMPLEMENTED_MANAGEMENT_ACTION": "Automation, route changes, transport conversion and franchise support were observed actions, not evidence that customers or economics improved because of them.",
    "EXECUTION": "Execution required post-cutoff service, utilization and parcel-cost evidence at the network boundary; capacity and outlet counts alone were deployment facts.",
    "CUSTOMER_COMPETITION_RESPONSE": "Customer response required share and complaint evidence to survive a rival explanation based on price concessions and common platform traffic.",
    "UNIT_ECONOMICS": "Revenue per parcel, parcel cost and gross margin had to move coherently; headquarters economics could not stand in for franchisee economics.",
    "WORKING_CAPITAL_CASH_CAPITAL": "Operating cash, cash capex and funding capacity were separate from distributable owner cash and from the capital borne by franchisees.",
    "ADAPTATION_PERMANENT_LOSS": "Resilience depended on adapting hub and service systems without destabilizing franchisees, increasing leverage or creating irreversible network loss.",
    "STRONGEST_ALTERNATIVE_EXPLANATION": "Industry demand and price-led volume could reproduce scale and share gains while customer quality, unit economics and capital returns weakened.",
}


def _flow_clock(year: int) -> dict[str, Any]:
    return {
        "clock_kind": "FLOW_PERIOD",
        "flow_period": {
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "fiscal_period": f"FY{year}",
        },
    }


def _balance_clock(year: int) -> dict[str, Any]:
    return {
        "clock_kind": "BALANCE_AS_OF",
        "balance_as_of": {"as_of": f"{year}-12-31", "fiscal_period": f"FY{year}"},
    }


def _event_clock() -> dict[str, Any]:
    return {
        "clock_kind": "EVENT_WINDOW",
        "event_window": {
            "event_start": "2019-05-02",
            "event_end": "2019-12-31",
            "window_name": "STRICT_POST_CUTOFF_EVENT_WINDOW",
        },
    }


def _outcome_period() -> dict[str, str]:
    return {
        "period_start": "2019-05-02T00:00:00+08:00",
        "period_end": "2019-12-31T23:59:59+08:00",
        "fiscal_period": "FY2019_MIXED_CLOCK_CONTEXT",
    }


def _boundary(scope: str) -> dict[str, str]:
    return {
        "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:002120",
        "perimeter_id": "PERIMETER:CN:002120:FY2019:LISTED_CONSOLIDATED",
        "arena_id": "ARENA:CN:EXPRESS:HUB_FRANCHISE_SERVICE_SYSTEM",
        "scope_requirement": scope,
    }


def _raw(
    field_id: str, role: str, unit: str, clock: dict[str, Any], table: str, line: str,
) -> dict[str, Any]:
    clock_value = clock.get("event_window") or clock.get("flow_period") or clock.get("balance_as_of") or {}
    period_column = (
        f"{clock_value.get('event_start')}..{clock_value.get('event_end')}"
        if clock.get("clock_kind") == "EVENT_WINDOW"
        else str(clock_value.get("fiscal_period"))
    )
    return {
        "field_id": field_id,
        "role": role,
        "unit": unit,
        "measurement_clock": deepcopy(clock),
        "locator": {
            "table_or_note": table,
            "line_item": line,
            "period_column": period_column,
        },
    }


def _conversion(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "field_id": raw["field_id"],
        "from_unit": raw["unit"],
        "to_unit": raw["unit"],
        "scale": "1",
    }


def _numeric_cell(
    *, name: str, thread_id: str, layer: str, table: str, line: str,
    raw_specs: list[tuple[str, str, str, dict[str, Any]]], operator: str,
    unit_kind: str, decrease_lte: float, increase_gte: float,
    scope: str, prohibited: str,
) -> dict[str, Any]:
    raw_fields = [
        _raw(field_id, role, unit, clock, table, line)
        for field_id, role, unit, clock in raw_specs
    ]
    outcome_fields = [raw for raw in raw_fields if raw["role"] in {"OUTCOME", "NUMERATOR"}]
    outcome_field = outcome_fields[-1] if outcome_fields else raw_fields[-1]
    baseline_fields = [raw for raw in raw_fields if raw["role"] == "BASELINE"]
    if operator == "RAW_VALUE":
        expression = raw_fields[0]["field_id"]
    elif operator == "PERCENT_CHANGE":
        expression = "(outcome - baseline) / abs(baseline)"
    elif operator == "RATIO_CHANGE":
        expression = "((outcome_numerator/outcome_denominator)-(baseline_numerator/baseline_denominator))/abs(baseline_ratio)"
    elif operator == "DIFFERENCE":
        expression = "outcome - baseline"
    else:  # pragma: no cover - builder owns the closed operator list
        raise ValueError(operator)
    return {
        "cell_id": CELL[name],
        "thread_id": thread_id,
        "layer": layer,
        "outcome_period": _outcome_period(),
        "measurement_clock": deepcopy(outcome_field["measurement_clock"]),
        "responsibility_boundary": _boundary(scope),
        "field_identity": {
            "outcome_field_id": outcome_field["field_id"],
            "baseline_field_id": baseline_fields[0]["field_id"] if baseline_fields else "",
            "statement_scope": "CONSOLIDATED_MIXED_CLOCK_CONTEXT",
            "table_or_note": table,
            "line_item": line,
            "field_kind": "AUDITED_OR_OPERATING_LINE_ITEM",
        },
        "unit": {"kind": unit_kind, "currency": "RMB" if "RMB" in {raw["unit"] for raw in raw_fields} else "NOT_APPLICABLE", "scale": "1"},
        "raw_input_fields": raw_fields,
        "formula": {
            "operator": operator,
            "input_field_ids": [raw["field_id"] for raw in raw_fields],
            "expression": expression,
            "unit_conversions": [_conversion(raw) for raw in raw_fields],
            "zero_baseline_rule": "NOT_APPLICABLE" if operator in {"RAW_VALUE", "DIFFERENCE"} else "RETURN_MEASUREMENT_MISMATCH",
        },
        "label_rule": {
            "type": "ABSOLUTE_CHANGE_BAND" if operator in {"RAW_VALUE", "DIFFERENCE"} else "PERCENT_CHANGE_BAND",
            "decrease_lte": decrease_lte,
            "increase_gte": increase_gte,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH",
                "OBSERVED_DECREASE",
                "OBSERVED_STABLE",
                "OBSERVED_INCREASE",
                "UNKNOWN",
            ],
        },
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {"conditions": ["one or more contracted raw fields absent"], "label": "UNKNOWN"},
        "mismatch_rule": {
            "conditions": ["scope, period, unit or unique-field conflict"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def _event_cell(*, name: str, thread_id: str, layer: str, line: str, scope: str, prohibited: str) -> dict[str, Any]:
    clock = _event_clock()
    raw = _raw(f"FIELD:002120:FY2019:{name}", "EVENT", "BOOLEAN_EVENT", clock, "FY2019 operating and risk review", line)
    return {
        "cell_id": CELL[name],
        "thread_id": thread_id,
        "layer": layer,
        "outcome_period": _outcome_period(),
        "measurement_clock": clock,
        "responsibility_boundary": _boundary(scope),
        "field_identity": {
            "outcome_field_id": raw["field_id"],
            "baseline_field_id": "",
            "statement_scope": "STRICT_POST_CUTOFF_ISSUER_EVENT",
            "table_or_note": raw["locator"]["table_or_note"],
            "line_item": line,
            "field_kind": "DISCLOSED_EVENT",
        },
        "unit": {"kind": "EVENT", "currency": "NOT_APPLICABLE", "scale": "BOOLEAN"},
        "raw_input_fields": [raw],
        "formula": {
            "operator": "EVENT_BOOLEAN",
            "input_field_ids": [raw["field_id"]],
            "expression": f"explicit_post_cutoff_event({raw['field_id']})",
            "unit_conversions": [_conversion(raw)],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        "label_rule": {
            "type": "EVENT_PRESENCE",
            "decrease_lte": 0,
            "increase_gte": 1,
            "ordered_labels": ["MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN"],
        },
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {"conditions": ["no explicit positive or negative post-cutoff event evidence"], "label": "UNKNOWN"},
        "mismatch_rule": {
            "conditions": ["event date, scope or implementation identity conflict"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def build_measurement_contract() -> dict[str, Any]:
    fy18, fy19 = _flow_clock(2018), _flow_clock(2019)
    b18, b19 = _balance_clock(2018), _balance_clock(2019)
    cells = [
        _numeric_cell(
            name="INDUSTRY_PARCEL_GROWTH", thread_id="THREAD:R8:INDUSTRY_RIVAL", layer="SALES_VOLUME",
            table="FY2019 industry review", line="national parcel volume growth rate",
            raw_specs=[("FIELD:002120:FY2019:INDUSTRY_PARCEL_GROWTH", "OUTCOME", "RATIO", fy19)],
            operator="RAW_VALUE", unit_kind="RATIO", decrease_lte=-0.000001, increase_gte=0.000001,
            scope="National industry context; FY2019 is MIXED_CLOCK_CONTEXT and receives no issuer causal credit.",
            prohibited="Industry growth is not customer preference for Yunda or evidence of issuer execution.",
        ),
        _numeric_cell(
            name="ISSUER_PARCEL_GROWTH", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="SALES_VOLUME",
            table="FY2019 operating review", line="issuer parcel volume growth rate",
            raw_specs=[("FIELD:002120:FY2019:ISSUER_PARCEL_GROWTH", "OUTCOME", "RATIO", fy19)],
            operator="RAW_VALUE", unit_kind="RATIO", decrease_lte=-0.000001, increase_gte=0.000001,
            scope="Issuer parcel flow for FY2019; the annual flow includes January-April before cutoff.",
            prohibited="Parcel growth is not customer absorption, loyalty, execution quality or value creation.",
        ),
        _numeric_cell(
            name="ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD", thread_id="THREAD:R8:INDUSTRY_RIVAL", layer="SALES_VOLUME",
            table="FY2019 industry and operating review", line="issuer parcel growth rate minus national parcel growth rate",
            raw_specs=[
                ("FIELD:002120:FY2019:SPREAD_INDUSTRY_GROWTH", "BASELINE", "RATIO", fy19),
                ("FIELD:002120:FY2019:SPREAD_ISSUER_GROWTH", "OUTCOME", "RATIO", fy19),
            ], operator="DIFFERENCE", unit_kind="ABSOLUTE_CHANGE", decrease_lte=-0.02, increase_gte=0.02,
            scope="Issuer-versus-industry descriptive spread with no untreated-control interpretation.",
            prohibited="A positive spread is not causal market-share capture or proof of service differentiation.",
        ),
        _numeric_cell(
            name="MARKET_SHARE_CHANGE", thread_id="THREAD:R8:CUSTOMER_FRANCHISE", layer="CUSTOMER_RESPONSE",
            table="FY2019 operating review", line="issuer national parcel market share",
            raw_specs=[
                ("FIELD:002120:FY2018:MARKET_SHARE", "BASELINE", "RATIO", fy18),
                ("FIELD:002120:FY2019:MARKET_SHARE", "OUTCOME", "RATIO", fy19),
            ], operator="DIFFERENCE", unit_kind="ABSOLUTE_CHANGE", decrease_lte=-0.005, increase_gte=0.005,
            scope="Issuer national parcel share; price, platform and product mix remain rival mechanisms.",
            prohibited="Share gains do not prove loyalty, pricing power or attractive shipper economics.",
        ),
        _numeric_cell(
            name="COMPLAINT_RATE_CHANGE", thread_id="THREAD:R8:CUSTOMER_FRANCHISE", layer="CUSTOMER_RESPONSE",
            table="FY2019 service-quality review", line="effective complaint rate",
            raw_specs=[
                ("FIELD:002120:FY2018:EFFECTIVE_COMPLAINT_RATE", "BASELINE", "RATIO", fy18),
                ("FIELD:002120:FY2019:EFFECTIVE_COMPLAINT_RATE", "OUTCOME", "RATIO", fy19),
            ], operator="DIFFERENCE", unit_kind="ABSOLUTE_CHANGE", decrease_lte=-0.0001, increase_gte=0.0001,
            scope="Issuer disclosed complaint metric with unchanged definition required across periods.",
            prohibited="Complaint-rate movement alone does not prove overall customer retention or causal service effect.",
        ),
        _event_cell(
            name="NETWORK_SCALE_EVENT", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="EXECUTED",
            line="explicit hub, route or trunk-capacity implementation dated from 2019-05-02 through 2019-12-31",
            scope="Issuer-controlled network implementation after cutoff; year-end scale without implementation timing is insufficient.",
            prohibited="Additional capacity does not prove utilization, service quality or economic return.",
        ),
        _event_cell(
            name="AUTOMATION_SERVICE_EVENT", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="IMPLEMENTED",
            line="explicit automation or service-system implementation dated from 2019-05-02 through 2019-12-31",
            scope="Issuer-controlled implementation event after cutoff.",
            prohibited="Deployment does not prove execution success, customer adoption or cost improvement.",
        ),
        _numeric_cell(
            name="EXPRESS_REVENUE_PER_PARCEL", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="PRICE",
            table="FY2019 express revenue and parcel volume", line="express-service revenue divided by completed parcels",
            raw_specs=[
                ("FIELD:002120:FY2018:EXPRESS_REVENUE_RPP_NUMERATOR", "BASELINE", "RMB", fy18),
                ("FIELD:002120:FY2018:PARCEL_VOLUME_RPP_DENOMINATOR", "DENOMINATOR", "PARCEL", fy18),
                ("FIELD:002120:FY2019:EXPRESS_REVENUE_RPP_NUMERATOR", "OUTCOME", "RMB", fy19),
                ("FIELD:002120:FY2019:PARCEL_VOLUME_RPP_DENOMINATOR", "DENOMINATOR", "PARCEL", fy19),
            ], operator="RATIO_CHANGE", unit_kind="RATIO_CHANGE", decrease_lte=-0.03, increase_gte=0.03,
            scope="Issuer express revenue per completed parcel; mix and headquarters settlement remain embedded.",
            prohibited="Revenue per parcel is a price-mix proxy, not customer willingness to pay or franchisee revenue.",
        ),
        _numeric_cell(
            name="PARCEL_COST", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="UNIT_COST",
            table="FY2019 express operating review", line="cost per completed parcel",
            raw_specs=[
                ("FIELD:002120:FY2018:PARCEL_COST", "BASELINE", "RMB_PER_PARCEL", fy18),
                ("FIELD:002120:FY2019:PARCEL_COST", "OUTCOME", "RMB_PER_PARCEL", fy19),
            ], operator="PERCENT_CHANGE", unit_kind="PERCENT_CHANGE", decrease_lte=-0.03, increase_gte=0.03,
            scope="Issuer disclosed parcel-cost boundary; definition and network perimeter must remain unchanged.",
            prohibited="Parcel-cost movement does not isolate automation, fuel, labor, mix or franchisee economics.",
        ),
        _numeric_cell(
            name="EXPRESS_GROSS_MARGIN", thread_id="THREAD:R8:NETWORK_PRODUCTIVITY", layer="GROSS_MARGIN",
            table="FY2019 principal business by service", line="express-service gross margin",
            raw_specs=[
                ("FIELD:002120:FY2018:EXPRESS_GROSS_MARGIN", "BASELINE", "RATIO", fy18),
                ("FIELD:002120:FY2019:EXPRESS_GROSS_MARGIN", "OUTCOME", "RATIO", fy19),
            ], operator="DIFFERENCE", unit_kind="ABSOLUTE_CHANGE", decrease_lte=-0.01, increase_gte=0.01,
            scope="Issuer express-service gross margin with same accounting and service perimeter required.",
            prohibited="Headquarters gross margin is not franchisee economics or management causal effect.",
        ),
        _numeric_cell(
            name="OPERATING_CASH_FLOW", thread_id="THREAD:R8:CASH_CAPITAL", layer="CASH",
            table="consolidated cash-flow statement", line="net cash flows from operating activities",
            raw_specs=[
                ("FIELD:002120:FY2018:OPERATING_CASH_FLOW", "BASELINE", "RMB", fy18),
                ("FIELD:002120:FY2019:OPERATING_CASH_FLOW", "OUTCOME", "RMB", fy19),
            ], operator="PERCENT_CHANGE", unit_kind="PERCENT_CHANGE", decrease_lte=-0.10, increase_gte=0.10,
            scope="Listed-consolidated operating cash; working-capital timing and franchise cash remain separate.",
            prohibited="Operating cash is not distributable owner cash.",
        ),
        _numeric_cell(
            name="CASH_CAPEX", thread_id="THREAD:R8:CASH_CAPITAL", layer="CAPITAL_BURDEN",
            table="consolidated cash-flow statement", line="cash paid to acquire and construct fixed assets, intangible assets and other long-term assets",
            raw_specs=[
                ("FIELD:002120:FY2018:CASH_CAPEX", "BASELINE", "RMB", fy18),
                ("FIELD:002120:FY2019:CASH_CAPEX", "OUTCOME", "RMB", fy19),
            ], operator="PERCENT_CHANGE", unit_kind="PERCENT_CHANGE", decrease_lte=-0.10, increase_gte=0.10,
            scope="Listed-consolidated cash capex with maintenance, growth and property ownership unseparated.",
            prohibited="Cash capex is neither automatic value creation nor automatic destruction.",
        ),
        _numeric_cell(
            name="OCF_TO_CASH_CAPEX", thread_id="THREAD:R8:CASH_CAPITAL", layer="CAPITAL_BURDEN",
            table="consolidated cash-flow statement", line="operating cash flow divided by cash capex",
            raw_specs=[
                ("FIELD:002120:FY2018:OCF_RATIO_NUMERATOR", "BASELINE", "RMB", fy18),
                ("FIELD:002120:FY2018:CAPEX_RATIO_DENOMINATOR", "DENOMINATOR", "RMB", fy18),
                ("FIELD:002120:FY2019:OCF_RATIO_NUMERATOR", "OUTCOME", "RMB", fy19),
                ("FIELD:002120:FY2019:CAPEX_RATIO_DENOMINATOR", "DENOMINATOR", "RMB", fy19),
            ], operator="RATIO_CHANGE", unit_kind="RATIO_CHANGE", decrease_lte=-0.10, increase_gte=0.10,
            scope="Issuer funding-capacity diagnostic; acquisition cash and franchise capital are outside the ratio.",
            prohibited="OCF-to-capex is not owner cash or an investment return.",
        ),
        _numeric_cell(
            name="ASSET_LIABILITY_RATIO", thread_id="THREAD:R8:CASH_CAPITAL", layer="FINANCING",
            table="FY2019 solvency review", line="asset-liability ratio",
            raw_specs=[
                ("FIELD:002120:FY2018:ASSET_LIABILITY_RATIO", "BASELINE", "RATIO", b18),
                ("FIELD:002120:FY2019:ASSET_LIABILITY_RATIO", "OUTCOME", "RATIO", b19),
            ], operator="DIFFERENCE", unit_kind="ABSOLUTE_CHANGE", decrease_lte=-0.03, increase_gte=0.03,
            scope="Listed-consolidated balance-sheet ratio; refinancing terms and franchise liabilities are separate.",
            prohibited="A one-year ratio change does not prove or disprove permanent-loss risk.",
        ),
        _event_cell(
            name="FRANCHISE_NETWORK_ADVERSE_EVENT", thread_id="THREAD:R8:CUSTOMER_FRANCHISE", layer="PERMANENT_LOSS",
            line="explicit franchise-network closure, default, material service disruption or irreversible capital-loss event dated from 2019-05-02 through 2019-12-31",
            scope="Issuer or disclosed franchise-network adverse event after cutoff; absence requires explicit negative evidence.",
            prohibited="No disclosed event does not prove franchisee health or eliminate permanent-loss risk.",
        ),
    ]
    return {
        "schema_version": "enterprise-outcome-measurement-contract.v3",
        "contract_set_id": MEASUREMENT_CONTRACT_ID,
        "package_ref": PACKAGE_ID,
        "company_id": "CN:002120",
        "cutoff_at": "2019-05-01T00:00:00+08:00",
        "outcome_window": {
            **_outcome_period(),
            "settlement_due_at": "2020-04-30T23:59:59+08:00",
        },
        "source_access": {
            "source_id": OUTCOME_SOURCE_ID,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": OUTCOME_SOURCE_URL,
            "published_after_cutoff": True,
            "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
            "custodian_access": "OUTCOME_ONLY",
            "issuer_id": "ISSUER:CN:002120",
            "report_period_end": "2019-12-31",
            "availability_precision": "DATE_ONLY",
            "source_available_at": None,
            "source_available_date": "2020-04-30",
            "authorization_receipt_id": OUTCOME_AUTHORIZATION_ID,
        },
        "atomic_cells": cells,
        "thread_combination_rules": [
            {
                "rule_id": "RULE:R8:NETWORK_PRODUCTIVITY",
                "thread_id": "THREAD:R8:NETWORK_PRODUCTIVITY",
                "input_cell_ids": [
                    CELL["NETWORK_SCALE_EVENT"], CELL["AUTOMATION_SERVICE_EVENT"],
                    CELL["EXPRESS_REVENUE_PER_PARCEL"], CELL["PARCEL_COST"],
                    CELL["EXPRESS_GROSS_MARGIN"],
                ],
                "evaluation_order": [
                    CELL["NETWORK_SCALE_EVENT"], CELL["AUTOMATION_SERVICE_EVENT"],
                    CELL["EXPRESS_REVENUE_PER_PARCEL"], CELL["PARCEL_COST"],
                    CELL["EXPRESS_GROSS_MARGIN"],
                ],
                "rule": "Review implementation, unit cost and margin separately; no cell can compensate for another.",
                "conflict_rule": "Preserve MIXED or NOT_DIAGNOSTIC rather than assigning causal credit.",
                "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
            },
            {
                "rule_id": "RULE:R8:CUSTOMER_FRANCHISE",
                "thread_id": "THREAD:R8:CUSTOMER_FRANCHISE",
                "input_cell_ids": [
                    CELL["MARKET_SHARE_CHANGE"], CELL["COMPLAINT_RATE_CHANGE"],
                    CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"],
                ],
                "evaluation_order": [
                    CELL["MARKET_SHARE_CHANGE"], CELL["COMPLAINT_RATE_CHANGE"],
                    CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"],
                ],
                "rule": "Customer and franchise evidence remain distinct from volume and headquarters economics.",
                "conflict_rule": "A missing customer or franchise field limits only the dependent claim.",
                "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
            },
        ],
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "contract_frozen_at": FROZEN_AT,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
        "rights": deepcopy(MEASUREMENT_RIGHTS),
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }


def build_decision_contract(block: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "turtle-training-decision-contract.v1",
        "contract_id": "DC:CN002120:20190501:ROUND8:V1",
        "contract_version": 1,
        "company_id": selection["company_id"],
        "issuer_id": selection["issuer_id"],
        "cutoff_at": selection["cutoff_at"],
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [
            {
                "constraint_id": "PLC:R8:FRANCHISE_NETWORK",
                "condition": "Headquarters growth depends on franchise economics or service continuity that is not directly observable.",
                "required_treatment": "Keep franchise resilience and permanent loss UNKNOWN unless direct same-boundary evidence settles them.",
            },
            {
                "constraint_id": "PLC:R8:CASH_CAPITAL",
                "condition": "Operating cash or margin is promoted to owner cash without separating network capital and franchisee capital.",
                "required_treatment": "Preserve listed-company cash, required capital and ordinary-share cash access as separate judgments.",
            },
        ],
        "decision_flip_questions": [
            {
                "question_id": "DQ:R8:CUSTOMER_OR_PRICE",
                "statement": "Did customer and service evidence improve after accounting for industry demand and price-led volume?",
                "decision_effect": "Failure keeps customer advantage unproven even if parcel volume or share rises.",
            },
            {
                "question_id": "DQ:R8:NETWORK_ECONOMICS",
                "statement": "Did network implementation improve coherent unit economics and cash funding capacity?",
                "decision_effect": "Failure weakens execution quality without turning every enterprise dimension negative.",
            },
            {
                "question_id": "DQ:R8:FRANCHISE_RESILIENCE",
                "statement": "Did headquarters growth preserve franchise continuity and avoid a material adverse network event?",
                "decision_effect": "Missing evidence remains a permanent-loss unknown rather than a positive assumption.",
            },
        ],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:CN002120:20190501:FY2018",
            "source_packet_refs": [deepcopy(selection["source_packet_ref"])],
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": deepcopy(block["roles"]),
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    }


def _scope() -> dict[str, list[str]]:
    return {
        "issuer_ids": ["ISSUER:CN:002120"],
        "product_or_service_ids": ["SERVICE:CN:EXPRESS:STANDARD_PARCEL"],
        "plant_ids": ["NETWORK:CN:002120:SELF_OPERATED_HUBS"],
        "channel_ids": ["CHANNEL:CN:EXPRESS:FRANCHISE_LAST_MILE"],
        "region_ids": ["REGION:CN:NATIONAL"],
        "arena_ids": [
            "ARENA:CN:EXPRESS:ECOMMERCE_PARCEL_DEMAND",
            "ARENA:CN:EXPRESS:HUB_TRUNK_NETWORK",
            "ARENA:CN:EXPRESS:FRANCHISE_LAST_MILE",
            "ARENA:CN:EXPRESS:SERVICE_RESPONSE",
        ],
    }


def build_episode(
    *, role: str, method_id: str, contract: dict[str, Any], block: dict[str, Any],
    packet_id: str,
) -> dict[str, Any]:
    statements = BASELINE_STATEMENTS if role == "BASELINE" else ENHANCED_STATEMENTS
    states = {
        "INITIAL_CONDITIONS": "OBSERVED",
        "IMPLEMENTED_MANAGEMENT_ACTION": "OBSERVED",
        "EXECUTION": "INFERRED",
        "CUSTOMER_COMPETITION_RESPONSE": "INFERRED",
        "UNIT_ECONOMICS": "OBSERVED" if role == "BASELINE" else "INFERRED",
        "WORKING_CAPITAL_CASH_CAPITAL": "OBSERVED",
        "ADAPTATION_PERMANENT_LOSS": "UNKNOWN",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "INFERRED",
    }
    level = {
        dimension: (
            "E0_CONTEXT" if dimension == "INITIAL_CONDITIONS"
            else "E1_RECONSTRUCTION" if dimension in {"WORKING_CAPITAL_CASH_CAPITAL", "STRONGEST_ALTERNATIVE_EXPLANATION"}
            else "E2_MECHANISM_PROBE"
        )
        for dimension in DIMENSIONS
    }
    question_by_dimension = {
        dimension: question["question_id"]
        for question in QUESTIONS
        for dimension in question["dimensions"]
    }
    claims = [
        {
            "claim_id": f"CLAIM:R8:{role}:{dimension}",
            "question_id": question_by_dimension[dimension],
            "method_id": method_id,
            "judgment_dimension": dimension,
            "claim_scope": _scope(),
            "domain": DOMAINS[dimension],
            "statement": statements[dimension],
            "cell_status": states[dimension],
            "admission_level": level[dimension],
            "evidence_refs": [packet_id],
            "evidence_locator_refs": deepcopy(LOCATORS_BY_DIMENSION[dimension]),
            "dependent_outcome_cell_ids": deepcopy(DEPENDENCIES[dimension]),
        }
        for dimension in DIMENSIONS
    ]
    question_set = [
        {
            "question_id": question["question_id"],
            "role": question["role"],
            "question": question["question"],
            "claim_ids": [f"CLAIM:R8:{role}:{dimension}" for dimension in question["dimensions"]],
        }
        for question in QUESTIONS
    ]
    return {
        "schema_version": episode_module.SCHEMA_VERSION,
        "episode_id": f"EJE:CN002120:20190501:{role}:V2",
        "company_id": "CN:002120",
        "issuer_id": "ISSUER:CN:002120",
        "cutoff_at": "2019-05-01T00:00:00+08:00",
        "decision_contract_ref": {
            "contract_id": contract["contract_id"],
            "contract_version": contract["contract_version"],
        },
        "component_refs": [
            {
                "component_type": "ENTERPRISE_CONTEXT_SNAPSHOT",
                "component_id": "ECS:CN002120:20190501:R8",
                "component_version": "1",
                "admission_level": "E0_CONTEXT",
                "read_only": True,
            },
            {
                "component_type": "ENTERPRISE_SYSTEM_MODEL",
                "component_id": "ESM:CN002120:20190501:R8",
                "component_version": "1",
                "admission_level": "E1_RECONSTRUCTION",
                "read_only": True,
            },
            {
                "component_type": "MANAGEMENT_DECISION_LEDGER",
                "component_id": "MDL:CN002120:20190501:R8",
                "component_version": "1",
                "admission_level": "E1_RECONSTRUCTION",
                "read_only": True,
            },
            {
                "component_type": "OUTCOME_MEASUREMENT_CONTRACT",
                "component_id": MEASUREMENT_CONTRACT_ID,
                "component_version": "3",
                "admission_level": "E2_MECHANISM_PROBE",
                "read_only": True,
            },
        ],
        "question_set": question_set,
        "claims": claims,
        "mechanism_threads": [
            {
                "thread_id": "THREAD:R8:NETWORK_PRODUCTIVITY",
                "role": "PRIMARY",
                "claim_ids": [
                    f"CLAIM:R8:{role}:IMPLEMENTED_MANAGEMENT_ACTION",
                    f"CLAIM:R8:{role}:EXECUTION",
                    f"CLAIM:R8:{role}:UNIT_ECONOMICS",
                ],
                "hypotheses": [
                    {
                        "hypothesis_id": f"H-A:R8:{role}:NETWORK_PRODUCTIVITY",
                        "role": "H_A",
                        "statement": "Implemented automation and route coordination improve service-capacity utilization and unit economics.",
                    },
                    {
                        "hypothesis_id": f"H-B:R8:{role}:NETWORK_PRODUCTIVITY",
                        "role": "H_B",
                        "statement": "Industry demand, price-led volume and capacity additions reproduce scale without better execution economics.",
                    },
                ],
                "observation_clock_ref": "STRICT_EVENTS_FROM_2019-05-02_AND_FY2019_MIXED_CLOCK_CONTEXT",
                "outcome_cell_ids": [
                    CELL["NETWORK_SCALE_EVENT"], CELL["AUTOMATION_SERVICE_EVENT"],
                    CELL["EXPRESS_REVENUE_PER_PARCEL"], CELL["PARCEL_COST"],
                    CELL["EXPRESS_GROSS_MARGIN"],
                ],
            },
            {
                "thread_id": "THREAD:R8:CUSTOMER_FRANCHISE",
                "role": "SUPPORTING",
                "claim_ids": [
                    f"CLAIM:R8:{role}:CUSTOMER_COMPETITION_RESPONSE",
                    f"CLAIM:R8:{role}:ADAPTATION_PERMANENT_LOSS",
                ],
                "hypotheses": [
                    {
                        "hypothesis_id": f"H-A:R8:{role}:CUSTOMER_FRANCHISE",
                        "role": "H_A",
                        "statement": "Service and franchise support improve customer response while preserving network continuity.",
                    },
                    {
                        "hypothesis_id": f"H-B:R8:{role}:CUSTOMER_FRANCHISE",
                        "role": "H_B",
                        "statement": "Price and platform demand lift volume while franchise economics or service resilience remain weak.",
                    },
                ],
                "observation_clock_ref": "STRICT_EVENTS_FROM_2019-05-02_AND_FY2019_MIXED_CLOCK_CONTEXT",
                "outcome_cell_ids": [
                    CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
                    CELL["MARKET_SHARE_CHANGE"], CELL["COMPLAINT_RATE_CHANGE"],
                    CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"],
                ],
            },
            {
                "thread_id": "THREAD:R8:CASH_CAPITAL",
                "role": "SUPPORTING",
                "claim_ids": [
                    f"CLAIM:R8:{role}:WORKING_CAPITAL_CASH_CAPITAL",
                    f"CLAIM:R8:{role}:STRONGEST_ALTERNATIVE_EXPLANATION",
                ],
                "hypotheses": [
                    {
                        "hypothesis_id": f"H-A:R8:{role}:CASH_CAPITAL",
                        "role": "H_A",
                        "statement": "Network growth remains internally fundable after listed-company cash capex and financing burden.",
                    },
                    {
                        "hypothesis_id": f"H-B:R8:{role}:CASH_CAPITAL",
                        "role": "H_B",
                        "statement": "Industry growth and franchise-carried capital make headquarters cash look stronger than the full system economics.",
                    },
                ],
                "observation_clock_ref": "FY2019_MIXED_CLOCK_CONTEXT_NO_OWNER_CASH_INFERENCE",
                "outcome_cell_ids": [
                    CELL["INDUSTRY_PARCEL_GROWTH"], CELL["OPERATING_CASH_FLOW"],
                    CELL["CASH_CAPEX"], CELL["OCF_TO_CASH_CAPEX"],
                    CELL["ASSET_LIABILITY_RATIO"],
                ],
            },
        ],
        "outcome_cells": [
            {
                "outcome_cell_id": cell_id,
                "dimension": CELL_DIMENSIONS[cell_id],
                "status": "UNKNOWN",
                "measurement_contract_ref": MEASUREMENT_CONTRACT_ID,
                "custodian_receipt_ref": "",
            }
            for cell_id in CELL.values()
        ],
        "roles": deepcopy(block["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST",
        "claim_class": "COMPOSITE_ENTERPRISE_JUDGMENT",
        "allowed_outputs": list(episode_module.ALLOWED_OUTPUTS),
    }


def build_preoutcome_package(
    block: dict[str, Any], source_packets: list[dict[str, Any]], selection: dict[str, Any],
) -> dict[str, Any]:
    packet_ref = selection["source_packet_ref"]
    packet = next(
        packet for packet in source_packets
        if packet.get("packet_id") == packet_ref["receipt_id"]
        and packet.get("packet_version") == packet_ref["receipt_version"]
    )
    contract = build_decision_contract(block, selection)
    baseline = build_episode(
        role="BASELINE", method_id=BASELINE_METHOD_ID, contract=contract,
        block=block, packet_id=packet["packet_id"],
    )
    enhanced = build_episode(
        role="ENHANCED", method_id=ENHANCED_METHOD_ID, contract=contract,
        block=block, packet_id=packet["packet_id"],
    )
    pairing = {
        "schema_version": decision_utility.PAIRING_SCHEMA_VERSION,
        "pairing_id": "UTILITY:PAIR:CN002120:20190501:ROUND8:V2",
        "decision_contract_ref": {
            "contract_id": contract["contract_id"],
            "contract_version": contract["contract_version"],
        },
        "baseline_episode_id": baseline["episode_id"],
        "enhanced_episode_id": enhanced["episode_id"],
        "baseline_method_id": BASELINE_METHOD_ID,
        "enhanced_method_id": ENHANCED_METHOD_ID,
        "baseline_research_cost_hours": 2.0,
        "enhanced_research_cost_hours": 4.0,
        "frozen_at": FROZEN_AT,
        "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": list(decision_utility.ALLOWED_OUTPUTS),
    }
    return {
        "schema_version": multidimensional.PREOUTCOME_SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "industry_block_ref": {
            "block_id": block["block_id"],
            "schema_version": block["schema_version"],
        },
        "selection_ref": {
            "selection_id": selection["selection_id"],
            "schema_version": selection["schema_version"],
        },
        "source_packet_ref": deepcopy(selection["source_packet_ref"]),
        "decision_contract": contract,
        "baseline_episode": baseline,
        "enhanced_episode": enhanced,
        "decision_utility_pairing": pairing,
        "outcome_measurement_contract": build_measurement_contract(),
        "contamination_boundary": {
            "historical_replay_status": "MODEL_MEMORY_MITIGATED",
            "model_memory_mitigation": "PROCEDURAL_OUTCOME_SEPARATION_ONLY",
            "score_authority": "NONE",
            "allowed_use": "DEVELOPMENT_MULTIDIMENSIONAL_UTILITY_ONLY",
        },
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "frozen_at": FROZEN_AT,
        "roles": deepcopy(block["roles"]),
        "rights": deepcopy(RIGHTS),
        "object_class": "MULTIDIMENSIONAL_PREOUTCOME_PACKAGE",
        "claim_class": "SAME_EVIDENCE_BASELINE_ENHANCED_RESEARCH",
        "allowed_outputs": list(multidimensional.PREOUTCOME_OUTPUTS),
    }


def build_outcome_authorization(package: dict[str, Any]) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    source = contract["source_access"]
    return {
        "schema_version": measurement_acquisition.ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_receipt_id": source["authorization_receipt_id"],
        "measurement_contract_ref": {
            "measurement_contract_id": contract["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "company_id": contract["company_id"],
        "custodian_id": package["roles"]["outcome_custodian_id"],
        "source_id": source["source_id"],
        "authorized": True,
        "content_read": True,
    }


def build_source_inventory(
    package: dict[str, Any], *, local_pdf_path: Path, registered_at: str,
) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    source = contract["source_access"]
    authorization = build_outcome_authorization(package)
    return {
        "schema_version": measurement_acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "OMINV:CN002120:FY2019:R8:V1",
        "measurement_contract_ref": authorization["measurement_contract_ref"],
        "custodian_id": authorization["custodian_id"],
        "registered_at": registered_at,
        "documents": [{
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(local_pdf_path),
            "issuer_id": source["issuer_id"],
            "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:002120",
            "report_period_end": source["report_period_end"],
            "official_source_type": source["source_type"],
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": (
                "FY2019 issuer-consolidated original annual-report vintage. "
                "Express revenue and cost presentation added dispatch fees from 2019-01-01; "
                "affected unit-economics fields retain local MEASUREMENT_MISMATCH."
            ),
            "availability_precision": source["availability_precision"],
            "source_available_at": source["source_available_at"],
            "source_available_date": source["source_available_date"],
        }],
        "object_class": measurement_acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": measurement_acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }


def _field_source(
    *,
    cell: dict[str, Any],
    raw_field: dict[str, Any],
    page: int,
    custodian_table: str,
    custodian_line: str,
    custodian_period: str,
) -> dict[str, Any]:
    locator = raw_field["locator"]
    return {
        "source_id": OUTCOME_SOURCE_ID,
        "source_url": OUTCOME_SOURCE_URL,
        "report_period_end": "2019-12-31",
        "official_source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": "ISSUER:CN:002120",
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "availability_precision": "DATE_ONLY",
        "source_available_date": "2020-04-30",
        "pdf_page": page,
        "field_ref": f"PDF p.{page}",
        "field_identity": raw_field["field_id"],
        "measurement_clock": deepcopy(raw_field["measurement_clock"]),
        "unit": raw_field["unit"],
        "table_or_note": locator["table_or_note"],
        "line_item": locator["line_item"],
        "period_column": locator["period_column"],
        "custodian_locator": {
            "table_or_note": custodian_table,
            "line_item": custodian_line,
            "period_column": custodian_period,
        },
    }


def _field_record_base(cell: dict[str, Any], raw_field: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": cell["cell_id"],
        "field_id": raw_field["field_id"],
        "measurement_clock": deepcopy(raw_field["measurement_clock"]),
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "unit": raw_field["unit"],
    }


def build_custodian_field_records(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the exact frozen raw-field roster after reading the authorized PDF."""
    contract = package["outcome_measurement_contract"]
    observed: dict[str, tuple[float, int, str, str, str]] = {
        "FIELD:002120:FY2019:ISSUER_PARCEL_GROWTH": (
            0.4359, 30, "Management discussion", "Issuer parcel volume increased 43.59%", "FY2019",
        ),
        "FIELD:002120:FY2019:SPREAD_ISSUER_GROWTH": (
            0.4359, 30, "Management discussion", "Issuer parcel volume increased 43.59%", "FY2019",
        ),
        "FIELD:002120:FY2018:MARKET_SHARE": (
            0.1377, 30, "Management discussion", "Prior-year market share implied by 15.79% less 2.02 percentage points", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:MARKET_SHARE": (
            0.1579, 30, "Management discussion", "Issuer parcel market share 15.79%", "FY2019",
        ),
        "FIELD:002120:FY2019:PARCEL_VOLUME_RPP_DENOMINATOR": (
            10_030_000_000.0, 30, "Management discussion", "Completed parcels 10.03 billion", "FY2019",
        ),
        "FIELD:002120:FY2018:OPERATING_CASH_FLOW": (
            3_714_468_466.28, 6, "Key accounting data", "Net cash flows from operating activities", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:OPERATING_CASH_FLOW": (
            5_035_636_370.68, 6, "Key accounting data", "Net cash flows from operating activities", "FY2019",
        ),
        "FIELD:002120:FY2018:CASH_CAPEX": (
            3_469_731_936.52, 138, "Consolidated cash-flow statement", "Cash paid to acquire long-lived assets", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:CASH_CAPEX": (
            4_377_106_950.41, 138, "Consolidated cash-flow statement", "Cash paid to acquire long-lived assets", "FY2019",
        ),
        "FIELD:002120:FY2018:OCF_RATIO_NUMERATOR": (
            3_714_468_466.28, 6, "Key accounting data", "Net cash flows from operating activities", "FY2018 comparative",
        ),
        "FIELD:002120:FY2018:CAPEX_RATIO_DENOMINATOR": (
            3_469_731_936.52, 138, "Consolidated cash-flow statement", "Cash paid to acquire long-lived assets", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:OCF_RATIO_NUMERATOR": (
            5_035_636_370.68, 6, "Key accounting data", "Net cash flows from operating activities", "FY2019",
        ),
        "FIELD:002120:FY2019:CAPEX_RATIO_DENOMINATOR": (
            4_377_106_950.41, 138, "Consolidated cash-flow statement", "Cash paid to acquire long-lived assets", "FY2019",
        ),
        "FIELD:002120:FY2018:ASSET_LIABILITY_RATIO": (
            6_539_236_799.10 / 18_080_928_087.75,
            129,
            "Consolidated balance sheet",
            "Total liabilities RMB6,539,236,799.10 divided by total assets RMB18,080,928,087.75",
            "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:ASSET_LIABILITY_RATIO": (
            8_962_500_289.53 / 22_496_654_773.40,
            129,
            "Consolidated balance sheet",
            "Total liabilities RMB8,962,500,289.53 divided by total assets RMB22,496,654,773.40",
            "FY2019",
        ),
    }
    mismatch: dict[str, tuple[str, int, str, str, str]] = {
        "FIELD:002120:FY2019:INDUSTRY_PARCEL_GROWTH": (
            "NATIONAL_INDUSTRY_FIELD_IS_FROZEN_TO_AN_ISSUER_CONSOLIDATED_RESPONSIBILITY_BOUNDARY",
            26, "Industry review", "National parcel volume increased 25.3%", "FY2019",
        ),
        "FIELD:002120:FY2019:SPREAD_INDUSTRY_GROWTH": (
            "NATIONAL_INDUSTRY_FIELD_IS_FROZEN_TO_AN_ISSUER_CONSOLIDATED_RESPONSIBILITY_BOUNDARY",
            26, "Industry review", "National parcel volume increased 25.3%", "FY2019",
        ),
        "FIELD:002120:FY2018:EFFECTIVE_COMPLAINT_RATE": (
            "FROZEN_RATIO_UNIT_DOES_NOT_MATCH_DISCLOSED_COMPLAINTS_PER_MILLION_PARCELS",
            35, "Service-quality review", "Prior-year effective complaints 0.77 per million parcels", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:EFFECTIVE_COMPLAINT_RATE": (
            "FROZEN_RATIO_UNIT_DOES_NOT_MATCH_DISCLOSED_COMPLAINTS_PER_MILLION_PARCELS",
            35, "Service-quality review", "Effective complaints 0.05 per million parcels", "FY2019",
        ),
        "FIELD:002120:FY2018:EXPRESS_REVENUE_RPP_NUMERATOR": (
            "FY2019_EXPRESS_REVENUE_ADDS_DISPATCH_FEES_AND_IS_NOT_DEFINITIONALLY_COMPARABLE_TO_FY2018",
            38, "Principal business by service", "Dispatch-fee revenue added from 2019-01-01", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:EXPRESS_REVENUE_RPP_NUMERATOR": (
            "FY2019_EXPRESS_REVENUE_ADDS_DISPATCH_FEES_AND_IS_NOT_DEFINITIONALLY_COMPARABLE_TO_FY2018",
            38, "Principal business by service", "Dispatch-fee revenue added from 2019-01-01", "FY2019",
        ),
        "FIELD:002120:FY2018:PARCEL_COST": (
            "FROZEN_FY2018_PARCEL_COST_IS_NOT_BRIDGED_TO_THE_FY2019_DISPATCH_FEE_COST_SCOPE",
            35, "Unit-cost review", "FY2019 reports RMB2.83 on a same-calibre series but gives no auditable bridge to frozen FY2018", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:PARCEL_COST": (
            "FROZEN_FY2018_PARCEL_COST_IS_NOT_BRIDGED_TO_THE_FY2019_DISPATCH_FEE_COST_SCOPE",
            35, "Unit-cost review", "FY2019 parcel cost RMB2.83 after dispatch-service presentation change", "FY2019",
        ),
        "FIELD:002120:FY2018:EXPRESS_GROSS_MARGIN": (
            "EXPRESS_GROSS_MARGIN_SCOPE_CHANGED_WITH_DISPATCH_FEE_REVENUE_AND_COST_PRESENTATION",
            38, "Principal business by service", "FY2019 gross-margin table includes newly presented dispatch fees", "FY2018 comparative",
        ),
        "FIELD:002120:FY2019:EXPRESS_GROSS_MARGIN": (
            "EXPRESS_GROSS_MARGIN_SCOPE_CHANGED_WITH_DISPATCH_FEE_REVENUE_AND_COST_PRESENTATION",
            38, "Principal business by service", "FY2019 gross margin 11.35% includes newly presented dispatch fees", "FY2019",
        ),
    }
    unknown = {
        "FIELD:002120:FY2018:PARCEL_VOLUME_RPP_DENOMINATOR": (
            "AUTHORIZED_FY2019_REPORT_DOES_NOT_DIRECTLY_DISCLOSE_THE_EXACT_FY2018_PARCEL_DENOMINATOR",
            "PDF p.30 gives rounded FY2019 volume and growth only",
        ),
        "FIELD:002120:FY2019:NETWORK_SCALE_EVENT": (
            "FY2019_NETWORK_IMPLEMENTATION_IS_DISCLOSED_WITHOUT_A_DATE_AFTER_2019_05_01",
            "PDF pp.24-35 FY2019 network and operating review",
        ),
        "FIELD:002120:FY2019:AUTOMATION_SERVICE_EVENT": (
            "FY2019_AUTOMATION_AND_SERVICE_IMPLEMENTATION_IS_DISCLOSED_WITHOUT_A_DATE_AFTER_2019_05_01",
            "PDF pp.24-35 FY2019 automation and service review",
        ),
        "FIELD:002120:FY2019:FRANCHISE_NETWORK_ADVERSE_EVENT": (
            "AUTHORIZED_REPORT_HAS_NO_EXPLICIT_DATED_POSITIVE_OR_NEGATIVE_EVENT_FOR_THE_FROZEN_WINDOW",
            "PDF pp.25-33 and risk disclosures",
        ),
    }
    considered_source = {
        "source_id": OUTCOME_SOURCE_ID,
        "source_url": OUTCOME_SOURCE_URL,
        "report_period_end": "2019-12-31",
        "official_source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": "ISSUER:CN:002120",
        "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:002120",
        "availability_precision": "DATE_ONLY",
        "source_available_date": "2020-04-30",
    }
    records: list[dict[str, Any]] = []
    for cell in contract["atomic_cells"]:
        for raw_field in cell["raw_input_fields"]:
            field_id = raw_field["field_id"]
            base = _field_record_base(cell, raw_field)
            if field_id in observed:
                value, page, table, line, period = observed[field_id]
                records.append({
                    **base,
                    "status": "OBSERVED",
                    "raw_value": value,
                    "source": _field_source(
                        cell=cell, raw_field=raw_field, page=page,
                        custodian_table=table, custodian_line=line, custodian_period=period,
                    ),
                })
            elif field_id in mismatch:
                reason, page, table, line, period = mismatch[field_id]
                records.append({
                    **base,
                    "status": "MEASUREMENT_MISMATCH",
                    "reason": reason,
                    "source": _field_source(
                        cell=cell, raw_field=raw_field, page=page,
                        custodian_table=table, custodian_line=line, custodian_period=period,
                    ),
                })
            else:
                reason, location = unknown[field_id]
                records.append({
                    **base,
                    "status": "UNKNOWN",
                    "reason": reason,
                    "sources_considered": [{**considered_source, "field_ref": location}],
                })
    return records


PAGE_VALUE_BINDINGS: dict[str, dict[str, Any]] = {
    "FIELD:002120:FY2019:ISSUER_PARCEL_GROWTH": {
        "pdf_page": 30, "anchor_tokens": ["累计完成快递业务量100.3亿票", "同比增长43.59%"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["43.59%"], "multiplier": "0.01"},
    },
    "FIELD:002120:FY2019:SPREAD_ISSUER_GROWTH": {
        "pdf_page": 30, "anchor_tokens": ["累计完成快递业务量100.3亿票", "同比增长43.59%"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["43.59%"], "multiplier": "0.01"},
    },
    "FIELD:002120:FY2018:MARKET_SHARE": {
        "pdf_page": 30, "anchor_tokens": ["市场份额达15.79%", "提高2.02个百分点"],
        "value_expression": {"operator": "DIFFERENCE_SCALED_TOKENS", "tokens": ["15.79%", "2.02"], "multiplier": "0.01"},
    },
    "FIELD:002120:FY2019:MARKET_SHARE": {
        "pdf_page": 30, "anchor_tokens": ["市场份额达15.79%", "提高2.02个百分点"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["15.79%"], "multiplier": "0.01"},
    },
    "FIELD:002120:FY2019:PARCEL_VOLUME_RPP_DENOMINATOR": {
        "pdf_page": 30, "anchor_tokens": ["累计完成快递业务量100.3亿票", "同比增长43.59%"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["100.3"], "multiplier": "100000000"},
    },
    "FIELD:002120:FY2018:OPERATING_CASH_FLOW": {
        "pdf_page": 6, "anchor_tokens": ["经营活动产生的现金流量净额", "3,714,468,466.28"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["3,714,468,466.28"], "multiplier": "1"},
    },
    "FIELD:002120:FY2019:OPERATING_CASH_FLOW": {
        "pdf_page": 6, "anchor_tokens": ["经营活动产生的现金流量净额", "5,035,636,370.68"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["5,035,636,370.68"], "multiplier": "1"},
    },
    "FIELD:002120:FY2018:CASH_CAPEX": {
        "pdf_page": 138, "anchor_tokens": ["购建固定资产、无形资产和其他", "3,469,731,936.52"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["3,469,731,936.52"], "multiplier": "1"},
    },
    "FIELD:002120:FY2019:CASH_CAPEX": {
        "pdf_page": 138, "anchor_tokens": ["购建固定资产、无形资产和其他", "4,377,106,950.41"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["4,377,106,950.41"], "multiplier": "1"},
    },
    "FIELD:002120:FY2018:OCF_RATIO_NUMERATOR": {
        "pdf_page": 6, "anchor_tokens": ["经营活动产生的现金流量净额", "3,714,468,466.28"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["3,714,468,466.28"], "multiplier": "1"},
    },
    "FIELD:002120:FY2018:CAPEX_RATIO_DENOMINATOR": {
        "pdf_page": 138, "anchor_tokens": ["购建固定资产、无形资产和其他", "3,469,731,936.52"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["3,469,731,936.52"], "multiplier": "1"},
    },
    "FIELD:002120:FY2019:OCF_RATIO_NUMERATOR": {
        "pdf_page": 6, "anchor_tokens": ["经营活动产生的现金流量净额", "5,035,636,370.68"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["5,035,636,370.68"], "multiplier": "1"},
    },
    "FIELD:002120:FY2019:CAPEX_RATIO_DENOMINATOR": {
        "pdf_page": 138, "anchor_tokens": ["购建固定资产、无形资产和其他", "4,377,106,950.41"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["4,377,106,950.41"], "multiplier": "1"},
    },
    "FIELD:002120:FY2018:ASSET_LIABILITY_RATIO": {
        "pdf_page": 129, "anchor_tokens": ["负债合计", "负债和所有者权益总计"],
        "value_expression": {"operator": "RATIO_TOKENS", "tokens": ["6,539,236,799.10", "18,080,928,087.75"], "multiplier": "1"},
    },
    "FIELD:002120:FY2019:ASSET_LIABILITY_RATIO": {
        "pdf_page": 129, "anchor_tokens": ["负债合计", "负债和所有者权益总计"],
        "value_expression": {"operator": "RATIO_TOKENS", "tokens": ["8,962,500,289.53", "22,496,654,773.40"], "multiplier": "1"},
    },
}


def build_page_extraction_receipts(field_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    receipts = []
    for record in field_records:
        if record.get("status") != "OBSERVED":
            continue
        field_id = record["field_id"]
        binding = PAGE_VALUE_BINDINGS.get(field_id)
        if binding is None:
            raise ValueError(f"round8 observed field lacks a page-value binding: {field_id}")
        source = record["source"]
        receipts.append({
            "schema_version": measurement_acquisition.PAGE_EXTRACTION_RECEIPT_SCHEMA_VERSION,
            "receipt_id": f"PAGEEXTRACT:R8:{field_id}",
            "field_id": field_id,
            "source_id": source["source_id"],
            "pdf_page": binding["pdf_page"],
            "unit": record["unit"],
            "anchor_tokens": deepcopy(binding["anchor_tokens"]),
            "value_expression": deepcopy(binding["value_expression"]),
            "object_class": "ENTERPRISE_PAGE_EXTRACTION_RECEIPT",
            "claim_class": "PDF_PAGE_VALUE_BINDING_ONLY",
        })
    return receipts


def settle_custodian_field_records(
    package: dict[str, Any],
    field_records: list[dict[str, Any]],
    *,
    page_extraction_receipts: list[dict[str, Any]],
    local_pdf_path: Path,
    registry_db: Path,
    registered_at: str,
    observed_at: str,
    settled_at: str,
) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    authorization = build_outcome_authorization(package)
    inventory = build_source_inventory(
        package, local_pdf_path=local_pdf_path, registered_at=registered_at,
    )
    inventory_validation = measurement_acquisition.validate_registered_local_pdf_inventory(
        inventory,
        measurement_contract=contract,
        outcome_access_authorization=authorization,
    )
    if not inventory_validation["valid"]:
        raise ValueError(
            "round8 source inventory invalid: " + "; ".join(inventory_validation["findings"]),
        )
    page_validation = measurement_acquisition.validate_page_bound_enterprise_field_records(
        field_records,
        page_extraction_receipts,
        measurement_contract=contract,
        inventory=inventory,
    )
    if not page_validation["valid"]:
        raise ValueError(
            "round8 page extraction receipts invalid: " + "; ".join(page_validation["findings"]),
        )
    acquisition_result = measurement_acquisition.acquire_outcome_measurements_from_field_records(
        contract,
        inventory,
        field_records,
        outcome_access_authorization=authorization,
    )
    previous_registry = reconstruction.CANONICAL_REGISTRY_PATH
    reconstruction.CANONICAL_REGISTRY_PATH = registry_db
    try:
        enterprise_control.register_measurement_contract(
            contract, frozen_at=contract["contract_frozen_at"],
        )
        settlement = settlement_adapter.settle_enterprise_acquisition_result(
            measurement_contract=contract,
            outcome_access_authorization=authorization,
            acquisition_result=acquisition_result,
            observed_at=observed_at,
            settlement_id=OUTCOME_SETTLEMENT_ID,
            settled_at=settled_at,
        )
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    settlement.pop("persisted", None)
    settlement.pop("idempotent", None)
    return {
        "authorization": authorization,
        "inventory": inventory,
        "field_records": deepcopy(field_records),
        "page_extraction_receipts": deepcopy(page_extraction_receipts),
        "acquisition_result": acquisition_result,
        "settlement": settlement,
    }


def build_scope_clock_adjudication(
    package: dict[str, Any], settlement: dict[str, Any], *, adjudicated_at: str,
) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    results = {row["cell_id"]: row for row in settlement["cell_results"]}
    cells = []
    for cell in contract["atomic_cells"]:
        cell_id = cell["cell_id"]
        clock_kind = cell["measurement_clock"]["clock_kind"]
        if cell_id in {
            CELL["INDUSTRY_PARCEL_GROWTH"],
            CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
        }:
            use_class = "BOUNDARY_MISMATCH"
        elif cell_id == CELL["COMPLAINT_RATE_CHANGE"]:
            use_class = "UNIT_MISMATCH_DIRECTION_ONLY"
        elif clock_kind == "FLOW_PERIOD":
            use_class = "MIXED_CLOCK_CONTEXT_ONLY"
        elif clock_kind == "EVENT_WINDOW":
            use_class = "POST_CUTOFF_EVENT_ONLY"
        else:
            use_class = "POST_CUTOFF_STATE_CONTEXT_ONLY"
        cells.append({
            "cell_id": cell_id,
            "settlement_status": results[cell_id]["status"],
            "measurement_use_class": use_class,
            "causal_credit": "NONE",
            "allowed_utility_use": (
                "ERROR_AVOIDANCE_OR_DESCRIPTIVE_CONTEXT_ONLY"
                if use_class != "POST_CUTOFF_EVENT_ONLY"
                else "EVENT_EVIDENCE_ONLY_IF_OBSERVED"
            ),
        })
    return {
        "schema_version": "enterprise-judgment-round8-scope-clock-adjudication.v1",
        "adjudication_id": "R8ADJ:CN002120:20190501:FY2019:V1",
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "adjudicated_at": adjudicated_at,
        "root_cause": ["MODEL", "REASONING"],
        "cells": cells,
        "overall_effect": (
            "No FY2019 flow, balance or unresolved event cell may support causal credit for a "
            "post-cutoff management action. National industry cells are locally ineligible because "
            "the frozen contract used an issuer-consolidated boundary."
        ),
        "accepted_risk": (
            "The exact post-cutoff source identity remains predeclared to prevent outcome-source "
            "selection; content isolation is procedural rather than adversarial."
        ),
        "object_class": "OUTCOME_SCOPE_CLOCK_ADJUDICATION",
        "claim_class": "POST_OUTCOME_CONSERVATIVE_ELIGIBILITY_OVERLAY",
        "allowed_outputs": ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


def _canonical_round8_settlement(
    settlement: dict[str, Any], *, registry_db: Path,
) -> dict[str, Any]:
    previous_registry = reconstruction.CANONICAL_REGISTRY_PATH
    reconstruction.CANONICAL_REGISTRY_PATH = registry_db
    try:
        canonical = enterprise_control.replay_enterprise_settlement(settlement["settlement_id"])
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    if canonical != settlement:
        raise ValueError("round8 settlement differs from canonical replay")
    return canonical


def _validate_scope_clock_adjudication(
    package: dict[str, Any], settlement: dict[str, Any], adjudication: dict[str, Any],
) -> None:
    expected = build_scope_clock_adjudication(
        package,
        settlement,
        adjudicated_at=adjudication.get("adjudicated_at", ""),
    )
    if adjudication != expected:
        raise ValueError("round8 adjudication does not replay from canonical settlement")


def build_utility_evaluation(
    package: dict[str, Any],
    settlement: dict[str, Any],
    adjudication: dict[str, Any],
    *,
    reviewer_id: str,
    evaluated_at: str,
    registry_db: Path,
) -> dict[str, Any]:
    settlement = _canonical_round8_settlement(settlement, registry_db=registry_db)
    _validate_scope_clock_adjudication(package, settlement, adjudication)
    adjudicated_ids = [row.get("cell_id") for row in adjudication.get("cells", [])]
    expected_ids = [
        cell["cell_id"] for cell in package["outcome_measurement_contract"]["atomic_cells"]
    ]
    if adjudicated_ids != expected_ids or any(
        row.get("causal_credit") != "NONE" for row in adjudication.get("cells", [])
    ):
        raise ValueError("round8 utility requires complete no-causal-credit adjudication")
    results = {row["cell_id"]: row for row in settlement["cell_results"]}
    if list(results) != expected_ids:
        raise ValueError("round8 utility requires ordered settlement coverage")
    adjudicated = {row["cell_id"]: row for row in adjudication["cells"]}
    if any(
        adjudicated[cell_id]["settlement_status"] != results[cell_id]["status"]
        for cell_id in expected_ids
    ):
        raise ValueError("round8 adjudication status does not match settlement")
    share_result = results[CELL["MARKET_SHARE_CHANGE"]]
    share_description = (
        f"market-share change settled {share_result['label']}"
        if share_result["status"] == "OBSERVED"
        else f"market-share change remained {share_result['status']}"
    )
    findings = [
        {
            "dimension_id": "INITIAL_CONDITIONS",
            "baseline_assessment": "NOT_DIAGNOSTIC",
            "enhanced_assessment": "NOT_DIAGNOSTIC",
            "supporting_cell_ids": [
                CELL["INDUSTRY_PARCEL_GROWTH"],
                CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
            ],
            "rationale": (
                "Both methods saw rapid parcel demand, but the frozen national-industry cell used an "
                "issuer-consolidated boundary and settled MEASUREMENT_MISMATCH. The initial-condition "
                "comparison is therefore not diagnostic of method advantage."
            ),
        },
        {
            "dimension_id": "IMPLEMENTED_MANAGEMENT_ACTION",
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": "NO_DIFFERENCE",
            "supporting_cell_ids": [
                CELL["NETWORK_SCALE_EVENT"], CELL["AUTOMATION_SERVICE_EVENT"],
            ],
            "rationale": (
                "Both frozen methods faced the same undated FY2019 automation, route and "
                "franchise-support narrative. Neither method gained a dated post-cutoff action result."
            ),
        },
        {
            "dimension_id": "EXECUTION",
            "baseline_assessment": "NOT_DIAGNOSTIC",
            "enhanced_assessment": "NOT_DIAGNOSTIC",
            "supporting_cell_ids": [
                CELL["ISSUER_PARCEL_GROWTH"], CELL["NETWORK_SCALE_EVENT"],
                CELL["AUTOMATION_SERVICE_EVENT"], CELL["PARCEL_COST"],
            ],
            "rationale": (
                "Parcel growth was observed, while both dated event cells remained UNKNOWN and parcel "
                "cost remained MEASUREMENT_MISMATCH. The pre-outcome package did not freeze separate "
                "method-specific outcome resolution rules, so neither method may receive execution "
                "credit or avoided-error credit after seeing these statuses."
            ),
        },
        {
            "dimension_id": "CUSTOMER_COMPETITION_RESPONSE",
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": "NO_DIFFERENCE",
            "supporting_cell_ids": [
                CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"], CELL["MARKET_SHARE_CHANGE"],
                CELL["COMPLAINT_RATE_CHANGE"],
            ],
            "rationale": (
                f"The {share_description}; complaint change settled "
                f"{results[CELL['COMPLAINT_RATE_CHANGE']]['status']} because the frozen RATIO unit did "
                "not match complaints per million parcels. Both methods already preserved price, "
                "platform traffic and shipper mix as rivals, so no incremental customer conclusion exists."
            ),
        },
        {
            "dimension_id": "UNIT_ECONOMICS",
            "baseline_assessment": "NOT_DIAGNOSTIC",
            "enhanced_assessment": "NOT_DIAGNOSTIC",
            "supporting_cell_ids": [
                CELL["EXPRESS_REVENUE_PER_PARCEL"], CELL["PARCEL_COST"],
                CELL["EXPRESS_GROSS_MARGIN"],
            ],
            "rationale": (
                "FY2019 added dispatch-fee revenue and the corresponding service cost. Revenue per "
                "parcel, parcel cost and express gross margin therefore failed the frozen same-definition "
                "test locally. This protection belongs to the shared Measurement Contract, not to the "
                "Enhanced reasoning method."
            ),
        },
        {
            "dimension_id": "WORKING_CAPITAL_CASH_CAPITAL",
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": "NO_DIFFERENCE",
            "supporting_cell_ids": [
                CELL["OPERATING_CASH_FLOW"], CELL["CASH_CAPEX"],
                CELL["OCF_TO_CASH_CAPEX"],
            ],
            "rationale": (
                f"Operating cash, cash capex and OCF-to-cash-capex settled "
                f"{results[CELL['OPERATING_CASH_FLOW']]['label']}, "
                f"{results[CELL['CASH_CAPEX']]['label']} and "
                f"{results[CELL['OCF_TO_CASH_CAPEX']]['label']}. Both methods already kept these "
                "headquarters flows separate from owner cash and franchisee cash economics."
            ),
        },
        {
            "dimension_id": "ADAPTATION_PERMANENT_LOSS",
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": "NO_DIFFERENCE",
            "supporting_cell_ids": [
                CELL["ASSET_LIABILITY_RATIO"], CELL["FRANCHISE_NETWORK_ADVERSE_EVENT"],
            ],
            "rationale": (
                f"Leverage change settled {results[CELL['ASSET_LIABILITY_RATIO']]['label']} and the "
                f"franchise adverse-event cell remained {results[CELL['FRANCHISE_NETWORK_ADVERSE_EVENT']]['status']}. "
                "Both methods already kept network resilience and irreversible franchisee loss UNKNOWN."
            ),
        },
        {
            "dimension_id": "STRONGEST_ALTERNATIVE_EXPLANATION",
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": "NO_DIFFERENCE",
            "supporting_cell_ids": [
                CELL["INDUSTRY_PARCEL_GROWTH"],
                CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"],
                CELL["EXPRESS_GROSS_MARGIN"],
            ],
            "rationale": (
                "Both frozen methods already retained industry demand, price-led volume and accounting "
                "presentation as rival explanations. The Enhanced text is more detailed but did not add "
                "a distinct rival or a settlement-backed discrimination in this turn."
            ),
        },
    ]
    evaluation = {
        "schema_version": decision_utility.EVALUATION_SCHEMA_VERSION,
        "evaluation_id": UTILITY_EVALUATION_ID,
        "pairing_id": package["decision_utility_pairing"]["pairing_id"],
        "evaluated_at": evaluated_at,
        "reviewer_id": reviewer_id,
        "outcome_settlement_ref": settlement["settlement_id"],
        "dimension_findings": findings,
        "holdout": {
            "training_company_ids": ["CN:600585", "CN:600801", "CN:600802"],
            "holdout_company_ids": ["CN:002120"],
            "training_cutoff_through": "2018-04-30T23:59:59+08:00",
            "holdout_cutoff_from": "2019-05-01T00:00:00+08:00",
        },
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": list(decision_utility.ALLOWED_OUTPUTS),
    }
    validation = decision_utility.validate_decision_utility_evaluation(
        evaluation,
        pairing=package["decision_utility_pairing"],
        contract=package["decision_contract"],
        baseline_episode=package["baseline_episode"],
        enhanced_episode=package["enhanced_episode"],
    )
    if not validation["valid"]:
        raise ValueError(
            "round8 utility evaluation invalid: " + "; ".join(validation["findings"]),
        )
    return evaluation


def validate_independent_utility_acceptance(
    package: dict[str, Any],
    settlement: dict[str, Any],
    adjudication: dict[str, Any],
    evaluation: dict[str, Any],
    acceptance: Any,
) -> dict[str, Any]:
    required = {
        "schema_version", "acceptance_id", "evaluation_ref", "package_ref", "settlement_ref",
        "scope_clock_adjudication_ref", "reviewer_id", "reviewed_at", "review_status",
        "accepted_dimension_conclusions", "overall_conclusion", "accepted_controls",
        "remaining_material_findings", "rights", "object_class", "claim_class", "allowed_outputs",
    }
    item = acceptance if isinstance(acceptance, dict) else {}
    findings = []
    if set(item) != required:
        findings.append("independent_acceptance_shape_invalid")
    if item.get("schema_version") != "enterprise-judgment-round8-independent-utility-acceptance.v2":
        findings.append("independent_acceptance_schema_invalid")
    expected_refs = {
        "evaluation_ref": evaluation.get("evaluation_id"),
        "package_ref": package.get("package_id"),
        "settlement_ref": settlement.get("settlement_id"),
        "scope_clock_adjudication_ref": adjudication.get("adjudication_id"),
    }
    if any(item.get(key) != value for key, value in expected_refs.items()):
        findings.append("independent_acceptance_reference_mismatch")
    if item.get("reviewer_id") != evaluation.get("reviewer_id") or item.get("reviewer_id") != INDEPENDENT_REVIEWER_ID:
        findings.append("independent_acceptance_reviewer_mismatch")
    if item.get("review_status") != "SUBSTANTIVE_ACCEPTED_NO_METHOD_ADVANTAGE":
        findings.append("independent_acceptance_status_invalid")
    expected_dimensions = {
        row["dimension_id"]: {
            "baseline_assessment": row["baseline_assessment"],
            "enhanced_assessment": row["enhanced_assessment"],
        }
        for row in evaluation.get("dimension_findings", [])
    }
    if item.get("accepted_dimension_conclusions") != expected_dimensions:
        findings.append("independent_acceptance_dimension_conclusions_mismatch")
    if item.get("overall_conclusion") != METHOD_CONCLUSION:
        findings.append("independent_acceptance_overall_conclusion_invalid")
    if not isinstance(item.get("accepted_controls"), list) or not item.get("accepted_controls"):
        findings.append("independent_acceptance_controls_required")
    if item.get("remaining_material_findings") != []:
        findings.append("independent_acceptance_material_findings_must_be_closed")
    if item.get("rights") != RIGHTS:
        findings.append("independent_acceptance_rights_invalid")
    if item.get("object_class") != "INDEPENDENT_UTILITY_REVIEW_ACCEPTANCE" or item.get("claim_class") != "NO_METHOD_ADVANTAGE_ACCEPTANCE":
        findings.append("independent_acceptance_object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ["ROUND8_COMPLETION_RECEIPT", "RESEARCH_AGENDA"]:
        findings.append("independent_acceptance_outputs_invalid")
    return {"valid": not findings, "findings": findings}


def build_completion_receipt(
    package: dict[str, Any],
    settlement: dict[str, Any],
    adjudication: dict[str, Any],
    evaluation: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    registry_db: Path,
) -> dict[str, Any]:
    settlement = _canonical_round8_settlement(settlement, registry_db=registry_db)
    _validate_scope_clock_adjudication(package, settlement, adjudication)
    expected_evaluation = build_utility_evaluation(
        package,
        settlement,
        adjudication,
        reviewer_id=evaluation.get("reviewer_id", ""),
        evaluated_at=evaluation.get("evaluated_at", ""),
        registry_db=registry_db,
    )
    if evaluation != expected_evaluation:
        raise ValueError("round8 evaluation does not replay from canonical settlement")
    acceptance_validation = validate_independent_utility_acceptance(
        package, settlement, adjudication, evaluation, acceptance,
    )
    if not acceptance_validation["valid"]:
        raise ValueError(
            "round8 independent utility acceptance invalid: "
            + "; ".join(acceptance_validation["findings"]),
        )
    return {
        "schema_version": "enterprise-judgment-round8-completion.v2",
        "completion_id": "R8COMPLETE:CN002120:20190501:FY2019:V1",
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "scope_clock_adjudication_ref": adjudication["adjudication_id"],
        "evaluation_ref": evaluation["evaluation_id"],
        "independent_acceptance_ref": acceptance["acceptance_id"],
        "company_id": package["decision_contract"]["company_id"],
        "cutoff_at": package["decision_contract"]["cutoff_at"],
        "status": "ROUND8_REAL_CROSS_INDUSTRY_FEEDBACK_COMPLETED",
        "method_conclusion": METHOD_CONCLUSION,
        "investor_summary": (
            "Round 8 completed real cross-industry feedback but did not prove that the Enhanced method "
            "outperformed the Baseline. The eight dimensions exposed boundary, unit and causal-attribution "
            "problems; without frozen method-specific resolution rules, those protections cannot be credited "
            "as a measured method advantage."
        ),
        "proved": [
            "The issuer grew parcel volume and the frozen share cell increased in FY2019.",
            "The annual report describes a lower complaint metric, but its per-million unit was not correctly frozen.",
            "Consolidated operating cash flow grew faster than cash capex, while leverage also increased.",
            "A dispatch-fee presentation change prevents same-definition unit-economics scoring.",
            "The eight-dimensional review exposed that scale, event timing and cost evidence cannot support an execution conclusion here.",
        ],
        "not_proved": [
            "The eight-dimensional Enhanced method has material overall utility versus an independent simple baseline.",
            "The Enhanced method avoided an error that the frozen Baseline would mechanically have made.",
            "The issuer outperformed a correctly bounded industry reference in the frozen result contract.",
            "Customer loyalty or pricing power caused the volume and share gains.",
            "Post-cutoff automation or network execution caused the FY2019 observations.",
            "Headquarters cash represents distributable owner cash or healthy franchisee cash economics.",
            "The franchise network avoided irreversible loss or established a durable moat.",
            "The eight-dimensional method is cross-industry or prospectively validated.",
            "The method is authorized for CJO, valuation, report or investment use.",
        ],
        "next_research_actions": [
            "Repeat the same eight-dimensional skeleton on a second unseen industry/company cutoff.",
            "Freeze a genuinely simple independent Baseline that does not reuse the Enhanced mechanism questions or rivals.",
            "Freeze separate outcome resolution rules for Baseline and Enhanced before opening any result source.",
            "Bind industry context to an industry responsibility perimeter rather than the issuer perimeter.",
            "Make causal eligibility machine-readable and require evaluation findings to cite eligible cells.",
            "Freeze complaints per million parcels as its own unit rather than a generic ratio.",
            "Freeze a definitionally comparable per-parcel revenue, cost and gross-margin bridge before outcome access.",
            "Add dated post-cutoff operating-event evidence when the official source provides it; otherwise retain UNKNOWN.",
            "Keep franchisee economics and ordinary-share owner cash as separate evidence targets.",
        ],
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_ROUND_COMPLETION_RECEIPT",
        "claim_class": "REAL_CROSS_INDUSTRY_METHOD_FEEDBACK",
        "allowed_outputs": ["ROUND8_REAL_FEEDBACK_COMPLETED", "RESEARCH_AGENDA"],
    }


def _read(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block", required=True)
    parser.add_argument("--source-packets", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--write-preoutcome")
    args = parser.parse_args()
    block = _read(args.block)
    packets = _read(args.source_packets)
    selection = _read(args.selection)
    package = build_preoutcome_package(block, packets, selection)
    result = multidimensional.validate_preoutcome_package(
        package, block=block, source_packets=packets, selection=selection,
    )
    if args.write_preoutcome and result["valid"]:
        Path(args.write_preoutcome).write_text(
            json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    print(json.dumps({"valid": result["valid"], "findings": result["findings"]}, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
