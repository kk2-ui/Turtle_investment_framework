#!/usr/bin/env python3
"""Appliance continuous-training pre-outcome compiler.

This is a thin, appliance-specific training adapter.  It consumes the
value-free Round 10 completion/review and reuses the existing Minimal
Historical Episode contracts for the next unseen company.  It does not read
an outcome, settle a field, or create a second training control plane.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from typing import Any

try:
    from scripts import minimal_historical_episode as minimal
    from scripts import minimal_historical_episode_control_plane as minimal_control
    from scripts import minimal_historical_episode_runner as minimal_runner
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as minimal
    import minimal_historical_episode_control_plane as minimal_control
    import minimal_historical_episode_runner as minimal_runner


SCHEMA_VERSION = "enterprise-judgment-appliance-continuous-training.v1"
CURRICULUM_SCHEMA_VERSION = "enterprise-judgment-appliance-curriculum-candidate.v1"
ROSTER_SCHEMA_VERSION = "enterprise-judgment-appliance-role-exposure-roster.v1"
EPISODE_ID = "APPLIANCE-R11:CN002032:20180930:V1"
CURRICULUM_CANDIDATE_ID = "APPLIANCE-CURRICULUM:PRODUCT-BOUNDARY-BEFORE-ISSUER-GROWTH:V1"
ROSTER_ID = "APPLIANCE-R11:UNSEEN-ROSTER:20180930:V1"
CUTOFF_AT = "2018-09-30T23:59:59+08:00"
FROZEN_AT = "2026-08-28T10:04:50+08:00"
OUTCOME_PERIOD_END = "2018-12-31"
SOURCE_ID = "CNINFO:002032:ANN:20180331:1204552803"
SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2018-03-31/1204552803.PDF"
ISSUER_ID = "ISSUER:CN:002032"
COMPANY_ID = "CN:002032"
SECURITY_CODE = "002032"
ORGANIZATION_ID = "gssz0002032"
CURATOR_ID = "ROLE:APPLIANCE-R11:CN002032:STATIC_EVIDENCE_CURATOR_FUNCTION"
FORECASTER_ID = "ROLE:APPLIANCE-R11:CN002032:FORECASTER_FUNCTION"
CUSTODIAN_ID = "ROLE:APPLIANCE-R11:CN002032:INDEPENDENT_OUTCOME_CUSTODIAN"

RIGHTS = {
    "method_transfer": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "buy_band": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}

DIMENSIONS = (
    "INITIAL_CONDITIONS_AND_BOUNDARY",
    "IMPLEMENTED_MANAGEMENT_ACTION",
    "EXECUTION_CAPABILITY",
    "CUSTOMER_AND_COMPETITIVE_RESPONSE",
    "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_AND_CAPITAL",
    "ADAPTATION_AND_PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION",
)

_FORBIDDEN_KEYS = {
    "outcome_value", "realized_value", "realised_value", "outcome_label",
    "settlement", "price", "return", "cjo", "valuation", "buy_band",
}

_WHITESPACE = re.compile(r"\s+")
_PAGE_REF = re.compile(r"\bPDF\s+p\.(\d+)\b", re.IGNORECASE)

_LOCAL_SOURCE_RULES = {
    "CONSOLIDATED_REVENUE_RMB": {
        "page": 12,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032",
        "field_ref": "PDF p.12; 营业收入合计; 2017 current-period value",
        "label": "营业收入合计",
        "exact_quote": "营业收入合计 14,187,347,425.77 100% 11,947,123,201.12 100% 18.75%",
        "numeric_value": Decimal("14187347425.77"),
    },
    "PRODUCT_REVENUE_RMB:电锅类": {
        "page": 12,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032:DISCLOSED_PRODUCT_CATEGORY:电锅类",
        "field_ref": "PDF p.12; 分产品; 电锅类; 2017 current-period revenue",
        "label": "电锅类",
        "exact_quote": "电锅类 3,809,138,321.20 26.85% 3,462,194,790.53 28.98% 10.02%",
        "numeric_value": Decimal("3809138321.20"),
    },
    "CONSOLIDATED_OPERATING_CASH_FLOW_RMB": {
        "page": 16,
        "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032",
        "field_ref": "PDF p.16; 经营活动产生的现金流量净额; 2017 current-period value",
        "label": "经营活动产生的现金流量净额",
        "exact_quote": "经营活动产生的现金流量净额 1,081,469,057.39 1,388,911,912.47 -22.14%",
        "numeric_value": Decimal("1081469057.39"),
    },
}


class ApplianceContinuousTrainingError(ValueError):
    """The appliance training object crosses its pre-outcome boundary."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _walk_forbidden(value: Any, *, path: str = "root") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            explicit_denial = path.endswith(".rights") and child == "NOT_AUTHORIZED"
            if key.casefold() in _FORBIDDEN_KEYS and not explicit_denial:
                findings.append(f"{path}.{key}_forbidden_preoutcome")
            findings.extend(_walk_forbidden(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_walk_forbidden(child, path=f"{path}[{index}]"))
    return findings


def build_curriculum_candidate(round10_review: Any, round10_completion: Any) -> dict[str, Any]:
    """Translate Round 10's accepted negative result into one future-only rule."""
    review, completion = _mapping(round10_review), _mapping(round10_completion)
    if review.get("review_status") != "NO_MATERIAL_UTILITY":
        raise ApplianceContinuousTrainingError("round10_no_material_utility_review_required")
    if completion.get("completion_status") != "ROUND10_COMPLETE_NO_METHOD_TRANSFER":
        raise ApplianceContinuousTrainingError("round10_terminal_completion_required")
    if completion.get("review_ref") != review.get("review_id"):
        raise ApplianceContinuousTrainingError("round10_review_completion_identity_mismatch")
    if review.get("accepted_treatment_delta_ids") != [] or completion.get("method_transfer") != "NOT_AUTHORIZED":
        raise ApplianceContinuousTrainingError("round10_method_transfer_must_remain_denied")
    return {
        "schema_version": CURRICULUM_SCHEMA_VERSION,
        "curriculum_candidate_id": CURRICULUM_CANDIDATE_ID,
        "source_review_ref": review["review_id"],
        "source_completion_ref": completion["completion_receipt_id"],
        "status": "FUTURE_EPISODE_RULE_CANDIDATE_ONLY",
        "lesson": {
            "question_change": "Before interpreting issuer growth, ask whether one disclosed product responsibility boundary moves in the same direction.",
            "minimum_distinguishing_evidence": "Freeze at least one directly settleable product-category operating field alongside issuer financial context.",
            "prohibited_upgrade": "Issuer revenue, issuer operating cash and total assets cannot establish customer response, unit economics, action effectiveness or ordinary-share owner cash.",
            "materiality_test": "The rule counts only if it changes a predeclared operating-underwriting treatment or prevents a baseline directional error in a later unseen episode.",
        },
        "round10_conclusion_preserved": "NO_MATERIAL_UTILITY",
        "automatic_method_advantage_count": 0,
        "allowed_outputs": ["FUTURE_PREOUTCOME_EPISODE_ONLY", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def validate_curriculum_candidate(candidate: Any) -> dict[str, Any]:
    item = _mapping(candidate)
    findings: list[str] = []
    required = {
        "schema_version", "curriculum_candidate_id", "source_review_ref",
        "source_completion_ref", "status", "lesson", "round10_conclusion_preserved",
        "automatic_method_advantage_count", "allowed_outputs", "rights",
    }
    if set(item) != required:
        findings.append("curriculum_candidate_shape_invalid")
    if item.get("schema_version") != CURRICULUM_SCHEMA_VERSION or item.get("curriculum_candidate_id") != CURRICULUM_CANDIDATE_ID:
        findings.append("curriculum_candidate_identity_invalid")
    if item.get("status") != "FUTURE_EPISODE_RULE_CANDIDATE_ONLY":
        findings.append("curriculum_candidate_cannot_self_accept")
    lesson = _mapping(item.get("lesson"))
    if set(lesson) != {"question_change", "minimum_distinguishing_evidence", "prohibited_upgrade", "materiality_test"} or any(not _text(value) for value in lesson.values()):
        findings.append("curriculum_candidate_lesson_shape_invalid")
    if item.get("round10_conclusion_preserved") != "NO_MATERIAL_UTILITY" or item.get("automatic_method_advantage_count") != 0:
        findings.append("curriculum_candidate_must_preserve_round10_negative_result")
    if item.get("allowed_outputs") != ["FUTURE_PREOUTCOME_EPISODE_ONLY", "RESEARCH_AGENDA"] or item.get("rights") != RIGHTS:
        findings.append("curriculum_candidate_rights_must_remain_closed")
    findings.extend(_walk_forbidden(item))
    return {"valid": not findings, "findings": findings, "candidate": deepcopy(item) if not findings else None}


def build_roster() -> dict[str, Any]:
    return {
        "schema_version": ROSTER_SCHEMA_VERSION,
        "roster_id": ROSTER_ID,
        "selection_basis": "ROLE_X_COMPANY_X_CUTOFF_ACTUAL_INPUT_EXPOSURE",
        "candidate_order": [
            {"company_id": "CN:002032", "issuer_name": "浙江苏泊尔股份有限公司", "arena": "COOKWARE_AND_KITCHEN_SMALL_APPLIANCES", "cutoff_at": CUTOFF_AT, "preoutcome_role_ids": [CURATOR_ID, FORECASTER_ID], "actual_input_exposure": "CUTOFF_BEFORE_SOURCE_ONLY", "role_independence": "SEQUENTIAL_FUNCTIONAL_PARTITION_NOT_HOLDOUT", "status": "FIRST_PREOUTCOME_EPISODE"},
            {"company_id": "CN:002242", "issuer_name": "九阳股份有限公司", "arena": "KITCHEN_SMALL_APPLIANCES", "cutoff_at": CUTOFF_AT, "preoutcome_role_id": None, "actual_input_exposure": "NOT_ASSESSED_NOT_OPENED", "status": "RESERVED_NOT_OPENED"},
            {"company_id": "CN:002543", "issuer_name": "广东万和新电气股份有限公司", "arena": "GAS_WATER_HEATING_AND_KITCHEN_APPLIANCES", "cutoff_at": CUTOFF_AT, "preoutcome_role_id": None, "actual_input_exposure": "NOT_ASSESSED_NOT_OPENED", "status": "RESERVED_NOT_OPENED"},
        ],
        "company_level_blacklist_policy": "PROHIBITED_ROLE_SPECIFIC_EXPOSURE_CONTROLS_ELIGIBILITY",
        "cross_company_comparator_claim": "NONE_DIFFERENT_PRODUCT_ARENAS",
        "outcome_content_read": False,
        "allowed_outputs": ["PREOUTCOME_TRAINING_ROSTER_ONLY"],
        "rights": deepcopy(RIGHTS),
    }


def validate_roster(roster: Any) -> dict[str, Any]:
    item = _mapping(roster)
    findings: list[str] = []
    if item.get("schema_version") != ROSTER_SCHEMA_VERSION or item.get("roster_id") != ROSTER_ID:
        findings.append("roster_identity_invalid")
    rows = _items(item.get("candidate_order"))
    if [row.get("company_id") for row in rows if isinstance(row, dict)] != ["CN:002032", "CN:002242", "CN:002543"]:
        findings.append("roster_fixed_order_invalid")
    if item.get("selection_basis") != "ROLE_X_COMPANY_X_CUTOFF_ACTUAL_INPUT_EXPOSURE" or item.get("company_level_blacklist_policy") != "PROHIBITED_ROLE_SPECIFIC_EXPOSURE_CONTROLS_ELIGIBILITY":
        findings.append("roster_must_use_role_company_cutoff_actual_exposure")
    first = _mapping(rows[0]) if rows else {}
    if first.get("cutoff_at") != CUTOFF_AT or first.get("preoutcome_role_ids") != [CURATOR_ID, FORECASTER_ID] or first.get("actual_input_exposure") != "CUTOFF_BEFORE_SOURCE_ONLY" or first.get("role_independence") != "SEQUENTIAL_FUNCTIONAL_PARTITION_NOT_HOLDOUT":
        findings.append("roster_first_role_exposure_invalid")
    if len({row.get("arena") for row in rows if isinstance(row, dict)}) != 3 or item.get("cross_company_comparator_claim") != "NONE_DIFFERENT_PRODUCT_ARENAS":
        findings.append("roster_must_not_claim_peer_comparability")
    if item.get("outcome_content_read") is not False or item.get("rights") != RIGHTS:
        findings.append("roster_must_remain_result_unseen_and_rights_closed")
    findings.extend(_walk_forbidden(item))
    return {"valid": not findings, "findings": findings, "roster": deepcopy(item) if not findings else None}


def build_source_packet() -> dict[str, Any]:
    return {
        "source_packet_id": "APPLIANCE-R11:CN002032:FY2017:PREOUTCOME-SOURCE:V1",
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "curator_id": CURATOR_ID,
        "source": {
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "published_at": "2018-03-31",
            "period_end": "2017-12-31",
            "source_type": "OFFICIAL_STATIC_CNINFO_ANNUAL_REPORT",
            "physical_pages": [11, 12, 13, 16, 21, 34],
        },
        "facts": [
            {"fact_id": "R11:F1:PRODUCT_AND_CHANNEL_ACTION", "status": "OBSERVED", "field_ref": "PDF p.11", "statement": "During FY2017 the issuer described product launches, lower-tier channel investment and expanded e-commerce execution; result attribution remains unproved."},
            {"fact_id": "R11:F2:PRODUCT_REVENUE", "status": "OBSERVED", "field_ref": "PDF p.12", "statement": "FY2017 disclosed cookware, electrical-appliance and electric-pot revenue at the listed-consolidated product table."},
            {"fact_id": "R11:F3:PRODUCT_ECONOMICS", "status": "OBSERVED", "field_ref": "PDF p.13", "statement": "Cookware gross margin declined while electrical-appliance margin was broadly stable; product inventory grew faster than product sales."},
            {"fact_id": "R11:F4:ISSUER_CASH", "status": "OBSERVED", "field_ref": "PDF p.16", "statement": "Issuer operating cash flow fell while reported revenue increased; this remains issuer cash, not ordinary-share owner cash."},
            {"fact_id": "R11:F5:RIVAL_AND_RISK", "status": "OBSERVED", "field_ref": "PDF p.21", "statement": "Consumer demand, SEB order transfer, raw-material and labour costs, and channel competition can reproduce later financial movement."},
            {"fact_id": "R11:F6:PERIMETER_TRANSITION", "status": "OBSERVED_PENDING_BOUNDARY", "field_ref": "PDF p.34", "statement": "The Shanghai Cyber acquisition had shareholder approval but registration was still in process at report publication, so later perimeter continuity requires explicit review."},
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
            "published_at": "2018-03-31",
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
    source_verification_input = {
        "schema_version": minimal_runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": {
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence["evidence_receipt_id"],
            "object_version": evidence["evidence_receipt_version"],
        },
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
        "source_verification_input": source_verification_input,
    }


def build_minimal_chains() -> list[dict[str, Any]]:
    specs = [
        {
            "chain_id": "APPLIANCE-R11:CN002032:FY2018:ISSUER_REVENUE:V1",
            "metric_role": "ISSUER_SCALE_CONTEXT",
            "metric_id": "CONSOLIDATED_REVENUE_RMB",
            "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032",
            "field_ref": "PDF p.12; 营业收入合计; 2017 current-period value",
            "exact_quote": _LOCAL_SOURCE_RULES["CONSOLIDATED_REVENUE_RMB"]["exact_quote"],
            "baseline_value": 14187347425.77,
            "predicted_direction": "INCREASE",
            "tolerance": 709367371.2885,
        },
        {
            "chain_id": "APPLIANCE-R11:CN002032:FY2018:ELECTRIC_POT_REVENUE:V1",
            "metric_role": "PRODUCT_BOUNDARY_DISTINGUISHER",
            "metric_id": "PRODUCT_REVENUE_RMB:电锅类",
            "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032:DISCLOSED_PRODUCT_CATEGORY:电锅类",
            "field_ref": "PDF p.12; 分产品; 电锅类; 2017 current-period revenue",
            "exact_quote": _LOCAL_SOURCE_RULES["PRODUCT_REVENUE_RMB:电锅类"]["exact_quote"],
            "baseline_value": 3809138321.20,
            "predicted_direction": "INCREASE",
            "tolerance": 190456916.06,
        },
        {
            "chain_id": "APPLIANCE-R11:CN002032:FY2018:ISSUER_OCF:V1",
            "metric_role": "ISSUER_CASH_CONTEXT_NOT_OWNER_CASH",
            "metric_id": "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
            "boundary": "LISTED_ISSUER_CONSOLIDATED:CN002032",
            "field_ref": "PDF p.16; 经营活动产生的现金流量净额; 2017 current-period value",
            "exact_quote": _LOCAL_SOURCE_RULES["CONSOLIDATED_OPERATING_CASH_FLOW_RMB"]["exact_quote"],
            "baseline_value": 1081469057.39,
            "predicted_direction": "STABLE",
            "tolerance": 216293811.478,
        },
    ]
    return [_chain(spec) for spec in specs]


def _finite_decimal(value: Any, *, field: str) -> Decimal:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ApplianceContinuousTrainingError(f"{field}_must_be_finite_numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - guarded above
        raise ApplianceContinuousTrainingError(f"{field}_must_be_finite_numeric") from exc
    if not parsed.is_finite():
        raise ApplianceContinuousTrainingError(f"{field}_must_be_finite_numeric")
    return parsed


def _normalized_pdf_text(value: str) -> str:
    return _WHITESPACE.sub("", value).replace(",", "").replace("，", "")


def build_local_pdf_source_verifier(local_pdf_path: str | Path) -> minimal_runner.SourceVerifier:
    """Build the narrow FY2017 Supor verifier used by the existing runner seam.

    The verifier opens only the already-registered local cutoff-before PDF. It
    supports exactly the three frozen appliance fields and delegates all
    controller chronology and persistence to ``freeze_preoutcome``.
    """
    pdf_path = Path(local_pdf_path)

    def verify(source: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
        if not pdf_path.is_file():
            raise ApplianceContinuousTrainingError("registered_local_pdf_not_found")
        metric_id = source.get("metric_id")
        rule = _LOCAL_SOURCE_RULES.get(metric_id)
        if rule is None:
            raise ApplianceContinuousTrainingError("source_metric_not_supported_by_appliance_verifier")
        if source.get("source_id") != SOURCE_ID or source.get("source_url") != SOURCE_URL:
            raise ApplianceContinuousTrainingError("source_identity_mismatch")
        if source.get("issuer_id") != ISSUER_ID:
            raise ApplianceContinuousTrainingError("source_issuer_mismatch")
        if source.get("responsibility_boundary") != rule["boundary"]:
            raise ApplianceContinuousTrainingError("source_responsibility_boundary_mismatch")
        if source.get("unit") != "RMB" or verification.get("unit") != "RMB":
            raise ApplianceContinuousTrainingError("source_unit_mismatch")
        if source.get("field_ref") != rule["field_ref"]:
            raise ApplianceContinuousTrainingError("source_field_ref_mismatch")
        page_match = _PAGE_REF.search(str(source.get("field_ref") or ""))
        if page_match is None or int(page_match.group(1)) != rule["page"]:
            raise ApplianceContinuousTrainingError("source_physical_page_mismatch")
        if verification.get("source_id") != SOURCE_ID or verification.get("source_url") != SOURCE_URL:
            raise ApplianceContinuousTrainingError("source_verification_identity_mismatch")
        if verification.get("exact_quote") != rule["exact_quote"]:
            raise ApplianceContinuousTrainingError("source_exact_quote_mismatch")
        if (
            _finite_decimal(source.get("numeric_value"), field="source_numeric_value")
            != rule["numeric_value"]
            or _finite_decimal(verification.get("numeric_value"), field="verification_numeric_value")
            != rule["numeric_value"]
        ):
            raise ApplianceContinuousTrainingError("source_numeric_value_mismatch")
        extracted = subprocess.run(
            [
                "pdftotext", "-f", str(rule["page"]), "-l", str(rule["page"]),
                "-layout", str(pdf_path), "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if _normalized_pdf_text(rule["exact_quote"]) not in _normalized_pdf_text(extracted):
            raise ApplianceContinuousTrainingError("registered_pdf_exact_quote_not_found_on_declared_page")
        row = re.search(
            rf"{re.escape(rule['label'])}\s*(?P<current>[0-9][0-9,，]*(?:\.[0-9]+)?)",
            extracted,
        )
        if row is None:
            raise ApplianceContinuousTrainingError("registered_pdf_metric_row_not_found")
        quoted_value = Decimal(row.group("current").replace(",", "").replace("，", ""))
        if quoted_value != rule["numeric_value"]:
            raise ApplianceContinuousTrainingError("registered_pdf_metric_value_mismatch")
        return {
            "schema_version": minimal_runner.SOURCE_RECEIPT_SCHEMA_VERSION,
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


def _write_runtime_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _controller_counts(database: str | Path) -> dict[str, int]:
    tables = {
        "decision_contracts": minimal_control.DECISION_CONTRACT_TABLE,
        "technical_route_identities": minimal_control.TECHNICAL_ROUTE_IDENTITY_TABLE,
        "measurement_contracts": minimal_control.CONTRACT_TABLE,
        "static_evidence": minimal_control.EVIDENCE_TABLE,
        "predictions": minimal_control.PREDICTION_TABLE,
        "outcome_access": minimal_control.ACCESS_TABLE,
        "source_inventories": minimal_control.OUTCOME_SOURCE_INVENTORY_TABLE,
        "observations": minimal_control.OBSERVATION_TABLE,
        "settlements": minimal_control.SETTLEMENT_TABLE,
    }
    conn = sqlite3.connect(database)
    try:
        minimal_control.initialize(conn)
        return {
            name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for name, table in tables.items()
        }
    finally:
        conn.close()


def freeze_supor_preoutcome(
    database: str | Path,
    *,
    local_pdf_path: str | Path,
    round10_review: Any,
    round10_completion: Any,
    source_receipt_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Freeze the canonical three-field batch through the existing runner."""
    candidate = build_curriculum_candidate(round10_review, round10_completion)
    roster = build_roster()
    episode = build_preoutcome_episode(candidate, roster)
    validation = validate_preoutcome_episode(
        episode, curriculum_candidate=candidate, roster=roster,
    )
    if not validation["valid"]:
        raise ApplianceContinuousTrainingError("canonical_preoutcome_episode_invalid")
    verifier = build_local_pdf_source_verifier(local_pdf_path)
    receipt_directory = Path(source_receipt_directory) if source_receipt_directory else None
    if receipt_directory is not None:
        receipt_directory.mkdir(parents=True, exist_ok=True)
    runner_receipts: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="appliance-r11-preoutcome-") as temporary:
        root = Path(temporary)
        for index, chain in enumerate(episode["minimal_field_chains"]):
            paths = {
                "decision": root / f"{index}-decision.json",
                "contract": root / f"{index}-contract.json",
                "evidence": root / f"{index}-evidence.json",
                "prediction": root / f"{index}-prediction.json",
                "verification": root / f"{index}-verification.json",
            }
            _write_runtime_json(paths["decision"], chain["decision_contract"])
            _write_runtime_json(paths["contract"], chain["measurement_contract"])
            _write_runtime_json(paths["evidence"], chain["static_evidence"])
            _write_runtime_json(paths["prediction"], chain["prediction"])
            _write_runtime_json(paths["verification"], chain["source_verification_input"])
            source_receipt_path = (
                receipt_directory / f"{index + 1:02d}_{chain['measurement_contract']['metric_id'].replace(':', '_')}_source_receipt.json"
                if receipt_directory is not None else None
            )
            runner_receipts.append(minimal_runner.freeze_preoutcome(
                database,
                decision_contract_path=paths["decision"],
                contract_path=paths["contract"],
                evidence_path=paths["evidence"],
                prediction_path=paths["prediction"],
                source_verification_path=paths["verification"],
                source_verifier=verifier,
                technical_route_resolver=lambda code: {
                    "security_code": code,
                    "organization_id": ORGANIZATION_ID,
                },
                source_receipt_output_path=source_receipt_path,
            ))
    counts = _controller_counts(database)
    expected_counts = {
        "decision_contracts": 3,
        "technical_route_identities": 3,
        "measurement_contracts": 3,
        "static_evidence": 3,
        "predictions": 3,
        "outcome_access": 0,
        "source_inventories": 0,
        "observations": 0,
        "settlements": 0,
    }
    if counts != expected_counts:
        raise ApplianceContinuousTrainingError("controller_preoutcome_counts_invalid")
    if any(receipt.get("stage") != "PRE_OUTCOME_FROZEN" for receipt in runner_receipts):
        raise ApplianceContinuousTrainingError("runner_preoutcome_freeze_incomplete")
    return {
        "schema_version": "enterprise-judgment-appliance-controller-freeze-receipt.v1",
        "episode_id": EPISODE_ID,
        "stage": "PRE_OUTCOME_BATCH_FROZEN",
        "field_receipts": runner_receipts,
        "controller_counts": counts,
        "outcome_access": {"authorized": False, "content_read": False, "custodian_started": False},
        "allowed_outputs": ["INDEPENDENT_PREOUTCOME_REVIEW_ONLY"],
        "rights": deepcopy(RIGHTS),
    }


def _enhanced_dimensions() -> list[dict[str, Any]]:
    rows = {
        "INITIAL_CONDITIONS_AND_BOUNDARY": ("OBSERVED", "The issuer spans cookware, electrical appliances and export/SEB channels; issuer totals and electric-pot product economics are separate responsibility boundaries.", ["R11:F2:PRODUCT_REVENUE"]),
        "IMPLEMENTED_MANAGEMENT_ACTION": ("OBSERVED_ACTION_RESULT_UNKNOWN", "FY2017 product launches, lower-tier channel investment and e-commerce expansion were described as undertaken, but their incremental result is not identified.", ["R11:F1:PRODUCT_AND_CHANNEL_ACTION"]),
        "EXECUTION_CAPABILITY": ("MIXED", "Product and channel activity was visible, while cookware inventory grew faster than sales and the Shanghai Cyber perimeter transition was unfinished at report publication.", ["R11:F3:PRODUCT_ECONOMICS", "R11:F6:PERIMETER_TRANSITION"]),
        "CUSTOMER_AND_COMPETITIVE_RESPONSE": ("UNKNOWN", "Annual-report narratives and third-party market-share references do not uniquely establish loyalty; FY2018 electric-pot revenue is frozen only as a product-boundary response signal.", ["R11:F1:PRODUCT_AND_CHANNEL_ACTION", "R11:F2:PRODUCT_REVENUE"]),
        "UNIT_ECONOMICS": ("MIXED", "Cookware margin declined while electrical-appliance margin was broadly stable; no FY2018 gross-margin cell is mechanically supported by the current acquisition catalogue.", ["R11:F3:PRODUCT_ECONOMICS"]),
        "WORKING_CAPITAL_CASH_AND_CAPITAL": ("UNKNOWN_OWNER_CASH", "Issuer operating cash fell despite revenue growth, but issuer OCF cannot be promoted to ordinary-share owner cash.", ["R11:F4:ISSUER_CASH"]),
        "ADAPTATION_AND_PERMANENT_LOSS": ("CONDITIONAL", "Brand/product breadth and SEB integration support adaptation, while input costs, channel competition and perimeter change remain loss-path risks.", ["R11:F5:RIVAL_AND_RISK", "R11:F6:PERIMETER_TRANSITION"]),
        "STRONGEST_ALTERNATIVE_EXPLANATION": ("OBSERVED_RIVAL", "Consumer upgrading, SEB order transfer, category mix and common channel expansion could explain growth without proving a company-specific action effect.", ["R11:F5:RIVAL_AND_RISK"]),
    }
    return [{"dimension_id": dimension, "status": rows[dimension][0], "judgment": rows[dimension][1], "evidence_refs": rows[dimension][2]} for dimension in DIMENSIONS]


def build_preoutcome_episode(curriculum_candidate: Any, roster: Any) -> dict[str, Any]:
    if not validate_curriculum_candidate(curriculum_candidate)["valid"]:
        raise ApplianceContinuousTrainingError("valid_curriculum_candidate_required")
    if not validate_roster(roster)["valid"]:
        raise ApplianceContinuousTrainingError("valid_roster_required")
    source_packet = build_source_packet()
    fact_refs = [fact["fact_id"] for fact in source_packet["facts"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": EPISODE_ID,
        "curriculum_candidate_ref": CURRICULUM_CANDIDATE_ID,
        "roster_ref": ROSTER_ID,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "frozen_at": FROZEN_AT,
        "method_identity": "MODEL_MEMORY_MITIGATED_HISTORICAL_APPLIANCE_TRAINING",
        "source_packet": source_packet,
        "same_fact_budget": {"fact_budget_id": "APPLIANCE-R11:CN002032:FACT-BUDGET:V1", "fact_refs": fact_refs},
        "fair_baseline": {
            "resolution_rule": "Issuer and disclosed product growth support continued operating underwriting; issuer cash volatility prevents a cash-quality conclusion.",
            "treatment": "CONTINUE_OPERATING_UNDERWRITING",
            "fact_refs": fact_refs,
        },
        "cumulative_enhanced": {
            "resolution_rule": "Issuer growth remains context until one product boundary and cash boundary are separately resolved; mixed product economics changes the treatment to conditional underwriting.",
            "treatment": "CONDITIONAL_PRODUCT_QUALITY_UNDERWRITING",
            "evidence_requirement_delta_id": "APPLIANCE-R11:DELTA:PRODUCT-BOUNDARY-FIELD",
            "dimensions": _enhanced_dimensions(),
            "fact_refs": fact_refs,
        },
        "material_treatment_snapshot": [
            {"treatment_id": "SCALE_TREND", "baseline": "POSITIVE_CONTEXT", "enhanced": "POSITIVE_CONTEXT_NOT_PRODUCT_PROOF"},
            {"treatment_id": "CORE_PRODUCT", "baseline": "BROAD_GROWTH", "enhanced": "DIRECT_PRODUCT_FIELD_REQUIRED"},
            {"treatment_id": "MANAGEMENT_ACTION", "baseline": "ACTION_PRESENT", "enhanced": "ACTION_RESULT_UNKNOWN"},
            {"treatment_id": "CUSTOMER_RESPONSE", "baseline": "UNKNOWN", "enhanced": "PRODUCT_REVENUE_SIGNAL_NOT_LOYALTY"},
            {"treatment_id": "UNIT_ECONOMICS", "baseline": "MIXED", "enhanced": "MIXED_AND_OUTCOME_FIELD_UNKNOWN"},
            {"treatment_id": "OWNER_CASH_AND_LOSS", "baseline": "UNKNOWN", "enhanced": "ISSUER_CASH_NOT_OWNER_CASH_AND_PERIMETER_REVIEW_REQUIRED"},
        ],
        "minimal_field_chains": build_minimal_chains(),
        "outcome_access": {"authorized": False, "content_read": False, "custodian_started": False},
        "review_state": "PREOUTCOME_INDEPENDENT_REVIEW_REQUIRED",
        "object_class": "APPLIANCE_CONTINUOUS_TRAINING_PREOUTCOME_EPISODE",
        "claim_class": "SAME_FACT_BUDGET_BASELINE_ENHANCED",
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def validate_preoutcome_episode(episode: Any, *, curriculum_candidate: Any, roster: Any) -> dict[str, Any]:
    item = _mapping(episode)
    findings: list[str] = []
    if item.get("schema_version") != SCHEMA_VERSION or item.get("episode_id") != EPISODE_ID:
        findings.append("episode_identity_invalid")
    if item.get("curriculum_candidate_ref") != CURRICULUM_CANDIDATE_ID or item.get("roster_ref") != ROSTER_ID:
        findings.append("episode_curriculum_or_roster_ref_invalid")
    if item.get("company_id") != COMPANY_ID or item.get("issuer_id") != ISSUER_ID or item.get("cutoff_at") != CUTOFF_AT:
        findings.append("episode_company_issuer_cutoff_invalid")
    if _instant(item.get("frozen_at")) is None or item.get("method_identity") != "MODEL_MEMORY_MITIGATED_HISTORICAL_APPLIANCE_TRAINING":
        findings.append("episode_freeze_or_method_identity_invalid")
    if not validate_curriculum_candidate(curriculum_candidate)["valid"] or not validate_roster(roster)["valid"]:
        findings.append("episode_requires_valid_curriculum_and_roster")
    source = _mapping(item.get("source_packet"))
    source_identity = _mapping(source.get("source"))
    if source.get("outcome_content_read") is not False or source_identity.get("source_id") != SOURCE_ID or source_identity.get("source_url") != SOURCE_URL:
        findings.append("episode_source_packet_invalid")
    published = source_identity.get("published_at")
    if published != "2018-03-31" or not all(isinstance(page, int) and page > 0 for page in _items(source_identity.get("physical_pages"))):
        findings.append("episode_source_date_or_pages_invalid")
    budget = _mapping(item.get("same_fact_budget"))
    baseline, enhanced = _mapping(item.get("fair_baseline")), _mapping(item.get("cumulative_enhanced"))
    if baseline.get("fact_refs") != budget.get("fact_refs") or enhanced.get("fact_refs") != budget.get("fact_refs"):
        findings.append("episode_methods_must_share_fact_budget")
    dimensions = _items(enhanced.get("dimensions"))
    if [row.get("dimension_id") for row in dimensions if isinstance(row, dict)] != list(DIMENSIONS):
        findings.append("episode_enhanced_dimensions_invalid")
    if baseline.get("treatment") == enhanced.get("treatment") or enhanced.get("evidence_requirement_delta_id") != "APPLIANCE-R11:DELTA:PRODUCT-BOUNDARY-FIELD":
        findings.append("episode_predeclared_evidence_treatment_delta_invalid")
    chains = _items(item.get("minimal_field_chains"))
    expected_metrics = ["CONSOLIDATED_REVENUE_RMB", "PRODUCT_REVENUE_RMB:电锅类", "CONSOLIDATED_OPERATING_CASH_FLOW_RMB"]
    if [_mapping(chain.get("measurement_contract")).get("metric_id") for chain in chains if isinstance(chain, dict)] != expected_metrics:
        findings.append("episode_requires_exact_three_ordered_fields")
    for index, raw_chain in enumerate(chains):
        chain = _mapping(raw_chain)
        decision = chain.get("decision_contract")
        route = chain.get("technical_route_identity")
        contract = chain.get("measurement_contract")
        evidence = chain.get("static_evidence")
        prediction = chain.get("prediction")
        verification = _mapping(chain.get("source_verification_input"))
        for prefix, result in (
            ("decision", minimal.validate_decision_contract(decision)),
            ("route", minimal.validate_technical_route_identity(route, decision_contract=decision)),
            ("contract", minimal.validate_measurement_contract(contract, decision_contract=decision, technical_route_identity=route)),
            ("evidence", minimal.validate_static_evidence(evidence, measurement_contract=contract)),
            ("prediction", minimal.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)),
        ):
            findings.extend(f"minimal_field_chains[{index}].{prefix}:{finding}" for finding in result["findings"])
        numeric = _mapping(_mapping(evidence).get("source")).get("numeric_value")
        if not isinstance(numeric, (int, float)) or isinstance(numeric, bool) or not math.isfinite(float(numeric)):
            findings.append(f"minimal_field_chains[{index}].baseline_value_invalid")
        source = _mapping(_mapping(evidence).get("source"))
        metric_id = source.get("metric_id")
        rule = _LOCAL_SOURCE_RULES.get(metric_id)
        verification_required = {
            "schema_version", "subject_ref", "source_id", "source_url", "exact_quote",
            "numeric_value", "unit", "allowed_outputs", "method_transfer_rights",
        }
        expected_subject_ref = {
            "object_type": "STATIC_EVIDENCE",
            "object_id": _mapping(evidence).get("evidence_receipt_id"),
            "object_version": _mapping(evidence).get("evidence_receipt_version"),
        }
        if (
            set(verification) != verification_required
            or verification.get("schema_version") != minimal_runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION
            or verification.get("subject_ref") != expected_subject_ref
            or verification.get("source_id") != source.get("source_id")
            or verification.get("source_url") != source.get("source_url")
            or verification.get("unit") != source.get("unit")
            or verification.get("allowed_outputs") != list(minimal.ALLOWED_OUTPUTS)
            or verification.get("method_transfer_rights") != minimal.NO_METHOD_TRANSFER_RIGHTS
            or rule is None
            or verification.get("exact_quote") != rule["exact_quote"]
        ):
            findings.append(f"minimal_field_chains[{index}].source_verification_input_invalid")
        else:
            try:
                if _finite_decimal(verification.get("numeric_value"), field="verification_numeric_value") != _finite_decimal(numeric, field="source_numeric_value"):
                    findings.append(f"minimal_field_chains[{index}].source_verification_numeric_value_mismatch")
            except ApplianceContinuousTrainingError:
                findings.append(f"minimal_field_chains[{index}].source_verification_numeric_value_invalid")
    outcome_access = _mapping(item.get("outcome_access"))
    if outcome_access != {"authorized": False, "content_read": False, "custodian_started": False}:
        findings.append("episode_outcome_access_must_remain_closed")
    if item.get("review_state") != "PREOUTCOME_INDEPENDENT_REVIEW_REQUIRED" or item.get("rights") != RIGHTS:
        findings.append("episode_review_or_rights_boundary_invalid")
    findings.extend(_walk_forbidden(item))
    return {"valid": not findings, "findings": findings, "episode": deepcopy(item) if not findings else None}
