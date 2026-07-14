#!/usr/bin/env python3
"""Auto-Fill v2.1 — Extract missing financial fields from STMT text → pdf_sections.

Called by data_gate.py on BLOCK/WARN. Section-scoped bilingual regex +
unit detection + cross-year scale normalization.
"""
import argparse, json, os, re, sys
from pathlib import Path
from typing import Optional

# ── Section markers ──
BS_MARKER = r"(?:STATEMENT OF FINANCIAL POSITION|FINANCIAL POSITION|CONSOLIDATED.*?FINANCIAL|綜合財務狀況表|合併資產負債表)"
IS_MARKER = r"(?:STATEMENT OF PROFIT OR LOSS|CONSOLIDATED.*?PROFIT|綜合損益表|合併利潤表|合併綜合收益表)"
CF_MARKER = r"(?:STATEMENT OF CASH FLOWS|CONSOLIDATED.*?CASH|綜合現金流量表|合併現金流量表)"

# ── Field patterns (bilingual + English-only) ──
PATTERNS = {
    "营业收入": [r'(?:营业收入|Revenue|收益|營業收入|營業額)[\s\S]{0,120}?([\d,]{5,})'],
    "营业成本": [r'(?:营业成本|Cost of sales|銷售成本|營業成本|Direct operating exp)[\s\S]{0,120}?([\d,]{5,})'],
    "归母净利润": [r'本公司擁有人\s+([\d,]{5,})\s+[\d,]{5,}\s*\n\s*少數股東權益', r'應佔溢利.*?本公司擁有人\s+([\d,]{5,})', r'(?:归属于母公司|归母|本公司權益股東|本公司擁有人應佔|Profit attributable to owners|Owners of the Company)[\s\S]{0,200}?([\d,]{5,})'],
    "少数股东损益": [r'少數股東(?:應佔|權益).*?([\d,]{4,})\s+[\d,]{4,}', r'Owners of the Company.*?\n\s*(?:–|－)\s*Non-controlling.*?([\d,]{4,})', r'Non-controlling interests\s+\d+\s*,\s*\d+\s*([\d,]{4,})', r'(?:少数股东损益|少數股東損益).*?([\d,]{4,})'],
    "税前利润": [r'稅前溢利\s+.*?([\d,]{5,})', r'除稅前溢利\s+.*?([\d,]{5,})', r'Profit before (?:income )?tax\s+\d*\s*([\d,]{4,})', r'(?:利润总额|利潤總額)[（(].*?([\d,]{5,})'],
    "所得税": [r'稅項支出\s+.*?(\(?[\d,]{4,}\)?)', r'Income tax (?:expense|expenses|credit)\s+\d*\s*(\(?[\d,]{4,}\)?)', r'(?:所得税费用|所得稅費用)[（(].*?(\(?[\d,]{4,}\)?)'],
    "资产总计": [r'(?:资产总[计計]|總資產|Total assets (?!less))[\s\S]{0,120}?([\d,]{5,})'],
    "货币资金": [r'(?:货币资金|現金及現金等價物|Cash and cash equivalents|Cash and bank)[\s\S]{0,120}?([\d,]{5,})'],
    "应收账款": [r'(?:应收账款|應收賬款|Trade receivables)[\s\S]{0,120}?([\d,]{4,})'],
    "应付账款": [r'(?:应付账款|應付賬款|Trade payables)[\s\S]{0,120}?([\d,]{4,})'],
    "存货": [r'(?:存货|存貨|Inventories)[\s\S]{0,120}?([\d,]{3,})'],
    "固定资产": [r'(?:固定资产|物業廠房及設備|Property, plant and equipment)[\s\S]{0,120}?([\d,]{4,})'],
    "固定资产折旧": [
        r'折舊及攤銷\s*(?:[\d]+[\(（][^)）]*[\)）]\s*)?([\d,]{4,})',  # v2.33: note refs like "6(c)"
        r'折舊及攤銷\s+[\d]+[)）]?\s*([\d,]{4,})',
        r'折舊\s+([\d,]{4,})',
        r'(?:固定资产折旧|物業廠房.*?折舊|Depreciation of (?:property|PPE))[\s\S]{0,200}?([\d,]{3,})'],
    "归母权益": [r'本公司擁有人[\s\S]{0,200}?([\d,]{5,})\s+[\d,]{5,}\s*\n\s*少數股東權益', r'Equity attributable[\s\S]{0,400}?Reserves[\s\S]{0,100}?([\d,]{5,})\s+[\d,]{5,}', r'歸屬於母公司所有者權益合計\s+([\d,]{5,})'],
    "少数股东权益": [r'少數股東權益\s+([\d,]{5,})\s+[\d,]{5,}\s*\n\s*總權益', r'EQUITY[\s\S]{0,500}?Non-controlling interests\s+([\d,]{4,})', r'少數股東權益\s+([\d,]{5,})'],
    "负债合计": [r'(?:负债总[计計]|负债合[计計]|總負債|Total liabilities (?!and))[\s\S]{0,120}?([\d,]{5,})'],
    "流动负债合计": [r'流動負債\s*\n[\s\S]{0,500}?(\d[\d,]{4,})\s*\n\s*總負債', r'Total current liabilities[\s\S]{0,50}?([\d,]{5,})', r'流動負債合計\s+([\d,]{5,})'],
    "非流动负债合计": [r'Total non-current liabilities[\s\S]{0,50}?([\d,]{4,})', r'非流動負債合計\s+([\d,]{5,})'],
    "流动资产合计": [r'流動資產\s*\n[\s\S]*?(\d[\d,]{4,})\s*\n\s*(?:分類|總資產)', r'Total current assets[\s\S]{0,50}?([\d,]{5,})', r'流動資產合計\s+([\d,]{5,})'],
    "非流动资产合计": [r'Total non-current assets[\s\S]{0,50}?([\d,]{5,})', r'非流動資產合計\s+([\d,]{5,})'],
    "商誉": [r'(?:商誉|商譽|Goodwill)[\s\S]{0,120}?([\d,]{3,})'],
    "无形资产": [r'(?:无形资产[^摊]|無形資產[^攤]|Intangible assets)[\s\S]{0,120}?([\d,]{3,})'],
    "使用权资产": [r'Right-of-use assets\s+\d+[ (b)\n]*\s*([\d,]{3,})', r'(?:使用权资产|使用權資產)[\s\S]{0,120}?([\d,]{3,})'],
    "租赁负债": [r'Lease liabilities\s+\d+[ (b)\n]*\s*([\d,]{3,})', r'(?:租赁负债|租賃負債)[\s\S]{0,120}?([\d,]{3,})'],
    "合同负债": [r'Contract liabilities[\s\S]{0,50}?([\d,]{4,})', r'(?:合同负债|合約負債)[\s\S]{0,120}?([\d,]{4,})'],
    "短期借款": [r'(?:短期借款|Short-term borrowings|Bank borrowings)[\s\S]{0,120}?([\d,]{3,})'],
    "长期借款": [r'(?:长期借款|Long-term borrowings|非流動銀行貸款)[\s\S]{0,120}?([\d,]{3,})'],
    "其他应收款": [r'Other receivables[\s\S]{0,80}?([\d,]{3,})', r'(?:其他应收|Prepayments, deposits and other)[\s\S]{0,120}?([\d,]{3,})'],
    "其他应付款": [r'Other payables[\s\S]{0,80}?([\d,]{3,})', r'(?:其他应付|Other payables and accruals)[\s\S]{0,120}?([\d,]{3,})'],
    "总股本": [r'Issued (?:share )?capital[\s\S]{0,80}?([\d,]{5,})', r'股本\s*[(（][^)）]+[)）]\s*([\d,]{5,})'],
    "经营活动CF": [r'營運業務[（(].*?[)）].*?現金淨額\s+\(?([\d,]{5,})\)?', r'經營活動.*?現金.*?淨額\s+([\d,]{5,})', r'(?:经营.*?现金.*?净额|Net cash (?:from|generated from) operating)[\s\S]{0,120}?([\d,]{5,})'],
    "Capex": [r'購入物業[、,\s]*廠房及設備\s+\(?([\d,]{4,})\)?', r'(?:Purchase of (?:items of )?PPE|购[建構].*?固定|購置.*?廠房)[\s\S]{0,120}?([\d,]{3,})'],
    "已付股息": [r'(?:已付股息|股息.*?支[付出]|Dividends paid)[\s\S]{0,200}?([\d,]{4,})'],
}

ZERO_OK = {'商誉', '短期借款', '长期借款', '其他应收款', '其他应付款', '总股本', '合同负债'}


def _safe_float(raw: str) -> Optional[float]:
    raw = raw.strip().replace(",", "")
    neg = raw.startswith("(") and raw.endswith(")")
    if neg: raw = raw[1:-1]
    try: v = float(raw); return -v if neg else v
    except: return None


def detect_unit(stmt: str) -> float:
    """Returns divisor: raw value / divisor = 百万元."""
    # 港幣千元 / HKD'000 / HK$'000 → /1000
    if re.search(r"(?:港幣|港币|港元)\s*[千仟]元|HKD?\s*['′]\s*000|HK\$\s*['′]\s*000", stmt[:5000]): return 1_000.0
    # 人民幣千元 / RMB'000 → /1000
    if re.search(r"(?:人民幣|人民币|RMB)\s*[千仟]元|RMB\s*['′]\s*000", stmt[:5000]): return 1_000.0
    # 人民幣元 / 人民币元 (A-share) → /1,000,000
    if re.search(r"(?:人民幣|人民币)\s*元", stmt[:5000]): return 1_000_000.0
    # 港幣元 / 港币元 (rare) → /1,000,000
    if re.search(r"(?:港幣|港币|港元)\s*元[^千仟]", stmt[:5000]): return 1_000_000.0
    # Heuristic: if most numbers are 9-10 digits, likely 元
    big = re.findall(r'[\d,]{9,10}', stmt[:5000])
    if len(big) > 5: return 1_000_000.0
    return 1_000.0


def section_search(field: str, stmt: str, pat: str) -> Optional[float]:
    bs = {'流动资产合计','非流动资产合计','无形资产','商誉','使用权资产','递延税项资产',
          '其他应收款','短期借款','长期借款','流动负债合计','非流动负债合计','负债合计',
          '租赁负债','其他应付款','归母权益','少数股东权益','总股本','货币资金','应收账款',
          '应付账款','存货','固定资产','合同负债','资产总计','递延税项负债'}
    if field in bs: marker, slen = BS_MARKER, 50000
    elif field in {'税前利润','所得税','营业利润','少数股东损益','营业收入','营业成本','归母净利润'}:
        marker, slen = IS_MARKER, 25000
    else: marker, slen = CF_MARKER, 30000
    m = re.search(marker, stmt)
    txt = stmt[m.start():min(len(stmt), m.start()+slen)] if m else stmt
    m2 = re.search(pat, txt, re.MULTILINE | re.DOTALL)
    if not m2: m2 = re.search(pat, stmt, re.MULTILINE | re.DOTALL)
    return _safe_float(m2.group(1)) if m2 else None


def normalize_scale(output_dir: str) -> int:
    corrections = 0; yearly = {}
    for fp in sorted(Path(output_dir).glob("pdf_sections_*.json")):
        if "interim" in fp.name: continue
        ym = re.search(r"(\d{4})", fp.name)
        if not ym: continue
        try:
            fin = json.loads(fp.read_text(encoding="utf-8")).get("financials", {})
            if fin: yearly[int(ym.group(1))] = fin
        except: pass
    for year, fin in yearly.items():
        rev = fin.get("营业收入", 0) or 0
        if rev <= 0 or 100 <= rev <= 500_000: continue
        div = 1.0
        if rev > 1_000_000:
            for d in [1_000_000, 1_000, 100]:
                if 100 <= rev / d <= 500_000: div = d; break
        elif rev < 10:
            for m in [1_000_000, 1_000, 100]:
                if 100 <= rev * m <= 500_000: div = 1.0 / m; break
        if div == 1.0: continue
        for k in list(fin.keys()):
            v = fin.get(k, 0) or 0
            if v and abs(v) > 0.01: fin[k] = round(v / div, 2); corrections += 1
    if corrections:
        for year, fin in yearly.items():
            fp = Path(output_dir) / f"pdf_sections_{year}.json"
            if fp.exists():
                try:
                    d = json.loads(fp.read_text(encoding="utf-8"))
                    d["financials"] = fin
                    fp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
                except: pass
        print(f"  normalize_scale: {corrections} corrections")
    return corrections


def run(output_dir: str, target_fields: Optional[list] = None) -> dict:
    out = Path(output_dir)
    files = sorted(out.glob("pdf_sections_*.json"))
    files = [f for f in files if "interim" not in f.name]
    if not files: return {}
    fields = target_fields or list(PATTERNS.keys())
    results = {}
    for fp in files:
        ym = re.search(r"(\d{4})", fp.name)
        if not ym: continue
        year = int(ym.group(1))
        try: data = json.loads(fp.read_text(encoding="utf-8"))
        except: continue
        stmt = data.get("STMT", "") or ""
        dan = data.get("DAN", "") or ""
        if dan: stmt = stmt + "\n" + dan  # v2.33: include DAN for D&A
        if not stmt: continue
        fin = data.get("financials", {})
        if not isinstance(fin, dict): fin = {}
        unit = detect_unit(stmt)
        filled = {}
        for field in fields:
            if field not in PATTERNS: continue
            cur = fin.get(field)
            if cur is not None and cur > 0: continue
            if cur == 0 and field in ZERO_OK: continue
            for pat in PATTERNS[field]:
                raw = section_search(field, stmt, pat)
                if raw is None: continue
                v = round(abs(raw) / unit, 2)
                if 0 < v < 100_000_000: fin[field] = v; filled[field] = v; break
            else:
                if field in ZERO_OK: fin[field] = 0; filled[field] = 0
        # Derived fields
        cl = fin.get("流动负债合计", 0) or 0
        ncl = fin.get("非流动负债合计", 0) or 0
        if cl > 0 and ncl > 0 and not fin.get("负债合计"):
            fin["负债合计"] = round(cl + ncl, 2); filled["负债合计"] = fin["负债合计"]
        ca = fin.get("流动资产合计", 0) or 0
        nca = fin.get("非流动资产合计", 0) or 0
        ta = fin.get("资产总计", 0) or 0
        if ca > 0 and nca > 0 and ta > 0 and (ca + nca) > ta * 1.5:
            fin["资产总计"] = round(ca + nca, 2); filled["资产总计"] = fin["资产总计"]
        if filled:
            data["financials"] = fin
            fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            results[year] = filled
    scale_fixes = normalize_scale(output_dir)
    total = sum(len(v) for v in results.values()) + scale_fixes
    if total:
        fset = set()
        for v in results.values(): fset.update(v.keys())
        print(f"[auto_fill] {total} values across {len(results)}y: {', '.join(sorted(fset))}")
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--fields")
    args = p.parse_args()
    if not os.path.isdir(args.output): print(f"ERROR: {args.output} not found", file=sys.stderr); return 1
    fl = [f.strip() for f in args.fields.split(",")] if args.fields else None
    r = run(args.output, fl)
    return 0 if r else 1


if __name__ == "__main__":
    sys.exit(main())
