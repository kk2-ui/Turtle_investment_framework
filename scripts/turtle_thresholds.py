"""Threshold selection for Turtle static throughput-return analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ThresholdProfile:
    category: str
    ii_pct: float
    star_5_pct: float
    star_4_pct: float
    star_3_pct: float
    method: str
    rationale: str
    evidence: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)


def market_fallback_threshold(ts_code: str, rf_pct: Optional[float]) -> tuple[float | None, str]:
    """Legacy market-level threshold used when no business subtype is clear."""
    if rf_pct is None:
        return None, "需Rf"
    if ts_code.endswith(".HK"):
        return max(5.0, rf_pct + 3.0), f"港股fallback: max(5%, {rf_pct:.2f}%+3%)"
    if ts_code.endswith(".US"):
        return max(4.0, rf_pct + 2.0), f"美股fallback: max(4%, {rf_pct:.2f}%+2%)"
    return max(3.5, rf_pct + 2.0), f"A股fallback: max(3.5%, {rf_pct:.2f}%+2%)"


def classify_threshold_profile(
    ts_code: str,
    company_name: str = "",
    fullname: str = "",
    industry: str = "",
    net_cash: Optional[float] = None,
    debt_ratio_pct: Optional[float] = None,
    payout_pct: Optional[float] = None,
    rf_pct: Optional[float] = None,
    minority_share_pct: Optional[float] = None,
) -> ThresholdProfile:
    """Select GG threshold after judging business subtype.

    The threshold is for static GG = distributable cash x payout / market cap
    under a zero-growth assumption.  It intentionally avoids a single fixed
    7% hurdle across all Hong Kong high-dividend names.
    """
    blob = " ".join([ts_code, company_name, fullname, industry]).lower()
    is_hk = ts_code.endswith(".HK")
    fallback_ii, fallback_method = market_fallback_threshold(ts_code, rf_pct)
    if fallback_ii is None:
        fallback_ii = 7.0 if is_hk else 5.5

    property_mgmt_codes = {"02669.HK", "01209.HK", "06049.HK", "01516.HK", "09666.HK"}
    property_mgmt_terms = [
        "物业", "物管", "property management", "property services",
        "onewo", "poly property", "china overseas property",
        "china resources mixc",
    ]
    utility_terms = ["电力", "公用", "燃气", "水务", "utility", "utilities", "power", "electric", "gas", "water"]
    bank_insurer_terms = ["bank", "银行", "hsbc", "保险", "insurance"]
    defensive_consumer_terms = [
        "食品", "饮料", "可口可乐", "中粮", "装瓶", "汽水",
        "food", "foods", "beverage", "beverages", "coca-cola",
        "consumer staples", "consumer", "bottling", "bottler",
    ]
    cyclic_terms = [
        "煤", "coal", "石油", "油气", "petro", "oil", "gas exploration",
        "mining", "steel", "有色", "commodity", "资源", "神华", "中石油",
    ]

    net_cash_positive = net_cash is not None and net_cash > 0
    low_debt = debt_ratio_pct is not None and debt_ratio_pct <= 5.0
    payout_stable = payout_pct is not None and payout_pct >= 30.0

    def evidence_base(category_hint: str) -> list[str]:
        evidence: list[str] = [f"业务关键词/代码匹配：{category_hint}"]
        if net_cash is not None:
            evidence.append(f"广义净现金：{net_cash:.2f} 百万元")
        if debt_ratio_pct is not None:
            evidence.append(f"有息负债/总资产：{debt_ratio_pct:.2f}%")
        if payout_pct is not None:
            evidence.append(f"派息率锚：{payout_pct:.2f}%")
        if rf_pct is not None:
            evidence.append(f"Rf：{rf_pct:.2f}%")
        while len(evidence) < 3:
            evidence.append("量化证据不足：需结合年报/市场数据复核")
        return evidence[:5]

    def finalize(profile: ThresholdProfile) -> ThresholdProfile:
        adjustments = list(profile.adjustments)
        method = profile.method
        ii_pct = profile.ii_pct
        star_5_pct = profile.star_5_pct
        star_4_pct = profile.star_4_pct
        star_3_pct = profile.star_3_pct
        if minority_share_pct is not None and minority_share_pct > 30.0:
            ii_pct = max(profile.ii_pct - 0.5, 0.0)
            star_5_pct = max(profile.star_5_pct - 0.5, 0.0)
            star_4_pct = max(profile.star_4_pct - 0.5, 0.0)
            star_3_pct = max(profile.star_3_pct - 0.5, 0.0)
            adjustments.append(
                f"少数股东占比{minority_share_pct:.2f}%>30%，II与星级锚下调0.5pct，反映普通股东利润传导折价"
            )
            method = f"{profile.method}；少数股东>30%调整后实际采用{ii_pct:.2f}%"
        return ThresholdProfile(
            category=profile.category,
            ii_pct=ii_pct,
            star_5_pct=star_5_pct,
            star_4_pct=star_4_pct,
            star_3_pct=star_3_pct,
            method=method,
            rationale=profile.rationale,
            evidence=profile.evidence,
            adjustments=adjustments,
        )

    if is_hk and any(term in blob for term in cyclic_terms):
        return finalize(ThresholdProfile(
            category="港股周期高派现金牛",
            ii_pct=8.5,
            star_5_pct=8.5,
            star_4_pct=7.5,
            star_3_pct=6.5,
            method="子类判断: 周期高派现金牛，GG五星锚8%-10%；基础采用8.5%作为买入门槛",
            rationale="周期盈利和估值双杀时才给出真正五星坑位，7%对这类资产偏松。",
            evidence=evidence_base("周期资源/高派现金牛"),
        ))

    if is_hk and (
        ts_code in property_mgmt_codes
        or any(term in blob for term in property_mgmt_terms)
        or (net_cash_positive and low_debt and payout_stable and any(term in blob for term in ["service", "服务", "management", "管理"]))
    ):
        return finalize(ThresholdProfile(
            category="港股净现金轻资产央企物管/服务",
            ii_pct=5.5,
            star_5_pct=5.5,
            star_4_pct=5.0,
            star_3_pct=4.5,
            method="子类判断: 净现金轻资产央企物管/服务，GG五星锚5.5%-6.0%；基础采用5.5%作为买入门槛",
            rationale="净现金硬底、低capex与低杠杆降低静态回报率要求；不按周期高派股的7%-10%坑位要求。",
            evidence=evidence_base("净现金轻资产物管/服务"),
        ))

    if is_hk and (
        any(term in blob for term in utility_terms + bank_insurer_terms + defensive_consumer_terms)
        or (net_cash_positive and payout_stable)
    ):
        return finalize(ThresholdProfile(
            category="港股防御型高派蓝筹/净现金央企",
            ii_pct=6.5,
            star_5_pct=6.5,
            star_4_pct=5.8,
            star_3_pct=5.2,
            method="子类判断: 防御型高派蓝筹/净现金央企，GG五星锚6.5%-7.0%；基础采用6.5%作为买入门槛",
            rationale="防御型现金流资产按历史高股息坑位定价，同时为低增长、利润率波动和治理折价预留安全边际。",
            evidence=evidence_base("防御消费/公用/金融或净现金高派"),
        ))

    return finalize(ThresholdProfile(
        category="通用市场fallback",
        ii_pct=fallback_ii,
        star_5_pct=fallback_ii,
        star_4_pct=max(fallback_ii - 0.75, 0.0),
        star_3_pct=max(fallback_ii - 1.50, 0.0),
        method=fallback_method,
        rationale="未能可靠识别子类，沿用市场无风险利率加风险溢价公式。",
        evidence=evidence_base("通用fallback"),
    ))


# ---------------------------------------------------------------------------
# CLI — used by coordinator Phase 2.6 (threshold anchoring before Phase 3)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json, os, re, sys

    p = argparse.ArgumentParser(description="Compute GG threshold (II) for a stock")
    p.add_argument("--code", required=True, help="Stock code, e.g. 02669.HK")
    p.add_argument("--from-datapack", default=None, help="Read params from data_pack_market.md path")
    p.add_argument("--company-name", default="", help="Company short name")
    p.add_argument("--fullname", default="", help="Company full name")
    p.add_argument("--industry", default="", help="Industry classification")
    p.add_argument("--net-cash", type=float, default=None, help="Net cash in millions")
    p.add_argument("--debt-ratio-pct", type=float, default=None, help="Interest-bearing debt / total assets (pct)")
    p.add_argument("--payout-pct", type=float, default=None, help="Dividend payout ratio 3yr avg (pct)")
    p.add_argument("--rf-pct", type=float, default=None, help="Risk-free rate (pct)")
    p.add_argument("--minority-share-pct", type=float, default=None, help="Minority interest / total profit (pct)")
    p.add_argument("--output", default=None, help="Write JSON to file instead of stdout")
    args = p.parse_args()

    # Auto-extract params from data_pack_market.md if --from-datapack is set
    if args.from_datapack:
        with open(args.from_datapack) as f:
            text = f.read()

        def _extract(pattern, text=text):
            m = re.search(pattern, text)
            return float(m.group(1).replace(",", "")) if m else None

        # Try to fill missing params from datapack
        if args.company_name == "":
            m = re.search(r'公司名称\s*\|\s*(.+?)\s*\|', text)
            if not m:
                m = re.search(r'\|\s*公司名称\s*\|\s*(.+?)\s*\|', text)
            if m: args.company_name = m.group(1).strip()
        if args.fullname == "":
            m = re.search(r'全称\s*\|\s*(.+?)\s*\|', text)
            if not m:
                m = re.search(r'\|\s*全称\s*\|\s*(.+?)\s*\|', text)
            if m: args.fullname = m.group(1).strip()
        if args.net_cash is None:
            args.net_cash = _extract(r'广义净现金.*?\|\s*([\d,]+\.?\d*)')
        if args.debt_ratio_pct is None:
            args.debt_ratio_pct = _extract(r'有息负债/总资产.*?\|\s*([\d,]+\.?\d*)')
        if args.payout_pct is None:
            # M = 支付率3年均值 from §17.2
            args.payout_pct = _extract(r'M（支付率3年均值）\s*\|\s*([\d,]+\.?\d*)')
        if args.rf_pct is None:
            args.rf_pct = _extract(r'Rf（无风险利率）\s*\|\s*([\d,]+\.?\d*)')
        if args.minority_share_pct is None:
            args.minority_share_pct = _extract(r'少数股东占比.*?\|\s*([\d,]+\.?\d*)')

    profile = classify_threshold_profile(
        ts_code=args.code,
        company_name=args.company_name,
        fullname=args.fullname,
        industry=args.industry,
        net_cash=args.net_cash,
        debt_ratio_pct=args.debt_ratio_pct,
        payout_pct=args.payout_pct,
        rf_pct=args.rf_pct,
        minority_share_pct=args.minority_share_pct,
    )

    result = {
        "code": args.code,
        "II": profile.ii_pct,
        "star_5": profile.star_5_pct,
        "star_4": profile.star_4_pct,
        "star_3": profile.star_3_pct,
        "category": profile.category,
        "method": profile.method,
        "rationale": profile.rationale,
        "evidence": profile.evidence,
        "adjustments": profile.adjustments,
    }

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Threshold written to {args.output}")
    else:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
