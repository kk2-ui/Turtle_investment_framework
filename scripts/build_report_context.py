#!/usr/bin/env python3
"""build_report_context.py — L4 Context Extraction Engine

Extracts structured operational, governance, audit, and market facts from:
  - pdf_sections_*.json (MDA, P3, STMT)
  - data_pack_market.md (market position, company profile)
  - stock_analysis.db (cross-validation)

Output: report_context.json — structured, source-traced, confidence-scored facts
for LLM report generation (L5).

Usage:
    python3 scripts/build_report_context.py --code 01502.HK
    python3 scripts/build_report_context.py --code 01502.HK --output output/01502_金融街物业
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


# ── Helpers ──

def fact(value, unit: str, source: str, confidence: float, quote: str = "", page: int = None) -> dict:
    """Create a standardized fact dict."""
    f = {"value": value, "unit": unit, "source": source, "confidence": confidence}
    if quote:
        f["quote"] = quote[:200]
    if page is not None:
        f["page"] = page
    return f


def load_text(path: str) -> Optional[str]:
    """Load file text, return None if not found."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_json(path: str) -> Optional[dict]:
    """Load JSON file, return None if not found."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_first(pattern: str, text: str, group: int = 1) -> Optional[str]:
    """Return first regex match group, or None."""
    m = re.search(pattern, text)
    return m.group(group).strip() if m else None


def try_float(s: str) -> Optional[float]:
    """Try to parse a cleaned string as float."""
    try:
        return float(s.replace(",", "").replace(" ", "").replace("约", ""))
    except (ValueError, TypeError):
        return None


# ── Extractors ──

class MarketPositionExtractor:
    """Extract price, 52-week, 10-year data from data_pack_market.md."""

    def extract(self, stock_dir: str) -> dict:
        dp = load_text(os.path.join(stock_dir, "data_pack_market.md"))
        if not dp:
            return {}

        facts = {}

        # Current price
        m = re.search(r"当前价格\s*\(HKD\)\s*\|\s*([\d.]+)", dp)
        if m:
            facts["price_latest"] = fact(float(m.group(1)), "HKD", "data_pack_market.md §11", 0.95)

        # 52-week
        m = re.search(r"52周最高\s*\|\s*([\d.]+)", dp)
        if m:
            facts["week_52_high"] = fact(float(m.group(1)), "HKD", "data_pack_market.md §11", 0.90)
        m = re.search(r"52周最低\s*\|\s*([\d.]+)", dp)
        if m:
            facts["week_52_low"] = fact(float(m.group(1)), "HKD", "data_pack_market.md §11", 0.90)

        # 10-year
        m = re.search(r"10年最高\s*\(HKD\)\s*\|\s*([\d.]+)", dp)
        if m:
            facts["ten_year_high"] = fact(float(m.group(1)), "HKD", "data_pack_market.md §11", 0.85)
        m = re.search(r"10年最低\s*\(HKD\)\s*\|\s*([\d.]+)", dp)
        if m:
            facts["ten_year_low"] = fact(float(m.group(1)), "HKD", "data_pack_market.md §11", 0.85)

        # Drawdown
        m = re.search(r"距最高回撤\s*\|\s*([\d.]+)%", dp)
        if m:
            facts["drawdown_from_high_pct"] = fact(float(m.group(1)), "pct", "data_pack_market.md §11", 0.85)

        # PE / PB (may be "—")
        m = re.search(r"PE\s*\(TTM\)\s*\|\s*([\d.—]+)", dp)
        if m and m.group(1).strip() not in ("—", "-"):
            facts["pe_ttm"] = fact(try_float(m.group(1)), "x", "data_pack_market.md §2", 0.80)
        m = re.search(r"^\|\s*PB\s*\|\s*([\d.—]+)", dp, re.MULTILINE)
        if m and m.group(1).strip() not in ("—", "-"):
            facts["pb"] = fact(try_float(m.group(1)), "x", "data_pack_market.md §2", 0.80)

        return facts


class CompanyProfileExtractor:
    """Extract controlling shareholder, ultimate controller, listing info."""

    def extract(self, stock_dir: str, ts_code: str) -> dict:
        dp = load_text(os.path.join(stock_dir, "data_pack_market.md"))
        facts = {}

        if dp:
            # Company name, listing date, market from data_pack
            m = re.search(r"公司名称\s*\|\s*(.+?)\s*\|", dp)
            if m:
                facts["name_cn"] = fact(m.group(1).strip(), "text", "data_pack_market.md §1", 0.95)

        # From DB
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT name_cn, name_en, listing_date, currency, shares_m FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
            if r:
                if r["name_en"]:
                    facts["name_en"] = fact(r["name_en"], "text", "stock_analysis.db:stocks", 0.95)
                if r["listing_date"]:
                    facts["listing_date"] = fact(r["listing_date"], "date", "stock_analysis.db:stocks", 0.95)
                if r["shares_m"]:
                    facts["shares_m"] = fact(r["shares_m"], "million_shares", "stock_analysis.db:stocks", 0.95)
            conn.close()
        except Exception:
            pass

        return facts


class AuditExtractor:
    """Extract auditor, audit opinion from pdf_sections STMT."""

    def extract(self, stock_dir: str, latest_year: int = 2025) -> dict:
        facts = {}

        for year in range(latest_year, latest_year - 5, -1):
            ps = load_json(os.path.join(stock_dir, f"pdf_sections_{year}.json"))
            if not ps:
                continue
            stmt = ps.get("STMT", "")
            if not stmt:
                continue

            year_facts = {}

            # Auditor
            for name in ["致同", "安永", "毕马威", "德勤", "普华永道", "罗兵咸", "信永中和",
                         "立信", "天健", "大华", "大信", "中审", "Grant Thornton",
                         "Ernst & Young", "KPMG", "Deloitte", "PwC", "Pricewaterhouse"]:
                if name in stmt:
                    year_facts["auditor"] = fact(name, "text", f"pdf_sections_{year}.json:STMT", 0.90)
                    break

            # Opinion — check for adverse/qualified keywords
            has_adverse = any(kw in stmt for kw in ["保留意见", "否定意见", "无法表示意见"])
            has_unqualified = any(kw in stmt for kw in ["无保留", "真实而中肯", "true and fair",
                                                         "present fairly", "公允反映", "無保留"])
            if has_adverse:
                year_facts["audit_opinion"] = fact("非标准意见", "text", f"pdf_sections_{year}.json:STMT", 0.85,
                                                   quote="检测到保留/否定/无法表示意见关键词")
            elif has_unqualified:
                year_facts["audit_opinion"] = fact("标准无保留意见", "text", f"pdf_sections_{year}.json:STMT", 0.85)

            # Report date
            m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", stmt)
            if m:
                year_facts["report_date"] = fact(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
                                                 "date", f"pdf_sections_{year}.json:STMT", 0.90)

            # Auditor switch detection
            if year_facts:
                facts[f"FY{year}"] = year_facts
                break  # only latest year for now

        return facts


class OperationsExtractor:
    """Extract managed area, project count, third-party ratio from MDA."""

    def extract(self, stock_dir: str, latest_year: int = 2025) -> dict:
        facts = {}

        for year in range(latest_year, latest_year - 5, -1):
            ps = load_json(os.path.join(stock_dir, f"pdf_sections_{year}.json"))
            if not ps:
                continue
            mda = ps.get("MDA", "")
            if not mda:
                continue

            year_facts = {}

            # Total managed area: "總計\s*([\d,]+)\s*100\s*([\d,]+)" in the table
            m = re.search(r"總計\s*([\d,]+)\s*100\s*([\d,]+)", mda)
            if m:
                area = try_float(m.group(1))
                projects = try_float(m.group(2))
                if area:
                    year_facts["managed_area_m_sqm"] = fact(area / 1000, "million_sqm",
                                                            f"pdf_sections_{year}.json:MDA", 0.85,
                                                            quote=f"在管面积{m.group(1)}千平方米")
                if projects:
                    year_facts["project_count"] = fact(int(projects), "count",
                                                       f"pdf_sections_{year}.json:MDA", 0.85)

            # Third-party area
            m = re.search(r"由獨立第三方開發的物業\s*([\d,]+)\s*([\d.]+)\s*(\d+)", mda)
            if m:
                tp_area = try_float(m.group(1))
                tp_pct = try_float(m.group(2))
                tp_projects = try_float(m.group(3))
                if tp_area:
                    year_facts["third_party_area_m_sqm"] = fact(tp_area / 1000, "million_sqm",
                                                                f"pdf_sections_{year}.json:MDA", 0.85)
                if tp_pct:
                    year_facts["third_party_area_pct"] = fact(tp_pct, "pct",
                                                              f"pdf_sections_{year}.json:MDA", 0.85)
                if tp_projects:
                    year_facts["third_party_project_count"] = fact(int(tp_projects), "count",
                                                                    f"pdf_sections_{year}.json:MDA", 0.85)

            # Related party area
            m = re.search(r"金融街聯屬集團開發的物業.*?約*?([\d.]+)\s*百萬平方米", mda)
            if m:
                year_facts["related_party_area_m_sqm"] = fact(try_float(m.group(1)), "million_sqm",
                                                               f"pdf_sections_{year}.json:MDA", 0.80)

            if year_facts:
                facts[f"FY{year}"] = year_facts
                break  # latest year

        return facts


class BusinessSegmentExtractor:
    """Extract gross margin by segment from MDA."""

    def extract(self, stock_dir: str, latest_year: int = 2025) -> dict:
        facts = {}

        for year in range(latest_year, latest_year - 5, -1):
            ps = load_json(os.path.join(stock_dir, f"pdf_sections_{year}.json"))
            if not ps:
                continue
            mda = ps.get("MDA", "")
            if not mda:
                continue

            year_facts = {}

            # Commercial property gross margin: "商務物業\s*([\d,]+)\s*([\d.]+)"
            m = re.search(r"商務物業\s*([\d,]+)\s*([\d.]+)\s*([\d,]+)\s*([\d.]+)", mda)
            if m:
                year_facts["commercial_gm_pct"] = fact(try_float(m.group(2)), "pct",
                                                       f"pdf_sections_{year}.json:MDA", 0.80)
                year_facts["commercial_prev_gm_pct"] = fact(try_float(m.group(4)), "pct",
                                                            f"pdf_sections_{year}.json:MDA", 0.80)

            # Non-commercial: "非商務物業\s*([\d,]+)\s*([\d.]+)"
            m = re.search(r"非商務物業\s*([\d,]+)\s*([\d.]+)\s*([\d,]+)\s*([\d.]+)", mda)
            if m:
                year_facts["non_commercial_gm_pct"] = fact(try_float(m.group(2)), "pct",
                                                           f"pdf_sections_{year}.json:MDA", 0.80)

            # Overall
            m = re.search(r"整體毛利率[約為]+\s*([\d.]+)%", mda)
            if m:
                year_facts["overall_gm_pct"] = fact(try_float(m.group(1)), "pct",
                                                     f"pdf_sections_{year}.json:MDA", 0.85)

            if year_facts:
                facts[f"FY{year}"] = year_facts
                break

        return facts


class RiskEventExtractor:
    """Extract goodwill impairment and receivable aging from P3."""

    def extract(self, stock_dir: str, latest_year: int = 2025) -> dict:
        facts = {}

        for year in range(latest_year, latest_year - 5, -1):
            ps = load_json(os.path.join(stock_dir, f"pdf_sections_{year}.json"))
            if not ps:
                continue
            p3 = ps.get("P3", "")
            if not p3:
                continue

            year_facts = {}

            # Goodwill impairment
            if "商譽" in p3 and "減值" in p3:
                # Try to find impairment numbers
                m = re.search(r"置佳.*?([\d,]+)\s*([\d,]+)", p3)
                if m:
                    year_facts["goodwill_balance"] = fact(try_float(m.group(1)), "RMB_thousand",
                                                          f"pdf_sections_{year}.json:P3", 0.80)
                year_facts["goodwill_impairment_detected"] = fact(True, "bool",
                                                                   f"pdf_sections_{year}.json:P3", 0.85,
                                                                   quote="P3 含有商誉减值信息")

            # Receivable aging
            if "應收" in p3:
                # Look for aging table with 一年内 / 一至二年 / 兩至三年 / 三年以上
                aging_buckets = {}
                for label, pattern in [
                    ("within_1y", r"(?:一年[以內内]|1年[以內内]).*?([\d,]+)"),
                    ("1_to_2y", r"(?:一至兩年|一至二年|1至2年).*?([\d,]+)"),
                    ("2_to_3y", r"(?:兩至三年|二至三年|2至3年).*?([\d,]+)"),
                    ("over_3y", r"(?:三年[以內内]上|3年[以內内]上).*?([\d,]+)"),
                ]:
                    m = re.search(pattern, p3)
                    if m:
                        val = try_float(m.group(1))
                        if val:
                            aging_buckets[label] = fact(val, "RMB_thousand",
                                                        f"pdf_sections_{year}.json:P3", 0.80)

                if aging_buckets:
                    year_facts["receivable_aging"] = aging_buckets

            if year_facts:
                facts[f"FY{year}"] = year_facts
                break

        return facts


class FinancialValidator:
    """Cross-validate pdf financials against DB annual_financials."""

    def extract(self, stock_dir: str, ts_code: str, latest_year: int = 2025) -> dict:
        warnings = []

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row

            for year in range(latest_year, latest_year - 5, -1):
                ps = load_json(os.path.join(stock_dir, f"pdf_sections_{year}.json"))
                if not ps:
                    continue
                pdf_fin = ps.get("financials", {})
                if not pdf_fin:
                    continue

                db_row = conn.execute(
                    "SELECT * FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
                    (ts_code, year)).fetchone()
                if not db_row:
                    continue

                # Map Chinese names to DB fields
                checks = [
                    ("资产总计", "total_assets"),
                    ("营业收入", "revenue"),
                ]

                for cn_name, db_field in checks:
                    pdf_val = pdf_fin.get(cn_name)
                    db_val = db_row[db_field] if db_field in db_row.keys() else None
                    if pdf_val and db_val:
                        if abs(db_val) > 0.01:
                            dev = abs(pdf_val - db_val) / abs(db_val) * 100
                            if dev > 5:
                                warnings.append({
                                    "field": db_field,
                                    "year": year,
                                    "pdf_value": pdf_val,
                                    "db_value": db_val,
                                    "deviation_pct": round(dev, 1),
                                    "action": "used_db_value"
                                })

            conn.close()
        except Exception as e:
            warnings.append({"error": str(e)})

        return {"cross_validation_warnings": warnings}


class EvidenceSummarizer:
    """Compute confidence stats and identify missing expected facts."""

    def summarize(self, all_facts: dict) -> dict:
        total = 0
        by_confidence = {"high": 0, "medium": 0, "low": 0}

        def count(d):
            nonlocal total
            if isinstance(d, dict):
                if "value" in d and "confidence" in d:
                    total += 1
                    c = d["confidence"]
                    if c >= 0.85: by_confidence["high"] += 1
                    elif c >= 0.70: by_confidence["medium"] += 1
                    else: by_confidence["low"] += 1
                else:
                    for v in d.values():
                        count(v)

        count(all_facts)

        # Check which expected sections have data
        expected = ["company_profile", "market_position", "audit", "operations",
                     "business_segments", "risk_events"]
        missing = [s for s in expected if s not in all_facts or not all_facts[s]]

        return {
            "total_facts": total,
            "by_confidence": by_confidence,
            "sections_present": [s for s in expected if s in all_facts and all_facts[s]],
            "sections_missing": missing,
        }


# ── Main ──

def build_context(ts_code: str, stock_dir: str, latest_year: int = 2025) -> dict:
    """Build the full report_context.json for a stock."""

    context = {
        "meta": {
            "ts_code": ts_code,
            "context_years": list(range(latest_year - 4, latest_year + 1)),
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "context_version": "v1",
        }
    }

    context["company_profile"] = CompanyProfileExtractor().extract(stock_dir, ts_code)
    context["market_position"] = MarketPositionExtractor().extract(stock_dir)
    context["audit"] = AuditExtractor().extract(stock_dir, latest_year)
    context["operations"] = OperationsExtractor().extract(stock_dir, latest_year)
    context["business_segments"] = BusinessSegmentExtractor().extract(stock_dir, latest_year)
    context["risk_events"] = RiskEventExtractor().extract(stock_dir, latest_year)

    # Cross-validation
    validator = FinancialValidator()
    context["_validation"] = validator.extract(stock_dir, ts_code, latest_year)

    # Evidence summary
    summarizer = EvidenceSummarizer()
    context["evidence_summary"] = summarizer.summarize(context)

    v_warnings = context["_validation"].get("cross_validation_warnings", [])
    context["evidence_summary"]["warnings"] = v_warnings

    return context


# ── Official Evidence Context v2 ──

EVIDENCE_CONTEXT_VERSION = "report-context.v2"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _context_fingerprint(payload: dict[str, Any]) -> str:
    core = deepcopy(payload)
    meta = core.get("meta") if isinstance(core.get("meta"), dict) else {}
    meta.pop("generated_at", None)
    meta.pop("context_fingerprint", None)
    core.pop("validation", None)
    return _canonical_hash(core)


def build_verified_context(
    stock_dir: str | Path,
    manifest: dict[str, Any],
    facts: dict[str, Any],
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Assemble only VERIFIED facts into the LLM-visible report context."""
    try:
        from scripts.evidence_documents import _atomic_write_json
    except ModuleNotFoundError:
        from evidence_documents import _atomic_write_json

    output = Path(stock_dir)
    domains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    conflicts: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for observation in facts.get("observations") or []:
        if not isinstance(observation, dict):
            continue
        status = str(observation.get("status") or "")
        counts[status] += 1
        if status == "VERIFIED":
            domains[str(observation.get("domain") or "other")].append(deepcopy(observation))
        elif status == "CONFLICT":
            conflicts.append({
                "observation_id": observation.get("observation_id"),
                "fact_name": observation.get("fact_name"),
                "as_of": observation.get("as_of"),
                "conflict_ids": observation.get("conflict_ids") or [],
            })
    for values in domains.values():
        values.sort(key=lambda item: (str(item.get("as_of")), str(item.get("fact_name")), str(item.get("observation_id"))))

    expected_domains = ("audit", "financial", "operations", "governance", "industry", "capital_allocation")
    gaps: list[dict[str, Any]] = []
    for domain in expected_domains:
        if not domains.get(domain):
            gaps.append({
                "gap_id": "GAP:" + _canonical_hash({"report_id": manifest.get("report_id"), "domain": domain})[:16],
                "domain": domain,
                "fact_name": None,
                "severity": "WARN",
                "reason": "verified_domain_fact_missing",
                "attempted_sources": [doc.get("doc_id") for doc in manifest.get("documents") or [] if isinstance(doc, dict)],
                "decision_impact": "Phase 02必须在问题入选后判断是否升级为关键缺口",
            })

    invalid = list((manifest.get("validation") or {}).get("invalid_findings") or [])
    invalid += list((facts.get("validation") or {}).get("invalid_findings") or [])
    incomplete = list((manifest.get("validation") or {}).get("incomplete_findings") or [])
    incomplete += list((facts.get("validation") or {}).get("incomplete_findings") or [])
    warnings = list((manifest.get("validation") or {}).get("warnings") or [])
    warnings += list((facts.get("validation") or {}).get("warnings") or [])
    warnings += [f"domain_gap:{item['domain']}" for item in gaps]
    if conflicts:
        incomplete.append("verified_fact_conflicts_unresolved")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_CONTEXT_VERSION,
        "meta": {
            "report_id": manifest.get("report_id"),
            "code": manifest.get("code"),
            "market": manifest.get("market"),
            "issuer": manifest.get("issuer"),
            "generated_at": _now_utc(),
            "manifest_hash": manifest.get("manifest_hash"),
            "observation_hash": facts.get("observation_hash"),
            "context_fingerprint": "",
        },
        "documents": sorted(str(doc.get("doc_id")) for doc in manifest.get("documents") or [] if isinstance(doc, dict) and doc.get("doc_id")),
        "domains": dict(sorted(domains.items())),
        "unresolved_gaps": gaps,
        "conflicts": conflicts,
        "coverage": {
            "document_count": len(manifest.get("documents") or []),
            "observation_counts": dict(sorted(counts.items())),
            "verified_domains": sorted(domains),
            "expected_domains": list(expected_domains),
            "domain_coverage_ratio": round(len(domains) / len(expected_domains), 4),
            "citable_observation_ids": sorted(
                str(item.get("observation_id")) for values in domains.values() for item in values
            ),
        },
        "validation": {
            "state": state,
            "invalid_findings": list(dict.fromkeys(invalid)),
            "incomplete_findings": list(dict.fromkeys(incomplete)),
            "warnings": list(dict.fromkeys(warnings)),
        },
    }
    payload["meta"]["context_fingerprint"] = _context_fingerprint(payload)
    if persist:
        _atomic_write_json(output / "report_context.json", payload)
    return payload


def build_official_evidence_bundle(
    stock_dir: str | Path,
    code: str,
    *,
    persist: bool = True,
    run_id: str | None = None,
    enforced: bool = False,
) -> dict[str, Any]:
    try:
        from scripts.computation_evidence import build_calculation_observations
        from scripts.evidence_documents import build_document_manifest, initialize_official_evidence_policy
        from scripts.evidence_facts import build_fact_observations
    except ModuleNotFoundError:
        from computation_evidence import build_calculation_observations
        from evidence_documents import build_document_manifest, initialize_official_evidence_policy
        from evidence_facts import build_fact_observations

    output = Path(stock_dir)
    manifest = build_document_manifest(output, code, persist=persist)
    facts = build_fact_observations(output, manifest, persist=persist)
    calculations = (
        build_calculation_observations(output, persist=persist)
        if (output / "compute_bundle.json").is_file() else {}
    )
    context = build_verified_context(output, manifest, facts, persist=persist)
    if run_id is not None:
        initialize_official_evidence_policy(output, run_id=run_id, enforced=enforced)
    migration: dict[str, Any] = {}
    claim_path = output / "claim_evidence.json"
    if persist and claim_path.is_file():
        claim_payload = _read_object(claim_path)
        needs_identity_migration = any(
            isinstance(evidence, dict)
            and evidence.get("direct_support")
            and evidence.get("support_type") == "supports"
            and not evidence.get("observation_id")
            and not evidence.get("calculation_id")
            for claim in claim_payload.get("claims") or [] if isinstance(claim, dict)
            for evidence in claim.get("raw_facts") or []
        )
        if needs_identity_migration:
            try:
                from scripts.claim_evidence_migration import migrate_claim_evidence, promote_migration_candidate
            except ModuleNotFoundError:
                from claim_evidence_migration import migrate_claim_evidence, promote_migration_candidate
            migration = migrate_claim_evidence(output, persist=True)
            if migration.get("report", {}).get("candidate_validation", {}).get("state") == "REVIEWABLE":
                migration["promotion"] = promote_migration_candidate(output)
    return {
        "manifest": manifest, "facts": facts, "calculations": calculations,
        "context": context, "claim_migration": migration,
    }


def evaluate_output_official_evidence(
    stock_dir: str | Path, *, persist: bool = True
) -> dict[str, Any]:
    """Evaluate new runs fail-closed while leaving legacy outputs as SKIP."""
    try:
        from scripts.evidence_documents import validate_document_manifest, _atomic_write_json
        from scripts.evidence_facts import validate_fact_observations
    except ModuleNotFoundError:
        from evidence_documents import validate_document_manifest, _atomic_write_json
        from evidence_facts import validate_fact_observations

    output = Path(stock_dir)
    policy = _read_object(output / "official_evidence_policy.json")
    enforced = bool(policy.get("enforced"))
    if not policy:
        return {
            "schema_version": "official-evidence-validation.v1", "state": "SKIP", "status": "SKIP",
            "invalid_findings": [], "incomplete_findings": [], "warnings": [], "enforced": False,
        }
    manifest = _read_object(output / "document_manifest.json")
    facts = _read_object(output / "fact_observations.json")
    context = _read_object(output / "report_context.json")
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if not manifest:
        incomplete.append("document_manifest_missing")
    if not facts:
        incomplete.append("fact_observations_missing")
    if not context:
        incomplete.append("report_context_missing")
    if manifest:
        check = validate_document_manifest(manifest, output)
        invalid += check["invalid_findings"]
        incomplete += check["incomplete_findings"]
        warnings += check["warnings"]
    if facts and manifest:
        check = validate_fact_observations(facts, manifest, output)
        invalid += check["invalid_findings"]
        incomplete += check["incomplete_findings"]
        warnings += check["warnings"]
    if context:
        if context.get("schema_version") != EVIDENCE_CONTEXT_VERSION:
            invalid.append("report_context_schema_version_invalid")
        if (context.get("meta") or {}).get("manifest_hash") != manifest.get("manifest_hash"):
            invalid.append("report_context_manifest_hash_mismatch")
        if (context.get("meta") or {}).get("observation_hash") != facts.get("observation_hash"):
            invalid.append("report_context_observation_hash_mismatch")
        if (context.get("meta") or {}).get("context_fingerprint") != _context_fingerprint(context):
            invalid.append("report_context_fingerprint_mismatch")
        context_validation = context.get("validation") or {}
        invalid += list(context_validation.get("invalid_findings") or [])
        incomplete += list(context_validation.get("incomplete_findings") or [])
        warnings += list(context_validation.get("warnings") or [])
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if enforced and incomplete else "REVIEWABLE"
    result = {
        "schema_version": "official-evidence-validation.v1",
        "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": warnings,
        "enforced": enforced,
        "manifest_hash": manifest.get("manifest_hash"),
        "observation_hash": facts.get("observation_hash"),
        "context_fingerprint": (context.get("meta") or {}).get("context_fingerprint"),
        "coverage": context.get("coverage") or {},
    }
    if persist:
        _atomic_write_json(output / "official_evidence_validation.json", result)
    return result


def _resolve_output_dir(code: str, requested: str | None) -> Path:
    if requested:
        return Path(requested)
    base = str(code).split(".", 1)[0]
    candidates = sorted(Path(OUTPUT_BASE).glob(base + "_*"))
    canonical = [path for path in candidates if path.is_dir() and not re.search(r"_(?:phase|stage|try)_", path.name, re.IGNORECASE)]
    if len(canonical) == 1:
        return canonical[0]
    raise SystemExit("无法唯一确定输出目录，请使用 --output-dir")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建可回读的官方证据report context")
    parser.add_argument("--code", required=True)
    parser.add_argument("--output-dir", "--output")
    parser.add_argument("--legacy", action="store_true", help="仅生成旧版内存context，不写v2证据产物")
    parser.add_argument("--latest-year", type=int, default=2025)
    args = parser.parse_args()
    output = _resolve_output_dir(args.code, args.output_dir)
    if args.legacy:
        print(json.dumps(build_context(args.code, str(output), args.latest_year), ensure_ascii=False, indent=2))
        return 0
    bundle = build_official_evidence_bundle(output, args.code, persist=True)
    context = bundle["context"]
    print(json.dumps({
        "path": str(output / "report_context.json"),
        "state": context["validation"]["state"],
        "context_fingerprint": context["meta"]["context_fingerprint"],
        "coverage": context["coverage"],
    }, ensure_ascii=False))
    return 0 if context["validation"]["state"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
