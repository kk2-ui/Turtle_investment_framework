"""计算工具集 — GG、DDM、护城河、决策。

对接 compute_bundle.json 的 factor2/3/4/params/market 实际结构。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from financial_rigor import (
    benford_check as _benford_check,
    cross_validate as _cross_validate,
    verify_market_cap as _verify_market_cap,
)


def _read_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _load_bundle(output_dir: str) -> dict[str, Any] | None:
    """加载 compute_bundle.json。"""
    return _read_json(os.path.join(output_dir, "compute_bundle.json"))


def _analyze_ap_driven_cashflow(output_dir: str) -> dict[str, Any]:
    """AP 驱动伪现金流拆解：对标 v2.39 AP-Driven AA 检测。

    若应付账款(AP)增速持续超出营业成本增速 → AA 中可能含有靠挤压供应商获得的伪现金流。
    返回：ap_pct（AP驱动占比）、ap_adjusted_aa（剔除AP后的真实AA）。
    """
    result: dict[str, Any] = {"ap_pct": 0, "ap_adjusted_aa": None, "warning": ""}
    try:
        ft = _read_json(os.path.join(output_dir, "financial_trends.json"))
        cb = _load_bundle(output_dir)
        if not ft or not cb:
            return result

        # 提取 AP 和营业成本
        ap_vals = []
        cost_vals = []
        for row in ft.get("balance_sheet", {}).get("rows", []):
            if row.get("field") in ("accounts_payable", "acct_payable"):
                ap_vals = row.get("values", []) or []
        for row in ft.get("income_statement", {}).get("rows", []):
            if row.get("field") == "oper_cost":
                cost_vals = row.get("values", []) or []

        if len(ap_vals) < 3 or len(cost_vals) < 3:
            return result

        # 方法 1: 5 年 AP/Cost 比率趋势（对标 v2.39 DPO 分析）
        # DPO ≈ AP / (Cost/365)。若 DPO 持续拉长且远超行业基准（物管行业 ~60-90 天），则是伪现金流信号。
        ap_cost_ratios = []
        for i in range(min(len(ap_vals), len(cost_vals))):
            if cost_vals[i] and cost_vals[i] > 0:
                ap_cost_ratios.append(ap_vals[i] / cost_vals[i])
        if len(ap_cost_ratios) >= 5:
            ratio_5y_ago = ap_cost_ratios[-5]
            ratio_latest = ap_cost_ratios[-1]
            ratio_increase = ratio_latest - ratio_5y_ago
            dpo_latest = round(ratio_latest * 365, 0)
            # 计算 AP 驱动的伪现金流
            if ratio_increase > 0.02 and cost_vals[-1]:
                normal_ap = cost_vals[-1] * ratio_5y_ago
                excess_ap = ap_vals[-1] - normal_ap
                f3 = cb.get("factor3", {})
                aa_avg_3y = f3.get("aa_avg", {}).get("3y", 0) or 0
                if aa_avg_3y > 0 and excess_ap > 0:
                    # 超额 AP 摊销到每年（假设 3 年累积）
                    annual_excess = excess_ap / 3
                    ap_pct = round(min(annual_excess / aa_avg_3y * 100, 100), 0)
                    ap_adjusted_aa = round(aa_avg_3y - annual_excess, 2)
                    result["ap_pct"] = ap_pct
                    result["ap_adjusted_aa"] = ap_adjusted_aa
                    result["excess_ap_annual"] = round(annual_excess, 2)
                    result["dpo_latest"] = dpo_latest
                    result["dpo_5y_ago"] = round(ratio_5y_ago * 365, 0)
                    result["warning"] = (
                        f"⚠️ DPO从{result['dpo_5y_ago']}天拉长至{dpo_latest}天(物管行业基准~60-90天)。"
                        f"AA中约{ap_pct:.0f}%来自延迟支付供应商（年均{annual_excess:.1f}M）。"
                        f"剔除后真实AA={ap_adjusted_aa}M。"
                        f"GG应从名义值下调约{ap_pct:.0f}%。"
                    )
    except Exception:
        pass
    return result


def _compute_ddm_implied_pe(output_dir: str) -> float | None:
    """计算 DDM 隐含 PE = DDM公允价 / EPS。"""
    try:
        ft = _read_json(os.path.join(output_dir, "financial_trends.json"))
        cb = _load_bundle(output_dir)
        if not ft or not cb:
            return None
        eps = None
        for row in ft.get("income_statement", {}).get("rows", []):
            if row.get("field") == "eps":
                vals = row.get("values", [])
                eps = vals[-1] if vals else None
        ddm_v = cb.get("factor4", {}).get("ddm_v_rmb")
        if eps and eps > 0 and ddm_v:
            return round(ddm_v / eps, 1)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Financial rigor helpers
# ---------------------------------------------------------------------------


def verify_market_cap(
    price: float,
    shares: float,
    reported_cap: float,
    currency: str = "",
) -> dict[str, Any]:
    """验证市值=股价×股本，并返回偏差结果。"""
    calculated = float(price) * float(shares)
    deviation_pct = abs(calculated - float(reported_cap)) / abs(float(reported_cap)) * 100 if float(reported_cap) else 0.0
    ok = _verify_market_cap(price, shares, reported_cap, currency)
    return {
        "price": float(price),
        "shares": float(shares),
        "reported_cap": float(reported_cap),
        "calculated_cap": calculated,
        "deviation_pct": round(deviation_pct, 4),
        "currency": currency,
        "ok": bool(ok),
    }


def cross_validate_data(
    field: str,
    sources_json: str,
    unit: str = "",
    tolerance: float = 2.0,
) -> dict[str, Any]:
    """对同一字段做多源交叉验证。"""
    values = json.loads(sources_json) if isinstance(sources_json, str) else dict(sources_json or {})
    result = _cross_validate(field, values, unit, tolerance)
    result.update({
        "field": field,
        "unit": unit,
        "tolerance_pct": float(tolerance),
        "sources": values,
    })
    return result


def check_benford(values_json: str) -> dict[str, Any]:
    """对一组数字做 Benford 定律检测。"""
    values = json.loads(values_json) if isinstance(values_json, str) else list(values_json or [])
    result = _benford_check(values)
    return result or {
        "mad": None,
        "chi2": None,
        "conformity": "insufficient_sample",
        "is_conforming": None,
        "sample_size": len(values),
    }


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def compute_gg(output_dir: str = ".") -> dict[str, Any]:
    """计算穿透回报率 GG。

    从 compute_bundle.json 提取 factor3 + calculation_trace。

    Args:
        output_dir: 股票输出目录。

    Returns:
        GG 各场景值 + 计算链路。
    """
    cb = _load_bundle(output_dir)
    if not cb:
        return {"error": "compute_bundle.json 不存在"}

    f3 = cb.get("factor3", {})
    p = cb.get("params", {})
    f2 = cb.get("factor2", {})
    m = cb.get("market", {})

    # V12 fix: 检测 yfinance 股本错误，用数据库股本修正 MC
    shares_yf = m.get("shares_m", 0)
    shares_warning = m.get("shares_warning", False)
    mc_rmb_yf = m.get("mc_rmb", 0)
    mc_rmb_corrected = mc_rmb_yf
    correction_note = ""

    if shares_warning and shares_yf > 0:
        try:
            import sqlite3
            # output_dir 是 output/01502_金融街物业, 往上两级到框架根目录
            _framework_dir = os.path.abspath(os.path.join(output_dir, "..", ".."))
            db_path = os.path.join(_framework_dir, "stock_analysis.db")
            if os.path.exists(db_path):
                db = sqlite3.connect(db_path)
                row = db.execute("SELECT shares_m FROM stocks WHERE ts_code LIKE ?", (f"%{os.path.basename(output_dir).split('_')[0]}%",)).fetchone()
                db.close()
                if row and row[0] and row[0] > 0:
                    db_shares = row[0]
                    price_rmb = m.get("price_rmb", 0) or (m.get("price_hkd", 0) or 0) * (m.get("fx", 0.93) or 0.93)
                    mc_rmb_corrected = round(db_shares * price_rmb, 2)
                    correction_note = f"⚠️ yfinance 股本={shares_yf}M(❌), 数据库股本={db_shares}M(✅)。MC已从{mc_rmb_yf}M修正为{mc_rmb_corrected}M RMB"
        except Exception:
            pass

    # V12: M 值自动计算——优先用实际分红数据，fallback 才用行业默认
    m_val = f2.get("M")
    m_source = f2.get("M_source", "unknown")
    m_samples = f2.get("M_samples", 0)

    # 尝试从 financial_trends 获取实际 DPS/EPS 计算真实 M
    m_actual = None
    if "fallback" in str(m_source).lower() or "default" in str(m_source).lower():
        try:
            ft = _read_json(os.path.join(output_dir, "financial_trends.json")) or {}
            dps, eps = None, None
            for row in ft.get("income_statement", {}).get("rows", []):
                if row.get("field") == "dps":
                    dps = (row.get("values", []) or [None])[-1]
                if row.get("field") == "eps":
                    eps = (row.get("values", []) or [None])[-1]
            if dps and eps and eps > 0:
                m_actual = round(dps / eps, 2)
                m_val = m_actual
                m_source = f"computed_from_DPS/EPS={dps}/{eps}"
        except Exception:
            pass

    # V12 fix: 直接从 factor3 读，不依赖 calculation_trace（经常为空）
    gg = f3.get("gg", {})
    gg_base = gg.get("base")
    gg_pessimistic = gg.get("pessimistic")
    gg_optimistic = gg.get("optimistic")

    # 从 compute_bundle 读取因子2/3 原始值
    r_np = f2.get("r_np")
    r_oe = f2.get("r_oe")
    gg_from_bundle = f3.get("gg", {}).get("base")
    gg_available = (
        not f3.get("gg_unavailable", False)
        and isinstance(gg_from_bundle, (int, float))
    )

    if not gg_available:
        return {
            "valuation_status": "UNRESOLVED_VALUATION",
            "gg_status": "UNRESOLVED",
            "gg_base": None,
            "gg_pessimistic": None,
            "gg_optimistic": None,
            "diagnostic_reference": {
                "r_np_pre_tax": r_np,
                "r_oe_pre_tax": r_oe,
                "authority": "DIAGNOSTIC_ONLY_NOT_CANONICAL_GG",
            },
            "II": p.get("II"),
            "reason": str(
                f3.get("gg_unavailable_reason")
                or f3.get("error")
                or "canonical GG input unavailable"
            ),
            "summary": "Canonical GG is unresolved; Factor2 profitability yields remain diagnostic and do not create a price action.",
        }

    # 如果 compute_bundle 用了 yfinance 的错误 MC，手动重算 R(NP)/R(OE)
    if mc_rmb_corrected != mc_rmb_yf and mc_rmb_corrected > 0:
        np_avg = f2.get("np_avg_3y", 0)
        oe_avg = f2.get("oe_avg_3y", 0)
        M_val = f2.get("M", 0.5)
        Q = p.get("Q", 0.1) if isinstance(p.get("Q"), (int, float)) else 0.1
        # 使用与 compute_bundle 一致的公式: R = RawValue × MC_old / MC_new
        # （compute_bundle 的 r_np 已经是 NP/old_MC × M × (1-Q)，只需做 MC 缩放）
        ratio = mc_rmb_yf / mc_rmb_corrected if mc_rmb_yf > 0 else 1.0
        if ratio < 0.95 and np_avg > 0:  # MC 修正超过 5% 才重算
            r_np = round(r_np * ratio, 1) if r_np else round(np_avg * M_val * (1 - Q) / mc_rmb_corrected * 100, 1)
            r_oe = round(r_oe * ratio, 1) if r_oe else round(oe_avg * M_val * (1 - Q) / mc_rmb_corrected * 100, 1)
            gg_base = round((r_np + r_oe) / 2 + f3.get("g_adj", 0), 1)
            correction_note += f"\nGG已重新计算(R(NP)×{ratio:.2f}): R(NP)={r_np}%, R(OE)={r_oe}%, GG={gg_base}%"
    # A missing canonical GG is never reconstructed from Factor2.  Factor2 is
    # a profitability diagnostic with a different economic identity.

    # HH must compare like with like.  Raw NP/MC is pre-distribution and
    # pre-tax, while GG already includes M and (1-Q); comparing those two
    # creates a large but meaningless spread.  Use the penetration return.
    r_np_for_hh = f2.get("r_np_penetration")
    hh_payload = f3.get("hh_deviation") if isinstance(f3.get("hh_deviation"), dict) else {}
    gg_for_hh = hh_payload.get("gg_aa", (f3.get("gg_raw") or {}).get("aa_based", gg_base))
    hh = None
    hh_note = ""
    if r_np_for_hh and gg_for_hh and r_np_for_hh > 0:
        hh = hh_payload.get("deviation")
        hh = round(float(hh), 2) if isinstance(hh, (int, float)) else round(abs(r_np_for_hh - gg_for_hh), 2)
        if hh > 3:
            hh_note = f"⚠️ HH=|R(NP)_penetration-GG|={hh}pct > 3pct → 因子2不适用，因子3为唯一有效穿透回报率"
        elif hh > 1.5:
            hh_note = f"HH=|R(NP)_penetration-GG|={hh}pct > 1.5pct，因子2可信度存疑"
        else:
            hh_note = f"HH=|R(NP)_penetration-GG|={hh}pct ≤ 1.5pct，因子2与因子3一致"

    m_warning = ""

    # mcapex_split 溯源
    mcapex_used = f3.get("mcapex_split_used")
    mcapex_note = f"维持性Capex占比={mcapex_used:.0%}" if mcapex_used is not None else "总Capex=维持性（维持性占比不可用）"

    return {
        # === 原料表（Agent 用来自行组装公式）===
        "ingredients": {
            "NP_avg_3y": {"value": f2.get("np_avg_3y"), "unit": "百万元", "label": "归母净利润(3年均值)"},
            "OE_avg_3y": {"value": f2.get("oe_avg_3y"), "unit": "百万元", "label": "所有者盈余(3年均值)"},
            "AA_avg_3y": {"value": f3.get("aa_avg", {}).get("3y"), "unit": "百万元", "label": "可支配现金FCF(3年均值)"},
            "M": {"value": m_val, "source": m_source, "samples": m_samples, "warning": m_warning, "label": "G系数(支付率)"},
            "Q": {"value": p.get("Q", 0.1), "label": "股息税率"},
            "MC": {"value": mc_rmb_corrected or mc_rmb_yf, "unit": "百万元 RMB", "original_yf": mc_rmb_yf if mc_rmb_corrected != mc_rmb_yf else None, "corrected": mc_rmb_corrected != mc_rmb_yf, "label": "市值"},
            "g_adj": {"value": f3.get("g_adj"), "formula": "g_base×(1-b_penalty)", "g_base": p.get("g_base"), "b_penalty": p.get("b_penalty"), "label": "增长调整"},
            "mcapex_note": mcapex_note,
        },
        # === 因子2 粗算 ===
        "r_np_pre_tax": r_np,
        "r_oe_pre_tax": r_oe,
        # V12.5: 穿透回报率 (Spec Factor2 Step8)
        "r_np_penetration": f2.get("r_np_penetration"),  # NP×M×(1-Q)/MC
        "r_oe_penetration": f2.get("r_oe_penetration"),  # OE×M×(1-Q)/MC
        # === 因子3 精算（原料代入公式的结果）===
        "gg_raw": f3.get("gg_raw", {}),
        "gg_base": gg_base,
        "gg_pessimistic": gg_pessimistic,
        "gg_optimistic": gg_optimistic,
        # V12.5: EV双轨 + λ敏感性 + 外推可信度
        "gg_ev": f3.get("gg_ev"),                        # EV双轨 (净现金/MC>40%触发)
        "gg_normalized": f3.get("gg_normalized"),         # V12.13: 正常化GG (只扣维持Capex)
        "gg_fcfe": f3.get("gg_fcfe"),                     # V12.13: FCFE GG (绕开W倒挤法)
        "lambda_sensitivity": f3.get("lambda_sensitivity"),  # λ=median(ΔAA/ΔS) + 临界收入倍数
        "extrapolation_rating": f3.get("extrapolation_rating"),  # 5维外推可信度评级
        # === 参数 ===
        "II": p.get("II"),
        "Rf": p.get("Rf"),
        "hh": hh,
        "hh_note": hh_note,
        "rejection": f3.get("rejection", {}),
        "correction_note": correction_note,
        "formula": "GG = AA_avg × M × (1-Q) / MC × 100. R(NP)_raw = NP/MC (诊断). R(NP)_penetration = NP×M×(1-Q)/MC (穿透, 与GG同单位)",
        # V12: 隐含PE
        "implied_pe": round(100 / gg_base, 1) if gg_base and gg_base > 0 else None,
        "summary": (
            f"原料: NP={f2.get('np_avg_3y')}M, M={m_val}({m_source}), MC={mc_rmb_corrected or mc_rmb_yf}M, g_adj={f3.get('g_adj')}% → "
            f"GG(base)={gg_base}%, II={p.get('II')}%"
            + (f", 隐含PE={round(100/gg_base,1)}x" if gg_base and gg_base > 0 else "")
            + (f" | {hh_note}" if hh_note else "")
        ),
    }


def compute_aa(output_dir: str = ".") -> dict[str, Any]:
    """展示 AA（可支配现金结余）的完整构建链路。

    从 compute_bundle.json 提取逐年 AA 数据 + 收款比率 + 收入还原，
    供 Agent 在 GG 章节展示计算推导过程。对标海螺水泥报告的 7 步 AA 构建。
    """
    cb = _load_bundle(output_dir)
    if not cb:
        return {"error": "compute_bundle.json 不存在"}

    f3 = cb.get("factor3", {})
    f2 = cb.get("factor2", {})
    p = cb.get("params", {})
    m = cb.get("market", {})

    # AA 逐年数据
    aa = f3.get("aa", {})
    aa_avg = f3.get("aa_avg", {})
    receipt = f3.get("receipt_ratios", {})
    true_rev = f3.get("true_revenue", {})
    raw_income = f3.get("_income_raw", [])

    # AA 趋势分析
    aa_years = sorted(aa.keys())
    aa_values = [aa[y] for y in aa_years]

    return {
        # AA 核心数据
        "aa_annual": aa,                           # 逐年 FCF（可支配现金）
        "aa_avg_3y": aa_avg.get("3y"),             # 近3年均值
        "aa_avg_5y": aa_avg.get("5y"),             # 近5年均值
        "aa_avg_all": aa_avg.get("all"),           # 全部年均值
        "aa_trend": "positive" if all(v > 0 for v in aa_values[-3:]) else ("negative" if all(v < 0 for v in aa_values[-3:]) else "mixed"),
        "aa_last_3y": {y: aa[y] for y in aa_years[-3:]} if len(aa_years) >= 3 else {},

        # 收入还原
        "true_revenue": true_rev,                   # 真实现金收入
        "receipt_ratios": receipt,                  # 收款比率

        # 因子2 参数
        "np_avg_3y": f2.get("np_avg_3y"),
        "np_avg_5y": f2.get("np_avg_5y"),
        "oe_avg_3y": f2.get("oe_avg_3y"),
        "oe_avg_5y": f2.get("oe_avg_5y"),
        "ocf_np_ratio": f2.get("ocf_np_ratio"),
        "M": f2.get("M"),
        "M_source": f2.get("M_source"),

        # 估值参数
        "g_base": f3.get("g_base"),
        "b_penalty": f3.get("b_penalty"),
        "g_adj": f3.get("g_adj"),
        "II": p.get("II"),
        "Rf": p.get("Rf"),
        "Q": p.get("Q"),
        "net_cash": f3.get("net_cash"),
        "net_cash_pct_mc": f3.get("net_cash_pct_mc"),
        # V12.6: 多层现金结构 + W分解
        "cash_structure": f3.get("cash_structure"),
        "w_breakdown": f3.get("w_breakdown"),

        # AP 检查
        "ap_cost_ratio_avg": f3.get("ap_cost_ratio_avg"),
        "ap_excess_financing": f3.get("ap_excess_financing"),

        # GG 公式提示
        # V12: AP 驱动伪现金流拆解（对标 v2.39 AP-Driven AA 检测）
        "ap_driven_analysis": _analyze_ap_driven_cashflow(output_dir),
        "gg_formula": "GG = AA_avg × M × (1-Q) / MC_rmb × 100",
        "gg_note": "此工具输出 AA 构建的中间数据。用 compute_gg 获取最终 GG 值（含股本修正）。若 ap_driven_analysis.ap_pct > 20%，应考虑使用 ap_adjusted_aa 计算保守 GG。",
    }


def compute_ddm(output_dir: str = ".") -> dict[str, Any]:
    """计算 DDM 估值。

    从 compute_bundle.json 提取 factor4 + market。

    Args:
        output_dir: 股票输出目录。

    Returns:
        DDM 公允价 + Tiers + 安全边际。
    """
    cb = _load_bundle(output_dir)
    if not cb:
        return {"error": "compute_bundle.json 不存在"}

    f4 = cb.get("factor4", {})
    p = cb.get("params", {})
    m = cb.get("market", {})
    trace = cb.get("calculation_trace", {})

    ddm = trace.get("factor4_ddm", {})
    tiers = f4.get("tiers", [])

    return {
        "valuation_status": f4.get("valuation_status", "RESOLVED"),
        "price_action_authorized": f4.get("valuation_status") != "UNRESOLVED_VALUATION",
        "ddm_price_hkd": f4.get("ddm_v_hkd"),
        "ddm_price_rmb": f4.get("ddm_v_rmb"),
        "current_price_hkd": m.get("price_hkd"),
        "current_price_rmb": m.get("price_rmb"),
        "upside_pct": tiers[0].get("upside_pct") if tiers else None,
        "dps_fy": p.get("dps_fy"),
        "dps_ttm": p.get("dps_ttm"),
        "dividend_identity": f4.get("dividend_identity"),
        "formula": ddm.get("formula"),
        "steps": ddm.get("steps"),
        "tiers": [
            {
                "stars": t.get("star"),
                "ddm_hkd": t.get("price_hkd"),
                "upside_pct": t.get("upside_pct"),
            }
            for t in tiers[:5]
        ],
        # V12.5: P_base 目标价 (Spec Factor4 Step4) + II 周期调整
        "p_base": f4.get("p_base"),                # P_base = MC×(GG/II)/shares
        "II_original": f4.get("II_original"),       # 原始II
        "II_adjusted": f4.get("II_adjusted"),       # 周期调整后II
        "cycle_adjustment": f4.get("cycle_adjustment"),  # 周期调整说明
        "position": f4.get("position"),
        "stop_loss": f4.get("stop_loss"),
        "value_trap": f4.get("value_trap"),
        "rejection": f4.get("rejection", {}),
        "implied_pe": _compute_ddm_implied_pe(output_dir),
        "summary": (
            f"DDM公允价={f4.get('ddm_v_hkd', '?')} HKD, "
            f"当前价={m.get('price_hkd', '?')} HKD, "
            f"安全边际={tiers[0].get('upside_pct', '?') if tiers else '?'}%"
        ),
    }


def assess_moat(output_dir: str = ".") -> dict[str, Any]:
    """获取护城河评级与 B 类惩罚分析。

    从 Zone J moat_assessment.json 提取。

    Args:
        output_dir: 股票输出目录。

    Returns:
        ``{moat_evidence, b_penalty, g_base, value_trap_signals}``。
    """
    ma = _read_json(os.path.join(output_dir, "moat_assessment.json"))
    if not ma or ma.get("_missing") or not ma.get("moat_evidence"):
        # 回退：从 compute_bundle 和 financial_trends 提取参考指标
        cb = _load_bundle(output_dir) or {}
        ft = _read_json(os.path.join(output_dir, "financial_trends.json")) or {}
        f2 = cb.get("factor2", {})
        return {
            "moat_rating": "unknown",
            "note": "护城河评级应由 Agent 基于定性分析（Ch1-Ch9）综合判断，而非机械规则。以下为参考指标。",
            "indicators": {
                "roe": ft.get("summary", {}).get("latest_roe"),
                "gross_margin": ft.get("summary", {}).get("latest_gross_margin"),
                "ocf_np_ratio": f2.get("ocf_np_ratio") if isinstance(f2, dict) else None,
                "capex_ratio": f2.get("capex_ratio_avg") if isinstance(f2, dict) else None,
                "M": f2.get("M") if isinstance(f2, dict) else None,
            },
        }

    return {
        "moat_evidence": ma.get("moat_evidence", []),
        "b_class_segments": ma.get("b_class_segments", []),
        "b_penalty_final": ma.get("b_penalty_final", {}),
        "g_base": ma.get("g_base", {}),
        "g_scenarios": ma.get("g_scenarios", {}),
        "value_trap_signals": ma.get("value_trap_signals", []),
        "summary": (
            f"护城河证据: {len(ma.get('moat_evidence', []))} 项, "
            f"B惩罚: {ma.get('b_penalty_final', {}).get('value', '?')}, "
            f"G_base: {ma.get('g_base', {}).get('value', '?')}%, "
            f"Value Trap信号: {len(ma.get('value_trap_signals', []))} 项"
        ),
    }


def assess_moat_fallback(output_dir: str = ".") -> dict[str, Any]:
    """护城河回退评估（从 compute_bundle 质量指标推断）。"""
    cb = _load_bundle(output_dir)
    if not cb:
        return {"error": "无护城河数据"}

    f2 = cb.get("factor2", {})
    oe = f2.get("oe_avg_3y", 0)
    ocf_np = f2.get("ocf_np_ratio", 0)
    m_val = f2.get("M", 0)

    if oe > 100 and ocf_np > 1.0 and m_val > 0.5:
        rating = "Wide" if oe > 300 else "Narrow"
    else:
        rating = "None"

    return {
        "moat_rating": rating,
        "moat_type": f"OE={oe}% OCF/NP={ocf_np} M={m_val}",
        "evidence": [f"OE_avg_3y={oe}%", f"OCF/NP={ocf_np}", f"M乘数={m_val}"],
        "summary": f"护城河: {rating}",
    }


def evaluate_decision(output_dir: str = ".") -> dict[str, Any]:
    """综合评估投资决策 (Continue/Hold/Abandon)。

    基于规则：GG vs II + 否决门状态。

    Args:
        output_dir: 股票输出目录。

    Returns:
        ``{verdict, confidence, rationale, triggers}``。
    """
    cb = _load_bundle(output_dir)
    if not cb:
        return {"error": "compute_bundle.json 不存在"}

    p = cb.get("params", {})
    f3 = cb.get("factor3", {})
    f4 = cb.get("factor4", {})
    m = cb.get("market", {})
    rej = cb.get("rejection_summary", {})
    trace = cb.get("calculation_trace", {})

    gg_final = f3.get("gg", {}).get("base")  # canonical Factor3 identity only
    valuation_unresolved = (
        f4.get("valuation_status") == "UNRESOLVED_VALUATION"
        or f3.get("gg_unavailable", False)
        or not isinstance(gg_final, (int, float))
    )
    ii = p.get("II", 0)
    rejected = rej.get("overall") == "block"

    tiers = f4.get("tiers", [])
    upside = tiers[0].get("upside_pct", 0) if tiers else 0
    v_trap = f4.get("value_trap", {})

    # 规则决策
    if valuation_unresolved:
        verdict, confidence = "Unresolved", "bounded"
        rationale = [
            "核心估值或当前价格输入不可用；企业经营判断继续，但当前价格动作与仓位暂不承保。"
        ]
    elif rejected:
        verdict, confidence = "Abandon", "high"
        rationale = ["否决门触发: " + ", ".join(rej.get("blocks", []))]
    elif gg_final < ii * 0.5:
        verdict, confidence = "Abandon", "high"
        rationale = [f"GG({gg_final}%) < II×0.5({ii*0.5:.1f}%)"]
    elif gg_final > ii:
        if upside >= 30 and not v_trap.get("exclude", False):
            verdict, confidence = "Continue", "high"
        else:
            verdict, confidence = "Continue", "medium"
        rationale = [
            f"GG({gg_final}%) > II({ii}%)",
            f"DDM upside={upside}%",
            f"Value Trap={'排除' if v_trap.get('exclude') else '不排除'}",
        ]
    else:
        verdict, confidence = "Hold", "medium"
        rationale = [f"GG({gg_final}%) 接近 II({ii}%)"]

    result = {
        "verdict": verdict,
        "valuation_status": "UNRESOLVED_VALUATION" if valuation_unresolved else "RESOLVED",
        "position_pct": None if valuation_unresolved else f4.get("position", {}).get("capped_pct"),
        "confidence": confidence,
        "rationale": rationale,
        "gg": gg_final,
        "ii": ii,
        "upside_pct": upside,
        "rejection": rej,
        "value_trap": v_trap.get("exclude", False),
        "current_price": m.get("price_hkd"),
        "ddm_price": f4.get("ddm_v_hkd"),
    }

    # V12: 事后一致性验证（来自 decision_synthesizer.validate_decision）
    try:
        if valuation_unresolved:
            return result
        from scripts.decision_synthesizer import validate_decision as _vd
        from scripts.models import DecisionInput, DecisionOutput
        di = DecisionInput(
            company_name=cb.get("meta", {}).get("company_name", ""),
            ts_code=cb.get("meta", {}).get("ts_code", ""),
            factor_2_gg=cb.get("factor2", {}).get("r_np", 0),
            factor_3_gg=gg_final,
            factor_4_ddm_v=f4.get("ddm_v_hkd", 0),
            factor_4_current_price=m.get("price_hkd", 0),
            ii=ii,
            rejection_status="block" if rejected else "pass",
        )
        do = DecisionOutput(verdict=verdict, confidence=confidence, rationale=rationale)
        warnings = _vd(do, di)
        if warnings:
            result["consistency_warnings"] = warnings
    except Exception:
        pass

    return result


# 元数据
def compute_data_quality(output_dir: str = ".") -> dict[str, Any]:
    """评估数据完整性，不从文件数量推导估值方向。

    检查 stock_dir 下所有 Zone A/B/J JSON 的字段覆盖率，
    输出完整性得分和局部置信度处理。经济折价必须由观察到的
    owner-cash/永久损失载体另行支持。
    """
    expected_files = {
        "Zone A": ["compute_bundle.json", "financial_trends.json", "industry_context.json"],
        "Zone B": ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"],
        "Zone J": ["moat_assessment.json", "capex_classification.json", "earnings_quality.json", "data_discount.json"],
    }
    result = {"ok": True, "categories": {}, "total_present": 0, "total_expected": 0}

    for category, files in expected_files.items():
        present = 0
        missing = []
        for f in files:
            path = os.path.join(output_dir, f)
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = json.load(fh)
                    # 粗略字段计数
                    field_count = len(data) if isinstance(data, dict) else 1
                    present += 1
                except Exception:
                    missing.append(f)
            else:
                missing.append(f)
        total = len(files)
        result["categories"][category] = {
            "present": present,
            "total": total,
            "score": f"{present}/{total}",
            "missing": missing,
        }
        result["total_present"] += present
        result["total_expected"] += total

    pct = result["total_present"] / result["total_expected"] * 100 if result["total_expected"] > 0 else 0
    missing_count = result["total_expected"] - result["total_present"]
    if missing_count:
        confidence_treatment = (
            "逐项定位缺失文件影响的主张；降低该主张置信度，必要时扩大对应估值区间或取消未证明溢价。"
            "缺失没有先验方向，不自动降低估值中枢。"
        )
    else:
        confidence_treatment = (
            "文件层覆盖完整；仍按事实质量和经济机制判断，不因完整性本身增加估值溢价。"
        )

    result["completeness_pct"] = round(pct, 1)
    # Retain the legacy field name for consumers, but make its semantics
    # explicit: completeness alone never supplies an economic haircut.
    result["automatic_discount_pct"] = 0.0
    result["discount_recommendation"] = "0% automatic point-estimate adjustment"
    result["confidence_treatment"] = confidence_treatment
    result["summary"] = (
        f"数据完整性={result['total_present']}/{result['total_expected']}文件({pct:.0f}%)，"
        f"缺失={missing_count}；估值中枢自动折价=0%，局部置信度处理={confidence_treatment}"
    )
    return result


verify_market_cap._tool_meta = {"name": "verify_market_cap", "description": "验证市值=股价×总股本，并返回偏差百分比。", "parameters": {"price": {"type": "number", "description": "股价"}, "shares": {"type": "number", "description": "总股本"}, "reported_cap": {"type": "number", "description": "报告或行情给出的市值"}, "currency": {"type": "string", "description": "币种", "optional": True}}}  # type: ignore[attr-defined]
cross_validate_data._tool_meta = {"name": "cross_validate_data", "description": "对同一财务字段做多源交叉验证并输出共识值。", "parameters": {"field": {"type": "string", "description": "字段名"}, "sources_json": {"type": "string", "description": "JSON: {来源: 数值}"}, "unit": {"type": "string", "description": "单位", "optional": True}, "tolerance": {"type": "number", "description": "容差百分比", "optional": True}}}  # type: ignore[attr-defined]
check_benford._tool_meta = {"name": "check_benford", "description": "对一组财务数字做 Benford 定律检测。", "parameters": {"values_json": {"type": "string", "description": "JSON数组"}}}  # type: ignore[attr-defined]
compute_aa._tool_meta = {"name": "compute_aa", "description": "展示AA(可支配现金)完整构建链路—逐年FCF+收款比率+收入还原。用于GG章节推导过程。", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
compute_data_quality._tool_meta = {"name": "compute_data_quality", "description": "评估数据完整性—统计Zone A/B/J文件覆盖率并给出局部置信度处理；文件缺失不自动产生估值折价。", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
compute_gg._tool_meta = {"name": "compute_gg", "description": "计算穿透回报率GG(GG_np/GG_oe/GG_base/II/Rf/G_adj/scenarios)—含yfinance股本自动修正", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
compute_ddm._tool_meta = {"name": "compute_ddm", "description": "计算DDM估值(公允价/tiers/安全边际/止损)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
assess_moat._tool_meta = {"name": "assess_moat", "description": "护城河评级(从moat_assessment或compute_bundle推断)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
evaluate_decision._tool_meta = {"name": "evaluate_decision", "description": "综合评估投资决策(Continue/Hold/Abandon)基于GG vs II + 否决门", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
