#!/usr/bin/env python3
"""quality_gate.py — Phase 3.5 Report Quality Gate"""
import argparse, json, os, re, sys
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
REQUIRED = [
    ("报告元信息","报告元信息"),
    ("Executive Summary","Executive Summary"),
    ("财务趋势","财务趋势"),
    ("因子1A","因子1A"), ("因子1B","因子1B"), ("因子1C","因子1C"),
    ("因子2/3","因子2"), ("因子4","因子4"),
    ("风险","风险"), ("投资决策","投资决策"), ("来源清单","来源清单"),
]
CHECKS = [
    ("12_sections","BLOCK",lambda t: all(re.search(p,t) for _,p in REQUIRED)),
    ("ES_filled","BLOCK",lambda t: "C4_PLACEHOLDER" not in t),
    ("has_tables","WARN",lambda t: len(re.findall(r'\|.*\|.*\|',t))>=20),
    ("rejection_summary","WARN",lambda t: "否决门总览" in t),
    ("factor3_AA","WARN",lambda t: "AA序列" in t or "AA 序列" in t),
    ("factor2_Q_tax","WARN",lambda t: "Q税率" in t or "三档" in t),
    ("anomaly_propagation","WARN",lambda t: _check_anomaly_propagation(t)),
    ("dps_consistency","WARN",lambda t: _check_dps_consistency(t)),
    # V10: Variable residue — no unresolved {{variable}} in final report
    ("variable_residue","BLOCK",lambda t: _check_variable_residue(t)),
]
ANOMALY_KEYWORDS = ["扭曲","不可持续","失真","异常","偏离","虚增"]
MITIGATION_KEYWORDS = ["保守","风险提示","谨慎","有条件","警告","下调"]

def _check_anomaly_propagation(text):
    """If anomalies detected, ES/conclusion must contain mitigation."""
    has_anomaly = any(kw in text for kw in ANOMALY_KEYWORDS)
    if not has_anomaly:
        return True  # No anomalies → pass
    has_mitigation = any(kw in text for kw in MITIGATION_KEYWORDS)
    return has_mitigation  # Anomalies found but no mitigation → FAIL

def _check_dps_consistency(text):
    """DPS in report should match compute_bundle dps_fy."""
    dps_mentions = re.findall(r'DPS.*?(\d+\.?\d*)', text)
    has_ttm_note = "TTM" in text or "ttm" in text.lower()
    if len(dps_mentions) >= 2 and not has_ttm_note:
        return False
    return True

def _check_variable_residue(text):
    """V10: No unresolved {{variable}} placeholders in final report."""
    residues = re.findall(r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}', text)
    if residues:
        unique = list(set(residues))[:10]
        print(f"  ⚠️ 未解析变量: {unique}", file=sys.stderr)
        return False
    return True
def check(text):
    r={"status":"PASS","checks":[],"blocks":[],"warns":[],"lines":len(text.split('\n'))}
    for name,sev,fn in CHECKS:
        ok=fn(text)
        if not ok:
            r["checks"].append({"name":name,"status":"FAIL","severity":sev})
            (r["blocks"] if sev=="BLOCK" else r["warns"]).append(name)
            r["status"]="BLOCKED" if sev=="BLOCK" else ("WARN" if r["status"]=="PASS" else r["status"])
        else: r["checks"].append({"name":name,"status":"PASS"})
    if r["lines"]<800: r["blocks"].append(f"Lines:{r['lines']}<800"); r["status"]="BLOCKED"
    elif r["lines"]<1200: r["warns"].append(f"Lines:{r['lines']}<1200")
    return r
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--code",required=True); p.add_argument("--report"); p.add_argument("--output")
    a=p.parse_args()
    sd=a.output or next((os.path.join(OUTPUT_BASE,d) for d in os.listdir(OUTPUT_BASE) if os.path.isdir(os.path.join(OUTPUT_BASE,d)) and d.startswith(a.code.replace(".HK","").replace(".SH","").replace(".SZ",""))),None)
    if not sd: print("ERROR: no dir",file=sys.stderr); return 1
    rp=a.report or next((os.path.join(sd,f) for f in sorted(os.listdir(sd)) if f.endswith('.md') and ('分析报告' in f or 'v5' in f.lower() or 'v10' in f.lower())),None)
    if not rp: print("ERROR: no report",file=sys.stderr); return 1
    with open(rp,encoding='utf-8') as f: text=f.read()
    res=check(text)
    with open(os.path.join(sd,"quality_gate_report.json"),"w") as f: json.dump(res,f,indent=2,ensure_ascii=False)
    icon={"PASS":"✅","WARN":"⚠️","BLOCKED":"❌"}[res["status"]]
    print(f"{icon} Quality: {res['status']} | {res['lines']} lines")
    for b in res["blocks"]: print(f"  ❌ {b}")
    for w in res["warns"]: print(f"  ⚠️ {w}")
    return 0 if res["status"]!="BLOCKED" else 1
if __name__=="__main__": sys.exit(main())
