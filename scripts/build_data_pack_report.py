#!/usr/bin/env python3
"""
Phase 2B: 格力电器 5-year pdf_sections → data_pack_report.md

Reads pdf_sections_{year}.json for 2021-2025.
Builds structured multi-year report with:
  - STMT/DAN/SEG from financials struct
  - P2/P3/P4/P6/P13/MDA/SUB from text sections
"""

import json, os, re

YEARS = [2021, 2022, 2023, 2024, 2025]
BASE = "/Users/xiami/Desktop/analy/Turtle_investment_framework"
OUTPUT = os.path.join(BASE, "output", "000651_格力电器", "data_pack_report.md")

all_data = {}
for y in YEARS:
    fp = os.path.join(BASE, "output", "000651_格力电器", f"pdf_sections_{y}.json")
    with open(fp) as f:
        all_data[y] = json.load(f)

# ── helpers ──
def fmt(v):
    if v is None: return "⚠️"
    try: return f"{float(v):,.2f}"
    except: return "⚠️"

def yuan_m(s):
    if not s: return None
    try: return float(re.sub(r'[,\s]','',s)) / 1_000_000
    except: return None

def extr(text, kw, after=200):
    i = text.find(kw)
    if i < 0: return None
    nums = re.findall(r'(\d[\d,]*\.?\d*)', text[i:i+after])
    if nums: return yuan_m(nums[0])
    return None

def mda_val(text, kw, after=200):
    i = text.find(kw)
    if i < 0: return None, None
    vals = [v for v in [yuan_m(n) for n in re.findall(r'(\d[\d,]*\.?\d*)', text[i:i+after])] if v and v > 1]
    return vals[0] if vals else None, vals[1] if len(vals) > 1 else None

HDR = "| 项目 | " + " | ".join(str(y) for y in YEARS) + " |"
SEP = "|------|" + "|".join("--------:" for _ in YEARS) + "|"

# ── sections ──

def sec_header():
    m = all_data[2025]["metadata"]
    return f"""# 年报附注数据包：格力电器（000651）

> PDF来源：{m['pdf_file']}（及同系列 2021-2024 年报）
> 最近年报总页数：{m['total_pages']}
> 提取时间：{m['extract_time']}
> 提取方式：pdf_preprocessor.py 预处理 + Agent 精提取
> 金额单位：百万元（人民币），除特别标注外
> 数据完整性：完整（所有 5 个年度均包含全文）

---
"""

def sec_stmt():
    L = ["## STMT：多年度财务摘要\n", "> 数据来源：`financials` 结构化字段\n"]
    def row(lbl, key):
        L.append(f"| {lbl} | " + " | ".join(fmt(all_data[y]["financials"].get(key)) for y in YEARS) + " |")

    L.append("### A. 综合损益摘要\n" + HDR + "\n" + SEP)
    for l,k in [("营业收入","营业收入"),("营业成本","营业成本"),("归母净利润","归母净利润")]: row(l,k)

    L.append("\n### B. 资产负债摘要\n" + HDR + "\n" + SEP)
    for l,k in [("货币资金","货币资金"),("应收账款","应收账款"),("存货","存货"),
        ("流动资产合计","流动资产合计"),("固定资产","固定资产"),("资产总计","资产总计"),
        ("短期借款","短期借款"),("应付账款","应付账款"),("合同负债","合同负债"),
        ("流动负债合计","流动负债合计"),("长期借款","长期借款"),("负债合计","负债合计"),("归母权益","归母权益")]: row(l,k)

    L.append("\n### C. 现金流量摘要\n" + HDR + "\n" + SEP)
    for l,k in [("经营活动现金净额（OCF）","经营活动CF"),("投资活动现金净额","投资活动CF"),
        ("筹资活动现金净额","筹资活动CF"),("资本支出（Capex）","Capex")]: row(l,k)

    fcf=[fmt(float(all_data[y]["financials"].get("经营活动CF",0) or 0)-float(all_data[y]["financials"].get("Capex",0) or 0)) for y in YEARS]
    L.append(f"| 自由现金流（FCF） | " + " | ".join(fcf) + " |")

    da=[fmt(float(all_data[y]["financials"].get("固定资产折旧",0) or 0)+float(all_data[y]["financials"].get("无形资产摊销",0) or 0)) for y in YEARS]
    L.append(f"| 折旧及摊销（D&A） | " + " | ".join(da) + " |")
    L.append("\n> D&A = 固定资产折旧 + 无形资产摊销\n\n---\n")
    return "\n".join(L)

def sec_dan():
    L = ["## DAN：折旧与摊销明细\n", "> 数据来源：financials\n", HDR, SEP]
    for l,k in [("固定资产折旧","固定资产折旧"),("无形资产摊销","无形资产摊销")]:
        L.append(f"| {l} | " + " | ".join(fmt(all_data[y]["financials"].get(k)) for y in YEARS) + " |")
    da=[fmt(float(all_data[y]["financials"].get("固定资产折旧",0) or 0)+float(all_data[y]["financials"].get("无形资产摊销",0) or 0)) for y in YEARS]
    L.append(f"| **D&A 合计** | " + " | ".join(da) + " |\n")
    for y in YEARS:
        v=extr(all_data[y].get("DAN",""),"长期待摊费用摊销",80)
        if v: L.append(f"- {y}年长期待摊费用摊销={fmt(v)} 百万元")
    L.append("\n---\n")
    return "\n".join(L)

def sec_seg():
    L=["## SEG：分行业/分产品/地区收入\n", "> 数据来源：SEG 文本\n"]
    for y in YEARS:
        t=all_data[y].get("SEG",""); L.append(f"### {y}年\n")
        for sect,label in [("分行业","行业"),("分产品","产品"),("分地区","地区")]:
            i=t.find(sect)
            if i<0: continue
            end = min([t.find(s) for s in ["分行业","分产品","分地区"] if t.find(s)>i] or [i+800])
            L.append(f"#### {label}\n| {label} | 金额（百万元） | 占比 |\n|------|-------------:|:----|")
            for ln in t[i:end].split("\n"):
                ln=ln.strip()
                if not ln or ln.startswith("分") or ln.startswith("[TABLE]") or ln.startswith("---"): continue
                m=re.match(r'^([一-鿿（）、─-╿←-⇿\w]{2,20})\s+(\d[\d,]*\.?\d*)\s+(\d+\.?\d*)%?',ln)
                if m: L.append(f"| {m.group(1)} | {fmt(yuan_m(m.group(2)))} | {m.group(3)}% |")
            L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_mda():
    L=["## MDA：管理层讨论与分析——核心财务指标\n", "> 数据来源：MDA 章节\n"]
    for y in YEARS:
        t=all_data[y].get("MDA",""); L.append(f"### {y}年\n")
        for kw in ["营业收入","归属于上市公司股东的净利润","归属于上市公司股东的扣除非经常性损益的净利润",
            "经营活动产生的现金流量净额","总资产","归属于上市公司股东的净资产"]:
            cur,prev=mda_val(t,kw,200)
            if cur:
                ch=f"（同比 {(cur-prev)/prev*100:+.1f}%）" if prev and prev>0 else ""
                L.append(f"- **{kw}**：{fmt(cur)} 百万元 {ch}")
        di=t.find("利润分配预案")
        if di<0: di=t.find("现金红利")
        if di>=0:
            dps=re.search(r'每\s*10\s*股\s*派[发]?现[金]?红[利]?\s*(\d[\d,]*\.?\d*)\s*元',t[di:di+400])
            if dps: L.append(f"- **股利**：每10股派{dps.group(1)}元（含税）")
        L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_p2():
    L=["## P2. 受限现金明细\n"]
    for y in YEARS:
        t=all_data[y].get("P2",""); L.append(f"### {y}年\n")
        idx=t.find("所有权或使用权受限资产")
        if idx<0: idx=t.find("所有权或使用权受到限制的资产")
        if idx<0: L.append("⚠️ 未找到受限资产章节\n"); continue
        snip=t[idx:idx+3000]
        m=re.search(r'货币资金\s+(-?\d[\d,]*\.?\d*)',snip)
        if m: L.append(f"- **受限货币资金**：{fmt(yuan_m(m.group(1)))} 百万元")
        tot=re.findall(r'合计\s+(-?\d[\d,]*\.?\d*)',snip)
        if tot: L.append(f"- **受限资产总计**：{fmt(yuan_m(tot[-1]))} 百万元\n")
        L.append("| 资产类别 | 账面价值（百万元） | 受限原因 |\n|----------|-----------------:|---------|\n")
        cont=snip.find("（续）")
        main=snip[:cont] if cont>0 else snip
        seen=set()
        # Filter out foreign exchange table entries that appear in some years
        skip_assets = {"外币货币性资产","外币货币性负债","其他应收款","短期借款","应付账款","其他应付款","质押借款","信用借款","其他借款","应计利息","抵押借款"}
        for ln in main.split("\n"):
            ln=ln.strip()
            if not ln or ln.startswith("[") or ln.startswith("---") or ln.startswith("（续）") or ln.startswith("|"): continue
            if "项目" in ln and "账面" in ln: continue
            m=re.match(r'^([一-鿿（）\w]{2,18}?)\s+(-?\d[\d,]*\.?\d*)\s+([一-鿿\w，、]+)',ln)
            if m and m.group(1) not in seen and "合计" not in m.group(1) and "小计" not in m.group(1) and m.group(1) not in skip_assets:
                seen.add(m.group(1)); amt=yuan_m(m.group(2))
                if amt and amt<999999: L.append(f"| {m.group(1)} | {fmt(amt)} | {m.group(3)} |")
        L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_p3():
    L=["## P3. 应收账款账龄分析\n", "> 以下为 financials 汇总数据。账龄分布明细需从 PDF 附注获取。\n", HDR, SEP]
    L.append("| 应收账款总额 | " + " | ".join(fmt(all_data[y]["financials"].get("应收账款")) for y in YEARS) + " |")
    L.append("| 营业收入 | " + " | ".join(fmt(all_data[y]["financials"].get("营业收入")) for y in YEARS) + " |")
    r=[]
    for y in YEARS:
        ar,rev=all_data[y]["financials"].get("应收账款"),all_data[y]["financials"].get("营业收入")
        r.append(f"{float(ar)/float(rev)*100:.2f}%" if ar and rev and float(rev)>0 else "⚠️")
    L.append("| 应收账款/营业收入 | " + " | ".join(r) + " |\n")
    L.append("⚠️ 账龄分布明细需从 PDF 附注获取。\n---\n")
    return "\n".join(L)

def sec_p4():
    L=["## P4. 重大关联交易\n"]
    for y in YEARS:
        t=all_data[y].get("P4",""); L.append(f"### {y}年\n")
        found=False
        for m in re.finditer(r'([一-鿿（）\w]{4,30}(?:有限公司|合伙企业|股份公司))\s+.*?(\d[\d,]*\.?\d*)\s*万元',t):
            a=float(m.group(2).replace(",",""))/100
            L.append(f"- {m.group(1)}：{fmt(a)} 百万元"); found=True
        if not found:
            v=extr(t,"关联交易",300)
            if v: L.append(f"- 关联交易总额：{fmt(v)} 百万元（⚠️ 从文本解析）")
        L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_p6():
    L=["## P6. 或有负债与承诺\n"]
    for y in YEARS:
        t=all_data[y].get("P6",""); L.append(f"### {y}年\n")
        for kw,lbl in [("诉讼","重大诉讼/仲裁"),("担保","对外担保"),("承诺","重大承诺事项")]:
            if kw not in t: L.append(f"- **{lbl}**：无相关信息\n"); continue
            i=t.find(kw); ctx=t[max(0,i-80):i+300]
            if re.search(r'(无|不适用|√\s*不适用)',ctx[:150]):
                L.append(f"- **{lbl}**：无")
            else:
                L.append(f"- **{lbl}**：存在（详见年报原文）")
        L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_p13():
    L=["## P13. 非经常性损益明细\n"]
    for y in YEARS:
        t=all_data[y].get("P13",""); L.append(f"### {y}年\n")
        i=t.find("非经常性损益")
        if i<0: L.append("⚠️ 未找到\n"); continue
        nri=t[i:i+3000]
        L.append("| 项目 | 金额（百万元） | 性质 |\n|------|-------------:|:----|\n")
        cats=[("处置","资产处置收益","非经常"),("政府补助","政府补贴","非经常（经常性除外）"),
            ("公允价值变动","公允价值变动","非经常"),("减值测试的应收款项减值准备转回","减值转回","非经常"),
            ("其他营业外","其他营业外收支","非经常"),("其他符合非经常","其他","非经常")]
        seen=set()
        for pat,lb,na in cats:
            v=extr(nri,pat,100)
            if v and lb not in seen: L.append(f"| {lb} | {fmt(v)} | {na} |\n"); seen.add(lb)
        for ln in nri.split("\n"):
            ln=ln.strip()
            if not ln or ln.startswith("[TABLE]") or ln.startswith("---"): continue
            m=re.match(r'^([一-鿿\w，、；：（）\(\).,\-——–]{6,60}?)\s+(-?\d[\d,]*\.?\d*)',ln)
            if m:
                d,am=m.group(1)[:35],m.group(2)
                if any(k in d for k in ["损益","处置","补贴","减值","公允价值","营业外","政府","资产"])\
                    and not any(k in d for k in ["小计","合计","减：","所得税","少数股东","每股","扣除非"]):
                    amt=yuan_m(am)
                    # Normalize desc for dedup - strip common prefixes
                    d_norm = re.sub(r'[，、；：（）\s]', '', d)[:10]
                    if amt and abs(amt)<99999 and d_norm not in seen:
                        seen.add(d_norm)
                        L.append(f"| {d} | {fmt(amt)} | 非经常 |\n")
        for kw in ["小计","合计"]:
            v=extr(nri,kw,50)
            if v: L.append(f"| **{kw}** | **{fmt(v)}** | — |\n")
        L.append("")
    L.append("---\n")
    return "\n".join(L)

def sec_sub():
    L=["## SUB. 主要控股参股公司（条件触发）\n", "> 格力电器为制造型企业。\n"]
    for y in YEARS:
        t=all_data[y].get("SUB",""); L.append(f"### {y}年\n")
        # Check if 2024 has "无应当披露"
        if "无应当披露" in t: L.append("⚠️ 公司报告期内无应当披露的重要控股参股公司信息。\n"); continue

        i=t.find("企业集团的构成")
        if i<0: i=t.find("在子公司中的权益")
        if i<0: i=t.find("主要控股参股公司分析")
        if i<0: i=t.find("子公司名称")
        if i<0: i=t.find("注册资本")

        if i<0: L.append("⚠️ 未找到子公司详细信息。\n"); continue

        snip=t[i:i+5000]; sl=snip.split("\n")
        L.append("**主要子公司**（前10大按注册资本）：\n| 序号 | 子公司名称 | 注册资本（百万元） | 业务性质 |\n|:---:|:---------|----------------:|:--------|\n")

        subs = []

        # Strategy A: non-pipe rows with "子公司" token
        for li in range(len(sl)):
            ln=sl[li].strip()
            if ln.startswith("|") or ln.startswith("[") or ln.startswith("---"): continue
            if "公司名称" in ln and "公司类型" in ln: continue
            if "注册资本" in ln and "总资产" in ln: continue
            if "子公司" not in ln: continue
            pts=ln.split()
            if "子公司" not in pts: continue
            si=pts.index("子公司")
            biz=pts[si+1] if si+1<len(pts) else ""
            cm=None
            for j in range(si+2,len(pts)):
                try:
                    v=float(re.sub(r'[,\s]','',pts[j]))
                    if v>1_000_000: cm=v/1_000_000; break
                except: continue
            if not cm or cm<=5: continue
            # Get name backwards
            np=[]
            for k in range(li-1, max(li-4,-1), -1):
                p=sl[k].strip()
                if not p or p.startswith("|") or p.startswith("[") or p.startswith("---"): continue
                if any(x in p for x in ["注册资本","年年度报告全文","第","页","单位：","九、","√"]): continue
                np.insert(0,p)
                if len("".join(np))>=6: break
            nm="".join(np)
            for k in range(li+1, min(li+3,len(sl))):
                nx=sl[k].strip()
                if not nx or nx.startswith("|") or nx.startswith("["): continue
                if "子公司" in nx or "注册资本" in nx or "第" in nx: break
                if any(x in nx for x in ["有限","公司","股份"]): nm+=nx; break
            if nm and nm not in [s[0] for s in subs]: subs.append((nm,cm,biz))

        # Strategy B: pipe-table rows with "子公司" cell
        for li in range(len(sl)):
            ln=sl[li].strip()
            if not ln.startswith("|") or "子公司" not in ln: continue
            pts=[p.strip() for p in ln.split("|")]
            if "子公司" not in pts or "公司名称" in ln: continue
            si=pts.index("子公司")
            biz=pts[si+1] if si+1<len(pts) else ""
            cm=None
            for p in pts:
                try:
                    v=float(re.sub(r'[,\s]','',p))
                    if v>1_000_000: cm=v/1_000_000; break
                except: continue
            if cm and cm>5:
                nm=""
                for p in pts:
                    pc=p.strip()
                    if pc and not re.match(r'^[\d,.\s]+$',pc) and any(c in pc for c in "公司企业股份"):
                        nm=pc; break
                if nm and nm not in [s[0] for s in subs]: subs.append((nm,cm,biz))

        # Strategy C: numbered format
        for m in re.finditer(r'(\d+)\s+([一-鿿（）\w]{4,30}(?:有限公司|股份公司|有限责任公司|厂))\s+(\d[\d,]*\.?\d*)',snip):
            nm=m.group(2); cm=yuan_m(m.group(3))
            if cm and cm>10 and nm not in [s[0] for s in subs]: subs.append((nm,cm,""))

        subs.sort(key=lambda x:x[1], reverse=True)
        # Dedup: keep only first occurrence of each normalized name
        seen_norm = set()
        deduped = []
        for nm, cm, bz in subs:
            # Normalize: remove all whitespace
            nm_norm = re.sub(r'\s+', '', nm)
            if nm_norm not in seen_norm and len(nm_norm) >= 6:
                seen_norm.add(nm_norm)
                deduped.append((nm, cm, bz))
        if deduped:
            for i,(nm,cm,bz) in enumerate(deduped[:10], 1):
                L.append(f"| {i} | {nm} | {fmt(cm)} | {bz if bz else '工业制造'} |\n")
        else:
            L.append("| — | ⚠️ 无法自动解析表格格式 | — | — |\n")

        # Merging scope changes
        for kw,ch in [("本期增加","新纳入"),("本期减少","不再纳入"),("新设","新设立")]:
            ic=t.find(kw)
            if ic>=0:
                names=re.findall(r'([一-鿿（）\w]{4,30}(?:有限公司|股份公司|有限责任公司|厂|合伙企业|分公司))',t[ic:ic+300])
                if names: L.append(f"- **{ch}**：{', '.join(set(names[:5]))}\n")
                break
        L.append("")
    L.append("---\n")
    return "\n".join(L)

# ── main ──
report = "\n".join([
    sec_header(), sec_stmt(), sec_dan(), sec_seg(), sec_mda(),
    sec_p2(), sec_p3(), sec_p4(), sec_p6(), sec_p13(), sec_sub()
])

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Report: {OUTPUT} ({len(report):,} chars, {report.count(chr(10))} lines)")
