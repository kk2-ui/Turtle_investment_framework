#!/usr/bin/env python3
"""compute_bundle.py — 定量计算中心 (v3.0 计算优先架构)

Reads data_pack_market.md + hk_report_fallback.json + threshold.json
and computes ALL quantitative metrics for Factors 2/3/4 in one pass.

Output: compute_bundle.json — structured parameters for LLM report generation.
No LLM agent needed for any computation herein.

Usage:
    python3 scripts/compute_bundle.py --output output/01502_金融街物业
"""

import argparse, json, os, sqlite3, sys, math, re, statistics
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from financial_rigor import exact as _exact

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


def _median_or_none(values):
    """Return the statistical median while preserving the no-data sentinel."""
    return statistics.median(values) if values else None


def _d(value, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return _exact(value)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _d_ratio_pct(numerator, denominator) -> float | None:
    den = _d(denominator)
    if den == 0:
        return None
    return float((_d(numerator) / den) * Decimal("100"))


def _d_penetration_pct(base_value, payout_ratio, tax_rate, buyback_value, denominator) -> float | None:
    den = _d(denominator)
    if den == 0:
        return None
    numerator = _d(base_value) * _d(payout_ratio) * (Decimal("1") - _d(tax_rate)) + _d(buyback_value)
    return float((numerator / den) * Decimal("100"))


def _normalized_aa_value(conservative_aa, full_capex, maintenance_capex) -> float:
    """Normalize owner earnings symmetrically around actual capex.

    Maintenance capex below actual capex adds back the excess; maintenance
    capex above actual capex subtracts the shortfall.  The old one-sided
    ``max(0, full-maintenance)`` silently overstated low-capex companies.
    """
    return max(
        0.0,
        float(_d(conservative_aa) + _d(full_capex) - _d(maintenance_capex)),
    )


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
    """Load Zone J parameters from a stock output directory (V9.2 → V12.15).

    Reads moat_assessment.json, capex_classification.json,
    earnings_quality.json, data_discount.json, governance_tension.json and extracts
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
        # V12.15: 治理折价
        "governance_tension.json": [
            ("governance_discount", None),
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

        # Pre-judgment-first files encoded missing disclosure itself as a
        # negative valuation adjustment.  They remain readable artifacts, but
        # are not economic-discount inputs until regenerated under the current
        # observed-carrier semantics.
        if (
            fname == "data_discount.json"
            and data.get("discount_basis") != "observed_economic_carrier_v1"
        ):
            continue

        if fname == "governance_tension.json":
            try:
                from zone_j_agent import validate_economic_discount_semantics
            except ImportError:
                from scripts.zone_j_agent import validate_economic_discount_semantics
            if validate_economic_discount_semantics("governance_tension", data):
                continue
            discount = data.get("governance_discount")
            pct = float(discount.get("additional_discount_pct", 0))
            params["governance_discount"] = pct
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


def load_gg_override(output_dir: Optional[str]) -> Optional[dict]:
    """Load optional gg_override.json and normalize to a year-keyed structure.

    Supported formats:
    1. Flat single-year:
       {
         "source_year": 2025,
         "direct_labor_cost": 3709,
         "admin_labor_cost": 717,
         "sales_labor_cost": 0,
         "rd_labor_cost": 35,
         "total_labor_cost": 4461,
         "outsourced_service_cost": 11410,
         "notes_basis": "...",
         "confidence": "high",
         "source_pages": [120, 121]
       }

    2. Multi-year:
       {
         "years": {
           "2024": {...},
           "2025": {...}
         }
       }
    """
    if not output_dir:
        return None
    path = os.path.join(output_dir, "gg_override.json")
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        print(f"⚠️  gg_override.json 读取失败: {exc}", file=sys.stderr)
        return None

    if not isinstance(raw, dict):
        print("⚠️  gg_override.json 顶层必须是 object，已忽略", file=sys.stderr)
        return None

    def _normalize_year_entry(entry: dict, year_key: str) -> Optional[dict]:
        if not isinstance(entry, dict):
            return None
        confidence = str(entry.get("confidence") or "medium").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        direct_labor_cost = safe_float(entry.get("direct_labor_cost"))
        admin_labor_cost = safe_float(entry.get("admin_labor_cost"))
        sales_labor_cost = safe_float(entry.get("sales_labor_cost"))
        rd_labor_cost = safe_float(entry.get("rd_labor_cost"))
        total_labor_cost = safe_float(entry.get("total_labor_cost"))
        if total_labor_cost is None:
            derived_total = sum(
                v for v in [direct_labor_cost, admin_labor_cost, sales_labor_cost, rd_labor_cost]
                if v is not None
            )
            if derived_total > 0:
                total_labor_cost = round(derived_total, 2)
        normalized = {
            "direct_labor_cost": direct_labor_cost,
            "admin_labor_cost": admin_labor_cost,
            "sales_labor_cost": sales_labor_cost,
            "rd_labor_cost": rd_labor_cost,
            "total_labor_cost": total_labor_cost,
            "outsourced_service_cost": safe_float(entry.get("outsourced_service_cost")),
            "notes_basis": str(entry.get("notes_basis") or "").strip() or None,
            "confidence": confidence,
            "source_pages": entry.get("source_pages") if isinstance(entry.get("source_pages"), list) else [],
            "source_year": year_key,
        }
        has_labor_fact = any(
            normalized.get(key) is not None
            for key in ("direct_labor_cost", "admin_labor_cost", "sales_labor_cost", "rd_labor_cost", "total_labor_cost")
        )
        if not has_labor_fact:
            return None
        return normalized

    years_raw = raw.get("years")
    year_map: dict[str, dict] = {}
    if isinstance(years_raw, dict):
        for year_key, entry in years_raw.items():
            year_str = re.sub(r"\D", "", str(year_key))[:4]
            if not year_str:
                continue
            normalized = _normalize_year_entry(entry, year_str)
            if normalized:
                year_map[year_str] = normalized
    else:
        source_year = re.sub(r"\D", "", str(raw.get("source_year") or ""))[:4]
        if source_year:
            normalized = _normalize_year_entry(raw, source_year)
            if normalized:
                year_map[source_year] = normalized

    if not year_map:
        print("⚠️  gg_override.json 未提供可用的 source_year/labor facts，已忽略", file=sys.stderr)
        return None

    print(f"📎 gg_override: {', '.join(sorted(year_map.keys()))}", file=sys.stderr)
    return {
        "source_file": path,
        "years": year_map,
    }


def load_labor_disclosure_summary(output_dir: Optional[str]) -> dict:
    """Summarize whether annual reports disclose total labor or function splits."""
    summary = {
        "years": {},
        "years_with_function_split": [],
        "years_with_total_only": [],
        "years_with_no_labor_disclosure": [],
    }
    if not output_dir or not os.path.isdir(output_dir):
        return summary

    for name in sorted(os.listdir(output_dir)):
        m = re.match(r"zone_b_(\d{4})_partial\.json$", name)
        if not m:
            continue
        year = m.group(1)
        path = os.path.join(output_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        labor = data.get("labor_by_function")
        total = safe_float(data.get("employee_benefit_expense_m"))
        has_split = isinstance(labor, dict) and any(
            labor.get(key) is not None for key in ("production", "sales", "admin", "rd", "total")
        )
        if has_split:
            status = "function_split"
            summary["years_with_function_split"].append(year)
        elif total is not None and total > 0:
            status = "total_only"
            summary["years_with_total_only"].append(year)
        else:
            status = "none"
            summary["years_with_no_labor_disclosure"].append(year)
        summary["years"][year] = {
            "status": status,
            "employee_benefit_expense_m": total,
        }

    return summary


def find_stock_output_dir(ts_code: str) -> Optional[str]:
    """Find stock output directory by ts_code prefix."""
    code_base = ts_code.split(".")[0]
    for name in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, name)
        if name.startswith(code_base) and os.path.isdir(path):
            return path
    return None


def _normalize_report_shares_m(raw):
    val = safe_float(raw)
    if val is None or val <= 0:
        return None
    return round(val / 1_000_000, 6) if val > 1_000_000 else round(val, 6)


def _align_report_shares_with_market(report_shares_m: Optional[float], db_shares_m: Optional[float]) -> tuple[Optional[float], str]:
    """Align report-extracted share counts to market scale.

    Some HK-derived pdf_sections store share counts in thousand shares rather than shares.
    """
    if report_shares_m is None:
        return None, "missing_report"
    if not db_shares_m or db_shares_m <= 0:
        return report_shares_m, "report"
    rel_diff = abs(report_shares_m - db_shares_m) / max(report_shares_m, db_shares_m)
    if rel_diff <= 0.5:
        return report_shares_m, "report"
    scaled_report = report_shares_m * 1000.0
    scaled_diff = abs(scaled_report - db_shares_m) / max(scaled_report, db_shares_m)
    if scaled_diff <= 0.5:
        return round(scaled_report, 6), "report_x1000"
    return db_shares_m, "db_fallback"


def _infer_ts_code_from_output_dir(output_dir: Optional[str]) -> Optional[str]:
    if not output_dir:
        return None
    dirname = os.path.basename(output_dir)
    code_part = dirname.split("_")[0] if "_" in dirname else dirname
    # A-shares: 6 digits. SH=600xxx/900xxx, SZ=000xxx/002xxx/300xxx.
    # HK stocks: 4-5 digits, often 0-padded in output dir names (e.g. "00506", "06186").
    if len(code_part) == 5 and code_part.isdigit():
        if code_part.startswith("0"):
            return code_part + ".HK"
        return code_part + ".SH"
    if len(code_part) == 6 and code_part.isdigit():
        if code_part.startswith("6") or code_part.startswith("9"):
            return code_part + ".SH"
        return code_part + ".SZ"
    if len(code_part) == 5 and code_part.isalpha():
        return code_part + ".HK"
    if re.fullmatch(r"\d+[A-Z]+", code_part):
        return code_part + ".DE"
    return code_part or None


def _build_gg_labor_bundle(
    factor3: dict,
    gg_override: Optional[dict],
    labor_disclosure_summary: Optional[dict],
) -> dict:
    summary = labor_disclosure_summary or {}
    bundle = {
        "source": factor3.get("gg_labor_source"),
        "confidence": factor3.get("gg_labor_confidence"),
        "method": factor3.get("gg_labor_method"),
        "explanation": factor3.get("gg_labor_explanation"),
        "capability": factor3.get("gg_labor_capability"),
        "override_applied": factor3.get("gg_override_applied", False),
        "override_years": factor3.get("gg_override_years", []),
        "override_modes": factor3.get("gg_override_modes", []),
        "w1_dedup_years": factor3.get("w_breakdown", {}).get("w1_dedup_years", {}),
        "w2_override_years": factor3.get("w_breakdown", {}).get("w2_override_years", {}),
        "annual_report_total_only_years": summary.get("years_with_total_only", []),
        "annual_report_function_split_years": summary.get("years_with_function_split", []),
        "annual_report_no_labor_disclosure_years": summary.get("years_with_no_labor_disclosure", []),
    }
    if gg_override:
        bundle["gg_override"] = {
            "source_file": os.path.basename(gg_override.get("source_file", "gg_override.json")),
            "years": sorted((gg_override.get("years") or {}).keys()),
            "applied": factor3.get("gg_override_applied", False),
            "applied_years": factor3.get("gg_override_years", []),
            "applied_modes": factor3.get("gg_override_modes", []),
        }
    return bundle


def _extract_report_shares_m_from_markdown(path: str) -> Optional[float]:
    try:
        with open(path) as f:
            text = f.read()
    except Exception:
        return None

    line_patterns = [
        r"(?:期末)?(?:已發行|已发行)?(?:股份總數|股份总数|總股本|总股本|已發行股份|已发行股份|股數|股数)[^0-9]{0,20}([0-9,]{6,})\s*(?:股|shares?)",
        r"(?:已發行及繳足普通股|已发行及缴足普通股)[^0-9]{0,20}([0-9,]{6,})",
        r"股本由报告期初的[0-9,]{6,}股变更为([0-9,]{6,})股",
    ]
    marker_words = ("股份總數", "股份总数", "總股本", "总股本", "已發行股份", "已发行股份", "股數", "股数", "已發行及繳足普通股", "已发行及缴足普通股")
    excluded_words = ("儲備", "储备", "權益", "权益", "股息", "每股", "股本證券", "股本证券", "購股權", "购股权", "上限")
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or any(word in line for word in excluded_words):
            continue
        if not any(word in line for word in marker_words):
            continue
        for pattern in line_patterns:
            match = re.search(pattern, line, flags=re.I)
            if not match:
                continue
            shares_m = _normalize_report_shares_m(str(match.group(1)).replace(",", ""))
            if shares_m and shares_m >= 1:
                return shares_m

    patterns = [
        r"期末总股本\s*([0-9,]{6,})\s*股",
        r"(?:股份总数|股份總數)[^\n]{0,40}?([0-9,]{6,})\s*股",
        r"(?:已发行股份|已發行股份)[^\n]{0,40}?([0-9,]{6,})\s*股",
        r"(?:总股本|總股本)[^\n]{0,40}?([0-9,]{6,})\s*股",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if not matches:
            continue
        for raw in reversed(matches):
            shares_m = _normalize_report_shares_m(str(raw).replace(",", ""))
            if shares_m:
                return shares_m
    return None


def _latest_annual_report_markdown(output_dir: Optional[str]) -> Optional[tuple[int, str]]:
    if not output_dir:
        return None
    candidates = []
    for name in os.listdir(output_dir):
        if re.match(r"\d{4}_年报\.md$", name):
            candidates.append((int(name[:4]), os.path.join(output_dir, name)))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1]


def _extract_annual_report_dividend_plan(output_dir: Optional[str]) -> dict:
    latest = _latest_annual_report_markdown(output_dir)
    if not latest:
        return {}
    year, path = latest
    try:
        with open(path) as f:
            text = f.read()
    except Exception:
        return {}

    result = {"fiscal_year": year}

    # 港股年报通常按「每股人民币/港元 X 元」披露，而不是 A 股的
    # 「每10股派X元」。先提取金额身份和币种，避免后续 DPS 与港币股价
    # 直接相除。末期股息是年报口径的首选锚点。
    hk_per_share_patterns = [
        r"(?:建議|建议)?末期股息每股(人民幣|人民币|港元|港幣|港币)\s*([\d.]+)元",
        r"每股普通股(人民幣|人民币|港元|港幣|港币)\s*([\d.]+)元",
    ]
    currency_map = {
        "人民幣": "RMB", "人民币": "RMB",
        "港元": "HKD", "港幣": "HKD", "港币": "HKD",
    }
    for pattern in hk_per_share_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        val = safe_float(m.group(2))
        if val and val > 0:
            result["final_per_share"] = round(val, 4)
            result["currency"] = currency_map.get(m.group(1), "RMB")
            break

    # Year-anchored patterns use [\s\S]{0,N}? (non-greedy) rather than [^。\n]:
    # the per-share amount frequently sits several sentences after the plan
    # label (separated by 。, dates, and share-base clauses), so a boundary
    # that stops at 。/\n misses it (e.g. 格力 interim). Non-greedy + the
    # specific "每10股派…元" tail keeps it anchored to the nearest amount.
    # The generic 董事会审议 fallback stays [^。\n] (not year-anchored → must
    # not span across into another year's figure).
    final_patterns = [
        rf"{year}年度利润分配(?:预案|方案)[\s\S]{{0,180}}?每10股派(?:发|送)?现金(?:红利|股利)?(?:人民币)?([\d.]+)元",
        rf"{year}年度[\s\S]{{0,80}}?利润分配(?:预案|方案)[\s\S]{{0,180}}?每10股派(?:发|送)?现金(?:红利|股利)?(?:人民币)?([\d.]+)元",
        rf"董事会审议[^。\n]{{0,160}}?每10股派(?:送)?现金(?:红利|股利)?(?:人民币)?([\d.]+)元",
        rf"按每10股派发现金(?:红利|股利)(?:人民币)?([\d.]+)元",
        rf"每10股派息数（元）（含税）\s*([\d.]+)",
    ]
    for pattern in final_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        val = safe_float(m.group(1))
        if val and val > 0:
            result["final_per_share"] = round(val / 10.0, 4)
            break

    interim_patterns = [
        rf"{year}年中期利润分配(?:预案|方案)[\s\S]{{0,220}}?每10股派发现金(?:红利|股利)(?:人民币)?([\d.]+)元",
        rf"{year}年中期[\s\S]{{0,180}}?每10股派发现金(?:红利|股利)(?:人民币)?([\d.]+)元",
        rf"{year}年半年度利润分配(?:预案|方案)[\s\S]{{0,220}}?每10股派发现金(?:红利|股利)(?:人民币)?([\d.]+)元",
        rf"{year}年9月30日[\s\S]{{0,180}}?每10股派发现金(?:红利|股利)(?:人民币)?([\d.]+)元",
    ]
    for pattern in interim_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        val = safe_float(m.group(1))
        if val and val > 0:
            result["interim_per_share"] = round(val / 10.0, 4)
            break

    if "中期" in text and ("合计分红金额" in text or "中期已派发红利金额合计" in text):
        result["mentions_interim"] = True

    return result


def _load_dividend_evidence(output_dir: Optional[str]) -> dict:
    if not output_dir:
        return {}
    path = os.path.join(output_dir, "dividend_evidence.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_dividend_evidence(data: dict) -> dict:
    if not data:
        return {}
    entries = data.get("entries") or []
    valid_entries = []
    for entry in entries:
        per_share = safe_float((entry or {}).get("per_share"))
        if per_share and per_share > 0:
            valid_entries.append(entry)
    if not valid_entries:
        return {}
    total = round(sum(float(entry["per_share"]) for entry in valid_entries), 4)
    return {
        "fiscal_year": data.get("fiscal_year"),
        "currency": data.get("currency") or "RMB",
        "dps_fy": total,
        "entries": valid_entries,
        "source": "dividend_evidence",
        "notes": data.get("notes"),
    }


def _latest_annual_report_shares_m(output_dir: Optional[str]) -> Optional[float]:
    if not output_dir:
        return None
    candidates = []
    for name in os.listdir(output_dir):
        if not (name.startswith("pdf_sections_") and name.endswith(".json")):
            continue
        m = re.match(r"pdf_sections_(\d{4})\.json$", name)
        if not m:
            continue
        year = int(m.group(1))
        path = os.path.join(output_dir, name)
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        financials = data.get("financials") or {}
        for key in ("总股本", "總股本", "期末总股本", "期末總股本", "股份总数", "股份總數", "已发行股份", "已發行股份"):
            raw = financials.get(key)
            shares_m = _normalize_report_shares_m(raw)
            if shares_m:
                candidates.append((year, shares_m, f"{path}:{key}"))
                break

    for name in os.listdir(output_dir):
        if not re.match(r"\d{4}_年报\.md$", name):
            continue
        year = int(name[:4])
        path = os.path.join(output_dir, name)
        shares_m = _extract_report_shares_m_from_markdown(path)
        if shares_m:
            candidates.append((year, shares_m, path))

    # V12.19: Fallback to DB stocks.shares_m when report extraction doesn't
    # contain a usable 总股本 field, and always cross-check extracted values.
    candidates.sort()
    try:
        ts_code = _infer_ts_code_from_output_dir(output_dir)
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
        if ts_code and os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT shares_m FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
            conn.close()
            if row and row[0]:
                db_shares = float(row[0])
                if candidates:
                    latest_year = max(year for year, _, _ in candidates)
                    latest_candidates = [c for c in candidates if c[0] == latest_year]
                    best_candidate = None
                    best_score = None
                    for cand in latest_candidates:
                        aligned_shares, align_mode = _align_report_shares_with_market(cand[1], db_shares)
                        if aligned_shares is None:
                            continue
                        score = abs(aligned_shares - db_shares) / max(aligned_shares, db_shares)
                        if best_score is None or score < best_score:
                            best_candidate = (cand, aligned_shares, align_mode)
                            best_score = score
                    if best_candidate is None:
                        best_candidate = (candidates[-1], candidates[-1][1], "report")
                    latest_entry, aligned_shares, align_mode = best_candidate
                    report_shares = latest_entry[1]
                    if align_mode == "report_x1000":
                        print(
                            f"⚠️ 年报股本({report_shares:.2f}M)疑似按千股披露，已换算为{aligned_shares:.2f}M",
                            file=sys.stderr,
                        )
                        candidates = [(latest_entry[0], aligned_shares, f"{latest_entry[2]} x1000")]
                    elif align_mode == "report":
                        candidates = [(latest_entry[0], aligned_shares, latest_entry[2])]
                    elif align_mode == "db_fallback":
                        print(f"⚠️ 年报股本({report_shares:.2f}M)与DB({db_shares:.2f}M)差异>50%，以DB为准", file=sys.stderr)
                        candidates = [(0, db_shares, "DB stocks table (corrected)")]
                else:
                    candidates.append((0, db_shares, "DB stocks table"))
    except Exception:
        pass

    if not candidates:
        return None
    return candidates[-1][1]


def _ensure_data_source_code(ts_code: str, data_source: str) -> None:
    """V12.19: Ensure data_source_code is set in stocks table.

    If already set and different, warn. If not set, write it.
    """
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT data_source_code FROM stocks WHERE ts_code=?", (ts_code,)
        ).fetchone()
        existing = row[0] if row else None
        if existing and existing != data_source:
            print(f"⚠️  {ts_code} data_source_code 已是 {existing}，忽略 --data-source {data_source}", file=sys.stderr)
        elif not existing:
            conn.execute(
                "UPDATE stocks SET data_source_code=? WHERE ts_code=?", (data_source, ts_code)
            )
            conn.commit()
            print(f"🔗 {ts_code} → {data_source}（已写入 stocks.data_source_code）", file=sys.stderr)
    except sqlite3.OperationalError:
        # Column might not exist in older DBs
        pass
    finally:
        conn.close()


def _inherit_annual_valuation(contract: Optional[dict]) -> Optional[dict]:
    """V12.19: 季度跟踪节点 — 从最新年报 bundle 继承估值锚。

    找到 output_dir 下最新的 annual compute_bundle，
    提取 GG/DDM/P_base 作为 inherited valuation。
    """
    if not contract or not isinstance(contract, dict):
        return None
    ts_code = contract.get("ts_code", "")
    if not ts_code:
        return None
    # 推断 output_dir
    output_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    code_short = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    for entry in os.listdir(output_base) if os.path.isdir(output_base) else []:
        if entry.startswith(code_short) and os.path.isdir(os.path.join(output_base, entry)):
            output_dir = os.path.join(output_base, entry)
            # 找最新的 annual bundle
            candidates = []
            for f in os.listdir(output_dir):
                if 'annual' in f and f.endswith('.json') and f.startswith('compute_bundle'):
                    candidates.append(os.path.join(output_dir, f))
            if candidates:
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                try:
                    with open(candidates[0]) as fh:
                        annual = json.load(fh)
                    f3 = annual.get("factor3", {})
                    f4 = annual.get("factor4", {})
                    inherited = {
                        "source": candidates[0],
                        "gg": f3.get("gg"),
                        "gg_discounted": f3.get("gg_discounted"),
                        "gg_fcfe": f3.get("gg_fcfe"),
                        "ddm_v_hkd": f4.get("ddm_v_hkd"),
                        "ddm_v_rmb": f4.get("ddm_v_rmb"),
                        "p_base": f4.get("p_base"),
                        "buy_ladder": f4.get("buy_ladder"),
                    }
                    return {k: v for k, v in inherited.items() if v is not None}
                except Exception:
                    pass
            break
    return None


def _check_gg_guard(ts_code: str, factor3: dict, market: dict, output_dir: Optional[str] = None) -> Optional[dict]:
    gg_base = safe_float((factor3 or {}).get("gg", {}).get("base"))
    if gg_base is None:
        return None
    if gg_base <= 10.0:
        return {
            "status": "pass",
            "gg_base": round(gg_base, 1),
            "threshold_pct": 10.0,
        }

    report_shares_m = _latest_annual_report_shares_m(output_dir)
    market_shares_m = safe_float((market or {}).get("shares_m"))
    guard = {
        "status": "annual_report_recheck_required",
        "gg_base": round(gg_base, 1),
        "threshold_pct": 10.0,
        "market_shares_m": round(market_shares_m, 6) if market_shares_m else None,
        "annual_report_shares_m": round(report_shares_m, 6) if report_shares_m else None,
    }
    if report_shares_m is None:
        return {
            "error": "gg_base_requires_annual_report_recheck",
            "message": f"GG(base)={gg_base:.1f}% > 10%。必须先复核年报股本/总股本后才能继续。",
            **guard,
        }
    if market_shares_m is None or market_shares_m <= 0:
        return {
            "error": "gg_base_requires_annual_report_recheck",
            "message": f"GG(base)={gg_base:.1f}% > 10%，且 market shares 缺失。必须先复核年报股本/总股本后才能继续。",
            **guard,
        }

    rel_diff = abs(report_shares_m - market_shares_m) / max(report_shares_m, market_shares_m)
    if rel_diff > 0.02:
        return {
            "error": "gg_base_annual_report_share_mismatch",
            "message": (
                f"GG(base)={gg_base:.1f}% > 10%，且年报总股本({report_shares_m:.3f}M)"
                f" 与计算使用股本({market_shares_m:.3f}M)不一致。请先修正年报数字后再执行。"
            ),
            "share_diff_pct": round(rel_diff * 100, 2),
            **guard,
        }

    return {
        "status": "annual_report_rechecked",
        "gg_base": round(gg_base, 1),
        "threshold_pct": 10.0,
        "market_shares_m": round(market_shares_m, 6),
        "annual_report_shares_m": round(report_shares_m, 6),
        "share_diff_pct": round(rel_diff * 100, 2),
        "message": f"GG(base)={gg_base:.1f}% > 10%，已通过年报股本复核。",
    }


def load_from_db(ts_code: str, contract: Optional[dict] = None) -> Optional[dict]:
    """Load financial data from stock_analysis.db. Returns hk_fallback-compatible dict.

    If contract is provided, filters to effective_years (dynamic window from Phase 0).

    V12.19: Supports data_source_code — when a stock (e.g. B-share 900936)
    has no financial data of its own, falls back to the linked A-share code.
    """
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # V12.19: Check for data_source_code (e.g. B-share → A-share financials)
    st_row_original = conn.execute("SELECT * FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
    data_source = ts_code
    if st_row_original and st_row_original["data_source_code"]:
        data_source = st_row_original["data_source_code"]
        print(f"📊 {ts_code}: 使用 {data_source} 的财务数据（data_source_code）", file=sys.stderr)

    rows = conn.execute("""
        SELECT * FROM annual_financials
        WHERE ts_code=? AND report_type='annual'
        ORDER BY fiscal_year
    """, (data_source,)).fetchall()

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
            "minority_profit": r["minority_profit"],
            "income_tax": r["income_tax"],
            "depr_fa_coga_dpba": r["d_a"],  # D&A stored in d_a field
            "oper_cost": r["oper_cost"],
            "sell_dist_exp": r["sell_dist_exp"],
            "admin_exp": r["admin_exp"],
            "other_income": r["other_income"],
            "gov_subsidy": r["gov_subsidy"] if "gov_subsidy" in r.keys() else None,    # V12.8: 政府补助
            "invest_income": r["invest_income"],    # 投资收益
            "total_profit": r["total_profit"],       # 税前利润
        })
        bs.append({
            "end_date": year_str + "1231",
            "money_cap": r["money_cap"],
            "accounts_receiv": r["accounts_receiv"],
            "acct_payable": r["acct_payable"],
            # V12.6: 新增字段（DB列可能不存在，使用 dict 安全访问）
            "employee_cost": r["employee_cost"] if "employee_cost" in r.keys() else None,
            "short_term_investments": r["short_term_investments"] if "short_term_investments" in r.keys() else None,
            "time_deposits": r["time_deposits"] if "time_deposits" in r.keys() else None,
            "short_term_deposits": r["short_term_deposits"] if "short_term_deposits" in r.keys() else None,
            "deferred_assets": r["deferred_assets"] if "deferred_assets" in r.keys() else None,     # V12.9
            "special_reserve": r["special_reserve"] if "special_reserve" in r.keys() else None,     # V12.9
            "contract_liab": r["contract_liab"],
            "total_assets": r["total_assets"],
            "total_liab": r["total_liab"],
            "total_hldr_eqy_exc_min_int": r["total_hldr_eqy_exc_min_int"],
            "goodwill": r["goodwill"],
            "st_borr": r["st_borr"],
            "lt_borr": r["lt_borr"],
            "minority_int": r["minority_int"],
            "inventories": r["inventories"],
            "fix_assets": r["fix_assets"],
            "intang_assets": r["intang_assets"],
        })
        cf.append({
            "end_date": year_str + "1231",
            "n_cashflow_act": r["n_cashflow_act"],
            "c_pay_acq_const_fiolta": -(r["c_pay_acq_const_fiolta"] or 0),  # DB stores absolute value
            "asset_disposal": r["asset_disposal"],
            "interest_received": r["interest_received"],
            "tax_paid": r["tax_paid"],
            "interest_paid": r["interest_paid"],
            "inventory_change": r["inventory_change"],
            "ar_change_cf": r["ar_change_cf"],
            "intangible_purchase": r["intangible_purchase"],
            "gain_asset_sale": r["gain_asset_sale"],
            "impairment_cf": r["impairment_cf"],
            "cash_paid_employees": r["cash_paid_employees"] if "cash_paid_employees" in r.keys() else None,
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

    # Load threshold (V12.19: fall back to data_source)
    th_row = conn.execute("SELECT * FROM thresholds WHERE ts_code=?", (ts_code,)).fetchone()
    if not th_row and data_source != ts_code:
        th_row = conn.execute("SELECT * FROM thresholds WHERE ts_code=?", (data_source,)).fetchone()

    # Load stock info (V12.19: use original ts_code for market data, reuse earlier fetch)
    st_row = st_row_original
    financial_st_row = conn.execute(
        "SELECT currency FROM stocks WHERE ts_code=?",
        (data_source,),
    ).fetchone()

    conn.close()

    return {
        "ts_code": ts_code,
        "currency": (financial_st_row["currency"] if financial_st_row and financial_st_row["currency"] else "RMB"),
        "financial_source_code": data_source,
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
        # V12.6 新增
        "employee_cost", "short_term_investments", "time_deposits", "short_term_deposits",
        "deferred_assets", "special_reserve",  # V12.9
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
    # V12.6 新增
    emp_cost_vals = yearly_array("employee_cost")
    st_inv_vals = yearly_array("short_term_investments")
    td_vals = yearly_array("time_deposits")
    sd_vals = yearly_array("short_term_deposits")
    def_assets_vals = yearly_array("deferred_assets")  # V12.9
    spec_res_vals = yearly_array("special_reserve")    # V12.9
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
            # V12.6 新增
            "employee_cost": emp_cost_vals[i] if i < len(emp_cost_vals) else None,
            "short_term_investments": st_inv_vals[i] if i < len(st_inv_vals) else None,
            "time_deposits": td_vals[i] if i < len(td_vals) else None,
            "short_term_deposits": sd_vals[i] if i < len(sd_vals) else None,
            "deferred_assets": def_assets_vals[i] if i < len(def_assets_vals) else None,
            "special_reserve": spec_res_vals[i] if i < len(spec_res_vals) else None,
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

    # OCF/NP ratio — V12.18: 双口径输出（原始+调整）
    np_match = np_years
    ocf_np_ratios = []
    for i in range(min(len(ocf_years), len(np_match))):
        if np_match[i] and np_match[i] > 0:
            ocf_np_ratios.append(ocf_years[i] / np_match[i])
    result["ocf_np_ratio"] = round(avg_last_n(ocf_np_ratios, 3), 2) if ocf_np_ratios else None
    # 双口径分析
    if ocf_np_ratios:
        raw_mean = round(sum(ocf_np_ratios) / len(ocf_np_ratios), 2)
        sorted_ratios = sorted(ocf_np_ratios)
        raw_median = round(sorted_ratios[len(sorted_ratios)//2], 2)
        result["ocf_np_analysis"] = {
            "raw_mean": raw_mean,
            "raw_median": raw_median,
            "years_used": [r.get("fiscal_year") for i, r in enumerate(inc) if i < len(ocf_np_ratios) and ocf_np_ratios[i] != 0],
            "display_primary": raw_mean,  # 报告应优先展示原始口径
        }
        # 如果原始均值与3y均值差异显著，标注
        if result["ocf_np_ratio"] and abs(result["ocf_np_ratio"] - raw_mean) > 0.15:
            result["ocf_np_analysis"]["caliber_note"] = (
                f"原始均值={raw_mean}，3y均值={result['ocf_np_ratio']}。"
                "差异可能来自扰动调整。报告中必须同时展示两个口径，标注差异来源。"
            )

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

    # V12.8: Normalized OE with maintenance Capex G coefficient (Spec Factor2 Step2)
    # OE_normalized = NP + D&A - D&A×G (只扣维持性Capex, 而非全额Capex)
    # G按capex/rev行业: <3%轻资产→0.85, 3-8%中→1.15, >8%重→1.5
    cr_avg_for_g = sum(capex_ratios[-3:]) / len(capex_ratios[-3:]) if len(capex_ratios) >= 3 else 0.08
    if cr_avg_for_g < 0.03:
        G_coef = 0.85; G_label = "轻资产"
    elif cr_avg_for_g < 0.08:
        G_coef = 1.15; G_label = "中等资产"
    else:
        G_coef = 1.5; G_label = "重资产"
    oe_norm = []
    for i in range(min(len(np_years), len(d_a_years))):
        oe_n = np_years[i] + d_a_years[i] - d_a_years[i] * G_coef
        oe_norm.append(max(oe_n, 0))
    result["oe_norm_avg_3y"] = round(avg_last_n(oe_norm, 3), 2) if oe_norm else None
    result["oe_norm_avg_5y"] = round(avg(oe_norm), 2) if oe_norm else None
    result["oe_maintenance_G"] = {"coefficient": G_coef, "category": G_label, "capex_rev_pct": round(cr_avg_for_g * 100, 1),
                                   "note": "Normalized OE = NP+D&A-D&A×G (仅扣维持性Capex)。保守OE = NP+D&A-全额Capex（更保守）"}

    # V12.10: 可预测性 P = conservative_rev × historical_min_margin (Spec Factor2 Step6)
    rev_vals = rev_years[-3:] if len(rev_years) >= 3 else rev_years
    margins = [safe_float(r.get("gross_margin"), 0) or (r.get("gross_profit", 0) / max(r.get("revenue", 1), 1)) for r in inc]
    margins_3y = margins[-3:] if len(margins) >= 3 else margins
    conservative_rev = min(rev_vals) if rev_vals else 0
    historical_min_margin = min(margins_3y) if margins_3y else 0
    predictability_p = conservative_rev * historical_min_margin
    result["predictability"] = {
        "conservative_revenue": round(conservative_rev, 2),
        "historical_min_margin_pct": round(historical_min_margin * 100, 1),
        "predictable_np_floor": round(predictability_p, 2),
        "formula": "P = min(revenue_3y) × min(gross_margin_3y)",
        "note": "保守收入×历史最低利润率=利润底线。若实际NP<P→显著恶化"
    }

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

    # V12.7: M_signal — DPS 增长 >15% 向上修正 M（Spec Module 0(8) Rule 2）
    # 管理层大幅提升分红是"释放信号"，具有粘性
    if len(dps_years) >= 2:
        dps_latest = dps_years[-1] if dps_years[-1] else 0
        dps_prev = dps_years[-2] if dps_years[-2] else 1
        if dps_prev > 0 and dps_latest / dps_prev > 1.15:
            m_signal = dps_latest / np_years[-1] if np_years[-1] and np_years[-1] > 0 else None
            if m_signal and 0.05 < m_signal < 1.2:
                m_signal = min(m_signal, 1.0)
                if m_signal > result["M"]:
                    result["M"] = round(m_signal, 4)
                    result["M_source"] = "signal_dps_increase_gt_15pct"
                    result["M_signal_triggered"] = True

    # R(NP)_raw = NP_avg_3y / Market_Cap (裸收益率, 诊断用)
    mc = market.get("mc_rmb", 0)
    if mc > 0 and np_avg_3y:
        result["r_np"] = round(_d_ratio_pct(np_avg_3y, mc), 2)
    else:
        result["r_np"] = None

    # R(OE)_raw = OE_avg_3y / Market_Cap (裸收益率, 诊断用)
    oe_avg = result.get("oe_avg_3y")
    if mc > 0 and oe_avg:
        result["r_oe"] = round(_d_ratio_pct(oe_avg, mc), 2)
    else:
        result["r_oe"] = None

    # ── V12.5: 穿透回报率 (Spec v0.15 Factor2 Step8) ──
    # R(NP)_penetration = [NP × M × (1-Q) + O] / MC → 股东视角穿透回报率
    M_val = result.get("M", 0.55)
    Q = params.get("Q", 0.10)
    O_val = params.get("O", 0)
    if mc > 0 and np_avg_3y:
        result["r_np_penetration"] = round(_d_penetration_pct(np_avg_3y, M_val, Q, O_val, mc), 2)
    else:
        result["r_np_penetration"] = None
    if mc > 0 and oe_avg:
        result["r_oe_penetration"] = round(_d_penetration_pct(oe_avg, M_val, Q, O_val, mc), 2)
    else:
        result["r_oe_penetration"] = None

    # Distribution check: FCF consistently positive and net financing negative
    # V12.18: 控股公司豁免 — 若投资收入为主要利润来源，用投资收入替代OCF
    invest_income_years = [safe_float(r.get("invest_income"), 0) for r in inc]
    is_holding_co = any(
        invest_income_years[i] > np_years[i] * 0.5
        for i in range(min(len(invest_income_years), len(np_years)))
        if np_years[i] and np_years[i] > 0
    ) if len(invest_income_years) >= 3 and len(np_years) >= 3 else False

    fcf_years = []
    financing_years = []
    for i in range(min(len(ocf_years), len(capex_years))):
        if is_holding_co and i < len(invest_income_years):
            # 控股公司：用投资收入(真实现金流入)替代OCF做FCF计算
            fcf = invest_income_years[i] - capex_years[i]
        else:
            fcf = ocf_years[i] - capex_years[i]
        fcf_years.append(fcf)
    if is_holding_co:
        result["holding_co_fcf_adjustment"] = True

    # V12.18: 框架局限性检测 — 自动识别Turtle模型不适配的公司类型
    limitations = []
    # (a) 控股/投资平台
    if is_holding_co:
        limitations.append({
            "type": "holding_company",
            "severity": "medium",
            "note": "利润主要来自投资收入而非经营活动。Turtle的OCF/AA路径基于经营现金流假设，对此类公司部分失效。FCF已用投资收入重算，但AA仍基于OCF。GG仅供参考，最终判断以定性分析为准。"
        })
    # (b) 轻资产服务/低OCF率
    ocf_rev_ratios = [ocf_years[i] / rev_years[i] for i in range(min(len(ocf_years), len(rev_years))) if rev_years[i] and rev_years[i] > 0]
    if len(ocf_rev_ratios) >= 2 and np_avg_3y and np_avg_3y > 0:
        avg_ocf_rev = sum(ocf_rev_ratios[-3:]) / len(ocf_rev_ratios[-3:])
        if avg_ocf_rev < 0.10:
            limitations.append({
                "type": "low_ocf_revenue",
                "severity": "medium",
                "note": f"OCF/收入仅{avg_ocf_rev*100:.0f}%，属于轻资产服务/物业类型。AA保守路径(W倒挤+全额扣Capex)可能严重低估真实自由现金流。请以FCFE GG(绕开W)为主要参考。"
            })
    # (c) 零分红/极低分红
    dps_val = params.get("DPS") or params.get("dps_fy", 0)
    payout = 0
    if dps_val and dps_val > 0 and np_avg_3y and np_avg_3y > 0:
        sh_m = params.get("shares_m", 0) or (market.get("shares_m", 0) if isinstance(market, dict) else 0)
        if sh_m > 0:
            payout = dps_val / (np_avg_3y / sh_m)
    if dps_val is None or (isinstance(dps_val, (int, float)) and dps_val < 0.01):
        limitations.append({
            "type": "zero_dividend",
            "severity": "high",
            "note": "公司不支付或极少支付股息。DDM模型完全失效(公允价≈0)，P_base和FCFE GG是唯一可用的估值参考。股息率为0不代表公司无价值——可能是利润全部用于再投资。"
        })
    elif payout < 0.15:
        limitations.append({
            "type": "low_payout",
            "severity": "low",
            "note": f"派息率仅{payout*100:.0f}%，DDM公允价可能显著低估。请同时参考P_base(GG/II折现公允价)和FCFE视角。"
        })
    # (d) OCF极端波动(强周期)
    ocf_vals_clean = [o for o in ocf_years[-5:] if o != 0]
    if len(ocf_vals_clean) >= 4:
        ocf_mean = sum(ocf_vals_clean) / len(ocf_vals_clean)
        ocf_std = (sum((o - ocf_mean) ** 2 for o in ocf_vals_clean) / len(ocf_vals_clean)) ** 0.5
        ocf_cv = ocf_std / abs(ocf_mean) if abs(ocf_mean) > 0 else 0
        if ocf_cv > 1.0:
            limitations.append({
                "type": "cyclical_ocf",
                "severity": "medium",
                "note": f"近5年OCF波动极大(CV={ocf_cv:.1f})。当前GG可能反映周期位置而非可持续水平。请结合Ch4(周期位置)和Ch9(风险)判断当前是周期底部还是结构性问题。"
            })
    if limitations:
        result["framework_limitations"] = limitations
    # V9.2: FCF positivity check — uses all available years (already filtered by contract)
    result["fcf_positive_window"] = all(f > 0 for f in fcf_years) if len(fcf_years) >= 3 else None
    # V12.8: Spec Factor2 Step3 — FCF持续负 AND 融资CF持续正 → 否决分配能力
    fin_cf_years = [safe_float(r.get("n_cash_flows_fnc_act"), 0) for r in cf]
    fcf_all_negative = all(f < 0 for f in fcf_years[-3:]) if len(fcf_years) >= 3 else False
    fin_cf_all_positive = all(f > 0 for f in fin_cf_years[-3:]) if len(fin_cf_years) >= 3 else False
    result["distribution_pass"] = (
        result["fcf_positive_window"]  # FCF all positive → pass
        and not (fcf_all_negative and fin_cf_all_positive)  # FCF all neg + financing all pos → fail
    )

    # V12.18: 扰动豁免 — 区分一次性经营扰动 vs 持续性恶化
    perturbation_waiver = False
    if not result["distribution_pass"] and len(ocf_years) >= 3 and len(np_years) >= 3:
        ocf_np_ratios = [ocf_years[i] / np_years[i] if np_years[i] and np_years[i] > 0 else 0
                         for i in range(len(ocf_years))]
        inv_years = [safe_float(r.get("inventories"), 0) for r in bs] if bs else []
        # 检测异常年：OCF/NP < 0.3 且其他年份 OCF/NP 均值 > 0.8
        anomalous_years = []
        for i in range(len(ocf_np_ratios)):
            if ocf_np_ratios[i] < 0.3:
                other_ratios = [ocf_np_ratios[j] for j in range(len(ocf_np_ratios)) if j != i]
                other_mean = sum(other_ratios) / len(other_ratios) if other_ratios else 0
                # 检查是否有一次性原因：存货异常增加(ΔInventory > 50% YoY)
                inv_spike = False
                if i > 0 and i < len(inv_years) and inv_years[i-1] and inv_years[i-1] > 0:
                    inv_chg = abs(inv_years[i] - inv_years[i-1]) / inv_years[i-1]
                    inv_spike = inv_chg > 0.5
                if other_mean > 0.8:
                    anomalous_years.append({
                        "year_idx": i,
                        "ocf_np": round(ocf_np_ratios[i], 2),
                        "other_mean": round(other_mean, 2),
                        "inventory_spike": inv_spike,
                    })
        if anomalous_years:
            # 剔除异常年后，剩余年份 FCF 是否全正？
            remaining_fcf = [fcf_years[i] for i in range(len(fcf_years)) if i not in {a["year_idx"] for a in anomalous_years}]
            remaining_pass = all(f > 0 for f in remaining_fcf) if len(remaining_fcf) >= 2 else False
            if remaining_pass:
                perturbation_waiver = True
                result["perturbation_waiver"] = {
                    "active": True,
                    "anomalous_years": anomalous_years,
                    "note": "检测到一次性经营扰动(OCF/NP异常低)，剔除后FCF恢复正常。S2降级为warn而非fail。"
                }

    if perturbation_waiver:
        result["distribution_pass"] = True
        result["rejection"]["s2"] = "warn"  # 扰动豁免，降级
    else:
        result["rejection"]["s2"] = "pass" if result.get("distribution_pass") else "fail"

    # Rejection checks — use penetration return (Spec v0.15: 否决门使用穿透回报率)
    II = params.get("II", 5.5)
    Rf = params.get("Rf", 4.0)
    r_penetration = result.get("r_np_penetration")  # V12.5: 改用穿透回报率做否决判断
    # V12.18: S2 已在上面处理（含扰动豁免逻辑），此处不重复赋值
    if r_penetration is not None:
        # 因子2 粗算否决门 (官方 Spec 4 级)
        if r_penetration < Rf:
            result["rejection"]["factor2_gate"] = "veto"  # ① R < Rf → 否决
        elif r_penetration < II * 0.5:
            result["rejection"]["factor2_gate"] = "veto"  # ② Rf ≤ R < II×0.5 → 否决
        elif r_penetration < II:
            result["rejection"]["factor2_gate"] = "marginal"  # ③ II×0.5 ≤ R < II → 边际不达标
        else:
            result["rejection"]["factor2_gate"] = "pass"  # ④ R ≥ II → 通过
        result["rejection"]["s4_1"] = "fail" if r_penetration < Rf else "pass"
        result["rejection"]["s4_2"] = "fail" if r_penetration < II * 0.5 else "pass"
    else:
        result["rejection"]["s4_1"] = "unknown"
        result["rejection"]["s4_2"] = "unknown"

    return result


# ── V12.7: 外推可信度辅助函数 ──

def _compute_profit_adjustment_rating(params: dict, np_avg_3y: float | None) -> dict:
    """从 Zone J earnings_quality 读取非经常项调整幅度，动态判断利润调整偏差评级。"""
    eq = params.get("_earnings_quality", {})
    if not eq or not isinstance(eq, dict):
        return {"rating": "high", "note": "默认假设利润调整偏差<5%。无Zone J数据覆盖"}
    nri = eq.get("non_recurring_items", {})
    if not isinstance(nri, dict):
        return {"rating": "high", "note": "默认假设利润调整偏差<5%。数据格式不匹配"}
    net_adj = abs(nri.get("net_adjustment_m", 0) or 0)
    np_val = abs(np_avg_3y) if np_avg_3y and np_avg_3y > 0 else 1
    pct = net_adj / np_val
    rating = "high" if pct < 0.05 else ("medium" if pct < 0.15 else "low")
    return {"net_adjustment_m": round(net_adj, 2), "pct_of_np": round(pct * 100, 1),
            "rating": rating, "source": "Zone J earnings_quality"}


def _compute_business_change_rating(params: dict, inc: list[dict]) -> dict:
    """从 Zone B mda.json strategy_changes 数量判断商业模式变化程度。"""
    mda = params.get("_mda", {})
    if not mda or not isinstance(mda, dict):
        return {"rating": "high", "note": "默认无重大商业模式变化。无Zone B数据"}
    strategy_text = str(mda.get("strategy_changes", ""))
    change_count = strategy_text.count("FY20")
    rating = "high" if change_count <= 2 else ("medium" if change_count <= 5 else "low")
    return {"strategy_change_entries": change_count, "rating": rating, "source": "Zone B mda.json"}


def _check_ev_pass_conditions(factor2_M: float | None, dps_vals: list, current_M: float) -> dict:
    """V12.10/V12.11: EV双轨通过条件 (Spec Module 0(8) Dual-track pass conditions)."""
    # 条件1: 近3年派息率波动 < 5pct (stable payout)
    payout_stable = False
    if factor2_M and current_M > 0:
        payout_stable = abs(factor2_M - current_M) / max(current_M, 0.01) < 0.05 if current_M > 0 else False
    # 条件2: DPS信号增长 (已有V12.7 M_signal检测)
    dps_signal = False
    if len(dps_vals) >= 2 and dps_vals[-1] and dps_vals[-2]:
        dps_signal = dps_vals[-1] / max(dps_vals[-2], 0.01) > 1.15
    # 条件3: 明确分红政策 — V12.11: 从 Zone B governance.json 读取
    explicit_policy = None  # 待 Zone B 或 Agent 填充
    can_pass = payout_stable or dps_signal  # explicit_policy需Agent确认后手动标记
    return {
        "payout_stable_3y": payout_stable,
        "dps_signal_increase": dps_signal,
        "explicit_policy_known": explicit_policy,
        "can_pass_auto": can_pass,  # 仅基于可程序化条件
        "can_pass": can_pass,       # Agent可手动改为True若Zone B发现明确分红政策
        "note": "EV双轨通过需R_EV≥II AND (派息率稳定 OR DPS信号 OR 明确分红政策)。明确分红政策需从governance.json dividend_policy_stated字段读取→Agent在Ch14中综合判断"
    }


# ── Factor 3: Bottom-Up Fine GG ──

def compute_factor3(fin_data: dict, market: dict, params: dict, factor2_M: float | None = None,
                    factor2_r_np: float | None = None, factor2_r_np_penetration: float | None = None,
                    gg_override: Optional[dict] = None,
                    labor_disclosure_summary: Optional[dict] = None) -> dict:
    """Factor 3:穿透回报率精算 (Bottom-Up). Steps 1-13.

    Args:
        factor2_M: 从 factor2 传入的 M 系数（G系数/支付率）。
                   如果不传，回退到 0.55 默认值。
        factor2_r_np: 裸 R(NP) — 仅用于向后兼容。
        factor2_r_np_penetration: V12.5 穿透 R(NP) = NP×M×(1-Q)+O / MC — 用于 HH 偏离检测。
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

    # ── Factor 3 Steps 1-7: AA (真实可支配现金结余) ──
    # 官方 Spec: 真实现金收入 → 分类调整 → 全额扣除 Capex → AA

    # Step 1: 真实现金收入还原 (S - ΔAR↑ - ΔContract↓)
    cash_revenue = []
    for i in range(n):
        ar_delta = ar[i] - ar[i-1] if i > 0 else 0
        ct_delta = contract[i] - contract[i-1] if i > 0 else 0
        cr = rev[i] - max(0, ar_delta) - max(0, -ct_delta)
        cash_revenue.append(cr)

    # Step 3: V (非经常性) — DB 细项 or 保守默认
    asset_disposals = [safe_float(r.get("asset_disposal"), 0) for r in cf]
    interest_received = [safe_float(r.get("interest_received"), 0) for r in cf]
    other_income_vals = [safe_float(r.get("other_income"), 0) for r in inc]
    # V12.8: V2 政府补助从 DB 读取（若有）
    gov_subsidy = [safe_float(r.get("gov_subsidy"), 0) for r in inc]
    V2 = gov_subsidy  # 政府补助 (V2) — 非持续性，扣除
    V3 = [0] * n      # 保险理赔 (V3) — 无DB数据
    V4 = [0] * n      # 其他一次性非投资流入 (V4) — 无DB数据
    V1 = asset_disposals  # 资产处置 (V1) — 保留
    V5 = [interest_received[i] + other_income_vals[i] for i in range(n)]  # 投资收入 (V5) — 保留
    V_deduct = [V2[i] + V3[i] + V4[i] for i in range(n)]

    # Step 4: W (经营支出) — V12.7 逐项法 + SG&A 代理
    # W = W1(供应商) + W2(员工) + W3(税款) + W4(利息)
    tax_paid_cf = [safe_float(r.get("tax_paid"), 0) for r in cf]
    interest_paid_cf = [safe_float(r.get("interest_paid"), 0) for r in cf]
    employee_cost = [safe_float(r.get("employee_cost"), 0) for r in inc]
    admin_exp_vals = [safe_float(r.get("admin_exp"), 0) for r in inc]
    sell_dist_vals = [safe_float(r.get("sell_dist_exp"), 0) for r in inc]
    rd_exp_vals = [safe_float(r.get("rd_exp"), 0) for r in inc]
    oper_cost = [safe_float(r.get("oper_cost"), 0) for r in inc]

    # W2: 员工成本四层回退 (V12.8)
    # L1: cash_paid_employees (CSMAR A股 CF直接法-支付给职工, 72K行覆盖)
    # L2: employee_cost (DB列, 港股几乎无数据)
    # L3: SG&A 代理 = admin_exp + sell_dist_exp (港股代理, 120K行覆盖)
    # L4: 倒挤法 = rev - OCF + interest + tax (纯fallback)
    cash_paid_emp = [safe_float(r.get("cash_paid_employees"), 0) for r in cf]
    use_csmar = not all(abs(v) < 1 for v in cash_paid_emp)
    use_db_employee = not all(abs(ec) < 1 for ec in employee_cost)
    use_sga_proxy = not all(abs(v) < 1 for v in [*(admin_exp_vals or []), *(sell_dist_vals or []), *(rd_exp_vals or [])])

    if use_csmar:
        w2_source = "CSMAR_cash_paid_employees"
        W2_employee = cash_paid_emp
    elif use_db_employee:
        w2_source = "DB_employee_cost"
        W2_employee = employee_cost
    elif use_sga_proxy:
        w2_source = "SGA_proxy"
        # V12.19 fix: cap at rev×50% instead of rev×25%.
        # The old 25% cap systematically understated expenses for high-marketing
        # consumer companies (e.g. milk powder at 49% SG&A/revenue), inflating AA.
        # 50% is a safety cap — anything above is likely a data error.
        sga_ratios = [(admin_exp_vals[i] + sell_dist_vals[i] + rd_exp_vals[i]) / max(rev[i], 1) for i in range(n)]
        high_sga_years = [i for i in range(n) if sga_ratios[i] > 0.35]
        W2_employee = [
            min(admin_exp_vals[i] + sell_dist_vals[i] + rd_exp_vals[i], rev[i] * 0.50)
            for i in range(n)
        ]
        if high_sga_years:
            hs = ", ".join(str(inc[iy]['end_date'][:4]) for iy in high_sga_years if iy < len(inc))
            print(f"  ⚠️  SGA/Rev>35% in FY {hs} — W2 uses SGA proxy (cap 50%). "
                  f"Consider OCF-based AA for cross-validation.", file=sys.stderr)
    else:
        w2_source = "reverse_squeeze"
        W2_employee = [0] * n  # placeholder, handled in W loop

    base_w2_source = w2_source
    override_years = (gg_override or {}).get("years", {}) if isinstance(gg_override, dict) else {}

    # V12.20+: W1 去重 — 服务业/外包密集行业的 oper_cost 可能包含直接人工，
    # 与 W2(员工总支出) 重叠。优先使用 gg_override.json 中的附注事实，
    # 否则回退到行业启发式推断 direct labor。
    W1_supplier = []
    oper_cost_ratios = [oper_cost[i] / max(rev[i], 1) for i in range(n)]
    can_dedup_w1 = w2_source in {"CSMAR_cash_paid_employees", "DB_employee_cost"}
    service_years = [i for i in range(n) if oper_cost_ratios[i] > 0.8 and can_dedup_w1]
    w1_dedup_years = {}
    w2_override_years = {}
    for i in range(n):
        oc = oper_cost[i]
        year = years[i]
        override_entry = override_years.get(year)
        total_labor_override = safe_float(override_entry.get("total_labor_cost")) if override_entry else None
        can_use_pdf_total_labor = (
            override_entry is not None
            and base_w2_source == "SGA_proxy"
            and total_labor_override is not None
        )
        if can_use_pdf_total_labor:
            W2_employee[i] = max(0, total_labor_override)
            w2_override_years[year] = {
                "source": "pdf_total_labor_override",
                "total_labor_cost": round(W2_employee[i], 2),
                "confidence": override_entry.get("confidence", "medium"),
                "notes_basis": override_entry.get("notes_basis"),
                "source_pages": override_entry.get("source_pages") or [],
            }

        if override_entry and override_entry.get("direct_labor_cost") is not None and (can_dedup_w1 or can_use_pdf_total_labor):
            direct_labor_in_cogs = max(0, safe_float(override_entry.get("direct_labor_cost"), 0))
            oc = max(0, oper_cost[i] - direct_labor_in_cogs)
            w1_dedup_years[year] = {
                "source": "pdf_override",
                "confidence": override_entry.get("confidence", "medium"),
                "direct_labor_cost": round(direct_labor_in_cogs, 2),
                "total_labor_cost": round(W2_employee[i], 2) if can_use_pdf_total_labor else total_labor_override,
                "notes_basis": override_entry.get("notes_basis"),
                "source_pages": override_entry.get("source_pages") or [],
            }
        elif override_entry and can_dedup_w1:
            sales_labor = max(0, safe_float(override_entry.get("sales_labor_cost"), 0))
            admin_labor = max(0, safe_float(override_entry.get("admin_labor_cost"), 0))
            rd_labor = max(0, safe_float(override_entry.get("rd_labor_cost"), 0))
            total_labor = safe_float(override_entry.get("total_labor_cost"))
            note_components = sales_labor + admin_labor + rd_labor
            if total_labor is not None and total_labor >= note_components:
                direct_labor_in_cogs = max(0, total_labor - note_components)
                hybrid_basis = "note total labor minus note sales/admin/rd labor"
            else:
                direct_labor_in_cogs = max(0, W2_employee[i] - note_components)
                hybrid_basis = "DB total employee cash minus note sales/admin/rd labor"
            oc = max(0, oper_cost[i] - direct_labor_in_cogs)
            w1_dedup_years[year] = {
                "source": "hybrid_override",
                "confidence": override_entry.get("confidence", "medium"),
                "direct_labor_cost": round(direct_labor_in_cogs, 2),
                "notes_basis": f"{override_entry.get('notes_basis')}; {hybrid_basis}",
                "source_pages": override_entry.get("source_pages") or [],
            }
        elif i in service_years:
            # 服务业: oper_cost 含直接人工，与 W2 重叠。无附注时回退行业启发式。
            sga_emp = admin_exp_vals[i] + sell_dist_vals[i] + rd_exp_vals[i]  # 行政+销售+研发员工
            direct_labor_in_cogs = max(0, W2_employee[i] - sga_emp)  # 营业成本中的人工
            oc = max(0, oper_cost[i] - direct_labor_in_cogs)
            w1_dedup_years[year] = {
                "source": "industry_heuristic",
                "confidence": "medium" if use_csmar else "low",
                "direct_labor_cost": round(direct_labor_in_cogs, 2),
                "notes_basis": "estimated as total employee cash minus sales/admin/R&D labor proxy",
                "source_pages": [],
            }
        ap_delta = ap[i] - ap[i-1] if i > 0 else 0
        W1_supplier.append(oc - ap_delta)
    if w1_dedup_years:
        sy = ", ".join(sorted(w1_dedup_years.keys()))
        print(f"  🔧 W1去重(FY {sy}): 排除 direct labor 与 W2 重叠", file=sys.stderr)
    if w2_override_years and base_w2_source == "SGA_proxy":
        sy = ", ".join(sorted(w2_override_years.keys()))
        print(f"  🔁 W2升级(FY {sy}): SGA proxy → pdf total labor", file=sys.stderr)

    w2_source_label = base_w2_source
    if w2_override_years and base_w2_source == "SGA_proxy":
        w2_source_label = "SGA_proxy+pdf_total_labor_override"

    W = []
    for i in range(n):
        if base_w2_source == "reverse_squeeze":
            w_i = rev[i] - ocf[i] + interest_paid_cf[i] + tax_paid_cf[i]
        else:
            w_i = W1_supplier[i] + W2_employee[i] + interest_paid_cf[i] + tax_paid_cf[i]
        W.append(w_i)

    dedup_sources = {meta["source"] for meta in w1_dedup_years.values()}
    if "pdf_override" in dedup_sources and len(dedup_sources) == 1:
        gg_labor_source = "pdf_override"
        gg_labor_confidence = "high" if all(meta.get("confidence") == "high" for meta in w1_dedup_years.values()) else "medium"
        gg_labor_explanation = "W1 direct labor dedup uses annual-report note facts from gg_override.json."
    elif "hybrid_override" in dedup_sources and len(dedup_sources) == 1:
        gg_labor_source = "hybrid_override"
        gg_labor_confidence = "medium"
        gg_labor_explanation = "W1 direct labor dedup uses annual-report SG&A/R&D labor facts plus DB total employee cash."
    elif "pdf_override" in dedup_sources:
        gg_labor_source = "mixed"
        gg_labor_confidence = "medium"
        gg_labor_explanation = "Some years use gg_override.json direct labor facts; remaining years use hybrid or heuristic fallback."
    elif "hybrid_override" in dedup_sources:
        gg_labor_source = "mixed"
        gg_labor_confidence = "medium"
        gg_labor_explanation = "Some years use annual-report SG&A/R&D labor facts plus DB total employee cash; remaining years fall back to industry heuristic."
    elif "industry_heuristic" in dedup_sources:
        gg_labor_source = "industry_heuristic"
        gg_labor_confidence = "medium" if use_csmar else "low"
        gg_labor_explanation = "Service-company direct labor estimated from total employee cash minus sales/admin/R&D labor proxy."
    else:
        gg_labor_source = "db_proxy"
        gg_labor_confidence = "low"
        gg_labor_explanation = "No direct-labor note override available; W remains on database/default proxy path."

    labor_disclosure_summary = labor_disclosure_summary or {}
    total_only_years = sorted(labor_disclosure_summary.get("years_with_total_only") or [])
    function_split_years = sorted(labor_disclosure_summary.get("years_with_function_split") or [])
    no_disclosure_years = sorted(labor_disclosure_summary.get("years_with_no_labor_disclosure") or [])
    override_applied = bool(w1_dedup_years or w2_override_years)
    override_years = sorted(set(w1_dedup_years.keys()) | set(w2_override_years.keys()))
    override_modes = sorted(
        {meta.get("source") for meta in list(w1_dedup_years.values()) + list(w2_override_years.values()) if meta.get("source")}
    )

    if gg_labor_source == "db_proxy":
        if total_only_years:
            gg_labor_capability = "annual_report_total_only"
            gg_labor_explanation = (
                f"Annual report discloses total labor only in FY {', '.join(total_only_years)}; "
                "without function split, override cannot be safely applied and W remains on proxy path."
            )
        elif no_disclosure_years:
            gg_labor_capability = "no_report_labor_disclosure"
        else:
            gg_labor_capability = "db_proxy_only"
    elif gg_labor_source == "pdf_override":
        gg_labor_capability = "function_split_available"
    elif gg_labor_source == "hybrid_override":
        gg_labor_capability = "partial_function_split"
    elif gg_labor_source == "industry_heuristic":
        gg_labor_capability = "heuristic_only"
    else:
        gg_labor_capability = "mixed"

    result["gg_labor_source"] = gg_labor_source
    result["gg_labor_confidence"] = gg_labor_confidence
    result["gg_labor_method"] = "pdf_override > hybrid_override > industry_heuristic > db_proxy"
    result["gg_labor_explanation"] = gg_labor_explanation
    result["gg_labor_capability"] = gg_labor_capability
    result["gg_override_applied"] = override_applied
    result["gg_override_years"] = override_years
    result["gg_override_modes"] = override_modes

    result["w_breakdown"] = {
        "method": f"V12.8: W1(供应商-ΔAP)+W2({w2_source_label})+W3(税)+W4(利息)",
        "W1_supplier_avg": round(avg(W1_supplier), 2) if W1_supplier else None,
        "W2_employee_avg": round(avg(W2_employee), 2) if W2_employee and any(abs(ec) > 1 for ec in W2_employee) else None,
        "W2_source": w2_source_label,
        "W3_tax_avg": round(avg(tax_paid_cf), 2) if tax_paid_cf else None,
        "W4_interest_avg": round(avg(interest_paid_cf), 2) if interest_paid_cf else None,
        "sga_used": base_w2_source == "SGA_proxy",
        "service_company_w1_dedup": len(w1_dedup_years) > 0,
        "service_years": ", ".join(sorted(w1_dedup_years.keys())) if w1_dedup_years else None,
        "w2_override_years": w2_override_years,
        "w1_dedup_years": w1_dedup_years,
        "override_applied": override_applied,
        "override_years": override_years,
        "override_modes": override_modes,
        "gg_labor_source": gg_labor_source,
        "gg_labor_confidence": gg_labor_confidence,
        "gg_labor_capability": gg_labor_capability,
        "annual_report_total_only_years": total_only_years,
        "annual_report_function_split_years": function_split_years,
        "annual_report_no_labor_disclosure_years": no_disclosure_years,
        # V12.19: SGA/Rev ratio for cross-validation
        "sga_rev_ratio_avg": round(avg(sga_ratios) * 100, 1) if base_w2_source == "SGA_proxy" and any(r > 0.35 for r in sga_ratios) else None,
        "sga_cap_note": "V12.19: SGA cap=50%(was 25%). OCF-based AA provides cross-validation." if base_w2_source == "SGA_proxy" and any(r > 0.35 for r in sga_ratios) else None,
    }

    # Step 5: Y = Capex(E) + 投资购买(X1) + 隐性支出(X2)
    intangible_purchases = [abs(safe_float(r.get("intangible_purchase"), 0)) for r in cf]
    X1 = intangible_purchases  # 投资购买 (无形资产)
    X2 = [0] * n  # 隐性支出 (无 DB 数据, 默认 0)
    mcapex_pct = params.get("mcapex_split_pct")
    if mcapex_pct is None:
        mcapex_pct = 1.0
    elif isinstance(mcapex_pct, dict):
        mcapex_pct = mcapex_pct.get("value", 1.0)
    mcapex_pct = min(max(float(mcapex_pct) / 100 if float(mcapex_pct) > 1 else float(mcapex_pct), 0), 1.0)
    if mcapex_pct > 1:
        mcapex_pct = mcapex_pct / 100

    # Step 7: 年度结余 = 真实现金收入 + V1 + V5 - V_deduct - W - Y
    aa_values = []
    aa_ocf_based = []
    annual_surplus = []
    for i in range(n):
        Y = capex[i] + X1[i] + X2[i]  # 全额扣除
        surplus = cash_revenue[i] + V1[i] + V5[i] - V_deduct[i] - W[i] - Y
        annual_surplus.append(surplus)
        aa_values.append(max(surplus, 0))
        aa_ocf_based.append(max(ocf[i] - capex[i] * mcapex_pct, 0))
        result["aa"][year_keys[i]] = round(surplus, 2)

    result["aa_detail"] = {
        "annual_surplus": {yk: round(s, 2) for yk, s in zip(year_keys, annual_surplus)},
        "V1_avg": round(avg(asset_disposals), 2),
        "V5_avg": round(avg(V5), 2),
        "W_avg": round(avg(W), 2) if W else None,
    }

    result["mcapex_split_used"] = round(mcapex_pct, 2) if mcapex_pct < 1.0 else None

    # ── V12.20 Step 3: 非经常性收入过滤 ──
    # 原版 Spec: (V1+V5)/OCF > 50% 标记为"非经营收入主导年"
    non_op_years = []
    for i in range(n):
        if ocf[i] > 0 and (asset_disposals[i] + V5[i]) > ocf[i] * 0.5:
            non_op_years.append(i)
    if non_op_years:
        ny = ", ".join(str(inc[iy]['end_date'][:4]) for iy in non_op_years if iy < len(inc))
        print(f"  ⚠️  FY {ny}: 非经常性收入>OCF的50%，AA_excl将排除这些年份", file=sys.stderr)

    # AA_incl vs AA_excl: 剔除异常年份
    aa_incl_3y = round(avg_last_n(aa_values, 3), 2)
    aa_incl_all = round(avg(aa_values), 2)
    # V12.20: AA_excl — 剔除非经营收入主导年
    aa_values_excl = [aa_values[i] for i in range(n) if i not in non_op_years] if non_op_years else aa_values[:]
    aa_excl_3y = round(avg_last_n(aa_values_excl, 3), 2) if len(aa_values_excl) >= 3 else aa_incl_3y
    # 原版 Spec Step 7: |diff|/min > 30% → 用 AA_excl
    use_excl = False
    if non_op_years and aa_excl_3y > 0 and aa_incl_3y > 0:
        diff_pct = abs(aa_excl_3y - aa_incl_3y) / min(aa_excl_3y, aa_incl_3y)
        use_excl = diff_pct > 0.30

    result["aa_avg"] = {
        "3y": aa_excl_3y if use_excl else aa_incl_3y,
        "5y": round(avg(aa_values), 2) if n >= 5 else round(avg(aa_values), 2),
        "all": aa_incl_all,
        "ocf_based_3y": round(avg_last_n(aa_ocf_based, 3), 2),
        "method": "真实现金收入 - 全额Capex (官方Spec Factor3 Steps1-7)",
    }
    if non_op_years:
        result["aa_avg"]["aa_incl_3y"] = aa_incl_3y
        result["aa_avg"]["aa_excl_3y"] = aa_excl_3y
        result["aa_avg"]["use_excl"] = use_excl
        result["aa_avg"]["excluded_years"] = [str(inc[iy]['end_date'][:4]) for iy in non_op_years if iy < len(inc)]
        result["aa_avg"]["excluded_reason"] = "(V1+V5)/OCF > 50%"

    # ── 少数股东权益调整：AA 口径对齐 ──
    # AA 用合并 OCF 计算，但 GG 分母是归母 MC，分子是归母 NP
    # 当少数股东权益显著时，AA 需按归母比例折算
    minority = [safe_float(r.get("minority_profit"), 0) for r in inc]
    np_consolidated = [np[i] + max(minority[i], 0) for i in range(n)]  # 合并净利润
    parent_ratios = [np[i] / np_consolidated[i] if np_consolidated[i] > 0 else 1.0 for i in range(n)]
    parent_ratio_3y = avg_last_n(parent_ratios, 3) if n >= 3 else parent_ratios[-1] if parent_ratios else 1.0

    if parent_ratio_3y < 0.90:  # 少数股东 > 10% → 触发调整
        aa_original = aa_values[:]
        aa_values = [max(aa_values[i] * parent_ratio_3y, 0) for i in range(n)]
        # Also adjust AA_excl after minority adjustment
        aa_values_excl = [aa_values[i] for i in range(n) if i not in non_op_years] if non_op_years else aa_values[:]
        aa_excl_3y = round(avg_last_n(aa_values_excl, 3), 2) if len(aa_values_excl) >= 3 else round(avg_last_n(aa_values, 3), 2)
        use_excl = False
        aa_incl_3y = round(avg_last_n(aa_values, 3), 2)
        if non_op_years and aa_excl_3y > 0 and aa_incl_3y > 0:
            diff_pct = abs(aa_excl_3y - aa_incl_3y) / min(aa_excl_3y, aa_incl_3y)
            use_excl = diff_pct > 0.30
        result["minority_adjustment"] = {
            "trigger": f"少数股东占比 {round((1-parent_ratio_3y)*100,1)}% > 10%",
            "parent_ratio_3y": round(parent_ratio_3y, 3),
            "minority_profit_3y_avg": round(avg_last_n(minority, 3), 2),
            "np_consolidated_3y_avg": round(avg_last_n(np_consolidated, 3), 2),
            "aa_before_3y": round(avg_last_n(aa_original, 3), 2),
            "aa_after_3y": aa_incl_3y,
            "impact_pct": round((1 - parent_ratio_3y) * 100, 1),
            "method": "AA = (OCF - 维持性Capex) × 归母比例。合并OCF含少数股东现金流，归母股东无法支配该部分。"
        }
        # 更新已写入的 aa 逐期值和均值
        for i in range(n):
            result["aa"][year_keys[i]] = round(aa_values[i], 2)
        result["aa_avg"] = {
            "3y": aa_excl_3y if use_excl else aa_incl_3y,
            "5y": round(avg(aa_values), 5) if n >= 5 else round(avg(aa_values), 2),
            "all": round(avg(aa_values), 2),
        }
        if non_op_years:
            result["aa_avg"]["aa_incl_3y"] = aa_incl_3y
            result["aa_avg"]["aa_excl_3y"] = aa_excl_3y
            result["aa_avg"]["use_excl"] = use_excl
            result["aa_avg"]["excluded_years"] = [str(inc[iy]['end_date'][:4]) for iy in non_op_years if iy < len(inc)]
            result["aa_avg"]["excluded_reason"] = "(V1+V5)/OCF > 50%"

    # NP average
    np_avg_3y = avg_last_n(np, 3)
    oe_vals = [np[i] + d_a[i] - capex[i] for i in range(n)]
    # 少数股东调整：D&A 和 Capex 也是合并口径，OE 需按归母比例折算
    if parent_ratio_3y < 0.90:
        oe_vals = [np[i] + (d_a[i] - capex[i]) * parent_ratio_3y for i in range(n)]
    oe_avg_3y = avg_last_n(oe_vals, 3)

    # Step 8: g_base & B-class penalty
    g_base = params.get("g_base", 2.0)
    if isinstance(g_base, dict):
        g_base = g_base.get("value", 2.0)
    b_penalty = params.get("b_penalty", 0.25)
    if isinstance(b_penalty, dict):
        b_penalty = b_penalty.get("value", 0.25)
    # V12.18: g_adj 定价权 floor — 有定价权的品牌消费品永续增长率应≥2.5%
    g_adj_raw = g_base * (1 - b_penalty)
    g_adj = max(g_adj_raw, 2.0)  # 绝对下限 2.0%（不能比 CPI 还低）
    result["g_base"] = g_base
    result["b_penalty"] = b_penalty
    result["g_adj"] = round(g_adj, 2)
    result["g_adj_raw"] = round(g_adj_raw, 2)
    if g_adj > g_adj_raw:
        result["g_adj_floor_applied"] = True

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
        lambda_conservative = round(float((_d(np_avg_3y) * Decimal("0.55")) / (_d(params["II"]) / Decimal("100"))), 0)
    result["lambda"] = {
        "conservative": lambda_conservative,
        "neutral": round(float(_d(aa_values[-3:][0]) / (_d(params.get("II", 5.5)) / Decimal("100"))), 0) if len(aa_values) >= 3 else None,
        "optimistic": round(float((_d(np_avg_3y) + _d(avg(d_a) if d_a and any(x > 0 for x in d_a) else 0)) * Decimal("0.55") / (_d(params.get("II", 5.5)) / Decimal("100"))), 0) if np_avg_3y else None,
    }

    # Step 11: GG computation
    mc = market.get("mc_rmb", 0)
    # V12 fix: 使用 factor2 传入的 M 系数（优先），避免硬编码 0.55
    M_val = factor2_M if factor2_M is not None else params.get("M", 0.55)
    Q = params.get("Q", 0.10)
    O_val = params.get("O", 0)  # buyback contribution

    if mc > 0:
        gg_np = _d_penetration_pct(np_avg_3y, M_val, Q, O_val, mc) if np_avg_3y else None
        gg_oe = _d_penetration_pct(oe_avg_3y, M_val, Q, O_val, mc) if oe_avg_3y else None
        aa3y = avg_last_n(aa_values, 3)
        gg_aa = _d_penetration_pct(aa3y, M_val, Q, O_val, mc) if aa3y else None

        result["gg_raw"] = {
            "np_based": round(gg_np, 2) if gg_np else None,
            "oe_based": round(gg_oe, 2) if gg_oe else None,
            "aa_based": round(gg_aa, 2) if gg_aa else None,
        }

        # ── HH 偏离检查：粗算穿透 R(NP)_penetration vs 精算 GG(AA) ──
        # V12.5 FIX: 使用同单位比较 (两者均含 M×(1-Q)+O)
        r_np_pen = factor2_r_np_penetration  # 穿透回报率 (NP×M×(1-Q)+O)/MC
        if gg_aa is not None and r_np_pen is not None:
            hh_deviation = round(r_np_pen - gg_aa, 2)
            result["hh_deviation"] = {
                "r_np_penetration": round(r_np_pen, 2),
                "gg_aa": round(gg_aa, 2),
                "deviation": hh_deviation,
                "flag": "⚠️ |R(NP)-GG|>2pp，因子2粗算不适用" if abs(hh_deviation) > 2 else ("⚠️ |R(NP)-GG|>1.5pp，因子2可信度存疑" if abs(hh_deviation) > 1.5 else "✅ 一致"),
                "formula": "HH = R(NP)_penetration - GG_aa = (NP×M×(1-Q)+O)/MC - (AA×M×(1-Q)+O)/MC",
                "note": "V12.5: 同单位比较——两者均含M×(1-Q)+O。差异仅来自NP vs AA（权责发生制vs现金制）"
            }
        elif gg_aa is not None and factor2_r_np is not None:
            # 向后兼容: r_np_penetration 不可用时用旧的 r_np
            hh_deviation = round(factor2_r_np - gg_aa, 2)
            result["hh_deviation"] = {
                "r_np_raw": round(factor2_r_np, 2),
                "gg_aa": round(gg_aa, 2),
                "deviation": hh_deviation,
                "flag": "⚠️ |R(NP)-GG|>2pp（注意：裸R(NP) vs GG，单位不一致）" if abs(hh_deviation) > 2 else "✅ 一致",
                "formula": "HH(legacy) = R(NP)_raw - GG_aa = NP/MC - AA×M×(1-Q)/MC",
                "note": "legacy: 裸NP收益率 vs M×(1-Q)调整后的GG，单位不一致。建议使用r_np_penetration"
            }

        # V12.4: GG 使用官方 spec — AA-based 精算穿透回报率
        # GG = [AA × M × (1-Q) + O] / MC
        # AA = 极端保守现金结余（全额扣除 Capex），已包含少数股东调整
        if gg_aa is not None:
            result["gg"] = {
                "pessimistic": round(gg_aa - b_penalty * 2, 1),
                "base": round(gg_aa, 1),
                "optimistic": round(gg_aa + g_base * 0.5, 1),
            }

        # ── V12.13: FCFE GG（股权自由现金流路径，绕开 W 倒挤法的保守性）──
        # 适用场景：高 OCF/NP、低 OCF/Rev 公司（如装瓶商），AA 路径过于保守
        # FCFE = OCF - Capex - 少数股东现金流分成
        if mc > 0 and ocf and capex and n >= 3:
            ocf_3y = avg_last_n(ocf, 3)
            capex_3y_avg = avg_last_n([abs(c) for c in capex], 3)
            # 少数股东部分：按合并NP中少数股东占比估算OCF中少数股东部分
            minority_vals = [safe_float(r.get("minority_profit"), 0) for r in inc]
            np_vals_temp = [safe_float(r.get("n_income_attr_p"), 0) for r in inc]
            minority_pct_3y = 0
            if sum(np_vals_temp[-3:]) + sum(minority_vals[-3:]) > 0:
                minority_pct_3y = sum(minority_vals[-3:]) / (sum(np_vals_temp[-3:]) + sum(minority_vals[-3:]))
            parent_pct = 1.0 - minority_pct_3y if minority_pct_3y > 0 else 1.0
            fcfe_3y = (ocf_3y - capex_3y_avg) * parent_pct  # 少数股东只参与FCF分配，不影响capex
            if fcfe_3y > 0:
                fcfe_yield = _d_ratio_pct(fcfe_3y, mc)
                distributed_fcfe_yield = _d_penetration_pct(fcfe_3y, M_val, Q, O_val, mc)
                result["gg_fcfe"] = {
                    # ``base`` is retained for storage/API compatibility.  It
                    # is a distributed-owner-return scenario, not raw FCFE/MC.
                    "base": round(distributed_fcfe_yield, 1),
                    "base_semantics": "distributed_fcfe_owner_return_pct",
                    "fcfe_yield_pct": round(fcfe_yield, 1),
                    "distributed_fcfe_yield_pct": round(distributed_fcfe_yield, 1),
                    "fcfe_3y": round(fcfe_3y, 2),
                    "ocf_3y": round(ocf_3y, 2),
                    "capex_3y": round(capex_3y_avg, 2),
                    "parent_pct": round(parent_pct * 100, 1),
                    "minority_pct": round(minority_pct_3y * 100, 1),
                    "note": "FCFE=(OCF-Capex)×归母比例；raw FCFE yield与按M、Q、O折算的可分配股东回报分列，base仅为后者兼容别名",
                    "formula": "FCFE=(OCF-Capex)×parent_ratio; FCFE_yield=FCFE/MC; distributed_return=[FCFE×M×(1-Q)+O]/MC"
                }

        # ── V12.13: 正常化 GG（Spec Factor2 Step2 G系数，只扣维持性Capex）──
        # 用于低资本开支公司（如装瓶商、品牌商），极端保守 GG 可能过于悲观
        # G_coef 从 params 传入（compute_from_db 从 Factor2 读取后注入）
        g_coef = params.get("_g_coef")
        if g_coef and gg_aa is not None and aa3y and M_val > 0:
            # 正常化 Capex = D&A × G_coef（只扣维持性）
            d_a_avg_3y = avg_last_n([safe_float(r.get("d_a"), 0) or (safe_float(r.get("depr_fa_coga_dpba"), 0) + safe_float(r.get("amort_intang_assets"), 0)) for r in inc], 3)
            if d_a_avg_3y and d_a_avg_3y > 0:
                # 重算正常化 AA: OCF - D&A×G_coef - X1（无形资产购买）
                mcapex = d_a_avg_3y * g_coef
                # 从已有 capex 数据推算正常化 AA 的调整量
                capex_avg_3y = avg_last_n(capex, 3)
                # 正常化 AA = 保守 AA + (全额capex - 维持capex)
                aa_norm_3y = _normalized_aa_value(
                    aa3y, capex_avg_3y if capex_avg_3y is not None else 0, mcapex
                )
                # 重新计算正常化 GG
                gg_aa_norm = _d_penetration_pct(aa_norm_3y, M_val, Q, O_val, mc) if mc > 0 else None
                if gg_aa_norm is not None:
                    result["gg_normalized"] = {
                        "base": round(gg_aa_norm, 1),
                        "aa_norm_3y": round(aa_norm_3y, 2),
                        "maintenance_capex": round(mcapex, 2),
                        "full_capex_3y": round(capex_avg_3y, 2) if capex_avg_3y else None,
                        "g_coef": g_coef,
                        "g_label": "轻资产" if g_coef < 1.0 else ("中等资产" if g_coef < 1.3 else "重资产"),
                        "note": "正常化口径：只扣维持性Capex(D&A×G)。适用于低capex公司，避免极端保守GG过于悲观",
                        "formula": "AA_norm = AA_conservative + (full_capex - D&A×G)"
                    }
        else:
            result["gg"] = {
                "pessimistic": None,
                "base": None,
                "optimistic": None,
            }
            result["gg_unavailable"] = True
            result["gg_unavailable_reason"] = "AA₃y数据不足（<3年），无法计算GG"

        # Zone J data discount represents an observed economic loss carrier,
        # not missing-disclosure pessimism.  Missing assessment therefore
        # leaves the point estimate unchanged; uncertainty belongs in the
        # confidence/range layer.
        disc_pct = params.get("total_discount_pct", 0)
        if isinstance(disc_pct, dict):
            disc_pct = disc_pct.get("value", 0)
        disc_pct = float(disc_pct)

        # V12.15: 叠加治理折价（来自 governance_tension.json）
        gov_discount_raw = params.get("governance_discount")
        gov_discount_pct = 0.0
        if isinstance(gov_discount_raw, dict):
            gov_discount_pct = float(gov_discount_raw.get("additional_discount_pct", 0))
        elif gov_discount_raw is not None:
            gov_discount_pct = float(gov_discount_raw)

        total_disc = disc_pct + gov_discount_pct
        disc = 1.0 - min(max(total_disc, 0), 50) / 100  # 总折价上限 50%
        if result["gg"]["base"] is not None:
            result["gg_discounted"] = {
                k: round(v * disc, 1) for k, v in result["gg"].items()
            }
            result["data_discount_used"] = round(float(disc_pct), 1)
            if gov_discount_pct > 0:
                result["governance_discount_used"] = round(gov_discount_pct, 1)
                result["total_discount_used"] = round(total_disc, 1)
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

    # ── V12.5: EV 双轨 (Spec Step10 EV track) ──
    # 净现金/市值 > 40% 时，用剔除现金后的 EV 做分母，反映真实经营回报率
    net_cash_pct = result.get("net_cash_pct_mc")
    net_cash_val = result.get("net_cash")
    if (net_cash_pct is not None and net_cash_pct > 40 and net_cash_val is not None
            and mc > 0 and aa3y):
        ev = mc - max(net_cash_val, 0)
        if ev > 0:
            gg_ev_val = _d_penetration_pct(aa3y, M_val, Q, O_val, ev)
            result["gg_ev"] = {
                "ev": round(ev, 2),
                "net_cash_deducted": round(max(net_cash_val, 0), 2),
                "gg_ev_base": round(gg_ev_val, 1),
                "gg_ev_pessimistic": round(gg_ev_val - b_penalty * 2, 1),
                "gg_ev_optimistic": round(gg_ev_val + g_base * 0.5, 1),
                "trigger": f"净现金/市值={net_cash_pct:.0f}% > 40%，剔除净现金{max(net_cash_val,0):.0f}M后EV={ev:.0f}M",
                "formula": "GG_EV = [AA × M × (1-Q) + O] / EV, EV = MC - NetCash",
                # V12.10: EV双轨通过条件 (Spec: R_EV≥II AND 派息稳定/分红政策/DPS信号)
                "pass_conditions": _check_ev_pass_conditions(factor2_M, dps_vals, result.get("M", 0.55))
            }

    # ── V12.5: λ 收入敏感性分析 (Spec Step10 λ sensitivity) ──
    # λ = ΔAA/ΔS 的中位数, 衡量收入变动→可支配现金的传导强度
    _lambda_vals = []
    for i in range(max(1, len(aa_values) - 3), len(aa_values)):
        if i > 0 and rev[i] != rev[i - 1] and rev[i - 1] != 0:
            _lambda_vals.append((aa_values[i] - aa_values[i - 1]) / abs(rev[i] - rev[i - 1]))
    # This diagnostic is explicitly defined as a median.  The former arithmetic
    # mean implementation was especially dangerous when one year was an outlier:
    # the field was labelled "median" while carrying a materially different
    # number into valuation narratives.
    _lambda_median = _median_or_none(_lambda_vals)
    result["lambda_sensitivity"] = {
        "lambda": round(_lambda_median, 3) if _lambda_median else None,
        "lambda_values": [round(v, 3) for v in _lambda_vals],
        "reliability": "unstable" if _lambda_vals and any(
            (a > 0) != (_lambda_vals[0] > 0) for a in _lambda_vals) else ("stable" if _lambda_vals else "insufficient_data"),
    }
    # 临界收入倍数: 解 GG = II 时的收入
    S_current = rev[-1] if rev else 0
    aa_current = aa_values[-1] if aa_values else 0
    if _lambda_median and _lambda_median != 0 and mc > 0 and S_current > 0 and aa_current > 0:
        II_decimal = params.get("II", 5.5) / 100
        critical_surplus = (II_decimal * mc - O_val) / (M_val * (1 - Q)) if M_val * (1 - Q) > 0 else None
        if critical_surplus is not None:
            critical_revenue = S_current + (critical_surplus - aa_current) / _lambda_median
            critical_multiple = critical_revenue / S_current
            result["lambda_sensitivity"]["critical_revenue"] = round(critical_revenue, 1)
            result["lambda_sensitivity"]["critical_multiple"] = round(critical_multiple, 2)
            result["lambda_sensitivity"]["assessment"] = (
                "⚠️ 敏感" if critical_multiple >= 0.85 else
                ("韧性强" if critical_multiple < 0.7 else "中等韧性")
            )
            result["lambda_sensitivity"]["formula"] = "临界收入 = S_current + (临界结余 - AA_current) / λ, 临界倍数 = 临界收入 / S_current"
            # λ 不稳定(符号翻转)时，线性外推的 critical_revenue 数学上不可靠：
            # 分母 λ 极小或变号会放大误差、甚至给出负增量。此处显式标注，
            # 供 Agent 判断——**报告须直接引用本字段值，不得自行另做线性外推**(会得到互相矛盾的第二个数)。
            if result["lambda_sensitivity"].get("reliability") == "unstable":
                result["lambda_sensitivity"]["critical_revenue_warning"] = (
                    "⚠️ λ不稳定(符号翻转)，此 critical_revenue 为形式化外推值，可信度低。"
                    "Agent 引用时须标注‘λ不可靠、临界营收为粗略参考’，"
                    "且全报告统一用此值，禁止自行另算第二个临界营收。"
                )

    # ── V12.5: 外推可信度 5 维评级 (Spec Step11 extrapolation reliability) ──
    rev_cv = None
    if len(rev) >= 3:
        rev_mean = sum(rev) / len(rev)
        if rev_mean > 0:
            import statistics as _st
            try:
                rev_cv = _st.stdev(rev[-5:]) / rev_mean if len(rev) >= 5 else _st.stdev(rev) / rev_mean
            except Exception:
                pass
    hh_val = abs(hh_deviation) if 'hh_deviation' in dir() else None
    extrapolation_rating = {
        "revenue_volatility": {
            "cv_5y": round(rev_cv, 3) if rev_cv else None,
            "rating": "high" if rev_cv is not None and rev_cv < 0.10 else (
                "medium" if rev_cv is not None and rev_cv < 0.25 else ("low" if rev_cv is not None else "insufficient_data"))
        },
        # V12.7: 动态覆盖——从 earnings_quality 读取非经常项调整幅度
        "profit_adjustment": _compute_profit_adjustment_rating(params, np_avg_3y),
        "hh_deviation": {
            "abs_hh": abs(hh_val) if hh_val is not None else None,
            "rating": "high" if hh_val is not None and abs(hh_val) < 1 else (
                "medium" if hh_val is not None and abs(hh_val) < 3 else ("low" if hh_val is not None else "insufficient_data"))
        },
        # V12.7: 动态覆盖——从 Zone B mda strategy_changes 数量判断
        "business_model_change": _compute_business_change_rating(params, inc),
        "lambda_reliability": {
            "rating": "high" if _lambda_vals and len(_lambda_vals) >= 2 and all(
                v > 0 for v in _lambda_vals) else (
                "medium" if _lambda_vals else "insufficient_data")
        },
    }
    _high = sum(1 for d in extrapolation_rating.values() if d.get("rating") == "high")
    _low = sum(1 for d in extrapolation_rating.values() if d.get("rating") == "low")
    extrapolation_rating["overall"] = "high" if _high >= 4 else ("low" if _low >= 2 else "medium")
    extrapolation_rating["high_count"] = _high
    extrapolation_rating["low_count"] = _low
    result["extrapolation_rating"] = extrapolation_rating

    # Rejection checks
    result["rejection"]["s11"] = "pass"  # cross-validation not triggered
    result["rejection"]["ap_finance"] = "pass" if result.get("ap_excess_financing", 0) == 0 else "warn"

    # ── V12.6: 多层现金结构 ──
    money_cap_val = money_cap[-1] if money_cap and money_cap[-1] else 0
    short_term_inv = [safe_float(r.get("short_term_investments"), 0) for r in bs]
    time_dep = [safe_float(r.get("time_deposits"), 0) for r in bs]
    short_dep = [safe_float(r.get("short_term_deposits"), 0) for r in bs]
    st_borr_vals = [safe_float(r.get("st_borr"), 0) for r in bs]
    lt_borr_vals = [safe_float(r.get("lt_borr"), 0) for r in bs]
    interest_bearing_debt = (st_borr_vals[-1] or 0) + (lt_borr_vals[-1] or 0) if st_borr_vals and lt_borr_vals else 0

    bb_narrow = money_cap_val
    bb_deposit = (time_dep[-1] or 0) + (short_dep[-1] or 0)
    bb_broad = bb_narrow + bb_deposit + (short_term_inv[-1] or 0)
    net_cash_narrow = bb_narrow - interest_bearing_debt
    net_cash_broad = bb_broad - interest_bearing_debt

    result["cash_structure"] = {
        "bb_narrow": round(bb_narrow, 2),
        "bb_deposit": round(bb_deposit, 2),
        "bb_broad": round(bb_broad, 2),
        "interest_bearing_debt": round(interest_bearing_debt, 2),
        "net_cash_narrow": round(net_cash_narrow, 2),
        "net_cash_broad": round(net_cash_broad, 2),
        "note": "V12.8: 多层现金。BB_narrow=现金等价物, BB_broad=+存款+短期投资。受限/质押标记需Zone B补充。",
        "cash_upgrade_conditions": {
            "maturity_1y": "⚠️ 无法验证(需附注数据)",
            "no_pledge": "⚠️ 无法验证(需Zone B restricted_cash)",
            "deposit_ratio": f"{round(bb_deposit/max(bb_narrow,1)*100,1)}% (阈值<50%)" if bb_narrow > 0 else "N/A",
            "can_upgrade": bb_deposit / max(bb_narrow, 1) < 0.5 if bb_narrow > 0 else None,
            "note": "三条件全部满足→可用BB(广义); 否则→只能用BB_narrow(窄口径)。条件1&2无法程序验证(需年报附注)。"
        }
    }

    net_cash = net_cash_broad if bb_broad > 0 else None
    result["net_cash"] = round(net_cash, 2) if net_cash else None
    if mc > 0 and net_cash:
        result["net_cash_pct_mc"] = round(net_cash / mc * 100, 1)

    # ── V12.10: ΔFF 现金储备变动 + 派息可持续年限 (Spec Factor3 Step8-9) ──
    # ΔFF ≈ AA_3y - dividends - buybacks（现金是净增还是净消耗）
    aa3y_for_ff = avg_last_n(aa_values, 3) if aa_values else 0
    _dps_arr = [safe_float(r.get("dps"), 0) for r in divs]
    _sh_arr = [safe_float(r.get("base_share"), 0) for r in divs]
    annual_dividend_total = _dps_arr[-1] * _sh_arr[-1] if _dps_arr and _sh_arr and _dps_arr[-1] and _sh_arr[-1] else 0
    result["delta_ff"] = {
        "aa_3y": round(aa3y_for_ff, 2) if aa3y_for_ff else None,
        "annual_dividend": round(annual_dividend_total, 2) if annual_dividend_total else None,
        "net_change": round(aa3y_for_ff - annual_dividend_total, 2) if aa3y_for_ff and annual_dividend_total else None,
        "assessment": "净增" if (aa3y_for_ff and annual_dividend_total and aa3y_for_ff > annual_dividend_total) else ("净消耗" if aa3y_for_ff and annual_dividend_total else "数据不足"),
    }
    # 派息可持续年限 = BB_broad / 年派息总额
    if annual_dividend_total and annual_dividend_total > 0 and bb_broad > 0:
        sustain_years = bb_broad / annual_dividend_total
        result["dividend_sustainability_years"] = round(sustain_years, 1)
        result["dividend_sustainability_note"] = (
            f"广义现金{bb_broad:.0f}M可覆盖{sustain_years:.1f}年派息({annual_dividend_total:.0f}M/年)。"
            + ("⚠️ 未剔除受限现金" if sustain_years < 5 else "✅ 充足")
        )

    # V9.2: EV口径止损 — 净现金/市值>40%时DDM可能不适用
    if result.get("net_cash_pct_mc") and result["net_cash_pct_mc"] > 40:
            result["valuation_warning"] = (
                f"净现金/市值={result['net_cash_pct_mc']:.0f}%超过40%，"
                f"DDM估值可能不适用，建议切换到EV口径"
            )

    # Pass raw data for downstream computation (value trap, etc.)
    result["_income_raw"] = inc

    # ── V12.20: W-based vs OCF-based AA 交叉验证 ──
    aa_w = result["aa_avg"]["3y"]
    aa_ocf = result["aa_avg"].get("ocf_based_3y")
    if aa_w and aa_ocf and aa_w > 0 and aa_ocf > 0:
        divergence = abs(aa_w - aa_ocf) / min(aa_w, aa_ocf)
        result["aa_divergence"] = {
            "aa_w": round(aa_w, 2),
            "aa_ocf": round(aa_ocf, 2),
            "ratio": round(aa_w / aa_ocf, 2),
            "divergence_pct": round(divergence * 100, 1),
        }
        if divergence > 0.5:
            result["aa_divergence"]["flag"] = "⚠️ W-based AA 与 OCF-based AA 差异>50%，GG可能被高估或低估。服务业(oper_cost含人工)或高capex周期股常见。优先参考OCF口径。"
        elif divergence > 0.3:
            result["aa_divergence"]["flag"] = "⚠️ 差异>30%，建议交叉验证。"

    # ── V12.20: Factor1 交叉验证 (GG vs 护城河评级) ──
    # b_penalty 来自 Zone J moat_assessment, >0.3 表示护城河偏弱
    gg_val = result["gg"]["base"]
    if b_penalty > 0.3 and gg_val > 8:
        result["factor1_crosscheck"] = {
            "flag": f"⚠️ GG={gg_val}%但b_penalty={b_penalty}(护城河偏弱)，定量与定性分歧。建议报告中讨论。",
            "gg": gg_val,
            "b_penalty": b_penalty,
        }
        print(f"  ⚠️  Factor1交叉验证: GG={gg_val}%但b_penalty={b_penalty}", file=sys.stderr)
    elif b_penalty < 0.15 and gg_val < 5:
        result["factor1_crosscheck"] = {
            "flag": f"⚠️ GG={gg_val}%偏低但b_penalty={b_penalty}(护城河较强)，可能被低估。",
            "gg": gg_val,
            "b_penalty": b_penalty,
        }

    return result


# ── Factor 4: DDM Valuation ──

def compute_factor4(factor3: dict, market: dict, params: dict, cycle_type: str = "") -> dict:
    """Factor 4: DDM阶梯买入估值 + V12.5 P_base目标价 + 周期调整."""
    native_currency = str(market.get("native_currency") or "RMB").upper()
    result = {"tiers": [], "rejection": {}, "native_currency": native_currency}

    # ── V12.5: 周期调整 ──
    II_original = params.get("II", 5.5)
    II_adjusted = II_original
    cycle_adjustment = ""
    if cycle_type and "强周期" in str(cycle_type):
        II_adjusted = II_original + 2.0  # 周期顶部→提高门槛(更保守)
        cycle_adjustment = f"强周期+2pct: II={II_original}%→{II_adjusted}%"
    elif cycle_type and ("弱周期" in str(cycle_type) or "成长" in str(cycle_type)):
        II_adjusted = II_original  # 弱周期/成长不调整
    result["II_original"] = II_original
    result["II_adjusted"] = II_adjusted
    result["cycle_adjustment"] = cycle_adjustment if cycle_adjustment else "无周期调整"
    II = II_adjusted  # 使用调整后的II

    def _unresolved_valuation(reason: str) -> dict:
        unresolved_rejection = dict(result.get("rejection") or {})
        unresolved_rejection["s1"] = "unresolved"
        return {
            **result,
            "valuation_status": "UNRESOLVED_VALUATION",
            "valuation_unresolved_reason": reason,
            "ddm_v_hkd": None,
            "ddm_v_rmb": None,
            "buy_ladder": [],
            "position": {
                "status": "UNRESOLVED_VALUATION",
                "jj_pct": None,
                "ii_adjusted_pct": round(II, 1),
                "base_pct": None,
                "capped_pct": None,
                "recommended": None,
                "rationale": "估值或价格输入不可用；撤回当前价格动作，不把未知写成0%或AVOID",
            },
            "verdict": {
                "gg_layer": {"gate": "UNAVAILABLE", "gg_pct": None, "ii_pct": round(II, 1)},
                "ddm_layer": {"gate": "UNAVAILABLE", "upside_pct": None},
                "asset_layer": {"gate": "UNAVAILABLE", "net_cash_pct_mc": None},
                "final": "UNRESOLVED_VALUATION",
                "framework": "企业判断继续；估值与当前价格动作暂不承保",
            },
            "rejection": unresolved_rejection,
            "error": reason,
        }

    dps = params.get("dps_latest")
    if dps is None:
        return _unresolved_valuation("dps_latest missing")
    g = _d(factor3.get("g_adj", 1.5)) / Decimal("100")
    # II already computed above with cycle adjustment
    r = _d(II) / Decimal("100")  # required return = II (cycle-adjusted, as decimal)
    Q = params.get("Q", 0.10)
    gg_base_raw = factor3.get("gg", {}).get("base")
    gg_available = (
        not factor3.get("gg_unavailable", False)
        and isinstance(gg_base_raw, (int, float))
    )
    gg_base = float(gg_base_raw) if gg_available else None
    mc = market.get("mc_rmb", 0)
    price_rmb = market.get("price_rmb")
    if not isinstance(price_rmb, (int, float)) or price_rmb <= 0:
        return _unresolved_valuation("current price missing")
    shares = market.get("shares_m")
    if shares is None:
        return _unresolved_valuation("shares_m missing")

    # DDM: V = DPS * (1+g) / (r - g)
    dps_dec = _d(dps)
    dps_currency = str(params.get("dps_currency") or params.get("financial_currency") or "RMB").upper()
    dps_fx_to_rmb = _d(fx_to_rmb(dps_currency), "1")
    market_fx_dec = _d(market.get("fx", 1), "1")
    dps_rmb = dps_dec * dps_fx_to_rmb
    dps_native = dps_rmb / market_fx_dec if market_fx_dec > 0 else dps_rmb
    dps_next_rmb = dps_rmb * (Decimal("1") + g)
    if r > g:
        v_ddm = dps_next_rmb / (r - g)
    else:
        v_ddm = dps_rmb * Decimal("20")  # fallback PE=20

    result["ddm_v_rmb"] = round(float(v_ddm), 2)
    fx = market.get("fx", 0.9346)
    fx_dec = _d(fx, "0.9346")
    ddm_v_native = round(float(v_ddm / fx_dec), 2)
    # Keep the old key during migration. It has historically meant "trading
    # currency", despite its misleading HKD name.
    result["ddm_v_native"] = ddm_v_native
    result["ddm_v_hkd"] = ddm_v_native

    # Tiered entry (five-star system) — 5★=最深折扣(60%公允价) 1★=公允价(无折扣)
    for star, discount in [(1, 0.0), (2, 0.10), (3, 0.20), (4, 0.30), (5, 0.40)]:
        target_rmb = v_ddm * (Decimal("1") - _d(discount))
        target_native = target_rmb / fx_dec
        upside = (float(target_native / (_d(price_rmb) / fx_dec)) - 1) * 100 if price_rmb > 0 else 0
        pe_implied = float((_d(target_rmb) * _d(shares)) / _d(factor3.get("np_avg_3y", 117))) if factor3.get("np_avg_3y") else None
        _disc_pct = int(round(discount * 100))
        result["tiers"].append({
            "star": star,
            "price_native": round(float(target_native), 2),
            "price_hkd": round(float(target_native), 2),
            "price_rmb": round(float(target_rmb), 2),
            "currency": native_currency,
            "upside_pct": round(upside, 1),
            "pe_implied": round(pe_implied, 1) if pe_implied else None,
            # 折价率标签：星级价 = 公允价 ×(1-discount)。安全边际=相对公允价的折价幅度。
            # ⚠️ 引用时必须用此字段，勿自行臆测折价%（5★=40%折价，非20%）。
            "discount_pct": _disc_pct,
            "margin_label": f"含{_disc_pct}%安全边际的DDM公允价" if _disc_pct else "DDM公允价(无折价)",
        })

    # DPS yield
    price_native = _d(market.get("price_native") or market.get("price_hkd") or 0)
    yield_pretax = None
    yield_after_tax = None
    if price_native > 0:
        yield_pretax = round(float((dps_native / price_native) * Decimal("100")), 2)
        yield_after_tax = round(float((dps_native * (Decimal("1") - _d(Q)) / price_native) * Decimal("100")), 2)
        result["dps_yield_pretax"] = yield_pretax
        result["dps_yield_after_tax"] = yield_after_tax
    result["dividend_identity"] = {
        "dps_fy_reported": round(float(dps_dec), 4),
        "dps_currency": dps_currency,
        "dps_fx_to_rmb": round(float(dps_fx_to_rmb), 6),
        "dps_rmb": round(float(dps_rmb), 4),
        "dps_native": round(float(dps_native), 4),
        "price_native": round(float(price_native), 4),
        "price_currency": native_currency,
        "yield_pretax_pct": yield_pretax,
        "yield_after_tax_pct": yield_after_tax,
        "period": params.get("dps_period") or "FY",
        "source": params.get("dps_fy_source") or "unknown",
        "formula": "dps_native = dps_reported × dps_fx_to_rmb ÷ price_fx_to_rmb; yield = dps_native ÷ price_native",
    }

    # ── V12.5: P_base 目标价 (Spec Factor4 Step4) ──
    # P_base = MC × (GG/II) / shares → GG=II时的公允价
    gg_base_val = factor3.get("gg", {}).get("base")
    # V12.10: 现金保护层 → 安全边际折扣 (Spec Module 0(8))
    net_cash_pct_f4 = factor3.get("net_cash_pct_mc") or 0
    if net_cash_pct_f4 > 40: protection_discount = 0.15
    elif net_cash_pct_f4 > 20: protection_discount = 0.20
    elif net_cash_pct_f4 > 0: protection_discount = 0.25
    else: protection_discount = 0.30
    if gg_base_val and gg_base_val > 0 and shares and shares > 0 and II > 0:
        p_base_rmb = round(float((_d(mc) * (_d(gg_base_val) / Decimal("100")) / (_d(II) / Decimal("100"))) / _d(shares)), 2)
        p_base_native = round(float(_d(p_base_rmb) / fx_dec), 2)
        result["p_base"] = {
            "price_rmb": p_base_rmb,
            "price_native": p_base_native,
            "price_hkd": p_base_native,
            "display_currency": native_currency,
            "display_price": p_base_native,
            "upside_pct": round((p_base_rmb / price_rmb - 1) * 100, 1) if price_rmb > 0 else None,
            "formula": "P_base = MC × (GG/II) / shares",
            "explanation": f"在此价格下，GG({gg_base_val}%)恰好等于II({II}%)，即公允价（{native_currency}计价）。",
            # V12.10: 按现金保护层折扣
            "protection_discount_pct": round(protection_discount * 100, 0),
            "protection_level": "极强保护" if protection_discount <= 0.15 else ("强保护" if protection_discount <= 0.20 else ("轻度保护" if protection_discount <= 0.25 else "无保护")),
            "p_base_discounted_rmb": round(p_base_rmb * (1 - protection_discount), 2),
            "p_base_discounted_native": round(p_base_rmb / fx * (1 - protection_discount), 2),
            "p_base_discounted_hkd": round(p_base_rmb / fx * (1 - protection_discount), 2),
        }
        # V12.14: FCFE-based P_base（少数股东重公司参考）
        fcfe_gg = factor3.get("gg_fcfe", {}).get("base")
        if fcfe_gg and fcfe_gg > 0 and shares and shares > 0 and II > 0:
            p_fcfe_rmb = round(float((_d(mc) * (_d(fcfe_gg) / Decimal("100")) / (_d(II) / Decimal("100"))) / _d(shares)), 2)
            result["p_base"]["p_fcfe"] = {
                "price_rmb": p_fcfe_rmb,
                "price_native": round(float(_d(p_fcfe_rmb) / fx_dec), 2),
                "price_hkd": round(float(_d(p_fcfe_rmb) / fx_dec), 2),
                "currency": native_currency,
                "upside_pct": round((p_fcfe_rmb / price_rmb - 1) * 100, 1) if price_rmb > 0 else None,
                "formula": "P_FCFE = MC × (GG_FCFE/II) / shares",
                "note": "基于FCFE GG(绕开W倒挤法)。少数股东重公司参考视角，与AA版P_base对比使用"
            }
        # P_EV (if EV dual-track triggered)
        gg_ev = factor3.get("gg_ev", {})
        if gg_ev and gg_ev.get("ev"):
            ev = gg_ev["ev"]
            gg_ev_base_val = gg_ev.get("gg_ev_base")
            net_cash_val_f4 = factor3.get("net_cash", 0) or 0
            if gg_ev_base_val and gg_ev_base_val > 0:
                p_ev_rmb = round(float((_d(max(net_cash_val_f4, 0)) + _d(ev) * (_d(gg_ev_base_val) / Decimal("100")) / (_d(II) / Decimal("100"))) / _d(shares)), 2)
                result["p_base"]["p_ev"] = {
                    "price_rmb": p_ev_rmb,
                    "price_native": round(float(_d(p_ev_rmb) / fx_dec), 2),
                    "price_hkd": round(float(_d(p_ev_rmb) / fx_dec), 2),
                    "currency": native_currency,
                    "upside_pct": round((p_ev_rmb / price_rmb - 1) * 100, 1) if price_rmb > 0 else None,
                    "formula": "P_EV = (NetCash + EV × GG_EV/II) / shares",
                    "note": "EV双轨目标价——净现金按面值，经营资产按GG_EV/II折现"
                }

    # Value trap check (7 criteria) — compute from actual data where possible
    # V12.5: 增强检测——连接AP分析 + 周期风险
    # Quantitative checks
    np_5y_cagr = cagr([safe_float(r.get("n_income_attr_p")) for r in factor3.get("_income_raw", [])]) if factor3.get("_income_raw") else None
    np_decline = np_5y_cagr is not None and np_5y_cagr < 0

    # FCF sustainability: AA > dividends_paid?
    aa3y = factor3.get("aa_avg", {}).get("3y", 0) or 0
    annual_dividend = params.get("dps_latest", 0) * shares if params.get("dps_latest") and shares else 0
    dividend_unsustainable = aa3y < annual_dividend * 0.8 if aa3y > 0 else None

    # Qualitative checks (require LLM judgment — mark as unknown when data unavailable)
    # V12.5: 增强——连接AP检测 + 周期风险
    ap_excess = factor3.get("ap_excess_financing", 0)
    ap_cost_ratio = factor3.get("ap_cost_ratio_avg", 0) or 0
    ap_trap = (ap_excess > 0 and aa3y > 0 and ap_cost_ratio > 0)  # AP驱动现金流质量差
    cycle_risk = (cycle_type and "强周期" in str(cycle_type))  # 周期顶部利润下行风险
    vt = {
        "np_decline": np_decline,
        "low_pb_roe": None,              # needs PB+ROE from market data
        "dividend_unsustainable": dividend_unsustainable,
        "business_disrupted": None,       # qualitative — LLM to judge
        "management_expropriation": None, # qualitative — LLM to judge
        "margin_irreversible": None,      # needs gross margin trend data
        "price_new_lows": None,           # needs price percentile data
        # V12.5 新增可计算项
        "ap_driven_cashflow": ap_trap,    # AP持续拉长→伪现金流风险
        "cyclical_peak_risk": cycle_risk, # 强周期公司周期顶部风险
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
        "exclude": bool(gg_available and vt_score_known >= 2 and gg_base < II * 100 * 1.5),
        "note": f"{vt_total_known}/7 criteria computable from data; {len([k for k,v in vt.items() if v is None])} require LLM judgment",
    }

    # ── V12.7: 动态仓位矩阵（Spec Factor4 Step3）──
    gg_base_val = gg_base
    jj = gg_base_val - II if gg_available else None  # JJ = GG - II（pct points）
    extrap_rating = factor3.get("extrapolation_rating", {}).get("overall", "medium")
    vt_exclude = result.get("value_trap", {}).get("exclude", False)
    cap = params.get("PORTFOLIO_CAP_PCT", 5)

    if not gg_available:
        position_pct, position_label = None, "GG不可用；撤回当前价格动作，不把未知写成0%"
    elif vt_exclude:
        position_pct, position_label = 0.0, "排除(价值陷阱)"
    elif jj >= 1.5 and extrap_rating == "high":
        position_pct, position_label = 5.0, "标准仓位(KK≥1.5pp+高可信度)"
    elif jj >= 1.5 and extrap_rating == "medium":
        position_pct, position_label = 3.5, "70%仓位(KK≥1.5pp+中可信度)"
    elif jj >= 0.5:
        if extrap_rating == "high":
            position_pct, position_label = 2.5, "50%仓位(KK≥0.5pp+高可信度)"
        else:
            position_pct, position_label = 1.5, "观察仓位(KK≥0.5pp+中/低可信度)"
    elif jj >= 0:
        position_pct, position_label = 0.5, "观察/等待(KK 0-0.5pp)"
    else:
        position_pct, position_label = 0.0, "不建仓(KK<0)"

    result["position"] = {
        "status": "RESOLVED" if gg_available else "UNRESOLVED_VALUATION",
        "jj_pct": round(jj, 1) if jj is not None else None,
        "ii_adjusted_pct": round(II, 1),
        "extrapolation_rating": extrap_rating,
        "value_trap_excluded": vt_exclude,
        "base_pct": round(position_pct, 1) if position_pct is not None else None,
        "capped_pct": round(min(position_pct, cap), 1) if position_pct is not None else None,
        "recommended": f"{min(position_pct, cap):.1f}%" if position_pct is not None else None,
        "rationale": position_label,
    }

    # Stop loss
    result["stop_loss"] = {
        "hard_native": round(price_rmb / fx * 0.765, 2),  # -23.5%
        "hard_hkd": round(price_rmb / fx * 0.765, 2),
        "currency": native_currency,
        "fundamental": "fy2026_h1_margin_lt_13pct",
        "time": "2yr_no_value_convergence",
        "event": "major_shareholder_sells_or_audit_change",
    }

    # ── V12.8: DDM 年化回报（Spec: N年期累积回报含股息再投）──
    dps_yield_after_tax = result.get("dps_yield_after_tax", 0) or 0
    if dps_yield_after_tax > 0 and price_rmb > 0:
        ddm_v_rmb = result.get("ddm_v_rmb")
        if ddm_v_rmb and ddm_v_rmb > 0:
            # 5年期年化回报 = [(1+股息率)^5 × DDM公允价/当前价]^(1/5) - 1
            cum_dividend_factor = (1 + dps_yield_after_tax / 100) ** 5
            terminal_value_ratio = ddm_v_rmb / price_rmb
            annualized_5yr = (cum_dividend_factor * terminal_value_ratio) ** (1 / 5) - 1
            result["ddm_annualized_return"] = {
                "5yr_pct": round(annualized_5yr * 100, 1),
                "cum_dividend_factor": round(cum_dividend_factor, 3),
                "terminal_value_ratio": round(terminal_value_ratio, 2),
                "formula": "[(1+股息率_税后)^5 × DDM公允价/当前价]^(1/5) - 1",
                "note": "5年期年化回报(含股息复利再投)。终点股价=DDM公允价。"
            }

    # ── V12.14: PE 估值参考 ──
    # 当前 PE = MC_rmb / NP（归母口径）
    np_latest = factor3.get("_income_raw", [{}])[-1].get("n_income_attr_p") if factor3.get("_income_raw") else None
    if not np_latest:
        np_latest = factor3.get("np_avg_3y")
    if np_latest and np_latest > 0 and mc > 0:
        result["current_pe"] = round(mc / np_latest, 1)
        result["current_pe_note"] = "PE = MC / NP(归母口径)。Agent应在Ch12中与industry_context的行业PE中位数对比，揭示折价来源(少数股东/流动性/增长)"

    # ── V12.8: 三视角统一裁决（Spec Factor4 层级决策）──
    jj = result["position"].get("jj_pct")
    _tiers = result.get("tiers", [])
    ddm_upside = _tiers[0].get("upside_pct", 0) if _tiers else 0
    vt_exclude_final = result.get("value_trap", {}).get("exclude", False)
    # GG层
    if not gg_available:
        gg_gate = "UNAVAILABLE"
    elif gg_base_val >= II and not vt_exclude_final:
        gg_gate = "准入"
    elif gg_base_val > 0:
        gg_gate = "边界"
    else:
        gg_gate = "不达标"
    # DDM层
    if ddm_upside >= 30: ddm_gate = "便宜"
    elif ddm_upside >= 0: ddm_gate = "合理"
    elif ddm_upside >= -20: ddm_gate = "偏贵"
    else: ddm_gate = "贵"
    # 资产层: 净现金/MC 保护
    net_cash_pct_raw = factor3.get("net_cash_pct_mc")
    net_cash_available = isinstance(net_cash_pct_raw, (int, float))
    net_cash_pct_f4 = float(net_cash_pct_raw) if net_cash_available else None
    if not net_cash_available: asset_gate = "UNAVAILABLE"
    elif net_cash_pct_f4 > 40: asset_gate = "极强保护"
    elif net_cash_pct_f4 > 20: asset_gate = "强保护"
    elif net_cash_pct_f4 > 0: asset_gate = "轻度保护"
    else: asset_gate = "无保护"
    # 统一裁决
    if vt_exclude_final:
        verdict = "AVOID"
    elif not gg_available:
        verdict = "UNRESOLVED_VALUATION"
    elif gg_gate == "准入" and ddm_gate in ("便宜", "合理") and jj >= 2.0 and ddm_upside >= 30:
        verdict = "STRONG_BUY"
    elif gg_gate == "准入" and ddm_gate in ("便宜", "合理") and jj >= 1.5:
        verdict = "BUY"
    elif gg_gate == "准入" and ddm_gate == "便宜":
        verdict = "BUY"  # GG不够但DDM极度便宜仍可买
    elif gg_gate in ("准入", "边界") and ddm_gate in ("便宜", "合理"):
        verdict = "HOLD_WATCH"
    elif gg_gate == "边界" and ddm_gate == "偏贵":
        verdict = "HOLD"
    else:
        verdict = "AVOID"

    # V12.18: 逆向期权价值覆盖 — 当定量Avoid仅因一次性扰动触发，且估值已极度压缩时
    s2_status = result.get("rejection", {}).get("s2", "")
    pert_waiver = result.get("perturbation_waiver", {}).get("active", False)
    current_pe = result.get("current_pe")
    if (verdict == "AVOID" and pert_waiver and s2_status == "warn"
            and gg_available and gg_base_val > II * 0.5
            and current_pe and current_pe < 12):
        verdict = "CAUTIOUS_WATCH"
        result["contrarian_override"] = {
            "active": True,
            "from": "AVOID",
            "to": "CAUTIOUS_WATCH",
            "rationale": (
                "定量Avoid仅因S2扰动豁免触发(非持续性恶化)。"
                f"PE={current_pe:.1f}x已极度压缩，市场对已知风险过度定价。"
                "定性若确认护城河未破坏，此处的定量Avoid本身就是逆向信号。"
            ),
            "position_note": "建议仓位0→1-2%，须附带明确的催化剂触发条件",
        }

    result["verdict"] = {
        "gg_layer": {"gate": gg_gate, "gg_pct": round(gg_base_val, 1) if gg_available else None, "ii_pct": round(II, 1)},
        "ddm_layer": {"gate": ddm_gate, "upside_pct": round(ddm_upside, 1)},
        "asset_layer": {"gate": asset_gate, "net_cash_pct_mc": round(net_cash_pct_f4, 1) if net_cash_available else None},
        "final": verdict,
        "framework": "GG层准入→DDM层定价→资产层仓位上限→统一裁决"
    }

    # Rejection
    result["valuation_status"] = "RESOLVED" if gg_available else "UNRESOLVED_VALUATION"
    result["rejection"]["s1"] = "pass" if gg_available else "unresolved"
    result["rejection"]["s2"] = "warn_not_exclude" if vt_score_known >= 2 else "pass"

    return result


# ── Main ──

def _build_calculation_trace(factor2, factor3, factor4, market, params):
    """Build step-by-step calculation traces for Zone C report writing."""
    mc_rmb = market.get("mc_rmb", 0)
    aa3y = factor3.get("aa_avg", {}).get("3y", 0) or 0
    np_3y = factor2.get("np_avg_3y", 0)
    oe_3y = factor2.get("oe_avg_3y", 0)
    aa_3y = factor3.get("aa_avg", {}).get("3y", 0)
    g_adj = factor3.get("g_adj", 1.5)
    g_base = factor3.get("g_base", 2.0)
    M_val = factor3.get("M", factor2.get("M", 0.55))
    Q = params.get("Q", 0.10)
    II = params.get("II", 5.5) / 100
    dps = params.get("dps_latest", 0)
    dividend_identity = factor4.get("dividend_identity", {}) or {}
    dps_native = safe_float(dividend_identity.get("dps_native"))
    if dps_native is None:
        dps_native = safe_float(dps)
    gg = factor3.get("gg", {})
    gg_raw = factor3.get("gg_raw", {})
    lamb = factor3.get("lambda", {})
    native_currency = str(market.get("native_currency") or "RMB").upper()

    ddm_value = safe_float(factor4.get("ddm_v_native", factor4.get("ddm_v_hkd")))
    ddm_resolved = (
        factor4.get("valuation_status") != "UNRESOLVED_VALUATION"
        and dps_native is not None
        and dps_native > 0
        and ddm_value is not None
    )
    ddm_trace = {
        "formula": "V = DPS × (1 + g_adj/100) / (II - g_adj/100)",
        "substitutions": {
            "DPS_native": round(dps_native, 4) if dps_native is not None else None,
            "DPS_currency": dividend_identity.get("price_currency", native_currency),
            "g": round(g_adj/100, 4),
            "II": round(II, 4),
        },
        "steps": (
            [
                f"DPS_native₁ = {dps_native:.4f} × (1+{g_adj/100:.4f}) = "
                f"{dps_native*(1+g_adj/100):.4f} {native_currency}",
                f"V = {dps_native*(1+g_adj/100):.4f} / "
                f"({II:.4f}-{g_adj/100:.4f}) = {ddm_value:.2f} {native_currency}",
            ]
            if ddm_resolved and II > g_adj/100
            else []
        ),
        "result": round(ddm_value, 2) if ddm_resolved else None,
        "unit": native_currency,
        "status": "RESOLVED" if ddm_resolved else "UNRESOLVED_VALUATION",
    }
    if not ddm_resolved:
        ddm_trace["reason"] = str(
            factor4.get("valuation_unresolved_reason")
            or factor4.get("error")
            or "DPS or current valuation input unavailable"
        )

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
            "result": round(factor2.get("r_oe") or 0, 2), "unit": "%"
        },
        "factor2_r_np_after_tax": {
            "formula": "R(NP)税后 = R(NP)税前 × (1 - Q)",
            "substitutions": {"R(NP)税前": round(factor2.get("r_np", 0), 2), "Q": Q},
            "steps": [f"{factor2.get('r_np',0):.2f}% × (1-{Q}) = {factor2.get('r_np',0)*(1-Q):.2f}%"],
            "result": round(factor2.get("r_np", 0) * (1 - Q), 2), "unit": "%"
        },
        "factor2_rough": {
            "formula": "R(NP)粗算 = NP₃y / MC_rmb × 100",
            "r_np": round(factor2.get("r_np"), 2) if factor2.get("r_np") else None,
            "note": "基于归母净利润的粗算穿透回报率，仅作基准对比。不作为最终GG。"
        },
        "factor3_precise": {
            "formula": "GG精算 = AA₃y × M × (1-Q) / MC_rmb × 100",
            "substitutions": {
                "AA₃y": factor3.get("aa_avg", {}).get("3y"),
                "M": round(M_val, 4),
                "Q": Q,
                "MC_rmb": round(mc_rmb, 2)
            },
            "steps": [
                f"GG = {aa3y:.1f} × {M_val:.4f} × (1-{Q}) / {mc_rmb:.1f} × 100 = {factor3.get('gg',{}).get('base',0)}%"
            ] if mc_rmb > 0 and aa3y else [],
            "gg_np_ref": factor3.get("gg_raw", {}).get("np_based"),
            "gg_oe_ref": factor3.get("gg_raw", {}).get("oe_based"),
            "gg_aa_raw": factor3.get("gg_raw", {}).get("aa_based"),
            "hh_deviation": factor3.get("hh_deviation", {}),
            "unit": "%"
        },
        "factor3_gg_scenarios": {
            "pessimistic": factor3["gg"]["pessimistic"],
            "base": factor3["gg"]["base"],
            "optimistic": factor3["gg"]["optimistic"],
            "note": "悲观=GG_aa - b_penalty×2; 基准=GG_aa(AA-based); 乐观=GG_aa + g_base×0.5",
            "unit": "%"
        },
        "factor3_lambda": {
            "formula": "λ_neutral = AA_latest_3y_first / (II/100)",
            "substitutions": {"AA_recent": factor3.get("aa_avg", {}).get("3y"), "II_pct": round(II*100, 1)},
            "result": factor3.get("lambda", {}).get("neutral"),
            "unit": "百万元 RMB"
        },
        "factor4_ddm": ddm_trace,
    }


def compute(output_dir: str, params_override: Optional[dict] = None,
            price_hkd: float = None, shares_m: float = None,
            contract: Optional[dict] = None,
            tracking_meta: Optional[dict] = None) -> dict:
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

    ts_code = fin_data.get("ts_code") or _infer_ts_code_from_output_dir(output_dir) or ""
    stock_info = {}
    currency = fin_data.get("currency", "RMB")
    gg_override = load_gg_override(output_dir)
    labor_disclosure_summary = load_labor_disclosure_summary(output_dir)

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
            row = None
            if ts_code:
                row = conn.execute("SELECT shares_m, currency, data_source_code FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
            conn.close()
            if row:
                if row[0]:
                    _shares_m = float(row[0])
                    print(f"📊 DB shares: {_shares_m}M", file=sys.stderr)
                stock_info = {
                    "shares_m": safe_float(row[0]),
                    "currency": row[1],
                    "data_source_code": row[2],
                }
        except Exception:
            pass
    # V8.3: Auto-fetch from yfinance if still missing
    if (_price_hkd is None or _shares_m is None) and ts_code:
        try:
            import yfinance as yf
            code = ts_code.replace(".HK", ".HK").replace(".SH", ".SS").replace(".SZ", ".SZ")
            t = yf.Ticker(code)
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

    # ── V12.19: Tracking valuation inheritance ──
    report_type = "annual"
    inherited_valuation = None
    if tracking_meta:
        report_type = tracking_meta.get("report_type", "annual")
    elif contract and isinstance(contract, dict):
        report_type = contract.get("report_type", "annual")
    if report_type in ("q1", "q3"):
        inherited_valuation = _inherit_annual_valuation(contract)
        print(f"  📊 {report_type.upper()} 跟踪节点：估值锚继承自最近年报", file=sys.stderr)
    elif report_type == "h1":
        print(f"  ⚠️  H1 跟踪节点：默认不重算GG，参照最近年报估值", file=sys.stderr)

    # Compute factors
    factor2 = compute_factor2(fin_data, market, params)
    # V12.13: 将 G_coef 注入 params 供 Factor3 正常化 GG 使用
    g_info = factor2.get("oe_maintenance_G", {})
    if g_info:
        params["_g_coef"] = g_info.get("coefficient")
    factor3 = compute_factor3(
        fin_data, market, params,
        factor2.get("M"), factor2.get("r_np"), factor2.get("r_np_penetration"),
        gg_override=gg_override,
        labor_disclosure_summary=labor_disclosure_summary,
    )
    gg_guard = _check_gg_guard(ts_code, factor3, market, output_dir=output_dir)
    if gg_guard and gg_guard.get("error"):
        factor3["gg_diagnostic_unverified"] = dict(factor3.get("gg") or {})
        factor3["gg"] = {"pessimistic": None, "base": None, "optimistic": None}
        factor3["gg_unavailable"] = True
        factor3["gg_unavailable_reason"] = str(gg_guard.get("error"))
        factor3.setdefault("rejection", {})["gg_identity"] = "unresolved"
    # Merge M from factor3 into factor2 if available
    if "M" not in factor2 or factor2["M"] == 0.55:
        factor2["M"] = factor3.get("M", factor2["M"])
    cycle_type = contract.get("cyclicality_profile", {}).get("label", "") if contract else ""
    factor4 = compute_factor4(factor3, market, params, cycle_type=cycle_type)

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
            elif status == "unresolved":
                rejection_summary["warnings"].append(f"{f_name}.{gate}:unresolved")
                if rejection_summary["overall"] != "block":
                    rejection_summary["overall"] = "unresolved"

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
        "gg_guard": gg_guard,
    }
    gg_labor_bundle = _build_gg_labor_bundle(factor3, gg_override, labor_disclosure_summary)
    bundle["gg_labor"] = gg_labor_bundle
    if "gg_override" in gg_labor_bundle:
        bundle["gg_override"] = gg_labor_bundle["gg_override"]

    # V12.19: Tracking valuation inheritance
    if report_type != "annual":
        bundle["tracking_valuation"] = {
            "report_type": report_type,
            "valuation_anchor_source": "latest_annual" if not inherited_valuation else "inherited",
            "inherited_from_latest_annual": inherited_valuation is not None,
            "note": (
                f"{report_type.upper()} 跟踪节点，估值锚（GG/DDM/P_base）继承自最新年报。"
                f"本节点不重算主估值锚。bundle 中的 factor3/factor4 为参考值，不作为主结论。"
            ),
        }
        if inherited_valuation:
            bundle["tracking_valuation"]["inherited"] = inherited_valuation
            # Override factor3.gg with inherited values for downstream consumption
            if inherited_valuation.get("gg"):
                bundle["factor3"]["gg"] = inherited_valuation["gg"]
            if inherited_valuation.get("gg_discounted"):
                bundle["factor3"]["gg_discounted"] = inherited_valuation["gg_discounted"]
            if inherited_valuation.get("ddm_v_hkd"):
                bundle["factor4"]["ddm_v_hkd"] = inherited_valuation["ddm_v_hkd"]
            if inherited_valuation.get("ddm_v_rmb"):
                bundle["factor4"]["ddm_v_rmb"] = inherited_valuation["ddm_v_rmb"]
            if inherited_valuation.get("p_base"):
                bundle["factor4"]["p_base"] = inherited_valuation["p_base"]
            print(f"  ✅ 估值锚已从最新年报继承: GG={inherited_valuation.get('gg',{}).get('base','?')}%, "
                  f"DDM={inherited_valuation.get('ddm_v_hkd','?')}", file=sys.stderr)

    # V12.19: 卫星上市标的标注
    data_source_code_val = stock_info.get("data_source_code")
    if data_source_code_val:
        trading_currency = stock_info.get("currency", "RMB")
        bundle["trading_info"] = {
            "type": "satellite_listing",
            "data_source_code": data_source_code_val,
            "trading_code": ts_code,
            "trading_currency": trading_currency,
            "note": (
                f"此为卫星上市标的（{trading_currency}计价）。"
                f"财务数据（AA/NP/OCF等）来自母标的 {data_source_code_val}，"
                f"价格和市值按 {ts_code} 独立获取。"
                f"GG/DDM/仓位均基于 {ts_code} 的市值和价格计算。"
            ),
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


def infer_trading_currency(ts_code: str, db_currency: str | None = None) -> str:
    """Infer trading currency from listing code, overriding stale DB rows when needed."""
    code = str(ts_code or "").upper()
    if code.endswith(".HK"):
        return "HKD"
    if code.endswith(".DE"):
        return "EUR"
    if code.endswith(".US"):
        return "USD"
    if code.endswith(".SZ") and code.startswith("200"):
        return "HKD"
    if code.endswith(".SH") and code.startswith("900"):
        return "USD"
    if db_currency:
        return str(db_currency).upper()
    return "RMB"


def fx_to_rmb(currency: str) -> float:
    code = str(currency or "RMB").upper()
    if code == "HKD":
        return float(os.environ.get("EXCHANGE_RATE_HKD", "0.9346"))
    if code == "USD":
        return float(os.environ.get("EXCHANGE_RATE_USD", "7.15"))
    if code == "EUR":
        return float(os.environ.get("EXCHANGE_RATE_EUR", "7.80"))
    return 1.0


def compute_from_db(ts_code: str, params_override: dict = None, price_hkd: float = None,
                     force: bool = False, contract: Optional[dict] = None,
                     zone_j_params: Optional[dict] = None,
                     price_source_code: str = "",
                     tracking_meta: Optional[dict] = None) -> dict:
    """Compute bundle from database. V9.2: dynamic window + Zone J parameters.

    ``ts_code`` identifies the research and financial statements. ``price_source_code``
    optionally identifies a separately traded listing whose price, shares, market
    cap, target prices and position sizing should be used.

    V12.19 tracking: ``tracking_meta`` controls quarterly tracking behavior.
    q1/q3 skip GG/DDM/P_base and inherit from latest annual bundle.
    h1 can do reference calculation with low confidence.

    If contract is provided, uses effective_years as data window.
    If zone_j_params is provided, merges into params_override.
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
    output_dir = find_stock_output_dir(ts_code)

    threshold = fin_data.pop("_threshold", {})
    stock_info = fin_data.pop("_stock", {})
    gg_override = load_gg_override(output_dir)
    labor_disclosure_summary = load_labor_disclosure_summary(output_dir)

    pricing_code = price_source_code or ts_code
    pricing_stock_info = stock_info
    if pricing_code != ts_code:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        pricing_row = conn.execute(
            "SELECT * FROM stocks WHERE ts_code=?",
            (pricing_code,),
        ).fetchone()
        conn.close()
        if not pricing_row:
            raise ValueError(
                f"Cannot use {pricing_code} as --price-source: it is missing from stocks."
            )
        pricing_stock_info = dict(pricing_row)
        print(f"💱 {ts_code}: 使用 {pricing_code} 的交易价格、股本和市值", file=sys.stderr)

    # Currency-aware FX rate. All market-native values use the pricing listing.
    stock_currency = infer_trading_currency(pricing_code, pricing_stock_info.get("currency"))
    fx = fx_to_rmb(stock_currency)
    price_label = stock_currency
    if stock_currency != "RMB":
        print(f"💱 {pricing_code}: {price_label} 计价，fx={fx}", file=sys.stderr)

    # Auto-fetch market data from Tushare/yfinance
    tushare_data = None
    if price_hkd is None:
        tushare_data = fetch_market_from_tushare(pricing_code)

    # Shares: DB → yfinance → override → default
    shares_m = pricing_stock_info.get("shares_m")
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
            f"Cannot determine shares outstanding for pricing code {pricing_code}. "
            f"DB stock_info.shares_m is NULL, yfinance/Tushare unavailable. "
            f"Provide --shares or populate DB stock_info."
        )

    # Price: manual → Tushare/yfinance → default
    price_fetch_source = "manual" if price_hkd else "default"
    if price_hkd is None:
        if tushare_data and tushare_data.get("price"):
            price_hkd = tushare_data["price"]
            price_fetch_source = tushare_data.get("source", "auto")
            print(f"📊 {price_fetch_source}: price={price_hkd} {price_label}, shares={shares_m}M")
        else:
            if params_override and params_override.get("price"):
                price_hkd = params_override["price"]
                price_fetch_source = "override"
            else:
                # V12.18: Tushare不可用时，不影响核心计算(GG不依赖price)
                price_hkd = 1.0
                price_fetch_source = "fallback(1.0)"
                print(f"⚠️  {pricing_code}: 无法获取股价(Tushare/yfinance不可用)，使用fallback=1.0。DDM/upside不可靠，GG计算不受影响。", file=sys.stderr)

    market = {
        "analysis_code": ts_code,
        "pricing_code": pricing_code,
        "native_currency": stock_currency,
        "price_native": price_hkd,
        "price_hkd": price_hkd,
        "price_rmb": round(price_hkd * fx, 2),
        "shares_m": shares_m,
        "mc_native": round(price_hkd * shares_m, 2),
        "mc_hkd": round(price_hkd * shares_m, 2),
        "mc_rmb": round(price_hkd * shares_m * fx, 2),
        "fx": fx,
        "shares_warning": pricing_stock_info.get("shares_m") is None,
        "price_source": price_fetch_source,
    }

    # Try to get DPS: override → dividends_paid/shares (全息,含中期) → DB dps列 → error
    dps_latest = (params_override.get("dps_latest") if params_override else None)
    db_dps_ref = None
    dps_fy_ref = None
    dps_fy_source = "db_dps"
    dps_ttm_source = "db_dps"
    annual_dividend_plan = _extract_annual_report_dividend_plan(output_dir)
    dividend_evidence = _resolve_dividend_evidence(_load_dividend_evidence(output_dir))
    if dps_latest is None:
        db_dps_rows = fin_data.get("dividends", [])
        # Get DB dps column as sanity check reference
        if db_dps_rows:
            ref_vals = [safe_float(r.get("dps")) for r in db_dps_rows[-3:]]
            ref_vals = [v for v in ref_vals if v is not None and 0 < v < 1000]
            if ref_vals:
                db_dps_ref = ref_vals[-1]
                dps_fy_ref = db_dps_ref
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
                            dps_ttm_source = "dividends_paid_over_shares"
                            print(f"📊 DPS: dividends_paid/shares={dps_latest:.4f} (vs DB dps={db_dps_ref:.4f}, ratio={ratio:.1f}x)", file=sys.stderr)
                        else:
                            print(f"⚠️  DPS: dividends_paid/shares={dps_from_div:.4f} out of range vs DB dps={db_dps_ref:.4f} (ratio={ratio:.1f}x) — using DB dps", file=sys.stderr)
                    else:
                        dps_latest = dps_from_div
                        dps_ttm_source = "dividends_paid_over_shares"
        if dps_latest is None and db_dps_ref is not None:
            dps_latest = db_dps_ref
            dps_ttm_source = "db_dps"

    report_final = safe_float(annual_dividend_plan.get("final_per_share"))
    report_interim = safe_float(annual_dividend_plan.get("interim_per_share"))
    evidence_fy = safe_float(dividend_evidence.get("dps_fy"))
    dps_currency = str(
        dividend_evidence.get("currency")
        or annual_dividend_plan.get("currency")
        or fin_data.get("currency")
        or "RMB"
    ).upper()
    if evidence_fy and evidence_fy > 0:
        dps_fy_ref = evidence_fy
        dps_fy_source = "dividend_evidence"
        entry_labels = []
        for entry in dividend_evidence.get("entries", []):
            kind = (entry.get("kind") or "entry").strip()
            per_share = safe_float(entry.get("per_share")) or 0
            entry_labels.append(f"{kind}={per_share:.4f}")
        print(f"📌 DPS(FY): dividend_evidence {' + '.join(entry_labels)} → {dps_fy_ref:.4f}", file=sys.stderr)
    elif report_final:
        report_fy = report_final + (report_interim or 0)
        if db_dps_ref and db_dps_ref > report_fy:
            dps_fy_ref = db_dps_ref
            dps_fy_source = "db_dps"
            print(
                f"📌 DPS(FY): keep DB dps={db_dps_ref:.4f} "
                f"(annual report plan={report_fy:.4f})",
                file=sys.stderr,
            )
        else:
            dps_fy_ref = report_fy
            dps_fy_source = "annual_report_dividend_plan"
            if report_interim:
                print(
                    f"📌 DPS(FY): annual report final={report_final:.4f} + interim={report_interim:.4f} "
                    f"→ {dps_fy_ref:.4f}",
                    file=sys.stderr,
                )
            else:
                print(f"📌 DPS(FY): using annual report final dividend={report_final:.4f}", file=sys.stderr)
    elif dps_fy_ref is None:
        dps_fy_ref = db_dps_ref or dps_latest
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
        "dps_fy": dps_fy_ref,        # V9.3: 年报全年DPS（必要时用现金分红总额校正）
        "dps_ttm": dps_latest,        # V9.3: 最近12个月(含特别股息)
        "dps_latest": dps_fy_ref or dps_latest,  # DDM默认用年报全年DPS
        "dps_fy_source": dps_fy_source,
        "dps_ttm_source": dps_ttm_source,
        "dps_currency": dps_currency,
        "financial_currency": fin_data.get("currency", "RMB"),
        "dps_period": f"FY{contract.get('analysis_end_year')}" if contract and contract.get("analysis_end_year") else "FY",
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
    # V12.13: 将 G_coef 注入 params 供 Factor3 正常化 GG 使用
    g_info = factor2.get("oe_maintenance_G", {})
    if g_info:
        params["_g_coef"] = g_info.get("coefficient")
    factor3 = compute_factor3(
        fin_data, market, params,
        factor2.get("M"), factor2.get("r_np"), factor2.get("r_np_penetration"),
        gg_override=gg_override,
        labor_disclosure_summary=labor_disclosure_summary,
    )
    output_dir = find_stock_output_dir(ts_code)
    gg_guard = _check_gg_guard(ts_code, factor3, market, output_dir=output_dir)
    if gg_guard and gg_guard.get("error"):
        factor3["gg_diagnostic_unverified"] = dict(factor3.get("gg") or {})
        factor3["gg"] = {"pessimistic": None, "base": None, "optimistic": None}
        factor3["gg_unavailable"] = True
        factor3["gg_unavailable_reason"] = str(gg_guard.get("error"))
        factor3.setdefault("rejection", {})["gg_identity"] = "unresolved"
    cycle_type = contract.get("cyclicality_profile", {}).get("label", "") if contract else ""
    factor4 = compute_factor4(factor3, market, params, cycle_type=cycle_type)
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
            elif status == "unresolved":
                rejection_summary["warnings"].append(f"{f_name}.{gate}:unresolved")
                if rejection_summary["overall"] != "block":
                    rejection_summary["overall"] = "unresolved"

    financial_currency = fin_data.get("currency", "RMB")
    bundle = {
        "meta": {
            "code": ts_code,
            "date": "2026-07-08",
            "version": "v3.0-db",
            "currency": stock_currency,
            "financial_currency": financial_currency,
            "financial_source_code": fin_data.get("financial_source_code", ts_code),
        },
        "market": market, "params": params,
        "factor2": factor2, "factor3": factor3, "factor4": factor4,
        "calculation_trace": calculation_trace,
        "rejection_summary": rejection_summary,
        "gg_guard": gg_guard,
    }
    gg_labor_bundle = _build_gg_labor_bundle(factor3, gg_override, labor_disclosure_summary)
    bundle["gg_labor"] = gg_labor_bundle
    if "gg_override" in gg_labor_bundle:
        bundle["gg_override"] = gg_labor_bundle["gg_override"]
    if dividend_evidence:
        bundle["dividend_evidence"] = dividend_evidence

    # V12.19: 卫星上市标的标注
    data_source = stock_info.get("data_source_code") or ""
    if data_source or pricing_code != ts_code:
        bundle["trading_info"] = {
            "type": "cross_listing" if (data_source or pricing_code != ts_code) else "direct_listing",
            "analysis_code": ts_code,
            "financial_source_code": data_source or ts_code,
            "pricing_code": pricing_code,
            "trading_code": pricing_code,
            "trading_currency": stock_currency,
            "note": (
                f"研究身份为 {ts_code}；财务数据来自 {data_source or ts_code}；"
                f"价格、市值、目标价和仓位按 {pricing_code}（{stock_currency}）计算。"
            ),
        }

    return bundle


def main():
    p = argparse.ArgumentParser(description="compute_bundle v3.0 — 定量计算中心")
    p.add_argument("--output", help="Output directory (JSON file path)")
    p.add_argument("--from-db", action="store_true", help="Read from stock_analysis.db instead of JSON files")
    p.add_argument("--code", type=str, default="01502.HK", help="Stock code for --from-db mode")
    p.add_argument("--g-base", type=float, default=2.0, help="g_base override")
    p.add_argument("--b-penalty", type=float, default=0.25, help="B-class penalty override")
    p.add_argument("--dps", type=float, default=None, help="Latest DPS override")
    p.add_argument("--price", type=float, default=None, help="Current price override (auto-fetched from Tushare if omitted)")
    p.add_argument("--market-snapshot", type=str, default=None,
                   help="Verified Niangao market_snapshot.json; authoritative over provider auto-fetch")
    p.add_argument("--shares", type=float, help="Shares outstanding (millions) override")
    p.add_argument("--force", action="store_true", help="Bypass BLOCKED readiness check")
    p.add_argument("--contract", type=str, default=None,
                   help="Path to analysis_contract.json (V9.2 dynamic window)")
    p.add_argument("--zone-j", type=str, default=None,
                   help="Path to stock output directory with Zone J JSONs (V9.2)")
    p.add_argument("--data-source", type=str, default=None,
                   help="V12.19: 卫星标的 — 指定财务数据来源母标代码（如 --data-source 600295.SH）。自动写入 stocks.data_source_code。")
    p.add_argument("--price-source", type=str, default=None,
                   help="指定市场价格、市值和仓位计算所用的交易代码（如 --price-source 900936.SH）")
    args = p.parse_args()

    market_snapshot = None
    if args.market_snapshot:
        try:
            try:
                from scripts.niangao_market_bridge import verify_snapshot_file
            except ModuleNotFoundError:
                from niangao_market_bridge import verify_snapshot_file
            market_snapshot = verify_snapshot_file(
                args.market_snapshot, expected_code=args.price_source or args.code,
            )
            snapshot_price = float(market_snapshot["price"])
            if args.price is not None and not math.isclose(float(args.price), snapshot_price, rel_tol=1e-9, abs_tol=1e-9):
                print("ERROR: --price conflicts with --market-snapshot", file=sys.stderr)
                return 1
            args.price = snapshot_price
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

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

        # V12.19: --data-source 显式指定母标
        if args.data_source:
            _ensure_data_source_code(args.code, args.data_source)

        # Only let contract fill in missing market suffix for short codes.
        # When the caller already passes a full code like 690D.DE or 200596.SZ,
        # it must remain the analysis identity even if an old contract is stale.
        effective_code = args.code
        if "." not in str(args.code or "") and contract:
            effective_code = contract.get("ts_code", args.code)
        bundle = compute_from_db(effective_code, override, price_hkd=args.price,
                                  force=args.force, contract=contract,
                                  zone_j_params=zone_j_params,
                                  price_source_code=args.price_source or "")
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
        contract = None
        if args.contract and os.path.exists(args.contract):
            with open(args.contract) as f:
                contract = json.load(f)
        elif not args.contract:
            contract_path = os.path.join(args.output, "analysis_contract.json")
            if os.path.exists(contract_path):
                with open(contract_path) as f:
                    contract = json.load(f)
        override = {
            "g_base": args.g_base, "b_penalty": args.b_penalty,
            "dps_latest": args.dps,
        }
        if args.shares:
            override["shares_m"] = args.shares
        bundle = compute(args.output, override, price_hkd=args.price, shares_m=args.shares, contract=contract)
        out_path = os.path.join(args.output, "compute_bundle.json")

    if "error" in bundle:
        print(f"ERROR: {bundle['error']}", file=sys.stderr)
        return 1

    if market_snapshot:
        bundle.setdefault("market", {}).update({
            "price_source": f"niangao:{market_snapshot['source']}",
            "price_fetched_at": market_snapshot["fetched_at"],
            "price_as_of": market_snapshot["as_of"],
            "market_snapshot_hash": market_snapshot["snapshot_hash"],
        })

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False, default=str)

    print(f"✅ compute_bundle.json written to {out_path}")
    print(f"   GG: {bundle['factor3']['gg']}")
    currency = bundle.get("market", {}).get("native_currency", "RMB")
    ddm = bundle["factor4"].get("ddm_v_native", bundle["factor4"].get("ddm_v_hkd"))
    print(f"   DDM: {ddm} {currency}")
    print(f"   Rejection: {bundle['rejection_summary']['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
