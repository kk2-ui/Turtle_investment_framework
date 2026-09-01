#!/usr/bin/env python3
"""Second result-unseen appliance E2 episode: Joyoung at 2018-09-30.

This appliance-only adapter applies three lessons from the completed Supor
iteration before any Joyoung FY2018 outcome is opened:

* interpret misses by their economic direction;
* compare the disclosed product boundary with issuer growth;
* require the outcome report's prior-period comparatives to bridge back to the
  frozen baseline before making a same-scope operating inference.

The module reuses the Minimal Historical Episode controller and runner.  It
does not create a settlement engine, method release, Comparative episode, CJO,
valuation, report or investment authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from typing import Any

from scripts import enterprise_judgment_appliance_continuous_training as prior
from scripts import minimal_historical_episode as minimal
from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner


SCHEMA_VERSION = "enterprise-judgment-appliance-four-stage-round2.v1"
RESOLUTION_SCHEMA_VERSION = "enterprise-judgment-appliance-e2-resolution-contract.v2"
EPISODE_ID = "APPLIANCE-R12:CN002242:20180930:V1"
RESOLUTION_CONTRACT_ID = "APPLIANCE:E2:CN002242:20180930:RESOLUTION:V2"
COMPANY_ID = "CN:002242"
ISSUER_ID = "ISSUER:CN:002242"
SECURITY_CODE = "002242"
ORGANIZATION_ID = "9900004732"
CUTOFF_AT = "2018-09-30T23:59:59+08:00"
FROZEN_AT = "2026-08-29T09:00:00+08:00"
OUTCOME_PERIOD_END = "2018-12-31"
SOURCE_ID = "CNINFO:002242:ANN:20180421:1204680243"
SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2018-04-21/1204680243.PDF"
CURATOR_ID = "ROLE:APPLIANCE-R12:CN002242:STATIC_EVIDENCE_CURATOR_FUNCTION"
FORECASTER_ID = "ROLE:APPLIANCE-R12:CN002242:FORECASTER_FUNCTION"
CUSTODIAN_ID = "ROLE:APPLIANCE-R12:CN002242:INDEPENDENT_OUTCOME_CUSTODIAN"
RIGHTS = deepcopy(prior.RIGHTS)

_WHITESPACE = re.compile(r"\s+")
_PAGE_REF = re.compile(r"\bPDF\s+p\.(\d+)\b", re.IGNORECASE)

_LOCAL_SOURCE_RULES = {
    "CONSOLIDATED_REVENUE_RMB": {
        "page": 60,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002242",
        "field_ref": "PDF p.60; consolidated income statement; 营业收入; FY2017 current-period value",
        "label": "营业收入",
        "exact_quote": "其中：营业收入                     7,247,524,855.71    7,314,804,589.33",
        "numeric_value": Decimal("7247524855.71"),
    },
    "PRODUCT_REVENUE_RMB:食品加工机系列": {
        "page": 13,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002242:DISCLOSED_PRODUCT_CATEGORY:食品加工机系列",
        "field_ref": "PDF p.13; product-category revenue composition; 食品加工机系列; FY2017 current-period value",
        "label": "食品加工机系列",
        "exact_quote": "食品加工机系列     3,149,788,827.00       43.46%     3,063,179,010.42        41.88%      2.83%",
        "numeric_value": Decimal("3149788827.00"),
    },
    "CONSOLIDATED_OPERATING_CASH_FLOW_RMB": {
        "page": 64,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002242",
        "field_ref": "PDF p.64; consolidated cash-flow statement; 经营活动产生的现金流量净额; FY2017 current-period value",
        "label": "经营活动产生的现金流量净额",
        "exact_quote": "经营活动产生的现金流量净额                      48,903,264.69    1,006,736,608.98",
        "numeric_value": Decimal("48903264.69"),
    },
}


class ApplianceRound2Error(ValueError):
    """The second appliance episode crossed a frozen identity or PIT bound."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finite_decimal(value: Any, *, field: str) -> Decimal:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ApplianceRound2Error(f"{field}_must_be_finite_numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ApplianceRound2Error(f"{field}_must_be_finite_numeric") from exc
    if not parsed.is_finite():
        raise ApplianceRound2Error(f"{field}_must_be_finite_numeric")
    return parsed


def _normalized(value: str) -> str:
    return _WHITESPACE.sub("", value).replace(",", "").replace("，", "")


def build_source_packet() -> dict[str, Any]:
    return {
        "source_packet_id": "APPLIANCE-R12:CN002242:FY2017:PREOUTCOME-SOURCE:V1",
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "curator_id": CURATOR_ID,
        "source": {
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "published_at": "2018-04-21",
            "period_end": "2017-12-31",
            "source_type": "OFFICIAL_STATIC_CNINFO_ANNUAL_REPORT",
            "physical_pages": [6, 9, 12, 13, 21, 26, 36, 37, 38, 45, 60, 64, 73, 129, 131],
        },
        "facts": [
            {"fact_id": "R12:F1:CHANNEL_ACTION", "status": "OBSERVED_ACTION_RESULT_UNKNOWN", "field_ref": "PDF p.9 and p.12", "statement": "FY2017 channel optimization, Shopping Mall entry, landmark-store renovation and online/offline integration were described as implemented; incremental results were not identified."},
            {"fact_id": "R12:F2:PRODUCT_REVENUE", "status": "OBSERVED", "field_ref": "PDF p.13", "statement": "Food-processing-machine revenue was RMB 3.150bn, up 2.83%, and was the largest eligible named product row."},
            {"fact_id": "R12:F3:ISSUER_REVENUE", "status": "OBSERVED", "field_ref": "PDF p.60", "statement": "FY2017 listed-consolidated revenue was RMB 7.248bn, slightly below the report's prior comparative."},
            {"fact_id": "R12:F4:ISSUER_CASH", "status": "OBSERVED_NOT_OWNER_CASH", "field_ref": "PDF p.64", "statement": "FY2017 issuer operating cash flow was RMB 48.9m versus RMB 1.007bn in the reported comparative; it is not ordinary-share owner cash."},
            {"fact_id": "R12:F5:COMPETITION", "status": "OBSERVED_GENERIC_RIVAL_UNKNOWN", "field_ref": "PDF p.21", "statement": "Entry, imitation and channel competition could compress margins; no named strongest rival was disclosed."},
            {"fact_id": "R12:F6:PERIMETER", "status": "OBSERVED_BRIDGE_UNKNOWN", "field_ref": "PDF p.73, p.129 and p.131", "statement": "One subsidiary was deconsolidated and minority interests changed; no constant-perimeter revenue or OCF bridge was disclosed."},
            {"fact_id": "R12:F7:RESTATEMENT", "status": "OBSERVED_LOCAL", "field_ref": "PDF p.6 and p.26", "statement": "No headline prior-period restatement was required, while a presentation reclassification affected asset-disposal reporting rather than the three frozen fields."},
        ],
        "outcome_content_read": False,
        "allowed_outputs": ["PREOUTCOME_EVIDENCE_ONLY"],
        "rights": deepcopy(RIGHTS),
    }


def _chain(spec: dict[str, Any]) -> dict[str, Any]:
    prefix = spec["chain_id"]
    decision = {
        "schema_version": minimal.DECISION_CONTRACT_SCHEMA_VERSION,
        "decision_contract_id": f"MHE:DECISION:{prefix}",
        "decision_contract_version": 1,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "metric_id": spec["metric_id"],
        "window_id": "ONE_YEAR",
        "decision_purpose": minimal.DECISION_PURPOSE,
        "roles": {"forecaster_id": FORECASTER_ID, "custodian_id": CUSTODIAN_ID},
        "object_class": "MINIMAL_HISTORICAL_DECISION_CONTRACT",
        "claim_class": "ONE_METRIC_DIRECTIONAL_DECISION_SCOPE",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    decision_ref = {"decision_contract_id": decision["decision_contract_id"], "decision_contract_version": 1}
    route = {
        "schema_version": minimal.TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION,
        "technical_route_identity_id": f"MHE:ROUTE:{prefix}",
        "technical_route_identity_version": 1,
        "decision_contract_ref": decision_ref,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "security_code": SECURITY_CODE,
        "organization_id": ORGANIZATION_ID,
        "resolver_endpoint": minimal.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT,
        "resolver_version": minimal.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION,
        "observed_at": FROZEN_AT,
        "object_class": "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY",
        "claim_class": "TECHNICAL_ROUTE_IDENTITY",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    route_ref = {"technical_route_identity_id": route["technical_route_identity_id"], "technical_route_identity_version": 1}
    contract = {
        "schema_version": minimal.MEASUREMENT_CONTRACT_SCHEMA_VERSION,
        "measurement_contract_id": f"MHE:CONTRACT:{prefix}",
        "measurement_contract_version": 2,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "metric_id": spec["metric_id"],
        "window_id": "ONE_YEAR",
        "decision_contract_ref": decision_ref,
        "outcome_period_end": OUTCOME_PERIOD_END,
        "responsibility_boundary": spec["boundary"],
        "unit": "RMB",
        "settlement_tolerance": spec["tolerance"],
        "technical_route_identity_ref": route_ref,
        "outcome_acquisition_route": {
            "provider": minimal.CNINFO_OUTCOME_ROUTE_PROVIDER,
            "provider_version": minimal.CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION,
            "security_code": SECURITY_CODE,
            "organization_id": ORGANIZATION_ID,
            "tab_name": minimal.CNINFO_OUTCOME_ROUTE_TAB,
            "announcement_category": minimal.CNINFO_OUTCOME_ROUTE_CATEGORY,
            "begin_date": "2019-01-01",
            "end_date": "2019-06-30",
            "page_size": 30,
            "static_pdf_url_policy": minimal.CNINFO_OUTCOME_ROUTE_URL_POLICY,
            "annual_report_version_policy": minimal.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
        },
        "roles": deepcopy(decision["roles"]),
        "object_class": "MINIMAL_HISTORICAL_MEASUREMENT_CONTRACT",
        "claim_class": "ONE_METRIC_PRE_OUTCOME_SCOPE",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    contract_ref = {"measurement_contract_id": contract["measurement_contract_id"], "measurement_contract_version": 2}
    evidence = {
        "schema_version": minimal.STATIC_EVIDENCE_SCHEMA_VERSION,
        "evidence_receipt_id": f"MHE:EVIDENCE:{prefix}",
        "evidence_receipt_version": 1,
        "measurement_contract_ref": contract_ref,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "metric_id": spec["metric_id"],
        "window_id": "ONE_YEAR",
        "curator_id": CURATOR_ID,
        "source": {
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "source_type": minimal.OFFICIAL_STATIC_FILING,
            "published_at": "2018-04-21",
            "issuer_id": ISSUER_ID,
            "metric_id": spec["metric_id"],
            "responsibility_boundary": spec["boundary"],
            "unit": "RMB",
            "field_ref": spec["field_ref"],
            "numeric_value": spec["baseline_value"],
        },
        "object_class": "MINIMAL_HISTORICAL_STATIC_EVIDENCE",
        "claim_class": "CUTOFF_VISIBLE_OFFICIAL_FIELD",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    prediction = {
        "schema_version": minimal.PREDICTION_SCHEMA_VERSION,
        "prediction_id": f"MHE:PREDICTION:{prefix}",
        "measurement_contract_ref": contract_ref,
        "evidence_receipt_ref": {"evidence_receipt_id": evidence["evidence_receipt_id"], "evidence_receipt_version": 1},
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "metric_id": spec["metric_id"],
        "window_id": "ONE_YEAR",
        "forecaster_id": FORECASTER_ID,
        "predicted_direction": spec["predicted_direction"],
        "object_class": "MINIMAL_HISTORICAL_PREDICTION",
        "claim_class": "ONE_METRIC_DIRECTIONAL_PREDICTION",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    verification = {
        "schema_version": runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": {"object_type": "STATIC_EVIDENCE", "object_id": evidence["evidence_receipt_id"], "object_version": 1},
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "exact_quote": spec["exact_quote"],
        "numeric_value": spec["baseline_value"],
        "unit": "RMB",
        "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
        "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
    }
    return {
        "metric_role": spec["metric_role"],
        "decision_contract": decision,
        "technical_route_identity": route,
        "measurement_contract": contract,
        "static_evidence": evidence,
        "prediction": prediction,
        "source_verification_input": verification,
    }


def build_minimal_chains() -> list[dict[str, Any]]:
    specs = [
        {"chain_id": "APPLIANCE-R12:CN002242:FY2018:ISSUER_REVENUE:V1", "metric_role": "ISSUER_SCALE_CONTEXT", "metric_id": "CONSOLIDATED_REVENUE_RMB", "boundary": _LOCAL_SOURCE_RULES["CONSOLIDATED_REVENUE_RMB"]["boundary"], "field_ref": _LOCAL_SOURCE_RULES["CONSOLIDATED_REVENUE_RMB"]["field_ref"], "exact_quote": _LOCAL_SOURCE_RULES["CONSOLIDATED_REVENUE_RMB"]["exact_quote"], "baseline_value": 7247524855.71, "predicted_direction": "STABLE", "tolerance": 362376242.7855},
        {"chain_id": "APPLIANCE-R12:CN002242:FY2018:FOOD_PROCESSOR_REVENUE:V1", "metric_role": "PRODUCT_RELATIVE_DISCRIMINATOR", "metric_id": "PRODUCT_REVENUE_RMB:食品加工机系列", "boundary": _LOCAL_SOURCE_RULES["PRODUCT_REVENUE_RMB:食品加工机系列"]["boundary"], "field_ref": _LOCAL_SOURCE_RULES["PRODUCT_REVENUE_RMB:食品加工机系列"]["field_ref"], "exact_quote": _LOCAL_SOURCE_RULES["PRODUCT_REVENUE_RMB:食品加工机系列"]["exact_quote"], "baseline_value": 3149788827.0, "predicted_direction": "INCREASE", "tolerance": 157489441.35},
        {"chain_id": "APPLIANCE-R12:CN002242:FY2018:ISSUER_OCF:V1", "metric_role": "SIGNED_ISSUER_CASH_CONTEXT_NOT_OWNER_CASH", "metric_id": "CONSOLIDATED_OPERATING_CASH_FLOW_RMB", "boundary": _LOCAL_SOURCE_RULES["CONSOLIDATED_OPERATING_CASH_FLOW_RMB"]["boundary"], "field_ref": _LOCAL_SOURCE_RULES["CONSOLIDATED_OPERATING_CASH_FLOW_RMB"]["field_ref"], "exact_quote": _LOCAL_SOURCE_RULES["CONSOLIDATED_OPERATING_CASH_FLOW_RMB"]["exact_quote"], "baseline_value": 48903264.69, "predicted_direction": "STABLE", "tolerance": 9780652.938},
    ]
    return [_chain(spec) for spec in specs]


def _enhanced_dimensions() -> list[dict[str, Any]]:
    rows = {
        "INITIAL_CONDITIONS_AND_BOUNDARY": ("OBSERVED_WITH_BRIDGE_UNKNOWN", "Issuer, named-product and ordinary-share cash boundaries are separate; the disposed subsidiary prevents assuming a constant issuer perimeter."),
        "IMPLEMENTED_MANAGEMENT_ACTION": ("OBSERVED_ACTION_RESULT_UNKNOWN", "Channel optimization, Shopping Mall entry, landmark-store renovation and online/offline integration were implemented, but incremental contribution is unknown."),
        "EXECUTION_CAPABILITY": ("OBSERVED_LOCAL", "Stores and integration work were undertaken; the report does not provide a frozen execution KPI that can establish effectiveness."),
        "CUSTOMER_AND_COMPETITIVE_RESPONSE": ("UNKNOWN", "Product revenue is a response signal, not loyalty, share or action attribution; the strongest named rival is unknown."),
        "UNIT_ECONOMICS": ("UNKNOWN", "No result-period product margin cell is frozen; product revenue cannot substitute for unit economics."),
        "WORKING_CAPITAL_CASH_AND_CAPITAL": ("UNKNOWN_OWNER_CASH", "Issuer OCF was volatile and is not ordinary-share owner cash; its future deviation must be interpreted by sign."),
        "ADAPTATION_AND_PERMANENT_LOSS": ("CONDITIONAL", "Channel adaptation is visible, while competition, imitation and a missing constant-perimeter bridge remain loss-path risks."),
        "STRONGEST_ALTERNATIVE_EXPLANATION": ("OBSERVED_GENERIC_RIVAL", "Category conditions, common channel migration, product mix and perimeter change can reproduce later movements without a company-specific action effect."),
    }
    return [{"dimension_id": dimension, "status": rows[dimension][0], "judgment": rows[dimension][1]} for dimension in prior.DIMENSIONS]


def build_preoutcome_episode() -> dict[str, Any]:
    packet = build_source_packet()
    fact_refs = [row["fact_id"] for row in packet["facts"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": EPISODE_ID,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "frozen_at": FROZEN_AT,
        "selection_rule": "SECOND_FIXED_RESULT_UNSEEN_COMPANY_IN_APPLIANCE_ROSTER",
        "method_identity": "MODEL_MEMORY_MITIGATED_HISTORICAL_APPLIANCE_TRAINING",
        "source_packet": packet,
        "same_fact_budget": {"fact_budget_id": "APPLIANCE-R12:CN002242:FACT-BUDGET:V1", "fact_refs": fact_refs},
        "fair_baseline": {
            "treatment": "WATCH_STABLE_ISSUER_AND_CHANNEL_EXECUTION",
            "resolution_rule": "Treat issuer scale and a disclosed product row as operating context; do not claim customer response, owner cash or action effectiveness.",
            "fact_refs": fact_refs,
        },
        "cumulative_enhanced": {
            "treatment": "CONDITIONAL_PRODUCT_RELATIVE_CASH_AND_BRIDGE_UNDERWRITING",
            "resolution_rule": "Require the product category to outperform issuer growth, interpret cash misses by economic sign, and pass the prior-period bridge before a same-scope mechanism reading.",
            "applied_learning_change_ids": [
                "APPLIANCE:R11:LEARNING:SIGNED_MISS_SEMANTICS",
                "APPLIANCE:R11:LEARNING:PRODUCT_RELATIVE_TO_ISSUER",
                "APPLIANCE:R11:LEARNING:PRIOR_PERIOD_BRIDGE",
            ],
            "dimensions": _enhanced_dimensions(),
            "fact_refs": fact_refs,
        },
        "minimal_field_chains": build_minimal_chains(),
        "resolution_contract": build_resolution_contract(),
        "outcome_access": {"authorized": False, "content_read": False, "custodian_started": False},
        "review_state": "PREOUTCOME_INDEPENDENT_REVIEW_REQUIRED",
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def build_resolution_contract() -> dict[str, Any]:
    contracts = [chain["measurement_contract"] for chain in build_minimal_chains()]
    by_metric = {row["metric_id"]: row for row in contracts}
    return {
        "schema_version": RESOLUTION_SCHEMA_VERSION,
        "resolution_contract_id": RESOLUTION_CONTRACT_ID,
        "episode_ref": EPISODE_ID,
        "frozen_before_outcome_access": True,
        "field_contract_refs": [row["measurement_contract_id"] for row in contracts],
        "signed_deviation_rules": {
            "STABLE_EXPECTATION_UPWARD_MISS": "FAVORABLE_UPWARD_DEVIATION_NOT_FORECAST_SUCCESS",
            "STABLE_EXPECTATION_DOWNWARD_MISS": "ADVERSE_DOWNWARD_DEVIATION",
            "INCREASE_EXPECTATION_STABLE": "INSUFFICIENT_UPWARD_MOVE",
            "INCREASE_EXPECTATION_DECREASE": "ADVERSE_DIRECTIONAL_MISS",
        },
        "product_relative_rule": {
            "product_contract_ref": by_metric["PRODUCT_REVENUE_RMB:食品加工机系列"]["measurement_contract_id"],
            "issuer_contract_ref": by_metric["CONSOLIDATED_REVENUE_RMB"]["measurement_contract_id"],
            "formula": "(product_outcome/product_frozen_baseline-1)-(issuer_outcome/issuer_frozen_baseline-1)",
            "outperformance_threshold_percentage_points": 5.0,
            "below_negative_threshold": "PRODUCT_UNDERPERFORMS_ISSUER",
            "within_threshold": "PRODUCT_TRACKS_ISSUER_NOT_DISTINGUISHING",
            "above_positive_threshold": "PRODUCT_OUTPERFORMS_ISSUER_SIGNAL_ONLY",
            "prohibited_upgrade": "NO_CUSTOMER_LOYALTY_SHARE_OR_ACTION_CAUSALITY",
        },
        "prior_period_bridge_rule": {
            "applies_to_contract_refs": [row["measurement_contract_id"] for row in contracts],
            "required_comparison": "OUTCOME_REPORT_DISCLOSED_PRIOR_COMPARATIVE_EQUALS_FROZEN_BASELINE",
            "absolute_rmb_tolerance": 0.01,
            "failure_resolution": "UNKNOWN_PRIOR_PERIOD_SCOPE_OR_RESTATEMENT_BRIDGE",
            "dependent_claims_blocked": ["PRODUCT_RELATIVE_RESULT", "SAME_SCOPE_ISSUER_TREND", "SAME_SCOPE_CASH_TREND"],
            "mechanical_field_settlement_preserved": True,
        },
        "combined_rule": "H_A_REMAINS_UNESTABLISHED_UNLESS_PRODUCT_OUTPERFORMS_ISSUER_AND_CASH_IS_NOT_ADVERSE_AND_ALL_REQUIRED_BRIDGES_PASS",
        "evidence_ceiling": "NARROW_ASSOCIATION_AND_BOUNDARY_PROBE",
        "allowed_outputs": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def validate_preoutcome_episode(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    findings: list[str] = []
    canonical = build_preoutcome_episode()
    if item != canonical:
        findings.append("episode_must_equal_canonical_result_unseen_projection")
    for index, chain in enumerate(_items(item.get("minimal_field_chains"))):
        decision = chain.get("decision_contract")
        route = chain.get("technical_route_identity")
        contract = chain.get("measurement_contract")
        evidence = chain.get("static_evidence")
        prediction = chain.get("prediction")
        checks = (
            minimal.validate_decision_contract(decision),
            minimal.validate_technical_route_identity(route, decision_contract=decision),
            minimal.validate_measurement_contract(contract, decision_contract=decision, technical_route_identity=route),
            minimal.validate_static_evidence(evidence, measurement_contract=contract),
            minimal.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence),
        )
        for result in checks:
            findings.extend(f"minimal_field_chains[{index}]:{finding}" for finding in result["findings"])
    if item.get("outcome_access") != {"authorized": False, "content_read": False, "custodian_started": False}:
        findings.append("outcome_access_must_remain_closed")
    if item.get("rights") != RIGHTS:
        findings.append("rights_must_remain_closed")
    return {"valid": not findings, "findings": findings, "episode": deepcopy(item) if not findings else None}


def validate_resolution_contract(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    findings = [] if item == build_resolution_contract() else ["resolution_contract_must_equal_preoutcome_canonical_contract"]
    return {"valid": not findings, "findings": findings, "resolution_contract": deepcopy(item) if not findings else None}


def build_local_pdf_source_verifier(local_pdf_path: str | Path) -> runner.SourceVerifier:
    pdf_path = Path(local_pdf_path)

    def verify(source: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
        if not pdf_path.is_file():
            raise ApplianceRound2Error("registered_local_pdf_not_found")
        rule = _LOCAL_SOURCE_RULES.get(source.get("metric_id"))
        if rule is None:
            raise ApplianceRound2Error("source_metric_not_supported")
        if source.get("source_id") != SOURCE_ID or source.get("source_url") != SOURCE_URL:
            raise ApplianceRound2Error("source_identity_mismatch")
        if source.get("issuer_id") != ISSUER_ID:
            raise ApplianceRound2Error("source_issuer_mismatch")
        if source.get("responsibility_boundary") != rule["boundary"]:
            raise ApplianceRound2Error("source_responsibility_boundary_mismatch")
        if source.get("unit") != "RMB" or verification.get("unit") != "RMB":
            raise ApplianceRound2Error("source_unit_mismatch")
        if source.get("field_ref") != rule["field_ref"]:
            raise ApplianceRound2Error("source_field_ref_mismatch")
        page = _PAGE_REF.search(str(source.get("field_ref") or ""))
        if page is None or int(page.group(1)) != rule["page"]:
            raise ApplianceRound2Error("source_physical_page_mismatch")
        if verification.get("source_id") != SOURCE_ID or verification.get("source_url") != SOURCE_URL:
            raise ApplianceRound2Error("source_verification_identity_mismatch")
        if verification.get("exact_quote") != rule["exact_quote"]:
            raise ApplianceRound2Error("source_exact_quote_mismatch")
        if _finite_decimal(source.get("numeric_value"), field="source_numeric_value") != rule["numeric_value"] or _finite_decimal(verification.get("numeric_value"), field="verification_numeric_value") != rule["numeric_value"]:
            raise ApplianceRound2Error("source_numeric_value_mismatch")
        extracted = subprocess.run(
            ["pdftotext", "-f", str(rule["page"]), "-l", str(rule["page"]), "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if _normalized(rule["exact_quote"]) not in _normalized(extracted):
            raise ApplianceRound2Error("registered_pdf_exact_quote_not_found_on_declared_page")
        match = re.search(rf"{re.escape(rule['label'])}\s*(?P<current>[0-9][0-9,，]*(?:\.[0-9]+)?)", extracted)
        if match is None or Decimal(match.group("current").replace(",", "").replace("，", "")) != rule["numeric_value"]:
            raise ApplianceRound2Error("registered_pdf_metric_value_mismatch")
        return {
            "schema_version": runner.SOURCE_RECEIPT_SCHEMA_VERSION,
            "verification_state": "OPENED_REGISTERED_LOCAL_PDF_FIELD_MATCHED",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "subject_ref": deepcopy(verification["subject_ref"]),
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "field_ref": rule["field_ref"],
            "exact_quote": rule["exact_quote"],
            "numeric_value": source["numeric_value"],
            "unit": "RMB",
            "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
            "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        }

    return verify


def _counts(database: str | Path) -> dict[str, int]:
    tables = {
        "decision_contracts": control.DECISION_CONTRACT_TABLE,
        "technical_route_identities": control.TECHNICAL_ROUTE_IDENTITY_TABLE,
        "measurement_contracts": control.CONTRACT_TABLE,
        "static_evidence": control.EVIDENCE_TABLE,
        "predictions": control.PREDICTION_TABLE,
        "outcome_access": control.ACCESS_TABLE,
        "source_inventories": control.OUTCOME_SOURCE_INVENTORY_TABLE,
        "observations": control.OBSERVATION_TABLE,
        "settlements": control.SETTLEMENT_TABLE,
    }
    conn = sqlite3.connect(database)
    try:
        control.initialize(conn)
        return {name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for name, table in tables.items()}
    finally:
        conn.close()


def freeze_preoutcome(database: str | Path, *, local_pdf_path: str | Path) -> dict[str, Any]:
    episode = build_preoutcome_episode()
    validation = validate_preoutcome_episode(episode)
    if not validation["valid"]:
        raise ApplianceRound2Error("canonical_preoutcome_episode_invalid")
    verifier = build_local_pdf_source_verifier(local_pdf_path)
    field_receipts = []
    with tempfile.TemporaryDirectory(prefix="appliance-r12-preoutcome-") as temporary:
        root = Path(temporary)
        for index, chain in enumerate(episode["minimal_field_chains"]):
            paths = {name: root / f"{index}-{name}.json" for name in ("decision", "contract", "evidence", "prediction", "verification")}
            prior._write_runtime_json(paths["decision"], chain["decision_contract"])
            prior._write_runtime_json(paths["contract"], chain["measurement_contract"])
            prior._write_runtime_json(paths["evidence"], chain["static_evidence"])
            prior._write_runtime_json(paths["prediction"], chain["prediction"])
            prior._write_runtime_json(paths["verification"], chain["source_verification_input"])
            field_receipts.append(runner.freeze_preoutcome(
                database,
                decision_contract_path=paths["decision"],
                contract_path=paths["contract"],
                evidence_path=paths["evidence"],
                prediction_path=paths["prediction"],
                source_verification_path=paths["verification"],
                source_verifier=verifier,
                technical_route_resolver=lambda code: {"security_code": code, "organization_id": ORGANIZATION_ID},
            ))
    counts = _counts(database)
    expected = {
        "decision_contracts": 3, "technical_route_identities": 3,
        "measurement_contracts": 3, "static_evidence": 3, "predictions": 3,
        "outcome_access": 0, "source_inventories": 0, "observations": 0, "settlements": 0,
    }
    if counts != expected or any(row.get("stage") != "PRE_OUTCOME_FROZEN" for row in field_receipts):
        raise ApplianceRound2Error("controller_preoutcome_freeze_incomplete")
    return {
        "schema_version": "enterprise-judgment-appliance-controller-freeze-receipt.v1",
        "episode_id": EPISODE_ID,
        "stage": "PRE_OUTCOME_BATCH_FROZEN",
        "field_receipts": field_receipts,
        "controller_counts": counts,
        "outcome_access": {"authorized": False, "content_read": False, "custodian_started": False},
        "allowed_outputs": ["INDEPENDENT_PREOUTCOME_REVIEW_ONLY"],
        "rights": deepcopy(RIGHTS),
    }
