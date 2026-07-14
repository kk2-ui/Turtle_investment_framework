#!/usr/bin/env python3
"""db_gate.py — 统一数据门禁（v2.0）

输出结构化 QualityFinding，覆盖 field / row / year / cross_source 四类检查。
所有检查结果进入 quality_findings 表，供 validate.py 生成 analysis contract。

Usage:
    from db_gate import detect_and_fix_unit, validate_row, QualityFinding
    findings = validate_row(row, prev_row)  # → list[QualityFinding]
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QualityFinding:
    """统一质量问题结构。"""
    check_name: str
    severity: str          # BLOCK / WARN / INFO
    scope: str             # field / row / year / stock / cross_source
    message: str
    field_name: str = ""
    ts_code: str = ""
    fiscal_year: int = 0
    observation_id: str = ""
    expected: str = ""
    actual: str = ""

    def to_row(self, batch_id: str = "") -> dict:
        return {
            "finding_id": f"qf_{uuid.uuid4().hex[:12]}",
            "batch_id": batch_id,
            "ts_code": self.ts_code,
            "fiscal_year": self.fiscal_year,
            "field_name": self.field_name,
            "observation_id": self.observation_id,
            "check_name": self.check_name,
            "severity": self.severity,
            "scope": self.scope,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


# ── Layer 1: Unit Detection ──

MONETARY_FIELDS = [
    "revenue", "oper_cost", "n_income_attr_p", "minority_profit",
    "pretax_profit", "income_tax", "d_a",
    "money_cap", "cash_broad", "accounts_receiv", "acct_payable",
    "contract_liab", "total_assets", "total_liab",
    "total_hldr_eqy_exc_min_int", "minority_int", "goodwill",
    "st_borr", "lt_borr",
    "n_cashflow_act", "c_pay_acq_const_fiolta", "fcf", "dividends_paid",
]


def detect_and_fix_unit(row: dict) -> tuple[dict, list[QualityFinding]]:
    """检测并修复单位问题。返回 (fixed_row, findings)."""
    findings = []
    fixed = dict(row)
    ts = row.get("ts_code", "")
    fy = row.get("fiscal_year", 0)

    for field in MONETARY_FIELDS:
        val = fixed.get(field)
        if val is None:
            continue
        if abs(val) > 10_000_000:  # >10M → raw yuan. Large SOEs can have revenue >100K in 百萬元
            old = val
            fixed[field] = val / 1_000_000
            findings.append(QualityFinding(
                check_name="unit_conversion",
                severity="INFO",
                scope="field",
                field_name=field,
                ts_code=ts, fiscal_year=fy,
                message=f"{field}: {old:,.0f} 元 → {fixed[field]:.2f} 百万元",
                expected="百万元",
                actual=f"{old:,.0f} 元",
            ))

    # Field swap: revenue ≈ total_assets
    rev = fixed.get("revenue")
    ta = fixed.get("total_assets")
    if rev and ta and rev > 0 and ta > 0:
        diff_pct = abs(rev - ta) / max(rev, ta)
        if diff_pct < 0.05:
            findings.append(QualityFinding(
                check_name="field_swap",
                severity="BLOCK",
                scope="row",
                field_name="revenue",
                ts_code=ts, fiscal_year=fy,
                message=f"revenue({rev:.1f}) ≈ total_assets({ta:.1f}), diff={diff_pct*100:.1f}%",
                expected="revenue ≠ total_assets",
                actual=f"revenue={rev:.1f}, total_assets={ta:.1f}",
            ))

    # NP ≈ equity swap
    np_val = fixed.get("n_income_attr_p")
    eq = fixed.get("total_hldr_eqy_exc_min_int")
    if np_val and eq and np_val > 0 and eq > 0:
        diff_pct = abs(np_val - eq) / max(np_val, eq)
        if diff_pct < 0.05:
            findings.append(QualityFinding(
                check_name="field_swap",
                severity="BLOCK",
                scope="row",
                field_name="n_income_attr_p",
                ts_code=ts, fiscal_year=fy,
                message=f"NP({np_val:.1f}) ≈ equity({eq:.1f}), diff={diff_pct*100:.1f}%",
                expected="n_income_attr_p ≠ total_hldr_eqy_exc_min_int",
                actual=f"np={np_val:.1f}, equity={eq:.1f}",
            ))

    # Negative values
    for field in ["revenue", "total_assets", "money_cap", "total_hldr_eqy_exc_min_int"]:
        v = fixed.get(field)
        if v is not None and v < 0:
            findings.append(QualityFinding(
                check_name="negative_value",
                severity="BLOCK",
                scope="field",
                field_name=field,
                ts_code=ts, fiscal_year=fy,
                message=f"{field}={v} is negative",
            ))

    return fixed, findings


# ── Layer 2: Business Rules ──

CORE_FIELDS = ["revenue", "n_income_attr_p", "total_assets", "total_hldr_eqy_exc_min_int"]


def validate_row(row: dict, prev_row: Optional[dict] = None) -> list[QualityFinding]:
    """行级业务规则验证。返回 QualityFinding 列表。"""
    findings = []
    ts = row.get("ts_code", "")
    fy = row.get("fiscal_year", 0)

    rev = row.get("revenue")
    np_val = row.get("n_income_attr_p")
    ta = row.get("total_assets")
    eq = row.get("total_hldr_eqy_exc_min_int")
    cash = row.get("money_cap")
    ocf = row.get("n_cashflow_act")
    tl = row.get("total_liab")

    # BLOCK: critical fields NULL
    for f in CORE_FIELDS:
        if row.get(f) is None:
            findings.append(QualityFinding(
                check_name="missing_critical_field",
                severity="BLOCK",
                scope="field",
                field_name=f,
                ts_code=ts, fiscal_year=fy,
                message=f"{f} is NULL",
            ))

    # BLOCK: NP > 1.5× revenue
    if rev and np_val and rev > 0 and abs(np_val) > abs(rev) * 1.5:
        findings.append(QualityFinding(
            check_name="np_vs_revenue",
            severity="BLOCK",
            scope="row",
            field_name="n_income_attr_p",
            ts_code=ts, fiscal_year=fy,
            message=f"NP({np_val:.1f}) > 1.5× revenue({rev:.1f})",
        ))

    # BLOCK: revenue ≈ total_assets (< 3%)
    if rev and ta and rev > 0 and ta > 0:
        diff_pct = abs(rev - ta) / max(rev, ta)
        if diff_pct < 0.03:
            findings.append(QualityFinding(
                check_name="field_swap_rev_assets",
                severity="BLOCK",
                scope="row",
                ts_code=ts, fiscal_year=fy,
                message=f"revenue ≈ total_assets, diff={diff_pct*100:.1f}%",
            ))

    # WARN/BLOCK: BS identity
    if ta and eq and tl and ta > 0:
        mi = row.get("minority_int") or 0
        identity = eq + mi + tl
        imbalance = abs(ta - identity) / ta
        if imbalance > 0.30:
            findings.append(QualityFinding(
                check_name="bs_identity",
                severity="BLOCK",
                scope="row",
                field_name="total_assets",
                ts_code=ts, fiscal_year=fy,
                message=f"A({ta:.1f}) ≠ E({eq:.1f})+MI({mi:.1f})+L({tl:.1f}), diff={imbalance*100:.0f}%",
                expected=f"A ≈ E+MI+L (±30%)",
                actual=f"diff={imbalance*100:.0f}%",
            ))
        elif imbalance > 0.10:
            findings.append(QualityFinding(
                check_name="bs_identity",
                severity="WARN",
                scope="row",
                field_name="total_assets",
                ts_code=ts, fiscal_year=fy,
                message=f"A≠E+MI+L, diff={imbalance*100:.0f}%",
            ))

    # WARN: cash > total_assets
    if ta and cash and ta > 0 and cash > ta:
        findings.append(QualityFinding(
            check_name="cash_vs_assets",
            severity="WARN",
            scope="row",
            field_name="money_cap",
            ts_code=ts, fiscal_year=fy,
            message=f"cash({cash:.1f}) > total_assets({ta:.1f})",
        ))

    # WARN: OCF > 2× revenue
    if rev and ocf and rev > 0 and abs(ocf) > abs(rev) * 2:
        findings.append(QualityFinding(
            check_name="ocf_vs_revenue",
            severity="WARN",
            scope="row",
            field_name="n_cashflow_act",
            ts_code=ts, fiscal_year=fy,
            message=f"OCF({ocf:.1f}) > 2× revenue({rev:.1f})",
        ))

    # WARN: YoY revenue jump > 10x
    if prev_row and rev:
        prev_rev = prev_row.get("revenue")
        if prev_rev and prev_rev > 0:
            jump = abs(rev - prev_rev) / abs(prev_rev)
            if jump > 10:
                findings.append(QualityFinding(
                    check_name="yoy_jump",
                    severity="WARN",
                    scope="year",
                    field_name="revenue",
                    ts_code=ts, fiscal_year=fy,
                    message=f"revenue YoY jump {jump*100:.0f}% ({prev_rev:.1f}→{rev:.1f})",
                ))

    return findings


def validate_stock_level(row: dict, stock_info: dict) -> list[QualityFinding]:
    """标的级检查。"""
    findings = []
    ts = row.get("ts_code", "")
    fy = row.get("fiscal_year", 0)

    # BLOCK: shares_m missing (needed for valuation)
    if not stock_info.get("shares_m"):
        findings.append(QualityFinding(
            check_name="shares_missing",
            severity="BLOCK",
            scope="stock",
            field_name="shares_m",
            ts_code=ts, fiscal_year=fy,
            message="shares_m is NULL — 市值/DDM/仓位计算将失真",
        ))

    return findings


def validate_cross_source(obs_a: dict, obs_b: dict) -> Optional[QualityFinding]:
    """跨源对账：对比同一字段的两个候选值。"""
    field_name = obs_a.get("field_name", "")
    val_a = obs_a.get("normalized_value")
    val_b = obs_b.get("normalized_value")
    if not val_a or not val_b or val_b == 0:
        return None
    diff = abs(val_a - val_b) / abs(val_b)
    severity = "BLOCK" if diff > 0.05 else "WARN" if diff > 0.01 else "INFO"
    return QualityFinding(
        check_name="cross_source",
        severity=severity,
        scope="cross_source",
        field_name=field_name,
        ts_code=obs_a.get("ts_code", ""),
        fiscal_year=obs_a.get("fiscal_year", 0),
        message=f"{field_name}: {obs_a.get('source_type','?')}={val_a:.1f} vs {obs_b.get('source_type','?')}={val_b:.1f}, diff={diff*100:.1f}%",
        expected=f"diff ≤ 5%",
        actual=f"diff={diff*100:.1f}%",
    )
