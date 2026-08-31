#!/usr/bin/env python3
"""Freeze value-free outcome measurement contracts for report-autonomy cohorts.

The contracts identify only permissible future official-report fields, clocks,
scope, and closed assessment predicates.  They intentionally contain neither
post-cutoff observations nor arm output, anonymous mappings, prices, returns,
valuations, or investment actions.  A later custodian may acquire only the
declared fields after the existing anonymous-review gate is frozen.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.report_autonomy_multicompany_prereg import (
        validate_multicompany_preregistration,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.report_autonomy_multicompany_prereg import (
        validate_multicompany_preregistration,
    )


SCHEMA_VERSION = "report-autonomy-outcome-measurement-contract.v1"
PLANE_VALIDATION_SCHEMA = "report-autonomy-outcome-measurement-plane-validation.v1"
CONTRACT_STATE = "PREOUTCOME_FROZEN"
_ROOT = Path(__file__).resolve().parents[1]
_DOMAINS = {
    "INDUSTRY_SITUATION", "NORMAL_EARNINGS", "OWNER_CASH",
    "PERMANENT_LOSS", "VALUE_ROUTE",
}
_FIELD_GROUPS = {
    "INDUSTRY_SITUATION_CARRIER", "NORMAL_EARNINGS_CARRIER",
    "OWNER_CASH_CARRIER", "PERMANENT_LOSS_CARRIER", "VALUE_ROUTE_CONDITION",
}
_OBSERVATION_KINDS = {"DIRECT_NUMERIC", "DIRECT_EVENT"}
_STATUSES = {
    "OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH", "NOT_MEASURABLE_BY_DESIGN",
}
_ASSESSMENT_STATUSES = {
    "SUPPORTED", "WEAKENED_OR_FALSIFIED", "INCONCLUSIVE_DATA", "NON_DISCRIMINATING",
}
_FORBIDDEN_TOKENS = {
    "price", "return", "valuation", "investment_action", "anonymous_label",
    "arm_id", "outcome_value", "observed_value", "result_value",
}
_OPAQUE_LABEL_PATTERN = re.compile(r"ANON_[BCDFGHJKLMNPQRSTVWXYZ]{12}")
MANIFEST_SCHEMA_VERSION = "report-autonomy-anonymous-arm-claim-manifest.v1"
RECEIPT_SCHEMA_VERSION = "report-autonomy-outcome-field-receipts.v1"
ASSESSMENT_SCHEMA_VERSION = "report-autonomy-anonymous-outcome-assessment.v1"
CLAIM_BINDING_RECEIPT_SCHEMA_VERSION = "report-autonomy-anonymous-claim-binding-receipt.v1"

_FIELD_TEMPLATES = (
    ("REVENUE", "INDUSTRY_SITUATION_CARRIER", "利润表", "营业收入", "RMB", "DIRECT_NUMERIC"),
    ("RECURRING_PROFIT", "NORMAL_EARNINGS_CARRIER", "财务摘要", "归属于上市公司股东的扣除非经常性损益的净利润", "RMB", "DIRECT_NUMERIC"),
    ("OPERATING_CASH_FLOW", "OWNER_CASH_CARRIER", "现金流量表", "经营活动产生的现金流量净额", "RMB", "DIRECT_NUMERIC"),
    ("LONG_LIVED_ASSET_CASH", "OWNER_CASH_CARRIER", "现金流量表", "购建固定资产、无形资产和其他长期资产支付的现金", "RMB", "DIRECT_NUMERIC"),
    ("CASH_DIVIDENDS_PAID", "OWNER_CASH_CARRIER", "现金流量表", "分配股利、利润或偿付利息支付的现金", "RMB", "DIRECT_NUMERIC"),
    ("SHORT_TERM_DEBT", "PERMANENT_LOSS_CARRIER", "资产负债表", "短期借款", "RMB", "DIRECT_NUMERIC"),
    ("LONG_TERM_DEBT", "PERMANENT_LOSS_CARRIER", "资产负债表", "长期借款", "RMB", "DIRECT_NUMERIC"),
    ("ASSET_IMPAIRMENT", "PERMANENT_LOSS_CARRIER", "利润表或附注", "资产减值损失或减值准备", "RMB", "DIRECT_NUMERIC"),
    ("SHARE_CAPITAL", "PERMANENT_LOSS_CARRIER", "资产负债表", "股本", "SHARES", "DIRECT_NUMERIC"),
    ("ROUTE_REALIZATION_EVENT", "VALUE_ROUTE_CONDITION", "重要事项或附注", "已披露的资产实现、处置或向普通股东分配事件", "BOOLEAN_EVENT", "DIRECT_EVENT"),
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required:" + str(path))
    return value


def _calendar() -> list[dict[str, str]]:
    return [
        {
            "slot_id": f"P{index}",
            "fiscal_period": f"FY{year}",
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "source_selection_rule": "FIRST_ORIGINAL_AUDITED_ANNUAL_REPORT_PUBLISHED_AFTER_CUTOFF",
        }
        for index, year in enumerate((2018, 2019, 2020), start=1)
    ]


def _predicate(operator: str, field_ids: list[str]) -> dict[str, Any]:
    return {
        "predicate_id": "PRED:" + operator + ":" + field_ids[0].rsplit(":", 1)[0],
        "operator": operator,
        "field_ids": field_ids,
    }


def _disposition(
    rules: list[tuple[str, str, str]], *, otherwise: str = "NON_DISCRIMINATING",
) -> dict[str, Any]:
    return {
        "rules": [
            {
                "predicate_id": predicate_id,
                "expected_direction": expected_direction,
                "assessment_status": assessment_status,
            }
            for predicate_id, expected_direction, assessment_status in rules
        ],
        "otherwise_status": otherwise,
        "unknown_or_mismatch_status": "INCONCLUSIVE_DATA",
        "not_measurable_status": "NON_DISCRIMINATING",
    }


def _fields(case_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for metric, group, table, line, unit, kind in _FIELD_TEMPLATES:
        for slot in ("P1", "P2", "P3"):
            result.append({
                "field_id": f"FIELD:{case_id}:{metric}:{slot}",
                "field_group": group,
                "source_role": "OFFICIAL_AUDITED_ANNUAL_REPORT",
                "source_field_identity": {"table_or_note": table, "line_item": line},
                "boundary_id": "BOUNDARY:ISSUER_CONSOLIDATED",
                "period_slot": slot,
                "observation_kind": kind,
                "unit": unit,
                "allowed_observation_statuses": sorted(_STATUSES - {"NOT_MEASURABLE_BY_DESIGN"}),
            })
    return result


def _field_ids(case_id: str, metric: str) -> list[str]:
    return [f"FIELD:{case_id}:{metric}:{slot}" for slot in ("P1", "P2", "P3")]


def _anchors(case_id: str) -> list[dict[str, Any]]:
    recurring = _field_ids(case_id, "RECURRING_PROFIT")
    ocf = _field_ids(case_id, "OPERATING_CASH_FLOW")
    capex = _field_ids(case_id, "LONG_LIVED_ASSET_CASH")
    debt = _field_ids(case_id, "SHORT_TERM_DEBT") + _field_ids(case_id, "LONG_TERM_DEBT")
    normal_positive = _predicate("ALL_NON_NEGATIVE", recurring)
    normal_negative = _predicate("ANY_NEGATIVE", recurring)
    cash_positive = _predicate("ALL_NON_NEGATIVE", ocf)
    cash_negative = _predicate("ANY_NEGATIVE", ocf)
    loss_profit = _predicate("ALL_NEGATIVE", recurring)
    loss_cash = _predicate("ALL_NEGATIVE", ocf)
    loss_debt = _predicate("NET_DEBT_CARRIER_RISES_FROM_P1_TO_P3", debt)
    return [
        {
            "assessment_id": "ASSESS:INDUSTRY_REGIME",
            "claim_domain": "INDUSTRY_SITUATION",
            "claim_scope": "INDUSTRY_REGIME",
            "boundary_id": "NOT_APPLICABLE",
            "assessment_mode": "NOT_MEASURABLE_BY_DESIGN",
            "eligible_measurement_field_ids": [],
            "minimum_observed_period_slots": [],
            "predicates": [],
            "predicate_disposition": _disposition([]),
            "limitations": "Issuer annual-report carriers cannot settle an industry-wide regime claim.",
        },
        {
            "assessment_id": "ASSESS:NORMAL_EARNINGS_CARRIER",
            "claim_domain": "NORMAL_EARNINGS",
            "claim_scope": "LISTED_ISSUER_CONSOLIDATED_RECURRING_PROFIT_CARRIER",
            "boundary_id": "BOUNDARY:ISSUER_CONSOLIDATED",
            "assessment_mode": "CLOSED_CARRIER_PREDICATE",
            "eligible_measurement_field_ids": recurring,
            "minimum_observed_period_slots": ["P1", "P2", "P3"],
            "predicates": [normal_positive, normal_negative],
            "predicate_disposition": _disposition([
                (normal_positive["predicate_id"], "IMPROVES", "SUPPORTED"),
                (normal_positive["predicate_id"], "DETERIORATES", "WEAKENED_OR_FALSIFIED"),
                (normal_negative["predicate_id"], "IMPROVES", "WEAKENED_OR_FALSIFIED"),
                (normal_negative["predicate_id"], "DETERIORATES", "SUPPORTED"),
            ]),
            "limitations": "Settles only the declared recurring-profit carrier; it does not create a new normalization adjustment.",
        },
        {
            "assessment_id": "ASSESS:OWNER_CASH_LIMITATION",
            "claim_domain": "OWNER_CASH",
            "claim_scope": "LISTED_ISSUER_CONSOLIDATED_CASH_ABSORPTION_CARRIER",
            "boundary_id": "BOUNDARY:ISSUER_CONSOLIDATED",
            "assessment_mode": "CLOSED_CARRIER_PREDICATE",
            "eligible_measurement_field_ids": ocf + capex,
            "minimum_observed_period_slots": ["P1", "P2", "P3"],
            "predicates": [cash_positive, cash_negative],
            "predicate_disposition": _disposition([
                (cash_negative["predicate_id"], "DETERIORATES", "SUPPORTED"),
                (cash_negative["predicate_id"], "IMPROVES", "WEAKENED_OR_FALSIFIED"),
                (cash_positive["predicate_id"], "DETERIORATES", "WEAKENED_OR_FALSIFIED"),
                (cash_positive["predicate_id"], "IMPROVES", "NON_DISCRIMINATING"),
            ]),
            "limitations": "Operating cash and total long-lived-asset cash remain distinct. Total capex cannot be renamed maintenance capital and cannot by itself support ordinary-shareholder owner cash.",
        },
        {
            "assessment_id": "ASSESS:PERMANENT_LOSS_STRESS_CARRIER",
            "claim_domain": "PERMANENT_LOSS",
            "claim_scope": "LISTED_ISSUER_CONSOLIDATED_EROSION_OR_FINANCING_STRESS_CARRIER",
            "boundary_id": "BOUNDARY:ISSUER_CONSOLIDATED",
            "assessment_mode": "CLOSED_CARRIER_PREDICATE",
            "eligible_measurement_field_ids": recurring + ocf + debt,
            "minimum_observed_period_slots": ["P1", "P2", "P3"],
            "predicates": [loss_profit, loss_cash, loss_debt],
            "predicate_disposition": _disposition([
                (loss_profit["predicate_id"], "DETERIORATES", "SUPPORTED"),
                (loss_profit["predicate_id"], "IMPROVES", "WEAKENED_OR_FALSIFIED"),
                (loss_cash["predicate_id"], "DETERIORATES", "SUPPORTED"),
                (loss_cash["predicate_id"], "IMPROVES", "WEAKENED_OR_FALSIFIED"),
                (loss_debt["predicate_id"], "DETERIORATES", "SUPPORTED"),
                (loss_debt["predicate_id"], "IMPROVES", "WEAKENED_OR_FALSIFIED"),
            ]),
            "limitations": "Absence of bankruptcy, impairment, price movement, or a single survival observation cannot support low permanent-loss risk.",
        },
        {
            "assessment_id": "ASSESS:VALUE_ROUTE_GENERIC",
            "claim_domain": "VALUE_ROUTE",
            "claim_scope": "UNSPECIFIED_ROUTE",
            "boundary_id": "NOT_APPLICABLE",
            "assessment_mode": "NOT_MEASURABLE_BY_DESIGN",
            "eligible_measurement_field_ids": [],
            "minimum_observed_period_slots": [],
            "predicates": [],
            "predicate_disposition": _disposition([]),
            "limitations": "A generic route cannot be validated from issuer results, stock price, or return. A later route-specific contract amendment is prohibited after arm execution starts.",
        },
    ]


def build_case_contract(preregistration: Any, case_id: str) -> dict[str, Any]:
    """Build one finite value-free contract from a frozen case identity only."""

    prereg = _mapping(preregistration)
    validation = validate_multicompany_preregistration(prereg)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("preregistration_invalid:" + ",".join(validation["findings"]))
    cases = [
        _mapping(item) for item in _items(prereg.get("cases"))
        if _mapping(item).get("case_id") == case_id
    ]
    if len(cases) != 1:
        raise ValueError("case_not_registered:" + case_id)
    case = cases[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "RAOMC:" + _text(prereg.get("preregistration_id")) + ":" + case_id,
        "state": CONTRACT_STATE,
        "identity": {
            "preregistration_id": prereg.get("preregistration_id"),
            "case_id": case_id,
            "company_id": case.get("company_id"),
            "legal_issuer_id": "ISSUER:" + _text(case.get("company_id")),
            "cutoff_at": case.get("cutoff_at"),
        },
        "custody": {
            "outcome_access": "SEALED",
            "authorized_inputs": ["FROZEN_CONTRACT", "OFFICIAL_AUDITED_ANNUAL_REPORT"],
            "prohibited_inputs": ["ARM_OUTPUT", "ARM_MAPPING", "PRICE", "RETURN", "VALUATION", "INVESTMENT_ACTION"],
            "allowed_output": "VALUE_FREE_FIELD_RECEIPTS_ONLY",
        },
        "source_policy": {
            "official_source_category": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "source_selection_rule": "FIRST_ORIGINAL_AUDITED_ANNUAL_REPORT_FOR_DECLARED_FISCAL_PERIOD",
            "amendment_rule": "PRESERVE_ORIGINAL_AND_EMIT_MEASUREMENT_MISMATCH_UNLESS_PREDECLARED_RESTATEMENT_BRIDGE_EXISTS",
            "issuer_boundary_rule": "DECLARED_LISTED_ISSUER_ONLY",
        },
        "observation_calendar": _calendar(),
        "responsibility_boundaries": [{
            "boundary_id": "BOUNDARY:ISSUER_CONSOLIDATED",
            "accounting_scope": "LISTED_ISSUER_CONSOLIDATED",
            "ordinary_shareholder_claim_coverage": "CONSOLIDATED_CASH_IS_NOT_AUTOMATICALLY_ORDINARY_SHAREHOLDER_CASH",
            "continuity_rule": "UNRECONCILED_DISPOSAL_REORGANIZATION_OR_RESTATEMENT_IS_MEASUREMENT_MISMATCH",
        }],
        "measurement_fields": _fields(case_id),
        "assessment_anchors": _anchors(case_id),
        "outcome_status_policy": {
            "acquisition_statuses": sorted(_STATUSES),
            "assessment_statuses": sorted(_ASSESSMENT_STATUSES),
            "unknown_or_mismatch_assessment": "INCONCLUSIVE_DATA",
            "not_measurable_assessment": "NON_DISCRIMINATING",
            "assessor_cannot_add_field_or_predicate": True,
        },
    }


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(path + ".must_be_object")
        return item
    extra = sorted(set(item) - allowed)
    missing = sorted(allowed - set(item))
    if extra:
        findings.append(path + ".unexpected_fields:" + ",".join(extra))
    if missing:
        findings.append(path + ".missing_fields:" + ",".join(missing))
    return item


def _forbidden_paths(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            location = path + "." + str(key) if path else str(key)
            if str(key).casefold() in _FORBIDDEN_TOKENS:
                findings.append(location)
            findings.extend(_forbidden_paths(child, location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return findings


def validate_case_contract(contract: Any, *, preregistration: Any, case_id: str) -> dict[str, Any]:
    """Validate one contract without opening a post-cutoff source."""

    findings: list[str] = []
    value = _closed(contract, {
        "schema_version", "contract_id", "state", "identity", "custody", "source_policy",
        "observation_calendar", "responsibility_boundaries", "measurement_fields",
        "assessment_anchors", "outcome_status_policy",
    }, "contract", findings)
    prereg = _mapping(preregistration)
    case = next((
        _mapping(raw) for raw in _items(prereg.get("cases"))
        if _mapping(raw).get("case_id") == case_id
    ), {})
    if case and value != build_case_contract(prereg, case_id):
        findings.append("contract.not_exact_frozen_case_template")
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("contract.schema_version_invalid")
    if value.get("state") != CONTRACT_STATE:
        findings.append("contract.state_must_be_preoutcome_frozen")
    identity = _closed(value.get("identity"), {
        "preregistration_id", "case_id", "company_id", "legal_issuer_id", "cutoff_at",
    }, "contract.identity", findings)
    expected = {
        "preregistration_id": prereg.get("preregistration_id"), "case_id": case_id,
        "company_id": case.get("company_id"), "cutoff_at": case.get("cutoff_at"),
    }
    for field, expectation in expected.items():
        if identity.get(field) != expectation:
            findings.append("contract.identity." + field + "_mismatch")
    if identity.get("legal_issuer_id") != "ISSUER:" + _text(case.get("company_id")):
        findings.append("contract.identity.legal_issuer_id_mismatch")
    if not _text(value.get("contract_id")):
        findings.append("contract.contract_id_required")
    custody = _closed(value.get("custody"), {
        "outcome_access", "authorized_inputs", "prohibited_inputs", "allowed_output",
    }, "contract.custody", findings)
    if custody.get("outcome_access") != "SEALED" or custody.get("allowed_output") != "VALUE_FREE_FIELD_RECEIPTS_ONLY":
        findings.append("contract.custody_invalid")
    if custody.get("prohibited_inputs") != ["ARM_OUTPUT", "ARM_MAPPING", "PRICE", "RETURN", "VALUATION", "INVESTMENT_ACTION"]:
        findings.append("contract.custody_prohibition_invalid")
    policy = _closed(value.get("source_policy"), {
        "official_source_category", "source_selection_rule", "amendment_rule", "issuer_boundary_rule",
    }, "contract.source_policy", findings)
    if policy.get("official_source_category") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
        findings.append("contract.source_policy_source_invalid")
    calendar = _items(value.get("observation_calendar"))
    expected_calendar = _calendar()
    if calendar != expected_calendar:
        findings.append("contract.observation_calendar_invalid")
    boundaries = _items(value.get("responsibility_boundaries"))
    if len(boundaries) != 1 or _mapping(boundaries[0]).get("boundary_id") != "BOUNDARY:ISSUER_CONSOLIDATED":
        findings.append("contract.boundary_registry_invalid")
    elif _mapping(boundaries[0]).get("accounting_scope") != "LISTED_ISSUER_CONSOLIDATED":
        findings.append("contract.boundary_scope_invalid")

    fields = [_mapping(raw) for raw in _items(value.get("measurement_fields"))]
    field_ids = [_text(field.get("field_id")) for field in fields]
    if len(fields) != len(_FIELD_TEMPLATES) * 3 or not all(field_ids) or len(set(field_ids)) != len(field_ids):
        findings.append("contract.measurement_fields_incomplete_or_duplicate")
    for index, field in enumerate(fields):
        path = f"contract.measurement_fields[{index}]"
        _closed(field, {
            "field_id", "field_group", "source_field_identity", "boundary_id", "period_slot",
            "observation_kind", "unit", "allowed_observation_statuses", "source_role",
        }, path, findings)
        if field.get("field_group") not in _FIELD_GROUPS:
            findings.append(path + ".field_group_invalid")
        if field.get("source_role") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
            findings.append(path + ".source_role_invalid")
        if field.get("boundary_id") != "BOUNDARY:ISSUER_CONSOLIDATED":
            findings.append(path + ".boundary_invalid")
        if field.get("period_slot") not in {"P1", "P2", "P3"}:
            findings.append(path + ".period_invalid")
        if field.get("observation_kind") not in _OBSERVATION_KINDS:
            findings.append(path + ".observation_kind_invalid")
        if field.get("allowed_observation_statuses") != sorted(_STATUSES - {"NOT_MEASURABLE_BY_DESIGN"}):
            findings.append(path + ".allowed_statuses_invalid")
        source_field = _mapping(field.get("source_field_identity"))
        if set(source_field) != {"table_or_note", "line_item"} or not all(_text(item) for item in source_field.values()):
            findings.append(path + ".source_field_identity_invalid")

    anchors = [_mapping(raw) for raw in _items(value.get("assessment_anchors"))]
    domains = {anchor.get("claim_domain") for anchor in anchors}
    if domains != _DOMAINS or len(anchors) != len(_DOMAINS):
        findings.append("contract.assessment_domains_must_cover_exactly_five")
    for index, anchor in enumerate(anchors):
        path = f"contract.assessment_anchors[{index}]"
        _closed(anchor, {
            "assessment_id", "claim_domain", "claim_scope", "boundary_id", "assessment_mode",
            "eligible_measurement_field_ids", "minimum_observed_period_slots", "predicates",
            "predicate_disposition", "limitations",
        }, path, findings)
        if anchor.get("claim_domain") not in _DOMAINS or not _text(anchor.get("assessment_id")):
            findings.append(path + ".identity_invalid")
        field_refs = anchor.get("eligible_measurement_field_ids")
        if not isinstance(field_refs, list) or len(field_refs) != len(set(field_refs)) or any(ref not in field_ids for ref in field_refs):
            findings.append(path + ".field_refs_invalid")
        predicate_ids: set[str] = set()
        if anchor.get("assessment_mode") == "NOT_MEASURABLE_BY_DESIGN":
            if field_refs or anchor.get("predicates") or anchor.get("boundary_id") != "NOT_APPLICABLE":
                findings.append(path + ".not_measurable_treatment_invalid")
        elif anchor.get("assessment_mode") == "CLOSED_CARRIER_PREDICATE":
            if anchor.get("boundary_id") != "BOUNDARY:ISSUER_CONSOLIDATED" or not field_refs:
                findings.append(path + ".carrier_scope_invalid")
            if anchor.get("minimum_observed_period_slots") != ["P1", "P2", "P3"]:
                findings.append(path + ".carrier_clock_invalid")
            predicates = _items(anchor.get("predicates"))
            if not predicates:
                findings.append(path + ".predicates_required")
            for predicate_index, predicate in enumerate(predicates):
                item = _mapping(predicate)
                predicate_id = _text(item.get("predicate_id"))
                if set(item) != {"predicate_id", "operator", "field_ids"} or not predicate_id or predicate_id in predicate_ids or item.get("operator") not in {
                    "ALL_NON_NEGATIVE", "ANY_NEGATIVE", "ALL_NEGATIVE", "NET_DEBT_CARRIER_RISES_FROM_P1_TO_P3",
                } or not isinstance(item.get("field_ids"), list) or any(
                    field_id not in field_refs for field_id in item.get("field_ids", [])
                ):
                    findings.append(path + f".predicates[{predicate_index}]_invalid")
                predicate_ids.add(predicate_id)
        else:
            findings.append(path + ".assessment_mode_invalid")
        disposition = _mapping(anchor.get("predicate_disposition"))
        if set(disposition) != {
            "rules", "otherwise_status", "unknown_or_mismatch_status", "not_measurable_status",
        } or disposition.get("otherwise_status") not in _ASSESSMENT_STATUSES or disposition.get("unknown_or_mismatch_status") != "INCONCLUSIVE_DATA" or disposition.get("not_measurable_status") != "NON_DISCRIMINATING":
            findings.append(path + ".predicate_disposition_invalid")
        rules = _items(disposition.get("rules"))
        rule_pairs: set[tuple[str, str]] = set()
        for rule_index, raw_rule in enumerate(rules):
            rule = _mapping(raw_rule)
            predicate_id = _text(rule.get("predicate_id"))
            expected_direction = rule.get("expected_direction")
            pair = (predicate_id, str(expected_direction))
            if set(rule) != {"predicate_id", "expected_direction", "assessment_status"} or predicate_id not in predicate_ids or expected_direction not in {"IMPROVES", "DETERIORATES"} or pair in rule_pairs or rule.get("assessment_status") not in {"SUPPORTED", "WEAKENED_OR_FALSIFIED", "NON_DISCRIMINATING"}:
                findings.append(path + f".predicate_disposition.rules[{rule_index}]_invalid")
            rule_pairs.add(pair)
        if anchor.get("assessment_mode") == "NOT_MEASURABLE_BY_DESIGN" and rules:
            findings.append(path + ".not_measurable_disposition_must_have_no_rules")
        if anchor.get("assessment_mode") == "CLOSED_CARRIER_PREDICATE" and rule_pairs != {
            (predicate_id, direction)
            for predicate_id in predicate_ids
            for direction in ("IMPROVES", "DETERIORATES")
        }:
            findings.append(path + ".predicate_disposition_must_cover_each_predicate_and_direction")
        if not _text(anchor.get("limitations")):
            findings.append(path + ".limitations_required")
    status_policy = _closed(value.get("outcome_status_policy"), {
        "acquisition_statuses", "assessment_statuses", "unknown_or_mismatch_assessment",
        "not_measurable_assessment", "assessor_cannot_add_field_or_predicate",
    }, "contract.outcome_status_policy", findings)
    if status_policy.get("acquisition_statuses") != sorted(_STATUSES) or status_policy.get("assessment_statuses") != sorted(_ASSESSMENT_STATUSES):
        findings.append("contract.status_policy_statuses_invalid")
    if status_policy.get("unknown_or_mismatch_assessment") != "INCONCLUSIVE_DATA" or status_policy.get("not_measurable_assessment") != "NON_DISCRIMINATING" or status_policy.get("assessor_cannot_add_field_or_predicate") is not True:
        findings.append("contract.status_policy_mapping_invalid")
    findings.extend("contract.forbidden:" + item for item in _forbidden_paths(value))
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": list(dict.fromkeys(findings))}


def _contract_path(root: Path, reference: Any) -> Path:
    candidate = Path(_text(reference))
    if candidate.is_absolute():
        raise ValueError("measurement_contract_ref_must_be_project_relative")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("measurement_contract_ref_escapes_project_root") from exc
    return resolved


def validate_outcome_measurement_plane(
    preregistration: Any, *, project_root: str | Path = _ROOT,
) -> dict[str, Any]:
    """Resolve and validate all eight value-free contracts before arms start."""

    findings: list[str] = []
    prereg = _mapping(preregistration)
    prereg_result = validate_multicompany_preregistration(prereg)
    if prereg_result["state"] != "REVIEWABLE":
        findings.extend("preregistration:" + item for item in prereg_result["findings"])
    root = Path(project_root).expanduser().resolve()
    measurements = _items(prereg.get("outcome_measurements"))
    case_ids = {_text(case.get("case_id")) for case in _items(prereg.get("cases")) if _text(_mapping(case).get("case_id"))}
    contracts: list[dict[str, Any]] = []
    paths: set[Path] = set()
    contract_ids: set[str] = set()
    for index, raw in enumerate(measurements):
        item = _mapping(raw)
        case_id = _text(item.get("case_id"))
        try:
            path = _contract_path(root, item.get("measurement_contract_ref"))
        except ValueError as exc:
            findings.append(f"outcome_measurements[{index}]:{exc}")
            continue
        if path in paths:
            findings.append(f"outcome_measurements[{index}].measurement_contract_ref_duplicate")
        paths.add(path)
        if not path.is_file():
            findings.append(f"outcome_measurements[{index}].measurement_contract_missing")
            continue
        try:
            contract = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            findings.append(f"outcome_measurements[{index}].measurement_contract_unreadable:{exc}")
            continue
        contracts.append(contract)
        result = validate_case_contract(contract, preregistration=prereg, case_id=case_id)
        if result["state"] != "REVIEWABLE":
            findings.extend(f"outcome_measurements[{index}]." + finding for finding in result["findings"])
        contract_id = _text(contract.get("contract_id"))
        if not contract_id or contract_id in contract_ids:
            findings.append(f"outcome_measurements[{index}].contract_id_missing_or_duplicate")
        contract_ids.add(contract_id)
    if len(measurements) != 8 or len(contracts) != 8 or len(case_ids) != 8:
        findings.append("outcome_measurement_plane_requires_exactly_eight_cases_and_contracts")
    return {
        "schema_version": PLANE_VALIDATION_SCHEMA,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
        "authority": "VALUE_FREE_PREOUTCOME_MEASUREMENT_CONTROL_PLANE_ONLY",
    }


def materialize_case_contracts(
    preregistration: Any, *, project_root: str | Path = _ROOT,
) -> dict[str, Any]:
    """Write all eight declared contracts only when none already exist."""

    prereg = _mapping(preregistration)
    prereg_result = validate_multicompany_preregistration(prereg)
    if prereg_result["state"] != "REVIEWABLE":
        raise ValueError("preregistration_invalid:" + ",".join(prereg_result["findings"]))
    root = Path(project_root).expanduser().resolve()
    measurements = _items(prereg.get("outcome_measurements"))
    if len(measurements) != 8:
        raise ValueError("requires_exactly_eight_measurement_refs")
    planned: list[tuple[Path, dict[str, Any]]] = []
    for raw in measurements:
        item = _mapping(raw)
        output = _contract_path(root, item.get("measurement_contract_ref"))
        if output.exists():
            raise ValueError("materialization_refuses_existing_contract:" + str(output))
        planned.append((output, build_case_contract(prereg, _text(item.get("case_id")))))
    for output, contract in planned:
        _atomic_json(output, contract)
    return validate_outcome_measurement_plane(prereg, project_root=root)


def _anchor_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(anchor.get("assessment_id")): _mapping(anchor)
        for anchor in _items(contract.get("assessment_anchors"))
        if _text(_mapping(anchor).get("assessment_id"))
    }


def _directions(episode: Any) -> dict[str, str]:
    directions = _mapping(_mapping(episode).get("underwriting_thesis")).get("economic_directions")
    return {
        "NORMAL_EARNINGS": _text(_mapping(directions).get("normal_earnings")),
        "OWNER_CASH": _text(_mapping(directions).get("owner_cash")),
        "PERMANENT_LOSS": _text(_mapping(directions).get("permanent_loss")),
    }


def build_anonymous_arm_claim_manifest(
    contract: Any, *, episode: Any, anonymous_label: str, frozen_episode_ref: str,
) -> dict[str, Any]:
    """Bind the five canonical claim surfaces before outcome access.

    The manifest deliberately uses the opaque review label rather than an arm
    id.  It records structured economic directions already present in the
    frozen Episode; it does not re-read or paraphrase the report to choose a
    more convenient claim later.
    """

    contract_value = _mapping(contract)
    episode_value = _mapping(episode)
    identity = _mapping(contract_value.get("identity"))
    if _OPAQUE_LABEL_PATTERN.fullmatch(anonymous_label) is None:
        raise ValueError("anonymous_label_invalid")
    if episode_value.get("company_id") != identity.get("company_id") or episode_value.get("cutoff_at") != identity.get("cutoff_at"):
        raise ValueError("episode_identity_mismatch")
    directions = _directions(episode_value)
    anchors = _anchor_by_id(contract_value)
    expected = {
        "INDUSTRY_SITUATION": ("ASSESS:INDUSTRY_REGIME", "NONE", "OUT_OF_SCOPE"),
        "NORMAL_EARNINGS": ("ASSESS:NORMAL_EARNINGS_CARRIER", directions["NORMAL_EARNINGS"], "DIRECTIONAL"),
        "OWNER_CASH": ("ASSESS:OWNER_CASH_LIMITATION", directions["OWNER_CASH"], "DIRECTIONAL"),
        "PERMANENT_LOSS": ("ASSESS:PERMANENT_LOSS_STRESS_CARRIER", directions["PERMANENT_LOSS"], "DIRECTIONAL"),
        "VALUE_ROUTE": ("ASSESS:VALUE_ROUTE_GENERIC", "NONE", "OUT_OF_SCOPE"),
    }
    claims: list[dict[str, str]] = []
    for domain in ("INDUSTRY_SITUATION", "NORMAL_EARNINGS", "OWNER_CASH", "PERMANENT_LOSS", "VALUE_ROUTE"):
        assessment_id, direction, eligibility = expected[domain]
        if assessment_id not in anchors:
            raise ValueError("required_assessment_anchor_missing:" + assessment_id)
        claims.append({
            "claim_id": "CLAIM:" + domain,
            "claim_domain": domain,
            "assessment_id": assessment_id,
            "expected_direction": direction,
            "source_episode_field": (
                "situation_model.industry_future_thesis" if domain == "INDUSTRY_SITUATION"
                else "value_route" if domain == "VALUE_ROUTE"
                else "underwriting_thesis.economic_directions."
                + {"NORMAL_EARNINGS": "normal_earnings", "OWNER_CASH": "owner_cash", "PERMANENT_LOSS": "permanent_loss"}[domain]
            ),
            "settlement_eligibility": (
                eligibility if direction in {"IMPROVES", "DETERIORATES"} or eligibility == "OUT_OF_SCOPE"
                else "NON_DIRECTIONAL"
            ),
        })
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "state": "PREOUTCOME_ARM_CLAIM_FROZEN",
        "manifest_id": "RAACM:" + _text(contract_value.get("contract_id")) + ":" + anonymous_label,
        "contract_id": contract_value.get("contract_id"),
        "case_id": identity.get("case_id"),
        "anonymous_label": anonymous_label,
        "frozen_episode_ref": frozen_episode_ref,
        "claims": claims,
    }


def validate_anonymous_arm_claim_manifest(
    manifest: Any, *, contract: Any, episode: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    value = _closed(manifest, {
        "schema_version", "state", "manifest_id", "contract_id", "case_id", "anonymous_label",
        "frozen_episode_ref", "claims",
    }, "manifest", findings)
    contract_value = _mapping(contract)
    if value.get("schema_version") != MANIFEST_SCHEMA_VERSION or value.get("state") != "PREOUTCOME_ARM_CLAIM_FROZEN":
        findings.append("manifest.schema_or_state_invalid")
    if _OPAQUE_LABEL_PATTERN.fullmatch(_text(value.get("anonymous_label"))) is None:
        findings.append("manifest.anonymous_label_invalid")
    if value.get("contract_id") != contract_value.get("contract_id") or value.get("case_id") != _mapping(contract_value.get("identity")).get("case_id"):
        findings.append("manifest.contract_identity_mismatch")
    try:
        expected = build_anonymous_arm_claim_manifest(
            contract_value, episode=episode, anonymous_label=_text(value.get("anonymous_label")),
            frozen_episode_ref=_text(value.get("frozen_episode_ref")),
        )
    except ValueError as exc:
        findings.append("manifest.unbuildable:" + str(exc))
    else:
        if value != expected:
            findings.append("manifest.not_exact_frozen_episode_binding")
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": findings}


def build_anonymous_case_claim_binding_receipt(
    contract: Any, *, manifest_episode_pairs: list[tuple[Any, Any]],
) -> dict[str, Any]:
    """Freeze all four anonymous claims for one case before custody opens.

    This is deliberately a case-level rather than arm-level object: it proves
    four opaque labels were each derived from their matching frozen Episode,
    while keeping any label-to-training-arm mapping out of the receipt.
    """

    contract_value = _mapping(contract)
    if len(manifest_episode_pairs) != 4:
        raise ValueError("anonymous_case_binding_requires_exactly_four_pairs")
    labels: set[str] = set()
    manifest_ids: list[str] = []
    for index, (manifest, episode) in enumerate(manifest_episode_pairs):
        result = validate_anonymous_arm_claim_manifest(
            manifest, contract=contract_value, episode=episode,
        )
        if result["state"] != "REVIEWABLE":
            raise ValueError("anonymous_manifest_invalid:" + str(index) + ":" + ",".join(result["findings"]))
        label = _text(_mapping(manifest).get("anonymous_label"))
        if label in labels:
            raise ValueError("anonymous_case_binding_label_duplicate")
        labels.add(label)
        manifest_ids.append(_text(_mapping(manifest).get("manifest_id")))
    return {
        "schema_version": CLAIM_BINDING_RECEIPT_SCHEMA_VERSION,
        "state": "ANONYMOUS_CASE_CLAIM_BINDINGS_FROZEN",
        "contract_id": contract_value.get("contract_id"),
        "case_id": _mapping(contract_value.get("identity")).get("case_id"),
        "anonymous_labels": sorted(labels),
        "manifest_ids": sorted(manifest_ids),
        "claim_bindings": sorted([
            {
                "anonymous_label": _mapping(manifest).get("anonymous_label"),
                "manifest_id": _mapping(manifest).get("manifest_id"),
                "claims": deepcopy(_items(_mapping(manifest).get("claims"))),
            }
            for manifest, _episode in manifest_episode_pairs
        ], key=lambda item: str(item["anonymous_label"])),
        "authority": "PREOUTCOME_ANONYMOUS_CLAIM_BINDING_ONLY",
    }


def validate_anonymous_case_claim_binding_receipt(
    receipt: Any, *, contract: Any, manifest_episode_pairs: list[tuple[Any, Any]],
) -> dict[str, Any]:
    findings: list[str] = []
    value = _closed(receipt, {
        "schema_version", "state", "contract_id", "case_id", "anonymous_labels", "manifest_ids", "claim_bindings", "authority",
    }, "claim_binding_receipt", findings)
    contract_value = _mapping(contract)
    if value.get("schema_version") != CLAIM_BINDING_RECEIPT_SCHEMA_VERSION or value.get("state") != "ANONYMOUS_CASE_CLAIM_BINDINGS_FROZEN":
        findings.append("claim_binding_receipt.schema_or_state_invalid")
    if value.get("contract_id") != contract_value.get("contract_id") or value.get("case_id") != _mapping(contract_value.get("identity")).get("case_id"):
        findings.append("claim_binding_receipt.contract_identity_mismatch")
    if value.get("authority") != "PREOUTCOME_ANONYMOUS_CLAIM_BINDING_ONLY":
        findings.append("claim_binding_receipt.authority_invalid")
    try:
        expected = build_anonymous_case_claim_binding_receipt(
            contract_value, manifest_episode_pairs=manifest_episode_pairs,
        )
    except ValueError as exc:
        findings.append("claim_binding_receipt.inputs_invalid:" + str(exc))
    else:
        if value != expected:
            findings.append("claim_binding_receipt.not_exact_manifest_episode_binding")
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": findings}


def _predicate_statuses(
    contract: dict[str, Any], receipts: dict[str, dict[str, Any]], anchor: dict[str, Any],
) -> tuple[str, set[str], set[str]]:
    """Evaluate only the contract's numeric predicates, never report prose."""

    field_status = {field_id: receipt.get("status") for field_id, receipt in receipts.items()}
    predicate_values: dict[str, bool] = {}
    receipt_ids: set[str] = set()
    for raw_predicate in _items(anchor.get("predicates")):
        predicate = _mapping(raw_predicate)
        field_ids = [str(field_id) for field_id in _items(predicate.get("field_ids"))]
        if any(field_status.get(field_id) != "OBSERVED" for field_id in field_ids):
            return "INCONCLUSIVE_DATA", set(), set()
        values = [receipts[field_id].get("observed_value") for field_id in field_ids]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
            return "INCONCLUSIVE_DATA", set(), set()
        receipt_ids.update(_text(receipts[field_id].get("receipt_id")) for field_id in field_ids)
        operator = predicate.get("operator")
        if operator == "ALL_NON_NEGATIVE":
            result = all(float(value) >= 0 for value in values)
        elif operator == "ANY_NEGATIVE":
            result = any(float(value) < 0 for value in values)
        elif operator == "ALL_NEGATIVE":
            result = all(float(value) < 0 for value in values)
        elif operator == "NET_DEBT_CARRIER_RISES_FROM_P1_TO_P3":
            p1 = sum(
                float(receipts[field_id]["observed_value"])
                for field_id in field_ids if field_id.endswith(":P1")
            )
            p3 = sum(
                float(receipts[field_id]["observed_value"])
                for field_id in field_ids if field_id.endswith(":P3")
            )
            result = p3 > p1
        else:  # Validator prevents this branch for frozen contracts.
            return "INCONCLUSIVE_DATA", set(), set()
        if result:
            predicate_values[_text(predicate.get("predicate_id"))] = True
    return "OBSERVED", set(predicate_values), receipt_ids


def _expected_assessments(
    manifest: dict[str, Any], contract: dict[str, Any], receipt_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    receipts = {
        _text(item.get("field_id")): _mapping(item)
        for item in _items(receipt_payload.get("field_receipts"))
        if _text(_mapping(item).get("field_id"))
    }
    anchors = _anchor_by_id(contract)
    assessments: list[dict[str, Any]] = []
    for claim in _items(manifest.get("claims")):
        item = _mapping(claim)
        anchor = anchors[_text(item.get("assessment_id"))]
        mode = anchor.get("assessment_mode")
        if item.get("settlement_eligibility") != "DIRECTIONAL" or mode == "NOT_MEASURABLE_BY_DESIGN":
            status, applied, receipt_ids = "NON_DISCRIMINATING", set(), set()
        else:
            status, applied, receipt_ids = _predicate_statuses(contract, receipts, anchor)
            if status == "OBSERVED":
                disposition = _mapping(anchor.get("predicate_disposition"))
                matching = [
                    _mapping(rule).get("assessment_status")
                    for rule in _items(disposition.get("rules"))
                    if _mapping(rule).get("predicate_id") in applied
                    and _mapping(rule).get("expected_direction") == item.get("expected_direction")
                ]
                status = matching[0] if len(set(matching)) == 1 and matching else disposition.get("otherwise_status")
        assessments.append({
            "claim_id": item.get("claim_id"),
            "assessment_id": item.get("assessment_id"),
            "assessment_status": status,
            "applied_predicate_ids": sorted(applied),
            "receipt_ids": sorted(receipt_id for receipt_id in receipt_ids if receipt_id),
        })
    return assessments


def validate_outcome_field_receipts(receipts: Any, *, contract: Any) -> dict[str, Any]:
    findings: list[str] = []
    value = _closed(receipts, {
        "schema_version", "state", "contract_id", "case_id", "field_receipts",
    }, "receipts", findings)
    contract_value = _mapping(contract)
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION or value.get("state") != "OUTCOME_FIELD_RECEIPTS_FROZEN":
        findings.append("receipts.schema_or_state_invalid")
    if value.get("contract_id") != contract_value.get("contract_id") or value.get("case_id") != _mapping(contract_value.get("identity")).get("case_id"):
        findings.append("receipts.contract_identity_mismatch")
    fields = {_text(field.get("field_id")): _mapping(field) for field in _items(contract_value.get("measurement_fields"))}
    entries = [_mapping(raw) for raw in _items(value.get("field_receipts"))]
    if len(entries) != len(fields):
        findings.append("receipts.must_cover_each_declared_field_once")
    receipt_ids: set[str] = set()
    received_fields: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"receipts.field_receipts[{index}]"
        _closed(entry, {
            "receipt_id", "field_id", "status", "observed_value", "unit", "source_period_slot", "source_locator",
        }, path, findings)
        field_id = _text(entry.get("field_id"))
        receipt_id = _text(entry.get("receipt_id"))
        if not receipt_id or receipt_id in receipt_ids or field_id not in fields or field_id in received_fields:
            findings.append(path + ".identity_missing_invalid_or_duplicate")
        receipt_ids.add(receipt_id)
        received_fields.add(field_id)
        if entry.get("status") not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
            findings.append(path + ".status_invalid")
        if entry.get("unit") != _mapping(fields.get(field_id)).get("unit"):
            findings.append(path + ".unit_mismatch")
        if entry.get("source_period_slot") != _mapping(fields.get(field_id)).get("period_slot"):
            findings.append(path + ".source_period_slot_mismatch")
        if not _text(entry.get("source_locator")):
            findings.append(path + ".source_locator_required")
        observed = entry.get("observed_value")
        if entry.get("status") == "OBSERVED":
            if not isinstance(observed, (int, float)) or isinstance(observed, bool):
                findings.append(path + ".observed_value_required_numeric")
        elif observed is not None:
            findings.append(path + ".nonobserved_value_must_be_null")
    if received_fields != set(fields):
        findings.append("receipts.field_coverage_invalid")
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": list(dict.fromkeys(findings))}


def build_anonymous_outcome_assessment(
    manifest: Any, *, contract: Any, field_receipts: Any, claim_binding_receipt: Any,
) -> dict[str, Any]:
    manifest_value = _mapping(manifest)
    contract_value = _mapping(contract)
    receipt_value = _mapping(field_receipts)
    binding = _mapping(claim_binding_receipt)
    if binding.get("schema_version") != CLAIM_BINDING_RECEIPT_SCHEMA_VERSION or binding.get("state") != "ANONYMOUS_CASE_CLAIM_BINDINGS_FROZEN":
        raise ValueError("claim_binding_receipt_invalid")
    matching_bindings = [
        _mapping(item) for item in _items(binding.get("claim_bindings"))
        if _mapping(item).get("anonymous_label") == manifest_value.get("anonymous_label")
    ]
    if len(matching_bindings) != 1 or matching_bindings[0].get("manifest_id") != manifest_value.get("manifest_id") or matching_bindings[0].get("claims") != manifest_value.get("claims"):
        raise ValueError("manifest_not_exact_frozen_claim_binding")
    receipts_result = validate_outcome_field_receipts(receipt_value, contract=contract_value)
    if receipts_result["state"] != "REVIEWABLE":
        raise ValueError("field_receipts_invalid:" + ",".join(receipts_result["findings"]))
    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "state": "ANONYMOUS_OUTCOME_ASSESSMENT_FROZEN",
        "contract_id": contract_value.get("contract_id"),
        "case_id": _mapping(contract_value.get("identity")).get("case_id"),
        "anonymous_label": manifest_value.get("anonymous_label"),
        "manifest_id": manifest_value.get("manifest_id"),
        "claim_binding_receipt_id": "RACBR:" + _text(binding.get("contract_id")) + ":" + _text(binding.get("case_id")),
        "assessments": _expected_assessments(manifest_value, contract_value, receipt_value),
    }


def validate_anonymous_outcome_assessment(
    assessment: Any, *, manifest: Any, contract: Any, field_receipts: Any, claim_binding_receipt: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    value = _closed(assessment, {
        "schema_version", "state", "contract_id", "case_id", "anonymous_label", "manifest_id", "claim_binding_receipt_id", "assessments",
    }, "assessment", findings)
    manifest_value, contract_value, receipt_value = _mapping(manifest), _mapping(contract), _mapping(field_receipts)
    if value.get("schema_version") != ASSESSMENT_SCHEMA_VERSION or value.get("state") != "ANONYMOUS_OUTCOME_ASSESSMENT_FROZEN":
        findings.append("assessment.schema_or_state_invalid")
    for field, expected in {
        "contract_id": contract_value.get("contract_id"), "case_id": _mapping(contract_value.get("identity")).get("case_id"),
        "anonymous_label": manifest_value.get("anonymous_label"), "manifest_id": manifest_value.get("manifest_id"),
        "claim_binding_receipt_id": "RACBR:" + _text(_mapping(claim_binding_receipt).get("contract_id")) + ":" + _text(_mapping(claim_binding_receipt).get("case_id")),
    }.items():
        if value.get(field) != expected:
            findings.append("assessment." + field + "_mismatch")
    try:
        expected = build_anonymous_outcome_assessment(manifest_value, contract=contract_value, field_receipts=receipt_value, claim_binding_receipt=claim_binding_receipt)
    except ValueError as exc:
        findings.append("assessment.inputs_invalid:" + str(exc))
    else:
        if value != expected:
            findings.append("assessment.not_exact_declared_predicate_result")
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": findings}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("materialize", "validate"):
        command = sub.add_parser(name)
        command.add_argument("preregistration", type=Path)
        command.add_argument("--project-root", type=Path, default=_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        preregistration = _read_json(args.preregistration.expanduser().resolve())
        result = (
            materialize_case_contracts(preregistration, project_root=args.project_root)
            if args.command == "materialize"
            else validate_outcome_measurement_plane(preregistration, project_root=args.project_root)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": PLANE_VALIDATION_SCHEMA, "state": "INVALID", "findings": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("state") == "REVIEWABLE" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
