#!/usr/bin/env python3
"""zone_b_plus_websearch.py — Zone B+ Web Research prompt generator.

Generates a structured LLM prompt for web research on a stock. The LLM
executes WebSearch/WebFetch calls and saves results as web_research.json.
This feeds into Zone C agents to eliminate "⚠️ 同业数据需外部获取" gaps.

Usage:
    python3 scripts/zone_b_plus_websearch.py --code 02669.HK --save-prompt
    # Then: LLM processes the prompt → saves web_research.json
    python3 scripts/zone_b_plus_websearch.py --code 02669.HK --validate
"""

import argparse, json, os, sys
from datetime import datetime

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")

WEB_RESEARCH_PROMPT = """你是龟龟投资策略框架的 Web Research Agent（Zone B+）。
你的任务：使用 WebSearch 和 WebFetch 工具，搜索以下信息并保存为结构化 JSON。

【目标公司】{company_name}（{ts_code}）
【行业】{industry}
【搜索日期】{today}

【搜索任务——按优先级执行】

## 1. 同业对标数据（最高优先级）
搜索 4 家与 {company_name} 最可比的公司，获取最新财务指标：
- 公司名称 + 股票代码
- 市值（HKD/RMB）
- PE(TTM)、PB
- 股息率
- 营收（最近财年）
- 毛利率、ROE
- 来源：雪球、同花顺、东方财富、Google Finance、Yahoo Finance

## 2. 管理层与治理
- 董事长/CEO 姓名、任期、背景
- 近期管理层变动
- 股权激励计划
- 控股股东及持股比例

## 3. 行业动态
- 行业最新政策/监管变化
- 竞争格局变化（新进入者、市场份额变动）
- 行业增长趋势

## 4. 风险事件
- 近期负面新闻（诉讼、处罚、评级下调）
- 审计师变更
- 大股东增减持

【输出格式——严格按此 JSON schema 输出，每条数据必须带 source_url】

```json
{{
  "peer_comparison": [
    {{
      "name": "公司名",
      "ts_code": "代码.HK/SH/SZ",
      "market_cap": {{"value": 数字, "unit": "亿HKD", "source_url": "..."}},
      "pe_ttm": {{"value": 数字, "source_url": "..."}},
      "pb": {{"value": 数字, "source_url": "..."}},
      "dividend_yield": {{"value": 数字, "unit": "%", "source_url": "..."}},
      "revenue": {{"value": 数字, "unit": "亿RMB", "source_url": "..."}},
      "gross_margin": {{"value": 数字, "unit": "%", "source_url": "..."}},
      "roe": {{"value": 数字, "unit": "%", "source_url": "..."}},
      "rationale": "为什么这家公司可比"
    }}
  ],
  "management": {{
    "ceo_name": "...",
    "ceo_tenure": "...",
    "recent_changes": "...",
    "equity_incentive": "...",
    "controlling_shareholder": "...",
    "source_urls": ["..."]
  }},
  "industry_dynamics": {{
    "key_trends": ["趋势1", "趋势2"],
    "policy_changes": ["政策1"],
    "competitive_landscape": "...",
    "source_urls": ["..."]
  }},
  "risk_events": [
    {{
      "event": "事件描述",
      "date": "YYYY-MM-DD",
      "severity": "high/medium/low",
      "source_url": "..."
    }}
  ],
  "_provenance": {{
    "search_date": "{today}",
    "ts_code": "{ts_code}",
    "cache_ttl_days": 30
  }}
}}
```

【规则】
1. 每条数字必须带 source_url（你从哪个网页获取的）
2. 搜索不到的数据填 null，不要编造
3. 只输出 JSON，不要任何解释文字
4. 如果搜索被限制（如某些网站反爬），标注 "⚠️ 搜索受限"
"""


def generate_prompt(ts_code: str, stock_dir: str) -> tuple:
    """Generate web research prompt. Returns (prompt_text, output_path)."""
    # Get company name and industry from DB
    company_name = ts_code
    industry = "未知"
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT name_cn, industry FROM stocks WHERE ts_code=?",
            (ts_code,)
        ).fetchone()
        if row:
            company_name = row["name_cn"] or ts_code
            industry = row["industry"] or "未知"
        # Also try industry_context
        ctx_path = os.path.join(stock_dir, "industry_context.json")
        if os.path.exists(ctx_path):
            with open(ctx_path) as f:
                ctx = json.load(f)
            l1 = ctx.get("meta", {}).get("industry_l1", "")
            l2 = ctx.get("meta", {}).get("industry_l2", "")
            if l1:
                industry = f"{l1}/{l2}" if l2 else l1
        conn.close()
    except Exception:
        pass

    prompt = WEB_RESEARCH_PROMPT.format(
        company_name=company_name,
        ts_code=ts_code,
        industry=industry,
        today=datetime.now().strftime("%Y-%m-%d"),
    )

    out_path = os.path.join(stock_dir, "zone_b_plus_websearch_prompt.txt")
    return prompt, out_path


def validate_result(stock_dir: str) -> dict:
    """Validate web_research.json has required fields."""
    path = os.path.join(stock_dir, "web_research.json")
    if not os.path.exists(path):
        return {"status": "MISSING", "message": "web_research.json not found — run web search first"}

    with open(path) as f:
        data = json.load(f)

    issues = []
    peers = data.get("peer_comparison", [])
    if len(peers) < 3:
        issues.append(f"Only {len(peers)} peers (need ≥3)")
    for i, p in enumerate(peers):
        if not p.get("source_url") and not any(v.get("source_url") for v in p.values() if isinstance(v, dict)):
            issues.append(f"Peer {i+1} ({p.get('name','?')}): missing source_urls")

    mgmt = data.get("management", {})
    if not mgmt.get("source_urls"):
        issues.append("Management section missing source_urls")

    return {
        "status": "PASS" if not issues else "WARN",
        "issues": issues,
        "peer_count": len(peers),
        "has_management": bool(mgmt.get("ceo_name")),
        "has_industry": bool(data.get("industry_dynamics", {}).get("key_trends")),
        "has_risks": len(data.get("risk_events", [])) > 0,
    }


def main():
    p = argparse.ArgumentParser(description="zone_b_plus_websearch.py — Zone B+ Web Research")
    p.add_argument("--code", type=str, required=True, help="Stock code (e.g. 02669.HK)")
    p.add_argument("--save-prompt", action="store_true", help="Save LLM prompt for web research")
    p.add_argument("--validate", action="store_true", help="Validate existing web_research.json")
    args = p.parse_args()

    ts_code = args.code
    code_prefix = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    stock_dir = None
    for d in os.listdir(OUTPUT_BASE):
        if d.startswith(code_prefix):
            stock_dir = os.path.join(OUTPUT_BASE, d)
            break

    if not stock_dir:
        print(f"ERROR: No output directory found for {ts_code}", file=sys.stderr)
        return 1

    if args.validate:
        result = validate_result(stock_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["status"] == "PASS" else 1

    if args.save_prompt:
        prompt, out_path = generate_prompt(ts_code, stock_dir)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"✅ WebSearch prompt → {out_path}")
        print(f"   Context: {len(prompt):,} chars")
        print(f"   Next: LLM reads prompt, executes WebSearch, saves to web_research.json")
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
