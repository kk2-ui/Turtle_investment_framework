#!/usr/bin/env python3
"""Case-calibrated router for the one question that should drive a report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")


def _benchmark() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "config" / "insight_case_benchmark.json"
    return _load(path)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_numbers(value: Any, key_pattern: str) -> list[float]:
    found: list[float] = []
    regex = re.compile(key_pattern, re.I)
    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                number = _number(child)
                if regex.search(str(key)) and number is not None:
                    found.append(number)
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return found


def classify_company_archetype(output_dir: str | Path) -> dict[str, Any]:
    """Classify from already-visible local evidence; never invent a company fact."""
    output = Path(output_dir)
    contract = _load(output / "analysis_contract.json")
    bundle = _load(output / "compute_bundle.json")
    valuation = _load(output / "valuation_model.json")
    fragments = [output.name, contract, bundle, valuation]
    for name in ("zone_b_v8_master.json", "zone_j_parameters.json", "data_pack_market.md", "segments.json", "governance.json", "risks.json", "moat_assessment.json"):
        path = output / name
        if path.is_file():
            try:
                fragments.append(path.read_text(encoding="utf-8")[:120000])
            except OSError:
                pass
    text = _flatten(fragments).lower()
    identity_text = _flatten([output.name, contract, valuation.get("company_profile")]).lower()
    scores = {name: 0 for name in _benchmark().get("archetypes", {})}
    signals: dict[str, list[str]] = {name: [] for name in scores}

    rules = {
        "regulated_financial": (r"银行|保险|证券|信托|物业|关联方|财务公司|监管资本", 4),
        "technology_transition": (r"半导体|芯片|软件|云计算|算法|研发强度|技术迭代", 4),
        "franchise_customer_lockin": (r"品牌|复购|经销商|渠道|客户粘性|定价权|市占率", 2),
        "mature_cash_return": (r"分红|股息|派息|回购|成熟|存量市场|低增长", 2),
        "distressed_survival": (r"持续经营|资不抵债|流动性危机|债务重组|亏损|违约", 4),
        "asset_catalyst": (r"净现金|隐蔽资产|处置|清算|折价|分部估值|催化剂", 2),
        "compounder_reinvestment": (r"再投资|复利|高roic|高roe|扩店|渗透率|产能扩张", 2),
        "operating_transition": (r"周期|结构性|转型|拐点|收入下滑|利润下滑|医疗器械|骨科|关节|集采", 2),
    }
    for name, (pattern, weight) in rules.items():
        matches = sorted(set(re.findall(pattern, text, re.I)))
        if matches:
            scores[name] += min(8, weight * len(matches))
            signals[name].extend(matches[:5])

    dividend_values = _find_numbers(bundle, r"dividend|yield|payout|dps")
    growth_values = _find_numbers(bundle, r"revenue.*growth|growth.*revenue|cagr")
    debt_values = _find_numbers(bundle, r"debt.*ratio|liabilit")
    if any(value >= 3 for value in dividend_values):
        scores["mature_cash_return"] += 3; signals["mature_cash_return"].append("quant:shareholder_return")
    if any(value < 0 for value in growth_values):
        scores["operating_transition"] += 3; signals["operating_transition"].append("quant:negative_growth")
    if any(value >= 70 for value in debt_values):
        scores["distressed_survival"] += 2; signals["distressed_survival"].append("quant:high_liability")

    ranked = sorted(scores, key=lambda name: (-scores[name], name))
    if not ranked or scores[ranked[0]] == 0:
        ranked = ["operating_transition"]
    primary = ranked[0]
    # High-signal business identity outranks generic dividend/valuation terms
    # that appear in almost every compute bundle.
    if re.search(r"银行|保险|信托|物业|财务公司", identity_text):
        primary = "regulated_financial"
    elif re.search(r"半导体|芯片|软件|云计算", identity_text) and scores.get("technology_transition", 0) >= 4:
        primary = "technology_transition"
    elif re.search(r"医疗|骨科|关节", identity_text) or scores.get("operating_transition", 0) >= 10:
        primary = "operating_transition"
    ranked = [primary] + [name for name in ranked if name != primary]
    secondary = [name for name in ranked[1:3] if scores[name] > 0]
    spec = _benchmark()["archetypes"][primary]
    return {
        "schema_version": "insight-research-brief.v1",
        "primary_archetype": primary,
        "secondary_archetypes": secondary,
        "decisive_question": spec["decisive_question"],
        "case_pattern": spec["case_pattern"],
        "case_provenance": spec.get("case_provenance", {}),
        "required_moves": spec["required_moves"],
        "forbidden_shortcuts": spec["forbidden_shortcuts"],
        "classification_scores": scores,
        "classification_signals": {key: value for key, value in signals.items() if value},
        "research_instruction": "Use the routed question as a hypothesis to refine from company evidence; do not mechanically copy it.",
    }


def build_insight_research_brief(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    brief = classify_company_archetype(output)
    routed = _load(output / "company_archetype.json")
    routed_id = str((routed.get("primary_archetype") or {}).get("archetype_id") or "")
    legacy_insight_archetype = {
        "property_service": "regulated_financial",
        "mature_consumer_manufacturing": "mature_cash_return",
        "asset_light_media_platform": "franchise_customer_lockin",
        "regulated_financial": "regulated_financial",
        "heavy_asset_cyclical": "operating_transition",
        "utility_infrastructure": "mature_cash_return",
        "property_developer_asset_holding": "asset_catalyst",
        "pre_revenue_biotech": "technology_transition",
        "general_operating": "operating_transition",
    }
    if routed_id in legacy_insight_archetype:
        brief["pre_phase03_archetype"] = brief.get("primary_archetype")
        brief["phase03_archetype_id"] = routed_id
        brief["primary_archetype"] = legacy_insight_archetype[routed_id]
        brief["classification_source"] = "company_archetype.json"
    decisive_plan = _load(output / "decisive_question_plan.json")
    selected = [
        item for item in decisive_plan.get("selected_questions") or []
        if isinstance(item, dict) and item.get("question_id") and item.get("question")
    ]
    if selected:
        brief["archetype_default_question"] = brief.get("decisive_question")
        brief["decisive_question"] = selected[0]["question"]
        brief["decisive_question_id"] = selected[0]["question_id"]
        brief["selected_decisive_questions"] = [
            {
                "question_id": item["question_id"],
                "topic_family": item.get("topic_family"),
                "question": item["question"],
                "priority": (item.get("score") or {}).get("priority"),
            }
            for item in selected
        ]
        brief["research_instruction"] = (
            "The pre-writing decisive-question plan is canonical. Use its question IDs, "
            "competitive explanations and discriminating signals; do not replace them with the archetype default."
        )
    if persist:
        path = output / "insight_research_brief.json"
        path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    return brief
