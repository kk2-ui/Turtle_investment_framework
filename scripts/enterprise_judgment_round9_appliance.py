#!/usr/bin/env python3
"""Round 9 pre-outcome appliance training for Sichuan Changhong.

The module deliberately has two phases.  This file initially owns only the
pre-outcome freeze: mechanical selection, a simple issuer-trend baseline, the
eight-dimensional method, atomic measurements, source-resolution policy, and
method-specific outcome rules.  Result-source metadata and content are bound
only after this freeze has been committed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode_module
    from scripts import enterprise_judgment_multidimensional_training as multidimensional
    from scripts import enterprise_judgment_source_packet as source_packet_module
    from scripts import judgment_decision_utility as decision_utility
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_episode as episode_module
    import enterprise_judgment_multidimensional_training as multidimensional
    import enterprise_judgment_source_packet as source_packet_module
    import judgment_decision_utility as decision_utility


COMPANY_ID = "CN:600839"
ISSUER_ID = "ISSUER:CN:600839"
CUTOFF_AT = "2018-09-30T23:59:59+08:00"
FROZEN_AT = "2026-08-27T18:00:00+08:00"
BLOCK_ID = "ILB:CN:APPLIANCE:CHANGHONG:20180930_20191231:R9:V1"
PACKET_ID = "SP:CN600839:20180930:FY2017:R9"
SOURCE_ID = "CNINFO:600839:ANN:20180418:1204647552"
SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2018-04-18/1204647552.PDF"
PACKAGE_ID = "R9:CN:APPLIANCE:CN600839:20180930:V1"
MEASUREMENT_CONTRACT_ID = "OMC:CN600839:20180930:EIGHT_DIMENSION:V3"
BASELINE_METHOD_ID = "METHOD:SIMPLE_WHITE_GOODS_TREND_WITH_GROUP_GUARD:V2"
ENHANCED_METHOD_ID = "METHOD:EIGHT_DIMENSION_ENTERPRISE_JUDGMENT:V1"
UNRESOLVED_SOURCE_ID = "UNRESOLVED:CNINFO:600839:FY2019:ORIGINAL_ANNUAL_REPORT"
UNRESOLVED_SOURCE_URL = (
    "https://static.cninfo.com.cn/finalpage/POST_FREEZE_RESOLUTION_REQUIRED.PDF"
)
RIGHTS = deepcopy(multidimensional.PREOUTCOME_RIGHTS)
DIMENSIONS = list(decision_utility.DIMENSIONS)


LOCATOR = {
    "INITIAL": "LOC:600839:FY2017:COMPETITIVE_INITIAL_CONDITIONS",
    "ACTION": "LOC:600839:FY2017:IMPLEMENTED_WHITE_GOODS_ACTIONS",
    "SYSTEM": "LOC:600839:FY2017:MULTI_PRODUCT_SYSTEM",
    "PRODUCT": "LOC:600839:FY2017:WHITE_GOODS_UNIT_ECONOMICS",
    "CASH": "LOC:600839:FY2017:GROUP_CASH_AND_PORTFOLIO",
}

CELL = {
    "INDUSTRY_CONTEXT_EVENT": "CELL:600839:FY2019:INDUSTRY_CONTEXT_EVENT",
    "GROUP_REVENUE_LEVEL": "CELL:600839:FY2019:GROUP_REVENUE_LEVEL",
    "WHITE_GOODS_REVENUE_LEVEL": "CELL:600839:FY2019:WHITE_GOODS_REVENUE_LEVEL",
    "WHITE_GOODS_GROSS_MARGIN": "CELL:600839:FY2019:WHITE_GOODS_GROSS_MARGIN",
    "WHITE_GOODS_REVENUE_SHARE": "CELL:600839:FY2019:WHITE_GOODS_REVENUE_SHARE",
    "GROUP_OCF_LEVEL": "CELL:600839:FY2019:GROUP_OCF_LEVEL",
    "GROUP_OCF_TO_CAPEX": "CELL:600839:FY2019:GROUP_OCF_TO_CAPEX",
    "GROUP_ASSET_LIABILITY_RATIO": "CELL:600839:FY2019:GROUP_ASSET_LIABILITY_RATIO",
    "WHITE_GOODS_ACTION_EVENT": "CELL:600839:FY2019:WHITE_GOODS_ACTION_EVENT",
    "PORTFOLIO_SCOPE_EVENT": "CELL:600839:FY2019:PORTFOLIO_SCOPE_EVENT",
    "OWNER_CASH_BRIDGE_EVENT": "CELL:600839:FY2019:OWNER_CASH_BRIDGE_EVENT",
}

CELL_DIMENSIONS = {
    CELL["INDUSTRY_CONTEXT_EVENT"]: "COMPETITION",
    CELL["GROUP_REVENUE_LEVEL"]: "OPERATIONS",
    CELL["WHITE_GOODS_REVENUE_LEVEL"]: "CUSTOMER",
    CELL["WHITE_GOODS_GROSS_MARGIN"]: "OPERATIONS",
    CELL["WHITE_GOODS_REVENUE_SHARE"]: "COMPETITION",
    CELL["GROUP_OCF_LEVEL"]: "CASH",
    CELL["GROUP_OCF_TO_CAPEX"]: "CAPITAL_RETURN",
    CELL["GROUP_ASSET_LIABILITY_RATIO"]: "LEVERAGE",
    CELL["WHITE_GOODS_ACTION_EVENT"]: "OPERATIONS",
    CELL["PORTFOLIO_SCOPE_EVENT"]: "PERMANENT_LOSS",
    CELL["OWNER_CASH_BRIDGE_EVENT"]: "CAPITAL_RETURN",
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

DEPENDENCIES = {
    "INITIAL_CONDITIONS": [CELL["INDUSTRY_CONTEXT_EVENT"], CELL["WHITE_GOODS_REVENUE_SHARE"]],
    "IMPLEMENTED_MANAGEMENT_ACTION": [CELL["WHITE_GOODS_ACTION_EVENT"]],
    "EXECUTION": [
        CELL["WHITE_GOODS_ACTION_EVENT"],
        CELL["WHITE_GOODS_REVENUE_LEVEL"],
        CELL["WHITE_GOODS_GROSS_MARGIN"],
    ],
    "CUSTOMER_COMPETITION_RESPONSE": [
        CELL["WHITE_GOODS_REVENUE_LEVEL"],
        CELL["WHITE_GOODS_REVENUE_SHARE"],
    ],
    "UNIT_ECONOMICS": [CELL["WHITE_GOODS_GROSS_MARGIN"]],
    "WORKING_CAPITAL_CASH_CAPITAL": [
        CELL["GROUP_OCF_LEVEL"],
        CELL["GROUP_OCF_TO_CAPEX"],
        CELL["OWNER_CASH_BRIDGE_EVENT"],
    ],
    "ADAPTATION_PERMANENT_LOSS": [
        CELL["GROUP_ASSET_LIABILITY_RATIO"],
        CELL["PORTFOLIO_SCOPE_EVENT"],
        CELL["OWNER_CASH_BRIDGE_EVENT"],
    ],
    "STRONGEST_ALTERNATIVE_EXPLANATION": [
        CELL["GROUP_REVENUE_LEVEL"],
        CELL["WHITE_GOODS_REVENUE_LEVEL"],
        CELL["WHITE_GOODS_REVENUE_SHARE"],
        CELL["PORTFOLIO_SCOPE_EVENT"],
    ],
}

ENHANCED_LOCATORS = {
    "INITIAL_CONDITIONS": [LOCATOR["INITIAL"], LOCATOR["SYSTEM"]],
    "IMPLEMENTED_MANAGEMENT_ACTION": [LOCATOR["ACTION"]],
    "EXECUTION": [LOCATOR["ACTION"], LOCATOR["PRODUCT"]],
    "CUSTOMER_COMPETITION_RESPONSE": [LOCATOR["INITIAL"], LOCATOR["ACTION"]],
    "UNIT_ECONOMICS": [LOCATOR["PRODUCT"]],
    "WORKING_CAPITAL_CASH_CAPITAL": [LOCATOR["SYSTEM"], LOCATOR["CASH"]],
    "ADAPTATION_PERMANENT_LOSS": [LOCATOR["INITIAL"], LOCATOR["CASH"]],
    "STRONGEST_ALTERNATIVE_EXPLANATION": [
        LOCATOR["INITIAL"], LOCATOR["SYSTEM"], LOCATOR["PRODUCT"], LOCATOR["CASH"],
    ],
}

ENHANCED_STATEMENTS = {
    "INITIAL_CONDITIONS": (
        "The listed issuer entered the cutoff as a television, white-goods, IT, intermediate-product "
        "and other-business portfolio; white goods competed in category-specific arenas rather than as "
        "a homogeneous group business."
    ),
    "IMPLEMENTED_MANAGEMENT_ACTION": (
        "FY2017 evidence records product launches, product-mix work, channel adjustment and organization "
        "changes, but implementation is not evidence of customer acceptance or economic effect."
    ),
    "EXECUTION": (
        "White-goods execution requires post-cutoff product-arena revenue and gross-margin coherence; "
        "consolidated issuer growth cannot substitute for those observations."
    ),
    "CUSTOMER_COMPETITION_RESPONSE": (
        "Air-conditioner and refrigerator revenue can show product-arena absorption, but without volume, "
        "price and share separation it cannot establish preference or competitive advantage."
    ),
    "UNIT_ECONOMICS": (
        "The air-conditioner and refrigerator gross margin is the product-arena economic observation; "
        "television, IT and intermediate-product margin cannot replace it."
    ),
    "WORKING_CAPITAL_CASH_CAPITAL": (
        "Consolidated operating cash and cash capex describe issuer funding only; ordinary-share owner cash "
        "requires a separate bridge through required capital and priority claims."
    ),
    "ADAPTATION_PERMANENT_LOSS": (
        "Leverage, portfolio changes and owner-cash access must be reviewed separately before concluding "
        "that product growth reduced permanent-loss risk."
    ),
    "STRONGEST_ALTERNATIVE_EXPLANATION": (
        "Category cycle, product mix, television/IT/intermediate-product performance and portfolio changes "
        "can reproduce consolidated improvement without better white-goods execution."
    ),
}


def _claim_id(role: str, dimension: str) -> str:
    return f"CLAIM:R9:{role}:{dimension}"


def _scope() -> dict[str, list[str]]:
    return {
        "issuer_ids": [ISSUER_ID],
        "product_or_service_ids": ["PRODUCT_SYSTEM:CN:600839:WHITE_GOODS"],
        "plant_ids": ["PLANT_SYSTEM:CN:600839:MULTI_SITE_MANUFACTURING"],
        "channel_ids": ["CHANNEL_SYSTEM:CN:600839:MULTI_CHANNEL"],
        "region_ids": ["REGION:CN:NATIONAL_WITH_EXPORT_CONTEXT"],
        "arena_ids": [
            "ARENA:CN:APPLIANCE:ROOM_AIR_CONDITIONING",
            "ARENA:CN:APPLIANCE:REFRIGERATION_AND_WASHING",
            "ARENA:CN:CONSUMER_ELECTRONICS:MULTI_PRODUCT_PORTFOLIO",
        ],
    }


def build_source_packets() -> list[dict[str, Any]]:
    baseline_claims = [
        _claim_id("BASELINE", "EXECUTION"),
        _claim_id("BASELINE", "WORKING_CAPITAL_CASH_CAPITAL"),
        _claim_id("BASELINE", "ADAPTATION_PERMANENT_LOSS"),
    ]
    locator_specs = [
        (
            "FIELD:600839:FY2017:INITIAL_CONDITIONS",
            LOCATOR["INITIAL"],
            10,
            "PDF p.10: white-goods arena structure, category leaders, company gaps and compressor cycle.",
            [
                _claim_id("ENHANCED", "INITIAL_CONDITIONS"),
                _claim_id("ENHANCED", "CUSTOMER_COMPETITION_RESPONSE"),
                _claim_id("ENHANCED", "ADAPTATION_PERMANENT_LOSS"),
                _claim_id("ENHANCED", "STRONGEST_ALTERNATIVE_EXPLANATION"),
            ],
        ),
        (
            "FIELD:600839:FY2017:IMPLEMENTED_ACTIONS",
            LOCATOR["ACTION"],
            12,
            "PDF p.12: white-goods product launches, mix, channel work and implemented company actions.",
            [
                _claim_id("ENHANCED", "IMPLEMENTED_MANAGEMENT_ACTION"),
                _claim_id("ENHANCED", "EXECUTION"),
                _claim_id("ENHANCED", "CUSTOMER_COMPETITION_RESPONSE"),
            ],
        ),
        (
            "FIELD:600839:FY2017:MULTI_PRODUCT_SYSTEM",
            LOCATOR["SYSTEM"],
            13,
            "PDF p.13: organization changes, group revenue/cost/cash and the multi-business issuer system.",
            [
                _claim_id("ENHANCED", "INITIAL_CONDITIONS"),
                _claim_id("ENHANCED", "WORKING_CAPITAL_CASH_CAPITAL"),
                _claim_id("ENHANCED", "STRONGEST_ALTERNATIVE_EXPLANATION"),
            ],
        ),
        (
            "FIELD:600839:FY2017:WHITE_GOODS_ECONOMICS",
            LOCATOR["PRODUCT"],
            14,
            "PDF p.14: air-conditioner and refrigerator revenue, cost, gross margin and group product mix.",
            [
                _claim_id("ENHANCED", "EXECUTION"),
                _claim_id("ENHANCED", "UNIT_ECONOMICS"),
                _claim_id("ENHANCED", "STRONGEST_ALTERNATIVE_EXPLANATION"),
            ],
        ),
        (
            "FIELD:600839:FY2017:GROUP_CASH_PORTFOLIO",
            LOCATOR["CASH"],
            18,
            "PDF p.18: consolidated cash flows and non-core disposal gain; no ordinary-share owner-cash bridge.",
            [
                _claim_id("ENHANCED", "WORKING_CAPITAL_CASH_CAPITAL"),
                _claim_id("ENHANCED", "ADAPTATION_PERMANENT_LOSS"),
                _claim_id("ENHANCED", "STRONGEST_ALTERNATIVE_EXPLANATION"),
            ],
        ),
    ]
    fields = []
    locators = []
    for field_id, locator_id, page, locator_text, enhanced_claim_ids in locator_specs:
        field_ref = source_packet_module.build_field_ref(PACKET_ID, SOURCE_ID, field_id)
        fields.append({
            "field_id": field_id,
            "field_ref": field_ref,
            "source_id": SOURCE_ID,
            "status": "LOCATED",
            "material_claim_ids": [*baseline_claims, *enhanced_claim_ids],
            "locator_ids": [locator_id],
        })
        locators.append({
            "locator_id": locator_id,
            "field_id": field_id,
            "field_ref": field_ref,
            "research_question_id": "Q:R9:CHANGHONG:WHITE_GOODS_BOUNDARY",
            "locator": locator_text,
            "page_number": page,
        })
    return [{
        "schema_version": source_packet_module.SCHEMA_VERSION,
        "packet_id": PACKET_ID,
        "packet_version": 1,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "fields": fields,
        "sources": [{
            "source_id": SOURCE_ID,
            "source_type": "OFFICIAL_ANNUAL_REPORT_STATIC_PDF",
            "official_url": SOURCE_URL,
            "published_on": "2018-04-18",
            "available_on": "2018-04-18",
            "availability_timezone": "Asia/Shanghai",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": [
                "INDUSTRY_CONTEXT:CN:WHITE_GOODS",
                "ISSUER_CONSOLIDATED:CN:600839",
                "PRODUCT_ARENA:CN:600839:WHITE_GOODS",
                "ORDINARY_SHARE_CASH:CN:600839",
            ],
            "responsibility_perimeter_id": "PERIMETER:CN:600839:FY2017:LISTED_CONSOLIDATED",
            "unit": "MIXED_DECLARED_FIELDS",
            "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": locators,
            "boundary_note": (
                "Product rows support white-goods observations; group cash and portfolio rows remain "
                "listed-issuer evidence and do not establish ordinary-share owner cash."
            ),
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": list(source_packet_module.ALLOWED_OUTPUTS),
    }]


def build_industry_block() -> dict[str, Any]:
    return {
        "schema_version": multidimensional.BLOCK_SCHEMA_VERSION,
        "block_id": BLOCK_ID,
        "industry_id": "INDUSTRY:CN:APPLIANCE:MULTI_CATEGORY",
        "cutoff_at": CUTOFF_AT,
        "observation_window": {
            "event_start": "2019-01-01",
            "event_end": "2019-12-31",
            "accounting_period": "FY2019",
            "settlement_source_type": "OFFICIAL_ANNUAL_REPORT_STATIC_PDF",
            "boundary_note": (
                "Every FY2019 flow and event is after the 2018-09-30 cutoff. Product-arena, issuer, "
                "industry-context and ordinary-share-cash boundaries remain typed separately."
            ),
        },
        "industry_epoch": {
            "epoch_id": "EPOCH:CN:APPLIANCE:FY2017_DISCLOSURE:C2",
            "condition": (
                "Domestic white goods were entering slower category growth and stronger concentration, "
                "while portfolio companies combined product upgrades, channel work and other businesses."
            ),
            "observed_industry_volume": "UNKNOWN_AT_FROZEN_PRODUCT_BOUNDARY",
            "observed_industry_revenue": "UNKNOWN_AT_FROZEN_PRODUCT_BOUNDARY",
            "observed_concentration": "Category leaders were disclosed, but no same-boundary concentration series was frozen.",
            "evidence_refs": [LOCATOR["INITIAL"]],
            "causal_credit": "NONE",
        },
        "mechanism_arenas": [
            {
                "arena_id": "ARENA:CN:APPLIANCE:ROOM_AIR_CONDITIONING",
                "mechanism": "Product, channel, price and installation capacity convert seasonal demand into air-conditioner sales and margin.",
                "economic_scope": "NATIONAL_CATEGORY_WITH_REGIONAL_AND_CHANNEL_VARIATION",
                "value_driver": "Product mix, sell-through, channel efficiency and unit margin.",
                "failure_mode": "A hot season or low price can lift revenue without durable execution quality.",
            },
            {
                "arena_id": "ARENA:CN:APPLIANCE:REFRIGERATION_AND_WASHING",
                "mechanism": "Product freshness, efficiency, brand and channel economics shape replacement demand and margin.",
                "economic_scope": "NATIONAL_REPLACEMENT_CATEGORY_WITH_EXPORT_CONTEXT",
                "value_driver": "Volume, price-mix, brand investment, unit cost and working capital.",
                "failure_mode": "Mix or acquisition can move reported revenue without organic customer preference.",
            },
            {
                "arena_id": "ARENA:CN:CONSUMER_ELECTRONICS:MULTI_PRODUCT_PORTFOLIO",
                "mechanism": "Television, IT, intermediate products and portfolio actions alter consolidated revenue, margin and cash independently of white goods.",
                "economic_scope": "LISTED_CONSOLIDATED_MULTI_BUSINESS_ISSUER",
                "value_driver": "Business mix, perimeter, non-operating gains and capital allocation.",
                "failure_mode": "Group improvement can be mistaken for white-goods operating quality.",
            },
        ],
        "members": [{
            "rank": 1,
            "company_id": COMPANY_ID,
            "issuer_id": ISSUER_ID,
            "company_name": "Sichuan Changhong Electric Co., Ltd.",
            "source_packet_ref": {"receipt_id": PACKET_ID, "receipt_version": 1},
            "packet_state": multidimensional.ELIGIBLE_PACKET_STATE,
            "archetype": "MULTI_PRODUCT_APPLIANCE_AND_CONSUMER_ELECTRONICS_PORTFOLIO",
            "responsibility_boundary": "LISTED_CONSOLIDATED_ISSUER_WITH_SEPARATE_WHITE_GOODS_ARENA",
            "arena_ids": [
                "ARENA:CN:APPLIANCE:ROOM_AIR_CONDITIONING",
                "ARENA:CN:APPLIANCE:REFRIGERATION_AND_WASHING",
                "ARENA:CN:CONSUMER_ELECTRONICS:MULTI_PRODUCT_PORTFOLIO",
            ],
            "cutoff_state": (
                "FY2017 air-conditioner and refrigerator revenue grew rapidly while product gross margin "
                "fell; group operating cash declined and the issuer retained television, IT, intermediate "
                "products and portfolio effects."
            ),
            "decision_heterogeneity": (
                "Management combined product launches, channel adjustment and organization reform inside "
                "a broader multi-business group, making boundary discipline the primary question."
            ),
            "evidence_refs": list(LOCATOR.values()),
        }],
        "selection_policy": {
            "policy_id": "SEL:CN:APPLIANCE:CHANGHONG:ROUND9:V1",
            "rule": multidimensional.SELECTION_POLICY,
            "eligible_packet_state": multidimensional.ELIGIBLE_PACKET_STATE,
            "tie_breaker": "LOWEST_ISSUER_ID",
            "prohibited_inputs": [
                "POST_CUTOFF_OUTCOME",
                "OUTCOME_SOURCE_CONVENIENCE",
                "PRICE_OR_RETURN",
                "EXPECTED_METHOD_WINNER",
            ],
        },
        "strongest_common_rivals": [
            "Television, IT and intermediate-product performance can dominate consolidated movement.",
            "Category cycle and product mix can lift white-goods revenue without better customer preference.",
            "Portfolio disposals or acquisitions can alter group profit and cash without operating improvement.",
        ],
        "unresolved_questions": [
            "Did white-goods revenue and gross margin move coherently after the cutoff?",
            "Did disclosed product and channel work translate into execution rather than deployment?",
            "Did consolidated cash fund required capital, and was any residual accessible to ordinary shares?",
            "Did portfolio scope or leverage change the permanent-loss path?",
        ],
        "outcome_access_status": "SEALED",
        "roles": {
            "judgment_owner_id": "ROLE:ROUND9:APPLIANCE:JUDGMENT_OWNER",
            "independent_challenger_id": "ROLE:ROUND9:APPLIANCE:INDEPENDENT_CHALLENGER",
            "outcome_custodian_id": "ROLE:ROUND9:APPLIANCE:OUTCOME_CUSTODIAN",
        },
        "object_class": "INDUSTRY_LEARNING_BLOCK",
        "claim_class": "CONDITIONAL_INDUSTRY_CONTEXT_AND_SAMPLING",
        "allowed_outputs": list(multidimensional.BLOCK_OUTPUTS),
    }


def build_selection(block: dict[str, Any], packets: list[dict[str, Any]]) -> dict[str, Any]:
    result = multidimensional.derive_selection(block, source_packets=packets)
    if not result["valid"]:
        raise ValueError("round9 mechanical selection invalid: " + "; ".join(result["findings"]))
    return result["selection"]


def build_decision_contract(block: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "turtle-training-decision-contract.v1",
        "contract_id": "DC:CN600839:20180930:ROUND9:V1",
        "contract_version": 1,
        "company_id": selection["company_id"],
        "issuer_id": selection["issuer_id"],
        "cutoff_at": selection["cutoff_at"],
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [
            {
                "constraint_id": "PLC:R9:PRODUCT_GROUP_BOUNDARY",
                "condition": "Consolidated performance is promoted to a white-goods operating conclusion.",
                "required_treatment": "Require product-arena evidence or retain the white-goods conclusion as UNKNOWN.",
            },
            {
                "constraint_id": "PLC:R9:OWNER_CASH",
                "condition": "Consolidated operating cash is promoted to ordinary-share owner cash.",
                "required_treatment": "Require an explicit bridge through required capital and priority claims or retain UNKNOWN.",
            },
        ],
        "decision_flip_questions": [
            {
                "question_id": "DQ:R9:GROUP_OR_WHITE_GOODS",
                "statement": "Do product-arena revenue and gross margin support the same direction as consolidated trends?",
                "decision_effect": "A divergence invalidates a broad issuer-to-white-goods proxy conclusion.",
            },
            {
                "question_id": "DQ:R9:CUSTOMER_OR_MIX",
                "statement": "Can volume, price, share or customer evidence distinguish preference from category cycle and mix?",
                "decision_effect": "Without that separation, customer advantage remains UNKNOWN.",
            },
            {
                "question_id": "DQ:R9:CASH_ACCESS",
                "statement": "Does issuer cash survive required capital and priority claims for ordinary shareholders?",
                "decision_effect": "Without a bridge, issuer funding cannot become owner cash.",
            },
        ],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:CN600839:20180930:FY2017",
            "source_packet_refs": [deepcopy(selection["source_packet_ref"])],
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": deepcopy(block["roles"]),
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    }


def _flow_clock() -> dict[str, Any]:
    return {
        "clock_kind": "FLOW_PERIOD",
        "flow_period": {
            "period_start": "2019-01-01",
            "period_end": "2019-12-31",
            "fiscal_period": "FY2019",
        },
    }


def _balance_clock() -> dict[str, Any]:
    return {
        "clock_kind": "BALANCE_AS_OF",
        "balance_as_of": {"as_of": "2019-12-31", "fiscal_period": "FY2019"},
    }


def _event_clock() -> dict[str, Any]:
    return {
        "clock_kind": "EVENT_WINDOW",
        "event_window": {
            "event_start": "2019-01-01",
            "event_end": "2019-12-31",
            "window_name": "FY2019_STRICT_POST_CUTOFF_EVENT_WINDOW",
        },
    }


def _outcome_period() -> dict[str, str]:
    return {
        "period_start": "2019-01-01T00:00:00+08:00",
        "period_end": "2019-12-31T23:59:59+08:00",
        "fiscal_period": "FY2019_STRICT_POST_CUTOFF",
    }


def _boundary(kind: str) -> dict[str, str]:
    boundaries = {
        "INDUSTRY": {
            "responsibility_unit_id": "INDUSTRY_CONTEXT:CN:WHITE_GOODS",
            "perimeter_id": "PERIMETER:CN:WHITE_GOODS:FY2019_CONTEXT",
            "arena_id": "ARENA:CN:APPLIANCE:WHITE_GOODS",
            "scope_requirement": "Industry context only; issuer filing cannot receive industry or issuer causal credit.",
        },
        "ISSUER": {
            "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:600839",
            "perimeter_id": "PERIMETER:CN:600839:FY2019:LISTED_CONSOLIDATED",
            "arena_id": "ARENA:CN:CONSUMER_ELECTRONICS:MULTI_PRODUCT_PORTFOLIO",
            "scope_requirement": "Listed-consolidated issuer; no product-arena or ordinary-share promotion.",
        },
        "PRODUCT": {
            "responsibility_unit_id": "PRODUCT_ARENA:CN:600839:WHITE_GOODS",
            "perimeter_id": "PERIMETER:CN:600839:FY2019:AIR_CONDITIONER_AND_REFRIGERATOR",
            "arena_id": "ARENA:CN:APPLIANCE:WHITE_GOODS",
            "scope_requirement": "Air-conditioner and refrigerator product arena only; exact same product row required.",
        },
        "ORDINARY_SHARE": {
            "responsibility_unit_id": "ORDINARY_SHARE_CASH:CN:600839",
            "perimeter_id": "PERIMETER:CN:600839:FY2019:ORDINARY_COMMON_CASH_ACCESS",
            "arena_id": "ARENA:CN:600839:ORDINARY_SHARE_CLAIM",
            "scope_requirement": "Residual ordinary-share cash after required capital and priority claims; group OCF is insufficient.",
        },
    }
    return deepcopy(boundaries[kind])


def _raw(field_id: str, unit: str, clock: dict[str, Any], table: str, line: str) -> dict[str, Any]:
    clock_value = clock.get("event_window") or clock.get("flow_period") or clock.get("balance_as_of") or {}
    period_column = (
        f"{clock_value.get('event_start')}..{clock_value.get('event_end')}"
        if clock.get("clock_kind") == "EVENT_WINDOW"
        else str(clock_value.get("fiscal_period"))
    )
    return {
        "field_id": field_id,
        "role": "EVENT" if clock.get("clock_kind") == "EVENT_WINDOW" else "OUTCOME",
        "unit": unit,
        "measurement_clock": deepcopy(clock),
        "locator": {"table_or_note": table, "line_item": line, "period_column": period_column},
    }


def _numeric_cell(
    *, name: str, thread_id: str, layer: str, unit: str, unit_kind: str,
    clock: dict[str, Any], table: str, line: str, decrease_lte: float,
    increase_gte: float, boundary_kind: str, prohibited: str,
) -> dict[str, Any]:
    raw = _raw(f"FIELD:600839:FY2019:{name}", unit, clock, table, line)
    return {
        "cell_id": CELL[name],
        "thread_id": thread_id,
        "layer": layer,
        "outcome_period": _outcome_period(),
        "measurement_clock": deepcopy(clock),
        "responsibility_boundary": _boundary(boundary_kind),
        "field_identity": {
            "outcome_field_id": raw["field_id"],
            "baseline_field_id": "",
            "statement_scope": "FY2019_STRICT_POST_CUTOFF",
            "table_or_note": table,
            "line_item": line,
            "field_kind": "AUDITED_OR_RECOMPUTABLE_ANNUAL_REPORT_LINE_ITEM",
        },
        "unit": {
            "kind": unit_kind,
            "currency": "RMB" if unit == "RMB" else "NOT_APPLICABLE",
            "scale": "1",
        },
        "raw_input_fields": [raw],
        "formula": {
            "operator": "RAW_VALUE",
            "input_field_ids": [raw["field_id"]],
            "expression": raw["field_id"],
            "unit_conversions": [{
                "field_id": raw["field_id"], "from_unit": unit, "to_unit": unit, "scale": "1",
            }],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        "label_rule": {
            "type": "ABSOLUTE_CHANGE_BAND",
            "decrease_lte": decrease_lte,
            "increase_gte": increase_gte,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE",
                "OBSERVED_INCREASE", "UNKNOWN",
            ],
        },
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {"conditions": ["contracted FY2019 field absent"], "label": "UNKNOWN"},
        "mismatch_rule": {
            "conditions": ["scope, period, unit, row identity or unique-field conflict"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def _event_cell(
    *, name: str, thread_id: str, layer: str, table: str, line: str,
    boundary_kind: str, prohibited: str,
) -> dict[str, Any]:
    clock = _event_clock()
    raw = _raw(f"FIELD:600839:FY2019:{name}", "BOOLEAN_EVENT", clock, table, line)
    return {
        "cell_id": CELL[name],
        "thread_id": thread_id,
        "layer": layer,
        "outcome_period": _outcome_period(),
        "measurement_clock": clock,
        "responsibility_boundary": _boundary(boundary_kind),
        "field_identity": {
            "outcome_field_id": raw["field_id"],
            "baseline_field_id": "",
            "statement_scope": "FY2019_STRICT_POST_CUTOFF",
            "table_or_note": table,
            "line_item": line,
            "field_kind": "DISCLOSED_EVENT",
        },
        "unit": {"kind": "EVENT", "currency": "NOT_APPLICABLE", "scale": "BOOLEAN"},
        "raw_input_fields": [raw],
        "formula": {
            "operator": "EVENT_BOOLEAN",
            "input_field_ids": [raw["field_id"]],
            "expression": f"explicit_fy2019_event({raw['field_id']})",
            "unit_conversions": [{
                "field_id": raw["field_id"], "from_unit": "BOOLEAN_EVENT",
                "to_unit": "BOOLEAN_EVENT", "scale": "1",
            }],
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
        "unknown_rule": {"conditions": ["no explicit positive or negative FY2019 evidence"], "label": "UNKNOWN"},
        "mismatch_rule": {
            "conditions": ["event period, responsibility or implementation identity conflict"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def build_measurement_contract() -> dict[str, Any]:
    flow, balance = _flow_clock(), _balance_clock()
    cells = [
        _event_cell(
            name="INDUSTRY_CONTEXT_EVENT", thread_id="THREAD:R9:INDUSTRY_AND_RIVAL", layer="SALES_VOLUME",
            table="FY2019 industry and competition review",
            line="explicit FY2019 white-goods category demand, concentration, price or competition condition",
            boundary_kind="INDUSTRY",
            prohibited="Issuer annual-report industry context is descriptive and cannot prove issuer execution or customer preference.",
        ),
        _numeric_cell(
            name="GROUP_REVENUE_LEVEL", thread_id="THREAD:R9:SIMPLE_ISSUER_TREND", layer="SALES_VOLUME",
            unit="RMB", unit_kind="VALUE", clock=flow, table="consolidated income statement",
            line="operating revenue; compare mechanically with frozen FY2017 RMB77,632,476,743.23 anchor",
            decrease_lte=73_750_852_906.07, increase_gte=81_514_100_580.39, boundary_kind="ISSUER",
            prohibited="Consolidated revenue is not white-goods revenue, execution, customer preference or owner cash.",
        ),
        _numeric_cell(
            name="WHITE_GOODS_REVENUE_LEVEL", thread_id="THREAD:R9:WHITE_GOODS_EXECUTION", layer="SALES_VOLUME",
            unit="RMB", unit_kind="VALUE", clock=flow, table="principal business by product",
            line="air-conditioner and refrigerator revenue; exact same product row as FY2017 required",
            decrease_lte=13_623_191_090.94, increase_gte=15_057_211_205.78, boundary_kind="PRODUCT",
            prohibited="Product revenue does not distinguish volume, price, category cycle or organic scope.",
        ),
        _numeric_cell(
            name="WHITE_GOODS_GROSS_MARGIN", thread_id="THREAD:R9:WHITE_GOODS_EXECUTION", layer="GROSS_MARGIN",
            unit="RATIO", unit_kind="RATIO", clock=flow, table="principal business by product",
            line="(air-conditioner and refrigerator revenue minus cost) divided by revenue; exact row tokens required",
            decrease_lte=0.1969, increase_gte=0.2369, boundary_kind="PRODUCT",
            prohibited="Gross-margin movement does not identify price, mix, cost driver or management causality.",
        ),
        _numeric_cell(
            name="WHITE_GOODS_REVENUE_SHARE", thread_id="THREAD:R9:INDUSTRY_AND_RIVAL", layer="SALES_VOLUME",
            unit="RATIO", unit_kind="RATIO", clock=flow, table="principal business by product and consolidated income statement",
            line="air-conditioner and refrigerator revenue divided by consolidated operating revenue",
            decrease_lte=0.1747, increase_gte=0.1947, boundary_kind="ISSUER",
            prohibited="Revenue share is a portfolio-boundary diagnostic, not competitive share or customer preference.",
        ),
        _numeric_cell(
            name="GROUP_OCF_LEVEL", thread_id="THREAD:R9:CASH_CAPITAL", layer="CASH",
            unit="RMB", unit_kind="VALUE", clock=flow, table="consolidated cash-flow statement",
            line="net cash flows from operating activities; compare mechanically with frozen FY2017 RMB1,456,160,300.99 anchor",
            decrease_lte=1_310_544_270.89, increase_gte=1_601_776_331.09, boundary_kind="ISSUER",
            prohibited="Consolidated operating cash is not white-goods cash or ordinary-share owner cash.",
        ),
        _numeric_cell(
            name="GROUP_OCF_TO_CAPEX", thread_id="THREAD:R9:CASH_CAPITAL", layer="CAPITAL_BURDEN",
            unit="RATIO", unit_kind="RATIO", clock=flow, table="consolidated cash-flow statement",
            line="net operating cash divided by cash paid to acquire and construct long-lived assets",
            decrease_lte=1.0, increase_gte=1.5, boundary_kind="ISSUER",
            prohibited="OCF-to-capex does not separate maintenance, growth, acquisitions, subsidiaries or ordinary-share access.",
        ),
        _numeric_cell(
            name="GROUP_ASSET_LIABILITY_RATIO", thread_id="THREAD:R9:CASH_CAPITAL", layer="FINANCING",
            unit="RATIO", unit_kind="RATIO", clock=balance, table="consolidated balance sheet",
            line="total liabilities divided by total assets at 2019-12-31",
            decrease_lte=0.65, increase_gte=0.75, boundary_kind="ISSUER",
            prohibited="A leverage ratio alone does not establish refinancing risk, ordinary-share loss or product economics.",
        ),
        _event_cell(
            name="WHITE_GOODS_ACTION_EVENT", thread_id="THREAD:R9:WHITE_GOODS_EXECUTION", layer="IMPLEMENTED",
            table="FY2019 management discussion",
            line="explicit FY2019 implemented air-conditioner or refrigerator product, channel or organization action",
            boundary_kind="PRODUCT",
            prohibited="Implementation does not prove customer response, margin effect or durable advantage.",
        ),
        _event_cell(
            name="PORTFOLIO_SCOPE_EVENT", thread_id="THREAD:R9:INDUSTRY_AND_RIVAL", layer="PERMANENT_LOSS",
            table="FY2019 scope, acquisition, disposal and non-operating review",
            line="explicit FY2019 acquisition, disposal or reorganization materially affecting consolidated or white-goods scope",
            boundary_kind="ISSUER",
            prohibited="A scope event is an alternative explanation, not evidence of better or worse operating execution by itself.",
        ),
        _event_cell(
            name="OWNER_CASH_BRIDGE_EVENT", thread_id="THREAD:R9:CASH_CAPITAL", layer="CAPITAL_BURDEN",
            table="FY2019 cash, capital and ordinary-share distribution review",
            line="explicit bridge from consolidated OCF through required capital and priority claims to residual ordinary-share cash",
            boundary_kind="ORDINARY_SHARE",
            prohibited="A dividend, OCF or cash balance alone is not the contracted ordinary-share owner-cash bridge.",
        ),
    ]
    return {
        "schema_version": "enterprise-outcome-measurement-contract.v3",
        "contract_set_id": MEASUREMENT_CONTRACT_ID,
        "package_ref": PACKAGE_ID,
        "company_id": COMPANY_ID,
        "cutoff_at": CUTOFF_AT,
        "outcome_window": {
            "period_start": "2019-01-01T00:00:00+08:00",
            "period_end": "2019-12-31T23:59:59+08:00",
            "fiscal_period": "FY2019_STRICT_POST_CUTOFF",
            "settlement_due_at": "2020-06-30T23:59:59+08:00",
        },
        "source_access": {
            "source_id": UNRESOLVED_SOURCE_ID,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": UNRESOLVED_SOURCE_URL,
            "published_after_cutoff": True,
            "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
            "custodian_access": "OUTCOME_ONLY",
            "issuer_id": ISSUER_ID,
            "report_period_end": "2019-12-31",
            "availability_precision": "DATE_ONLY",
            "source_available_at": None,
            "source_available_date": None,
            "authorization_receipt_id": "OUTCOME-AUTH:R9:CN600839:FY2019:V1",
        },
        "atomic_cells": cells,
        "thread_combination_rules": [
            {
                "rule_id": "RULE:R9:WHITE_GOODS_EXECUTION",
                "thread_id": "THREAD:R9:WHITE_GOODS_EXECUTION",
                "input_cell_ids": [
                    CELL["WHITE_GOODS_ACTION_EVENT"], CELL["WHITE_GOODS_REVENUE_LEVEL"],
                    CELL["WHITE_GOODS_GROSS_MARGIN"],
                ],
                "evaluation_order": [
                    CELL["WHITE_GOODS_ACTION_EVENT"], CELL["WHITE_GOODS_REVENUE_LEVEL"],
                    CELL["WHITE_GOODS_GROSS_MARGIN"],
                ],
                "rule": "Keep implementation, product absorption and unit economics separate; no cell compensates for another.",
                "conflict_rule": "Missing or mismatched product evidence limits only product-dependent conclusions.",
                "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
            },
            {
                "rule_id": "RULE:R9:CASH_AND_ACCESS",
                "thread_id": "THREAD:R9:CASH_CAPITAL",
                "input_cell_ids": [
                    CELL["GROUP_OCF_LEVEL"], CELL["GROUP_OCF_TO_CAPEX"],
                    CELL["GROUP_ASSET_LIABILITY_RATIO"], CELL["OWNER_CASH_BRIDGE_EVENT"],
                ],
                "evaluation_order": [
                    CELL["GROUP_OCF_LEVEL"], CELL["GROUP_OCF_TO_CAPEX"],
                    CELL["GROUP_ASSET_LIABILITY_RATIO"], CELL["OWNER_CASH_BRIDGE_EVENT"],
                ],
                "rule": "Assess issuer funding before ordinary-share access; no inferred bridge is permitted.",
                "conflict_rule": "Absent owner-cash bridge preserves UNKNOWN without invalidating issuer cash cells.",
                "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
            },
        ],
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "contract_frozen_at": FROZEN_AT,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
        "rights": {key: value for key, value in RIGHTS.items() if key != "method_transfer"},
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }


def _baseline_episode(contract: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    claims = []
    active_dimensions = {
        "EXECUTION": [LOCATOR["INITIAL"], LOCATOR["ACTION"], LOCATOR["SYSTEM"], LOCATOR["PRODUCT"]],
        "WORKING_CAPITAL_CASH_CAPITAL": [LOCATOR["SYSTEM"], LOCATOR["CASH"]],
        "ADAPTATION_PERMANENT_LOSS": [LOCATOR["INITIAL"], LOCATOR["CASH"]],
    }
    question_by_dimension = {
        "EXECUTION": "Q:R9:BASELINE:GROUP_REVENUE",
        "WORKING_CAPITAL_CASH_CAPITAL": "Q:R9:BASELINE:GROUP_CASH",
        "ADAPTATION_PERMANENT_LOSS": "Q:R9:BASELINE:GROUP_LEVERAGE",
    }
    for dimension in DIMENSIONS:
        active = dimension in active_dimensions
        claims.append({
            "claim_id": _claim_id("BASELINE", dimension),
            "question_id": question_by_dimension.get(dimension, "Q:R9:BASELINE:GROUP_REVENUE"),
            "method_id": BASELINE_METHOD_ID,
            "judgment_dimension": dimension,
            "claim_scope": _scope(),
            "domain": DOMAINS[dimension],
            "statement": (
                "Classify white-goods direction from product revenue and product gross margin, use consolidated "
                "cash and leverage only as a background guard, and abstain when group and product directions diverge."
                if active else "The simple product-trend baseline does not separately assess this dimension."
            ),
            "cell_status": "INFERRED" if active else "NOT_APPLICABLE",
            "admission_level": "E2_MECHANISM_PROBE" if active else "E0_CONTEXT",
            "evidence_refs": [PACKET_ID] if active else [],
            "evidence_locator_refs": deepcopy(active_dimensions.get(dimension, [])),
            "dependent_outcome_cell_ids": deepcopy(DEPENDENCIES[dimension]),
        })
    return _episode_root(
        role="BASELINE",
        contract=contract,
        block=block,
        question_set=[
            {
                "question_id": "Q:R9:BASELINE:GROUP_REVENUE",
                "role": "PRIMARY",
                "question": "Did white-goods revenue and gross margin move coherently without a group/product boundary divergence?",
                "claim_ids": [
                    _claim_id("BASELINE", dimension)
                    for dimension in DIMENSIONS
                    if dimension not in {"WORKING_CAPITAL_CASH_CAPITAL", "ADAPTATION_PERMANENT_LOSS"}
                ],
            },
            {
                "question_id": "Q:R9:BASELINE:GROUP_CASH",
                "role": "SUPPORTING",
                "question": "Did consolidated operating cash clear the frozen broad-progress threshold?",
                "claim_ids": [_claim_id("BASELINE", "WORKING_CAPITAL_CASH_CAPITAL")],
            },
            {
                "question_id": "Q:R9:BASELINE:GROUP_LEVERAGE",
                "role": "SUPPORTING",
                "question": "Did consolidated leverage stay within the frozen broad-progress threshold?",
                "claim_ids": [_claim_id("BASELINE", "ADAPTATION_PERMANENT_LOSS")],
            },
        ],
        claims=claims,
        threads=[
            {
                "thread_id": "THREAD:R9:SIMPLE_ISSUER_TREND",
                "role": "PRIMARY",
                "claim_ids": [_claim_id("BASELINE", "EXECUTION")],
                "hypotheses": [
                    {"hypothesis_id": "H-A:R9:BASELINE:REVENUE", "role": "H_A", "statement": "Coherent white-goods revenue and margin direction indicates a simple product operating trend."},
                    {"hypothesis_id": "H-B:R9:BASELINE:REVENUE", "role": "H_B", "statement": "A group/product direction divergence requires abstention because business mix can dominate the issuer trend."},
                ],
                "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF",
                "outcome_cell_ids": [
                    CELL["GROUP_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_LEVEL"],
                    CELL["WHITE_GOODS_GROSS_MARGIN"],
                ],
            },
            {
                "thread_id": "THREAD:R9:SIMPLE_GROUP_CASH",
                "role": "SUPPORTING",
                "claim_ids": [_claim_id("BASELINE", "WORKING_CAPITAL_CASH_CAPITAL")],
                "hypotheses": [
                    {"hypothesis_id": "H-A:R9:BASELINE:CASH", "role": "H_A", "statement": "Consolidated OCF growth supports broad issuer progress."},
                    {"hypothesis_id": "H-B:R9:BASELINE:CASH", "role": "H_B", "statement": "Working capital and portfolio mix can move OCF without better white-goods economics."},
                ],
                "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF",
                "outcome_cell_ids": [CELL["GROUP_OCF_LEVEL"]],
            },
            {
                "thread_id": "THREAD:R9:SIMPLE_GROUP_LEVERAGE",
                "role": "SUPPORTING",
                "claim_ids": [_claim_id("BASELINE", "ADAPTATION_PERMANENT_LOSS")],
                "hypotheses": [
                    {"hypothesis_id": "H-A:R9:BASELINE:LEVERAGE", "role": "H_A", "statement": "Stable or lower consolidated leverage is compatible with broad progress."},
                    {"hypothesis_id": "H-B:R9:BASELINE:LEVERAGE", "role": "H_B", "statement": "A group leverage ratio does not identify product economics or ordinary-share loss."},
                ],
                "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF",
                "outcome_cell_ids": [CELL["GROUP_ASSET_LIABILITY_RATIO"]],
            },
        ],
    )


def _enhanced_episode(contract: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    states = {
        "INITIAL_CONDITIONS": "OBSERVED",
        "IMPLEMENTED_MANAGEMENT_ACTION": "OBSERVED",
        "EXECUTION": "INFERRED",
        "CUSTOMER_COMPETITION_RESPONSE": "INFERRED",
        "UNIT_ECONOMICS": "OBSERVED",
        "WORKING_CAPITAL_CASH_CAPITAL": "OBSERVED",
        "ADAPTATION_PERMANENT_LOSS": "UNKNOWN",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "INFERRED",
    }
    levels = {
        "INITIAL_CONDITIONS": "E0_CONTEXT",
        "WORKING_CAPITAL_CASH_CAPITAL": "E1_RECONSTRUCTION",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "E1_RECONSTRUCTION",
    }
    questions = [
        ("Q:R9:ENHANCED:BOUNDARY", "SUPPORTING", "What initial portfolio boundary and rival explanations govern the white-goods question?", ["INITIAL_CONDITIONS", "STRONGEST_ALTERNATIVE_EXPLANATION"]),
        ("Q:R9:ENHANCED:ACTION_EXECUTION", "PRIMARY", "Did implemented product and channel work translate into coherent white-goods execution?", ["IMPLEMENTED_MANAGEMENT_ACTION", "EXECUTION"]),
        ("Q:R9:ENHANCED:CUSTOMER_ECONOMICS", "SUPPORTING", "Did product-arena absorption and gross margin support customer and unit-economic progress?", ["CUSTOMER_COMPETITION_RESPONSE", "UNIT_ECONOMICS"]),
        ("Q:R9:ENHANCED:CASH_LOSS", "SUPPORTING", "Could issuer funding and leverage support the business without assuming ordinary-share owner cash?", ["WORKING_CAPITAL_CASH_CAPITAL", "ADAPTATION_PERMANENT_LOSS"]),
    ]
    question_by_dimension = {
        dimension: question_id
        for question_id, _, _, dimensions in questions
        for dimension in dimensions
    }
    claims = [{
        "claim_id": _claim_id("ENHANCED", dimension),
        "question_id": question_by_dimension[dimension],
        "method_id": ENHANCED_METHOD_ID,
        "judgment_dimension": dimension,
        "claim_scope": _scope(),
        "domain": DOMAINS[dimension],
        "statement": ENHANCED_STATEMENTS[dimension],
        "cell_status": states[dimension],
        "admission_level": levels.get(dimension, "E2_MECHANISM_PROBE"),
        "evidence_refs": [] if states[dimension] == "UNKNOWN" else [PACKET_ID],
        "evidence_locator_refs": [] if states[dimension] == "UNKNOWN" else deepcopy(ENHANCED_LOCATORS[dimension]),
        "dependent_outcome_cell_ids": deepcopy(DEPENDENCIES[dimension]),
    } for dimension in DIMENSIONS]
    question_set = [{
        "question_id": question_id,
        "role": role,
        "question": question,
        "claim_ids": [_claim_id("ENHANCED", dimension) for dimension in dimensions],
    } for question_id, role, question, dimensions in questions]
    threads = [
        {
            "thread_id": "THREAD:R9:WHITE_GOODS_EXECUTION",
            "role": "PRIMARY",
            "claim_ids": [
                _claim_id("ENHANCED", "IMPLEMENTED_MANAGEMENT_ACTION"),
                _claim_id("ENHANCED", "EXECUTION"),
                _claim_id("ENHANCED", "UNIT_ECONOMICS"),
            ],
            "hypotheses": [
                {"hypothesis_id": "H-A:R9:WHITE_GOODS_EXECUTION", "role": "H_A", "statement": "Product and channel actions improve product-arena absorption and gross margin coherently."},
                {"hypothesis_id": "H-B:R9:WHITE_GOODS_EXECUTION", "role": "H_B", "statement": "Category cycle, price or mix changes revenue without better unit economics."},
            ],
            "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF_PRODUCT_ARENA",
            "outcome_cell_ids": [
                CELL["WHITE_GOODS_ACTION_EVENT"], CELL["WHITE_GOODS_REVENUE_LEVEL"],
                CELL["WHITE_GOODS_GROSS_MARGIN"],
            ],
        },
        {
            "thread_id": "THREAD:R9:CUSTOMER_RESPONSE",
            "role": "SUPPORTING",
            "claim_ids": [_claim_id("ENHANCED", "CUSTOMER_COMPETITION_RESPONSE")],
            "hypotheses": [
                {"hypothesis_id": "H-A:R9:CUSTOMER", "role": "H_A", "statement": "Product-arena absorption reflects stronger customer response."},
                {"hypothesis_id": "H-B:R9:CUSTOMER", "role": "H_B", "statement": "Volume, price, mix and category cycle remain unresolved drivers."},
            ],
            "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF_NO_CUSTOMER_CAUSAL_CREDIT",
            "outcome_cell_ids": [CELL["WHITE_GOODS_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_SHARE"]],
        },
        {
            "thread_id": "THREAD:R9:CASH_AND_LOSS",
            "role": "SUPPORTING",
            "claim_ids": [_claim_id("ENHANCED", "ADAPTATION_PERMANENT_LOSS")],
            "hypotheses": [
                {"hypothesis_id": "H-A:R9:CASH", "role": "H_A", "statement": "Issuer cash covers capital needs without weakening ordinary-share resilience."},
                {"hypothesis_id": "H-B:R9:CASH", "role": "H_B", "statement": "Leverage, portfolio scope and inaccessible subsidiary cash leave permanent-loss risk unresolved."},
            ],
            "observation_clock_ref": "FY2019_STRICT_POST_CUTOFF_TYPED_CASH_BOUNDARIES",
            "outcome_cell_ids": [
                CELL["GROUP_OCF_LEVEL"], CELL["GROUP_OCF_TO_CAPEX"],
                CELL["GROUP_ASSET_LIABILITY_RATIO"], CELL["PORTFOLIO_SCOPE_EVENT"],
                CELL["OWNER_CASH_BRIDGE_EVENT"],
            ],
        },
    ]
    return _episode_root(
        role="ENHANCED", contract=contract, block=block,
        question_set=question_set, claims=claims, threads=threads,
    )


def _episode_root(
    *, role: str, contract: dict[str, Any], block: dict[str, Any],
    question_set: list[dict[str, Any]], claims: list[dict[str, Any]],
    threads: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": episode_module.SCHEMA_VERSION,
        "episode_id": f"EJE:CN600839:20180930:{role}:R9:V1",
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "decision_contract_ref": {
            "contract_id": contract["contract_id"],
            "contract_version": contract["contract_version"],
        },
        "component_refs": [
            {"component_type": "ENTERPRISE_CONTEXT_SNAPSHOT", "component_id": "ECS:CN600839:20180930:R9", "component_version": "1", "admission_level": "E0_CONTEXT", "read_only": True},
            {"component_type": "ENTERPRISE_SYSTEM_MODEL", "component_id": "ESM:CN600839:20180930:R9", "component_version": "1", "admission_level": "E1_RECONSTRUCTION", "read_only": True},
            {"component_type": "MANAGEMENT_DECISION_LEDGER", "component_id": "MDL:CN600839:20180930:R9", "component_version": "1", "admission_level": "E1_RECONSTRUCTION", "read_only": True},
            {"component_type": "OUTCOME_MEASUREMENT_CONTRACT", "component_id": MEASUREMENT_CONTRACT_ID, "component_version": "3", "admission_level": "E2_MECHANISM_PROBE", "read_only": True},
        ],
        "question_set": question_set,
        "claims": claims,
        "mechanism_threads": threads,
        "outcome_cells": [{
            "outcome_cell_id": cell_id,
            "dimension": CELL_DIMENSIONS[cell_id],
            "status": "UNKNOWN",
            "measurement_contract_ref": MEASUREMENT_CONTRACT_ID,
            "custodian_receipt_ref": "",
        } for cell_id in CELL.values()],
        "roles": deepcopy(block["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST",
        "claim_class": "COMPOSITE_ENTERPRISE_JUDGMENT",
        "allowed_outputs": list(episode_module.ALLOWED_OUTPUTS),
    }


def build_canonical_preoutcome_package(
    block: dict[str, Any], packets: list[dict[str, Any]], selection: dict[str, Any],
) -> dict[str, Any]:
    contract = build_decision_contract(block, selection)
    baseline = _baseline_episode(contract, block)
    enhanced = _enhanced_episode(contract, block)
    pairing = {
        "schema_version": decision_utility.PAIRING_SCHEMA_VERSION,
        "pairing_id": "UTILITY:PAIR:CN600839:20180930:ROUND9:V1",
        "decision_contract_ref": {"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
        "baseline_episode_id": baseline["episode_id"],
        "enhanced_episode_id": enhanced["episode_id"],
        "baseline_method_id": BASELINE_METHOD_ID,
        "enhanced_method_id": ENHANCED_METHOD_ID,
        "baseline_research_cost_hours": 3.0,
        "enhanced_research_cost_hours": 3.0,
        "frozen_at": FROZEN_AT,
        "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": list(decision_utility.ALLOWED_OUTPUTS),
    }
    return {
        "schema_version": multidimensional.PREOUTCOME_SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "industry_block_ref": {"block_id": block["block_id"], "schema_version": block["schema_version"]},
        "selection_ref": {"selection_id": selection["selection_id"], "schema_version": selection["schema_version"]},
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


def build_source_resolution_policy() -> dict[str, Any]:
    return {
        "schema_version": "enterprise-judgment-round9-source-resolution-policy.v1",
        "policy_id": "SOURCE-RESOLUTION:R9:CN600839:FY2019:V1",
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "report_period_end": "2019-12-31",
        "provider": "CNINFO",
        "security_code": "600839",
        "document_category": "ANNUAL_REPORT",
        "bounded_announcement_window": {"start": "2020-01-01", "end": "2020-06-30"},
        "selection_rule": "EARLIEST_ORIGINAL_FULL_FY2019_ANNUAL_REPORT_STATIC_FINALPAGE_PDF",
        "required_static_host": "static.cninfo.com.cn",
        "excluded_titles": ["SUMMARY", "ABSTRACT", "REVISION", "CORRECTION", "ENGLISH_VERSION"],
        "resolution_timing": "ONLY_AFTER_PREOUTCOME_FREEZE_COMMIT",
        "permitted_metadata_use": "ENUMERATE_AND_BIND_STATIC_PDF_IDENTITY_ONLY",
        "prohibited_prebinding_use": ["PDF_CONTENT", "OUTCOME_VALUE", "OUTCOME_DIRECTION", "PRICE", "RETURN"],
        "object_class": "OUTCOME_SOURCE_RESOLUTION_POLICY",
        "claim_class": "POST_FREEZE_DETERMINISTIC_SOURCE_IDENTITY_ONLY",
        "allowed_outputs": ["OUTCOME_SOURCE_BINDING_RECEIPT", "RESEARCH_AGENDA"],
    }


def build_resolution_contract() -> dict[str, Any]:
    return {
        "schema_version": "enterprise-judgment-round9-method-resolution-contract.v1",
        "contract_id": "METHOD-RESOLUTION:R9:CN600839:FY2019:V1",
        "package_ref": PACKAGE_ID,
        "frozen_at": FROZEN_AT,
        "baseline": {
            "method_id": BASELINE_METHOD_ID,
            "method_kind": "SIMPLE_PRODUCT_TREND_WITH_GROUP_BOUNDARY_GUARD",
            "resolver_id": "resolve_method_outputs.v1",
            "input_cell_ids": [
                CELL["GROUP_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_LEVEL"],
                CELL["WHITE_GOODS_GROSS_MARGIN"], CELL["GROUP_OCF_LEVEL"],
                CELL["GROUP_ASSET_LIABILITY_RATIO"],
            ],
            "signal_rules": [
                {"signal_id": "PRODUCT_REVENUE_DIRECTION", "cell_ids": [CELL["WHITE_GOODS_REVENUE_LEVEL"]], "positive_labels": ["OBSERVED_INCREASE"], "negative_labels": ["OBSERVED_DECREASE"], "other_observed": "NEUTRAL"},
                {"signal_id": "PRODUCT_MARGIN_DIRECTION", "cell_ids": [CELL["WHITE_GOODS_GROSS_MARGIN"]], "positive_labels": ["OBSERVED_INCREASE"], "negative_labels": ["OBSERVED_DECREASE"], "other_observed": "NEUTRAL"},
                {"signal_id": "GROUP_FINANCIAL_BACKDROP", "cell_ids": [CELL["GROUP_OCF_LEVEL"], CELL["GROUP_ASSET_LIABILITY_RATIO"]], "positive_rule": "OCF_INCREASE_AND_LEVERAGE_NOT_INCREASE", "negative_rule": "OCF_DECREASE_OR_LEVERAGE_INCREASE", "other_observed": "NEUTRAL"},
            ],
            "boundary_guard": {
                "input_cell_ids": [CELL["GROUP_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_LEVEL"]],
                "divergence_pairs": [
                    ["OBSERVED_INCREASE", "OBSERVED_DECREASE"],
                    ["OBSERVED_DECREASE", "OBSERVED_INCREASE"],
                ],
                "divergence_output": "WHITE_GOODS_UNKNOWN",
            },
            "output_rule": {
                "WHITE_GOODS_POSITIVE": "product revenue and margin are positive, group/product guard passes, and backdrop is not negative",
                "WHITE_GOODS_NEGATIVE": "product revenue and margin are negative and group/product guard passes",
                "WHITE_GOODS_UNKNOWN": "fully observed signals do not meet a directional rule or group/product directions diverge",
                "NOT_DIAGNOSTIC": "one or more signals UNKNOWN or MEASUREMENT_MISMATCH",
            },
            "primary_question_projection": "Answer only a simple white-goods operating trend; never promote a group trend across the product boundary.",
            "prohibited_post_outcome_revision": "No customer, action-causality, owner-cash, portfolio or new threshold condition may be added after freeze.",
        },
        "enhanced": {
            "method_id": ENHANCED_METHOD_ID,
            "method_kind": "EIGHT_DIMENSION_NO_SCORE_QUESTION_SKELETON",
            "resolver_id": "resolve_method_outputs.v1",
            "dimension_rules": [
                {"dimension_id": "INITIAL_CONDITIONS", "input_cell_ids": [CELL["INDUSTRY_CONTEXT_EVENT"], CELL["PORTFOLIO_SCOPE_EVENT"]], "resolution_rule": "DESCRIPTIVE_CONTEXT_ONLY; never causal credit."},
                {"dimension_id": "IMPLEMENTED_MANAGEMENT_ACTION", "input_cell_ids": [CELL["WHITE_GOODS_ACTION_EVENT"]], "resolution_rule": "Observed only for an explicit FY2019 implemented product/channel/organization action; effect remains unproved."},
                {"dimension_id": "EXECUTION", "input_cell_ids": [CELL["WHITE_GOODS_ACTION_EVENT"], CELL["WHITE_GOODS_REVENUE_LEVEL"], CELL["WHITE_GOODS_GROSS_MARGIN"]], "resolution_rule": "SUPPORTED_TREND only when action is OBSERVED_YES and both product revenue and margin are OBSERVED_INCREASE; WEAKENED_TREND when both product signals decrease; MIXED otherwise; any unavailable input is NOT_DIAGNOSTIC."},
                {"dimension_id": "CUSTOMER_COMPETITION_RESPONSE", "input_cell_ids": [CELL["WHITE_GOODS_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_SHARE"]], "resolution_rule": "Revenue and portfolio share are descriptive absorption only; without frozen volume, price or customer-share cells the conclusion is always NOT_DIAGNOSTIC for customer preference."},
                {"dimension_id": "UNIT_ECONOMICS", "input_cell_ids": [CELL["WHITE_GOODS_GROSS_MARGIN"]], "resolution_rule": "Use the product-arena gross-margin label only; do not attribute cause."},
                {"dimension_id": "WORKING_CAPITAL_CASH_CAPITAL", "input_cell_ids": [CELL["GROUP_OCF_LEVEL"], CELL["GROUP_OCF_TO_CAPEX"], CELL["OWNER_CASH_BRIDGE_EVENT"]], "resolution_rule": "Issuer funding may be described from OCF and coverage; owner cash is supported only by OBSERVED_YES owner-cash bridge."},
                {"dimension_id": "ADAPTATION_PERMANENT_LOSS", "input_cell_ids": [CELL["GROUP_ASSET_LIABILITY_RATIO"], CELL["PORTFOLIO_SCOPE_EVENT"], CELL["OWNER_CASH_BRIDGE_EVENT"]], "resolution_rule": "Adverse leverage or scope change is a risk signal; absence is not proof against permanent loss and owner-cash UNKNOWN remains local."},
                {"dimension_id": "STRONGEST_ALTERNATIVE_EXPLANATION", "input_cell_ids": [CELL["GROUP_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_LEVEL"], CELL["WHITE_GOODS_REVENUE_SHARE"], CELL["PORTFOLIO_SCOPE_EVENT"]], "resolution_rule": "Portfolio rival is material when group and product directions diverge, product share decreases, or a scope event is observed."},
            ],
            "causal_credit_rule": "NONE_FOR_ALL_FY2019_ANNUAL_REPORT_CELLS",
            "ordinary_share_rule": "No group OCF, capex or dividend may substitute for the contracted owner-cash bridge.",
            "prohibited_post_outcome_revision": "No threshold, dimension rule, rival or boundary may be added after freeze.",
        },
        "paired_utility_rules": {
            "resolver_id": "resolve_method_outputs.v1",
            "common_decision_treatments": {
                "baseline": {
                    "WHITE_GOODS_POSITIVE": "CONTINUE_OPERATING_UNDERWRITING",
                    "WHITE_GOODS_NEGATIVE": "ESCALATE_PERMANENT_LOSS_REVIEW",
                    "WHITE_GOODS_UNKNOWN": "RESEARCH_REQUIRED",
                    "NOT_DIAGNOSTIC": "RESEARCH_REQUIRED",
                },
                "enhanced": {
                    "SUPPORTED_WITHOUT_MATERIAL_RIVAL_OR_RISK": "CONTINUE_OPERATING_UNDERWRITING",
                    "WEAKENED_WITHOUT_MATERIAL_RIVAL_OR_RISK": "ESCALATE_PERMANENT_LOSS_REVIEW",
                    "ALL_OTHER_CASES": "RESEARCH_REQUIRED",
                },
                "owner_cash": {
                    "baseline": "OWNER_CASH_UNKNOWN",
                    "enhanced_bridge_observed": "OWNER_CASH_EVIDENCED",
                    "enhanced_other": "OWNER_CASH_UNKNOWN",
                },
            },
            "AVOIDED_ERROR": {
                "allowed_pairs": [
                    ["WHITE_GOODS_POSITIVE", "WEAKENED_TREND"],
                    ["WHITE_GOODS_NEGATIVE", "SUPPORTED_TREND"],
                ],
                "portfolio_rival_alone_is_insufficient": True,
                "baseline_unknown_or_not_diagnostic_is_ineligible": True,
            },
            "MATERIAL_IMPROVEMENT": {
                "allowed_cases": [
                    "OWNER_CASH_DECISION_TREATMENT_CHANGES_FROM_UNKNOWN_TO_EVIDENCED",
                    "MATERIAL_RIVAL_OR_SCOPE_RISK_CHANGES_COMMON_DECISION_TREATMENT",
                ],
                "coverage_alone_is_insufficient": True,
            },
            "NO_DIFFERENCE": "Both methods reach the same decision-relevant treatment from frozen rules.",
            "NOT_DIAGNOSTIC": "A required field is unavailable or neither method-specific material condition is met.",
            "method_release": "CANDIDATE_ONLY_REGARDLESS_OF_ONE_SAMPLE_RESULT",
        },
        "rights": deepcopy(RIGHTS),
        "object_class": "METHOD_SPECIFIC_OUTCOME_RESOLUTION_CONTRACT",
        "claim_class": "PRE_OUTCOME_MECHANICAL_METHOD_COMPARISON_RULES",
        "allowed_outputs": ["METHOD_RESOLUTION_RECEIPT", "DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


UNAVAILABLE_LABELS = {"UNKNOWN", "MEASUREMENT_MISMATCH"}
NUMERIC_LABELS = {
    "OBSERVED_DECREASE", "OBSERVED_STABLE", "OBSERVED_INCREASE",
    *UNAVAILABLE_LABELS,
}
EVENT_LABELS = {"OBSERVED_YES", "OBSERVED_NO", *UNAVAILABLE_LABELS}


def _require_resolution_labels(labels: Any) -> dict[str, str]:
    if not isinstance(labels, dict) or set(labels) != set(CELL.values()):
        raise ValueError("round9 resolution labels must cover every frozen cell exactly once")
    result = {str(cell_id): str(label) for cell_id, label in labels.items()}
    event_ids = {
        CELL["INDUSTRY_CONTEXT_EVENT"], CELL["WHITE_GOODS_ACTION_EVENT"],
        CELL["PORTFOLIO_SCOPE_EVENT"], CELL["OWNER_CASH_BRIDGE_EVENT"],
    }
    for cell_id, label in result.items():
        domain = EVENT_LABELS if cell_id in event_ids else NUMERIC_LABELS
        if label not in domain:
            raise ValueError(f"round9 resolution label invalid for {cell_id}: {label}")
    return result


def _unavailable(*labels: str) -> bool:
    return any(label in UNAVAILABLE_LABELS for label in labels)


def resolve_method_outputs(labels: Any) -> dict[str, Any]:
    """Mechanically resolve both methods from the frozen cell-label vector."""
    item = _require_resolution_labels(labels)
    group_revenue = item[CELL["GROUP_REVENUE_LEVEL"]]
    product_revenue = item[CELL["WHITE_GOODS_REVENUE_LEVEL"]]
    product_margin = item[CELL["WHITE_GOODS_GROSS_MARGIN"]]
    group_ocf = item[CELL["GROUP_OCF_LEVEL"]]
    leverage = item[CELL["GROUP_ASSET_LIABILITY_RATIO"]]

    baseline_required = [group_revenue, product_revenue, product_margin, group_ocf, leverage]
    if _unavailable(*baseline_required):
        backdrop = "NOT_DIAGNOSTIC"
        baseline_direction = "NOT_DIAGNOSTIC"
        boundary_guard = "NOT_DIAGNOSTIC"
    else:
        if group_ocf == "OBSERVED_DECREASE" or leverage == "OBSERVED_INCREASE":
            backdrop = "NEGATIVE"
        elif group_ocf == "OBSERVED_INCREASE" and leverage in {
            "OBSERVED_DECREASE", "OBSERVED_STABLE",
        }:
            backdrop = "POSITIVE"
        else:
            backdrop = "NEUTRAL"
        divergent = (group_revenue, product_revenue) in {
            ("OBSERVED_INCREASE", "OBSERVED_DECREASE"),
            ("OBSERVED_DECREASE", "OBSERVED_INCREASE"),
        }
        boundary_guard = "DIVERGENT" if divergent else "PASSED"
        if divergent:
            baseline_direction = "WHITE_GOODS_UNKNOWN"
        elif (
            product_revenue == "OBSERVED_INCREASE"
            and product_margin == "OBSERVED_INCREASE"
            and backdrop != "NEGATIVE"
        ):
            baseline_direction = "WHITE_GOODS_POSITIVE"
        elif (
            product_revenue == "OBSERVED_DECREASE"
            and product_margin == "OBSERVED_DECREASE"
        ):
            baseline_direction = "WHITE_GOODS_NEGATIVE"
        else:
            baseline_direction = "WHITE_GOODS_UNKNOWN"

    industry_event = item[CELL["INDUSTRY_CONTEXT_EVENT"]]
    action = item[CELL["WHITE_GOODS_ACTION_EVENT"]]
    product_share = item[CELL["WHITE_GOODS_REVENUE_SHARE"]]
    ocf_to_capex = item[CELL["GROUP_OCF_TO_CAPEX"]]
    portfolio_event = item[CELL["PORTFOLIO_SCOPE_EVENT"]]
    owner_cash_bridge = item[CELL["OWNER_CASH_BRIDGE_EVENT"]]

    if _unavailable(action, product_revenue, product_margin):
        enhanced_execution = "NOT_DIAGNOSTIC"
    elif (
        action == "OBSERVED_YES"
        and product_revenue == "OBSERVED_INCREASE"
        and product_margin == "OBSERVED_INCREASE"
    ):
        enhanced_execution = "SUPPORTED_TREND"
    elif (
        product_revenue == "OBSERVED_DECREASE"
        and product_margin == "OBSERVED_DECREASE"
    ):
        enhanced_execution = "WEAKENED_TREND"
    else:
        enhanced_execution = "MIXED_TREND"

    rival_required = [group_revenue, product_revenue, product_share, portfolio_event]
    if _unavailable(*rival_required):
        portfolio_rival = "NOT_DIAGNOSTIC"
    else:
        group_product_divergence = (group_revenue, product_revenue) in {
            ("OBSERVED_INCREASE", "OBSERVED_DECREASE"),
            ("OBSERVED_DECREASE", "OBSERVED_INCREASE"),
        }
        portfolio_rival = (
            "MATERIAL"
            if group_product_divergence
            or product_share == "OBSERVED_DECREASE"
            or portfolio_event == "OBSERVED_YES"
            else "NOT_MATERIAL_FROM_FROZEN_CELLS"
        )

    if _unavailable(group_ocf, ocf_to_capex):
        issuer_funding = "NOT_DIAGNOSTIC"
    elif group_ocf == "OBSERVED_INCREASE" and ocf_to_capex == "OBSERVED_INCREASE":
        issuer_funding = "STRONGER"
    elif group_ocf == "OBSERVED_DECREASE" or ocf_to_capex == "OBSERVED_DECREASE":
        issuer_funding = "WEAKER"
    else:
        issuer_funding = "MIXED"
    owner_cash = (
        "NOT_DIAGNOSTIC"
        if owner_cash_bridge in UNAVAILABLE_LABELS
        else "BRIDGE_OBSERVED"
        if owner_cash_bridge == "OBSERVED_YES"
        else "NO_EXPLICIT_BRIDGE"
    )
    permanent_loss = (
        "NOT_DIAGNOSTIC"
        if _unavailable(leverage, portfolio_event)
        else "RISK_SIGNAL"
        if leverage == "OBSERVED_INCREASE" or portfolio_event == "OBSERVED_YES"
        else "NOT_PROVED_SAFE"
    )
    enhanced_dimensions = {
        "INITIAL_CONDITIONS": (
            "NOT_DIAGNOSTIC" if industry_event in UNAVAILABLE_LABELS else "DESCRIPTIVE_CONTEXT_ONLY"
        ),
        "IMPLEMENTED_MANAGEMENT_ACTION": (
            "NOT_DIAGNOSTIC"
            if action in UNAVAILABLE_LABELS
            else "IMPLEMENTED_ACTION_OBSERVED"
            if action == "OBSERVED_YES"
            else "NO_EXPLICIT_ACTION",
        ),
        "EXECUTION": enhanced_execution,
        "CUSTOMER_COMPETITION_RESPONSE": "NOT_DIAGNOSTIC",
        "UNIT_ECONOMICS": (
            "NOT_DIAGNOSTIC" if product_margin in UNAVAILABLE_LABELS else product_margin
        ),
        "WORKING_CAPITAL_CASH_CAPITAL": {
            "issuer_funding": issuer_funding,
            "ordinary_share_owner_cash": owner_cash,
        },
        "ADAPTATION_PERMANENT_LOSS": permanent_loss,
        "STRONGEST_ALTERNATIVE_EXPLANATION": portfolio_rival,
    }

    baseline_decision_treatment = {
        "WHITE_GOODS_POSITIVE": "CONTINUE_OPERATING_UNDERWRITING",
        "WHITE_GOODS_NEGATIVE": "ESCALATE_PERMANENT_LOSS_REVIEW",
        "WHITE_GOODS_UNKNOWN": "RESEARCH_REQUIRED",
        "NOT_DIAGNOSTIC": "RESEARCH_REQUIRED",
    }[baseline_direction]
    if (
        enhanced_execution == "SUPPORTED_TREND"
        and portfolio_rival == "NOT_MATERIAL_FROM_FROZEN_CELLS"
        and permanent_loss != "RISK_SIGNAL"
    ):
        enhanced_decision_treatment = "CONTINUE_OPERATING_UNDERWRITING"
    elif (
        enhanced_execution == "WEAKENED_TREND"
        and portfolio_rival == "NOT_MATERIAL_FROM_FROZEN_CELLS"
        and permanent_loss != "RISK_SIGNAL"
    ):
        enhanced_decision_treatment = "ESCALATE_PERMANENT_LOSS_REVIEW"
    else:
        enhanced_decision_treatment = "RESEARCH_REQUIRED"
    baseline_owner_cash_treatment = "OWNER_CASH_UNKNOWN"
    enhanced_owner_cash_treatment = (
        "OWNER_CASH_EVIDENCED" if owner_cash == "BRIDGE_OBSERVED" else "OWNER_CASH_UNKNOWN"
    )
    operating_treatment_changed = baseline_decision_treatment != enhanced_decision_treatment
    owner_cash_treatment_changed = baseline_owner_cash_treatment != enhanced_owner_cash_treatment

    directional_pair = (baseline_direction, enhanced_execution)
    execution_utility = (
        "AVOIDED_ERROR"
        if directional_pair in {
            ("WHITE_GOODS_POSITIVE", "WEAKENED_TREND"),
            ("WHITE_GOODS_NEGATIVE", "SUPPORTED_TREND"),
        }
        else "NO_DIFFERENCE"
        if directional_pair in {
            ("WHITE_GOODS_POSITIVE", "SUPPORTED_TREND"),
            ("WHITE_GOODS_NEGATIVE", "WEAKENED_TREND"),
        }
        else "NOT_DIAGNOSTIC"
    )
    material_rival_changed_treatment = (
        operating_treatment_changed
        and (portfolio_rival == "MATERIAL" or portfolio_event == "OBSERVED_YES")
    )
    paired_utility = {
        "INITIAL_CONDITIONS": (
            "NO_DIFFERENCE" if enhanced_dimensions["INITIAL_CONDITIONS"] != "NOT_DIAGNOSTIC" else "NOT_DIAGNOSTIC"
        ),
        "IMPLEMENTED_MANAGEMENT_ACTION": "NOT_DIAGNOSTIC",
        "EXECUTION": execution_utility,
        "CUSTOMER_COMPETITION_RESPONSE": "NOT_DIAGNOSTIC",
        "UNIT_ECONOMICS": (
            "NO_DIFFERENCE" if enhanced_dimensions["UNIT_ECONOMICS"] != "NOT_DIAGNOSTIC" else "NOT_DIAGNOSTIC"
        ),
        "WORKING_CAPITAL_CASH_CAPITAL": (
            "MATERIAL_IMPROVEMENT" if owner_cash_treatment_changed
            else "NOT_DIAGNOSTIC" if issuer_funding == "NOT_DIAGNOSTIC"
            else "NO_DIFFERENCE"
        ),
        "ADAPTATION_PERMANENT_LOSS": (
            "MATERIAL_IMPROVEMENT" if material_rival_changed_treatment
            else "NOT_DIAGNOSTIC" if permanent_loss == "NOT_DIAGNOSTIC"
            else "NO_DIFFERENCE"
        ),
        "STRONGEST_ALTERNATIVE_EXPLANATION": (
            "MATERIAL_IMPROVEMENT" if material_rival_changed_treatment
            else "NOT_DIAGNOSTIC" if portfolio_rival == "NOT_DIAGNOSTIC"
            else "NO_DIFFERENCE"
        ),
    }
    return {
        "resolver_id": "resolve_method_outputs.v1",
        "baseline": {
            "white_goods_direction": baseline_direction,
            "group_product_boundary_guard": boundary_guard,
            "group_financial_backdrop": backdrop,
        },
        "enhanced": {"dimension_outputs": enhanced_dimensions},
        "common_decision_treatments": {
            "baseline_operating": baseline_decision_treatment,
            "enhanced_operating": enhanced_decision_treatment,
            "baseline_owner_cash": baseline_owner_cash_treatment,
            "enhanced_owner_cash": enhanced_owner_cash_treatment,
        },
        "paired_utility": paired_utility,
        "method_release": "CANDIDATE_ONLY_REGARDLESS_OF_ONE_SAMPLE_RESULT",
    }


def _labels_from_settlement(settlement: Any) -> tuple[str, dict[str, str]]:
    item = settlement if isinstance(settlement, dict) else {}
    settlement_id = item.get("settlement_id")
    if not isinstance(settlement_id, str) or not settlement_id:
        raise ValueError("round9 canonical settlement_id required")
    if item.get("company_id") != COMPANY_ID or item.get("cutoff_at") != CUTOFF_AT:
        raise ValueError("round9 canonical settlement company or cutoff mismatch")
    if item.get("measurement_contract_ref") != {
        "measurement_contract_id": MEASUREMENT_CONTRACT_ID,
        "measurement_contract_version": 3,
    }:
        raise ValueError("round9 canonical settlement measurement contract mismatch")
    rows = item.get("cell_results")
    if not isinstance(rows, list):
        raise ValueError("round9 canonical settlement cell_results required")
    expected_ids = list(CELL.values())
    actual_ids = [row.get("cell_id") for row in rows if isinstance(row, dict)]
    if len(rows) != len(expected_ids) or actual_ids != expected_ids:
        raise ValueError("round9 canonical settlement cells must be complete, unique and ordered")
    labels: dict[str, str] = {}
    for row in rows:
        status = row.get("status")
        label = row.get("label")
        if status == "UNKNOWN" and label != "UNKNOWN":
            raise ValueError("round9 canonical settlement UNKNOWN label mismatch")
        if status == "MEASUREMENT_MISMATCH" and label != "MEASUREMENT_MISMATCH":
            raise ValueError("round9 canonical settlement mismatch label mismatch")
        if status == "OBSERVED" and label in UNAVAILABLE_LABELS:
            raise ValueError("round9 canonical settlement observed label invalid")
        if status not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
            raise ValueError("round9 canonical settlement status invalid")
        labels[str(row["cell_id"])] = str(label)
    return settlement_id, _require_resolution_labels(labels)


def build_method_resolution_receipt(
    settlement: Any, *, resolved_at: str,
) -> dict[str, Any]:
    settlement_ref, frozen_labels = _labels_from_settlement(settlement)
    return {
        "schema_version": "enterprise-judgment-round9-method-resolution-receipt.v1",
        "resolution_id": "METHOD-RESOLUTION-RECEIPT:R9:CN600839:FY2019:V1",
        "resolution_contract_ref": build_resolution_contract()["contract_id"],
        "settlement_ref": settlement_ref,
        "resolved_at": resolved_at,
        "input_labels": {cell_id: frozen_labels[cell_id] for cell_id in CELL.values()},
        "resolved_outputs": resolve_method_outputs(frozen_labels),
        "rights": deepcopy(RIGHTS),
        "object_class": "METHOD_RESOLUTION_RECEIPT",
        "claim_class": "MECHANICAL_REPLAY_FROM_FROZEN_SETTLEMENT_LABELS",
        "allowed_outputs": ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


def validate_method_resolution_receipt(receipt: Any, *, canonical_settlement: Any) -> dict[str, Any]:
    item = receipt if isinstance(receipt, dict) else {}
    findings: list[str] = []
    try:
        expected = build_method_resolution_receipt(
            canonical_settlement,
            resolved_at=str(item.get("resolved_at") or ""),
        )
    except ValueError as exc:
        return {"valid": False, "findings": [str(exc)]}
    if item != expected:
        findings.append("method_resolution_receipt_does_not_replay_frozen_resolver")
    if not item.get("resolved_at"):
        findings.append("method_resolution_receipt_time_missing")
    return {"valid": not findings, "findings": findings}


def build_preoutcome_freeze() -> dict[str, Any]:
    packets = build_source_packets()
    block = build_industry_block()
    selection = build_selection(block, packets)
    package = build_canonical_preoutcome_package(block, packets, selection)
    return {
        "schema_version": "enterprise-judgment-round9-preoutcome-freeze.v1",
        "freeze_id": "R9FREEZE:CN600839:20180930:V1",
        "existing_episode_ref": "J2:CN:600839:C2",
        "industry_block": block,
        "source_packets": packets,
        "mechanical_selection_receipt": selection,
        "canonical_preoutcome_package": package,
        "source_resolution_policy": build_source_resolution_policy(),
        "method_resolution_contract": build_resolution_contract(),
        "freeze_state": "PRE_OUTCOME_FROZEN_SOURCE_UNRESOLVED",
        "frozen_at": FROZEN_AT,
        "outcome_source_located": False,
        "outcome_content_read": False,
        "rights": deepcopy(RIGHTS),
        "object_class": "ROUND9_PREOUTCOME_FREEZE",
        "claim_class": "SIMPLE_BASELINE_VS_EIGHT_DIMENSION_BLIND_METHOD_TEST",
        "allowed_outputs": ["PREOUTCOME_COMMIT", "POST_FREEZE_SOURCE_RESOLUTION", "RESEARCH_AGENDA"],
    }


def validate_preoutcome_freeze(freeze: Any) -> dict[str, Any]:
    expected = build_preoutcome_freeze()
    findings: list[str] = []
    if not isinstance(freeze, dict) or freeze != expected:
        findings.append("round9_preoutcome_freeze_must_equal_deterministic_builder")
        return {"valid": False, "findings": findings}
    block = freeze["industry_block"]
    packets = freeze["source_packets"]
    selection = freeze["mechanical_selection_receipt"]
    package = freeze["canonical_preoutcome_package"]
    validation = multidimensional.validate_preoutcome_package(
        package, block=block, source_packets=packets, selection=selection,
    )
    findings.extend("canonical_preoutcome:" + item for item in validation["findings"])
    source_validation = source_packet_module.validate_source_packet_receipt(packets[0])
    findings.extend("source_packet:" + item for item in source_validation["findings"])
    baseline = package["baseline_episode"]
    enhanced = package["enhanced_episode"]
    baseline_active = [claim for claim in baseline["claims"] if claim["cell_status"] != "NOT_APPLICABLE"]
    if len(baseline["question_set"]) != 3 or len(baseline_active) != 3:
        findings.append("baseline_must_remain_three_signal_consolidated_heuristic")
    baseline_locators = {
        locator for claim in baseline["claims"] for locator in claim["evidence_locator_refs"]
    }
    enhanced_locators = {
        locator for claim in enhanced["claims"] for locator in claim["evidence_locator_refs"]
    }
    if baseline_locators != enhanced_locators or baseline_locators != set(LOCATOR.values()):
        findings.append("methods_must_use_same_complete_cutoff_before_locator_union")
    measurement = package["outcome_measurement_contract"]
    source_access = measurement["source_access"]
    if source_access["source_id"] != UNRESOLVED_SOURCE_ID or source_access["official_url"] != UNRESOLVED_SOURCE_URL:
        findings.append("outcome_source_identity_must_remain_unresolved_before_commit")
    if freeze["outcome_source_located"] is not False or freeze["outcome_content_read"] is not False:
        findings.append("outcome_access_flags_must_remain_false_before_commit")
    boundary_ids = {
        cell["responsibility_boundary"]["responsibility_unit_id"]
        for cell in measurement["atomic_cells"]
    }
    expected_boundaries = {
        "INDUSTRY_CONTEXT:CN:WHITE_GOODS",
        "ISSUER_CONSOLIDATED:CN:600839",
        "PRODUCT_ARENA:CN:600839:WHITE_GOODS",
        "ORDINARY_SHARE_CASH:CN:600839",
    }
    if boundary_ids != expected_boundaries:
        findings.append("four_typed_responsibility_boundaries_required")
    for cell in measurement["atomic_cells"]:
        clock = cell["measurement_clock"]
        if clock["clock_kind"] == "FLOW_PERIOD" and clock["flow_period"]["period_start"] != "2019-01-01":
            findings.append("all_flow_cells_must_be_strictly_post_cutoff_fy2019")
        if clock["clock_kind"] == "EVENT_WINDOW" and clock["event_window"]["event_start"] != "2019-01-01":
            findings.append("all_event_cells_must_be_strictly_post_cutoff_fy2019")
    resolution = freeze["method_resolution_contract"]
    if resolution["baseline"]["method_id"] == resolution["enhanced"]["method_id"]:
        findings.append("method_resolution_rules_must_be_separate")
    if resolution != build_resolution_contract():
        findings.append("method_resolution_contract_must_equal_frozen_builder")
    return {"valid": not findings, "findings": findings}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def materialize_preoutcome(output_dir: Path) -> dict[str, Any]:
    freeze = build_preoutcome_freeze()
    validation = validate_preoutcome_freeze(freeze)
    if not validation["valid"]:
        raise ValueError("round9 preoutcome freeze invalid: " + "; ".join(validation["findings"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "01_industry_learning_block.json", freeze["industry_block"])
    _write_json(output_dir / "02_source_packet_receipts.json", freeze["source_packets"])
    _write_json(output_dir / "03_mechanical_selection_receipt.json", freeze["mechanical_selection_receipt"])
    _write_json(output_dir / "04_canonical_preoutcome_package.json", freeze["canonical_preoutcome_package"])
    _write_json(output_dir / "05_source_resolution_policy.json", freeze["source_resolution_policy"])
    _write_json(output_dir / "06_method_resolution_contract.json", freeze["method_resolution_contract"])
    _write_json(output_dir / "07_round9_preoutcome_freeze.json", freeze)
    return freeze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-preoutcome-dir")
    args = parser.parse_args()
    freeze = build_preoutcome_freeze()
    result = validate_preoutcome_freeze(freeze)
    if args.write_preoutcome_dir and result["valid"]:
        materialize_preoutcome(Path(args.write_preoutcome_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
