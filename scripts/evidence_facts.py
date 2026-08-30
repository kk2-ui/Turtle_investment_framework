#!/usr/bin/env python3
"""Extract, verify and persist facts linked to official document identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.evidence_documents import _atomic_write_json, _canonical_json
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json, _canonical_json


SCHEMA_VERSION = "fact-observations.v1"
STATUSES = {"CANDIDATE", "VERIFIED", "REJECTED", "CONFLICT"}
TEMPORAL_ROLES = {"POSITION_AS_OF", "HISTORICAL_PERIOD", "EVENT"}
OFFICIAL_DOCUMENT_AUTHORITIES = {
    "issuer", "audited_filing", "company_filing", "official_statistics", "other_official",
}
_VALUATION_EVIDENCE_ROLE_RE = re.compile(r"[A-Z][A-Z0-9_]*")
_VALUATION_EXCLUSION_DESTINATIONS = {
    "OTHER_REPLACEMENT_COMPONENT",
    "BALANCE_SHEET_WORKING_CAPITAL",
    "EPV_MAINTENANCE_NEED",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _payload_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_identity_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def make_observation_id(observation: dict[str, Any]) -> str:
    identity = {
        "doc_id": observation.get("doc_id"),
        "locator": observation.get("locator"),
        "fact_name": observation.get("fact_name"),
        "normalized_value": _normalized_identity_value(observation.get("normalized_value")),
        "measurement_context": observation.get("measurement_context"),
        "temporal_role": observation.get("temporal_role"),
        "event_date": observation.get("event_date"),
        "observed_at": observation.get("observed_at"),
        "valuation_evidence_roles": sorted(
            str(item) for item in observation.get("valuation_evidence_roles") or []
        ),
        "valuation_exclusion_destinations": sorted(
            str(item)
            for item in observation.get("valuation_exclusion_destinations") or []
        ),
    }
    return "OBS:" + _payload_hash(identity)[:20]


def _parse_temporal_date(value: Any) -> Any:
    """Return the calendar date carried by a date or ISO date-time string."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _temporal_contract_findings(
    observation: dict[str, Any], document: dict[str, Any]
) -> list[str]:
    """Validate an explicit fact clock without changing legacy ``as_of`` facts.

    Old observations remain document-period observations.  A specialist fact
    opts into one of three explicit roles so a balance, a historical flow and
    a later realized event cannot be silently relabelled as one another.
    """
    role = observation.get("temporal_role")
    as_of = _parse_temporal_date(observation.get("as_of"))
    document_period_end = _parse_temporal_date(document.get("period_end"))
    measurement = (
        observation.get("measurement_context")
        if isinstance(observation.get("measurement_context"), dict)
        else {}
    )
    findings: list[str] = []
    if role is None:
        if observation.get("as_of") != document.get("period_end"):
            findings.append("period_document_mismatch")
        return findings
    if role not in TEMPORAL_ROLES:
        return ["temporal_role_invalid"]
    if as_of is None:
        findings.append("as_of_invalid")

    event_date = _parse_temporal_date(observation.get("event_date"))
    observed_at = _parse_temporal_date(observation.get("observed_at"))
    period_start = _parse_temporal_date(measurement.get("period_start"))
    period_end = _parse_temporal_date(measurement.get("period_end"))

    if role == "POSITION_AS_OF":
        # An explicitly dated stock may be an opening balance disclosed in a
        # later annual report.  Its economic clock is the quoted position date,
        # not the reporting document's period end.  Legacy observations that do
        # not opt into a temporal role retain the old document-period rule above.
        if observation.get("event_date") is not None:
            findings.append("position_event_date_forbidden")
    elif role == "HISTORICAL_PERIOD":
        if period_start is None or period_end is None:
            findings.append("historical_period_bounds_missing_or_invalid")
        elif period_start > period_end:
            findings.append("historical_period_reversed")
        if as_of is not None and period_end is not None and as_of != period_end:
            findings.append("historical_as_of_must_equal_period_end")
        if observation.get("event_date") is not None:
            findings.append("historical_period_event_date_forbidden")
    else:
        if event_date is None:
            findings.append("event_date_missing_or_invalid")
        if observed_at is None:
            findings.append("event_observed_at_missing_or_invalid")
        if as_of is not None and event_date is not None and as_of != event_date:
            findings.append("event_as_of_must_equal_event_date")
        if event_date is not None and observed_at is not None and event_date > observed_at:
            findings.append("event_observed_before_event_date")
        if period_start is not None or period_end is not None:
            findings.append("event_period_bounds_forbidden")
        published_at = _parse_temporal_date(document.get("published_at"))
        if published_at is None:
            findings.append("event_document_published_at_missing_or_invalid")
        elif observed_at is not None and observed_at < published_at:
            findings.append("event_observed_before_document_publication")
    return findings


def _observation_core(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "report_id": payload.get("report_id"),
        "manifest_hash": payload.get("manifest_hash"),
        "observations": payload.get("observations") or [],
    }


def _parse_number(value: str) -> float:
    return float(str(value).replace(",", "").replace("，", "").strip())


def _parse_accounting_number(value: str) -> float:
    """Parse a filing number where parentheses denote a negative value."""
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    number = _parse_number(text[1:-1] if negative else text)
    return -number if negative else number


def _parse_yoy_change(value: str) -> float:
    """Parse a Chinese year-over-year direction without losing its sign."""
    text = re.sub(r"\s+", "", str(value))
    match = re.search(r"([\d.]+)%", text)
    if not match:
        raise ValueError(f"year_over_year_change_unparseable:{value}")
    amount = _parse_number(match.group(1))
    return -amount if "下降" in text or "微降" in text else amount


def _page_blocks(text: str) -> list[dict[str, Any]]:
    markers = list(re.finditer(r"^##\s+第\s*(\d+)\s*页\s*$", text, re.MULTILINE))
    blocks: list[dict[str, Any]] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        blocks.append({"page": int(marker.group(1)), "start": start, "end": end, "text": text[start:end]})
    return blocks


def _line_quote(block: dict[str, Any], match: re.Match[str]) -> tuple[str, int, int]:
    text = str(block["text"])
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end < 0:
        line_end = len(text)
    quote = text[line_start:line_end].strip()
    absolute_start = int(block["start"]) + line_start
    return quote[:500], absolute_start, absolute_start + (line_end - line_start)


@dataclass(frozen=True)
class PatternRule:
    fact_name: str
    domain: str
    pattern: re.Pattern[str]
    unit: str
    basis: str
    currency: str | None = None
    transform: Callable[[str], Any] = lambda value: value.strip()
    min_page: int = 1
    required_page_pattern: re.Pattern[str] | None = None
    nearby_page_pattern: re.Pattern[str] | None = None


_AUDITOR_NAMES = (
    "致同", "安永", "畢馬威", "毕马威", "德勤", "普華永道", "普华永道", "羅兵咸", "罗兵咸",
    "信永中和", "立信", "天健", "大華", "大华", "大信", "中審", "中审",
    "Grant Thornton", "Ernst & Young", "KPMG", "Deloitte", "PwC", "PricewaterhouseCoopers",
)

_CONSOLIDATED_BALANCE_SHEET_PAGE = re.compile(r"合\s*并\s*资\s*产\s*负\s*债\s*表")
_CASH_EQUIVALENTS_COMPOSITION_PAGE = re.compile(r"现金和现金等价物的构成")
_BALANCE_SHEET_NOTE = r"(?:\s+(?:[（(][^）)\n]+[）)]\d*|[\u4e00-\u9fff]+、\d+))?"
_BALANCE_SHEET_COMPARATIVE_VALUES = r"\s+([\d,]+\.\d+)\s+[\d,]+\.\d+(?:\s+[\d,]+\.\d+)?\s*$"

_PATTERN_RULES = (
    PatternRule(
        "auditor_name", "audit",
        re.compile("(" + "|".join(re.escape(name) for name in _AUDITOR_NAMES) + ")", re.IGNORECASE),
        "text", "not_applicable",
    ),
    PatternRule(
        "audit_opinion", "audit",
        re.compile(r"(無保留意見|无保留意见|未經修訂意見|未经修订意见|unqualified opinion)", re.IGNORECASE),
        "text", "consolidated", transform=lambda _value: "unmodified", min_page=20,
    ),
    PatternRule(
        "audit_opinion", "audit",
        re.compile(r"((?<!無)(?<!无)保留意見|(?<!無)(?<!无)保留意见|否定意見|否定意见|無法表示意見|无法表示意见|qualified opinion|adverse opinion|disclaimer of opinion)", re.IGNORECASE),
        "text", "consolidated", transform=lambda value: "modified:" + value.strip(), min_page=20,
    ),
    PatternRule(
        "overall_gross_margin_pct", "operations",
        re.compile(r"整[體体]毛利率[^\d%]{0,20}([\d.]+)\s*%"),
        "pct", "consolidated", transform=_parse_number,
    ),
    PatternRule(
        "business_property_gross_margin_pct", "operations",
        re.compile(r"^商務物業\s+[\d,().-]+\s+([\d.]+)(?:\s|$)", re.MULTILINE),
        "pct", "business_property_segment", transform=_parse_number,
    ),
    PatternRule(
        "non_business_property_gross_margin_pct", "operations",
        re.compile(r"^非商務物業\s+[\d,().-]+\s+([\d.]+)(?:\s|$)", re.MULTILINE),
        "pct", "non_business_property_segment", transform=_parse_number,
    ),
    PatternRule(
        "diversified_operations_gross_margin_pct", "operations",
        # Require a parenthesized gross-profit value so the revenue-mix table
        # (which has the same row label) cannot be mistaken for gross margin.
        re.compile(r"^多元經營\s+(?:\([\d,.]+\))\s+(\(?[\d.]+\)?)(?:\s|$)", re.MULTILINE),
        "pct", "diversified_operations_segment", transform=_parse_accounting_number,
    ),
    PatternRule(
        "net_profit_parent_rmb_m", "financial",
        re.compile(r"本公司擁有人應佔利潤(?:約為|约为)?人民幣\s*([\d.]+)\s*百萬元"),
        "RMB_m", "attributable_to_company_owners", currency="RMB", transform=_parse_number,
    ),
    PatternRule(
        "residential_ac_industry_domestic_units_m", "operations",
        re.compile(
            r"(?:根据|据)产业在\s*线(?:数据)?[\s\S]{0,220}?家用空调(?:行业)?[\s\S]{0,220}?"
            r"(?:其中[，,]?(?:空调)?内销(?:市场)?(?:销量|出货)?|内销(?:市场)?(?:销量|出货)?)\s*([\d,]+(?:\.\d+)?)\s*万\s*台",
        ),
        "million_units", "named_industry_provider_domestic_sales_or_shipments", transform=_parse_number,
    ),
    PatternRule(
        "residential_ac_industry_domestic_units_yoy_pct", "operations",
        re.compile(
            r"(?:根据|据)产业在\s*线(?:数据)?[\s\S]{0,220}?家用空调(?:行业)?[\s\S]{0,220}?"
            r"(?:其中[，,]?(?:空调)?内销(?:市场)?(?:销量|出货)?|内销(?:市场)?(?:销量|出货)?)\s*[\d,]+(?:\.\d+)?\s*万\s*台[，,]?"
            r"((?:同比)?(?:增长|下降|微增|微降)\s*[\d.]+%)",
        ),
        "pct", "named_industry_provider_domestic_sales_or_shipments", transform=_parse_yoy_change,
    ),
    PatternRule(
        "company_residential_ac_domestic_units_m", "operations",
        re.compile(r"公司家用空调内销为\s*([\d,]+(?:\.\d+)?)\s*万台"),
        "million_units", "company_disclosed_domestic_sales_volume", transform=_parse_number,
    ),
    PatternRule(
        "company_residential_ac_domestic_units_yoy_pct", "operations",
        re.compile(r"公司家用空调内销为\s*[\d,]+(?:\.\d+)?\s*万台[，,]?((?:同比)?(?:增长|下降|微增|微降)\s*[\d.]+%)"),
        "pct", "company_disclosed_domestic_sales_volume", transform=_parse_yoy_change,
    ),
    # Chinese A-share annual reports often contain the items below only in the
    # cash-flow notes.  Extract them separately so a headline OCF figure cannot
    # be silently promoted into recurring owner cash.
    PatternRule(
        "operating_cash_flow_rmb_m", "financial",
        re.compile(r"经营活动产生的现金流量净额\s+([\d,]+\.\d+)\s+[\d,]+\.\d+", re.MULTILINE),
        "RMB_m", "consolidated_cash_flow", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "cash_capex_rmb_m", "financial",
        re.compile(r"购建固定资产、无形资产和其他长期资产支付的现金\s+([\d,]+\.\d+)\s+[\d,]+\.\d+", re.MULTILINE),
        "RMB_m", "consolidated_cash_flow", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "cash_receipts_from_customers_rmb_m", "financial",
        re.compile(r"销售商品、提供劳务收到的现金\s+([\d,]+\.\d+)\s+[\d,]+\.\d+", re.MULTILINE),
        "RMB_m", "consolidated_cash_flow", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "operating_restricted_funds_release_rmb_m", "financial",
        re.compile(r"票据、保函保证金等经营活动有关\s*\n\s*受限资金净减少额\s*\n\s*([\d,]+\.\d+)", re.MULTILINE),
        "RMB_m", "operating_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "operating_restricted_funds_release_rmb_m", "financial",
        re.compile(r"票据、保函保证金等经营活动有关\s*\n\s*([\d,]+\.\d+)\s*\n\s*受限资金净减少额", re.MULTILINE),
        "RMB_m", "operating_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "operating_restricted_funds_release_rmb_m", "financial",
        re.compile(r"票据质押保证金、保函保证金等净减少额\s+([\d,]+\.\d+)", re.MULTILINE),
        "RMB_m", "operating_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "operating_restricted_funds_addition_rmb_m", "financial",
        re.compile(r"票据、保函保证金等经营活动有关\s*\n\s*([\d,]+\.\d+)(?:\s+[\d,]+\.\d+)?\s*\n\s*受限资金净增加额", re.MULTILINE),
        "RMB_m", "operating_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    # The cash-flow supplement is the only report location that separates
    # immediately usable cash from term deposits and restricted deposits.
    # This is a liquidity-state observation, not a claim that the balance is
    # distributable owner cash (the finance subsidiary and capital needs still
    # require their own evidence).
    PatternRule(
        "cash_and_cash_equivalents_rmb_m", "financial",
        re.compile(r"^四、期末现金及现金等价物余额\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_cash_equivalents_composition", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
        nearby_page_pattern=_CASH_EQUIVALENTS_COMPOSITION_PAGE,
    ),
    # Some extracted CNInfo tables render the amount between a split word;
    # others retain the full label ahead of the amount.  They are deliberately
    # separate rules with one fact identity so only the first valid rendering
    # on the identified cash-equivalents page is admitted.
    PatternRule(
        "term_deposits_excluded_from_cash_equivalents_rmb_m", "financial",
        re.compile(r"^不属于现金及现金等价物范\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s+畴的定期存款及应计利息\s*$", re.MULTILINE),
        "RMB_m", "consolidated_cash_equivalents_composition", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
        nearby_page_pattern=_CASH_EQUIVALENTS_COMPOSITION_PAGE,
    ),
    PatternRule(
        "term_deposits_excluded_from_cash_equivalents_rmb_m", "financial",
        re.compile(r"^不属于现金及现金等价物范\s*畴的定期存款及应计利息\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_cash_equivalents_composition", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
        nearby_page_pattern=_CASH_EQUIVALENTS_COMPOSITION_PAGE,
    ),
    PatternRule(
        "restricted_monetary_funds_rmb_m", "financial",
        re.compile(r"^使用受到限制的存款\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_cash_equivalents_composition", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
        nearby_page_pattern=_CASH_EQUIVALENTS_COMPOSITION_PAGE,
    ),
    PatternRule(
        "financial_product_redemptions_rmb_m", "capital_allocation",
        re.compile(r"货币性投资产品、大额存单、债务\s*\n?\s*([\d,]+\.\d+)\s+[\d,]+\.\d+\s*\n?\s*工具投资等产品赎回", re.MULTILINE),
        "RMB_m", "investment_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "financial_product_purchases_rmb_m", "capital_allocation",
        re.compile(r"货币性投资产品、大额存单、债务\s*\n?\s*([\d,]+\.\d+)\s+[\d,]+\.\d+\s*\n?\s*工具投资等产品支付", re.MULTILINE),
        "RMB_m", "investment_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "net_new_term_deposits_rmb_m", "capital_allocation",
        re.compile(r"定期存款净增加额\s+([\d,]+\.\d+)\s+[\d,]+\.\d+", re.MULTILINE),
        "RMB_m", "investment_cash_flow_note", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "gree_titanium_cip_impairment_rmb_m", "capital_allocation",
        re.compile(r"在建工程的减值测试情况[\s\S]{0,1000}?格力钛工程\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+([\d,]+\.\d+)", re.MULTILINE),
        "RMB_m", "construction_project_impairment_test", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "accounts_receivable_rmb_m", "financial",
        re.compile(r"^应收账款" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "contract_assets_rmb_m", "financial",
        re.compile(r"^合同资产" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "prepayments_rmb_m", "financial",
        re.compile(r"^预付款项" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "other_receivables_rmb_m", "financial",
        re.compile(r"^其他应收款" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "trading_financial_assets_rmb_m", "capital_allocation",
        re.compile(r"^交易性金融资产" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "inventory_rmb_m", "financial",
        re.compile(r"^存货" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "accounts_payable_rmb_m", "financial",
        re.compile(r"^应付账款" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "short_term_borrowings_rmb_m", "financial",
        re.compile(r"^短期借款" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    PatternRule(
        "contract_liabilities_rmb_m", "financial",
        re.compile(r"^合同负债" + _BALANCE_SHEET_NOTE + _BALANCE_SHEET_COMPARATIVE_VALUES, re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
        required_page_pattern=_CONSOLIDATED_BALANCE_SHEET_PAGE,
    ),
    # This is an accounting-note identification of the counterparty, not a
    # conclusion about channel demand, inventory, or cash accessibility.
    PatternRule(
        "contract_liabilities_primary_counterparty", "financial",
        re.compile(r"(合同负债主要是预收经销商的货款)"),
        "text", "contract_liability_note", transform=lambda _value: "dealer_prepayments",
    ),
    # Sales rebates sit in other current liabilities.  Extract them separately
    # from sales expense so research cannot silently treat a balance as a
    # period promotion cost or infer a rebate rate without a revenue/channel bridge.
    PatternRule(
        "sales_rebates_payable_rmb_m", "financial",
        re.compile(r"^销售返利\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "other_current_liabilities_sales_rebates", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "sales_expense_rmb_m", "financial",
        re.compile(r"^销售费用\s+五、\d+\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_sales_expense", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    # A later annual report can restate an earlier comparative amount because
    # costs moved between sales expense and operating cost.  Preserve that
    # signed movement as its own observation; never silently overwrite the
    # original-period filing or call the difference a channel-cost trend.
    PatternRule(
        "sales_expense_policy_reclassification_rmb_m", "financial",
        re.compile(r"销售费用\s+(-?[\d,]+\.\d+)\s*\n\s*营业成本\s+[\d,]+\.\d+", re.MULTILINE),
        "RMB_m", "sales_expense_to_operating_cost_policy_reclassification", currency="RMB",
        transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "interest_expense_rmb_m", "financial",
        re.compile(r"^其中：利息费用\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_income_statement", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "interest_income_rmb_m", "financial",
        re.compile(r"^利息收入\s+([\d,]+\.\d+)\s+[\d,]+\.\d+\s*$", re.MULTILINE),
        "RMB_m", "consolidated_income_statement", currency="RMB", transform=lambda value: _parse_number(value) / 1_000_000,
    ),
    PatternRule(
        "consumer_electrics_gross_margin_pct", "operations",
        # The operating-analysis table places product revenue and cost before
        # margin.  Requiring both monetary columns and the percentage keeps it
        # distinct from the revenue-mix table with the same product label.
        re.compile(r"^消费电器\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+([\d.]+)%\s+[-\d.]", re.MULTILINE),
        "pct", "consumer_electrics_product_gross_margin", transform=_parse_number,
    ),
    PatternRule(
        "consumer_electrics_revenue_yoy_pct", "operations",
        re.compile(r"^消费电器\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+[\d.]+%\s+(-?[\d.]+)%", re.MULTILINE),
        "pct", "consumer_electrics_product_revenue_year_over_year", transform=_parse_number,
    ),
    PatternRule(
        "air_conditioner_product_gross_margin_pct", "operations",
        re.compile(r"^空调\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+([\d.]+)%\s+-?[\d.]+%", re.MULTILINE),
        "pct", "air_conditioner_product_gross_margin", transform=_parse_number,
    ),
    PatternRule(
        "air_conditioner_product_revenue_yoy_pct", "operations",
        re.compile(r"^空调\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+[\d.]+%\s+(-?[\d.]+)%", re.MULTILINE),
        "pct", "air_conditioner_product_revenue_year_over_year", transform=_parse_number,
    ),
    PatternRule(
        "domestic_main_business_revenue_yoy_pct", "operations",
        re.compile(r"^内销-主营业\s*务\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+[\d.]+%\s+(-?[\d.]+)%", re.MULTILINE),
        "pct", "domestic_main_business_revenue_year_over_year", transform=_parse_number,
    ),
    PatternRule(
        "residential_ac_online_retail_share_pct", "operations",
        # This is a named third-party market-data observation reproduced in an
        # audited annual report.  It is a channel signal, not a proxy for total
        # market share or a reason to infer a whole-company margin.
        re.compile(r"家\s*用\s*空\s*调线上(?:市场)?零售额(?:市场)?(?:份额|占比)为\s*([\d.]+)%"),
        "pct", "company_position_in_named_channel_market_data", transform=_parse_number,
    ),
    PatternRule(
        "goodwill_impairment_rmb_m", "capital_allocation",
        re.compile(r"商譽減值虧損[^\d]{0,30}(?:人民幣)?\s*([\d.]+)\s*百萬元"),
        "RMB_m", "consolidated_income_statement", currency="RMB",
        transform=_parse_number,
    ),
    PatternRule(
        "dividend_payout_ratio_pct", "capital_allocation",
        re.compile(r"派息比\s*例(?:相當於)?約為\s*([\d.]+)\s*%"),
        "pct", "board_proposal", transform=_parse_number,
    ),
    PatternRule(
        "finance_company_max_daily_deposit_rmb_m", "governance",
        re.compile(r"最高每日存款結\s*餘約為人民幣\s*([\d.]+)\s*百萬元"),
        "RMB_m", "related_party_deposit_framework", currency="RMB",
        transform=_parse_number,
    ),
    PatternRule(
        "finance_company_interest_income_rmb_m", "governance",
        re.compile(r"獲取的最高利息為人民\s*幣\s*([\d.]+)\s*百萬元"),
        "RMB_m", "related_party_deposit_framework", currency="RMB",
        transform=_parse_number,
    ),
    PatternRule(
        "restricted_bank_deposits_rmb_m", "financial",
        re.compile(r"^受限制銀行存款(?:（[^\n]*?）)?\s+(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB",
        transform=lambda value: _parse_number(value) / 1000,
    ),
    PatternRule(
        "cash_and_cash_equivalents_rmb_m", "financial",
        re.compile(r"^現金及現金等價物(?:（[^\n]*?）)?\s+(?:\d{1,2}\s+)?(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE),
        "RMB_m", "consolidated_balance_sheet", currency="RMB",
        transform=lambda value: _parse_number(value) / 1000,
    ),
    PatternRule(
        "related_party_term_deposits_rmb_m", "governance",
        re.compile(r"^—\s*同系附屬公司的定期存款(?:（[^\n]*?）)?\s+(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE),
        "RMB_m", "related_party_deposit", currency="RMB",
        transform=lambda value: _parse_number(value) / 1000,
    ),
    PatternRule(
        "amounts_placed_with_fellow_subsidiary_rmb_m", "governance",
        re.compile(r"^存於一間同系附屬公司的款項\s+(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE),
        "RMB_m", "related_party_balance", currency="RMB",
        transform=lambda value: _parse_number(value) / 1000,
    ),
    PatternRule(
        "controlling_shareholder_identity", "governance",
        re.compile(r"(金融街集團)[^\u3002\n]{0,40}(?:我們的|本公司的|本公司之)?控股股東"),
        "text", "legal_control", transform=lambda value: value.strip(),
    ),
    PatternRule(
        "managed_area_m_sqm", "operations",
        re.compile(r"(?:總|总)?在管(?:建築|建筑)面積(?:約為|约为|約|约|為|为)\s*([\d.]+)\s*百萬平方米"),
        "million_sqm", "operating_disclosure", transform=_parse_number,
    ),
    PatternRule(
        "project_count", "operations",
        re.compile(r"(?:總|总)在管(?:項目|项目)(?:數量|数量)?(?:約為|约为|為|为)?\s*([\d,]+)\s*個"),
        "count", "operating_disclosure", transform=lambda value: int(_parse_number(value)),
    ),
)

_FINANCIAL_CANDIDATES: dict[str, tuple[str, str, str | None]] = {
    "资产总计": ("total_assets", "financial", None),
    "資產總計": ("total_assets", "financial", None),
    "营业收入": ("revenue", "financial", None),
    "營業收入": ("revenue", "financial", None),
    "经营活动CF": ("operating_cash_flow", "financial", None),
    "經營活動CF": ("operating_cash_flow", "financial", None),
    "归母净利润": ("net_profit_parent", "financial", None),
    "歸母淨利潤": ("net_profit_parent", "financial", None),
    "货币资金": ("cash", "financial", None),
    "貨幣資金": ("cash", "financial", None),
    "总股本": ("shares_outstanding", "financial", None),
    "總股本": ("shares_outstanding", "financial", None),
    "股息总额": ("dividends_total", "capital_allocation", None),
    "股息總額": ("dividends_total", "capital_allocation", None),
}


def _document_text(output: Path, document: dict[str, Any]) -> tuple[Path | None, str]:
    relative = document.get("derived_text_path")
    if not relative and str(document.get("local_path") or "").endswith(".md"):
        relative = document.get("local_path")
    path = output / str(relative) if relative else None
    if path is None or not path.is_file():
        return None, ""
    try:
        return path, path.read_text(encoding="utf-8")
    except OSError:
        return path, ""


def _verified_observations(output: Path, document: dict[str, Any]) -> list[dict[str, Any]]:
    path, text = _document_text(output, document)
    if path is None or not text or document.get("authority") not in OFFICIAL_DOCUMENT_AUTHORITIES:
        return []
    observations: list[dict[str, Any]] = []
    seen_fact: set[str] = set()
    blocks = _page_blocks(text)
    for rule in _PATTERN_RULES:
        for block_index, block in enumerate(blocks):
            if int(block["page"]) < rule.min_page:
                continue
            if rule.required_page_pattern and not rule.required_page_pattern.search(str(block["text"])):
                continue
            if rule.nearby_page_pattern:
                previous_page_text = str(blocks[block_index - 1]["text"]) if block_index else ""
                if (
                    not rule.nearby_page_pattern.search(str(block["text"]))
                    and not rule.nearby_page_pattern.search(previous_page_text)
                ):
                    continue
            match = rule.pattern.search(str(block["text"]))
            if not match:
                continue
            raw_value = match.group(1)
            normalized = rule.transform(raw_value)
            dedupe = rule.fact_name
            if dedupe in seen_fact:
                break
            quote, start, end = _line_quote(block, match)
            observation: dict[str, Any] = {
                "observation_id": "",
                "fact_name": rule.fact_name,
                "domain": rule.domain,
                "raw_value": raw_value,
                "normalized_value": normalized,
                "unit": rule.unit,
                "currency": rule.currency,
                "basis": rule.basis,
                "as_of": document["period_end"],
                "doc_id": document["doc_id"],
                "locator": {
                    "page": int(block["page"]), "section": rule.domain, "table": None,
                    "row": None, "column": None, "char": {"start": start, "end": end},
                },
                "raw_text": quote,
                "extraction_method": "page_markdown_regex_verified",
                "status": "VERIFIED",
                "confidence": 0.95,
                "conflict_ids": [],
            }
            observation["observation_id"] = make_observation_id(observation)
            observations.append(observation)
            seen_fact.add(dedupe)
            break
    return observations


def _company_only_balance_sheet_observations(output: Path, document: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the listed-company (not consolidated) cash location.

    A group cash balance and a parent-company balance answer different
    questions.  The latter is essential for cash-realisation analysis, so it
    must not be lost merely because the same row labels occur earlier in the
    consolidated statement.
    """
    path, text = _document_text(output, document)
    if path is None or not text or document.get("authority") not in OFFICIAL_DOCUMENT_AUTHORITIES:
        return []
    rules = (
        ("company_only_cash_and_cash_equivalents_rmb_m", re.compile(
            r"^現金及現金等價物(?:（[^\n]*?）)?\s+(?:\d{1,2}\s+)?(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE
        )),
        ("company_only_term_deposits_rmb_m", re.compile(
            r"^到期日超過三個月的銀行存款\s+(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE
        )),
        ("company_only_restricted_bank_deposits_rmb_m", re.compile(
            r"^受限制銀行存款\s+(\d[\d,]*)\s+\d[\d,]*\s*$", re.MULTILINE
        )),
    )
    observations: list[dict[str, Any]] = []
    company_statement_page: int | None = None
    for block in _page_blocks(text):
        page = int(block["page"])
        page_text = str(block["text"])
        if re.search(r"公司財務狀況報表", page_text):
            company_statement_page = page
        if company_statement_page is None or not company_statement_page <= page <= company_statement_page + 2:
            continue
        for fact_name, pattern in rules:
            if any(item["fact_name"] == fact_name for item in observations):
                continue
            match = pattern.search(page_text)
            if not match:
                continue
            quote, start, end = _line_quote(block, match)
            observation: dict[str, Any] = {
                "observation_id": "",
                "fact_name": fact_name,
                "domain": "financial",
                "raw_value": match.group(1),
                "normalized_value": _parse_number(match.group(1)) / 1000,
                "unit": "RMB_m",
                "currency": "RMB",
                "basis": "company_only_balance_sheet",
                "as_of": document["period_end"],
                "doc_id": document["doc_id"],
                "locator": {
                    "page": page, "section": "financial", "table": None,
                    "row": None, "column": None, "char": {"start": start, "end": end},
                },
                "raw_text": quote,
                "extraction_method": "company_only_balance_sheet_regex_verified",
                "status": "VERIFIED",
                "confidence": 0.95,
                "conflict_ids": [],
            }
            observation["observation_id"] = make_observation_id(observation)
            observations.append(observation)
    return observations


def _candidate_financials(output: Path, document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("doc_type") != "annual_report":
        return []
    year = str(document.get("period_end") or "")[:4]
    path = output / f"pdf_sections_{year}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    financials = payload.get("financials") if isinstance(payload, dict) else None
    if not isinstance(financials, dict):
        return []
    result: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for label, value in sorted(financials.items()):
        definition = _FINANCIAL_CANDIDATES.get(str(label))
        if definition is None or value is None:
            continue
        fact_name, domain, currency = definition
        if fact_name in emitted:
            continue
        observation: dict[str, Any] = {
            "observation_id": "",
            "fact_name": fact_name,
            "domain": domain,
            "raw_value": value,
            "normalized_value": value,
            "unit": "source_native_unresolved",
            "currency": currency,
            "basis": "unresolved",
            "as_of": document["period_end"],
            "doc_id": document["doc_id"],
            "locator": {"page": None, "section": "financials", "table": None, "row": str(label), "column": None, "char": None},
            "raw_text": "",
            "extraction_method": "legacy_pdf_sections_candidate",
            "status": "CANDIDATE",
            "confidence": 0.4,
            "conflict_ids": [],
        }
        observation["observation_id"] = make_observation_id(observation)
        result.append(observation)
        emitted.add(fact_name)
    return result


def _apply_conflicts(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(observations)
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in result:
        if item.get("status") not in {"VERIFIED", "CONFLICT"}:
            continue
        key = (
            str(item.get("fact_name")), str(item.get("as_of")), str(item.get("basis")),
            str(item.get("unit")), str(item.get("currency")),
        )
        groups[key].append(item)
    for members in groups.values():
        values = {_canonical_json(_normalized_identity_value(item.get("normalized_value"))) for item in members}
        if len(values) <= 1:
            continue
        ids = [str(item["observation_id"]) for item in members]
        for item in members:
            item["status"] = "CONFLICT"
            item["conflict_ids"] = sorted(value for value in ids if value != item["observation_id"])
    return result


def validate_fact_observations(
    payload: dict[str, Any], manifest: dict[str, Any], output_dir: str | Path | None = None
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if payload.get("manifest_hash") != manifest.get("manifest_hash"):
        invalid.append("manifest_hash_mismatch")
    documents = {str(doc.get("doc_id")): doc for doc in manifest.get("documents") or [] if isinstance(doc, dict)}
    observations = payload.get("observations")
    if not isinstance(observations, list):
        invalid.append("observations_not_array")
        observations = []
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    output = Path(output_dir) if output_dir is not None else None
    text_cache: dict[str, str] = {}
    for index, item in enumerate(observations):
        prefix = f"observations[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        observation_id = str(item.get("observation_id") or "")
        if observation_id != make_observation_id(item):
            invalid.append(f"{observation_id or prefix}:identity_mismatch")
        elif observation_id in seen:
            invalid.append("duplicate_observation_id:" + observation_id)
        seen.add(observation_id)
        status = str(item.get("status") or "")
        counts[status] += 1
        if status not in STATUSES:
            invalid.append(f"{observation_id or prefix}:status_invalid")
        valuation_roles = item.get("valuation_evidence_roles")
        if valuation_roles is not None:
            if (
                not isinstance(valuation_roles, list)
                or not valuation_roles
                or any(
                    not isinstance(role, str)
                    or not _VALUATION_EVIDENCE_ROLE_RE.fullmatch(role)
                    for role in valuation_roles
                )
                or len(valuation_roles) != len(set(valuation_roles))
            ):
                invalid.append(
                    f"{observation_id or prefix}:valuation_evidence_roles_invalid"
                )
        exclusion_destinations = item.get("valuation_exclusion_destinations")
        if exclusion_destinations is not None:
            if (
                not isinstance(exclusion_destinations, list)
                or not exclusion_destinations
                or any(
                    destination not in _VALUATION_EXCLUSION_DESTINATIONS
                    for destination in exclusion_destinations
                )
                or len(exclusion_destinations) != len(set(exclusion_destinations))
            ):
                invalid.append(
                    f"{observation_id or prefix}:valuation_exclusion_destinations_invalid"
                )
        measurement_context = item.get("measurement_context")
        if measurement_context is not None:
            if not isinstance(measurement_context, dict):
                invalid.append(f"{observation_id or prefix}:measurement_context_invalid")
            else:
                allowed_context_fields = {
                    "period_start", "period_end", "economic_entity", "operating_perimeter",
                    "cohort_id", "project_id", "customer_scope", "batch_id",
                    "stock_flow_role", "settlement_status", "loss_treatment",
                }
                if set(measurement_context) - allowed_context_fields:
                    invalid.append(
                        f"{observation_id or prefix}:measurement_context_unknown_fields"
                    )
                start = measurement_context.get("period_start")
                end = measurement_context.get("period_end")
                try:
                    start_date = datetime.fromisoformat(start).date() if start else None
                    end_date = datetime.fromisoformat(end).date() if end else None
                except (TypeError, ValueError):
                    invalid.append(
                        f"{observation_id or prefix}:measurement_period_invalid"
                    )
                    start_date = end_date = None
                if start_date and end_date and start_date > end_date:
                    invalid.append(
                        f"{observation_id or prefix}:measurement_period_reversed"
                    )
        doc_id = str(item.get("doc_id") or "")
        doc = documents.get(doc_id)
        if doc is None:
            invalid.append(f"{observation_id or prefix}:unknown_doc_id:{doc_id}")
            continue
        invalid.extend(
            f"{observation_id or prefix}:{finding}"
            for finding in _temporal_contract_findings(item, doc)
        )
        if status == "VERIFIED":
            locator = item.get("locator") if isinstance(item.get("locator"), dict) else {}
            quote = str(item.get("raw_text") or "")
            if not quote or not locator.get("page"):
                invalid.append(f"{observation_id or prefix}:verified_locator_missing")
            if doc.get("authority") not in OFFICIAL_DOCUMENT_AUTHORITIES:
                invalid.append(f"{observation_id or prefix}:non_official_source_cannot_verify")
            if output is not None and quote:
                relative = doc.get("derived_text_path")
                if not relative:
                    invalid.append(f"{observation_id or prefix}:derived_text_missing")
                else:
                    if doc_id not in text_cache:
                        try:
                            text_cache[doc_id] = (output / str(relative)).read_text(encoding="utf-8")
                        except OSError:
                            text_cache[doc_id] = ""
                    page_text = next((b["text"] for b in _page_blocks(text_cache[doc_id]) if b["page"] == locator.get("page")), "")
                    if quote not in page_text:
                        invalid.append(f"{observation_id or prefix}:quote_not_at_locator")
        if status == "CONFLICT":
            incomplete.append(f"fact_conflict:{item.get('fact_name')}:{item.get('as_of')}")
        if status == "CANDIDATE":
            warnings.append(f"candidate_not_citable:{observation_id}")
    expected_hash = _payload_hash(_observation_core(payload))
    if payload.get("observation_hash") != expected_hash:
        invalid.append("observation_hash_mismatch")
    if not counts.get("VERIFIED"):
        incomplete.append("verified_fact_missing")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "state": state,
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
        "warnings": list(dict.fromkeys(warnings)),
        "counts": dict(sorted(counts.items())),
    }


def build_fact_observations(
    output_dir: str | Path, manifest: dict[str, Any], *, persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    observations: list[dict[str, Any]] = []
    for document in manifest.get("documents") or []:
        if not isinstance(document, dict):
            continue
        observations.extend(_verified_observations(output, document))
        observations.extend(_company_only_balance_sheet_observations(output, document))
        observations.extend(_candidate_financials(output, document))
    # Exact-quote observations are durable research work. Preserve them across
    # deterministic rebuilds as long as their source document still exists;
    # validation below rechecks the quote and locator against current content.
    known_docs = {str(item.get("doc_id")) for item in manifest.get("documents") or [] if isinstance(item, dict)}
    try:
        previous = json.loads((output / "fact_observations.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    observations.extend(
        deepcopy(item)
        for item in previous.get("observations") or []
        if isinstance(item, dict)
        and item.get("extraction_method") == "exact_quote_programmatic_verification"
        and str(item.get("doc_id")) in known_docs
    )
    observations = list({str(item.get("observation_id")): item for item in observations}.values())
    observations = _apply_conflicts(observations)
    observations.sort(key=lambda item: (
        str(item.get("as_of")), str(item.get("domain")), str(item.get("fact_name")),
        str(item.get("doc_id")), str(item.get("observation_id")),
    ))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": manifest.get("report_id"),
        "manifest_hash": manifest.get("manifest_hash"),
        "generated_at": _now(),
        "observations": observations,
    }
    payload["observation_hash"] = _payload_hash(_observation_core(payload))
    payload["validation"] = validate_fact_observations(payload, manifest, output)
    if persist:
        _atomic_write_json(output / "fact_observations.json", payload)
    return payload


def verify_fact_from_quote(
    output_dir: str | Path,
    *,
    doc_id: str,
    page: int,
    fact_name: str,
    domain: str,
    raw_value: Any,
    normalized_value: Any,
    unit: str,
    basis: str,
    quote: str,
    currency: str | None = None,
    as_of: str | None = None,
    temporal_role: str | None = None,
    event_date: str | None = None,
    observed_at: str | None = None,
    measurement_context: dict[str, Any] | None = None,
    valuation_evidence_roles: list[str] | None = None,
    valuation_exclusion_destinations: list[str] | None = None,
) -> dict[str, Any]:
    """Programmatically promote an exact page quote to VERIFIED evidence."""
    output = Path(output_dir)
    manifest = json.loads((output / "document_manifest.json").read_text(encoding="utf-8"))
    try:
        from scripts.evidence_documents import validate_document_manifest
    except ModuleNotFoundError:
        from evidence_documents import validate_document_manifest
    if validate_document_manifest(manifest, output).get("state") != "REVIEWABLE":
        return {"verified": False, "error": "document_manifest_not_reviewable"}
    documents = {str(doc.get("doc_id")): doc for doc in manifest.get("documents") or []}
    document = documents.get(str(doc_id))
    if not document:
        return {"verified": False, "error": "unknown_doc_id"}
    if document.get("authority") not in OFFICIAL_DOCUMENT_AUTHORITIES:
        return {"verified": False, "error": "non_official_source_cannot_verify"}
    if document.get("verification_mode") == "STRUCTURED_DATA":
        return {"verified": False, "error": "structured_document_requires_deterministic_data_verifier"}
    _, text = _document_text(output, document)
    block = next((item for item in _page_blocks(text) if item["page"] == int(page)), None)
    exact_quote = str(quote or "").strip()
    if not block or not exact_quote or exact_quote not in str(block["text"]):
        return {"verified": False, "error": "quote_not_at_locator"}
    if isinstance(raw_value, (int, float)):
        numeric_tokens = [_parse_number(item) for item in re.findall(r"[-+]?\d[\d,，]*(?:\.\d+)?", exact_quote)]
        if not any(abs(float(raw_value) - token) <= max(1e-9, abs(float(raw_value)) * 1e-9) for token in numeric_tokens):
            return {"verified": False, "error": "raw_value_not_in_quote"}
    quote_start = str(block["text"]).index(exact_quote)
    absolute_start = int(block["start"]) + quote_start
    explicit_as_of = str(as_of or "").strip()
    if temporal_role == "HISTORICAL_PERIOD" and not explicit_as_of:
        explicit_as_of = str(
            (measurement_context.get("period_end") or "")
            if isinstance(measurement_context, dict)
            else ""
        )
    if temporal_role == "EVENT" and not explicit_as_of:
        explicit_as_of = str(event_date or "")
    observation: dict[str, Any] = {
        "observation_id": "",
        "fact_name": str(fact_name).strip(),
        "domain": str(domain).strip(),
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "unit": str(unit).strip(),
        "currency": currency,
        "basis": str(basis).strip(),
        "as_of": explicit_as_of or document["period_end"],
        "doc_id": document["doc_id"],
        "locator": {"page": int(page), "section": str(domain), "table": None, "row": None, "column": None, "char": {"start": absolute_start, "end": absolute_start + len(exact_quote)}},
        "raw_text": exact_quote,
        "extraction_method": "exact_quote_programmatic_verification",
        "status": "VERIFIED",
        "confidence": 0.98,
        "conflict_ids": [],
    }
    if temporal_role is not None:
        if temporal_role not in TEMPORAL_ROLES:
            return {"verified": False, "error": "temporal_role_invalid"}
        observation["temporal_role"] = temporal_role
    if event_date is not None:
        observation["event_date"] = str(event_date)
    if observed_at is not None:
        observation["observed_at"] = str(observed_at)
    if measurement_context is not None:
        allowed_context_fields = {
            "period_start", "period_end", "economic_entity", "operating_perimeter",
            "cohort_id", "project_id", "customer_scope", "batch_id",
            "stock_flow_role", "settlement_status", "loss_treatment",
        }
        unknown_context_fields = set(measurement_context) - allowed_context_fields
        if unknown_context_fields:
            return {
                "verified": False,
                "error": "measurement_context_unknown_fields:" + "|".join(
                    sorted(unknown_context_fields)
                ),
            }
        if measurement_context.get("stock_flow_role") not in {
            None, "OPENING_STOCK", "CLOSING_STOCK", "GROWTH_LAUNCH_ADDITION",
            "STEADY_ROLLOVER_ADDITION", "COLLECTION_OR_SETTLEMENT",
            "PERMANENT_LOSS", "NONCASH_SCOPE_CHANGE",
        }:
            return {"verified": False, "error": "measurement_context_stock_flow_role_invalid"}
        if measurement_context.get("loss_treatment") not in {
            None, "RECURRING_EXPECTED", "ONE_OFF_PERMANENT", "NO_LOSS", "UNKNOWN",
        }:
            return {"verified": False, "error": "measurement_context_loss_treatment_invalid"}
        observation["measurement_context"] = deepcopy(measurement_context)
    temporal_findings = _temporal_contract_findings(observation, document)
    if temporal_findings:
        return {
            "verified": False,
            "error": "temporal_contract_invalid:" + "|".join(temporal_findings),
        }
    if valuation_evidence_roles is not None:
        if (
            not valuation_evidence_roles
            or any(
                not isinstance(role, str)
                or not _VALUATION_EVIDENCE_ROLE_RE.fullmatch(role)
                for role in valuation_evidence_roles
            )
            or len(valuation_evidence_roles) != len(set(valuation_evidence_roles))
        ):
            return {"verified": False, "error": "valuation_evidence_roles_invalid"}
        observation["valuation_evidence_roles"] = sorted(valuation_evidence_roles)
    if valuation_exclusion_destinations is not None:
        if (
            not valuation_exclusion_destinations
            or any(
                destination not in _VALUATION_EXCLUSION_DESTINATIONS
                for destination in valuation_exclusion_destinations
            )
            or len(valuation_exclusion_destinations)
            != len(set(valuation_exclusion_destinations))
        ):
            return {"verified": False, "error": "valuation_exclusion_destinations_invalid"}
        observation["valuation_exclusion_destinations"] = sorted(
            valuation_exclusion_destinations
        )
    if not observation["fact_name"] or not observation["domain"] or not observation["unit"] or not observation["basis"]:
        return {"verified": False, "error": "required_identity_field_missing"}
    observation["observation_id"] = make_observation_id(observation)
    path = output / "fact_observations.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = build_fact_observations(output, manifest, persist=False)
    existing = [item for item in payload.get("observations") or [] if item.get("observation_id") != observation["observation_id"]]
    existing.append(observation)
    payload["observations"] = sorted(_apply_conflicts(existing), key=lambda item: str(item.get("observation_id")))
    payload["generated_at"] = _now()
    payload["observation_hash"] = _payload_hash(_observation_core(payload))
    payload["validation"] = validate_fact_observations(payload, manifest, output)
    _atomic_write_json(path, payload)
    stored = next(item for item in payload["observations"] if item["observation_id"] == observation["observation_id"])
    return {"verified": stored["status"] == "VERIFIED", "observation": stored, "validation": payload["validation"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="从官方文件派生候选/已验证事实")
    parser.add_argument("--output-dir", "--output", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    manifest = json.loads((output / "document_manifest.json").read_text(encoding="utf-8"))
    payload = build_fact_observations(output, manifest, persist=True)
    print(json.dumps({
        "path": str(output / "fact_observations.json"),
        "state": payload["validation"]["state"],
        "counts": payload["validation"]["counts"],
        "observation_hash": payload["observation_hash"],
    }, ensure_ascii=False))
    return 0 if payload["validation"]["state"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
