#!/usr/bin/env python3
"""Pre-writing engine that selects the few questions able to change a decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    from scripts.evidence_documents import _atomic_write_json
    from scripts.insight_research import classify_company_archetype
    from scripts.judgment_research_router import route_research_need
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json
    from insight_research import classify_company_archetype
    from judgment_research_router import route_research_need


SCHEMA_VERSION = "decisive-question-plan.v1"
POLICY_VERSION = "decisive-question-policy.v1"
VALIDATION_VERSION = "decisive-question-validation.v1"
FINDINGS_VERSION = "decisive-question-findings.v1"
MAX_SELECTED = 3
MINIMUM_PRIORITY = 0.48
INDUSTRY_COMPANY_ASSESSMENTS = {
    "SUPPORTED", "CONTRADICTED", "NOT_EVIDENCED", "NOT_APPLICABLE",
}
WEIGHTS = {
    "decision_sensitivity": 0.35,
    "evidence_discriminability": 0.25,
    "observability": 0.15,
    "time_value": 0.15,
    "base_rate_relevance": 0.10,
}
KNOWN_METRIC_IDS = {
    "market.price.current", "return.gg.base", "return.gg.fcfe", "return.gg.normalized",
    "hurdle.ii", "valuation.v_final", "moat.lambda", "return.required", "moat.decay",
    "margin.price", "margin.return", "decision.position.recommended", "trigger.buy",
    "trigger.reduce", "trigger.exit",
}
PIT_INDUSTRY_DEGRADATION = "pit_global_industry_knowledge_forbidden_without_object_level_admission"
PIT_BASE_RATE_DEGRADATION = "pit_global_base_rate_library_forbidden_without_case_level_admission"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _pit_contract(output_dir: str | Path) -> dict[str, Any]:
    contract = _load(Path(output_dir) / "analysis_contract.json")
    pit = contract.get("pit_production")
    return {"_present": True, **pit} if isinstance(pit, dict) else {}


def _pit_plan_knowledge_safe(plan: dict[str, Any]) -> bool:
    industry = (
        plan.get("industry_knowledge_context")
        if isinstance(plan.get("industry_knowledge_context"), dict) else {}
    )
    availability = industry.get("availability") if isinstance(industry.get("availability"), dict) else {}
    if availability.get("mode") != "PIT_EVIDENCE_ONLY" or industry.get("matched_mechanisms"):
        return False
    for item in plan.get("selected_questions") or []:
        if not isinstance(item, dict):
            return False
        try:
            sample_size = int(item.get("base_rate_sample_size") or 0)
        except (TypeError, ValueError):
            return False
        if item.get("base_rate_refs") or sample_size != 0:
            return False
        if any(str(origin).startswith("industry_knowledge:") for origin in item.get("candidate_origins") or []):
            return False
    return True


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


_FINDING_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)


def _finding_numbers(value: Any) -> list[float]:
    result: list[float] = []
    text = re.sub(
        r"\b(?:OBS|CALC):[A-Za-z0-9_.:@/=-]+", "", str(value or "")
    )
    text = re.sub(
        r"(?<![A-Za-z])p(?:age)?\.?\s*\d+|第\s*\d+\s*页",
        "", text, flags=re.IGNORECASE,
    )
    for token in _FINDING_NUMBER_RE.findall(text):
        try:
            number = float(token.replace(",", ""))
        except ValueError:
            continue
        if number.is_integer() and 1900 <= number <= 2100:
            continue
        result.append(number)
    return result


def _unsupported_numbers(text: str, sources: list[Any]) -> list[float]:
    asserted = _finding_numbers(text)
    if not asserted:
        return []
    supported: list[float] = []
    for source in sources:
        if isinstance(source, dict):
            matched_field = False
            for field in ("raw_text", "raw_value", "normalized_value", "value"):
                if field in source:
                    matched_field = True
                    supported.extend(_finding_numbers(source.get(field)))
            if not matched_field:
                supported.extend(_finding_numbers(_canonical(source)))
        else:
            supported.extend(_finding_numbers(source))
    return [
        value for value in asserted
        if not any(
            math.isclose(value, candidate, rel_tol=1e-6, abs_tol=0.00501)
            for candidate in supported
        )
    ]


def _numbers_supported(text: str, sources: list[Any]) -> bool:
    return not _unsupported_numbers(text, sources)


def _unsupported_suffix(values: list[float]) -> str:
    return "|".join(format(value, ".12g") for value in dict.fromkeys(values))


_EVIDENCE_REF_RE = re.compile(r"\[((?:OBS|CALC):[A-Za-z0-9_.:@/=-]+)\]")
_LOCAL_NUMBER_RE = re.compile(
    r"([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?:%|pct|pp|x|倍|M|百万元|元|RMB|HKD)?\s*$",
    re.IGNORECASE,
)
_ABSOLUTE_ASSERTIONS = (
    "唯一", "排除", "确保", "充分折价", "所有重大决策", "无有息负债",
    "无资产抵押", "无强制机制", "上市以来无回购", "不构成",
)
_INFERENCE_MARKERS = (
    "驱动", "导致", "源于", "因为", "因此", "表明", "证明", "反映",
    "意味着", "结构性", "可持续", "主要威胁", "主要兑现路径", "主导重大决策",
    "理论上可分配", "假象", "加强结构恶化判断",
)
_INFERENCE_TAG_RE = re.compile(r"\[inference(?::\s*([^\]]+))?\]", re.I)
_NEGATIVE_EVIDENCE_TAG_RE = re.compile(
    r"\[negative-evidence(?::\s*([^\]]+))?\]", re.I
)


def _citation_numeric_mismatches(
    text: str, sources_by_id: dict[str, Any], declared_ids: set[str]
) -> list[str]:
    """Require each adjacent evidence identity to support its own displayed number.

    Pooling every number in a paragraph allowed one CALC identity to impersonate
    another calculation with the same displayed value.  Only the number directly
    adjacent to ``[OBS:...]`` or ``[CALC:...]`` is checked here; the existing
    paragraph-level check remains as a second line of defence.
    """
    mismatches: list[str] = []
    for match in _EVIDENCE_REF_RE.finditer(str(text or "")):
        evidence_id = match.group(1)
        if evidence_id not in declared_ids or evidence_id not in sources_by_id:
            continue
        prefix = str(text or "")[max(0, match.start() - 64):match.start()]
        number_match = _LOCAL_NUMBER_RE.search(prefix)
        if not number_match:
            continue
        number = float(number_match.group(1).replace(",", ""))
        if not _numbers_supported(str(number), [sources_by_id[evidence_id]]):
            mismatches.append(f"{evidence_id}={format(number, '.12g')}")
    return list(dict.fromkeys(mismatches))


def _unsupported_absolute_assertions(text: str, sources: list[Any]) -> list[str]:
    raw = "\n".join(
        str(source.get("raw_text") or source.get("fact") or "")
        for source in sources if isinstance(source, dict)
    )
    return [
        token for token in _ABSOLUTE_ASSERTIONS
        if token in str(text or "") and token not in raw
    ]


def _dimensionally_invalid_comparisons(text: str) -> list[str]:
    invalid: list[str] = []
    for sentence in re.split(r"[。；;\n]", str(text or "")):
        if not re.search(r"远?[高低]于|超过|不及", sentence):
            continue
        has_money = bool(re.search(r"\d(?:[\d,.]*)\s*(?:M|百万元|亿元|RMB|HKD)", sentence, re.I))
        has_rate = bool(re.search(r"\d(?:[\d,.]*)\s*(?:%|pct|pp)", sentence, re.I))
        if has_money and has_rate:
            invalid.append(sentence.strip()[:120])
    return invalid


def _unlabeled_inference_claims(text: str, sources: list[Any]) -> list[str]:
    """Expose analyst inference instead of letting it masquerade as source fact."""
    raw = "\n".join(
        str(source.get("raw_text") or source.get("fact") or "")
        for source in sources if isinstance(source, dict)
    )
    invalid: list[str] = []
    for sentence in re.split(r"[。；;\n]", str(text or "")):
        if _INFERENCE_TAG_RE.search(sentence):
            continue
        # Epistemic limits such as "cannot prove access" are safeguards, not
        # positive causal claims.  Remove only the negated marker phrase; a
        # separate positive "X proves Y" in the same sentence is still caught.
        marker_text = re.sub(
            r"(?:不|并不|不能|无法|未能|难以)(?:单独|据此)?(?:证明|表明|意味着)",
            "", sentence,
        )
        markers = [
            marker for marker in _INFERENCE_MARKERS
            if marker in marker_text and marker not in raw
        ]
        if re.search(r"(?:无法|不能|难以)用?.{0,16}解释", sentence) and "解释" not in raw:
            markers.append("无法由其他因素解释")
        if markers:
            invalid.append("+".join(markers) + "=" + sentence.strip()[:100])
    return invalid


def _undisclosed_negative_evidence(text: str) -> bool:
    value = str(text or "")
    is_negative_search = bool(re.search(
        r"(?:0\s*(?:hits?|命中)|未发现|未發現|未检索到|未檢索到|未载明|未載明)",
        value, re.I,
    ))
    return is_negative_search and not _NEGATIVE_EVIDENCE_TAG_RE.search(value)


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _scalar_leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            leaves.update(_scalar_leaves(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            leaves.update(_scalar_leaves(item, f"{prefix}[{index}]"))
    elif value is not None:
        leaves[prefix] = value
    return leaves


def _source_value(path: Path, payload: dict[str, Any]) -> str:
    if path.name == "report_context.json":
        return str(_nested(payload, "meta", "context_fingerprint") or _hash(payload))
    value = deepcopy(payload)
    value.pop("generated_at", None)
    value.pop("updated_at", None)
    return _hash(value)


def decisive_input_sources(output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    names = [
        "report_context.json", "compute_bundle.json", "analysis_contract.json",
        "valuation_model.json", "industry_context.json", "segments.json",
        "governance.json", "risks.json", "moat_assessment.json",
        "zone_b_v8_master.json", "zone_j_parameters.json", "data_pack_market.md",
        "company_archetype.json", "valuation_route.json",
        "base_rate_context.json",
    ]
    result: dict[str, str] = {}
    for name in names:
        path = output / name
        if not path.is_file():
            continue
        if path.suffix.lower() == ".json":
            payload = _load(path)
            if payload:
                result[name] = _source_value(path, payload)
        else:
            try:
                result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
    return dict(sorted(result.items()))


def decisive_input_fingerprint(input_sources: dict[str, str]) -> str:
    return _hash(input_sources)


def _industry_usage_contract() -> dict[str, Any]:
    """Keep industry knowledge in its proper role: a research aid, never evidence.

    A cross-company mechanism can tell the analyst which alternative explanation
    to test and which fields to seek.  It cannot establish that the mechanism
    applies to this issuer, nor supply an input to the valuation model.
    """
    return {
        "may_supply": ["decisive_research_questions", "alternative_explanations", "company_verification_fields"],
        "must_not_supply": ["claim_evidence", "official_observation", "valuation_parameter", "probability", "price", "action_basis"],
        "company_evidence_required": True,
    }


def _industry_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    source_metadata = profile.get("source_metadata")
    source_files = (
        source_metadata.get("source_metadata_files")
        if isinstance(source_metadata, dict) else []
    )
    return {
        "schema_version": str(profile.get("schema_version") or "industry-profile-unavailable.v1"),
        "company_id": str(profile.get("company_id") or ""),
        "industry_keys": [
            str(item) for item in profile.get("industry_keys") or [] if str(item).strip()
        ],
        "profile_role": str(profile.get("profile_role") or "UNKNOWN"),
        "source_basis": ",".join(
            str(item) for item in source_files if str(item).strip()
        ) or str(profile.get("source_basis") or "company_archetype_and_official_context"),
    }


def _industry_fields(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
        elif isinstance(value, list):
            result.extend(str(item).strip() for item in value if str(item).strip())
    return list(dict.fromkeys(result))


def build_industry_knowledge_context(output_dir: str | Path) -> dict[str, Any]:
    """Create the plan-safe projection of reusable industry mechanisms.

    The core knowledge module owns the full mechanism cards and matching
    implementation.  The decisive-question layer records only the matched ID,
    why it was surfaced, and the issuer fields that still need official
    verification.  Every match starts as NOT_EVIDENCED by design.
    """
    output = Path(output_dir)
    usage_contract = _industry_usage_contract()
    pit = _pit_contract(output)
    if pit:
        return {
            "source": "industry_knowledge",
            "profile": _industry_profile_summary({}),
            "matched_mechanisms": [],
            "validation_status": "PIT_EVIDENCE_ONLY",
            "availability": {
                "mode": "PIT_EVIDENCE_ONLY",
                "cutoff_at": str(pit.get("cutoff_at") or ""),
                "industry_knowledge": "UNAVAILABLE_NO_OBJECT_LEVEL_ADMISSION",
            },
            "usage_contract": usage_contract,
            "warnings": [PIT_INDUSTRY_DEGRADATION],
        }
    try:
        from scripts.industry_knowledge import (
            build_company_industry_profile,
            load_company_industry_metadata,
            read_industry_knowledge_context,
        )
    except ModuleNotFoundError:
        try:
            from industry_knowledge import (
                build_company_industry_profile,
                load_company_industry_metadata,
                read_industry_knowledge_context,
            )
        except ModuleNotFoundError:
            return {
                "source": "industry_knowledge",
                "profile": _industry_profile_summary({}),
                "matched_mechanisms": [],
                "validation_status": "UNAVAILABLE",
                "usage_contract": usage_contract,
                "warnings": ["industry_knowledge_module_unavailable"],
            }
    try:
        company_input = load_company_industry_metadata(output)
        industry_keys = company_input.get("industry_keys") or []
        mechanism_keys = company_input.get("mechanism_keys") or []
        profile = build_company_industry_profile(
            company_input, industry_keys=industry_keys,
            mechanism_keys=mechanism_keys, max_ready=3, max_corroborated=0,
        )
        profile = profile if isinstance(profile, dict) else {}
        raw_context = read_industry_knowledge_context(
            company_input, industry_keys=industry_keys,
            mechanism_keys=mechanism_keys, max_ready=3, max_corroborated=0,
        )
        raw_context = raw_context if isinstance(raw_context, dict) else {}
    except Exception as exc:
        return {
            "source": "industry_knowledge",
            "profile": _industry_profile_summary({}),
            "matched_mechanisms": [],
            "validation_status": "UNAVAILABLE",
            "usage_contract": usage_contract,
            "warnings": [f"industry_knowledge_context_unavailable:{type(exc).__name__}"],
        }

    context_profile = raw_context.get("profile")
    if isinstance(context_profile, dict) and context_profile:
        profile = context_profile
    mechanism_by_id = {
        str(item.get("mechanism_id")): item
        for item in profile.get("mechanisms") or []
        if isinstance(item, dict) and str(item.get("mechanism_id") or "").strip()
    }
    research_rows = [
        item for item in raw_context.get("research_questions") or []
        if isinstance(item, dict) and str(item.get("mechanism_id") or "").strip()
    ]
    research_by_id = {
        str(item.get("mechanism_id")): item for item in research_rows
    }
    matches: list[dict[str, Any]] = []
    for mechanism_id in sorted(set(mechanism_by_id) | set(research_by_id)):
        mechanism = mechanism_by_id.get(mechanism_id, {})
        research = research_by_id.get(mechanism_id, {})
        status = str(
            research.get("status") or mechanism.get("status") or "NOT_READY"
        )
        fields = _industry_fields(
            research.get("company_verification_fields"),
            mechanism.get("company_verification_fields"),
            profile.get("required_company_verification_fields"),
        )
        if not fields:
            fields = ["本公司对应经营、成本、现金或治理披露"]
        company_industries = ",".join(
            str(item) for item in profile.get("industry_keys") or [] if str(item).strip()
        ) or "UNKNOWN"
        mechanism_industries = ",".join(
            str(item) for item in mechanism.get("industry_keys") or [] if str(item).strip()
        ) or "UNKNOWN"
        reason = str(
            research.get("match_reason") or mechanism.get("match_reason")
            or research.get("reason") or mechanism.get("reason")
            or (
                f"本公司行业键[{company_industries}]命中机制行业键"
                f"[{mechanism_industries}]；仍须以本公司官方披露逐项验证"
            )
        )
        matches.append({
            "mechanism_id": mechanism_id,
            "mechanism_key": str(
                research.get("mechanism_key") or mechanism.get("mechanism_key")
                or mechanism_id
            ),
            "title": str(research.get("title") or mechanism.get("title") or mechanism_id),
            "status": status,
            "match_reason": reason,
            "company_verification_fields": fields,
            "alternative_explanations": _industry_fields(
                research.get("alternative_explanations"),
                mechanism.get("alternative_explanations"),
            ),
            "company_assessment": "NOT_EVIDENCED",
            # This is updated after ranking. A ready card may still lose to a
            # more decision-relevant question when the three-question cap binds.
            "question_injected": False,
            "forbidden_model_role": str(
                research.get("forbidden_model_role") or mechanism.get("forbidden_model_role")
                or "not_a_claim_evidence_or_valuation_input"
            ),
        })
    warnings = [str(item) for item in raw_context.get("warnings") or [] if str(item).strip()]
    return {
        "source": "industry_knowledge",
        "profile": _industry_profile_summary(profile),
        "matched_mechanisms": matches,
        "validation_status": str(
            raw_context.get("validation_status") or raw_context.get("state") or "AVAILABLE"
        ),
        "availability": raw_context.get("availability") or {
            "mode": "CURRENT_LIBRARY", "industry_knowledge": "AVAILABLE",
        },
        "usage_contract": usage_contract,
        "warnings": warnings,
    }


def make_question_id(report_id: str, topic_family: str, mechanism_key: str) -> str:
    suffix = _hash({
        "report_id": str(report_id), "topic_family": str(topic_family),
        "mechanism_key": str(mechanism_key),
    })[:14]
    return f"DQ:{topic_family}:{suffix}"


def _observations(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for values in (context.get("domains") or {}).values() for item in values
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    ]


def _observation_ids(
    context: dict[str, Any], *, domains: tuple[str, ...] = (), fact_names: tuple[str, ...] = ()
) -> list[str]:
    result = []
    for item in _observations(context):
        if domains and str(item.get("domain")) not in domains:
            continue
        if fact_names and str(item.get("fact_name")) not in fact_names:
            continue
        result.append(str(item["observation_id"]))
    return sorted(set(result))


def _observation_ids_by_tokens(
    context: dict[str, Any], *, domains: tuple[str, ...], tokens: tuple[str, ...]
) -> list[str]:
    """Select VERIFIED observations whose stable fact identity is mechanism-relevant."""
    result: list[str] = []
    lowered_tokens = tuple(token.lower() for token in tokens)
    for item in _observations(context):
        if domains and str(item.get("domain")) not in domains:
            continue
        fact_name = str(item.get("fact_name") or "").lower()
        if any(token in fact_name for token in lowered_tokens):
            result.append(str(item["observation_id"]))
    return sorted(set(result))


def _score(
    decision_sensitivity: float,
    evidence_discriminability: float,
    observability: float,
    time_value: float,
    base_rate_relevance: float,
    basis: list[str],
    *,
    redundancy_penalty: float = 0.0,
) -> dict[str, Any]:
    components = {
        "decision_sensitivity": _clip(decision_sensitivity),
        "evidence_discriminability": _clip(evidence_discriminability),
        "observability": _clip(observability),
        "time_value": _clip(time_value),
        "base_rate_relevance": _clip(base_rate_relevance),
    }
    priority = sum(WEIGHTS[key] * components[key] for key in WEIGHTS) - _clip(redundancy_penalty)
    return {
        **components,
        "redundancy_penalty": _clip(redundancy_penalty),
        "priority": _clip(priority),
        "basis": [str(item) for item in basis if str(item).strip()],
    }


def _explanations(
    topic: str,
    label_a: str,
    mechanism_a: str,
    label_b: str,
    mechanism_b: str,
    support_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    ids = list(support_ids or [])
    return [
        {
            "explanation_id": f"{topic}.A", "label": label_a, "mechanism": mechanism_a,
            "current_support_observation_ids": ids, "current_contradiction_observation_ids": [],
        },
        {
            "explanation_id": f"{topic}.B", "label": label_b, "mechanism": mechanism_b,
            "current_support_observation_ids": [], "current_contradiction_observation_ids": ids,
        },
    ]


def _signal(
    signal_id: str,
    observable: str,
    direction_a: str,
    direction_b: str,
    source_type: str,
    window: str,
    observation_ids: list[str] | None = None,
    availability: str = "下一次定期报告或现有年报逐页回读",
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "observable": observable,
        "direction_if_explanation_a": direction_a,
        "direction_if_explanation_b": direction_b,
        "source_type": source_type,
        "availability": availability,
        "observation_window": window,
        "current_observation_ids": list(observation_ids or []),
    }


def _decision_link(
    metric_ids: list[str],
    sensitivity_basis: dict[str, Any],
    action_a: tuple[str, str, str],
    action_b: tuple[str, str, str],
    flip_condition: str,
) -> dict[str, Any]:
    return {
        "affected_metric_ids": metric_ids,
        "sensitivity_basis": sensitivity_basis,
        "if_explanation_a": {
            "valuation_direction": action_a[0], "position_direction": action_a[1], "action": action_a[2],
        },
        "if_explanation_b": {
            "valuation_direction": action_b[0], "position_direction": action_b[1], "action": action_b[2],
        },
        "flip_condition": flip_condition,
    }


def _premise_assessment_policy(
    topic_family: str, sensitivity_basis: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Define what each scalar premise can and cannot diagnose.

    A decision-sensitive input is not automatically a discriminating signal.  In
    particular, a large cash balance establishes the importance of the cash
    question but says nothing by itself about control or distribution access.
    Keeping this policy in the plan prevents the synthesis model from inventing a
    direction after seeing the desired decision.
    """
    policies: dict[str, dict[str, Any]] = {}
    for premise_key, value in _scalar_leaves(sensitivity_basis).items():
        policies[premise_key] = {
            "allowed_directions": ["SUPPORTS_A", "SUPPORTS_B", "NEUTRAL", "UNKNOWN"],
            "diagnostic_role": "decision_input",
            "interpretation_rule": (
                "只判断该前提本身对竞争解释的区分力；不得用市场价格或最终动作反推方向"
            ),
            "requires_decisive_plan_calculation": True,
        }

    if topic_family == "cash_value_realization":
        if "net_cash_pct_market_cap" in policies:
            policies["net_cash_pct_market_cap"].update({
                "allowed_directions": ["NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "stakes_only_not_cash_access",
                "interpretation_rule": (
                    "净现金/市值只说明潜在价值规模和研究重要性，不能单独证明现金可达或受控；"
                    "不得把市场折价当作现金受控的证据"
                ),
            })
        if "dividend_coverage_years" in policies:
            try:
                years = float(sensitivity_basis["dividend_coverage_years"])
            except (TypeError, ValueError, KeyError):
                years = 0.0
            if years >= 10:
                allowed = ["SUPPORTS_B", "NEUTRAL", "UNKNOWN"]
                rule = (
                    "高覆盖年数同时表示支付能力充足和按当前分红速度兑现缓慢；对“合理时间兑现”"
                    "不得判为SUPPORTS_A，支付能力不能替代分配意愿"
                )
            else:
                allowed = ["SUPPORTS_A", "NEUTRAL", "UNKNOWN"]
                rule = "较低覆盖年数可支持较快兑现，但仍须另有治理证据证明分配意愿"
            policies["dividend_coverage_years"].update({
                "allowed_directions": allowed,
                "diagnostic_role": "realization_speed_at_current_distribution",
                "interpretation_rule": rule,
            })
    if topic_family == "owner_return_hurdle":
        try:
            hurdle = float(sensitivity_basis["ii_pct"])
        except (TypeError, ValueError, KeyError):
            hurdle = None
        for key in (
            "gg_base_pct", "gg_discounted_pct", "gg_fcfe_pct",
            "gg_error_range_pct[0]", "gg_error_range_pct[1]",
        ):
            if key not in policies or hurdle is None:
                continue
            try:
                premise_value = float(_scalar_leaves(sensitivity_basis)[key])
            except (TypeError, ValueError, KeyError):
                continue
            supports = "SUPPORTS_A" if premise_value > hurdle else "SUPPORTS_B"
            policies[key].update({
                "allowed_directions": [supports, "NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "owner_return_relative_to_hurdle",
                "interpretation_rule": (
                    f"该口径{premise_value:g}%相对II={hurdle:g}%只裁决回报是否跨越门槛；"
                    "持续性仍须现金流和资本开支证据，方向不得写反"
                ),
            })
        if "ii_pct" in policies:
            policies["ii_pct"].update({
                "allowed_directions": ["NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "comparison_hurdle_not_explanation_evidence",
                "interpretation_rule": "II是比较标尺，本身不支持任一竞争解释",
            })
    if topic_family == "operating_transition":
        if "revenue_growth_pct" in policies:
            policies["revenue_growth_pct"].update({
                "allowed_directions": ["NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "growth_signal_requires_profit_and_segment_bridge",
                "interpretation_rule": "收入增速单独不能区分周期、结构或会计扰动，必须与利润及分部桥联合解释",
            })
        if "profit_growth_pct" in policies:
            policies["profit_growth_pct"].update({
                "allowed_directions": ["SUPPORTS_B", "NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "deterioration_signal_not_causal_proof",
                "interpretation_rule": "利润负增长可支持恶化风险但不能单独证明结构性原因；不得判为支持暂时扰动",
            })
        if "lambda_reliability" in policies:
            policies["lambda_reliability"].update({
                "allowed_directions": ["SUPPORTS_B", "NEUTRAL", "UNKNOWN"],
                "diagnostic_role": "normalization_reliability",
                "interpretation_rule": "unstable表示历史现金回报映射不稳，可支持口径/结构风险但不能证明具体原因",
            })
    return policies


def _attach_premise_assessment_policy(candidate: dict[str, Any]) -> None:
    link = candidate.get("decision_link") if isinstance(candidate.get("decision_link"), dict) else {}
    sensitivity = link.get("sensitivity_basis") if isinstance(link.get("sensitivity_basis"), dict) else {}
    link["premise_assessment_policy"] = _premise_assessment_policy(
        str(candidate.get("topic_family") or ""), sensitivity
    )


def _research_task(question_id: str, question: str, need: str) -> dict[str, Any]:
    route = route_research_need(question + " " + need)
    tools = ["read_evidence_context"] + list(route.get("tools") or [])
    if "read_section" in tools:
        tools.append("verify_official_fact")
    tools = list(dict.fromkeys(tools))
    return {
        "task_id": "DQT:" + question_id.rsplit(":", 1)[-1] + ":01",
        "route": str(route.get("route") or "primary_source_gap"),
        "research_question": need,
        "required_tools": tools,
        "annual_report_sections": list(route.get("sections") or []),
        "required_source_types": list(route.get("source_types") or ["annual_report"]),
        "stopping_rule": {
            "max_tool_calls": 8,
            "stop_when": "证据足以区分两种解释并更新估值/动作，或原始来源明确显示信息不可获得",
            "unavailable_is_a_valid_outcome": True,
            "candidate_evidence_cannot_close_task": True,
        },
    }


def _candidate(
    report_id: str,
    *,
    topic_family: str,
    mechanism_key: str,
    question: str,
    origins: list[str],
    score: dict[str, Any],
    explanations: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    decision_link: dict[str, Any],
    research_need: str,
    confidence: float,
    confidence_basis: str,
) -> dict[str, Any]:
    question_id = make_question_id(report_id, topic_family, mechanism_key)
    return {
        "question_id": question_id,
        "topic_family": topic_family,
        "mechanism_key": mechanism_key,
        "question": question,
        "candidate_origins": origins,
        "score": score,
        "competing_explanations": explanations,
        "discriminating_signals": signals,
        "decision_link": decision_link,
        "research_tasks": [_research_task(question_id, question, research_need)],
        "stopping_rule": {
            "stop_when": "至少一个区分信号获得VERIFIED证据，且解释更新会映射到估值或动作",
            "do_not_stop_on": "搜索摘要、同源转载、只有风险描述而没有区分力",
        },
        "confidence": {
            "kind": "working_hypothesis", "value": round(float(confidence), 2),
            "basis": confidence_basis, "not_a_frequency_probability": True,
        },
    }


def _valuation_values(bundle: dict[str, Any]) -> dict[str, float]:
    candidates = {
        "market_price": _nested(bundle, "market", "price_native"),
        "ddm": _nested(bundle, "factor4", "ddm_v_native"),
        "p_base": _nested(bundle, "factor4", "p_base", "price_native"),
        "p_base_discounted": _nested(bundle, "factor4", "p_base", "p_base_discounted_native"),
        "p_fcfe": _nested(bundle, "factor4", "p_base", "p_fcfe", "price_native"),
    }
    return {key: value for key, raw in candidates.items() if (value := _number(raw)) is not None and value > 0}


def _income_change(bundle: dict[str, Any]) -> dict[str, float | None]:
    rows = [row for row in (_nested(bundle, "factor3", "_income_raw") or []) if isinstance(row, dict)]
    rows.sort(key=lambda row: str(row.get("end_date") or ""))
    if len(rows) < 2:
        return {"revenue_growth_pct": None, "profit_growth_pct": None}
    previous, latest = rows[-2], rows[-1]
    def growth(field: str) -> float | None:
        old, new = _number(previous.get(field)), _number(latest.get(field))
        if old is None or new is None or abs(old) < 1e-12:
            return None
        return round((new / old - 1) * 100, 2)
    return {"revenue_growth_pct": growth("revenue"), "profit_growth_pct": growth("n_income_attr_p")}


def _industry_topic_family(match: dict[str, Any]) -> str:
    """Route a mechanism question into an existing report chapter family."""
    text = " ".join(
        str(match.get(key) or "")
        for key in ("mechanism_key", "title", "match_reason")
    ).lower()
    if any(token in text for token in ("cash", "distribution", "dividend", "debt", "上游", "分派", "债务", "现金")):
        return "cash_value_realization"
    if any(token in text for token in ("terminal", "legal", "期限", "终值", "清算", "资产兑现")):
        return "valuation_model_applicability"
    if any(token in text for token in ("return", "capex", "margin", "成本", "资本开支", "毛利", "回报")):
        return "owner_return_hurdle"
    return "operating_transition"


def _industry_mechanism_candidates(
    report_id: str, company: str, industry_context: dict[str, Any]
) -> list[dict[str, Any]]:
    """Turn only ready cards into bounded company-verification questions.

    The card text is deliberately not a factual premise.  The two explanations
    are applicability alternatives, and the only closing route is an official
    company source that covers each requested field.
    """
    candidates: list[dict[str, Any]] = []
    for match in industry_context.get("matched_mechanisms") or []:
        if not isinstance(match, dict) or match.get("status") != "MECHANISM_READY":
            continue
        if match.get("company_assessment") != "NOT_EVIDENCED":
            continue
        mechanism_id = str(match.get("mechanism_id") or "")
        mechanism_key = str(match.get("mechanism_key") or mechanism_id)
        title = str(match.get("title") or mechanism_id)
        fields = [str(item) for item in match.get("company_verification_fields") or [] if str(item).strip()]
        if not mechanism_id or not fields:
            continue
        field_text = "、".join(fields[:5])
        alternatives = [
            str(item) for item in match.get("alternative_explanations") or []
            if str(item).strip()
        ]
        alternative_text = "；".join(alternatives[:3])
        family = _industry_topic_family(match)
        candidate = _candidate(
            report_id,
            topic_family=family,
            mechanism_key="industry_knowledge:" + mechanism_id,
            question=(
                f"{company}是否满足行业机制“{title}”的适用边界，还是存在公司特异反例？"
                f"本公司必须以官方披露验证：{field_text}吗？"
            ),
            origins=["industry_knowledge:" + mechanism_id, "company_archetype"],
            score=_score(
                0.74, 0.82, 0.72, 0.76, 0.0,
                [
                    "industry mechanism is a research prompt, not company evidence",
                    f"mechanism_id={mechanism_id}",
                    f"required_company_fields={field_text}",
                ],
            ),
            explanations=_explanations(
                "industry_mechanism_" + re.sub(r"[^A-Za-z0-9]+", "_", mechanism_id)[:32],
                "本公司满足机制边界",
                "本公司官方披露逐项支持该机制的适用条件，且没有重大反例。",
                "本公司不适用或存在反例",
                (
                    "本公司披露显示关键经营、现金、合同或治理条件与机制前提不符。"
                    + ("还须排除替代解释：" + alternative_text + "。" if alternative_text else "")
                ),
            ),
            signals=[_signal(
                "industry_company_verification_" + re.sub(r"[^A-Za-z0-9]+", "_", mechanism_id)[:28],
                "本公司对以下字段的逐项官方披露：" + field_text,
                "所需字段支持适用边界且无重大反例",
                "所需字段缺失、反驳机制或显示不适用",
                "official_company_filing",
                "当前年报、最新中报和必要公告",
            )],
            decision_link=_decision_link(
                ["valuation.v_final", "decision.position.recommended"],
                {},
                ("仅在公司证据支持后再评估相关经营假设", "维持或谨慎提高", "完成公司验证后重估"),
                ("不得使用该机制支持经营假设", "维持或降低", "反例成立或无法验证时不把机制写入论点"),
                "公司官方证据未逐项支持机制适用，或出现会改变现金流、竞争位置或兑现路径的反例",
            ),
            research_need=(
                f"行业知识只提供待验证机制。逐项回读本公司官方披露的{field_text}；"
                "未验证时结论必须保持NOT_EVIDENCED，不得作为claim/evidence、估值参数、概率、价格或行动依据。"
            ),
            confidence=0.5,
            confidence_basis="行业机制仅是待验证研究提示，不代表本公司事实、经验概率或估值结论",
        )
        task = candidate["research_tasks"][0]
        task["route"] = "industry_mechanism_company_verification"
        task["annual_report_sections"] = fields
        candidates.append(candidate)
    return candidates


def generate_decisive_candidates(
    output_dir: str | Path,
    context: dict[str, Any],
    bundle: dict[str, Any],
    contract: dict[str, Any],
    archetype: dict[str, Any],
    industry_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    report_id = str(_nested(context, "meta", "report_id") or contract.get("ts_code") or Path(output_dir).name)
    company = str(_nested(context, "meta", "issuer") or Path(output_dir).name)
    values = _valuation_values(bundle)
    price = values.get("market_price")
    gg = _number(_nested(bundle, "factor3", "gg", "base"))
    gg_discounted = _number(_nested(bundle, "factor3", "gg_discounted", "base"))
    gg_fcfe = _number(_nested(bundle, "factor3", "gg_fcfe", "base"))
    ii = _number(_nested(bundle, "factor4", "II_adjusted")) or _number(_nested(bundle, "params", "II"))
    gg_min = _number(_nested(bundle, "factor3", "error_propagation", "gg_min"))
    gg_max = _number(_nested(bundle, "factor3", "error_propagation", "gg_max"))
    net_cash_pct = _number(_nested(bundle, "factor3", "net_cash_pct_mc"))
    dividend_years = _number(_nested(bundle, "factor3", "dividend_sustainability_years"))
    lambda_reliability = str(_nested(bundle, "factor3", "lambda_sensitivity", "reliability") or "unknown")
    income_change = _income_change(bundle)
    archetype_name = str(archetype.get("primary_archetype") or "operating_transition")
    candidates: list[dict[str, Any]] = []

    audit_obs = _observation_ids(context, domains=("audit",))
    operations_obs = _observation_ids_by_tokens(
        context,
        domains=("operations", "financial", "capital_allocation"),
        tokens=("revenue", "profit", "margin", "area", "project", "impairment", "segment", "cash_flow"),
    )
    owner_return_obs = _observation_ids_by_tokens(
        context,
        domains=("financial", "operations", "capital_allocation", "governance"),
        tokens=("net_profit", "cash", "deposit", "gross_margin", "dividend", "capex", "cash_flow"),
    )
    capital_obs = _observation_ids_by_tokens(
        context,
        domains=("capital_allocation", "governance", "financial"),
        tokens=("cash", "deposit", "dividend", "shareholder", "restricted", "pledge"),
    )

    # 1) Owner-return hurdle resilience.
    if gg is not None and ii is not None:
        central = gg_discounted if gg_discounted is not None else gg
        margin = central - ii
        crosses = gg_min is not None and gg_max is not None and gg_min <= ii <= gg_max
        sensitivity = 0.96 if margin <= 0 or crosses else 0.82 if margin <= 2 else 0.68
        candidates.append(_candidate(
            report_id,
            topic_family="owner_return_hurdle",
            mechanism_key="normalized_owner_return_vs_required_return",
            question=(
                f"{company}经数据折价后的股东穿透回报{central:.1f}%能否持续高于要求回报{ii:.1f}%，"
                "还是口径与正常化假设会使投资结论翻转？"
            ),
            origins=["compute_bundle.gg", "compute_bundle.error_propagation", "report_context"],
            score=_score(
                sensitivity, 0.92, 0.88, 0.92, 0.45,
                [f"GG_discounted={central:.2f}%", f"II={ii:.2f}%", f"margin={margin:.2f}pct", f"error_range={gg_min}..{gg_max}", f"range_crosses_hurdle={crosses}"],
            ),
            explanations=_explanations(
                "owner_return_hurdle",
                "回报真实且可持续", "正常化自由现金流和归母口径稳定，维持性资本开支不会吞噬当前穿透回报。",
                "回报被口径高估", "营运资本、少数股东、维持性资本开支或一次性现金使GG高估可分配股东回报。",
                owner_return_obs,
            ),
            signals=[
                _signal("normalized_fcfe", "连续期归母FCFE、AA与净利润的差异", "三种口径收敛且均高于II", "AA/FCFE下修并跌破II", "annual_report_financial_statement", "最近三年及下一期", owner_return_obs),
                _signal("maintenance_capex", "维持性资本开支占折旧和收入的比例", "稳定且不会侵蚀回报", "显著高于当前模型假设", "annual_report_notes", "三年滚动"),
            ],
            decision_link=_decision_link(
                ["return.gg.base", "return.gg.fcfe", "return.gg.normalized", "hurdle.ii", "margin.return", "decision.position.recommended"],
                {"gg_base_pct": gg, "gg_discounted_pct": gg_discounted, "gg_fcfe_pct": gg_fcfe, "ii_pct": ii, "gg_error_range_pct": [gg_min, gg_max]},
                ("维持或上调可信估值区间", "维持或提高", "满足价格安全边际时允许建仓"),
                ("下调至保守现金流价值", "降低或归零", "若回报低于II则避免或减仓"),
                "VERIFIED正常化GG不高于II，或压力区间大部分落在II以下",
            ),
            research_need="用逐页财报证据重建归母FCFE、维持性资本开支和营运资本桥，判断GG是否真实跨过II",
            confidence=0.75 if crosses or margin <= 1 else 0.65,
            confidence_basis="工作置信度来自确定性GG/II敏感性，不代表事件频率",
        ))

    # 2) Model applicability and output divergence.
    model_values = {key: value for key, value in values.items() if key != "market_price"}
    if len(model_values) >= 2:
        spread = max(model_values.values()) - min(model_values.values())
        denominator = max(abs(median(model_values.values())), abs(price or 0), 1e-9)
        spread_ratio = spread / denominator
        if spread_ratio >= 0.12:
            low_name = min(model_values, key=model_values.get)
            high_name = max(model_values, key=model_values.get)
            candidates.append(_candidate(
                report_id,
                topic_family="valuation_model_applicability",
                mechanism_key="cashflow_model_divergence_and_terminal_dependence",
                question=(
                    f"{company}的{low_name}估值{model_values[low_name]:.2f}与{high_name}估值{model_values[high_name]:.2f}"
                    "为何分歧，哪一种现金流归属和终值假设才适合当前业务？"
                ),
                origins=["compute_bundle.factor4", "valuation_model_applicability"],
                score=_score(
                    min(0.98, 0.62 + spread_ratio / 2), 0.86, 0.82, 0.78, 0.42,
                    [f"model_values={model_values}", f"model_spread_ratio={spread_ratio:.3f}", f"market_price={price}"],
                ),
                explanations=_explanations(
                    "valuation_model_applicability",
                    "高值模型适用", "分红或股东现金流具有长期持续性，高值模型的折现率和终值与决策主体匹配。",
                    "高值模型形成错误锚定", "现金流不可持续、终值依赖过高或资产/股权口径错配，低值模型更接近可兑现价值。",
                    capital_obs,
                ),
                signals=[
                    _signal("distribution_coverage", "分红、回购相对归母FCFE的覆盖率", "长期覆盖且压力期不借债分配", "分配依赖存量现金或融资", "annual_report_cashflow_and_notes", "至少三年", capital_obs),
                    _signal("terminal_fragility", "折现率+1pct、增长率-1pct及组合压力下的价值和动作", "压力后仍保留正安全边际", "小幅参数变化即翻转动作", "deterministic_valuation", "当前估值时点"),
                ],
                decision_link=_decision_link(
                    ["valuation.v_final", "margin.price", "decision.position.recommended", "trigger.buy"],
                    {"market_price": price, "model_values": model_values, "spread_ratio": round(spread_ratio, 4)},
                    ("采用经压力测试后的高值区间", "按安全边际分级", "价格低于压力价值时买入"),
                    ("采用低值或资产兑现区间", "降低", "高值模型失效时等待或避免"),
                    "高值模型在折现率+1pct和增长率-1pct组合压力下不再支持当前动作",
                ),
                research_need="核对模型现金流归属、分红覆盖、r-g安全距离和终值占比，并说明为何拒绝另一模型",
                confidence=0.7,
                confidence_basis="模型输出分歧可确定，适用性仍需原始现金流证据裁决",
            ))

    # 3) Cash accessibility and value realization.
    if net_cash_pct is not None and (net_cash_pct >= 30 or archetype_name in {"asset_catalyst", "regulated_financial"}):
        candidates.append(_candidate(
            report_id,
            topic_family="cash_value_realization",
            mechanism_key="cash_control_access_and_distribution",
            question=(
                f"{company}相当于市值{net_cash_pct:.1f}%的净现金中，有多少由上市公司控制、可合法分配并能在合理时间内兑现给外部股东？"
            ),
            origins=["compute_bundle.cash_structure", "report_context.gaps", f"archetype:{archetype_name}"],
            score=_score(
                min(0.98, 0.68 + net_cash_pct / 400), 0.95, 0.82, 0.86, 0.5,
                [f"net_cash_pct_market_cap={net_cash_pct:.1f}%", f"archetype={archetype_name}", "cash ownership and restrictions not proven by balance alone"],
            ),
            explanations=_explanations(
                "cash_value_realization",
                "现金可达外部股东", "现金位于上市主体、未受限且资本配置政策允许通过分红、回购或经营投入创造股东价值。",
                "现金受控或被消耗", "现金受监管、关联安排、少数股东、业务营运或低回报投资约束，不能按面值视为安全垫。",
                capital_obs,
            ),
            signals=[
                _signal("cash_location", "母公司现金、受限资金、定期存款和关联方存款的主体与期限", "上市主体可随时支配", "受限、质押、长期或位于非归母主体", "annual_report_notes", "报告期末及期后", capital_obs),
                _signal("distribution_governance", "分红回购政策、董事会权限和关联交易条款", "形成可执行兑现路径", "控制人保留或转移现金", "governance_and_company_announcement", "未来12–24个月"),
            ],
            decision_link=_decision_link(
                ["valuation.v_final", "margin.price", "decision.position.recommended", "trigger.exit"],
                {"net_cash_pct_market_cap": net_cash_pct, "dividend_coverage_years": dividend_years},
                ("将可达现金计入价值下限", "允许提高上限", "按兑现概率分层买入"),
                ("现金按零或大幅折价计入", "降低", "若治理阻断则避免价值陷阱"),
                "VERIFIED证据显示关键现金受限、归属非外部股东或没有可信分配路径",
            ),
            research_need="逐页核对现金所在主体、受限/质押、关联存款条款、少数股东归属和正式分配权限",
            confidence=0.78 if net_cash_pct >= 100 else 0.68,
            confidence_basis="现金规模确定，但可达性未被资产负债表数字直接证明",
        ))

    # 4) Operating transition: cycle, structure or accounting disturbance.
    rev_growth = income_change.get("revenue_growth_pct")
    profit_growth = income_change.get("profit_growth_pct")
    transition_trigger = lambda_reliability == "unstable" or (rev_growth is not None and rev_growth < 0) or (profit_growth is not None and profit_growth < 0)
    if transition_trigger:
        candidates.append(_candidate(
            report_id,
            topic_family="operating_transition",
            mechanism_key="cycle_structure_or_accounting_disturbance",
            question=(
                f"{company}最新收入增速{rev_growth if rev_growth is not None else '未知'}%、利润增速{profit_growth if profit_growth is not None else '未知'}%"
                f"且λ可靠性为{lambda_reliability}，异常主要是周期、结构变化还是会计/口径扰动？"
            ),
            origins=["compute_bundle.income_history", "compute_bundle.lambda_sensitivity", "report_context.operations"],
            score=_score(
                0.84 if (profit_growth is not None and profit_growth < 0) else 0.72,
                0.9, 0.88, 0.94, 0.5,
                [f"latest_revenue_growth_pct={rev_growth}", f"latest_profit_growth_pct={profit_growth}", f"lambda_reliability={lambda_reliability}"],
            ),
            explanations=_explanations(
                "operating_transition",
                "周期或暂时扰动", "需求、确认节奏、原材料或会计项目暂时压低表现，核心单位经济性和竞争位置未恶化。",
                "结构性恶化", "客户选择、价格、产品结构或竞争格局永久改变，历史利润率和增长不能外推。",
                operations_obs,
            ),
            signals=[
                _signal("segment_volume_price", "核心分部销量/项目量、价格和收入的分解", "量价随周期恢复", "份额或价格持续弱于行业", "annual_report_segment_and_official_industry", "连续2–4个报告期", operations_obs),
                _signal("margin_cash_confirmation", "毛利率、费用率和现金转化的同步性", "利润与现金共同恢复", "利润率或现金转化持续恶化", "annual_report_financial_statement", "连续两期", operations_obs),
            ],
            decision_link=_decision_link(
                ["return.gg.normalized", "valuation.v_final", "moat.lambda", "moat.decay", "decision.position.recommended"],
                {"revenue_growth_pct": rev_growth, "profit_growth_pct": profit_growth, "lambda_reliability": lambda_reliability},
                ("使用周期正常化盈利", "维持观察或分步增加", "等待区分信号确认恢复"),
                ("下调利润率、增长和优势持续期", "降低或退出", "结构性证据成立即重估"),
                "连续两期份额/量价或现金转化恶化，且无法由行业周期和会计项目解释",
            ),
            research_need="拆分核心分部量价、份额、利润率和现金变化，用同行/行业数据区分周期与结构",
            confidence=0.68,
            confidence_basis="转折信号来自历史财务与λ稳定性，原因尚需竞争证据",
        ))

    # 5) Reverse expectations, always available when price and P_base exist.
    p_base = values.get("p_base")
    if price is not None and p_base is not None and ii is not None:
        implied_ratio = price / p_base if p_base else None
        candidates.append(_candidate(
            report_id,
            topic_family="market_implied_path",
            mechanism_key="price_implied_owner_return_path",
            question=(
                f"{company}当前价格{price:.2f}相当于P_base的{implied_ratio:.2f}倍，市场隐含的是怎样的盈利、现金回报和优势持续路径，哪项事实会证明市场错了？"
            ),
            origins=["compute_bundle.market", "compute_bundle.p_base", "reverse_expectations"],
            score=_score(
                0.72, 0.78, 0.72, 0.78, 0.38,
                [f"market_price={price}", f"p_base={p_base}", f"price_to_p_base={implied_ratio:.3f}", f"II={ii}"],
                redundancy_penalty=0.1 if len(model_values) >= 2 else 0.0,
            ),
            explanations=_explanations(
                "market_implied_path",
                "市场过度悲观", "当前价格隐含的回报衰减或利润路径低于公司可验证的正常化能力。",
                "低价正确反映风险", "市场价格反映现金不可达、结构性衰退或资本配置损失，表面低估不是错价。",
                audit_obs + operations_obs,
            ),
            signals=[
                _signal("reverse_operating_path", "由当前价格反推的正常化盈利、GG或优势持续期", "实际路径持续优于隐含值", "实际路径等于或差于隐含值", "deterministic_reverse_valuation", "当前价格与未来2–3期"),
                _signal("market_discriminator", "可观察经营事实相对市场隐含路径的偏差", "偏差扩大并支持上修", "偏差收敛或转负", "official_filing_and_market_data", "每次披露"),
            ],
            decision_link=_decision_link(
                ["market.price.current", "return.gg.base", "valuation.v_final", "margin.price", "trigger.buy"],
                {"market_price": price, "p_base": p_base, "price_to_p_base": round(implied_ratio, 4), "ii_pct": ii},
                ("上调错价置信度", "按安全边际增加", "隐含路径过度悲观时买入"),
                ("维持或下调价值", "不增加", "市场路径被事实确认时等待"),
                "实际正常化回报不再优于当前价格反推路径",
            ),
            research_need="不用PE/PB标签，直接由当前价格反推可支持的正常化现金回报、盈利路径和优势持续期",
            confidence=0.58,
            confidence_basis="价格与P_base可确定，但完整反向模型留待Phase 03模型路由",
        ))

    candidates.extend(_industry_mechanism_candidates(
        report_id, company, industry_context or {}
    ))

    # Ensure a real question exists even when the deterministic bundle is thin.
    if not candidates:
        gap_domains = [str(item.get("domain")) for item in context.get("unresolved_gaps") or [] if isinstance(item, dict)]
        candidates.append(_candidate(
            report_id,
            topic_family="critical_evidence_gap",
            mechanism_key="missing_fact_that_can_flip_action",
            question=f"{company}当前哪些尚未验证的关键事实最可能使估值或仓位动作翻转？",
            origins=["report_context.unresolved_gaps"],
            score=_score(0.6, 0.72, 0.62, 0.78, 0.3, [f"unresolved_domains={gap_domains}"]),
            explanations=_explanations(
                "critical_evidence_gap", "缺口不改变结论", "缺失资料对核心现金流和控制权不具决定性。",
                "缺口隐藏关键风险", "缺失资料涉及现金流归属、治理或持续性并会翻转动作。",
            ),
            signals=[_signal("gap_resolution", "关键缺口的官方原文", "确认现有口径", "否定现有口径", "official_filing", "当前研究轮次")],
            decision_link=_decision_link(
                ["valuation.v_final", "decision.position.recommended"], {},
                ("保持当前范围", "维持", "继续评估"), ("下调或不可估", "归零", "信息不足时停止发布"),
                "关键缺口经VERIFIED证据证明会改变现金流归属或持续性",
            ),
            research_need="按决策影响排序回读证据缺口，先关闭能改变动作的一项",
            confidence=0.5,
            confidence_basis="输入不足，只能形成待验证问题，不能形成投资结论",
        ))
    for candidate in candidates:
        _attach_premise_assessment_policy(candidate)
    return candidates


_REDUNDANCY_PAIRS = {
    frozenset({"valuation_model_applicability", "market_implied_path"}): 0.1,
    frozenset({"cash_value_realization", "valuation_model_applicability"}): 0.04,
    frozenset({"owner_return_hurdle", "market_implied_path"}): 0.04,
}


def rank_and_select(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = deepcopy(candidates)
    base_penalties = {
        str(item["question_id"]): float(item["score"].get("redundancy_penalty") or 0)
        for item in remaining
    }
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    while remaining:
        rescored: list[dict[str, Any]] = []
        for candidate in remaining:
            family = str(candidate["topic_family"])
            pair_penalty = max(
                (_REDUNDANCY_PAIRS.get(frozenset({family, str(item["topic_family"])}), 0.0) for item in selected),
                default=0.0,
            )
            base_penalty = base_penalties[str(candidate["question_id"])]
            candidate["score"]["redundancy_penalty"] = _clip(base_penalty + pair_penalty)
            base = sum(WEIGHTS[key] * float(candidate["score"][key]) for key in WEIGHTS)
            candidate["score"]["priority"] = _clip(base - candidate["score"]["redundancy_penalty"])
            if pair_penalty and not any(str(value).startswith("redundancy_penalty=") for value in candidate["score"]["basis"]):
                candidate["score"]["basis"].append(f"redundancy_penalty={pair_penalty:.2f}")
            rescored.append(candidate)
        rescored.sort(key=lambda item: (-float(item["score"]["priority"]), item["question_id"]))
        candidate = rescored[0]
        remaining = rescored[1:]
        family = str(candidate["topic_family"])
        if family in seen_families:
            reason = "duplicate_topic_family"
        elif len(selected) >= MAX_SELECTED:
            reason = "lower_priority_than_top_three"
        elif candidate["score"]["priority"] < MINIMUM_PRIORITY and selected:
            reason = "below_minimum_priority"
        else:
            selected.append(candidate)
            seen_families.add(family)
            continue
        rejected.append({
            "question_id": candidate["question_id"], "topic_family": family,
            "question": candidate["question"], "priority": candidate["score"]["priority"],
            "rejection_reason": reason,
        })
    selected.sort(key=lambda item: (-float(item["score"]["priority"]), item["question_id"]))
    rejected.sort(key=lambda item: (-float(item["priority"]), item["question_id"]))
    return selected, rejected


def _mark_industry_question_injection(
    industry_context: dict[str, Any], selected: list[dict[str, Any]],
) -> None:
    """Record which ready mechanisms made this plan's final top-three cut."""
    selected_mechanism_ids = {
        str(origin).split(":", 1)[1]
        for question in selected
        if isinstance(question, dict)
        for origin in question.get("candidate_origins") or []
        if str(origin).startswith("industry_knowledge:")
    }
    for match in industry_context.get("matched_mechanisms") or []:
        if not isinstance(match, dict):
            continue
        match["question_injected"] = (
            str(match.get("status") or "") == "MECHANISM_READY"
            and str(match.get("mechanism_id") or "") in selected_mechanism_ids
        )


def build_decisive_question_findings(
    output_dir: str | Path, findings: list[dict[str, Any]], *, change_reason: str = ""
) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "decisive_question_plan.json")
    return {
        "schema_version": FINDINGS_VERSION,
        "report_id": str(plan.get("report_id") or output.name),
        "plan_input_fingerprint": str(plan.get("input_fingerprint") or ""),
        "generated_at": _now(),
        "change_reason": str(change_reason or "").strip(),
        "findings": deepcopy(findings),
    }


def validate_decisive_question_findings(
    payload: dict[str, Any], plan: dict[str, Any], *, output_dir: str | Path
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if payload.get("schema_version") != FINDINGS_VERSION:
        invalid.append("findings_schema_version_invalid")
    if payload.get("report_id") != plan.get("report_id"):
        invalid.append("findings_report_id_mismatch")
    if payload.get("plan_input_fingerprint") != plan.get("input_fingerprint"):
        invalid.append("findings_plan_fingerprint_mismatch")
    selected = {
        str(item.get("question_id")): item for item in plan.get("selected_questions") or []
        if isinstance(item, dict)
    }
    facts = _load(Path(output_dir) / "fact_observations.json")
    verified_observations = {
        str(item.get("observation_id")): item for item in facts.get("observations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    }
    calculations = _load(Path(output_dir) / "calculation_observations.json")
    try:
        from scripts.computation_evidence import validate_calculation_observations
    except ModuleNotFoundError:
        from computation_evidence import validate_calculation_observations
    calculation_validation = validate_calculation_observations(
        calculations, output_dir, rebuild=True
    ) if calculations else {"state": "INVALID"}
    verified_calculations = {
        str(item.get("calculation_id")): item
        for item in calculations.get("calculations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    } if calculation_validation.get("state") == "VERIFIED" else {}
    decision_ledger = _load(Path(output_dir) / "decision_ledger.json")
    canonical_sources: list[Any] = [
        decision_ledger,
        _load(Path(output_dir) / "valuation_model.json"),
        _load(Path(output_dir) / "thesis_test.json"),
    ]
    active_decisions = {
        str(item.get("entry_id")): item
        for item in decision_ledger.get("entries") or []
        if isinstance(item, dict) and item.get("status") == "active"
    }
    all_evidence_sources = {**verified_observations, **verified_calculations}
    rows = payload.get("findings")
    if not isinstance(rows, list):
        invalid.append("findings_not_array")
        rows = []
    seen: set[str] = set()
    for index, finding in enumerate(rows):
        prefix = f"findings[{index}]"
        if not isinstance(finding, dict):
            invalid.append(prefix + ":not_object")
            continue
        question_id = str(finding.get("question_id") or "")
        if question_id not in selected:
            invalid.append(prefix + ":question_not_selected:" + question_id)
            continue
        if question_id in seen:
            invalid.append("duplicate_finding:" + question_id)
        seen.add(question_id)
        question = selected[question_id]
        outcome = str(finding.get("outcome") or "")
        if outcome not in {"RESOLVED", "INCONCLUSIVE", "PUBLIC_INFO_UNAVAILABLE"}:
            invalid.append(question_id + ":outcome_invalid")
        evidence_ids = [str(value) for value in finding.get("evidence_observation_ids") or []]
        for observation_id in evidence_ids:
            if observation_id not in verified_observations:
                invalid.append(question_id + ":unknown_or_unverified_observation:" + observation_id)
        calculation_ids = [
            str(value) for value in finding.get("evidence_calculation_ids") or []
        ]
        for calculation_id in calculation_ids:
            if calculation_id not in verified_calculations:
                invalid.append(question_id + ":unknown_or_unverified_calculation:" + calculation_id)
        premise_values = _scalar_leaves(
            _nested(question, "decision_link", "sensitivity_basis") or {}
        )
        premise_policy = (
            _nested(question, "decision_link", "premise_assessment_policy") or {}
        )
        assessment = (
            finding.get("resolution_assessment")
            if isinstance(finding.get("resolution_assessment"), dict) else {}
        )
        if outcome == "RESOLVED" and not assessment:
            incomplete.append(question_id + ":resolution_assessment_missing")
        net_support = str(assessment.get("net_support") or "")
        if assessment and net_support not in {
            "EXPLANATION_A", "EXPLANATION_B", "MIXED", "INSUFFICIENT"
        }:
            invalid.append(question_id + ":resolution_net_support_invalid")
        if assessment and not str(assessment.get("decision_consistency") or "").strip():
            incomplete.append(question_id + ":resolution_decision_consistency_missing")
        premise_rows = assessment.get("premise_resolution") if assessment else []
        if assessment and not isinstance(premise_rows, list):
            invalid.append(question_id + ":premise_resolution_not_array")
            premise_rows = []
        seen_premises: set[str] = set()
        premise_directions: set[str] = set()
        for premise_index, premise in enumerate(premise_rows or []):
            premise_prefix = f"{question_id}:premise_resolution[{premise_index}]"
            if not isinstance(premise, dict):
                invalid.append(premise_prefix + ":not_object")
                continue
            premise_key = str(premise.get("premise_key") or "")
            if premise_key not in premise_values:
                invalid.append(premise_prefix + ":unknown_premise_key:" + premise_key)
                continue
            if premise_key in seen_premises:
                invalid.append(premise_prefix + ":duplicate_premise_key:" + premise_key)
            seen_premises.add(premise_key)
            if _canonical(premise.get("plan_value")) != _canonical(premise_values[premise_key]):
                invalid.append(premise_prefix + ":plan_value_mismatch")
            direction = str(premise.get("direction") or "")
            if direction not in {"SUPPORTS_A", "SUPPORTS_B", "NEUTRAL", "UNKNOWN"}:
                invalid.append(premise_prefix + ":direction_invalid")
            policy = premise_policy.get(premise_key) if isinstance(premise_policy, dict) else {}
            allowed_directions = [str(value) for value in (policy or {}).get("allowed_directions") or []]
            if allowed_directions and direction not in allowed_directions:
                invalid.append(
                    premise_prefix + ":direction_violates_plan_policy:" + direction
                    + ":allowed=" + ",".join(allowed_directions)
                )
            premise_directions.add(direction)
            if not str(premise.get("assessment") or "").strip():
                incomplete.append(premise_prefix + ":assessment_missing")
            premise_evidence_ids = [str(value) for value in premise.get("evidence_ids") or []]
            if direction != "UNKNOWN" and not premise_evidence_ids:
                incomplete.append(premise_prefix + ":evidence_missing")
            for evidence_id in premise_evidence_ids:
                if evidence_id not in set(evidence_ids + calculation_ids):
                    invalid.append(premise_prefix + ":evidence_not_declared:" + evidence_id)
                elif evidence_id not in all_evidence_sources:
                    invalid.append(premise_prefix + ":evidence_not_verified:" + evidence_id)
            expected_metric_path = f"{question_id}.sensitivity_basis.{premise_key}"
            expected_premise_calculations = {
                calculation_id for calculation_id, calculation in verified_calculations.items()
                if calculation.get("tool") == "decisive_plan"
                and calculation.get("metric_path") == expected_metric_path
                and _canonical(calculation.get("value")) == _canonical(premise_values[premise_key])
            }
            if len(expected_premise_calculations) != 1:
                invalid.append(premise_prefix + ":decisive_plan_calculation_identity_invalid")
            elif direction != "UNKNOWN" and not expected_premise_calculations.issubset(set(premise_evidence_ids)):
                invalid.append(premise_prefix + ":exact_decisive_plan_calculation_missing")
        for missing_key in sorted(set(premise_values) - seen_premises):
            incomplete.append(question_id + ":premise_not_resolved:" + missing_key)
        if outcome == "RESOLVED" and "UNKNOWN" in premise_directions:
            invalid.append(question_id + ":resolved_with_unknown_decision_premise")
        if outcome == "RESOLVED" and net_support == "INSUFFICIENT":
            invalid.append(question_id + ":resolved_with_insufficient_net_support")
        if {"SUPPORTS_A", "SUPPORTS_B"}.issubset(premise_directions) and net_support != "MIXED":
            invalid.append(question_id + ":mixed_premises_require_mixed_net_support")
        attempts = [str(value).strip() for value in finding.get("attempted_sources") or [] if str(value).strip()]
        if outcome == "RESOLVED" and not evidence_ids:
            incomplete.append(question_id + ":resolved_without_verified_evidence")
        if outcome in {"INCONCLUSIVE", "PUBLIC_INFO_UNAVAILABLE"} and not (evidence_ids or attempts):
            incomplete.append(question_id + ":research_attempt_not_recorded")
        explanation_ids = {
            str(item.get("explanation_id")) for item in question.get("competing_explanations") or []
            if isinstance(item, dict)
        }
        update = finding.get("explanation_update") if isinstance(finding.get("explanation_update"), dict) else {}
        favored = str(update.get("favored_explanation_id") or "")
        if favored and favored not in explanation_ids:
            invalid.append(question_id + ":unknown_favored_explanation:" + favored)
        if outcome == "RESOLVED" and not favored:
            incomplete.append(question_id + ":favored_explanation_missing")
        confidence_valid = True
        try:
            before = float(update.get("confidence_before"))
            after = float(update.get("confidence_after"))
            if not (0 <= before <= 1 and 0 <= after <= 1):
                raise ValueError
        except (TypeError, ValueError):
            before = after = 0.0
            confidence_valid = False
            invalid.append(question_id + ":confidence_update_invalid")
        if not str(update.get("basis") or "").strip():
            incomplete.append(question_id + ":explanation_update_basis_missing")
        allowed_signals = {
            str(item.get("signal_id")) for item in question.get("discriminating_signals") or []
            if isinstance(item, dict)
        }
        signal_results = finding.get("signal_results")
        requires_uncertainty = False
        inference_tag_ids: list[str] = []
        if not isinstance(signal_results, list):
            invalid.append(question_id + ":signal_results_not_array")
            signal_results = []
        if outcome == "RESOLVED" and not signal_results:
            incomplete.append(question_id + ":resolved_without_signal_result")
        for result in signal_results:
            if not isinstance(result, dict) or str(result.get("signal_id")) not in allowed_signals:
                invalid.append(question_id + ":unknown_signal_result")
                continue
            signal_id = str(result.get("signal_id"))
            signal_evidence_ids = result.get("evidence_ids")
            if not isinstance(signal_evidence_ids, list) or not signal_evidence_ids:
                incomplete.append(question_id + ":" + signal_id + ":signal_evidence_missing")
                signal_evidence_ids = []
            signal_sources: list[Any] = []
            for evidence_id in [str(value) for value in signal_evidence_ids]:
                if evidence_id in verified_observations and evidence_id in evidence_ids:
                    signal_sources.append(verified_observations[evidence_id])
                elif evidence_id in verified_calculations and evidence_id in calculation_ids:
                    signal_sources.append(verified_calculations[evidence_id])
                else:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":signal_evidence_not_declared_or_verified:" + evidence_id
                    )
            support = str(result.get("supports_explanation_id") or "")
            if support and support not in explanation_ids:
                invalid.append(question_id + ":signal_supports_unknown_explanation:" + support)
            if not str(result.get("result") or "").strip():
                incomplete.append(question_id + ":signal_result_empty")
            else:
                result_text = str(result.get("result") or "")
                unsupported = _unsupported_numbers(result_text, signal_sources)
                if unsupported:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":signal_numeric_support_mismatch:unsupported="
                        + _unsupported_suffix(unsupported)
                    )
                local_mismatches = _citation_numeric_mismatches(
                    result_text, all_evidence_sources,
                    {str(value) for value in signal_evidence_ids},
                )
                if local_mismatches:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":citation_identity_numeric_mismatch:"
                        + "|".join(local_mismatches)
                    )
                absolute = _unsupported_absolute_assertions(result_text, signal_sources)
                if absolute:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":unsupported_absolute_assertion:"
                        + "|".join(absolute)
                    )
                dimensions = _dimensionally_invalid_comparisons(result_text)
                if dimensions:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":dimensionally_invalid_comparison:"
                        + "|".join(dimensions)
                    )
                inference = _unlabeled_inference_claims(result_text, signal_sources)
                if inference:
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":unlabeled_analyst_inference:"
                        + "|".join(inference)
                    )
                if _undisclosed_negative_evidence(result_text):
                    invalid.append(
                        question_id + ":" + signal_id
                        + ":negative_search_presented_as_fact"
                    )
                requires_uncertainty = requires_uncertainty or any(
                    pattern.search(result_text)
                    for pattern in (_INFERENCE_TAG_RE, _NEGATIVE_EVIDENCE_TAG_RE)
                )
                inference_tag_ids.extend(
                    str(match.group(1) or "").strip()
                    for match in _INFERENCE_TAG_RE.finditer(result_text)
                )
        decision = finding.get("decision_update") if isinstance(finding.get("decision_update"), dict) else {}
        for field in ("valuation_impact", "position_impact", "action"):
            if not str(decision.get(field) or "").strip():
                incomplete.append(question_id + ":decision_update_missing:" + field)
        if not isinstance(decision.get("changed"), bool):
            invalid.append(question_id + ":decision_changed_not_boolean")
        decision_ids = [str(value) for value in decision.get("decision_entry_ids") or []]
        for entry_id in decision_ids:
            if entry_id not in active_decisions:
                invalid.append(question_id + ":unknown_or_inactive_decision_entry:" + entry_id)
        decision_text = " ".join(
            str(decision.get(field) or "")
            for field in ("valuation_impact", "position_impact", "action")
        )
        decision_numbers = _finding_numbers(
            re.sub(r"\b(?:Ch|FY)\s*\d+(?:\s*H[12])?", "", decision_text, flags=re.I)
        )
        for value in decision_numbers:
            matching_ids = {
                entry_id for entry_id, entry in active_decisions.items()
                if isinstance(entry.get("value"), (int, float))
                and math.isclose(float(entry["value"]), value, rel_tol=1e-6, abs_tol=0.00501)
            }
            if matching_ids and not matching_ids.intersection(decision_ids):
                invalid.append(
                    question_id + ":decision_value_missing_binding:"
                    + format(value, ".12g") + ":expected_one_of="
                    + "|".join(sorted(matching_ids))
                )
        if confidence_valid and outcome != "RESOLVED" and after > before:
            invalid.append(question_id + ":unresolved_research_increased_confidence")
        if not str(finding.get("conclusion") or "").strip():
            incomplete.append(question_id + ":conclusion_missing")
        narrative_sources = [
            verified_observations[value] for value in evidence_ids
            if value in verified_observations
        ] + [
            verified_calculations[value] for value in calculation_ids
            if value in verified_calculations
        ] + canonical_sources
        declared_narrative_ids = set(evidence_ids + calculation_ids)
        narrative_fields: list[tuple[str, Any, list[Any], set[str]]] = [
            ("explanation_basis", update.get("basis"), narrative_sources, declared_narrative_ids),
            ("valuation_impact", decision.get("valuation_impact"), narrative_sources, declared_narrative_ids),
            ("position_impact", decision.get("position_impact"), narrative_sources, declared_narrative_ids),
            ("action", decision.get("action"), narrative_sources, declared_narrative_ids),
            ("conclusion", finding.get("conclusion"), narrative_sources, declared_narrative_ids),
        ]
        if assessment:
            narrative_fields.append((
                "resolution_decision_consistency",
                assessment.get("decision_consistency"),
                narrative_sources,
                declared_narrative_ids,
            ))
            for premise_index, premise in enumerate(premise_rows or []):
                if not isinstance(premise, dict):
                    continue
                local_ids = {
                    str(value) for value in premise.get("evidence_ids") or []
                }
                local_sources = [
                    all_evidence_sources[value] for value in local_ids
                    if value in all_evidence_sources
                ]
                narrative_fields.append((
                    f"premise_resolution[{premise_index}].assessment",
                    premise.get("assessment"), local_sources, local_ids,
                ))
        for label, text, text_sources, text_declared_ids in narrative_fields:
            unsupported = _unsupported_numbers(str(text or ""), text_sources)
            if unsupported:
                invalid.append(
                    question_id + ":" + label
                    + ":numeric_support_mismatch:unsupported="
                    + _unsupported_suffix(unsupported)
                )
            local_mismatches = _citation_numeric_mismatches(
                str(text or ""), all_evidence_sources,
                text_declared_ids,
            )
            if local_mismatches:
                invalid.append(
                    question_id + ":" + label
                    + ":citation_identity_numeric_mismatch:"
                    + "|".join(local_mismatches)
                )
            absolute = _unsupported_absolute_assertions(str(text or ""), text_sources)
            if absolute:
                invalid.append(
                    question_id + ":" + label
                    + ":unsupported_absolute_assertion:"
                    + "|".join(absolute)
                )
            dimensions = _dimensionally_invalid_comparisons(str(text or ""))
            if dimensions:
                invalid.append(
                    question_id + ":" + label
                    + ":dimensionally_invalid_comparison:"
                    + "|".join(dimensions)
                )
            inference = _unlabeled_inference_claims(str(text or ""), text_sources)
            if inference:
                invalid.append(
                    question_id + ":" + label
                    + ":unlabeled_analyst_inference:"
                    + "|".join(inference)
                )
            if _undisclosed_negative_evidence(str(text or "")):
                invalid.append(
                    question_id + ":" + label
                    + ":negative_search_presented_as_fact"
                )
            requires_uncertainty = requires_uncertainty or any(
                pattern.search(str(text or ""))
                for pattern in (_INFERENCE_TAG_RE, _NEGATIVE_EVIDENCE_TAG_RE)
            )
            inference_tag_ids.extend(
                str(match.group(1) or "").strip()
                for match in _INFERENCE_TAG_RE.finditer(str(text or ""))
            )
        unresolved_values = [
            str(value).strip() for value in finding.get("unresolved") or []
            if str(value).strip()
        ]
        for value in unresolved_values:
            requires_uncertainty = requires_uncertainty or bool(
                _INFERENCE_TAG_RE.search(value) or _NEGATIVE_EVIDENCE_TAG_RE.search(value)
            )
            inference_tag_ids.extend(
                str(match.group(1) or "").strip()
                for match in _INFERENCE_TAG_RE.finditer(value)
            )
        if requires_uncertainty and not [
            value for value in unresolved_values
        ]:
            incomplete.append(question_id + ":disclosed_inference_requires_unresolved")
        inference_audit = finding.get("inference_audit")
        if inference_tag_ids:
            if not isinstance(inference_audit, list) or not inference_audit:
                incomplete.append(question_id + ":inference_audit_missing")
                inference_audit = []
            audit_ids: set[str] = set()
            declared_all = set(evidence_ids + calculation_ids)
            for audit_index, audit in enumerate(inference_audit):
                audit_prefix = f"{question_id}:inference_audit[{audit_index}]"
                if not isinstance(audit, dict):
                    invalid.append(audit_prefix + ":not_object")
                    continue
                inference_id = str(audit.get("inference_id") or "").strip()
                if not inference_id or inference_id in audit_ids:
                    invalid.append(audit_prefix + ":id_missing_or_duplicate")
                audit_ids.add(inference_id)
                for field in (
                    "claim", "strongest_alternative", "discriminating_observation",
                    "decision_if_wrong",
                ):
                    if not str(audit.get(field) or "").strip():
                        incomplete.append(audit_prefix + ":missing:" + field)
                support_ids = [str(value) for value in audit.get("supporting_evidence_ids") or []]
                if not support_ids:
                    incomplete.append(audit_prefix + ":supporting_evidence_missing")
                for evidence_id in support_ids:
                    if evidence_id not in declared_all or evidence_id not in all_evidence_sources:
                        invalid.append(audit_prefix + ":unknown_or_undeclared_evidence:" + evidence_id)
            named_tags = {value for value in inference_tag_ids if value}
            for inference_id in sorted(named_tags - audit_ids):
                invalid.append(question_id + ":unknown_inference_tag:" + inference_id)
            if any(not value for value in inference_tag_ids) and len(audit_ids) != 1:
                invalid.append(question_id + ":bare_inference_tag_is_ambiguous")
            if confidence_valid and after > before + 0.050001:
                invalid.append(question_id + ":inference_confidence_jump_exceeds_0.05")
    for question_id in selected:
        if question_id not in seen:
            incomplete.append(question_id + ":research_task_not_completed")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "DECISION_READY"
    return {
        "schema_version": VALIDATION_VERSION,
        "state": state,
        "status": "PASS" if state == "DECISION_READY" else "FAIL",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": [],
        "completed_question_ids": sorted(seen),
    }


def persist_decisive_question_findings(
    output_dir: str | Path, payload: dict[str, Any]
) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "decisive_question_plan.json")
    validation = validate_decisive_question_findings(payload, plan, output_dir=output)
    # Keep the latest attempted validation separate from the canonical gate.
    # Invalid submissions used to disappear completely, leaving both the
    # synthesis agent and an engineer to guess which nested field was wrong.
    _atomic_write_json(
        output / "decisive_question_findings_last_attempt_validation.json",
        {**validation, "attempted_at": _now(), "payload_hash": _hash(payload)},
    )
    _atomic_write_json(
        output / "decisive_question_findings_last_attempt.json", payload
    )
    if validation["state"] != "DECISION_READY":
        best_path = output / "decisive_question_findings_best_rejected.json"
        best_validation_path = (
            output / "decisive_question_findings_best_rejected_validation.json"
        )
        best_payload = _load(best_path)
        best_validation = _load(best_validation_path)
        if best_payload.get("plan_input_fingerprint") != plan.get("input_fingerprint"):
            best_validation = {}
        elif best_payload:
            # Validator rules evolve during real-report calibration.  Never rank
            # a current rejection against a stale error count from an older
            # validator; re-evaluate the saved candidate under today's gate.
            refreshed_best = validate_decisive_question_findings(
                best_payload, plan, output_dir=output
            )
            best_validation = {
                **refreshed_best,
                "attempted_at": str(best_validation.get("attempted_at") or _now()),
                "payload_hash": _hash(best_payload),
                "validation_refreshed_at": _now(),
            }
            _atomic_write_json(best_validation_path, best_validation)

        def rejection_score(value: dict[str, Any]) -> tuple[int, int, int]:
            completed = len(value.get("completed_question_ids") or [])
            invalid_count = len(value.get("invalid_findings") or [])
            incomplete_count = len(value.get("incomplete_findings") or [])
            return (
                max(0, len(plan.get("selected_questions") or []) - completed),
                invalid_count + incomplete_count,
                invalid_count,
            )

        same_best_payload = bool(best_payload) and _hash(best_payload) == _hash(payload)
        if (
            not best_validation
            or rejection_score(validation) < rejection_score(best_validation)
            or (
                same_best_payload
                and rejection_score(validation) == rejection_score(best_validation)
            )
        ):
            _atomic_write_json(best_path, payload)
            _atomic_write_json(
                best_validation_path,
                {**validation, "attempted_at": _now(), "payload_hash": _hash(payload)},
            )
        return {
            "written": False,
            "validation": validation,
            "last_attempt_path": str(
                output / "decisive_question_findings_last_attempt.json"
            ),
            "last_attempt_validation_path": str(
                output / "decisive_question_findings_last_attempt_validation.json"
            ),
            "best_rejected_path": str(best_path),
            "best_rejected_validation_path": str(best_validation_path),
        }
    _atomic_write_json(output / "decisive_question_findings.json", payload)
    _atomic_write_json(output / "decisive_question_findings_validation.json", validation)
    return {
        "written": True,
        "path": str(output / "decisive_question_findings.json"),
        "validation": validation,
    }


def patch_decisive_question_findings(
    output_dir: str | Path,
    patches: list[dict[str, Any]],
    *,
    change_reason: str = "",
) -> dict[str, Any]:
    """Merge bounded top-level finding patches into the best rejected candidate.

    The restored object remains non-canonical until the complete merged payload
    passes the ordinary validator.  Patch mode cannot add questions or alter a
    question identity, and every merged finding is revalidated in full.
    """
    output = Path(output_dir)
    plan = _load(output / "decisive_question_plan.json")
    selected_ids = {
        str(item.get("question_id")) for item in plan.get("selected_questions") or []
        if isinstance(item, dict)
    }
    best_path = output / "decisive_question_findings_best_rejected.json"
    best = _load(best_path)
    if not best or best.get("plan_input_fingerprint") != plan.get("input_fingerprint"):
        return {"written": False, "error": "compatible_best_rejected_missing"}
    current_best_validation = validate_decisive_question_findings(
        best, plan, output_dir=output
    )
    frontier_rows = [
        str(value) for value in (
            (current_best_validation.get("invalid_findings") or [])
            + (current_best_validation.get("incomplete_findings") or [])
        )
    ]
    frontier_question_ids = {
        question_id for question_id in selected_ids
        if any(row.startswith(question_id + ":") for row in frontier_rows)
    }
    allowed = {
        "outcome", "evidence_observation_ids", "evidence_calculation_ids",
        "attempted_sources", "signal_results", "explanation_update", "inference_audit",
        "resolution_assessment", "premise_resolution",
        "decision_update", "conclusion", "unresolved",
    }
    candidate = deepcopy(best)
    rows = {
        str(item.get("question_id")): item
        for item in candidate.get("findings") or [] if isinstance(item, dict)
    }
    seen: set[str] = set()
    for index, patch in enumerate(patches or []):
        if not isinstance(patch, dict):
            return {"written": False, "error": f"finding_patches[{index}]:not_object"}
        question_id = str(patch.get("question_id") or "")
        if question_id not in selected_ids or question_id not in rows:
            return {"written": False, "error": f"finding_patches[{index}]:unknown_question_id:{question_id}"}
        if question_id not in frontier_question_ids:
            return {
                "written": False,
                "error": f"finding_patches[{index}]:question_outside_current_validation_frontier:{question_id}",
            }
        if question_id in seen:
            return {"written": False, "error": f"finding_patches[{index}]:duplicate_question_id:{question_id}"}
        seen.add(question_id)
        unknown = sorted(set(patch) - allowed - {"question_id"})
        if unknown:
            return {"written": False, "error": f"finding_patches[{index}]:unknown_fields:{'|'.join(unknown)}"}
        if "premise_resolution" in patch:
            assessment = rows[question_id].get("resolution_assessment")
            if not isinstance(assessment, dict):
                return {
                    "written": False,
                    "error": f"finding_patches[{index}]:resolution_assessment_missing",
                }
            existing_premises = assessment.get("premise_resolution")
            if not isinstance(existing_premises, list):
                return {
                    "written": False,
                    "error": f"finding_patches[{index}]:premise_resolution_missing",
                }
            premise_rows = deepcopy(existing_premises)
            premise_by_key = {
                str(item.get("premise_key")): item
                for item in premise_rows if isinstance(item, dict)
            }
            seen_premises: set[str] = set()
            premise_allowed = {
                "premise_key", "plan_value", "direction", "evidence_ids", "assessment",
            }
            for premise_index, premise_patch in enumerate(
                patch.get("premise_resolution") or []
            ):
                if not isinstance(premise_patch, dict):
                    return {
                        "written": False,
                        "error": f"finding_patches[{index}].premise_resolution[{premise_index}]:not_object",
                    }
                premise_key = str(premise_patch.get("premise_key") or "")
                if premise_key not in premise_by_key:
                    return {
                        "written": False,
                        "error": f"finding_patches[{index}].premise_resolution[{premise_index}]:unknown_premise_key:{premise_key}",
                    }
                if premise_key in seen_premises:
                    return {
                        "written": False,
                        "error": f"finding_patches[{index}].premise_resolution[{premise_index}]:duplicate_premise_key:{premise_key}",
                    }
                seen_premises.add(premise_key)
                premise_unknown = sorted(set(premise_patch) - premise_allowed)
                if premise_unknown:
                    return {
                        "written": False,
                        "error": f"finding_patches[{index}].premise_resolution[{premise_index}]:unknown_fields:{'|'.join(premise_unknown)}",
                    }
                for premise_field in premise_allowed - {"premise_key"}:
                    if premise_field in premise_patch:
                        premise_by_key[premise_key][premise_field] = deepcopy(
                            premise_patch[premise_field]
                        )
            assessment = deepcopy(assessment)
            assessment["premise_resolution"] = premise_rows
            rows[question_id]["resolution_assessment"] = assessment
        for key in allowed - {"premise_resolution"}:
            if key in patch:
                rows[question_id][key] = deepcopy(patch[key])
    if not seen:
        return {"written": False, "error": "finding_patches_empty"}
    candidate["generated_at"] = _now()
    candidate["change_reason"] = str(change_reason or "bounded best-rejected patch").strip()
    return persist_decisive_question_findings(output, candidate)


def rebind_decisive_findings_to_current_plan(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Rebind only a stale plan fingerprint when all semantic IDs still validate."""
    output = Path(output_dir)
    plan = _load(output / "decisive_question_plan.json")
    findings = _load(output / "decisive_question_findings.json")
    if not plan or not findings:
        return {"rebound": False, "reason": "plan_or_findings_missing"}
    current = str(plan.get("input_fingerprint") or "")
    previous = str(findings.get("plan_input_fingerprint") or "")
    if current == previous:
        return {"rebound": False, "reason": "already_bound"}
    plan_ids = {
        str(item.get("question_id")) for item in plan.get("selected_questions") or []
        if isinstance(item, dict)
    }
    finding_ids = {
        str(item.get("question_id")) for item in findings.get("findings") or []
        if isinstance(item, dict)
    }
    if plan_ids != finding_ids:
        return {"rebound": False, "reason": "semantic_identity_changed"}
    candidate = deepcopy(findings)
    candidate["plan_input_fingerprint"] = current
    candidate["change_reason"] = (
        str(candidate.get("change_reason") or "").strip()
        + "; deterministic plan fingerprint rebind after compatible input refresh"
    ).strip("; ")
    # Premise CALC identities include the plan fingerprint.  A compatible plan
    # refresh therefore requires a deterministic identity remap even when every
    # question and value is unchanged; this is not a model rewrite.
    old_calculations = _load(output / "calculation_observations.json")
    old_by_metric = {
        (str(item.get("tool")), str(item.get("metric_path"))): str(item.get("calculation_id"))
        for item in old_calculations.get("calculations") or []
        if isinstance(item, dict)
    }
    try:
        from scripts.computation_evidence import build_calculation_observations
    except ModuleNotFoundError:
        from computation_evidence import build_calculation_observations
    rebuilt = build_calculation_observations(output, persist=True)
    new_by_metric = {
        (str(item.get("tool")), str(item.get("metric_path"))): str(item.get("calculation_id"))
        for item in rebuilt.get("calculations") or []
        if isinstance(item, dict)
    }
    identity_remap = {
        old_by_metric[identity]: new_id for identity, new_id in new_by_metric.items()
        if identity in old_by_metric and old_by_metric[identity] != new_id
    }

    def remap_calculation_identities(value: Any) -> Any:
        """Rewrite opaque CALC identities in every structured findings field.

        IDs also occur inside assessment prose and inference-audit claims, not
        only in the two top-level evidence arrays.  Leaving those references
        stale makes a deterministic plan refresh fail numeric-support checks.
        """
        if isinstance(value, dict):
            return {
                key: remap_calculation_identities(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [remap_calculation_identities(item) for item in value]
        if isinstance(value, str):
            result = value
            for old_id, new_id in identity_remap.items():
                result = result.replace(old_id, new_id)
            return result
        return value

    candidate = remap_calculation_identities(candidate)
    validation = validate_decisive_question_findings(
        candidate, plan, output_dir=output
    )
    if validation.get("state") != "DECISION_READY":
        return {
            "rebound": False, "reason": "semantic_identity_changed",
            "validation": validation,
        }
    _atomic_write_json(output / "decisive_question_findings.json", candidate)
    _atomic_write_json(
        output / "decisive_question_findings_validation.json", validation
    )
    return {
        "rebound": True, "from_fingerprint": previous,
        "to_fingerprint": current, "validation": validation,
    }


_OBSERVATION_ID_FIELDS = {
    "current_support_observation_ids",
    "current_contradiction_observation_ids",
    "current_observation_ids",
}


def _plan_semantics(value: Any) -> Any:
    """Remove refresh-only evidence metadata from question semantics.

    ``base_rate_context`` is a persisted evidence-context binding (path,
    fingerprints and warnings), not part of the identity of a decisive
    question.  Its fingerprint legitimately changes when verified evidence is
    added even if the selected questions, mechanisms and decision links remain
    identical.
    """
    if isinstance(value, dict):
        return {
            key: _plan_semantics(item)
            for key, item in value.items()
            if key not in {
                "generated_at", "validation", "input_sources", "input_fingerprint",
                "base_rate_context",
            } | _OBSERVATION_ID_FIELDS
        }
    if isinstance(value, list):
        return [_plan_semantics(item) for item in value]
    return value


def _plan_observation_ids(payload: dict[str, Any]) -> set[str]:
    result: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _OBSERVATION_ID_FIELDS and isinstance(item, list):
                    result.update(str(identity) for identity in item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload.get("selected_questions") or [])
    return result


def refresh_decisive_question_plan(
    output_dir: str | Path, *, run_id: str | None = None, enforced: bool = False
) -> dict[str, Any]:
    """Refresh evidence memberships without silently replacing changed research semantics."""
    output = Path(output_dir)
    old = _load(output / "decisive_question_plan.json")
    candidate = build_decisive_question_plan(output, persist=False, enforced=enforced)

    def persist_base_rate_context(plan: dict[str, Any]) -> dict[str, Any]:
        """Persist the exact base-rate context summarized by a refreshed plan."""
        try:
            from scripts.base_rate_case_library import build_base_rate_context
        except ModuleNotFoundError:
            from base_rate_case_library import build_base_rate_context
        preliminary = plan.get("preliminary_archetype") or {}
        archetype_ids = [
            str(item) for item in [
                preliminary.get("primary"), *(preliminary.get("secondary") or [])
            ] if str(item or "").strip()
        ]
        questions = [
            item for item in [
                *(plan.get("selected_questions") or []),
                *(plan.get("rejected_candidates") or []),
            ] if isinstance(item, dict)
        ]
        context = build_base_rate_context(
            output, archetype_ids=archetype_ids, questions=questions, persist=True
        )
        summary = plan.setdefault("base_rate_context", {})
        summary.update({
            "path": "base_rate_context.json",
            "context_fingerprint": context.get("context_fingerprint"),
            "library_fingerprint": context.get("library_fingerprint"),
            "warnings": context.get("warnings") or [],
        })
        # Revalidate after binding the on-disk context.  This prevents a
        # REVIEWABLE plan from coexisting with base_rate_context_missing.
        plan["validation"] = validate_decisive_question_plan(
            plan, output_dir=output, enforced=enforced,
            base_rate_context_override=context,
        )
        return context
    if not old:
        persist_base_rate_context(candidate)
        _atomic_write_json(output / "decisive_question_plan.json", candidate)
        _atomic_write_json(output / "decisive_question_validation.json", candidate["validation"])
        if run_id is not None:
            initialize_decisive_question_policy(output, run_id=run_id, enforced=enforced)
        return {"refreshed": True, "reason": "initialized", "plan": candidate}

    if _pit_contract(output) and not _pit_plan_knowledge_safe(old):
        persist_base_rate_context(candidate)
        _atomic_write_json(output / "decisive_question_plan.json", candidate)
        _atomic_write_json(output / "decisive_question_validation.json", candidate["validation"])
        if run_id is not None:
            initialize_decisive_question_policy(output, run_id=run_id, enforced=enforced)
        return {
            "refreshed": True,
            "reason": "pit_unsafe_upstream_plan_replaced",
            "plan": candidate,
        }

    compatible = _plan_semantics(old) == _plan_semantics(candidate)
    audit = {
        "schema_version": "decisive-question-plan-refresh.v1",
        "generated_at": _now(),
        "status": "EVIDENCE_REFRESHED" if compatible else "SEMANTIC_CHANGE_REQUIRES_RESEARCH",
        "old_input_fingerprint": old.get("input_fingerprint"),
        "candidate_input_fingerprint": candidate.get("input_fingerprint"),
        "old_question_ids": [item.get("question_id") for item in old.get("selected_questions") or []],
        "candidate_question_ids": [item.get("question_id") for item in candidate.get("selected_questions") or []],
        "removed_observation_ids": sorted(_plan_observation_ids(old) - _plan_observation_ids(candidate)),
        "added_observation_ids": sorted(_plan_observation_ids(candidate) - _plan_observation_ids(old)),
    }
    _atomic_write_json(output / "decisive_question_plan_refresh.json", audit)
    if not compatible:
        _atomic_write_json(output / "decisive_question_plan_candidate.json", candidate)
        if run_id is not None:
            initialize_decisive_question_policy(output, run_id=run_id, enforced=enforced)
        return {
            "refreshed": False, "reason": "semantic_change_requires_research",
            "plan": old, "candidate": candidate, "audit": audit,
        }

    persist_base_rate_context(candidate)
    _atomic_write_json(output / "decisive_question_plan.json", candidate)
    _atomic_write_json(output / "decisive_question_validation.json", candidate["validation"])
    candidate_path = output / "decisive_question_plan_candidate.json"
    if candidate_path.is_file():
        candidate_path.unlink()
    findings_rebind = rebind_decisive_findings_to_current_plan(output)
    if run_id is not None:
        initialize_decisive_question_policy(output, run_id=run_id, enforced=enforced)
    return {
        "refreshed": True, "reason": "observation_membership_only",
        "plan": candidate, "audit": audit, "findings_rebind": findings_rebind,
    }


def _normalise_mechanism(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", str(text).lower()))


def validate_decisive_question_plan(
    payload: dict[str, Any], *, output_dir: str | Path | None = None, enforced: bool = False,
    base_rate_context_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    report_id = str(payload.get("report_id") or "")
    if not report_id:
        invalid.append("report_id_missing")
    input_sources = payload.get("input_sources")
    if not isinstance(input_sources, dict) or not input_sources:
        incomplete.append("input_sources_missing")
        input_sources = {}
    if payload.get("input_fingerprint") != decisive_input_fingerprint(input_sources):
        invalid.append("input_fingerprint_mismatch")
    if output_dir is not None:
        output = Path(output_dir)
        for name, expected in input_sources.items():
            path = output / str(name)
            if path.suffix.lower() == ".json":
                current = _load(path)
                current_hash = _source_value(path, current) if current else ""
            else:
                try:
                    current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    current_hash = ""
            if current_hash != expected:
                warnings.append("input_source_changed_after_plan:" + str(name))
    selected = payload.get("selected_questions")
    if not isinstance(selected, list):
        invalid.append("selected_questions_not_array")
        selected = []
    if len(selected) > MAX_SELECTED:
        invalid.append("selected_question_limit_exceeded")
    if enforced and not selected:
        incomplete.append("decisive_question_missing")
    facts = _load(Path(output_dir) / "fact_observations.json") if output_dir is not None else {}
    verified_ids = {
        str(item.get("observation_id")) for item in facts.get("observations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    }
    base_rate_enabled = bool(payload.get("base_rate_context"))
    base_rate_queries: dict[str, Any] = {}
    base_rate_policy_present = bool(
        output_dir is not None and (Path(output_dir) / "base_rate_policy.json").is_file()
    )
    if base_rate_policy_present:
        base_rate_enabled = True
    if base_rate_enabled:
        summary = payload.get("base_rate_context") if isinstance(payload.get("base_rate_context"), dict) else {}
        if not summary:
            incomplete.append("base_rate_context_summary_missing")
        if base_rate_context_override is not None:
            context = base_rate_context_override
            if str(summary.get("context_fingerprint") or "") != str(context.get("context_fingerprint") or ""):
                invalid.append("base_rate_context_fingerprint_mismatch")
            if str(summary.get("library_fingerprint") or "") != str(context.get("library_fingerprint") or ""):
                invalid.append("base_rate_library_fingerprint_mismatch")
            base_rate_queries = context.get("queries") if isinstance(context.get("queries"), dict) else {}
            warnings.extend(str(value) for value in context.get("warnings") or [] if str(value).strip())
        elif output_dir is None:
            warnings.append("base_rate_context_not_revalidated_without_output_dir")
        else:
            context_path = Path(output_dir) / str(summary.get("path") or "base_rate_context.json")
            context = _load(context_path)
            if not context:
                if base_rate_policy_present:
                    incomplete.append("base_rate_context_missing")
                else:
                    warnings.append("base_rate_context_not_available_for_revalidation")
            else:
                if str(summary.get("context_fingerprint") or "") != str(context.get("context_fingerprint") or ""):
                    invalid.append("base_rate_context_fingerprint_mismatch")
                if str(summary.get("library_fingerprint") or "") != str(context.get("library_fingerprint") or ""):
                    invalid.append("base_rate_library_fingerprint_mismatch")
                base_rate_queries = context.get("queries") if isinstance(context.get("queries"), dict) else {}
                warnings.extend(str(value) for value in context.get("warnings") or [] if str(value).strip())
        if output_dir is not None and _pit_contract(output_dir):
            availability = context.get("availability") if isinstance(context.get("availability"), dict) else {}
            if availability.get("mode") != "PIT_EVIDENCE_ONLY":
                invalid.append("pit_base_rate_context_lacks_isolation_proof")
    industry_context = payload.get("industry_knowledge_context")
    industry_matches: dict[str, dict[str, Any]] = {}
    if industry_context is not None:
        if not isinstance(industry_context, dict):
            invalid.append("industry_knowledge_context_not_object")
            industry_context = {}
        if industry_context.get("source") != "industry_knowledge":
            invalid.append("industry_knowledge_context_source_invalid")
        profile = industry_context.get("profile")
        if not isinstance(profile, dict):
            incomplete.append("industry_knowledge_profile_missing")
        usage = industry_context.get("usage_contract")
        if not isinstance(usage, dict):
            incomplete.append("industry_knowledge_usage_contract_missing")
        else:
            prohibited = {str(value) for value in usage.get("must_not_supply") or []}
            required_prohibited = {
                "claim_evidence", "official_observation", "valuation_parameter",
                "probability", "price", "action_basis",
            }
            if not required_prohibited.issubset(prohibited):
                invalid.append("industry_knowledge_usage_contract_allows_decision_input")
            if usage.get("company_evidence_required") is not True:
                invalid.append("industry_knowledge_company_evidence_requirement_missing")
        if not str(industry_context.get("validation_status") or "").strip():
            incomplete.append("industry_knowledge_validation_status_missing")
        if output_dir is not None and _pit_contract(output_dir):
            availability = (
                industry_context.get("availability")
                if isinstance(industry_context.get("availability"), dict) else {}
            )
            if availability.get("mode") != "PIT_EVIDENCE_ONLY":
                invalid.append("pit_industry_context_lacks_isolation_proof")
        matches = industry_context.get("matched_mechanisms")
        if not isinstance(matches, list):
            invalid.append("industry_knowledge_matches_not_array")
            matches = []
        for index, match in enumerate(matches):
            prefix = f"industry_knowledge_context.matched_mechanisms[{index}]"
            if not isinstance(match, dict):
                invalid.append(prefix + ":not_object")
                continue
            mechanism_id = str(match.get("mechanism_id") or "")
            if not mechanism_id:
                incomplete.append(prefix + ":mechanism_id_missing")
                continue
            if mechanism_id in industry_matches:
                invalid.append("industry_knowledge_duplicate_mechanism:" + mechanism_id)
            industry_matches[mechanism_id] = match
            for field in ("mechanism_key", "title", "status", "match_reason", "forbidden_model_role"):
                if not str(match.get(field) or "").strip():
                    incomplete.append(prefix + ":" + field + "_missing")
            fields = match.get("company_verification_fields")
            if not isinstance(fields, list) or not [value for value in fields if str(value).strip()]:
                incomplete.append(prefix + ":company_verification_fields_missing")
            assessment = str(match.get("company_assessment") or "")
            if assessment not in INDUSTRY_COMPANY_ASSESSMENTS:
                invalid.append(prefix + ":company_assessment_invalid")
            # A matching rule is not an issuer conclusion. New plans are
            # deliberately born unverified; research findings, not a plan edit,
            # are the only place where company evidence can change the view.
            if assessment != "NOT_EVIDENCED":
                invalid.append(prefix + ":company_assessment_must_start_not_evidenced")
            if match.get("question_injected") is True and str(match.get("status")) != "MECHANISM_READY":
                invalid.append(prefix + ":non_ready_mechanism_auto_injected")
    seen_ids: set[str] = set()
    seen_families: set[str] = set()
    all_selected_ids: set[str] = set()
    for index, item in enumerate(selected):
        prefix = f"selected_questions[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        question_id = str(item.get("question_id") or "")
        family = str(item.get("topic_family") or "")
        mechanism_key = str(item.get("mechanism_key") or "")
        if question_id != make_question_id(report_id, family, mechanism_key):
            invalid.append(f"{question_id or prefix}:question_id_mismatch")
        if question_id in seen_ids:
            invalid.append("duplicate_question_id:" + question_id)
        if family in seen_families:
            invalid.append("duplicate_selected_topic_family:" + family)
        seen_ids.add(question_id); seen_families.add(family); all_selected_ids.add(question_id)
        if base_rate_enabled:
            query = base_rate_queries.get(mechanism_key) if isinstance(base_rate_queries.get(mechanism_key), dict) else {}
            eligible_ids = {
                str(value.get("case_id")) for value in query.get("eligible_cases") or []
                if isinstance(value, dict) and value.get("case_id")
            }
            refs = {str(value) for value in item.get("base_rate_refs") or [] if str(value).strip()}
            unknown_refs = sorted(refs - eligible_ids)
            if unknown_refs:
                invalid.append(f"{question_id or prefix}:ineligible_base_rate_refs:" + ",".join(unknown_refs))
            try:
                sample_size = int(item.get("base_rate_sample_size"))
            except (TypeError, ValueError):
                invalid.append(f"{question_id or prefix}:base_rate_sample_size_invalid")
            else:
                expected_size = int(query.get("independent_company_sample_size", query.get("eligible_sample_size") or 0) or 0)
                if sample_size != expected_size or sample_size != len(eligible_ids):
                    invalid.append(f"{question_id or prefix}:base_rate_sample_size_mismatch")
        question = str(item.get("question") or "").strip()
        if len(question) < 15 or not question.endswith(("?", "？")):
            incomplete.append(f"{question_id or prefix}:question_not_decisive")
        score = item.get("score") if isinstance(item.get("score"), dict) else {}
        try:
            recomputed = sum(WEIGHTS[key] * float(score[key]) for key in WEIGHTS) - float(score.get("redundancy_penalty") or 0)
            if abs(float(score.get("priority")) - _clip(recomputed)) > 0.001:
                invalid.append(f"{question_id or prefix}:priority_formula_mismatch")
        except (KeyError, TypeError, ValueError):
            invalid.append(f"{question_id or prefix}:score_invalid")
        if not score.get("basis"):
            incomplete.append(f"{question_id or prefix}:score_basis_missing")
        industry_origins = [
            str(origin).split(":", 1)[1]
            for origin in item.get("candidate_origins") or []
            if str(origin).startswith("industry_knowledge:")
        ]
        for mechanism_id in industry_origins:
            match = industry_matches.get(mechanism_id)
            if not match:
                invalid.append(f"{question_id or prefix}:industry_mechanism_not_in_context:{mechanism_id}")
                continue
            if match.get("question_injected") is not True:
                invalid.append(f"{question_id or prefix}:industry_mechanism_not_injectable:{mechanism_id}")
            if str(match.get("status") or "") != "MECHANISM_READY":
                invalid.append(f"{question_id or prefix}:industry_mechanism_not_ready:{mechanism_id}")
        explanations = item.get("competing_explanations")
        if not isinstance(explanations, list) or len(explanations) < 2:
            incomplete.append(f"{question_id or prefix}:competing_explanations_missing")
            explanations = []
        mechanisms = [_normalise_mechanism(value.get("mechanism")) for value in explanations if isinstance(value, dict)]
        if len(mechanisms) >= 2 and mechanisms[0] == mechanisms[1]:
            invalid.append(f"{question_id or prefix}:explanations_not_competing")
        for explanation in explanations:
            if not isinstance(explanation, dict):
                invalid.append(f"{question_id or prefix}:explanation_not_object")
                continue
            for field in ("current_support_observation_ids", "current_contradiction_observation_ids"):
                for observation_id in explanation.get(field) or []:
                    if str(observation_id) not in verified_ids:
                        invalid.append(f"{question_id or prefix}:unknown_or_unverified_observation:{observation_id}")
        signals = item.get("discriminating_signals")
        if not isinstance(signals, list) or not signals:
            incomplete.append(f"{question_id or prefix}:discriminating_signal_missing")
            signals = []
        for signal in signals:
            if not isinstance(signal, dict):
                invalid.append(f"{question_id or prefix}:signal_not_object")
                continue
            if str(signal.get("direction_if_explanation_a") or "").strip() == str(signal.get("direction_if_explanation_b") or "").strip():
                invalid.append(f"{question_id or prefix}:signal_has_no_discriminating_direction")
            for observation_id in signal.get("current_observation_ids") or []:
                if str(observation_id) not in verified_ids:
                    invalid.append(f"{question_id or prefix}:unknown_or_unverified_observation:{observation_id}")
        link = item.get("decision_link") if isinstance(item.get("decision_link"), dict) else {}
        if industry_origins and link.get("sensitivity_basis"):
            invalid.append(f"{question_id or prefix}:industry_knowledge_used_as_model_input")
        metrics = link.get("affected_metric_ids") or []
        if not metrics:
            incomplete.append(f"{question_id or prefix}:decision_metrics_missing")
        for metric in metrics:
            if str(metric) not in KNOWN_METRIC_IDS:
                invalid.append(f"{question_id or prefix}:unknown_metric_id:{metric}")
        if not str(link.get("flip_condition") or "").strip():
            incomplete.append(f"{question_id or prefix}:flip_condition_missing")
        premise_values = _scalar_leaves(link.get("sensitivity_basis") or {})
        premise_policy = link.get("premise_assessment_policy")
        if not isinstance(premise_policy, dict):
            incomplete.append(f"{question_id or prefix}:premise_assessment_policy_missing")
            premise_policy = {}
        for premise_key in premise_values:
            policy = premise_policy.get(premise_key) if isinstance(premise_policy.get(premise_key), dict) else {}
            allowed = policy.get("allowed_directions") if isinstance(policy.get("allowed_directions"), list) else []
            if not allowed or any(
                str(value) not in {"SUPPORTS_A", "SUPPORTS_B", "NEUTRAL", "UNKNOWN"}
                for value in allowed
            ):
                invalid.append(f"{question_id or prefix}:premise_policy_invalid:{premise_key}")
            if not str(policy.get("diagnostic_role") or "").strip() or not str(policy.get("interpretation_rule") or "").strip():
                incomplete.append(f"{question_id or prefix}:premise_policy_explanation_missing:{premise_key}")
            if policy.get("requires_decisive_plan_calculation") is not True:
                invalid.append(f"{question_id or prefix}:premise_identity_requirement_missing:{premise_key}")
        for extra_key in sorted(set(premise_policy) - set(premise_values)):
            invalid.append(f"{question_id or prefix}:unknown_premise_policy:{extra_key}")
        for scenario in ("if_explanation_a", "if_explanation_b"):
            action = link.get(scenario) if isinstance(link.get(scenario), dict) else {}
            if any(not str(action.get(field) or "").strip() for field in ("valuation_direction", "position_direction", "action")):
                incomplete.append(f"{question_id or prefix}:{scenario}_action_missing")
        tasks = item.get("research_tasks")
        if not isinstance(tasks, list) or not tasks:
            incomplete.append(f"{question_id or prefix}:research_task_missing")
            tasks = []
        for task in tasks:
            if not isinstance(task, dict) or not task.get("required_tools") or not task.get("required_source_types"):
                incomplete.append(f"{question_id or prefix}:research_task_route_incomplete")
                continue
            stopping = task.get("stopping_rule") or {}
            if not stopping.get("stop_when") or int(stopping.get("max_tool_calls") or 0) not in range(1, 9):
                invalid.append(f"{question_id or prefix}:research_task_stopping_rule_invalid")
    rejected = payload.get("rejected_candidates")
    if not isinstance(rejected, list):
        invalid.append("rejected_candidates_not_array")
        rejected = []
    for item in rejected:
        if not isinstance(item, dict):
            invalid.append("rejected_candidate_not_object")
            continue
        if str(item.get("question_id")) in all_selected_ids:
            invalid.append("selected_question_also_rejected:" + str(item.get("question_id")))
        if not str(item.get("rejection_reason") or "").strip():
            invalid.append("rejected_candidate_reason_missing")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": VALIDATION_VERSION,
        "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": warnings,
        "selected_count": len(selected),
        "selected_question_ids": sorted(all_selected_ids),
        "enforced": bool(enforced),
    }


def build_decisive_question_plan(
    output_dir: str | Path,
    *,
    persist: bool = True,
    run_id: str | None = None,
    enforced: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    context = _load(output / "report_context.json")
    bundle = _load(output / "compute_bundle.json")
    contract = _load(output / "analysis_contract.json")
    routed_archetype = _load(output / "company_archetype.json")
    if routed_archetype:
        primary = routed_archetype.get("primary_archetype") or {}
        archetype = {
            "primary_archetype": primary.get("archetype_id"),
            "secondary_archetypes": [
                item.get("archetype_id") for item in routed_archetype.get("secondary_archetypes") or []
                if isinstance(item, dict) and item.get("archetype_id")
            ],
            "source": "company_archetype.json",
        }
    else:
        archetype = classify_company_archetype(output)
    report_id = str(_nested(context, "meta", "report_id") or contract.get("ts_code") or output.name)
    # The profile is generated after official evidence and the company archetype,
    # immediately before question selection.  It may guide what to verify, but
    # cannot itself create a company claim or a valuation input.
    industry_knowledge_context = build_industry_knowledge_context(output)
    candidates = generate_decisive_candidates(
        output, context, bundle, contract, archetype, industry_knowledge_context,
    )
    try:
        from scripts.base_rate_case_library import build_base_rate_context
    except ModuleNotFoundError:
        from base_rate_case_library import build_base_rate_context
    archetype_ids = [
        str(item) for item in [archetype.get("primary_archetype"), *(archetype.get("secondary_archetypes") or [])]
        if str(item or "").strip()
    ]
    base_rate_context = build_base_rate_context(
        output, archetype_ids=archetype_ids, questions=candidates, persist=persist
    )
    for candidate in candidates:
        query = (base_rate_context.get("queries") or {}).get(str(candidate.get("mechanism_key"))) or {}
        candidate["base_rate_refs"] = [
            str(item.get("case_id")) for item in query.get("eligible_cases") or []
            if isinstance(item, dict) and item.get("case_id")
        ]
        candidate["base_rate_sample_size"] = int(query.get("independent_company_sample_size", query.get("eligible_sample_size") or 0) or 0)
    selected, rejected = rank_and_select(candidates)
    _mark_industry_question_injection(industry_knowledge_context, selected)
    input_sources = decisive_input_sources(output)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "input_sources": input_sources,
        "input_fingerprint": decisive_input_fingerprint(input_sources),
        "generated_at": _now(),
        "preliminary_archetype": {
            "primary": archetype.get("primary_archetype"),
            "secondary": archetype.get("secondary_archetypes") or [],
            "instruction": "仅作候选问题生成假设；Phase 03再完成正式行业原型和模型路由",
        },
        "selection_policy": {
            "max_selected": MAX_SELECTED,
            "minimum_priority": MINIMUM_PRIORITY,
            "weights": WEIGHTS,
            "ranking_is_not_a_quality_substitute": True,
        },
        "base_rate_context": {
            "path": "base_rate_context.json",
            "context_fingerprint": base_rate_context.get("context_fingerprint"),
            "library_fingerprint": base_rate_context.get("library_fingerprint"),
            "warnings": base_rate_context.get("warnings") or [],
        },
        "industry_knowledge_context": industry_knowledge_context,
        "selected_questions": selected,
        "rejected_candidates": rejected,
    }
    payload["validation"] = validate_decisive_question_plan(
        payload, output_dir=output, enforced=enforced,
        base_rate_context_override=base_rate_context if not persist else None,
    )
    if persist:
        _atomic_write_json(output / "decisive_question_plan.json", payload)
        _atomic_write_json(output / "decisive_question_validation.json", payload["validation"])
        try:
            from scripts.computation_evidence import build_calculation_observations
        except ModuleNotFoundError:
            from computation_evidence import build_calculation_observations
        build_calculation_observations(output, persist=True)
    if run_id is not None:
        initialize_decisive_question_policy(output, run_id=run_id, enforced=enforced)
    return payload


def initialize_decisive_question_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION, "run_id": str(run_id),
        "enforced": bool(enforced), "created_at": _now(),
    }
    _atomic_write_json(Path(output_dir) / "decisive_question_policy.json", payload)
    return payload


def evaluate_output_decisive_questions(
    output_dir: str | Path, *, persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _load(output / "decisive_question_policy.json")
    previous_findings_validation = _load(
        output / "decisive_question_findings_validation.json"
    )
    if not policy:
        return {
            "schema_version": VALIDATION_VERSION, "state": "SKIP", "status": "SKIP",
            "invalid_findings": [], "incomplete_findings": [], "warnings": [], "enforced": False,
        }
    payload = _load(output / "decisive_question_plan.json")
    if not payload:
        result = {
            "schema_version": VALIDATION_VERSION, "state": "INCOMPLETE", "status": "FAIL",
            "invalid_findings": [], "incomplete_findings": ["decisive_question_plan_missing"],
            "warnings": [], "enforced": bool(policy.get("enforced")),
        }
    else:
        result = validate_decisive_question_plan(
            payload, output_dir=output, enforced=bool(policy.get("enforced"))
        )
        if result["state"] == "REVIEWABLE" and bool(policy.get("enforced")):
            findings = _load(output / "decisive_question_findings.json")
            if not findings:
                result = {
                    **result,
                    "state": "INCOMPLETE",
                    "status": "FAIL",
                    "incomplete_findings": ["decisive_question_findings_missing"],
                }
            else:
                findings_result = validate_decisive_question_findings(
                    findings, payload, output_dir=output
                )
                if (
                    persist
                    and findings_result.get("state") != "DECISION_READY"
                    and previous_findings_validation.get("state") == "DECISION_READY"
                ):
                    # A stricter validator can demote yesterday's canonical file.
                    # Preserve that rich candidate as a non-authoritative repair
                    # frontier instead of falling back to an older, emptier draft.
                    persist_decisive_question_findings(output, findings)
                if persist:
                    _atomic_write_json(
                        output / "decisive_question_findings_validation.json",
                        findings_result,
                    )
                result = {
                    **findings_result,
                    "plan_state": "REVIEWABLE",
                    "selected_count": result.get("selected_count", 0),
                    "selected_question_ids": result.get("selected_question_ids", []),
                    "enforced": True,
                }
    if persist:
        _atomic_write_json(output / "decisive_question_validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="生成最多三个决定性问题及有界研究任务")
    parser.add_argument("--output-dir", "--output", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--enforced", action="store_true")
    args = parser.parse_args()
    payload = build_decisive_question_plan(
        args.output_dir, persist=True, run_id=args.run_id or None, enforced=args.enforced
    )
    print(json.dumps({
        "path": str(Path(args.output_dir) / "decisive_question_plan.json"),
        "state": payload["validation"]["state"],
        "selected": [
            {"question_id": item["question_id"], "priority": item["score"]["priority"], "question": item["question"]}
            for item in payload["selected_questions"]
        ],
    }, ensure_ascii=False))
    return 0 if payload["validation"]["state"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
