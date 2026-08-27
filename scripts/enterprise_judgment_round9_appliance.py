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
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode_module
    from scripts import enterprise_judgment_multidimensional_training as multidimensional
    from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
    from scripts import enterprise_judgment_reconstruction as reconstruction
    from scripts import enterprise_judgment_source_packet as source_packet_module
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import judgment_decision_utility as decision_utility
    from scripts import outcome_measurement_acquisition as measurement_acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_episode as episode_module
    import enterprise_judgment_multidimensional_training as multidimensional
    import enterprise_judgment_real_mechanism_training as mechanism_training
    import enterprise_judgment_reconstruction as reconstruction
    import enterprise_judgment_source_packet as source_packet_module
    import enterprise_judgment_training_control_plane as enterprise_control
    import judgment_decision_utility as decision_utility
    import outcome_measurement_acquisition as measurement_acquisition
    import outcome_measurement_settlement_adapter as settlement_adapter


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
OUTCOME_SOURCE_ID = "CNINFO:600839:ANN:20200418:1207528466"
OUTCOME_SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2020-04-18/1207528466.PDF"
OUTCOME_SOURCE_AVAILABLE_DATE = "2020-04-18"
OUTCOME_SETTLEMENT_ID = "R9SETTLE:CN600839:20180930:FY2019:V1"
METHOD_CONCLUSION = "ROUND9_METHOD_COMPARISON_INVALID_MODEL_ERROR"
NEXT_METHOD_EPOCH_ID = "METHOD-EPOCH:ENTERPRISE-JUDGMENT:EIGHT-DIMENSION:V2"
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
    frozen_outputs = resolve_method_outputs(frozen_labels)
    action_output = frozen_outputs["enhanced"]["dimension_outputs"][
        "IMPLEMENTED_MANAGEMENT_ACTION"
    ]
    model_errors = []
    if not isinstance(action_output, str):
        model_errors.append({
            "error_id": "R9MODEL:NON_SCALAR_IMPLEMENTED_ACTION",
            "field_path": "enhanced.dimension_outputs.IMPLEMENTED_MANAGEMENT_ACTION",
            "expected_type": "str",
            "actual_type": type(action_output).__name__,
            "root_cause": "MODEL",
            "economic_impact": (
                "The frozen post-settlement resolver cannot support a valid blind method comparison."
            ),
        })
    return {
        "schema_version": "enterprise-judgment-round9-method-resolution-receipt.v1",
        "resolution_id": "METHOD-RESOLUTION-RECEIPT:R9:CN600839:FY2019:V1",
        "resolution_contract_ref": build_resolution_contract()["contract_id"],
        "settlement_ref": settlement_ref,
        "resolved_at": resolved_at,
        "input_labels": {cell_id: frozen_labels[cell_id] for cell_id in CELL.values()},
        "resolution_status": "MODEL_ERROR" if model_errors else "RESOLVED",
        "model_errors": model_errors,
        "resolved_outputs": None if model_errors else frozen_outputs,
        "rights": deepcopy(RIGHTS),
        "object_class": "METHOD_RESOLUTION_RECEIPT",
        "claim_class": (
            "FROZEN_RESOLVER_MODEL_ERROR"
            if model_errors else "MECHANICAL_REPLAY_FROM_FROZEN_SETTLEMENT_LABELS"
        ),
        "allowed_outputs": (
            ["METHOD_FEEDBACK_INVALIDATION", "NEW_METHOD_EPOCH", "RESEARCH_AGENDA"]
            if model_errors else ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"]
        ),
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


def build_source_binding_receipt() -> dict[str, Any]:
    return {
        "schema_version": "enterprise-judgment-round9-source-binding-receipt.v1",
        "binding_id": "SOURCE-BINDING:R9:CN600839:FY2019:V1",
        "policy_ref": build_source_resolution_policy()["policy_id"],
        "preoutcome_freeze_ref": "R9FREEZE:CN600839:20180930:V1",
        "preoutcome_commit": "f147c8961a2508fb1945abf16308766aa50a5f6b",
        "resolved_after_preoutcome_commit": True,
        "bounded_query": {
            "provider": "CNINFO",
            "org_id": "gssh0600839",
            "security_code": "600839",
            "announcement_window": {"start": "2020-01-01", "end": "2020-06-30"},
            "result_count": 2,
        },
        "selected_source": {
            "title": "2019年年度报告",
            "announcement_date": OUTCOME_SOURCE_AVAILABLE_DATE,
            "announcement_id": "1207528466",
            "source_id": OUTCOME_SOURCE_ID,
            "official_url": OUTCOME_SOURCE_URL,
            "selection_reason": "EARLIEST_ORIGINAL_FULL_FY2019_ANNUAL_REPORT_STATIC_FINALPAGE_PDF",
        },
        "excluded_results": [{
            "title": "2019年年度报告摘要",
            "exclusion_reason": "SUMMARY_EXCLUDED_BY_FROZEN_POLICY",
        }],
        "content_read_during_identity_resolution": False,
        "allowed_contract_substitutions": [
            "source_access.source_id",
            "source_access.official_url",
            "source_access.source_available_date",
        ],
        "prohibited_changes": [
            "atomic_cells", "measurement_clocks", "responsibility_boundaries",
            "formulas", "label_rules", "method_resolution_rules",
        ],
        "object_class": "OUTCOME_SOURCE_BINDING_RECEIPT",
        "claim_class": "POST_FREEZE_DETERMINISTIC_SOURCE_IDENTITY_ONLY",
        "allowed_outputs": ["SOURCE_BOUND_MEASUREMENT_CONTRACT", "OUTCOME_ACCESS_AUTHORIZATION"],
    }


def build_source_bound_measurement_contract() -> dict[str, Any]:
    contract = build_measurement_contract()
    contract["source_access"].update({
        "source_id": OUTCOME_SOURCE_ID,
        "official_url": OUTCOME_SOURCE_URL,
        "source_available_at": None,
        "source_available_date": OUTCOME_SOURCE_AVAILABLE_DATE,
    })
    return contract


def validate_source_bound_measurement_contract(contract: Any) -> dict[str, Any]:
    item = contract if isinstance(contract, dict) else {}
    findings: list[str] = []
    if item != build_source_bound_measurement_contract():
        findings.append("source_bound_measurement_contract_must_equal_deterministic_binding")
        return {"valid": False, "findings": findings}
    preoutcome = build_measurement_contract()
    restored = deepcopy(item)
    restored["source_access"] = deepcopy(preoutcome["source_access"])
    if restored != preoutcome:
        findings.append("source_binding_changed_frozen_measurement_logic")
    validation = mechanism_training.validate_outcome_measurement_contract(item)
    findings.extend("source_bound_contract:" + finding for finding in validation["findings"])
    return {"valid": not findings, "findings": findings}


def build_outcome_authorization(
    package: dict[str, Any], contract: dict[str, Any],
) -> dict[str, Any]:
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
    package: dict[str, Any], contract: dict[str, Any], *, local_pdf_path: Path,
    registered_at: str,
) -> dict[str, Any]:
    source = contract["source_access"]
    authorization = build_outcome_authorization(package, contract)
    return {
        "schema_version": measurement_acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "OMINV:CN600839:FY2019:R9:V1",
        "measurement_contract_ref": deepcopy(authorization["measurement_contract_ref"]),
        "custodian_id": authorization["custodian_id"],
        "registered_at": registered_at,
        "documents": [{
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(local_pdf_path),
            "issuer_id": source["issuer_id"],
            "responsibility_boundary": "ISSUER_FILING:CN:600839:FY2019:MULTI_TYPED_BOUNDARIES",
            "report_period_end": source["report_period_end"],
            "official_source_type": source["source_type"],
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": (
                "Original FY2019 annual-report vintage. The issuer disposed of Sichuan Changhong New Energy "
                "at year-end and added newly established entities; the scope event is observed separately and "
                "does not rewrite the frozen product or issuer fields."
            ),
            "availability_precision": source["availability_precision"],
            "source_available_at": source["source_available_at"],
            "source_available_date": source["source_available_date"],
        }],
        "object_class": measurement_acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": measurement_acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }


def _field_record_base(cell: dict[str, Any], raw_field: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": cell["cell_id"],
        "field_id": raw_field["field_id"],
        "measurement_clock": deepcopy(raw_field["measurement_clock"]),
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "unit": raw_field["unit"],
    }


def _field_source(
    *, cell: dict[str, Any], raw_field: dict[str, Any], page: int,
    custodian_table: str, custodian_line: str, custodian_period: str,
) -> dict[str, Any]:
    locator = raw_field["locator"]
    return {
        "source_id": OUTCOME_SOURCE_ID,
        "source_url": OUTCOME_SOURCE_URL,
        "report_period_end": "2019-12-31",
        "official_source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": ISSUER_ID,
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "availability_precision": "DATE_ONLY",
        "source_available_date": OUTCOME_SOURCE_AVAILABLE_DATE,
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


def _ratio(numerator: str, denominator: str) -> float:
    return float(Decimal(numerator) / Decimal(denominator))


def build_custodian_field_records(contract: dict[str, Any]) -> list[dict[str, Any]]:
    observed: dict[str, tuple[bool | float, int, str, str, str]] = {
        "FIELD:600839:FY2019:INDUSTRY_CONTEXT_EVENT": (
            True, 8, "Industry development review",
            "Refrigerator average prices declined while air-conditioner overcapacity drove price promotion.",
            "FY2019",
        ),
        "FIELD:600839:FY2019:GROUP_REVENUE_LEVEL": (
            88_792_895_883.36, 77, "Consolidated income statement", "Operating revenue", "FY2019",
        ),
        "FIELD:600839:FY2019:WHITE_GOODS_REVENUE_LEVEL": (
            14_008_069_937.89, 14, "Principal business by product", "Air-conditioner and refrigerator revenue", "FY2019",
        ),
        "FIELD:600839:FY2019:WHITE_GOODS_GROSS_MARGIN": (
            _ratio("14008069937.89", "14008069937.89")
            - _ratio("10875926873.34", "14008069937.89"),
            14, "Principal business by product",
            "(RMB14,008,069,937.89 revenue less RMB10,875,926,873.34 cost) divided by revenue",
            "FY2019",
        ),
        "FIELD:600839:FY2019:WHITE_GOODS_REVENUE_SHARE": (
            _ratio("14008069937.89", "88792895883.36"), 14,
            "Principal business by product plus consolidated income statement",
            "White-goods revenue divided by consolidated operating revenue", "FY2019",
        ),
        "FIELD:600839:FY2019:GROUP_OCF_LEVEL": (
            1_565_512_587.09, 81, "Consolidated cash-flow statement",
            "Net cash flows from operating activities", "FY2019",
        ),
        "FIELD:600839:FY2019:GROUP_OCF_TO_CAPEX": (
            _ratio("1565512587.09", "1521162648.20"), 81,
            "Consolidated cash-flow statement",
            "Operating cash flow divided by cash paid to acquire long-lived assets", "FY2019",
        ),
        "FIELD:600839:FY2019:GROUP_ASSET_LIABILITY_RATIO": (
            _ratio("52853641256.70", "73989213869.68"), 73,
            "Consolidated balance sheet", "Total liabilities divided by total assets", "2019-12-31",
        ),
        "FIELD:600839:FY2019:WHITE_GOODS_ACTION_EVENT": (
            True, 12, "FY2019 management discussion",
            "The smart-white-goods industrial park reached full production during FY2019.", "FY2019",
        ),
        "FIELD:600839:FY2019:PORTFOLIO_SCOPE_EVENT": (
            True, 207, "Consolidation-scope change note",
            "The issuer transferred its 70.6835% New Energy stake and ceased consolidation at 2019-12-31.",
            "FY2019",
        ),
    }
    considered_source = {
        "source_id": OUTCOME_SOURCE_ID,
        "source_url": OUTCOME_SOURCE_URL,
        "report_period_end": "2019-12-31",
        "official_source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": ISSUER_ID,
        "responsibility_boundary": "ORDINARY_SHARE_CASH:CN:600839",
        "availability_precision": "DATE_ONLY",
        "source_available_date": OUTCOME_SOURCE_AVAILABLE_DATE,
        "field_ref": "PDF pp.23-24, 73-74 and 80-82",
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
            else:
                records.append({
                    **base,
                    "status": "UNKNOWN",
                    "reason": (
                        "AUTHORIZED_FY2019_REPORT_DISCLOSES_GROUP_CASH_CAPEX_LEVERAGE_AND_DIVIDEND_BUT_NO_"
                        "EXPLICIT_BRIDGE_THROUGH_REQUIRED_CAPITAL_AND_PRIORITY_CLAIMS_TO_RESIDUAL_ORDINARY_SHARE_CASH"
                    ),
                    "sources_considered": [deepcopy(considered_source)],
                })
    return records


PAGE_VALUE_BINDINGS: dict[str, dict[str, Any]] = {
    "FIELD:600839:FY2019:INDUSTRY_CONTEXT_EVENT": {
        "pdf_page": 8,
        "anchor_tokens": ["冰箱产品市场均价下行", "空调产品行业产能过剩"],
        "value_expression": {"operator": "BOOLEAN_TOKEN_PRESENCE", "tokens": ["通过降价促销来拉动市场需求"]},
    },
    "FIELD:600839:FY2019:GROUP_REVENUE_LEVEL": {
        "pdf_page": 77, "anchor_tokens": ["合并利润表", "88,792,895,883.36"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["88,792,895,883.36"], "multiplier": "1"},
    },
    "FIELD:600839:FY2019:WHITE_GOODS_REVENUE_LEVEL": {
        "pdf_page": 14,
        "anchor_tokens": ["空调冰箱", "14,008,069,937.89", "-6.70"],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["14,008,069,937.89"], "multiplier": "1"},
    },
    "FIELD:600839:FY2019:WHITE_GOODS_GROSS_MARGIN": {
        "pdf_page": 14, "anchor_tokens": ["空调冰箱", "22.36", "0.17"],
        "value_expression": {
            "operator": "GROSS_MARGIN_TOKENS", "tokens": ["14,008,069,937.89", "10,875,926,873.34"], "multiplier": "1",
        },
    },
    "FIELD:600839:FY2019:WHITE_GOODS_REVENUE_SHARE": {
        "pdf_page": 14, "supporting_pdf_pages": [77],
        "anchor_tokens": ["空调冰箱", "合并利润表"],
        "value_expression": {
            "operator": "RATIO_TOKENS", "tokens": ["14,008,069,937.89", "88,792,895,883.36"], "multiplier": "1",
        },
    },
    "FIELD:600839:FY2019:GROUP_OCF_LEVEL": {
        "pdf_page": 81,
        "anchor_tokens": [
            "经营活动产生的现金流", "量净额", "1,565,512,587.09", "4,424,454,303.24",
        ],
        "value_expression": {"operator": "SCALED_TOKEN", "tokens": ["1,565,512,587.09"], "multiplier": "1"},
    },
    "FIELD:600839:FY2019:GROUP_OCF_TO_CAPEX": {
        "pdf_page": 81, "supporting_pdf_pages": [82],
        "anchor_tokens": ["经营活动产生的现金流", "购建固定资产、无形资产和其", "他长期资产支付的现金"],
        "value_expression": {
            "operator": "RATIO_TOKENS", "tokens": ["1,565,512,587.09", "1,521,162,648.20"], "multiplier": "1",
        },
    },
    "FIELD:600839:FY2019:GROUP_ASSET_LIABILITY_RATIO": {
        "pdf_page": 73, "supporting_pdf_pages": [74],
        "anchor_tokens": ["资产总计", "负债合计"],
        "value_expression": {
            "operator": "RATIO_TOKENS", "tokens": ["52,853,641,256.70", "73,989,213,869.68"], "multiplier": "1",
        },
    },
    "FIELD:600839:FY2019:WHITE_GOODS_ACTION_EVENT": {
        "pdf_page": 12,
        "anchor_tokens": ["以智能白电及特种业务为核心的经开区工业园", "已实现全面投产"],
        "value_expression": {"operator": "BOOLEAN_TOKEN_PRESENCE", "tokens": ["智能白电", "全面投产"]},
    },
    "FIELD:600839:FY2019:PORTFOLIO_SCOPE_EVENT": {
        "pdf_page": 207,
        "anchor_tokens": ["四川长虹新能源科技股份有限公司", "不再将长虹新能源公司纳入合并"],
        "value_expression": {"operator": "BOOLEAN_TOKEN_PRESENCE", "tokens": ["本公司不再持有长虹新能源公司股权"]},
    },
}


def build_page_extraction_receipts(field_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for record in field_records:
        if record.get("status") != "OBSERVED":
            continue
        field_id = record["field_id"]
        binding = PAGE_VALUE_BINDINGS.get(field_id)
        if binding is None:
            raise ValueError(f"round9 observed field lacks page-value binding: {field_id}")
        receipt = {
            "schema_version": measurement_acquisition.PAGE_EXTRACTION_RECEIPT_SCHEMA_VERSION,
            "receipt_id": f"PAGEEXTRACT:R9:{field_id}",
            "field_id": field_id,
            "source_id": record["source"]["source_id"],
            "pdf_page": binding["pdf_page"],
            "unit": record["unit"],
            "anchor_tokens": deepcopy(binding["anchor_tokens"]),
            "value_expression": deepcopy(binding["value_expression"]),
            "object_class": "ENTERPRISE_PAGE_EXTRACTION_RECEIPT",
            "claim_class": "PDF_PAGE_VALUE_BINDING_ONLY",
        }
        if binding.get("supporting_pdf_pages"):
            receipt["supporting_pdf_pages"] = deepcopy(binding["supporting_pdf_pages"])
        receipts.append(receipt)
    return receipts


def settle_custodian_field_records(
    package: dict[str, Any], contract: dict[str, Any], field_records: list[dict[str, Any]], *,
    page_extraction_receipts: list[dict[str, Any]], local_pdf_path: Path,
    registry_db: Path, registered_at: str, observed_at: str, settled_at: str,
) -> dict[str, Any]:
    source_validation = validate_source_bound_measurement_contract(contract)
    if not source_validation["valid"]:
        raise ValueError("round9 source-bound contract invalid: " + "; ".join(source_validation["findings"]))
    authorization = build_outcome_authorization(package, contract)
    authorization_validation = measurement_acquisition.validate_enterprise_outcome_access_authorization(
        authorization, measurement_contract=contract,
    )
    if not authorization_validation["valid"]:
        raise ValueError("round9 outcome authorization invalid: " + "; ".join(authorization_validation["findings"]))
    inventory = build_source_inventory(
        package, contract, local_pdf_path=local_pdf_path, registered_at=registered_at,
    )
    inventory_validation = measurement_acquisition.validate_registered_local_pdf_inventory(
        inventory, measurement_contract=contract, outcome_access_authorization=authorization,
    )
    if not inventory_validation["valid"]:
        raise ValueError("round9 source inventory invalid: " + "; ".join(inventory_validation["findings"]))
    page_validation = measurement_acquisition.validate_page_bound_enterprise_field_records(
        field_records, page_extraction_receipts,
        measurement_contract=contract, inventory=inventory,
    )
    if not page_validation["valid"]:
        raise ValueError("round9 page extraction receipts invalid: " + "; ".join(page_validation["findings"]))
    acquisition_result = measurement_acquisition.acquire_outcome_measurements_from_field_records(
        contract, inventory, field_records, outcome_access_authorization=authorization,
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
        settlement.pop("persisted", None)
        settlement.pop("idempotent", None)
        replayed = enterprise_control.replay_enterprise_settlement(OUTCOME_SETTLEMENT_ID)
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    if replayed != settlement:
        raise ValueError("round9 settlement differs from canonical replay")
    return {
        "source_binding_receipt": build_source_binding_receipt(),
        "source_bound_measurement_contract": deepcopy(contract),
        "authorization": authorization,
        "inventory": inventory,
        "field_records": deepcopy(field_records),
        "page_extraction_receipts": deepcopy(page_extraction_receipts),
        "acquisition_result": acquisition_result,
        "settlement": settlement,
    }


def _canonical_round9_settlement(
    settlement: dict[str, Any], *, registry_db: Path,
) -> dict[str, Any]:
    previous_registry = reconstruction.CANONICAL_REGISTRY_PATH
    reconstruction.CANONICAL_REGISTRY_PATH = registry_db
    try:
        canonical = enterprise_control.replay_enterprise_settlement(settlement["settlement_id"])
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    if canonical != settlement:
        raise ValueError("round9 settlement differs from canonical replay")
    return canonical


def build_method_feedback_invalidation(method_receipt: dict[str, Any]) -> dict[str, Any]:
    if method_receipt.get("resolution_status") != "MODEL_ERROR":
        raise ValueError("round9 invalidation requires frozen resolver MODEL_ERROR")
    return {
        "schema_version": "enterprise-judgment-method-feedback-invalidation.v1",
        "invalidation_id": "METHOD-INVALIDATION:R9:CN600839:FY2019:V1",
        "method_resolution_ref": method_receipt["resolution_id"],
        "status": "METHOD_COMPARISON_INVALID_MODEL_ERROR",
        "root_causes": ["MODEL"],
        "economic_impact": (
            "Round 9 cannot establish whether the simple Baseline or the eight-dimensional method "
            "would have produced the better investment treatment under an unchanged blind resolver."
        ),
        "preserved_scope": [
            "OUTCOME_SOURCE_BINDING",
            "FIELD_LEVEL_ACQUISITION",
            "CANONICAL_OUTCOME_SETTLEMENT",
            "INVESTOR_FACT_READOUT",
        ],
        "prohibited_claims": [
            "METHOD_FEEDBACK_COMPLETED",
            "NO_MATERIAL_METHOD_ADVANTAGE_PROVED",
            "AVOIDED_ERROR",
            "MATERIAL_IMPROVEMENT",
            "METHOD_TRANSFER",
        ],
        "remediation": (
            "Freeze a corrected scalar resolver and unique treatment-delta accounting in a new method "
            "epoch, then test it only on a different unseen company-cutoff."
        ),
        "rights": deepcopy(RIGHTS),
        "object_class": "METHOD_FEEDBACK_INVALIDATION",
        "claim_class": "POST_OUTCOME_MODEL_ERROR_BOUNDARY",
        "allowed_outputs": ["OUTCOME_SETTLED_CLOSEOUT", "NEW_METHOD_EPOCH", "RESEARCH_AGENDA"],
    }


def build_next_method_epoch_requirements() -> dict[str, Any]:
    return {
        "schema_version": "enterprise-judgment-method-epoch-requirements.v1",
        "method_epoch_id": NEXT_METHOD_EPOCH_ID,
        "state": "DESIGN_REQUIREMENTS_FROZEN_NOT_SAMPLE_VALIDATED",
        "excluded_validation_samples": [{"company_id": COMPANY_ID, "cutoff_at": CUTOFF_AT}],
        "resolver_requirements": [
            "Every dimension output must be a JSON scalar or a declared typed object.",
            "A treatment change must carry one unique treatment_delta_id.",
            "Several dimensions may explain one treatment delta, but method_advantage_count must remain one.",
            "Baseline and Enhanced resolution rules must be committed before outcome identity or content access.",
        ],
        "review_requirements": {
            "input_mode": "EXTERNAL_ARTIFACT_ONLY",
            "implementation_must_not_generate_review_decision": True,
            "completion_without_external_review": "REJECT",
        },
        "rights": deepcopy(RIGHTS),
        "object_class": "METHOD_EPOCH_DESIGN_REQUIREMENTS",
        "claim_class": "POST_ROUND9_REMEDIATION_ONLY",
        "allowed_outputs": ["NEW_UNSEEN_PREOUTCOME_FREEZE"],
    }


def build_next_epoch_treatment_deltas(
    *, baseline_operating: str, enhanced_operating: str,
    portfolio_rival: str, portfolio_event: str,
) -> list[dict[str, Any]]:
    if baseline_operating == enhanced_operating:
        return []
    if portfolio_rival != "MATERIAL" and portfolio_event != "OBSERVED_YES":
        return []
    return [{
        "treatment_delta_id": "TREATMENT-DELTA:PORTFOLIO-SCOPE:OPERATING:V2",
        "baseline_treatment": baseline_operating,
        "enhanced_treatment": enhanced_operating,
        "explanatory_dimensions": [
            "ADAPTATION_PERMANENT_LOSS",
            "STRONGEST_ALTERNATIVE_EXPLANATION",
        ],
        "method_advantage_count": 1,
    }]


def validate_external_postoutcome_review(
    package: dict[str, Any], settlement: dict[str, Any], method_receipt: dict[str, Any],
    invalidation: dict[str, Any], review: Any,
) -> dict[str, Any]:
    item = review if isinstance(review, dict) else {}
    findings: list[str] = []
    expected_refs = {
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "method_resolution_ref": method_receipt["resolution_id"],
        "method_invalidation_ref": invalidation["invalidation_id"],
    }
    for key, expected in expected_refs.items():
        if item.get(key) != expected:
            findings.append(f"external_review_{key}_mismatch")
    reviewer_id = item.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        findings.append("external_reviewer_id_required")
    elif reviewer_id in set(package["roles"].values()):
        findings.append("external_reviewer_conflicts_with_training_role")
    if item.get("review_status") != "NEEDS_REVISION":
        findings.append("round9_model_error_requires_needs_revision_review")
    if item.get("outcome_settlement_status") != "ACCEPTED":
        findings.append("external_review_must_state_outcome_settlement_status")
    if item.get("method_feedback_status") != "REJECTED_MODEL_ERROR":
        findings.append("external_review_must_reject_method_feedback_model_error")
    review_findings = item.get("findings")
    required_finding_keys = {
        "finding_id", "priority", "root_causes", "economic_impact", "missing_facts",
        "prohibited_assumptions", "remediation", "acceptance_criteria",
    }
    if not isinstance(review_findings, list) or not review_findings:
        findings.append("external_review_material_findings_required")
    else:
        for index, finding in enumerate(review_findings):
            if not isinstance(finding, dict) or not required_finding_keys.issubset(finding):
                findings.append(f"external_review_finding_{index}_incomplete")
    if item.get("rights") != RIGHTS:
        findings.append("external_review_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings}


def build_outcome_closeout_receipt(
    package: dict[str, Any], settlement: dict[str, Any], method_receipt: dict[str, Any],
    invalidation: dict[str, Any], review: dict[str, Any], *, registry_db: Path,
) -> dict[str, Any]:
    settlement = _canonical_round9_settlement(settlement, registry_db=registry_db)
    method_validation = validate_method_resolution_receipt(
        method_receipt, canonical_settlement=settlement,
    )
    if not method_validation["valid"]:
        raise ValueError("round9 method-error receipt does not replay frozen resolver")
    if invalidation != build_method_feedback_invalidation(method_receipt):
        raise ValueError("round9 method invalidation does not replay")
    review_validation = validate_external_postoutcome_review(
        package, settlement, method_receipt, invalidation, review,
    )
    if not review_validation["valid"]:
        raise ValueError("round9 external review invalid: " + "; ".join(review_validation["findings"]))
    return {
        "schema_version": "enterprise-judgment-round9-outcome-closeout.v1",
        "completion_id": "R9CLOSEOUT:CN600839:20180930:FY2019:V2",
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "method_resolution_ref": method_receipt["resolution_id"],
        "method_invalidation_ref": invalidation["invalidation_id"],
        "independent_review_ref": review["review_id"],
        "company_id": COMPANY_ID,
        "cutoff_at": CUTOFF_AT,
        "status": "ROUND9_OUTCOME_SETTLED_METHOD_COMPARISON_INVALID",
        "method_conclusion": METHOD_CONCLUSION,
        "investor_summary": (
            "FY2019 outcome facts support separating consolidated growth from white-goods economics, but "
            "the blind method comparison is invalid because the frozen resolver contains a model error."
        ),
        "result_period_context": [
            {
                "metric": "WHITE_GOODS_REVENUE_YOY",
                "value": -6.70,
                "unit": "PERCENT",
                "source_id": OUTCOME_SOURCE_ID,
                "pdf_page": 14,
                "scoring_role": "NON_SCORING_CONTEXT",
            },
            {
                "metric": "WHITE_GOODS_GROSS_MARGIN_YOY_CHANGE",
                "value": 0.17,
                "unit": "PERCENTAGE_POINT",
                "source_id": OUTCOME_SOURCE_ID,
                "pdf_page": 14,
                "scoring_role": "NON_SCORING_CONTEXT",
            },
            {
                "metric": "GROUP_OCF_FY2018_COMPARATIVE",
                "value": 4_424_454_303.24,
                "unit": "RMB",
                "source_id": OUTCOME_SOURCE_ID,
                "pdf_page": 81,
                "scoring_role": "NON_SCORING_CONTEXT",
            },
        ],
        "proved": [
            "FY2019 consolidated operating revenue was RMB88.79 billion and cleared the frozen FY2017-anchor increase threshold.",
            "Air-conditioner and refrigerator revenue was RMB14.01 billion and gross margin was about 22.36%; both were inside frozen bands relative to the FY2017 anchor, not year-on-year stability claims.",
            "The annual report separately shows FY2019 white-goods revenue down 6.70% year on year and gross margin up 0.17 percentage point.",
            "FY2019 consolidated OCF was RMB1.57 billion versus about RMB4.42 billion in FY2018; its frozen label is relative to FY2017 only.",
            "The smart-white-goods industrial park reached full production, and the issuer disposed of its controlling New Energy stake.",
            "Ordinary-share owner cash remains UNKNOWN.",
        ],
        "not_proved": [
            "Either method produced the better investment treatment in a valid blind comparison.",
            "Implemented actions caused better white-goods execution, customer preference or durable advantage.",
            "Consolidated cash represents residual ordinary-share owner cash.",
            "The portfolio disposal increased or reduced permanent-loss risk by itself.",
            "Any method transfer, CJO, valuation, report conclusion, buy band or investment action.",
        ],
        "next_research_actions": [
            "Freeze the corrected V2 method epoch before selecting a different unseen company-cutoff.",
            "Count one treatment change once even when several dimensions explain it.",
            "Require an external review artifact as input; implementation may generate only a review candidate.",
            "Keep volume, price, customer share and ordinary-share owner cash as priority evidence targets.",
        ],
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_ROUND_OUTCOME_CLOSEOUT",
        "claim_class": "REAL_OUTCOME_SETTLED_METHOD_FEEDBACK_INVALID",
        "allowed_outputs": ["NEW_METHOD_EPOCH", "RESEARCH_AGENDA"],
    }


def build_investor_readout(completion: dict[str, Any]) -> str:
    if completion.get("status") != "ROUND9_OUTCOME_SETTLED_METHOD_COMPARISON_INVALID":
        raise ValueError("round9 investor readout requires outcome-only closeout")
    return """# 家电 Round 9 投资者读出

> 状态：`OUTCOME_SETTLED / METHOD_COMPARISON_INVALID_MODEL_ERROR`
>
> 公司与 cutoff：四川长虹 `CN:600839`，`2018-09-30`
>
> 权限：无方法迁移、CJO、估值、报告或投资权限

## 可信的企业结果

- FY2019 集团营业收入约 `887.93 亿元`，相对事前冻结的 FY2017 锚跨过上升阈值。
- 空调冰箱收入约 `140.08 亿元`、毛利率约 `22.36%`。相对 FY2017 锚处于冻结稳定区间，但这不表示 FY2019 同比稳定：年报披露收入同比下降 `6.70%`，毛利率同比上升 `0.17` 个百分点。
- FY2019 集团经营现金约 `15.66 亿元`，而 FY2018 约为 `44.24 亿元`。冻结的稳定标签只相对 FY2017 锚，不能用来描述 FY2019 同比现金表现。
- 智能白电工业园实现全面投产，公司同时处置长虹新能源控制权；普通股 owner cash 仍为 `UNKNOWN`。

## 对企业判断的帮助

集团增长不能直接代表白电业务变强。核心产品收入同比下降、集团组合发生变化，而工业园投产只证明管理层完成了建设，不能证明客户多买、公司有定价权、毛利改善或资本投入产生了良好股东回报。

因此研究顺序已经更清楚：先拆集团组合与核心产品，再检查量、价、客户份额和普通股现金，最后才评价执行能力、竞争优势和永久损失。

## 为什么本轮不能评价方法胜负

独立审阅发现，事前冻结的解析器把“已实施行动”错误输出为 tuple。结果揭示后曾在工作树中修正该错误，这会破坏盲测边界。现在已恢复事前版本，并将本轮诚实结算为 `MODEL_ERROR`：真实公司结果可以保留，但不能声称八维方法更好，也不能声称已经证明两种方法没有差异。

## 下一步

下一轮使用新的方法 epoch：解析器必须在结果前冻结，同一个投资处理变化只能计一次，独立 reviewer 必须从外部提交审阅工件。四川长虹不得再作为修正版的未见验证样本。
"""


def build_postoutcome_candidate_artifacts(
    *, local_pdf_path: Path, registry_db: Path,
) -> dict[str, Any]:
    freeze = build_preoutcome_freeze()
    package = freeze["canonical_preoutcome_package"]
    contract = build_source_bound_measurement_contract()
    records = build_custodian_field_records(contract)
    page_receipts = build_page_extraction_receipts(records)
    artifacts = settle_custodian_field_records(
        package, contract, records,
        page_extraction_receipts=page_receipts,
        local_pdf_path=local_pdf_path,
        registry_db=registry_db,
        registered_at="2026-08-27T19:00:00+08:00",
        observed_at="2026-08-27T19:01:00+08:00",
        settled_at="2026-08-27T19:02:00+08:00",
    )
    settlement = artifacts["settlement"]
    method_receipt = build_method_resolution_receipt(
        _canonical_round9_settlement(settlement, registry_db=registry_db),
        resolved_at="2026-08-27T19:03:00+08:00",
    )
    invalidation = build_method_feedback_invalidation(method_receipt)
    return {
        **artifacts,
        "method_resolution_receipt": method_receipt,
        "method_feedback_invalidation": invalidation,
        "next_method_epoch_requirements": build_next_method_epoch_requirements(),
    }


def build_postoutcome_artifacts(
    *, local_pdf_path: Path, registry_db: Path, external_review: dict[str, Any],
) -> dict[str, Any]:
    freeze = build_preoutcome_freeze()
    package = freeze["canonical_preoutcome_package"]
    artifacts = build_postoutcome_candidate_artifacts(
        local_pdf_path=local_pdf_path, registry_db=registry_db,
    )
    completion = build_outcome_closeout_receipt(
        package, artifacts["settlement"], artifacts["method_resolution_receipt"],
        artifacts["method_feedback_invalidation"], external_review,
        registry_db=registry_db,
    )
    return {
        **artifacts,
        "independent_postoutcome_review": deepcopy(external_review),
        "completion_receipt": completion,
        "investor_readout": build_investor_readout(completion),
    }


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


def materialize_postoutcome(
    output_dir: Path, *, local_pdf_path: Path, registry_db: Path,
    external_review_path: Path,
) -> dict[str, Any]:
    external_review = json.loads(external_review_path.read_text(encoding="utf-8"))
    artifacts = build_postoutcome_artifacts(
        local_pdf_path=local_pdf_path, registry_db=registry_db,
        external_review=external_review,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "09_source_binding_receipt.json": "source_binding_receipt",
        "10_source_bound_measurement_contract.json": "source_bound_measurement_contract",
        "11_outcome_access_authorization.json": "authorization",
        "12_outcome_source_inventory.json": "inventory",
        "13_custodian_field_records.json": "field_records",
        "13a_page_extraction_receipts.json": "page_extraction_receipts",
        "14_outcome_acquisition_result.json": "acquisition_result",
        "15_outcome_settlement.json": "settlement",
        "16_method_resolution_receipt.json": "method_resolution_receipt",
        "17_method_feedback_invalidation.json": "method_feedback_invalidation",
        "18_independent_postoutcome_review.json": "independent_postoutcome_review",
        "19_round9_completion_receipt.json": "completion_receipt",
        "21_next_method_epoch_requirements.json": "next_method_epoch_requirements",
    }
    for name, key in files.items():
        _write_json(output_dir / name, artifacts[key])
    (output_dir / "20_investor_readout.md").write_text(
        artifacts["investor_readout"], encoding="utf-8",
    )
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-preoutcome-dir")
    parser.add_argument("--write-postoutcome-dir")
    parser.add_argument("--local-pdf-path")
    parser.add_argument("--registry-db")
    parser.add_argument("--external-review-path")
    args = parser.parse_args()
    freeze = build_preoutcome_freeze()
    result = validate_preoutcome_freeze(freeze)
    if args.write_preoutcome_dir and result["valid"]:
        materialize_preoutcome(Path(args.write_preoutcome_dir))
    if args.write_postoutcome_dir and result["valid"]:
        if not args.local_pdf_path or not args.registry_db or not args.external_review_path:
            parser.error(
                "--write-postoutcome-dir requires --local-pdf-path, --registry-db and "
                "--external-review-path"
            )
        materialize_postoutcome(
            Path(args.write_postoutcome_dir),
            local_pdf_path=Path(args.local_pdf_path),
            registry_db=Path(args.registry_db),
            external_review_path=Path(args.external_review_path),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
