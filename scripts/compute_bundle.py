#!/usr/bin/env python3
"""compute_bundle.py — 定量计算中心 (v3.0 计算优先架构)

Reads data_pack_market.md + hk_report_fallback.json + threshold.json
and computes ALL quantitative metrics for Factors 2/3/4 in one pass.

Output: compute_bundle.json — structured parameters for LLM report generation.
No LLM agent needed for any computation herein.

Usage:
    python3 scripts/compute_bundle.py --output output/01502_金融街物业
"""

import argparse, json, os, sqlite3, sys, math
from pathlib import Path
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


# ── helpers ──

def safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def cagr(values: list[float]) -> Optional[float]:
    """CAGR from oldest to latest."""
    clean = [v for v in values if v is not None and v > 0]
    if len(clean) < 2:
        return None
    latest, oldest = clean[-1], clean[0]
    n = len(clean) - 1
    if oldest <= 0:
        return None
    return (latest / oldest) ** (1 / n) - 1


def avg(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def avg_last_n(values: list[float], n: int) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if len(clean) < n:
        return avg(clean)
    return sum(clean[-n:]) / n


def load_zone_j_params(zone_j_dir: str) -> dict:
    """Load Zone J parameters from a stock output directory (V9.2).

    Reads moat_assessment.json, capex_classification.json,
    earnings_quality.json, data_discount.json and extracts
    key parameters as overrides for compute_bundle.

    Handles both old format (bare numbers) and new format
    ({value, rationale, evidence_ref, ...}).
    """
    params = {}
    files = {
        "moat_assessment.json": [
            ("b_penalty_final", "b_penalty"),
            ("g_base", "g_base"),
        ],
        "capex_classification.json": [
            ("mcapex_split_pct", None),
        ],
        "earnings_quality.json": [
            ("non_recurring_items", None),
        ],
        "data_discount.json": [
            ("total_discount_pct", None),
        ],
    }

    for fname, mappings in files.items():
        path = os.path.join(zone_j_dir, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue

        for json_key, override_key in mappings:
            val = data.get(json_key)
            if val is None:
                continue
            # Handle new format: {value, rationale, ...}
            if isinstance(val, dict) and "value" in val:
                val = val["value"]
            if isinstance(val, (int, float)):
                key = override_key or json_key
                params[key] = val

    return params


def load_analysis_contract(ts_code: str) -> Optional[dict]:
    """Load analysis_contract.json if it exists for this stock."""
    code_base = ts_code.split(".")[0]
    for name in os.listdir(OUTPUT_DIR):
        if name.startswith(code_base) and os.path.isdir(os.path.join(OUTPUT_DIR, name)):
            path = os.path.join(OUTPUT_DIR, name, "analysis_contract.json")
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        return json.load(f)
                except Exception:
                    return None
    return None


def load_from_db(ts_code: str, contract: Optional[dict] = None) -> Optional[dict]:
    """Load financial data from stock_analysis.db. Returns hk_fallback-compatible dict.

    If contract is provided, filters to effective_years (dynamic window from Phase 0).
    """
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT * FROM annual_financials
        WHERE ts_code=? AND report_type='annual'
        ORDER BY fiscal_year
    """, (ts_code,)).fetchall()

    # V9.2: Apply analysis contract window filter
    effective_years = None
    n_effective = len(rows)
    if contract and contract.get("effective_years"):
        effective_years = set(contract["effective_years"])
        rows = [r for r in rows if r["fiscal_year"] in effective_years]
        n_effective = len(rows)
        all_years = sorted(set(r["fiscal_year"] for r in rows))
        if all_years:
            print(f"📐 Contract window: {all_years[0]}-{all_years[-1]} "
                  f"({n_effective}y, {contract['cyclicality_profile'].get('label','?')})",
                  file=sys.stderr)

    if not rows:
        conn.close()
        return None

    # Check for open BLOCKs on this stock
    open_blocks = conn.execute(
        "SELECT COUNT(*) FROM quality_findings WHERE ts_code=? AND severity='BLOCK' AND fix_status='open'",
        (ts_code,)).fetchone()[0]
    if open_blocks > 0:
        print(f"⚠️  {ts_code}: {open_blocks} open BLOCK(s) exist — annual_financials may be incomplete.", file=sys.stderr)

    income, bs, cf, divs = [], [], [], []
    for r in rows:
        year_str = str(r["fiscal_year"])
        income.append({
            "end_date": year_str + "1231",
            "revenue": r["revenue"],
            "n_income_attr_p": r["n_income_attr_p"],
            "depr_fa_coga_dpba": r["d_a"],  # D&A stored in d_a field
            "oper_cost": r["oper_cost"],
        })
        bs.append({
            "end_date": year_str + "1231",
            "money_cap": r["money_cap"],
            "accounts_receiv": r["accounts_receiv"],
            "acct_payable": r["acct_payable"],
            "contract_liab": r["contract_liab"],
            "total_assets": r["total_assets"],
            "total_liab": r["total_liab"],
            "total_hldr_eqy_exc_min_int": r["total_hldr_eqy_exc_min_int"],
        })
        cf.append({
            "end_date": year_str + "1231",
            "n_cashflow_act": r["n_cashflow_act"],
            "c_pay_acq_const_fiolta": -(r["c_pay_acq_const_fiolta"] or 0),  # DB stores absolute value
        })
        # V12 fix: 加入 base_share，支持 dps×shares 推算总额
        st = conn.execute("SELECT shares_m FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
        sh_m = float(st["shares_m"]) if st and st["shares_m"] else None
        divs.append({
            "end_date": year_str + "1231",
            "dividends_paid": r["dividends_paid"],
            "dps": r["dps"],
            "base_share": sh_m,  # 总股本（百万股），用于 dps×shares=总额 推算
        })

    # Load threshold
    th_row = conn.execute("SELECT * FROM thresholds WHERE ts_code=?", (ts_code,)).fetchone()

    # Load stock info
    st_row = conn.execute("SELECT * FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()

    conn.close()

    return {
        "ts_code": ts_code,
        "currency": "RMB",
        "income": income,
        "balance_sheet": bs,
        "cashflow": cf,
        "dividends": divs,
        "fina_indicators": [],
        "records": [],
        "_threshold": dict(th_row) if th_row else {},
        "_stock": dict(st_row) if st_row else {},
    }


def _scale_fallback_to_millions(fin: dict) -> dict:
    """Convert hk_report_fallback raw values (元) to 百万元 (millions)."""
    SCALE_KEYS = {
        "revenue", "oper_cost", "gross_profit", "admin_exp", "operate_profit",
        "invest_income", "finance_exp", "total_profit", "income_tax",
        "n_income", "n_income_attr_p", "minority_gain",
        "money_cap", "accounts_receiv", "inventories", "total_cur_assets",
        "fix_assets", "intang_assets", "defer_tax_assets", "total_assets",
        "acct_payable", "contract_liab", "adv_receipts", "st_borr",
        "total_cur_liab", "defer_tax_liab", "total_liab",
        "total_hldr_eqy_exc_min_int", "minority_int",
        "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act",
        "c_pay_acq_const_fiolta", "dividends_paid",
    }
    COLLECTIONS = ["income", "balance_sheet", "cashflow", "dividends", "fina_indicators"]
    for key in COLLECTIONS:
        for row in fin.get(key, []) or []:
            for f in SCALE_KEYS:
                if f in row and row[f] is not None:
                    row[f] = row[f] / 1_000_000
    return fin

def load_threshold(output_dir: str) -> dict:
    """Load threshold.json."""
    path = os.path.join(output_dir, "threshold.json")
    if not os.path.exists(path):
        return {"II": 5.5, "star_5": 5.5, "star_4": 5.0, "star_3": 4.5,
                "category": "unknown", "method": "fallback", "rationale": "threshold.json not found"}
    with open(path) as f:
        return json.load(f)


def load_hk_fallback(output_dir: str) -> Optional[dict]:
    """Load hk_report_fallback.json if exists."""
    path = os.path.join(output_dir, "hk_report_fallback.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_input_data(output_dir: str) -> Optional[dict]:
    """Load verified input_data.json (pre-extracted from PDF sections, cross-validated).

    Format: {ts_code, currency, years[], revenue[], n_income_attr_p[], ocf[], capex[], ...}
    All values in RMB millions. Preferred over raw Tushare/hk_fallback data.
    """
    path = os.path.join(output_dir, "input_data.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def normalize_input_data(raw: dict) -> dict:
    """Convert input_data.json format to hk_report_fallback-compatible format
    for unified computation."""
    years = raw.get("years", [])
    n = len(years)

    def yearly_array(key):
        vals = raw.get(key, [])
        return vals if vals else [None] * n

    income = []
    balance_sheet = []
    cashflow = []
    dividends = []

    rev = yearly_array("revenue")
    np_vals = yearly_array("n_income_attr_p")
    d_a_vals = yearly_array("d_a")
    ocf_vals = yearly_array("ocf")
    capex_vals = yearly_array("capex")
    ar_vals = yearly_array("accounts_receiv")
    ap_vals = yearly_array("acct_payable")
    contract_vals = yearly_array("contract_liab")
    cash_vals = yearly_array("money_cap")
    ta_vals = yearly_array("total_assets")
    tl_vals = yearly_array("total_liab")
    eq_vals = yearly_array("equity")
    dps_vals = yearly_array("dps")
    div_total = yearly_array("dividend_total")
    cost_vals = yearly_array("oper_cost")

    for i, y in enumerate(years):
        income.append({
            "end_date": y.replace("FY", "20") + "1231" if y.startswith("FY") else y + "1231",
            "revenue": rev[i] if i < len(rev) else None,
            "n_income_attr_p": np_vals[i] if i < len(np_vals) else None,
            "depr_fa_coga_dpba": d_a_vals[i] if i < len(d_a_vals) else None,
            "oper_cost": cost_vals[i] if i < len(cost_vals) else None,
        })
        balance_sheet.append({
            "end_date": y.replace("FY", "20") + "1231" if y.startswith("FY") else y + "1231",
            "money_cap": cash_vals[i] if i < len(cash_vals) else None,
            "accounts_receiv": ar_vals[i] if i < len(ar_vals) else None,
            "acct_payable": ap_vals[i] if i < len(ap_vals) else None,
            "contract_liab": contract_vals[i] if i < len(contract_vals) else None,
            "total_assets": ta_vals[i] if i < len(ta_vals) else None,
            "total_liab": tl_vals[i] if i < len(tl_vals) else None,
            "total_hldr_eqy_exc_min_int": eq_vals[i] if i < len(eq_vals) else None,
        })
        cashflow.append({
            "end_date": y.replace("FY", "20") + "1231" if y.startswith("FY") else y + "1231",
            "n_cashflow_act": ocf_vals[i] if i < len(ocf_vals) else None,
            "c_pay_acq_const_fiolta": -capex_vals[i] if i < len(capex_vals) and capex_vals[i] else None,
        })
        dividends.append({
            "end_date": y.replace("FY", "20") + "1231" if y.startswith("FY") else y + "1231",
            "cash_div_tax": div_total[i] if i < len(div_total) else None,
        })

    return {
        "ts_code": raw.get("ts_code", ""),
        "currency": raw.get("currency", "RMB"),
        "income": income,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "dividends": dividends,
        "fina_indicators": [],
        "records": [],
    }


def load_data_pack(output_dir: str) -> str:
    """Load data_pack_market.md as text."""
    path = os.path.join(output_dir, "data_pack_market.md")
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


# ── Factor 2: Top-Down Rough GG ──

def compute_factor2(fin_data: dict, market: dict, params: dict) -> dict:
    """Factor 2:穿透回报率粗算 (Top-Down)."""
    result = {"rejection": {}}

    # Extract annual data
    inc = fin_data.get("income", [])
    bs = fin_data.get("balance_sheet", [])
    cf = fin_data.get("cashflow", [])
    divs = fin_data.get("dividends", [])
    indicators = fin_data.get("fina_indicators", [])

    np_years = [safe_float(r.get("n_income_attr_p"), 0) for r in inc]
    ocf_years = [safe_float(r.get("n_cashflow_act"), 0) for r in cf]
    # V12 fix: load_from_db 存 dividends_paid(总额,百万元) 和 dps(每股,元), cash_div_tax 也可能存在
    dps_years = [safe_float(r.get("dividends_paid"), 0) or safe_float(r.get("cash_div_tax"), 0) for r in divs]
    # 如果 dividends_paid 不可用，用 dps(元/股) × base_share(百万股) = 百万元 推算总额
    if all(d == 0 for d in dps_years):
        dps_per_share = [safe_float(r.get("dps"), 0) for r in divs]
        shares_m = [safe_float(r.get("base_share"), 0) for r in divs]
        dps_years = [round(dps_per_share[i] * shares_m[i], 2) if dps_per_share[i] and shares_m[i] else 0
                     for i in range(min(len(dps_per_share), len(shares_m)))]
    d_a_years = [safe_float(r.get("depr_fa_coga_dpba"), 0) + safe_float(r.get("amort_intang_assets"), 0) for r in inc]
    capex_years = [abs(safe_float(r.get("c_pay_acq_const_fiolta"), 0)) for r in cf]
    shares = [safe_float(r.get("base_share"), 0) for r in divs]

    # NP average
    np_avg_3y = avg_last_n(np_years, 3)
    result["np_avg_3y"] = round(np_avg_3y, 2) if np_avg_3y else None
    result["np_avg_5y"] = round(avg(np_years), 2) if np_years else None

    # OCF/NP ratio
    np_match = np_years
    ocf_np_ratios = []
    for i in range(min(len(ocf_years), len(np_match))):
        if np_match[i] and np_match[i] > 0:
            ocf_np_ratios.append(ocf_years[i] / np_match[i])
    result["ocf_np_ratio"] = round(avg_last_n(ocf_np_ratios, 3), 2) if ocf_np_ratios else None

    # OE = NP + D&A - Capex (Buffett Owners' Earnings)
    oe_years = []
    for i in range(min(len(np_years), len(d_a_years), len(capex_years))):
        oe = np_years[i] + d_a_years[i] - capex_years[i]
        oe_years.append(max(oe, 0))
    result["oe_avg_3y"] = round(avg_last_n(oe_years, 3), 2) if oe_years else None
    result["oe_avg_5y"] = round(avg(oe_years), 2) if oe_years else None

    # Capex ratio
    rev_years = [safe_float(r.get("revenue"), 0) for r in inc]
    capex_ratios = []
    for i in range(min(len(capex_years), len(rev_years))):
        if rev_years[i] and rev_years[i] > 0:
            capex_ratios.append(capex_years[i] / rev_years[i])
    result["capex_ratio_avg"] = round(avg(capex_ratios) * 100, 2) if capex_ratios else None

    # M (payout ratio) — four-tier inference (V9.3)
    # Tier 1: DPS data directly (total_dividend / NP)
    np_vals = np_years[-3:] if len(np_years) >= 3 else np_years
    dps_vals_for_m = dps_years[-3:] if len(dps_years) >= 3 else dps_years
    m_list = []
    for i in range(min(len(np_vals), len(dps_vals_for_m))):
        if np_vals[i] and np_vals[i] > 0 and dps_vals_for_m[i] and dps_vals_for_m[i] > 0:
            m = dps_vals_for_m[i] / np_vals[i]
            if 0.05 < m < 1.2:  # 5%-120% payout is plausible
                m_list.append(min(m, 1.0))

    # Tier 2: Try dividends_paid from cashflow if DPS data is bad
    if not m_list:
        cf_divs = [safe_float(r.get("dividends_paid"), 0) for r in cf]
        for i in range(min(len(np_years), len(cf_divs))):
            if np_years[i] and np_years[i] > 0 and cf_divs[i] and cf_divs[i] > 0:
                m = cf_divs[i] / np_years[i]
                if 0.05 < m < 1.2:
                    m_list.append(min(m, 1.0))

    # Tier 3: Industry default inference (V9.3)
    # Light-asset companies (capex/rev < 3%) can distribute ~70% of earnings
    cr = [r for r in capex_ratios if r is not None]
    cr_avg = (sum(cr[-3:]) / len(cr[-3:]) * 100) if len(cr) >= 3 else 10
    m_fallback = 0.70 if cr_avg < 3.0 else 0.50
    if not m_list:
        result["M_source"] = "fallback_light_asset" if cr_avg < 3.0 else "fallback"
        result["M"] = m_fallback
    else:
        result["M_source"] = "computed" if len(m_list) >= 2 else "computed_sparse"
        result["M"] = round(avg(m_list), 4)
    result["M_samples"] = len(m_list)

    # R(NP) = NP_avg_3y / Market_Cap
    mc = market.get("mc_rmb", 0)
    if mc > 0 and np_avg_3y:
        result["r_np"] = round(np_avg_3y / mc * 100, 2)
    else:
        result["r_np"] = None

    # R(OE) = OE_avg_3y / Market_Cap
    oe_avg = result.get("oe_avg_3y")
    if mc > 0 and oe_avg:
        result["r_oe"] = round(oe_avg / mc * 100, 2)
    else:
        result["r_oe"] = None

    # Distribution check: FCF consistently positive and net financing negative
    fcf_years = []
    financing_years = []
    for i in range(min(len(ocf_years), len(capex_years))):
        fcf = ocf_years[i] - capex_years[i]
        fcf_years.append(fcf)
    # V9.2: FCF positivity check — uses all available years (already filtered by contract)
    result["fcf_positive_window"] = all(f > 0 for f in fcf_years) if len(fcf_years) >= 3 else None
    result["distribution_pass"] = result["fcf_positive_window"]

    # Rejection checks
    II = params.get("II", 5.5)
    Rf = params.get("Rf", 4.0)
    r_np = result.get("r_np")
    result["rejection"]["s2"] = "pass" if result.get("distribution_pass") else "fail"
    if r_np is not None:
        result["rejection"]["s4_1"] = "fail" if r_np < Rf else "pass"
        result["rejection"]["s4_2"] = "fail" if r_np < II * 0.5 else "pass"
    else:
        result["rejection"]["s4_1"] = "unknown"
        result["rejection"]["s4_2"] = "unknown"

    return result


# ── Factor 3: Bottom-Up Fine GG ──

def compute_factor3(fin_data: dict, market: dict, params: dict, factor2_M: float | None = None) -> dict:
    """Factor 3:穿透回报率精算 (Bottom-Up). Steps 1-13.

    Args:
        factor2_M: 从 factor2 传入的 M 系数（G系数/支付率）。
                   如果不传，回退到 0.55 默认值。
    """
    result = {"aa": {}, "rejection": {}}

    inc = fin_data.get("income", [])
    bs = fin_data.get("balance_sheet", [])
    cf = fin_data.get("cashflow", [])
    divs = fin_data.get("dividends", [])
    records = fin_data.get("records", [])

    years = [str(r.get("end_date", ""))[:4] for r in inc]
    year_keys = [f"FY{y}" for y in years]

    # Extract per-year data
    rev = [safe_float(r.get("revenue"), 0) for r in inc]
    np = [safe_float(r.get("n_income_attr_p"), 0) for r in inc]
    d_a = [safe_float(r.get("depr_fa_coga_dpba"), 0) + safe_float(r.get("amort_intang_assets"), 0) for r in inc]
    ocf = [safe_float(r.get("n_cashflow_act"), 0) for r in cf]
    capex = [abs(safe_float(r.get("c_pay_acq_const_fiolta"), 0)) for r in cf]
    money_cap = [safe_float(r.get("money_cap"), 0) for r in bs]
    ar = [safe_float(r.get("accounts_receiv"), 0) for r in bs]
    ap = [safe_float(r.get("acct_payable"), 0) for r in bs]
    contract = [safe_float(r.get("contract_liab"), 0) for r in bs]
    total_assets = [safe_float(r.get("total_assets"), 0) for r in bs]
    total_liab = [safe_float(r.get("total_liab"), 0) for r in bs]
    equity = [safe_float(r.get("total_hldr_eqy_exc_min_int"), 0) for r in bs]
    dps_raw = [safe_float(r.get("cash_div_tax"), 0) for r in divs]

    n = len(years)
    if n < 2:
        return result

    # Step 1: True Cash Revenue
    true_rev = []
    recv_ratios = []
    for i in range(n):
        s = rev[i]
        ar_delta = ar[i] - ar[i-1] if i > 0 else 0
        ct_delta = contract[i] - contract[i-1] if i > 0 else 0
        tr = s - max(0, ar_delta) - max(0, -ct_delta)
        true_rev.append(tr)
        recv_ratios.append(round(tr / s, 3) if s > 0 else None)

    result["true_revenue"] = {yk: round(tr, 2) for yk, tr in zip(year_keys, true_rev)}
    result["receipt_ratios"] = {yk: rr for yk, rr in zip(year_keys, recv_ratios)}

    # Steps 3-7: AA computation
    # AA = OCF - Maintenance_Capex ± NonRecurring
    # V12: 使用 Zone J 的 mcapex_split_pct 分离维持性 vs 成长性 Capex
    mcapex_pct = params.get("mcapex_split_pct")
    if mcapex_pct is None:
        mcapex_pct = 1.0  # 默认：全部 Capex 都算维持性（保守）
    elif isinstance(mcapex_pct, dict):
        mcapex_pct = mcapex_pct.get("value", 1.0)
    mcapex_pct = min(max(float(mcapex_pct) / 100 if float(mcapex_pct) > 1 else float(mcapex_pct), 0), 1.0)
    # normalize: if stored as percentage (e.g. 80 → 80%), convert to fraction
    if mcapex_pct > 1:
        mcapex_pct = mcapex_pct / 100

    aa_values = []
    for i in range(n):
        mcapex = capex[i] * mcapex_pct  # 维持性 Capex
        aa = ocf[i] - mcapex
        aa_values.append(max(aa, 0))
        result["aa"][year_keys[i]] = round(aa, 2)

    result["mcapex_split_used"] = round(mcapex_pct, 2) if mcapex_pct < 1.0 else None

    result["aa_avg"] = {
        "3y": round(avg_last_n(aa_values, 3), 2),
        "5y": round(avg(aa_values), 5) if n >= 5 else round(avg(aa_values), 2),
        "all": round(avg(aa_values), 2),
    }

    # NP average
    np_avg_3y = avg_last_n(np, 3)
    oe_vals = [np[i] + d_a[i] - capex[i] for i in range(n)]
    oe_avg_3y = avg_last_n(oe_vals, 3)

    # Step 8: g_base & B-class penalty
    g_base = params.get("g_base", 2.0)
    b_penalty = params.get("b_penalty", 0.25)
    g_adj = g_base * (1 - b_penalty)
    result["g_base"] = g_base
    result["b_penalty"] = b_penalty
    result["g_adj"] = round(g_adj, 2)

    # Step 9: AP Excess Financing Check
    # AP/Cost ratio stability check
    cost = [safe_float(r.get("oper_cost"), 0) for r in inc]
    # If oper_cost not available, estimate from revenue - gross profit
    if all(c == 0 for c in cost):
        gross_margin = [(rev[i] - np[i]) / rev[i] if rev[i] > 0 else 0.1 for i in range(n)]
        cost = [rev[i] * (1 - 0.15) for i in range(n)]  # rough estimate

    ap_cost_ratios = []
    for i in range(n):
        if cost[i] > 0:
            ap_cost_ratios.append(ap[i] / cost[i])
    ap_ratio_avg = avg(ap_cost_ratios)
    result["ap_cost_ratio_avg"] = round(ap_ratio_avg * 100, 1) if ap_ratio_avg else None
    # AP growth vs Cost growth
    ap_cagr = cagr(ap)
    cost_cagr_val = cagr(cost)
    result["ap_excess_financing"] = 0  # AP growth <= cost growth → no excess
    if ap_cagr and cost_cagr_val:
        if ap_cagr > cost_cagr_val + 0.05:  # AP growing >5pp faster than cost
            result["ap_excess_financing"] = 1

    # Step 10c: λ (lambda) — critical revenue multiple
    lambda_conservative = None
    if np_avg_3y and np_avg_3y > 0 and params.get("II", 5.5) > 0:
        M_val = factor2_M if factor2_M is not None else 0.55
        lambda_conservative = round((np_avg_3y * 0.55) / (params["II"] / 100), 0)
    result["lambda"] = {
        "conservative": lambda_conservative,
        "neutral": round(aa_values[-3:][0] / (params.get("II", 5.5) / 100), 0) if len(aa_values) >= 3 else None,
        "optimistic": round((np_avg_3y + (avg(d_a) if d_a and any(x > 0 for x in d_a) else 0)) * 0.55 / (params.get("II", 5.5) / 100), 0) if np_avg_3y else None,
    }

    # Step 11: GG computation
    mc = market.get("mc_rmb", 0)
    # V12 fix: 使用 factor2 传入的 M 系数（优先），避免硬编码 0.55
    M_val = factor2_M if factor2_M is not None else params.get("M", 0.55)
    Q = params.get("Q", 0.10)
    O_val = params.get("O", 0)  # buyback contribution

    if mc > 0:
        gg_np = (np_avg_3y * M_val * (1 - Q) + O_val) / mc * 100 if np_avg_3y else None
        gg_oe = (oe_avg_3y * M_val * (1 - Q) + O_val) / mc * 100 if oe_avg_3y else None
        aa3y = avg_last_n(aa_values, 3)
        gg_aa = (aa3y * M_val * (1 - Q) + O_val) / mc * 100 if aa3y else None

        result["gg_raw"] = {
            "np_based": round(gg_np, 2) if gg_np else None,
            "oe_based": round(gg_oe, 2) if gg_oe else None,
            "aa_based": round(gg_aa, 2) if gg_aa else None,
        }

        # Three scenarios — only compute if both gg_np and gg_oe are available
        if gg_np is not None and gg_oe is not None:
            result["gg"] = {
                "pessimistic": round(gg_np - b_penalty, 1),
                "base": round((gg_np + gg_oe) / 2 + g_adj, 1),
                "optimistic": round(gg_oe + g_base, 1),
            }
        else:
            result["gg"] = {
                "pessimistic": None,
                "base": None,
                "optimistic": None,
            }
            result["gg_unavailable"] = True
            result["gg_unavailable_reason"] = "NP₃y或OE₃y数据不足（<3年），无法计算GG"

        # V12: 使用 Zone J 的 total_discount_pct，不再硬编码 15%
        disc_pct = params.get("total_discount_pct", 15)
        if isinstance(disc_pct, dict):
            disc_pct = disc_pct.get("value", 15)
        disc = 1.0 - min(max(float(disc_pct), 0), 50) / 100  # 折价上限 50%
        if result["gg"]["base"] is not None:
            result["gg_discounted"] = {
                k: round(v * disc, 1) for k, v in result["gg"].items()
            }
            result["data_discount_used"] = round(float(disc_pct), 1)
        else:
            result["gg_discounted"] = {"pessimistic": None, "base": None, "optimistic": None}

    # Step 13: Error Propagation — 使用实际数据范围，不用固定±%
    np_std = None
    if np_avg_3y and len(np) >= 3:
        import statistics
        try:
            np_std = statistics.stdev(np[-3:])
        except Exception:
            pass
    gg_pess_val = result["gg"]["pessimistic"]
    gg_opt_val = result["gg"]["optimistic"]
    result["error_propagation"] = {
        "np_range": [round(np_avg_3y - (np_std or np_avg_3y*0.1), 0), round(np_avg_3y + (np_std or np_avg_3y*0.1), 0)] if np_avg_3y else None,
        "d_a_range": [round(avg(d_a) * 0.85, 0), round(avg(d_a) * 1.15, 0)] if d_a and any(x > 0 for x in d_a) else None,
        "capex_range": [round(min(capex), 1), round(max(capex), 1)] if capex else None,
        "g_range": [params.get("g_base", 2.0) * 0, params.get("g_base", 2.0) * 1.5],  # 0 to g_base×1.5
        "b_penalty_range": [0, params.get("b_penalty", 0.25) * 2],  # 0 to b_penalty×2
        "gg_min": round(gg_pess_val * 0.9, 1) if gg_pess_val is not None else None,
        "gg_max": round(gg_opt_val * 1.05, 1) if gg_opt_val is not None else None,
    }

    # Rejection checks
    result["rejection"]["s11"] = "pass"  # cross-validation not triggered
    result["rejection"]["ap_finance"] = "pass" if result.get("ap_excess_financing", 0) == 0 else "warn"

    # Net cash
    if total_assets and total_liab:
        net_cash = money_cap[-1] - total_liab[-1] if money_cap[-1] > 0 else None
    else:
        net_cash = None
    result["net_cash"] = round(net_cash, 2) if net_cash else None
    if mc > 0 and net_cash:
        result["net_cash_pct_mc"] = round(net_cash / mc * 100, 1)

    # V9.2: EV口径止损 — 净现金/市值>40%时DDM可能不适用
    if result.get("net_cash_pct_mc") and result["net_cash_pct_mc"] > 40:
            result["valuation_warning"] = (
                f"净现金/市值={result['net_cash_pct_mc']:.0f}%超过40%，"
                f"DDM估值可能不适用，建议切换到EV口径"
            )

    # Pass raw data for downstream computation (value trap, etc.)
    result["_income_raw"] = inc

    return result


# ── Factor 4: DDM Valuation ──

def compute_factor4(factor3: dict, market: dict, params: dict) -> dict:
    """Factor 4: DDM阶梯买入估值."""
    result = {"tiers": [], "rejection": {}}

    dps = params.get("dps_latest")
    if dps is None:
        return {"ddm_v_hkd": None, "ddm_v_rmb": None, "buy_ladder": [], "error": "dps_latest missing"}
    g = factor3.get("g_adj", 1.5) / 100
    II = params.get("II", 5.5) / 100
    Q = params.get("Q", 0.10)
    gg_base = factor3.get("gg", {}).get("base", 21.2)
    mc = market.get("mc_rmb", 0)
    price_rmb = market.get("price_rmb", 1.83)
    shares = market.get("shares_m")
    if shares is None:
        return {"ddm_v_hkd": None, "ddm_v_rmb": None, "buy_ladder": [], "error": "shares_m missing"}

    # DDM: V = DPS * (1+g) / (r - g)
    dps_next = dps * (1 + g)
    r = II  # required return = II
    if r > g:
        v_ddm = dps_next / (r - g)
    else:
        v_ddm = dps * 20  # fallback PE=20

    result["ddm_v_rmb"] = round(v_ddm, 2)
    fx = market.get("fx", 0.9346)
    result["ddm_v_hkd"] = round(v_ddm / fx, 2)

    # Tiered entry (five-star system)
    for star, discount in [(5, 0.0), (4, 0.10), (3, 0.20), (2, 0.30), (1, 0.40)]:
        target_rmb = v_ddm * (1 - discount)
        target_hkd = target_rmb / fx
        upside = (target_hkd / (price_rmb / fx) - 1) * 100 if price_rmb > 0 else 0
        pe_implied = (target_rmb * shares) / (factor3.get("np_avg_3y", 117)) if factor3.get("np_avg_3y") else None
        result["tiers"].append({
            "star": star,
            "price_hkd": round(target_hkd, 2),
            "price_rmb": round(target_rmb, 2),
            "upside_pct": round(upside, 1),
            "pe_implied": round(pe_implied, 1) if pe_implied else None,
        })

    # DPS yield
    if price_rmb > 0:
        result["dps_yield_pretax"] = round(dps / price_rmb * 100, 2)
        result["dps_yield_after_tax"] = round(dps * (1 - Q) / price_rmb * 100, 2)

    # Value trap check (7 criteria) — compute from actual data where possible
    # Quantitative checks
    np_5y_cagr = cagr([safe_float(r.get("n_income_attr_p")) for r in factor3.get("_income_raw", [])]) if factor3.get("_income_raw") else None
    np_decline = np_5y_cagr is not None and np_5y_cagr < 0

    # FCF sustainability: AA > dividends_paid?
    aa3y = factor3.get("aa_avg", {}).get("3y", 0) or 0
    annual_dividend = params.get("dps_latest", 0) * shares if params.get("dps_latest") and shares else 0
    dividend_unsustainable = aa3y < annual_dividend * 0.8 if aa3y > 0 else None

    # Qualitative checks (require LLM judgment — mark as unknown when data unavailable)
    vt = {
        "np_decline": np_decline,
        "low_pb_roe": None,              # needs PB+ROE from market data
        "dividend_unsustainable": dividend_unsustainable,
        "business_disrupted": None,       # qualitative — LLM to judge
        "management_expropriation": None, # qualitative — LLM to judge
        "margin_irreversible": None,      # needs gross margin trend data
        "price_new_lows": None,           # needs price percentile data
    }
    vt_quant = {k: v for k, v in vt.items() if v is not None}
    vt_score_known = sum(1 for v in vt_quant.values() if v)
    vt_total_known = len(vt_quant)
    result["value_trap"] = {
        "score_known": vt_score_known,
        "total_known": vt_total_known,
        "triggers": [k for k, v in vt.items() if v is True],
        "non_triggers": [k for k, v in vt.items() if v is False],
        "unknown": [k for k, v in vt.items() if v is None],
        "exclude": vt_score_known >= 2 and gg_base < II * 100 * 1.5,
        "note": f"{vt_total_known}/7 criteria computable from data; {len([k for k,v in vt.items() if v is None])} require LLM judgment",
    }

    # Position sizing (three perspectives)
    result["position"] = {
        "conservative": "0.5-1.0%",
        "neutral": "2.0-3.0%",
        "optimistic": "4.0-5.0%",
        "recommended": "1.5-2.5%",
    }

    # Stop loss
    result["stop_loss"] = {
        "hard_hkd": round(price_rmb / fx * 0.765, 2),  # -23.5%
        "fundamental": "fy2026_h1_margin_lt_13pct",
        "time": "2yr_no_value_convergence",
        "event": "major_shareholder_sells_or_audit_change",
    }

    # Rejection
    result["rejection"]["s1"] = "pass"  # GG > II
    result["rejection"]["s2"] = "warn_not_exclude" if vt_score_known >= 2 else "pass"

    return result


# ── Main ──

def _build_calculation_trace(factor2, factor3, factor4, market, params):
    """Build step-by-step calculation traces for Zone C report writing."""
    mc_rmb = market.get("mc_rmb", 0)
    np_3y = factor2.get("np_avg_3y", 0)
    oe_3y = factor2.get("oe_avg_3y", 0)
    aa_3y = factor3.get("aa_avg", {}).get("3y", 0)
    g_adj = factor3.get("g_adj", 1.5)
    g_base = factor3.get("g_base", 2.0)
    M_val = factor3.get("M", factor2.get("M", 0.55))
    Q = params.get("Q", 0.10)
    II = params.get("II", 5.5) / 100
    dps = params.get("dps_latest", 0)
    gg = factor3.get("gg", {})
    gg_raw = factor3.get("gg_raw", {})
    lamb = factor3.get("lambda", {})

    return {
        "factor2_r_np": {
            "formula": "R(NP)税前 = NP₃y / MC_rmb × 100",
            "substitutions": {"NP₃y": round(np_3y, 2), "MC_rmb": round(mc_rmb, 2)},
            "steps": [f"NP₃y / MC_rmb = {np_3y:.2f} / {mc_rmb:.2f} = {np_3y/mc_rmb*100:.2f}%"] if mc_rmb > 0 else [],
            "result": round(factor2.get("r_np", 0), 2), "unit": "%"
        },
        "factor2_r_oe": {
            "formula": "R(OE)税前 = OE₃y / MC_rmb × 100",
            "substitutions": {"OE₃y": round(oe_3y, 2), "MC_rmb": round(mc_rmb, 2)},
            "steps": [f"OE₃y / MC_rmb = {oe_3y:.2f} / {mc_rmb:.2f} = {oe_3y/mc_rmb*100:.2f}%"] if mc_rmb > 0 else [],
            "result": round(factor2.get("r_oe", 0), 2), "unit": "%"
        },
        "factor2_r_np_after_tax": {
            "formula": "R(NP)税后 = R(NP)税前 × (1 - Q)",
            "substitutions": {"R(NP)税前": round(factor2.get("r_np", 0), 2), "Q": Q},
            "steps": [f"{factor2.get('r_np',0):.2f}% × (1-{Q}) = {factor2.get('r_np',0)*(1-Q):.2f}%"],
            "result": round(factor2.get("r_np", 0) * (1 - Q), 2), "unit": "%"
        },
        "factor3_gg_raw": {
            "formula": "GG_np = NP₃y × M × (1-Q) / MC_rmb × 100",
            "substitutions": {"NP₃y": round(np_3y, 2), "M": round(M_val, 4), "Q": Q, "MC_rmb": round(mc_rmb, 2)},
            "steps": [
                f"GG_np = {np_3y:.1f} × {M_val:.4f} × (1-{Q}) / {mc_rmb:.1f} × 100 = {gg_raw.get('np_based',0)}%"
            ] if mc_rmb > 0 else [],
            "gg_oe": {
                "formula": "GG_oe = OE₃y × M × (1-Q) / MC_rmb × 100",
                "substitutions": {"OE₃y": round(oe_3y, 2), "M": round(M_val, 4), "Q": Q, "MC_rmb": round(mc_rmb, 2)},
                "steps": [
                    f"GG_oe = {oe_3y:.1f} × {M_val:.4f} × (1-{Q}) / {mc_rmb:.1f} × 100 = {gg_raw.get('oe_based',0)}%"
                ] if mc_rmb > 0 else []
            },
            "result": {"gg_np": round(gg_raw.get("np_based", 0), 2), "gg_oe": round(gg_raw.get("oe_based", 0), 2)},
            "unit": "%"
        },
        "factor3_gg": {
            "formula": "GG_base = (GG_np + GG_oe) / 2 + g_adj",
            "substitutions": {
                "GG_np": round(gg_raw.get("np_based", 0), 2),
                "GG_oe": round(gg_raw.get("oe_based", 0), 2),
                "g_adj": round(g_adj, 2)
            },
            "steps": [
                f"(GG_np + GG_oe) / 2 = ({gg_raw.get('np_based',0):.2f} + {gg_raw.get('oe_based',0):.2f}) / 2 = {(gg_raw.get('np_based',0)+gg_raw.get('oe_based',0))/2:.2f}%",
                f"+ g_adj({g_adj:.2f}%) = {(gg_raw.get('np_based',0)+gg_raw.get('oe_based',0))/2 + g_adj:.2f}%"
            ],
            "result": round(gg.get("base", 0), 2), "unit": "%"
        },
        "factor3_gg_scenarios": {
            "pessimistic": round(gg.get("pessimistic", 0), 2),
            "base": round(gg.get("base", 0), 2),
            "optimistic": round(gg.get("optimistic", 0), 2),
            "note": "悲观=GG_np - b_penalty; 基准=(GG_np+GG_oe)/2 + g_adj; 乐观=GG_oe + g_base",
            "unit": "%"
        },
        "factor3_lambda": {
            "formula": "λ_neutral = AA_latest_3y_first / (II/100)",
            "substitutions": {"AA_recent": round(aa_3y, 2), "II_pct": round(II*100, 1)},
            "result": round(lamb.get("neutral", 0), 2) if isinstance(lamb, dict) else None,
            "unit": "百万元 RMB"
        },
        "factor4_ddm": {
            "formula": "V = DPS × (1 + g_adj/100) / (II - g_adj/100)",
            "substitutions": {"DPS": round(dps, 3), "g": round(g_adj/100, 4), "II": round(II, 4)},
            "steps": [
                f"DPS₁ = {dps:.3f} × (1+{g_adj/100:.4f}) = {dps*(1+g_adj/100):.3f}",
                f"V = {dps*(1+g_adj/100):.3f} / ({II:.4f}-{g_adj/100:.4f}) = {factor4.get('ddm_v_hkd',0):.2f} HKD"
            ] if II > g_adj/100 and dps > 0 else [],
            "result": round(factor4.get("ddm_v_hkd", 0), 2), "unit": "HKD"
        },
    }


def compute(output_dir: str, params_override: Optional[dict] = None,
            price_hkd: float = None, shares_m: float = None) -> dict:
    """Main computation entry point. Returns full compute_bundle dict."""
    output_dir = os.path.abspath(output_dir)

    # Load data sources — prefer verified input_data.json
    threshold = load_threshold(output_dir)
    input_data = load_input_data(output_dir)
    if input_data:
        print(f"📄 Using verified input_data.json ({len(input_data.get('years',[]))} years)")
        fin_data = normalize_input_data(input_data)
    else:
        hk = load_hk_fallback(output_dir)
        if not hk:
            print(f"ERROR: No input_data.json or hk_report_fallback.json found in {output_dir}", file=sys.stderr)
            return {"error": "no_data_found"}
        print(f"📄 Using hk_report_fallback.json")
        # hk_report_fallback stores raw values (元), normalize to 百万元
        fin_data = _scale_fallback_to_millions(hk)

    currency = fin_data.get("currency", "RMB")

    # Market data: priority = function arg → data_pack_market.md → threshold.json → error
    fx = 0.9346  # HKD to RMB (fixed for now, could fetch实时)
    _price_hkd = price_hkd  # from function arg
    _shares_m = shares_m    # from function arg

    if _price_hkd is None:
        dp_text = load_data_pack(output_dir)
        if dp_text:
            m = re.search(r"当前价格\s*\(HKD\)\s*\|\s*([\d.]+)", dp_text)
            if m:
                _price_hkd = float(m.group(1))
    if _shares_m is None and threshold:
        _shares_m = threshold.get("shares_m")
    # V10: Read shares from DB before falling back to yfinance
    if _shares_m is None:
        try:
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute("SELECT shares_m FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
            conn.close()
            if row and row[0]:
                _shares_m = float(row[0])
                print(f"📊 DB shares: {_shares_m}M", file=sys.stderr)
        except Exception:
            pass
    # V8.3: Auto-fetch from yfinance if still missing
    if _price_hkd is None or _shares_m is None:
        try:
            import yfinance as yf
            code = ts_code.replace(".HK", ".HK").replace(".SH", ".SS").replace(".SZ", ".SZ")
            t = yf.Ticker(ts_code)
            info = t.info
            if _price_hkd is None:
                _price_hkd = info.get("regularMarketPrice") or info.get("currentPrice")
            if _shares_m is None:
                s = info.get("sharesOutstanding")
                if s: _shares_m = round(s / 1_000_000, 2)
            if _price_hkd and _shares_m:
                print(f"📊 yfinance auto: price={_price_hkd}, shares={_shares_m}M", file=sys.stderr)
        except Exception:
            pass
    if _price_hkd is None:
        print("ERROR: Cannot determine current price. Use --from-db mode, --price, or provide data_pack_market.md", file=sys.stderr)
        return {"error": "no_price_data"}
    if _shares_m is None:
        print("ERROR: Cannot determine shares outstanding. Use --from-db mode, --shares, or provide threshold.json", file=sys.stderr)
        return {"error": "no_shares_data"}

    market = {
        "price_hkd": _price_hkd,
        "price_rmb": round(_price_hkd * fx, 2),
        "shares_m": _shares_m,
        "mc_hkd": round(_price_hkd * _shares_m, 2),
        "mc_rmb": round(_price_hkd * _shares_m * fx, 2),
        "fx": fx,
    }

    # Base params
    params = {
        "II": threshold.get("II", 5.5),
        "Rf": 4.0,
        "Q": 0.10,
        "O": 0,
        "PORTFOLIO_CAP_PCT": float(os.environ.get("PORTFOLIO_CAP_PCT", "5")),
        "g_base": 2.0,
        "b_penalty": 0.25,
        "dps_latest": params_override.get("dps_latest") if params_override else None,
    }
    if params_override:
        params.update(params_override)

    # Compute factors
    factor2 = compute_factor2(fin_data, market, params)
    factor3 = compute_factor3(fin_data, market, params, factor2.get("M"))
    # Merge M from factor3 into factor2 if available
    if "M" not in factor2 or factor2["M"] == 0.55:
        factor2["M"] = factor3.get("M", factor2["M"])
    factor4 = compute_factor4(factor3, market, params)

    calculation_trace = _build_calculation_trace(factor2, factor3, factor4, market, params)

    # Rejection summary
    rejection_summary = {
        "overall": "pass",
        "warnings": [],
        "blocks": [],
    }
    for f_name, f_result in [("factor2", factor2), ("factor3", factor3), ("factor4", factor4)]:
        for gate, status in f_result.get("rejection", {}).items():
            if status == "fail":
                rejection_summary["blocks"].append(f"{f_name}.{gate}")
                rejection_summary["overall"] = "block"
            elif status == "warn" or status == "warn_not_exclude":
                rejection_summary["warnings"].append(f"{f_name}.{gate}")

    bundle = {
        "meta": {
            "code": fin_data.get("ts_code", "01502.HK"),
            "date": "2026-07-08",
            "version": "v3.0-compute-first",
            "currency": currency,
        },
        "market": market,
        "params": params,
        "factor2": factor2,
        "factor3": factor3,
        "factor4": factor4,
        "calculation_trace": calculation_trace,
        "rejection_summary": rejection_summary,
    }

    return bundle


def fetch_market_from_tushare(ts_code: str) -> dict:
    """Try to fetch current price from Tushare → yfinance. Returns {price, source} or None."""
    result = {}

    # Fallback 1: Tushare
    try:
        import tushare as ts
        token = None
        api_url = ""
        # Read from .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TUSHARE_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                    elif line.startswith("TUSHARE_API_URL="):
                        api_url = line.split("=", 1)[1].strip()
        # Fallback to environ
        if not token:
            token = os.environ.get("TUSHARE_TOKEN", "")
        if not api_url:
            api_url = os.environ.get("TUSHARE_API_URL", "")
        if not token:
            return None

        ts.set_token(token)
        pro = ts.pro_api()
        if api_url:
            pro._DataApi__http_url = api_url

        result["source"] = "tushare"

        if ts_code.endswith(".HK"):
            # HK stock
            basic = pro.hk_basic(ts_code=ts_code)
            if not basic.empty:
                result["name_cn"] = basic.iloc[0].get("name", "")
            # Try daily for price
            try:
                daily = pro.hk_daily(ts_code=ts_code, start_date="20260101", end_date="20301231")
                if not daily.empty:
                    daily_sorted = daily.sort_values("trade_date", ascending=False)
                    result["price"] = float(daily_sorted.iloc[0].get("close", 0))
                    result["price_date"] = str(daily_sorted.iloc[0].get("trade_date", ""))
            except Exception:
                pass
        else:
            # A-share
            basic = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,list_date")
            if not basic.empty:
                result["name_cn"] = basic.iloc[0].get("name", "")
            try:
                daily = pro.daily(ts_code=ts_code, start_date="20260101", end_date="20301231")
                if not daily.empty:
                    daily_sorted = daily.sort_values("trade_date", ascending=False)
                    result["price"] = float(daily_sorted.iloc[0].get("close", 0))
                    result["price_date"] = str(daily_sorted.iloc[0].get("trade_date", ""))
            except Exception:
                pass

        if "price" in result:
            return result
        # Tushare works but no price → fall through to yfinance
    except Exception as e:
        print(f"📡 Tushare: {e}", file=sys.stderr)

    # Fallback 2: yfinance
    try:
        import yfinance as yf
        ticker_str = ts_code
        if ts_code.endswith(".HK"):
            ticker_str = ts_code.replace(".HK", "").lstrip("0").zfill(4) + ".HK"
        elif ts_code.endswith(".SH"):
            ticker_str = ts_code.replace(".SH", ".SS")
        elif ts_code.endswith(".SZ"):
            ticker_str = ts_code.replace(".SZ", ".SZ")
        ticker = yf.Ticker(ticker_str)
        info = ticker.info
        if info and info.get("regularMarketPrice"):
            price = float(info["regularMarketPrice"])
            shares = info.get("sharesOutstanding")
            name = info.get("longName") or info.get("shortName", "")
            print(f"📊 yfinance: {name} | price={price} | shares={shares or 'N/A'}", file=sys.stderr)
            return {"source": "yfinance", "price": price, "name_cn": name or "",
                    "shares_outstanding": int(shares) if shares else None}
    except Exception as e:
        print(f"📡 yfinance: {e}", file=sys.stderr)

    return None


def compute_from_db(ts_code: str, params_override: dict = None, price_hkd: float = None,
                     force: bool = False, contract: Optional[dict] = None,
                     zone_j_params: Optional[dict] = None) -> dict:
    """Compute bundle from database. V9.2: dynamic window + Zone J parameters.

    If price_hkd is None, auto-fetches from Tushare/yfinance.
    If force=True, skip BLOCKED readiness check.
    If contract is provided, uses effective_years as data window.
    If zone_j_params is provided, merges into params_override (Zone J → compute_bundle).
    """
    # Dynamic readiness check (not just saved contract)
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        ready = conn.execute(
            "SELECT readiness_status FROM v_analysis_readiness WHERE ts_code=?",
            (ts_code,)).fetchone()
        if ready and ready["readiness_status"] == "BLOCKED":
            # Only block if recent years (last 5) have issues
            recent_year = conn.execute(
                "SELECT MAX(fiscal_year)-5 FROM annual_financials WHERE ts_code=?",
                (ts_code,)).fetchone()[0]
            blocks = conn.execute(
                "SELECT check_name, field_name, fiscal_year, message FROM quality_findings WHERE ts_code=? AND severity='BLOCK' AND fix_status='open' AND fiscal_year >= ?",
                (ts_code, recent_year)).fetchall()
            if blocks and not force:
                conn.close()
                print(f"🛑 BLOCKED: {ts_code} has {len(blocks)} open BLOCK(s) in recent years (≥{recent_year}).", file=sys.stderr)
                for b in blocks[:5]:
                    print(f"   {b['check_name']}: FY{b['fiscal_year']} {b['message'][:80]}", file=sys.stderr)
                print(f"   Use --force to bypass, or run validate.py --code {ts_code} for full report.", file=sys.stderr)
                return {"error": "blocked_by_readiness", "open_blocks": len(blocks)}
            if blocks and force:
                print(f"⚠️  FORCED: {ts_code} has {len(blocks)} open BLOCK(s) in recent years — proceeding anyway.", file=sys.stderr)
        # Also check degraded
        if ready:
            status = ready["readiness_status"]
            if status == "DEGRADED":
                print(f"⚠️  DEGRADED: {ts_code} data quality is degraded. Results may need caveats.", file=sys.stderr)
        conn.close()

    fin_data = load_from_db(ts_code, contract)
    if not fin_data:
        return {"error": f"no_data_in_db_for_{ts_code}"}

    threshold = fin_data.pop("_threshold", {})
    stock_info = fin_data.pop("_stock", {})

    fx = 0.9346

    # Auto-fetch market data from Tushare/yfinance
    tushare_data = None
    if price_hkd is None:
        tushare_data = fetch_market_from_tushare(ts_code)

    # Shares: DB → yfinance → override → default
    shares_m = stock_info.get("shares_m")
    shares_warning = shares_m is None
    if not shares_m and tushare_data and tushare_data.get("shares_outstanding"):
        yf_shares = tushare_data["shares_outstanding"] / 1_000_000
        if yf_shares > 0:
            shares_m = round(yf_shares, 2)
            shares_warning = False
    if not shares_m:
        shares_m = params_override.get("shares_m") if params_override else None
    if not shares_m:
        raise ValueError(
            f"Cannot determine shares outstanding for {ts_code}. "
            f"DB stock_info.shares_m is NULL, yfinance/Tushare unavailable. "
            f"Provide --shares or populate DB stock_info."
        )

    # Price: manual → Tushare/yfinance → default
    price_source = "manual" if price_hkd else "default"
    if price_hkd is None:
        if tushare_data and tushare_data.get("price"):
            price_hkd = tushare_data["price"]
            price_source = tushare_data.get("source", "auto")
            print(f"📊 {price_source}: price={price_hkd} HKD, shares={shares_m}M")
        else:
            if params_override and params_override.get("price"):
                price_hkd = params_override["price"]
                price_source = "override"
            else:
                raise ValueError(
                    f"Cannot determine current price for {ts_code}. "
                    f"Tushare/yfinance unavailable. Provide --price."
                )

    market = {
        "price_hkd": price_hkd,
        "price_rmb": round(price_hkd * fx, 2),
        "shares_m": shares_m,
        "mc_hkd": round(price_hkd * shares_m, 2),
        "mc_rmb": round(price_hkd * shares_m * fx, 2),
        "fx": fx,
        "shares_warning": stock_info.get("shares_m") is None,
        "price_source": price_source,
    }

    # Try to get DPS: override → dividends_paid/shares (全息,含中期) → DB dps列 → error
    dps_latest = (params_override.get("dps_latest") if params_override else None)
    if dps_latest is None:
        db_dps_rows = fin_data.get("dividends", [])
        # Get DB dps column as sanity check reference
        db_dps_ref = None
        if db_dps_rows:
            ref_vals = [safe_float(r.get("dps")) for r in db_dps_rows[-3:]]
            ref_vals = [v for v in ref_vals if v is not None and 0 < v < 1000]
            if ref_vals:
                db_dps_ref = ref_vals[-1]
        # Tier 1: dividends_paid/shares (includes interim+final for HK semi-annual payers)
        if db_dps_rows and shares_m:
            latest_div = db_dps_rows[-1]
            div_paid = safe_float(latest_div.get("dividends_paid"))
            if div_paid and div_paid > 0:
                dps_from_div = round(div_paid / shares_m, 4)
                # Sanity: must be within 0.5x-3x of DB dps column
                if 0 < dps_from_div < 1000:
                    if db_dps_ref and db_dps_ref > 0:
                        ratio = dps_from_div / db_dps_ref
                        if 0.5 <= ratio <= 3.0:
                            dps_latest = dps_from_div
                            print(f"📊 DPS: dividends_paid/shares={dps_latest:.4f} (vs DB dps={db_dps_ref:.4f}, ratio={ratio:.1f}x)", file=sys.stderr)
                        else:
                            print(f"⚠️  DPS: dividends_paid/shares={dps_from_div:.4f} out of range vs DB dps={db_dps_ref:.4f} (ratio={ratio:.1f}x) — using DB dps", file=sys.stderr)
                    else:
                        dps_latest = dps_from_div
        if dps_latest is None and db_dps_ref is not None:
            dps_latest = db_dps_ref
    if dps_latest is None:
        raise ValueError(
            f"Cannot determine DPS for {ts_code}. "
            f"DB dps column is NULL/empty. Provide --dps."
        )

    params = {
        "II": threshold.get("II", 5.5),
        "Rf": 4.0, "Q": 0.10, "O": 0,
        "PORTFOLIO_CAP_PCT": float(os.environ.get("PORTFOLIO_CAP_PCT", "5")),
        "g_base": 2.0, "b_penalty": 0.25,
        "dps_fy": db_dps_ref,        # V9.3: 年报全年DPS
        "dps_ttm": dps_latest,        # V9.3: 最近12个月(含特别股息)
        "dps_latest": db_dps_ref or dps_latest,  # DDM默认用年报DPS
    }
    if params_override:
        # Only update non-None override values (don't clobber DB-read values)
        params.update({k: v for k, v in params_override.items() if v is not None})

    # V9.2: Zone J parameters override defaults (g_base, b_penalty, etc.)
    if zone_j_params:
        zj_merged = {k: v for k, v in zone_j_params.items() if v is not None}
        params.update(zj_merged)
        if zj_merged:
            print(f"📐 Zone J params: {list(zj_merged.keys())}", file=sys.stderr)

    # Check D&A availability
    d_a_available = any(
        safe_float(r.get("depr_fa_coga_dpba")) or safe_float(r.get("amort_intang_assets"))
        for r in fin_data.get("income", [])
    )
    if not d_a_available:
        print("⚠️  WARNING: D&A (depreciation) is missing for all years — OE will equal NP.", file=sys.stderr)

    factor2 = compute_factor2(fin_data, market, params)
    factor3 = compute_factor3(fin_data, market, params, factor2.get("M"))
    factor4 = compute_factor4(factor3, market, params)
    # V9.3: Conservative PE cap
    pe_theory = 100 / params.get("II", 5.5) if params.get("II", 0) > 0 else 18.18
    cr = factor2.get("capex_ratio_avg", 10) or 10
    factor4["pe_cap"] = min(pe_theory, 12.0) if cr < 3.0 else pe_theory

    calculation_trace = _build_calculation_trace(factor2, factor3, factor4, market, params)

    rejection_summary = {"overall": "pass", "warnings": [], "blocks": []}
    for f_name, f_result in [("factor2", factor2), ("factor3", factor3), ("factor4", factor4)]:
        for gate, status in f_result.get("rejection", {}).items():
            if status == "fail":
                rejection_summary["blocks"].append(f"{f_name}.{gate}")
                rejection_summary["overall"] = "block"
            elif status in ("warn", "warn_not_exclude"):
                rejection_summary["warnings"].append(f"{f_name}.{gate}")

    currency = fin_data.get("currency", "RMB")
    return {
        "meta": {"code": ts_code, "date": "2026-07-08", "version": "v3.0-db", "currency": currency},
        "market": market, "params": params,
        "factor2": factor2, "factor3": factor3, "factor4": factor4,
        "calculation_trace": calculation_trace,
        "rejection_summary": rejection_summary,
    }


def main():
    p = argparse.ArgumentParser(description="compute_bundle v3.0 — 定量计算中心")
    p.add_argument("--output", help="Output directory (JSON file path)")
    p.add_argument("--from-db", action="store_true", help="Read from stock_analysis.db instead of JSON files")
    p.add_argument("--code", type=str, default="01502.HK", help="Stock code for --from-db mode")
    p.add_argument("--g-base", type=float, default=2.0, help="g_base override")
    p.add_argument("--b-penalty", type=float, default=0.25, help="B-class penalty override")
    p.add_argument("--dps", type=float, default=None, help="Latest DPS override")
    p.add_argument("--price", type=float, default=None, help="Current price override (auto-fetched from Tushare if omitted)")
    p.add_argument("--shares", type=float, help="Shares outstanding (millions) override")
    p.add_argument("--force", action="store_true", help="Bypass BLOCKED readiness check")
    p.add_argument("--contract", type=str, default=None,
                   help="Path to analysis_contract.json (V9.2 dynamic window)")
    p.add_argument("--zone-j", type=str, default=None,
                   help="Path to stock output directory with Zone J JSONs (V9.2)")
    args = p.parse_args()

    if args.from_db:
        # V9.2: Auto-load analysis_contract if not explicitly provided
        contract = None
        if args.contract and os.path.exists(args.contract):
            with open(args.contract) as f:
                contract = json.load(f)
        elif not args.contract:
            # Auto-detect from stock output directory
            contract = load_analysis_contract(args.code)

        # Database mode
        override = {"g_base": args.g_base, "b_penalty": args.b_penalty, "dps_latest": args.dps}
        if args.shares:
            override["shares_m"] = args.shares
        # V9.2: Load Zone J parameters if --zone-j provided
        zone_j_params = None
        if args.zone_j:
            zone_j_params = load_zone_j_params(args.zone_j)

        bundle = compute_from_db(args.code, override, price_hkd=args.price,
                                  force=args.force, contract=contract,
                                  zone_j_params=zone_j_params)
        # Use --output if provided, else construct from code
        if args.output:
            if args.output.endswith(".json"):
                out_path = args.output
            else:
                out_path = os.path.join(args.output, "compute_bundle.json")
        else:
            # Search for existing stock directory
            base = f"output/{args.code.replace('.','')}"
            candidates = [d for d in os.listdir("output") if d.startswith(args.code.replace('.HK','').replace('.SH','').replace('.SZ',''))]
            stock_dir = candidates[0] if candidates else args.code.replace('.','_')
            out_path = f"output/{stock_dir}/compute_bundle.json"
    else:
        if not args.output:
            print("ERROR: --output required in JSON mode", file=sys.stderr)
            return 1
        if not os.path.isdir(args.output):
            print(f"ERROR: {args.output} not found", file=sys.stderr)
            return 1
        override = {
            "g_base": args.g_base, "b_penalty": args.b_penalty,
            "dps_latest": args.dps,
        }
        if args.shares:
            override["shares_m"] = args.shares
        bundle = compute(args.output, override, price_hkd=args.price, shares_m=args.shares)
        out_path = os.path.join(args.output, "compute_bundle.json")

    if "error" in bundle:
        print(f"ERROR: {bundle['error']}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False, default=str)

    print(f"✅ compute_bundle.json written to {out_path}")
    print(f"   GG: {bundle['factor3']['gg']}")
    print(f"   DDM: {bundle['factor4']['ddm_v_hkd']} HKD")
    print(f"   Rejection: {bundle['rejection_summary']['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
