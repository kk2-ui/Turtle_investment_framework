#!/usr/bin/env python3
"""Turn bounded industry experience into a pre-underwriting evidence agenda.

The industry experience layer is useful when it changes what the next company
researcher looks for.  It must not smuggle a teacher-company fact, a valuation
parameter, or an action into a new issuer's report.  This module therefore has
three deliberately separate products:

* a small role-bound external-evidence plan derived from
  ``IndustryUnderwritingContext``;
* a receipt for sources actually reviewed before the report cutoff; and
* a conservative Episode binding that exposes only accepted industry
  observations and explicitly preserves the company-evidence step.

The module does not fetch documents or decide an investment conclusion.  A
source receipt is auditable only when it names a stable source reference,
publication/availability time, measurement boundary, locator and the company
transmission that still needs target-company evidence.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

try:
    from scripts.industry_underwriting_context import (
        DEFAULT_OUTPUT_NAME as CONTEXT_OUTPUT_NAME,
        validate_industry_underwriting_context,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from industry_underwriting_context import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT_NAME as CONTEXT_OUTPUT_NAME,
        validate_industry_underwriting_context,
    )


PLAN_SCHEMA_VERSION = "industry-evidence-acquisition-plan.v1"
RECEIPT_SCHEMA_VERSION = "industry-evidence-acquisition-receipt.v1"
VALIDATION_SCHEMA_VERSION = "industry-evidence-acquisition-validation.v1"
DEFAULT_PLAN_OUTPUT_NAME = "industry_evidence_acquisition_plan.json"
DEFAULT_RECEIPT_OUTPUT_NAME = "industry_evidence_acquisition_receipt.json"

_DRIVER_ROLES = {
    "demand": "DEMAND",
    "supply": "SUPPLY_COMPETITION",
    "competition": "SUPPLY_COMPETITION",
    "regulation": "REGULATION",
}
_ROLE_ORDER = (
    "DEMAND",
    "SUPPLY_COMPETITION",
    "PRICE_COST",
    "CUSTOMER_CHANNEL",
    "REGULATION",
    "COMPANY_TRANSMISSION",
)
_ROLE_SOURCE_REQUIREMENTS = {
    "DEMAND": (
        "OFFICIAL_STATISTICS",
        "INDUSTRY_ASSOCIATION",
        "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
    ),
    "SUPPLY_COMPETITION": (
        "REGULATORY_DISCLOSURE",
        "INDUSTRY_ASSOCIATION",
        "COMPETITOR_DISCLOSURE",
    ),
    "PRICE_COST": (
        "OFFICIAL_STATISTICS",
        "INDUSTRY_ASSOCIATION",
        "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
        "COMPETITOR_DISCLOSURE",
    ),
    "CUSTOMER_CHANNEL": (
        "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
        "INDUSTRY_ASSOCIATION",
        "COMPETITOR_DISCLOSURE",
    ),
    "REGULATION": ("REGULATORY_DISCLOSURE",),
    "COMPANY_TRANSMISSION": ("TARGET_COMPANY_DISCLOSURE",),
}
_SOURCE_KINDS = {
    "OFFICIAL_STATISTICS": {"GOVERNMENT_STATISTIC", "OFFICIAL_DATA_RELEASE"},
    "INDUSTRY_ASSOCIATION": {"INDUSTRY_ASSOCIATION_RELEASE", "INDUSTRY_ASSOCIATION_DATA"},
    "REGULATORY_DISCLOSURE": {"REGULATORY_NOTICE", "REGULATORY_DATA_RELEASE"},
    "COMPETITOR_DISCLOSURE": {"COMPETITOR_FILING", "COMPETITOR_IR_RELEASE"},
    "SUPPLIER_OR_CUSTOMER_DISCLOSURE": {
        "SUPPLIER_DISCLOSURE", "CUSTOMER_DISCLOSURE", "CHANNEL_PARTNER_DISCLOSURE",
    },
    "TARGET_COMPANY_DISCLOSURE": {"TARGET_COMPANY_FILING", "TARGET_COMPANY_IR_RELEASE"},
}
_RECEIPT_OUTCOMES = {
    "VERIFIED",
    "CONTRADICTED",
    "UNKNOWN",
    "PUBLIC_INFO_UNAVAILABLE",
}
_STOP_REASONS = {
    "COMPLETED",
    "CONFLICT_RETAINED",
    "PUBLIC_INFO_UNAVAILABLE",
    "SCOPE_MISMATCH",
}
_EVIDENCE_USES = {
    "INDUSTRY_FUTURE_THESIS",
    "COMPANY_TRANSMISSION_TEST",
    "NORMALIZATION_CONDITION",
    "PERMANENT_LOSS_CONDITION",
}
_FORBIDDEN_PROMOTION_KEYS = {
    "price",
    "market_price",
    "share_price",
    "buy_price",
    "buy_band",
    "buyband",
    "valuation",
    "valuation_parameter",
    "investment_action",
    "action",
    "owner_cash",
    "owner_cash_value",
    "expected_return",
}
_PRICE_COST_TERMS = (
    "price", "pricing", "cost", "margin", "input", "energy", "燃料", "价格", "成本", "毛利",
)
_CUSTOMER_CHANNEL_TERMS = (
    "customer", "channel", "client", "distribution", "dealer", "客户", "渠道", "经销", "终端",
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    return [item for raw in value if (item := _text(raw))]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _instant(value: Any, *, date_as_end: bool = False) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    if len(raw) == 10:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").replace(
                tzinfo=timezone(timedelta(hours=8))
            )
        except ValueError:
            return None
        if date_as_end:
            parsed = parsed.replace(hour=23, minute=59, second=59)
        return parsed.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _same_company(left: Any, right: Any) -> bool:
    first, second = _text(left).upper(), _text(right).upper()
    if not first or not second:
        return False
    if first == second:
        return True
    digits_first = "".join(char for char in first if char.isdigit())
    digits_second = "".join(char for char in second if char.isdigit())
    return (
        len(digits_first) >= 5
        and len(digits_second) >= 5
        and digits_first[-6:] == digits_second[-6:]
    )


def _forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            lowered = str(key).lower()
            if (
                lowered in _FORBIDDEN_PROMOTION_KEYS
                or lowered.endswith("_market_price")
                or lowered.endswith("_share_price")
            ):
                findings.append(path)
            else:
                findings.extend(_forbidden_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, f"{prefix}[{index}]"))
    return findings


def _identity(context: Mapping[str, Any]) -> dict[str, Any]:
    company = _mapping(context.get("company_identity"))
    return {
        "company_id": _text(company.get("company_id")),
        "company_name": _text(company.get("company_name")),
        "cutoff_at": _text(company.get("cutoff_at")),
        "industry_ids": _unique(_strings(company.get("industry_ids"))),
    }


def _driver_refs(context: Mapping[str, Any], driver_key: str) -> list[str]:
    refs: list[str] = []
    drivers = _mapping(context.get("industry_drivers"))
    for raw in _items(drivers.get(driver_key)):
        refs.extend(_strings(_mapping(raw).get("evidence_refs")))
    return _unique(refs)


def _driver_text(context: Mapping[str, Any], driver_key: str) -> str:
    drivers = _mapping(context.get("industry_drivers"))
    return " ".join(
        _text(_mapping(raw).get("driver")) for raw in _items(drivers.get(driver_key))
    ).lower()


def _verification_text(context: Mapping[str, Any]) -> str:
    return " ".join(
        _text(_mapping(item).get("field"))
        for item in _items(context.get("company_verification_fields"))
    ).lower()


def _task_wording(role: str) -> tuple[str, str, str, str]:
    """Return generic wording so experience never copies teacher-company facts."""
    wording = {
        "DEMAND": (
            "截至截止日，终端需求处于什么方向、强度和地区/产品边界？",
            "检验该需求条件如何通过本公司的客户覆盖、销量、利用率或业务量进入经营结果。",
            "行业或终端市场；不得把行业总量直接当作公司销量。",
            "当已取得同口径需求序列与本公司暴露证据，或公开资料无法提供该口径时停止。",
        ),
        "SUPPLY_COMPETITION": (
            "截至截止日，新增供给、产能约束、竞争结构或竞争者行为是否改变利润池？",
            "检验本公司的地区、产品、竞争位置和执行边界是否真的暴露于该结构变化。",
            "行业/竞争 arena 与本公司实际经营边界必须分别记录。",
            "当供给或竞争观察与本公司边界证据能够相互检验，或边界无法公开取得时停止。",
        ),
        "PRICE_COST": (
            "截至截止日，量价、关键投入成本或单位经济的变化是否足以改变行业利润池？",
            "检验该变化是否进入本公司的实现价格、单位成本、毛利或现金转换，而非仅存在于行业平均数。",
            "同一产品、地区、期间和单位；不得用行业均值替代公司实现口径。",
            "当量价/成本口径与公司传导证据一致，或公开资料不足以连接口径时停止。",
        ),
        "CUSTOMER_CHANNEL": (
            "截至截止日，客户需求、渠道结构或议价权是否改变收入质量和利润池分配？",
            "检验本公司客户/渠道责任边界、份额或服务能力是否足以承接该变化。",
            "客户/渠道对象、服务内容与本公司责任边界；不得把行业渠道趋势升级为公司优势。",
            "当客户/渠道变化与本公司暴露证据可以区分，或公开资料无法识别传导时停止。",
        ),
        "REGULATION": (
            "截至截止日，监管、准入、环保、标准或政策如何改变供给、成本或竞争规则？",
            "检验该规则是否覆盖本公司所处地区、资产、产品或许可边界，而不是推定其自动受益。",
            "监管适用范围与本公司资产/经营范围必须分别核对。",
            "当规则文本、适用期和本公司适用边界均已核对，或公开资料无法确定适用性时停止。",
        ),
        "COMPANY_TRANSMISSION": (
            "行业机制在本公司处的关键传导环节是什么，且哪一项公司披露可以证实或否定它？",
            "只验证本公司的经营、资本或竞争暴露；行业经验不得替代该公司的一手披露。",
            "目标公司合并口径及其明确披露的地区、产品、客户或资产边界。",
            "当公司一手披露能够确认、反证或保留该传导为未知时停止。",
        ),
    }
    return wording[role]


def _task(role: str, *, task_id: str, context_refs: Iterable[str]) -> dict[str, Any]:
    question, transmission, boundary, stop_rule = _task_wording(role)
    return {
        "task_id": task_id,
        "role": role,
        "decisive_question": question,
        "company_transmission_to_verify": transmission,
        "measurement_boundary": boundary,
        "required_source_roles": list(_ROLE_SOURCE_REQUIREMENTS[role]),
        "evidence_uses": [
            "INDUSTRY_FUTURE_THESIS",
            "COMPANY_TRANSMISSION_TEST",
        ],
        "stop_rule": stop_rule,
        "context_evidence_refs": _unique(context_refs),
    }


def compile_industry_evidence_acquisition_plan(
    context: Mapping[str, Any],
    *,
    context_ref: str = CONTEXT_OUTPUT_NAME,
) -> dict[str, Any]:
    """Compile no more than one small research task for each economic role."""
    source_context = deepcopy(dict(context))
    validation = validate_industry_underwriting_context(source_context)
    if validation.get("state") != "REVIEWABLE":
        raise ValueError(
            "industry_underwriting_context_not_reviewable:"
            + ",".join(_strings(validation.get("findings")))
        )
    identity = _identity(source_context)
    if not all(identity[key] for key in ("company_id", "company_name", "cutoff_at")):
        raise ValueError("industry_underwriting_context_identity_incomplete")

    role_refs: dict[str, list[str]] = {role: [] for role in _ROLE_ORDER}
    for driver, role in _DRIVER_ROLES.items():
        role_refs[role].extend(_driver_refs(source_context, driver))
    combined_text = " ".join(
        [
            *(_driver_text(source_context, key) for key in _DRIVER_ROLES),
            _verification_text(source_context),
        ]
    )
    if any(term in combined_text for term in _PRICE_COST_TERMS):
        role_refs["PRICE_COST"].extend(
            [
                *_driver_refs(source_context, "demand"),
                *_driver_refs(source_context, "supply"),
                *_driver_refs(source_context, "competition"),
            ]
        )
    if any(term in combined_text for term in _CUSTOMER_CHANNEL_TERMS):
        role_refs["CUSTOMER_CHANNEL"].extend(
            [
                *_driver_refs(source_context, "demand"),
                *_driver_refs(source_context, "competition"),
            ]
        )
    verification_fields = _items(source_context.get("company_verification_fields"))
    has_company_transmission_task = bool(verification_fields)
    if verification_fields:
        role_refs["COMPANY_TRANSMISSION"].extend(
            ref
            for item in verification_fields
            for ref in _strings(_mapping(item).get("evidence_refs"))
        )

    tasks: list[dict[str, Any]] = []
    for role in _ROLE_ORDER:
        refs = _unique(role_refs[role])
        if refs or (role == "COMPANY_TRANSMISSION" and has_company_transmission_task):
            tasks.append(_task(
                role,
                task_id=f"IEAT:{identity['company_id']}:{role}:{len(tasks) + 1}",
                context_refs=refs,
            ))
    warnings: list[str] = []
    if not tasks:
        warnings.append("no_role_specific_external_evidence_task_from_available_context")
    context_status = _text(source_context.get("context_status"))
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": f"IEAP:{identity['company_id']}:{identity['cutoff_at']}",
        "company_identity": identity,
        "source_context_ref": _text(context_ref),
        "context_id": _text(source_context.get("context_id")),
        "plan_status": "READY" if tasks and context_status == "READY" else "BOUNDED",
        "use_policy": {
            "mode": "PRE_UNDERWRITING_EXTERNAL_EVIDENCE_AGENDA",
            "non_blocking": True,
            "can_support": [
                "EXTERNAL_INDUSTRY_SOURCE_SELECTION",
                "COMPANY_TRANSMISSION_TEST_SELECTION",
                "INDUSTRY_FUTURE_THESIS_EVIDENCE_CANDIDATES",
            ],
            "cannot_establish": [
                "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE",
                "OWNER_CASH_VALUE",
                "VALUATION_PARAMETER",
                "INVESTMENT_ACTION",
            ],
            "boundary": "The plan expresses questions and source roles only. It contains no teacher-company facts, values, prices, valuation, or action.",
        },
        "tasks": tasks,
        "warnings": warnings,
    }
    result = validate_industry_evidence_acquisition_plan(payload)
    if result["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_acquisition_plan_invalid:" + ",".join(result["findings"]))
    return payload


def validate_industry_evidence_acquisition_plan(payload: Any) -> dict[str, Any]:
    """Validate the plan's identity and its prohibition on direct promotions."""
    value = _mapping(payload)
    findings: list[str] = []
    required = (
        "plan_id", "company_identity", "source_context_ref", "context_id", "plan_status",
        "use_policy", "tasks", "warnings",
    )
    if value.get("schema_version") != PLAN_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in required:
        if field not in value:
            findings.append(field + "_missing")
    identity = _mapping(value.get("company_identity"))
    for field in ("company_id", "company_name", "cutoff_at"):
        if not _text(identity.get(field)):
            findings.append("company_identity." + field + "_missing")
    if _instant(identity.get("cutoff_at"), date_as_end=True) is None:
        findings.append("company_identity.cutoff_at_invalid")
    if value.get("plan_status") not in {"READY", "BOUNDED"}:
        findings.append("plan_status_invalid")
    if not _text(value.get("source_context_ref")):
        findings.append("source_context_ref_missing")
    policy = _mapping(value.get("use_policy"))
    if policy.get("mode") != "PRE_UNDERWRITING_EXTERNAL_EVIDENCE_AGENDA":
        findings.append("use_policy.mode_invalid")
    if policy.get("non_blocking") is not True:
        findings.append("use_policy.non_blocking_required")
    tasks = _items(value.get("tasks"))
    if value.get("plan_status") == "READY" and not tasks:
        findings.append("ready_plan_tasks_missing")
    seen_ids: set[str] = set()
    seen_roles: set[str] = set()
    for index, raw in enumerate(tasks):
        task = _mapping(raw)
        path = f"tasks[{index}]"
        required_task_fields = {
            "task_id", "role", "decisive_question", "company_transmission_to_verify",
            "measurement_boundary", "required_source_roles", "evidence_uses", "stop_rule",
            "context_evidence_refs",
        }
        if set(task) != required_task_fields:
            findings.append(path + ".fields_invalid")
        task_id = _text(task.get("task_id"))
        if not task_id or task_id in seen_ids:
            findings.append(path + ".task_id_missing_or_duplicate")
        seen_ids.add(task_id)
        role = _text(task.get("role"))
        if role not in _ROLE_ORDER:
            findings.append(path + ".role_invalid")
        elif role in seen_roles:
            findings.append(path + ".role_duplicate")
        seen_roles.add(role)
        for field in (
            "decisive_question", "company_transmission_to_verify", "measurement_boundary", "stop_rule",
        ):
            if not _text(task.get(field)):
                findings.append(path + "." + field + "_missing")
        expected_roles = set(_ROLE_SOURCE_REQUIREMENTS.get(role, ()))
        supplied_roles = _strings(task.get("required_source_roles"))
        if set(supplied_roles) != expected_roles:
            findings.append(path + ".required_source_roles_invalid")
        evidence_uses = _strings(task.get("evidence_uses"))
        if not evidence_uses or any(item not in _EVIDENCE_USES for item in evidence_uses):
            findings.append(path + ".evidence_uses_invalid")
        if not isinstance(task.get("context_evidence_refs"), list):
            findings.append(path + ".context_evidence_refs_invalid")
    findings.extend("promotion_field_forbidden:" + path for path in _forbidden_paths(value))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def _source_reference_usable(source_ref: Any) -> bool:
    value = _text(source_ref)
    if not value or "://" in value:
        return False
    if value.startswith(("SRC:", "DOC:", "OBS:", "INDDOC:", "canonical:")):
        return True
    return Path(value).expanduser().is_file()


def _source_time_before_cutoff(value: Any, cutoff: datetime) -> tuple[bool, str]:
    raw = _text(value)
    moment = _instant(raw, date_as_end=False)
    if moment is None:
        return False, "invalid"
    if len(raw) == 10 and moment.date() == cutoff.date():
        return False, "time_unknown_at_cutoff"
    return (moment <= cutoff, "after_cutoff" if moment > cutoff else "ok")


def build_industry_evidence_acquisition_receipt(
    plan: Mapping[str, Any],
    task_receipts: Iterable[Mapping[str, Any]],
    *,
    source_plan_ref: str = DEFAULT_PLAN_OUTPUT_NAME,
) -> dict[str, Any]:
    """Bind completed, unknown, and contradicted research attempts to a plan."""
    plan_value = deepcopy(dict(plan))
    plan_validation = validate_industry_evidence_acquisition_plan(plan_value)
    if plan_validation["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_acquisition_plan_invalid:" + ",".join(plan_validation["findings"]))
    supplied = [
        deepcopy(dict(item)) if isinstance(item, Mapping) else deepcopy(item)
        for item in task_receipts
    ]
    planned_ids = {_text(item.get("task_id")) for item in _items(plan_value.get("tasks"))}
    receipt_ids = {_text(item.get("task_id")) for item in supplied}
    completion_state = "REVIEWABLE" if planned_ids <= receipt_ids else "PARTIAL"
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": f"IEAR:{plan_value['plan_id']}",
        "plan_id": plan_value["plan_id"],
        "source_plan_ref": _text(source_plan_ref),
        "company_identity": deepcopy(plan_value["company_identity"]),
        "completion_state": completion_state,
        "task_receipts": supplied,
        "warnings": [],
    }
    result = validate_industry_evidence_acquisition_receipt(payload, plan_value)
    if result["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_acquisition_receipt_invalid:" + ",".join(result["findings"]))
    return payload


def validate_industry_evidence_acquisition_receipt(
    receipt: Any,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate source time, role, boundary and local UNKNOWN/contradiction states."""
    value = _mapping(receipt)
    plan_value = _mapping(plan)
    findings: list[str] = []
    if validate_industry_evidence_acquisition_plan(plan_value).get("state") != "REVIEWABLE":
        findings.append("source_plan_not_reviewable")
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in (
        "receipt_id", "plan_id", "source_plan_ref", "company_identity", "completion_state",
        "task_receipts", "warnings",
    ):
        if field not in value:
            findings.append(field + "_missing")
    if value.get("plan_id") != plan_value.get("plan_id"):
        findings.append("plan_id_mismatch")
    if not _text(value.get("source_plan_ref")):
        findings.append("source_plan_ref_missing")
    identity = _mapping(value.get("company_identity"))
    plan_identity = _mapping(plan_value.get("company_identity"))
    if not _same_company(identity.get("company_id"), plan_identity.get("company_id")):
        findings.append("company_identity_mismatch")
    if _text(identity.get("cutoff_at")) != _text(plan_identity.get("cutoff_at")):
        findings.append("cutoff_identity_mismatch")
    cutoff = _instant(plan_identity.get("cutoff_at"), date_as_end=True)
    if cutoff is None:
        findings.append("plan_cutoff_invalid")
    if value.get("completion_state") not in {"PARTIAL", "REVIEWABLE"}:
        findings.append("completion_state_invalid")

    plan_tasks = {
        _text(item.get("task_id")): _mapping(item)
        for item in _items(plan_value.get("tasks"))
        if _text(_mapping(item).get("task_id"))
    }
    task_receipts = _items(value.get("task_receipts"))
    seen_task_ids: set[str] = set()
    seen_observation_ids: set[str] = set()
    received_ids: set[str] = set()
    for index, raw in enumerate(task_receipts):
        task_receipt = _mapping(raw)
        path = f"task_receipts[{index}]"
        required = {
            "task_id", "outcome", "research_summary", "attempted_source_roles", "stop_reason", "observations",
        }
        if set(task_receipt) != required:
            findings.append(path + ".fields_invalid")
        task_id = _text(task_receipt.get("task_id"))
        if not task_id or task_id in seen_task_ids:
            findings.append(path + ".task_id_missing_or_duplicate")
        seen_task_ids.add(task_id)
        received_ids.add(task_id)
        plan_task = plan_tasks.get(task_id)
        if plan_task is None:
            findings.append(path + ".task_not_in_plan")
            allowed_roles: set[str] = set()
        else:
            allowed_roles = set(_strings(plan_task.get("required_source_roles")))
        if task_receipt.get("outcome") not in _RECEIPT_OUTCOMES:
            findings.append(path + ".outcome_invalid")
        if not _text(task_receipt.get("research_summary")):
            findings.append(path + ".research_summary_missing")
        attempted = _strings(task_receipt.get("attempted_source_roles"))
        if not attempted or any(item not in allowed_roles for item in attempted):
            findings.append(path + ".attempted_source_roles_invalid")
        if task_receipt.get("stop_reason") not in _STOP_REASONS:
            findings.append(path + ".stop_reason_invalid")
        observations = _items(task_receipt.get("observations"))
        if task_receipt.get("outcome") in {"VERIFIED", "CONTRADICTED"} and not observations:
            findings.append(path + ".observations_required_for_outcome")
        if task_receipt.get("outcome") in {"UNKNOWN", "PUBLIC_INFO_UNAVAILABLE"} and observations:
            findings.append(path + ".observations_not_allowed_for_unknown")
        for obs_index, raw_observation in enumerate(observations):
            observation = _mapping(raw_observation)
            obs_path = f"{path}.observations[{obs_index}]"
            required_observation = {
                "observation_id", "source_role", "source_kind", "source_ref", "source_url",
                "publisher", "published_at", "available_at", "period", "locator", "metric", "unit",
                "responsibility_boundary", "statement", "company_transmission", "relation", "evidence_use",
            }
            if set(observation) != required_observation:
                findings.append(obs_path + ".fields_invalid")
            observation_id = _text(observation.get("observation_id"))
            if not observation_id or observation_id in seen_observation_ids:
                findings.append(obs_path + ".observation_id_missing_or_duplicate")
            seen_observation_ids.add(observation_id)
            for field in required_observation - {"period"}:
                if not _text(observation.get(field)):
                    findings.append(obs_path + "." + field + "_missing")
            if not _text(observation.get("period")):
                findings.append(obs_path + ".period_missing")
            source_role = _text(observation.get("source_role"))
            if source_role not in allowed_roles:
                findings.append(obs_path + ".source_role_not_permitted")
            elif _text(observation.get("source_kind")) not in _SOURCE_KINDS[source_role]:
                findings.append(obs_path + ".source_kind_not_permitted")
            if not _source_reference_usable(observation.get("source_ref")):
                findings.append(obs_path + ".source_ref_invalid")
            source_url = urlparse(_text(observation.get("source_url")))
            if source_url.scheme != "https" or not source_url.netloc:
                findings.append(obs_path + ".source_url_invalid")
            if cutoff is not None:
                for field in ("published_at", "available_at"):
                    accepted, reason = _source_time_before_cutoff(observation.get(field), cutoff)
                    if not accepted:
                        findings.append(obs_path + f".{field}_{reason}")
                published = _instant(observation.get("published_at"), date_as_end=False)
                available = _instant(observation.get("available_at"), date_as_end=False)
                if published is not None and available is not None and available < published:
                    findings.append(obs_path + ".available_before_published")
            if observation.get("relation") not in {"SUPPORTS", "CONTRADICTS"}:
                findings.append(obs_path + ".relation_invalid")
            if observation.get("evidence_use") not in _EVIDENCE_USES:
                findings.append(obs_path + ".evidence_use_invalid")
    if value.get("completion_state") == "REVIEWABLE" and set(plan_tasks) != received_ids:
        findings.append("reviewable_receipt_does_not_cover_plan")
    if value.get("completion_state") == "PARTIAL" and set(plan_tasks) <= received_ids:
        findings.append("partial_receipt_covers_plan")
    findings.extend("promotion_field_forbidden:" + path for path in _forbidden_paths(value))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def build_episode_industry_evidence_binding(
    receipt: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    receipt_ref: str = DEFAULT_RECEIPT_OUTPUT_NAME,
) -> dict[str, Any]:
    """Expose admitted observations as optional Episode trace candidates.

    The caller must still pair them with target-company evidence.  The binding
    intentionally does not create an Episode or alter its economic treatments.
    """
    result = validate_industry_evidence_acquisition_receipt(receipt, plan)
    if result["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_acquisition_receipt_invalid:" + ",".join(result["findings"]))
    candidates: list[dict[str, Any]] = []
    for task_receipt in _items(receipt.get("task_receipts")):
        if _mapping(task_receipt).get("outcome") not in {"VERIFIED", "CONTRADICTED"}:
            continue
        for observation in _items(_mapping(task_receipt).get("observations")):
            item = _mapping(observation)
            candidates.append({
                "evidence_id": "IEA:" + _text(item.get("observation_id")),
                "source_ref": _text(item.get("source_ref")),
                "locator": _text(item.get("locator")),
                "scope": (
                    "External " + _text(item.get("source_role"))
                    + " observation; boundary: " + _text(item.get("responsibility_boundary"))
                    + "."
                ),
                "used_for": (
                    _text(item.get("evidence_use"))
                    + "; target-company transmission still requires its own primary evidence: "
                    + _text(item.get("company_transmission"))
                ),
            })
    return {
        "status": "READY" if candidates else "NO_ADMITTED_EXTERNAL_OBSERVATIONS",
        "existing_object_ref": {
            "kind": "INDUSTRY_EVIDENCE_ACQUISITION_RECEIPT",
            "ref": _text(receipt_ref),
            "role": "External industry observations select and test company transmission; they never establish a target-company fact, owner-cash value, valuation parameter, or investment action by themselves.",
        },
        "evidence_trace_candidates": candidates,
        "instruction": "Use only with the cited target-company primary evidence. UNKNOWN and PUBLIC_INFO_UNAVAILABLE remain valid local research outcomes and emit no trace candidate.",
    }


def project_industry_evidence_acquisition_for_handoff(
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any] | None = None,
    *,
    receipt_ref: str = DEFAULT_RECEIPT_OUTPUT_NAME,
) -> dict[str, Any]:
    """Produce the bounded RESEARCH_AGENDA slice; sources remain canonical."""
    plan_value = deepcopy(dict(plan))
    if validate_industry_evidence_acquisition_plan(plan_value).get("state") != "REVIEWABLE":
        raise ValueError("industry_evidence_acquisition_plan_invalid")
    receipt_value = deepcopy(dict(receipt or {}))
    receipt_state = "NOT_RECORDED"
    accepted: list[dict[str, Any]] = []
    binding: dict[str, Any] = {
        "status": "NOT_RECORDED",
        "instruction": "Complete role-bound external evidence receipts before using an observation in an Episode.",
    }
    if receipt_value:
        receipt_validation = validate_industry_evidence_acquisition_receipt(receipt_value, plan_value)
        if receipt_validation.get("state") != "REVIEWABLE":
            raise ValueError("industry_evidence_acquisition_receipt_invalid")
        receipt_state = _text(receipt_value.get("completion_state"))
        binding = build_episode_industry_evidence_binding(
            receipt_value, plan_value, receipt_ref=receipt_ref,
        )
        for task_receipt in _items(receipt_value.get("task_receipts")):
            task = _mapping(task_receipt)
            for observation in _items(task.get("observations")):
                item = _mapping(observation)
                accepted.append({
                    "observation_id": _text(item.get("observation_id")),
                    "task_id": _text(task.get("task_id")),
                    "relation": _text(item.get("relation")),
                    "source_ref": _text(item.get("source_ref")),
                    "source_role": _text(item.get("source_role")),
                    "metric": _text(item.get("metric")),
                    "unit": _text(item.get("unit")),
                    "evidence_use": _text(item.get("evidence_use")),
                })
    return {
        "plan_id": _text(plan_value.get("plan_id")),
        "plan_status": _text(plan_value.get("plan_status")),
        "source_context_ref": _text(plan_value.get("source_context_ref")),
        "use_policy": deepcopy(_mapping(plan_value.get("use_policy"))),
        "tasks": deepcopy(_items(plan_value.get("tasks"))),
        "receipt_state": receipt_state,
        "accepted_observations": accepted,
        "episode_binding": binding,
        "instruction": "Use this agenda to acquire and assess industry evidence before writing. Return to the cited source before using an observation; do not promote the plan or an industry observation into a company fact, owner-cash value, valuation input, price, or action.",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_command = sub.add_parser("compile-plan")
    compile_command.add_argument("--context", required=True, type=Path)
    compile_command.add_argument("--output", required=True, type=Path)
    validate_plan_command = sub.add_parser("validate-plan")
    validate_plan_command.add_argument("--plan", required=True, type=Path)
    receipt_command = sub.add_parser("build-receipt")
    receipt_command.add_argument("--plan", required=True, type=Path)
    receipt_command.add_argument("--task-receipts", required=True, type=Path)
    receipt_command.add_argument("--output", required=True, type=Path)
    validate_receipt_command = sub.add_parser("validate-receipt")
    validate_receipt_command.add_argument("--plan", required=True, type=Path)
    validate_receipt_command.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.command == "compile-plan":
        context = _read_json(args.context)
        payload = compile_industry_evidence_acquisition_plan(context, context_ref=str(args.context))
        _write_json(args.output, payload)
        print(json.dumps({"state": payload["plan_status"], "output": str(args.output)}, ensure_ascii=False))
        return 0
    if args.command == "validate-plan":
        result = validate_industry_evidence_acquisition_plan(_read_json(args.plan))
    elif args.command == "build-receipt":
        source = _read_json(args.task_receipts)
        task_receipts = source.get("task_receipts") if isinstance(source.get("task_receipts"), list) else source
        payload = build_industry_evidence_acquisition_receipt(
            _read_json(args.plan), task_receipts, source_plan_ref=str(args.plan),
        )
        _write_json(args.output, payload)
        print(json.dumps({"state": payload["completion_state"], "output": str(args.output)}, ensure_ascii=False))
        return 0
    else:
        result = validate_industry_evidence_acquisition_receipt(
            _read_json(args.receipt), _read_json(args.plan),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "REVIEWABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
