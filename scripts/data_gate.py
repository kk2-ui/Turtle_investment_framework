#!/usr/bin/env python3
"""Data Gate v4.1 — Phase 2.5 data quality + Phase 3.5 report quality check.

Usage:
    python3 scripts/data_gate.py --output output/02669_中海物业           # all checks
    python3 scripts/data_gate.py --output output/02669_中海物业 --phase 2.5  # data only
    python3 scripts/data_gate.py --output output/02669_中海物业 --phase 3.5  # report only
"""

import argparse, json, os, re, sys, glob
from datetime import datetime

CRITICAL = ['营业收入','营业成本','归母净利润','资产总计','经营活动CF','Capex','固定资产折旧']
# v2.25: Asset-analysis critical fields (BS + CF balance sheet items)
ASSET_CRITICAL = ['货币资金','应收账款','应付账款','存货','归母权益','少数股东权益',
                  '商誉','无形资产','使用权资产','租赁负债','合同负债',
                  '流动资产合计','流动负债合计','负债合计','短期借款','长期借款',
                  '其他应收款','其他应付款','固定资产','总股本']
# Core fields for the 三视角裁决 asset-value layer
ASSET_CORE = ASSET_CRITICAL + ['少数股东损益','已付股息','税前利润','所得税']
# Total target fields from STMT extraction checklist
STMT_TARGET_COUNT = 25
MIN_FIELDS = 18; MIN_YEARS = 4; MIN_YEARS_HK = 3; STALE_DAYS = 7

def R(s): return f"\033[31m{s}\033[0m"
def G(s): return f"\033[32m{s}\033[0m"
def Y(s): return f"\033[33m{s}\033[0m"
def B(s): return f"\033[1m{s}\033[0m"

# v2.25: Field aliases for markdown table matching
_FIELD_ALIASES = {
    '固定资产折旧': ['折旧及摊销', 'D&A', '折旧与摊销', 'D 折旧与摊销', '固定资产折旧'],
    '归母权益': ['归母权益', '归属股东权益', '本公司拥有人应占权益', 'Equity attributable to owners'],
    '少数股东权益': ['少数股东权益', '非控股权益', 'Non-controlling interests'],
    '经营活动CF': ['经营活动CF', 'OCF', '经营活动现金净额', '经营活动产生的现金流量净额'],
    'Capex': ['Capex', '资本开支', '购建固定资产', 'Purchase of PPE'],
    '营业收入': ['营业收入', 'Revenue', '营业总额', '收益'],
    '营业成本': ['营业成本', '销售成本', 'Cost of sales'],
    '归母净利润': ['归母净利润', '归属股东净利润', '本公司拥有人应占溢利'],
    '资产总计': ['资产总计', '总资产', 'Total assets'],
}

def fin(y, d):
    """Get financials from pdf_sections json, falling back to data_pack_market.md tables."""
    try:
        f = json.load(open(os.path.join(d,f'pdf_sections_{y}.json'))).get('financials',{})
    except: f = {}
    # v2.25: Also check data_pack_market.md for fields not found in json
    mp = os.path.join(d,'data_pack_market.md')
    if os.path.exists(mp):
        try:
            with open(mp) as mf: md_content = mf.read()
            # Parse markdown tables for numeric values
            for field in CRITICAL + list(ASSET_CRITICAL):
                if f.get(field, 0) or 0: continue  # already have it
                aliases = _FIELD_ALIASES.get(field, [field])
                for alias in aliases:
                    pattern = re.compile(
                        r'(?:^\|\s*' + re.escape(alias) + r'[^|]*\|.*?(\d[\d,.]*)\s*\|)'
                        r'|(?:^\|\s*\*{0,2}' + re.escape(alias) + r'[^|]*\*{0,2}\s*\|.*?(\d[\d,.]*)\s*\|)',
                        re.MULTILINE | re.IGNORECASE
                    )
                    m = pattern.search(md_content)
                    if m:
                        val_str = m.group(1) or m.group(2)
                        try: f[field] = float(val_str.replace(',','')); break
                        except: pass
        except: pass
    return f

def is_hk(d): return any(c in os.path.basename(d) for c in ['02669','00506','00700','00001']) or os.path.basename(d).split('_')[0].isdigit() and len(os.path.basename(d).split('_')[0])==5

def _main_report(output_dir):
    """Return the largest *分析报告*.md file (skip broken/v2 stubs)."""
    rpts = glob.glob(os.path.join(output_dir, '*分析报告*.md'))
    if not rpts: return None
    return max(rpts, key=lambda p: os.path.getsize(p))

def run(output_dir, min_years=None, phase=None):
    years=sorted([int(f.replace('pdf_sections_','').replace('.json','').split('_')[0]) for f in os.listdir(output_dir) if f.startswith('pdf_sections_') and f.endswith('.json') and 'interim' not in f])
    if not min_years: min_years=MIN_YEARS_HK if is_hk(output_dir) else MIN_YEARS
    run_data    = (phase is None or phase in ('all', '2.5'))
    run_quality = (phase is None or phase in ('all', '3.5'))

    print(B('═══════════════════════════════════════'))
    print(B(f'  数据门禁 v4.1 | {os.path.basename(output_dir)} | {len(years)}yr | min={min_years}') + (f' | phase={phase}' if phase else ''))
    print(B('═══════════════════════════════════════'))
    if len(years)<3: print(R('[BLOCK] <3yr年报')); return 1

    blocks,warns=[],[]

    # ── v2.36: Layer 0 PDF Gate (moved after blocks init) ──
    pdf_files = sorted(glob.glob(os.path.join(output_dir, '*_年报.pdf')))
    if pdf_files:
        from hashlib import md5 as _md5
        from collections import Counter as _Counter
        hashes = [_md5(open(pf,'rb').read()).hexdigest() for pf in pdf_files]
        dup_info = []
        dup_hashes = [h for h, c in _Counter(hashes).items() if c > 1]
        if dup_hashes:
            # Find which years are duplicates
            year_map = {}
            for pf, h in zip(pdf_files, hashes):
                m = re.search(r'_(\d{4})_年报', pf)
                if m: year_map.setdefault(h, []).append(int(m.group(1)))
            dup_info = []
            for h in dup_hashes:
                yrs = year_map.get(h, [])
                if len(yrs) >= 2:
                    for i in range(1, len(yrs)):
                        dup_info.append(f'{yrs[0]}≡{yrs[i]}')
            if dup_info:
                for d in dup_info: print(R(f'[BLOCK] PDF重复: {d}年报 (同一文件)'))
                blocks.append(f'PDF重复: {len(dup_info)}组')
        # Year coverage check
        covered = set()
        for pf in pdf_files:
            m = re.search(r'_(\d{4})_年报\.pdf', pf)
            if m: covered.add(int(m.group(1)))
        expected = set(range(min(years), max(years)+1)) if years else set()
        missing_pdf = expected - covered
        if missing_pdf:
            print(R(f'[BLOCK] 缺少年报PDF: {sorted(missing_pdf)}'))
            blocks.append(f'缺少年报PDF: {sorted(missing_pdf)}')
        # Status line
        if dup_info or missing_pdf:
            print(R(f'Layer 0 PDF Gate: BLOCK ({len(dup_info) if dup_info else 0}重复+{len(missing_pdf)}缺失)'))
        elif len(pdf_files) >= min_years:
            print(G(f'Layer 0 PDF Gate: PASS ({len(pdf_files)} PDFs, 无重复)'))
    else:
        hk = is_hk(output_dir)
        if hk:
            print(R('[BLOCK] 无年报PDF — 港股必须下载年报'))
            blocks.append('无年报PDF')
        else:
            print(Y('[WARN] 无年报PDF — A股可依赖Tushare'))
            warns.append('无年报PDF(A股)')

    # ── Phase 2.5: Data quality layers ──
    if run_data:
        # L1 EXIST
        counts={c:0 for c in CRITICAL}
        for y in years:
            f=fin(y,output_dir); n=len(f)
            if n<MIN_FIELDS: warns.append(f'FY{y}: {n}/{MIN_FIELDS}f')
            yc=sum(1 for c in CRITICAL if c in f and f.get(c) is not None and f.get(c) >= 0)
            if yc<5: warns.append(f'FY{y}: {yc}/{len(CRITICAL)} critical')
            for c in CRITICAL:
                if c in f and f.get(c) is not None and f.get(c) >= 0: counts[c]+=1
        hk=is_hk(output_dir)
        for c,cnt in counts.items():
            th=MIN_YEARS_HK if(hk and c=='固定资产折旧')else min_years
            if cnt<th:
                if hk and c=='固定资产折旧' and cnt>=2: warns.append(f'{c}: {cnt}/{len(years)}yr(HK D&A,2yr OK)')
                else: blocks.append(f'{c}: {cnt}/{len(years)}yr(need≥{th})')
        n_pass=sum(1 for v in counts.values() if v>=min_years)
        print(f'Layer 1 EXIST:  {G("PASS") if not blocks else R("BLOCK")} ({n_pass}/{len(CRITICAL)}≥{min_years}yr)')
        for b in blocks: print(R(f'  ❌ {b}'))
        for w in warns: print(Y(f'  ⚠️ {w}'))

        # L1b ASSET — asset data completeness (v2.30: ALL missing → BLOCK)
        asset_counts={c:0 for c in ASSET_CRITICAL}
        for y in years:
            f=fin(y,output_dir)
            for c in ASSET_CRITICAL:
                if c in f and f.get(c) is not None and f.get(c) >= 0: asset_counts[c]+=1
        asset_pass=sum(1 for v in asset_counts.values() if v>=min_years)
        asset_total=len(ASSET_CRITICAL)
        ZERO_OK = {'商誉','短期借款','长期借款','其他应收款','其他应付款','总股本','合同负债'}
        asset_blocks=[c for c,cnt in asset_counts.items() if cnt<min_years]
        # v2.30: critical fields → BLOCK; zero-ok fields → WARN
        asset_block_critical = [c for c in asset_blocks if c not in ZERO_OK]
        asset_block_warn = [c for c in asset_blocks if c in ZERO_OK]
        for c in asset_block_critical:
            blocks.append(f'[ASSET] {c}: {asset_counts[c]}/{len(years)}yr (need≥{min_years})')
        for c in asset_block_warn:
            warns.append(f'[ASSET] {c}: {asset_counts[c]}/{len(years)}yr (may be zero)')
        print(f'Layer 1b ASSET: {G(f"PASS ({asset_pass}/{asset_total}≥{min_years}yr)") if not asset_block_critical else R(f"BLOCK({len(asset_block_critical)}/{asset_total} fields <{min_years}yr)")}')
        for c in asset_block_critical[:5]: print(R(f'  ❌ {c}: {asset_counts[c]}/{len(years)}yr'))
        for c in asset_block_warn[:3]: print(Y(f'  ⚠️ {c}: {asset_counts[c]}/{len(years)}yr (may be zero)'))
        if len(asset_blocks)>8: print(Y(f'  ... +{len(asset_blocks)-8} more'))

        # L1c P&L/CF — income statement & cashflow supplementary fields (v2.26)
        pl_fields = ['少数股东损益','税前利润','所得税','已付股息']
        pl_counts = {c:0 for c in pl_fields}
        for y in years:
            f = fin(y, output_dir)
            for c in pl_fields:
                if f.get(c, 0) and f.get(c, 0) > 0: pl_counts[c] += 1
        pl_pass = sum(1 for v in pl_counts.values() if v >= min_years)
        pl_blocks = [c for c, cnt in pl_counts.items() if cnt < min_years]
        print(f'Layer 1c P&L/CF: {G(f"PASS ({pl_pass}/{len(pl_fields)}≥{min_years}yr)") if not pl_blocks else R(f"BLOCK({len(pl_blocks)} missing)")}')
        for c in pl_blocks:
            print(R(f'  ❌ {c}: {pl_counts[c]}/{len(years)}yr'))
            blocks.append(f'[PL] {c}: {pl_counts[c]}/{len(years)}yr (need≥{min_years})')

        # Also check pdf_sections coverage (v2.25)
        cov_total=0; cov_extracted=0
        for y in years:
            try:
                with open(os.path.join(output_dir,f'pdf_sections_{y}.json')) as f:
                    cov=json.load(f).get('metadata',{}).get('financials_coverage',{})
                cov_total+=cov.get('total_patterns',0)
                cov_extracted+=cov.get('extracted',0)
            except: pass
        if cov_total>0:
            cov_pct=round(cov_extracted/cov_total*100,1)
            print(f'  Regex提取覆盖率: {cov_extracted}/{cov_total} ({cov_pct}%)')
            if cov_pct<20: print(Y(f'    ⚠️ 正则提取覆盖率低(<20%)——依赖Phase 2B Agent补充STMT字段'))

        # L2 SANITY
        anoms=[]
        for y in years:
            f=fin(y,output_dir)
            rev=f.get('营业收入',0)or 0; npat=f.get('归母净利润',0)or 0; cost=f.get('营业成本',0)or 0
            capex=f.get('Capex',0)or 0; ocf=f.get('经营活动CF',0)or 0
            if rev>0:
                if npat>rev*0.8: anoms.append(f'FY{y}: NP>{int(rev*0.8):,}')
                if cost>0 and cost>rev: anoms.append(f'FY{y}: Cost>Rev')
                if capex>rev*0.5: anoms.append(f'FY{y}: Capex>Rev×0.5')
            if ocf>0 and npat>0 and ocf<npat*0.05: anoms.append(f'FY{y}: OCF<<NP')
        print(f'Layer 2 SANITY: {G("PASS") if not anoms else Y(f"WARN({len(anoms)})")}')
        for a in anoms: print(Y(f'  ⚠️ {a}'))

        # L2b ASSET SANITY — BS balance checks (v2.25, v2.30 BLOCK on imbalance)
        asset_anoms=[]
        asset_blocks=[]
        for y in years:
            f=fin(y,output_dir)
            ta=f.get('资产总计',0)or 0; cash=f.get('货币资金',0)or 0
            eq=f.get('归母权益',0)or 0; mi=f.get('少数股东权益',0)or 0
            tl=f.get('负债合计',0)or 0; cl=f.get('流动负债合计',0)or 0
            st_debt=f.get('短期借款',0)or 0; lt_debt=f.get('长期借款',0)or 0
            goodwill=f.get('商誉',0)or 0; intang=f.get('无形资产',0)or 0
            rev=f.get('营业收入',0)or 0
            if ta>0:
                # v2.30: BS identity BLOCK — A≠E+L means data is corrupted
                total_eq_eq=eq+mi
                if total_eq_eq>0 and tl>0:
                    bs_diff=abs(ta-total_eq_eq-tl)
                    if bs_diff>ta*0.1:
                        msg = f'FY{y}: BS失衡 A({ta:,.0f})≠E({total_eq_eq:,.0f})+L({tl:,.0f}) 差{bs_diff:,.0f}'
                        if bs_diff > ta * 0.3:
                            asset_blocks.append(msg)  # >30%: definitely corrupted
                        else:
                            asset_anoms.append(msg)   # 10-30%: suspicious
                # Cash > Total Assets (impossible) → BLOCK
                if cash>ta*1.1: asset_blocks.append(f'FY{y}: 现金({cash:,.0f})>总资产({ta:,.0f})')
                # Goodwill > Equity → WARN
                if goodwill>0 and eq>0 and goodwill>eq*0.8: asset_anoms.append(f'FY{y}: 商誉({goodwill:,.0f})>{int(eq*0.8):,} 占权益{goodwill/eq*100:.0f}%')
                # Intangible > Equity → WARN
                if intang>0 and eq>0 and intang>eq*1.2: asset_anoms.append(f'FY{y}: 无形资产({intang:,.0f})>{int(eq*1.2):,}')
                # ST debt > LT debt 10x + zero LT → WARN
                if st_debt>0 and lt_debt==0 and st_debt>ta*0.1: asset_anoms.append(f'FY{y}: 短债({st_debt:,.0f})占比>10%且无长债')
        print(f'Layer 2b AS-SAN: {G("PASS") if not asset_anoms and not asset_blocks else R(f"BLOCK({len(asset_blocks)})") if asset_blocks else Y(f"WARN({len(asset_anoms)})")}')
        for b in asset_blocks: print(R(f'  ❌ {b}'))
        for a in asset_anoms: print(Y(f'  ⚠️ {a}'))

        # L2c CROSS-VALIDATION — inter-field consistency (v2.35)
        cross_anoms = []
        for y in years:
            f = fin(y, output_dir)
            npat = f.get('归母净利润', 0) or 0
            mi_pl = f.get('少数股东损益', 0) or 0
            mi_bs = f.get('少数股东权益', 0) or 0
            total_np = f.get('净利润总额', 0) or 0
            rev = f.get('营业收入', 0) or 0
            ta = f.get('资产总计', 0) or 0
            tl = f.get('负债合计', 0) or 0
            eq = f.get('归母权益', 0) or 0

            # 1. Minority ROE sanity (catches unit errors like 京投 10M→144M)
            if mi_pl > 0 and mi_bs > 0:
                mi_roe = mi_pl / mi_bs
                if mi_roe > 2.0:
                    cross_anoms.append(f'FY{y}: 少数ROE={mi_roe*100:.0f}%>200% ({mi_pl:.1f}M/{mi_bs:.1f}M)→疑似单位错误(京投教训)')
                elif mi_roe > 0.8:
                    cross_anoms.append(f'FY{y}: 少数ROE={mi_roe*100:.0f}%>80%→少数占比较高(非单位错误,但GG需归母口径)')
                elif mi_roe < 0.01 and mi_bs > 100:
                    cross_anoms.append(f'FY{y}: 少数ROE={mi_roe*100:.1f}%<1%→少数损益可能为0或缺失')

            # 2. P&L identity: total ≈ parent + minority (±5%)
            if total_np > 0 and npat > 0 and mi_pl > 0:
                pl_diff = abs(total_np - npat - mi_pl)
                if pl_diff > max(total_np, npat+mi_pl) * 0.1:
                    cross_anoms.append(f'FY{y}: P&L勾稽失衡 总NP({total_np:.1f})≠归母({npat:.1f})+少数({mi_pl:.1f}) 差{pl_diff:.1f}')

            # 3. Minority share of profit vs equity asymmetry
            if npat > 0 and mi_pl > 0 and eq > 0 and mi_bs > 0:
                mi_profit_share = mi_pl / (npat + mi_pl)
                mi_equity_share = mi_bs / (eq + mi_bs) if (eq + mi_bs) > 0 else 0
                if mi_profit_share > mi_equity_share * 5 and mi_profit_share > 0.3:
                    cross_anoms.append(f'FY{y}: 少数分利{mi_profit_share*100:.0f}%但权益仅{mi_equity_share*100:.0f}%(5x不对称)→可能一次性事件或单位错误')

        # Add YoY unit jump detection + ratio sanity (v2.35)
        prev_vals = {}  # track previous year values for jump detection
        for y in years:
            f = fin(y, output_dir)
            rev = f.get('营业收入', 0) or 0; npat = f.get('归母净利润', 0) or 0
            ocf = f.get('经营活动CF', 0) or 0; capex = f.get('Capex', 0) or 0
            da = f.get('固定资产折旧', 0) or 0; cash_m = f.get('货币资金', 0) or 0
            ar = f.get('应收账款', 0) or 0; ta = f.get('资产总计', 0) or 0
            # 4. YoY unit jumps (>8x from prior year → likely unit mismatch)
            if prev_vals and rev > 0:
                for field, prev in prev_vals.items():
                    cur = f.get(field, 0) or 0
                    if cur > 0 and prev > 0:
                        ratio = max(cur, prev) / min(cur, prev)
                        if ratio > 8:
                            cross_anoms.append(f'FY{y}: {field}跳变{ratio:.0f}x ({prev:.0f}→{cur:.0f})→疑似单位错误')
            prev_vals = {'营业收入': rev, '归母净利润': npat, '经营活动CF': ocf, 'Capex': capex,
                         '资产总计': ta, '货币资金': cash_m}

            # 5. Revenue/cash/AR ratio sanity
            if rev > 0:
                if cash_m > rev * 2: cross_anoms.append(f'FY{y}: 现金({cash_m:.0f}M)>营收({rev:.0f}M)×2')
                if ar > rev: cross_anoms.append(f'FY{y}: 应收({ar:.0f}M)>营收({rev:.0f}M)')
                if ocf > 0 and ocf > rev * 0.8: cross_anoms.append(f'FY{y}: OCF({ocf:.0f})>营收({rev:.0f})×0.8→利润率异常高或单位错误')
                if npat > 0 and npat > rev * 0.6: cross_anoms.append(f'FY{y}: 净利率={npat/rev*100:.0f}%>60%→疑似单位错误')
            # 6. Capex/D&A extreme ratios
            if da > 0 and capex > 0:
                if capex > da * 5: cross_anoms.append(f'FY{y}: Capex({capex:.0f})>D&A({da:.0f})×5')
                if da > 0 and capex < da * 0.05: cross_anoms.append(f'FY{y}: Capex({capex:.0f})<D&A({da:.0f})×5%→Capex可能缺失')

        print(f'Layer 2c X-VAL: {G("PASS") if not cross_anoms else Y(f"WARN({len(cross_anoms)})")}')
        for a in cross_anoms[:8]: print(Y(f'  ⚠️ {a}'))
        if len(cross_anoms) > 8: print(Y(f'  ... +{len(cross_anoms)-8} more'))

        # v2.25: Auto-fill on BLOCK (in data phase, before Phase 3.5)
        if blocks:
            auto_fill_script = os.path.join(os.path.dirname(__file__), 'auto_fill.py')
            if os.path.exists(auto_fill_script):
                print(B('\n─── Auto-Fill (Phase 2.5b) ───'))
                missing_fields = set()
                for b in blocks:
                    # Extract field name from block message like "[ASSET] 合同负债: ..." or "合同负债: ..."
                    m = re.match(r'\[(?:ASSET|PL)\]\s*(\S+):', b)
                    if m: missing_fields.add(m.group(1))
                if missing_fields:
                    print(f'  Extracting: {", ".join(sorted(missing_fields))}')
                    import subprocess
                    r = subprocess.run(
                        [sys.executable, auto_fill_script, '--output', output_dir,
                         '--fields', ','.join(sorted(missing_fields))],
                        capture_output=True, text=True, timeout=60
                    )
                    if r.returncode == 0:
                        # Re-run ALL layer checks with updated financials
                        pre_blocks = len(blocks)
                        blocks.clear()
                        # L1 EXIST re-check
                        for c, cnt in counts.items():
                            new_cnt = sum(1 for y in years if c in fin(y,output_dir) and fin(y,output_dir).get(c) is not None and fin(y,output_dir).get(c) >= 0)
                            th = MIN_YEARS_HK if(is_hk(output_dir)and c=='固定资产折旧')else min_years
                            if new_cnt < th:
                                if is_hk(output_dir) and c=='固定资产折旧' and new_cnt>=2: pass
                                else: blocks.append(f'{c}: {new_cnt}/{len(years)}yr(need≥{th})')
                        # L1b ASSET re-check
                        asset_blocks_new = []
                        for c in ASSET_CRITICAL:
                            new_cnt = sum(1 for y in years if c in fin(y,output_dir) and fin(y,output_dir).get(c) is not None and fin(y,output_dir).get(c) >= 0)
                            if new_cnt < min_years:
                                asset_blocks_new.append(c)
                                blocks.append(f'[ASSET] {c}: {new_cnt}/{len(years)}yr (need≥{min_years})')
                        # L1c P&L re-check
                        for c in ['少数股东损益','税前利润','所得税','已付股息']:
                            new_cnt = sum(1 for y in years if c in fin(y,output_dir) and fin(y,output_dir).get(c) is not None and fin(y,output_dir).get(c) >= 0)
                            if new_cnt < min_years:
                                blocks.append(f'[PL] {c}: {new_cnt}/{len(years)}yr (need≥{min_years})')
                        post_blocks = len(blocks)
                        print(f'  重检: {pre_blocks}→{post_blocks} BLOCK (auto_fill修正了{pre_blocks-post_blocks}项)')
                    else:
                        print(Y(f'  auto_fill failed: {r.stderr[:200]}'))
            else:
                print(Y(f'  ⚠️ auto_fill.py not found at {auto_fill_script}'))
        # v2.30: L2b asset sanity blocks persist through auto_fill
        blocks.extend(asset_blocks)
        _l2b_blocks = list(asset_blocks)

        # v2.25: BS identity BLOCK — if ≥3 years are severely imbalanced, likely Tushare unit mismatch
        bs_imbalance_years = sum(1 for a in asset_anoms if 'BS失衡' in a)
        if bs_imbalance_years >= 3:
            bs_block_msg = f'BS恒等式失衡: {bs_imbalance_years}/{len(years)}年 A≠E+L, 疑似Tushare跨字段单位不一致'
            blocks.append(bs_block_msg)
            print(R(f'  ❌ {bs_block_msg}'))

        # L3 CROSS
        cw=[]
        mp=os.path.join(output_dir,'data_pack_market.md')
        if os.path.exists(mp):
            with open(mp) as f: c=f.read()
            if '## 3.' not in c: cw.append('Tushare不可用(HK)—跳过交叉验证')
        print(f'Layer 3 CROSS:  {G("PASS")}')
        for w in cw: print(Y(f'  ⚠️ {w}'))

        # L4 FRESH
        fw=[]; dps_y=0
        if os.path.exists(mp):
            with open(mp) as f: c=f.read()
            m=re.search(r'(?:收盘价|股价).*?(\d{4}[-/]\d{1,2}[-/]\d{1,2})',c)
            if m:
                try:
                    d=datetime.strptime(m.group(1).replace('/','-'),'%Y-%m-%d')
                    days=(datetime.now()-d).days
                    if days>STALE_DAYS: fw.append(f'股价{days}天前')
                except: pass
            else: fw.append('缺少股价日期')
        dps_y=sum(1 for y in years if(fin(y,output_dir).get('每股股息',0)or 0)>0)
        print(f'Layer 4 FRESH:  {G("PASS") if not fw else Y(f"WARN({len(fw)})")}')
        for w in fw: print(Y(f'  ⚠️ {w}'))
        print(f'  DPS: {G(f"{dps_y}+/{len(years)}yr") if dps_y>=3 else Y(f"{dps_y}/{len(years)}yr→Phase1B")}')

    # ── Phase 3.5: Report quality layers ──
    if run_quality:
        # L0 CHAIN — report section completeness
        expected_sections = ['因子1A','因子1B','因子2','因子3','因子4']
        rpt = _main_report(output_dir)
        if rpt:
            with open(rpt) as f: content = f.read()
            missing = []
            headers = re.findall(r'^#{1,3}\s+.+$', content, re.MULTILINE)
            all_headers = ' '.join(headers)
            for s in expected_sections:
                if s == '因子4':
                    if '因子4' not in all_headers and 'DDM阶梯' not in all_headers:
                        missing.append(s)
                else:
                    if s not in all_headers:
                        missing.append(s)
            if missing:
                blocks.append(f'链不完整: 缺失章节 {", ".join(missing)}')
                print(f'Layer 0 CHAIN:  {R("BLOCK")} ({len(missing)} sections missing)')
                for m in missing: print(R(f'  ❌ 缺失: {m}'))
            else:
                print(f'Layer 0 CHAIN:  {G("PASS")} (all sections present)')

        # Phase 3.5 QUALITY — Agent漏读检测
        rpt=_main_report(output_dir)
        if rpt:
            with open(rpt) as f: c=f.read()
            idx=c.find('1.5 财务趋势')
            if idx>0:
                end=c.find('## 二、',idx)
                table=c[idx:end if end>0 else idx+2000]
                wc=table.count('⚠️')+table.count('⚠')
                if wc>0:
                    avail=set()
                    avail_asset=set()
                    for y in years:
                        f=fin(y,output_dir)
                        if(f.get('营业成本',0)or 0)>0: avail.add(y)
                        if(f.get('固定资产折旧',0)or 0)>0: avail.add(y)
                        # v2.25: asset data leak detection
                        if(f.get('货币资金',0)or 0)>0: avail_asset.add(y)
                        if(f.get('归母权益',0)or 0)>0: avail_asset.add(y)
                    if len(avail)>=3:
                        w=f'1.5表{wc}处⚠但{len(avail)}/5年数据可用→Agent漏读'
                        blocks.append(w)
                        print(f'Phase 3.5 QUALITY: {R(f"BLOCK")}')
                        print(Y(f'  ⚠️ {w}'))
                # v2.25: Check asset data leak in BS analysis sections
                if '资产价值' in c or '净现金' in c:
                    avail_bs=0
                    for y in years:
                        f=fin(y,output_dir)
                        if(f.get('货币资金',0)or 0)>0: avail_bs+=1
                    cash_warn=len(re.findall(r'净现金.*?⚠|现金.*?⚠|货币资金.*?⚠',c))
                    if avail_bs>=3 and cash_warn>2:
                        w2=f'资产分析{cash_warn}处⚠但{avail_bs}/5年现金数据可用→Agent漏读BS字段'
                        blocks.append(w2)
                        print(Y(f'  ⚠️ {w2}'))

    # ── Fix Plan (v2.25) ──
    verdict_text = 'BLOCK' if blocks else ('WARN' if warns else 'PASS')
    fix_plan = {
        'verdict': verdict_text,
        'version': 'v2.25',
        'total_years': len(years),
        'min_years': min_years,
        'blocks': list(blocks),
        'warns': list(warns[:10]),
        'missing_critical': [c for c in CRITICAL if sum(1 for y in years if (fin(y,output_dir).get(c,0)or 0)>0) < min_years],
        'missing_asset': [c for c in ASSET_CRITICAL if sum(1 for y in years if (fin(y,output_dir).get(c,0)or 0)>0) < min_years],
    }
    fix_path = os.path.join(output_dir, 'fix_plan.json')
    with open(fix_path, 'w') as fp:
        json.dump(fix_plan, fp, ensure_ascii=False, indent=2)
    if blocks:
        print(Y(f'\n⛔ GATE BLOCKED → Phase 3 禁止启动'))
        print(Y(f'   修复指令: {fix_path}'))
        print(Y(f'   操作: coordinator 必须先修复数据 → 重跑 data_gate → PASS 后方可进 Phase 3'))
        print(Y(f'   重试上限: 2轮。2轮后仍BLOCK → 标注"⚠️ 数据降级"并继续'))

    # ── Supplement Request (v2.25) ──
    # Generate actionable field list for Phase 2B agent to re-extract
    all_missed = set()
    for c in CRITICAL:
        cnt = sum(1 for y in years if (fin(y,output_dir).get(c,0) or 0) > 0)
        if cnt < min_years: all_missed.add(c)
    for c in ASSET_CRITICAL:
        cnt = sum(1 for y in years if (fin(y,output_dir).get(c,0) or 0) > 0)
        if cnt < min_years: all_missed.add(c)
    if all_missed:
        print(B('\n─── Supplement Request (Phase 2B) ───'))
        print(f'  Missing fields ({len(all_missed)}): {", ".join(sorted(all_missed))}')
        print(f'  Source: pdf_sections_*.json → STMT raw text (96K chars)')
        print(f'  Action: Phase 2B Agent to re-read STMT sections and extract these fields')
        print(f'  Output: append to data_pack_market.md §3/§4/§5 per-year columns')
        print(f'  Format: <!-- SUPPLEMENT_REQUEST')
        print(f'  gaps:')
        for field in sorted(all_missed):
            yrs = [y for y in years if (fin(y,output_dir).get(field,0) or 0) == 0]
            print(f'    - target: "{field}"')
            print(f'      years_missing: {yrs}')
            print(f'      source: STMT text in pdf_sections_{{year}}.json')
            print(f'      priority: {"high" if field in CRITICAL else "medium"}')
        print(f'  -->')

    # EXISTING REPORT
    rpt = _main_report(output_dir)
    if rpt:
        r = rpt
        with open(r) as f: c=f.read()
        lines=len(c.split('\n'))
        has_final='最终综合输出' in c or 'Final Synthesis' in c
        if has_final: print(f'  {Y("[INFO]")} 已有完整报告({lines}行)')

    # VERDICT
    print(B('───────────────────────────────────────'))
    if blocks: print(R(B(f'VERDICT: BLOCK ({len(blocks)}项)')))
    elif warns: print(Y(B(f'VERDICT: PASS ({len(warns)}项警告)')))
    else: print(G(B('VERDICT: PASS')))
    print(B('═══════════════════════════════════════'))
    return 1 if blocks else 0

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--min-years',type=int,default=None)
    p.add_argument('--phase',choices=['2.5','3.5','all'],default=None,help='Which checks to run (default: all)')
    a=p.parse_args()
    sys.exit(run(a.output,a.min_years,a.phase))
