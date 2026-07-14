#!/usr/bin/env python3
"""zone_c_chain.py — V10: Zone C Report Generation with Template-Based Pipeline.

V10 新增:
- --pipeline: 使用 write_pipeline.py 的分章节并行写作管线
- --template: 指定自定义模板文件
- --save-chapter-prompts: 按模板章节生成独立 prompt 文件
- --legacy: 强制使用 V9 单体 C_FULL 模式

V9 兼容:
- --agent / --save-prompts / --assemble 继续可用
"""
import argparse, json, os, re, sys
from datetime import datetime
from typing import Dict, List, Optional

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)
OUTPUT_DIR = os.path.join(ROOT, "output")
DB_PATH = os.path.join(ROOT, "stock_analysis.db")
VENV_PYTHON = os.path.join(ROOT, ".venv", "bin", "python3")
DEFAULT_TEMPLATE = os.path.join(ROOT, "templates", "report_template_v10.md")

_ZONE_J_FILES = {"moat_assessment.json", "capex_classification.json", "earnings_quality.json", "data_discount.json"}
_MOAT_EVIDENCE_FIELD_MAP = {"proof": "evidence", "strength": "durability", "source": "_source"}

def _normalize_moat_evidence(item: dict) -> dict:
    if not isinstance(item, dict): return item
    result = {}
    for k, v in item.items():
        canonical = _MOAT_EVIDENCE_FIELD_MAP.get(k, k)
        result[canonical] = v
    return result

_ZONE_J_STRIP_KEYS = {"moat_rating", "summary", "methodology_note"}

def _strip_zone_j_narrative(data: dict) -> dict:
    if not isinstance(data, dict): return data
    result = {}
    for k, v in data.items():
        if k in _ZONE_J_STRIP_KEYS: continue
        if isinstance(v, dict): result[k] = _strip_zone_j_narrative(v)
        elif isinstance(v, list):
            result[k] = [_normalize_moat_evidence(_strip_zone_j_narrative(i) if isinstance(i, dict) else i) for i in v]
        else: result[k] = v
    return result


AGENTS = {}

AGENTS["C1"] = {
    "name": "报告头部+因子1A+1B深度",
    "target_lines": "800-1200",
    "min_lines": 600,
    "context_budget_tokens": 8000,
    "allowed_inputs": ["compute_bundle.json", "compute_bundle_precise.json", "financial_trends.json", "mda.json", "segments.json", "governance.json", "audit.json", "moat_assessment.json", "industry_context.json", "pdf_full_text.json"],
    "task": "placeholder"
}

AGENTS["C_FULL"] = {
    "name": "综合报告(单Agent V9)",
    "target_lines": "3000-4000",
    "min_lines": 2000,
    "context_budget_tokens": 200000,
    "allowed_inputs": ["analysis_contract.json", "audit.json", "compute_bundle.json", "compute_bundle_precise.json", "financial_trends.json", "governance.json", "industry_context.json", "mda.json", "moat_assessment.json", "pdf_full_text.json", "segments.json"],
    "task": """你是数据填充器。把JSON数据填入以下预建表格模板。禁止压缩表格、禁止跳过章节、禁止写摘要。每个[?]替换为具体数值或⚠️。目标3000-4000行。

【输入数据】
{context}

# 龟龟投资策略 · 分析报告：[读取 meta.code]

## 报告元信息
| 项目 | 值 | 项目 | 值 |
|------|-----|------|-----|
| 分析日期 | [? meta.date] | 股票代码 | [? meta.code] |
| 公司 | [? 公司名] | 行业 | [? industry_context] |
| 股价 | [? market.price_hkd] HKD | 市值 | [? market.mc_hkd] M HKD |
| II | [? params.II]% | Rf | [? params.Rf]% | Q | [? params.Q×100]% |
| DPS | [? params.dps_latest] HKD | 版本 | V9 |

## Executive Summary
[C4_PLACEHOLDER]

## 模块〇：参数锚定

### A.市值(模块〇A项)
| 参数 | 符号 | 值 |
|------|:--:|:--:|
| 股价(HKD) | P | [? market.price_hkd] |
| 总股本(M) | S | [? market.shares_m] |
| MC(HKD M) | MC | [? market.mc_hkd] |
| MC(RMB M) | MC_RMB | [? market.mc_rmb] |

### B.盈利(模块〇B项)
| 参数 | 符号 | 值 |
|------|:--:|:--:|
| NP₃y | — | [? factor2.np_avg_3y] M |
| NP₅y | — | [? factor2.np_avg_5y] M |
| OE₃y | — | [? factor2.oe_avg_3y] M |
| OCF/NP | — | [? factor2.ocf_np_ratio] |
| M(G系数) | — | [? factor2.M]([? factor2.M_source], [? factor2.M_samples]样本) |

### C.现金(模块〇C项)
| 参数 | 符号 | 值 |
|------|:--:|:--:|
| 货币资金 | — | [? mda或financial_trends,否则⚠️] |
| 有息负债 | — | [? 同上,否则⚠️] |
| 净现金 | NCASH | [? =CASH-DEBT] |
| 净现金/MC | NCASH% | [?]% |

### D.分配(模块〇D项)
| 参数 | 符号 | 值 |
|------|:--:|:--:|
| DPS(HKD) | — | [? params.dps_latest] |
| 回购 | O | [? audit或governance,否则⚠️] |

### E.估值基准(模块〇E项)
| 参数 | 符号 | 值 |
|------|:--:|:--:|
| II | — | [? params.II]% |
| Q | — | [? params.Q×100]% |
| g_base | — | [? params.g_base]% |
| b_penalty | — | [? params.b_penalty×100]% |
| g_adj | — | [? =g_base×(1-b)]% |

### F.核心结果(模块〇F项)
| 参数 | 符号 | base值 | precise值 |
|------|:--:|:--:|:--:|
| GG基准 | — | [? factor3.gg.base]% | [? precise值]% |
| DDM公允价 | V | [? factor4.ddm_v_hkd] HKD | [? precise值] HKD |
| 否决门 | — | [? rejection_summary.overall] | — |

## 财务趋势速览

### 利润表趋势
| 指标(M RMB) | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|------|:--:|:--:|:--:|:--:|:--:|
| 营业收入 | [? income_trend[0].revenue] | [?] | [?] | [?] | [?] |
| 营收YoY | — | [?]% | [?]% | [?]% | [?]% |
| 毛利率 | [?]% | [?]% | [?]% | [?]% | [?]% |
| 归母NP | [?] | [?] | [?] | [?] | [?] |
| NP YoY | — | [?]% | [?]% | [?]% | [?]% |
| ROE | [?]% | [?]% | [?]% | [?]% | [?]% |
| EPS(RMB) | [?] | [?] | [?] | [?] | [?] |
| DPS(RMB) | [?] | [?] | [?] | [?] | [?] |

行业坐标:[营收=?M(中位?M,P?)|毛利率=?%(中位?%,P?)|ROE=?%(P?)|NP CAGR 3y=?%]
关键信号:[列出≤5条:🔴/🟡/✅ + 一句话]

### 现金流量表趋势
| 指标(M RMB) | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|------|:--:|:--:|:--:|:--:|:--:|
| OCF | [?] | [?] | [?] | [?] | [?] |
| Capex | [?] | [?] | [?] | [?] | [?] |
| FCF(=OCF-Capex) | [?] | [?] | [?] | [?] | [?] |
| OCF/NP | [?] | [?] | [?] | [?] | [?] |

### 毛利率分业务
| 业务 | FY2024毛利率 | FY2025毛利率 | 变动 |
|------|:--:|:--:|:--:|
| [? segments.segments[0].name] | [?]% | [?]% | [?]pp |
| (列出segments.json中所有业务) | | | |

## 一、因子1A：五分钟快筛
| 序号 | 检查项 | 结果 | 证据 |
|------|--------|:--:|------|
| 1 | 审计意见异常 | [? 是/否] | [audit] |
| 2 | 频繁更换审计师 | [? 是/否] | [audit] |
| 3 | 财务造假前科 | [? 是/否] | [governance] |
| 4 | 看不懂 | [? 是/否] | [segments] |
| 5 | 未经验证 | [? 是/否] | [trends] |
| 6 | 控股股东负面 | [? 是/否] | [governance] |

初步画像:
| 维度 | 判断 | 说明 |
|------|:--:|------|
| 资本消耗 | [? capital-light/capital-hungry] | Capex/营收=?% |
| 收款模式 | [? 先款后货/先货后款] | 收款比率=? |
| 周期性 | [? 强周期/弱周期/非周期] | CV=? |
| 护城河直觉 | [?] | |

## 二、因子1B：深度定性分析

### 模块〇：数据校验与口径锚定
**(1)异常扫描(FY2021-FY2025,上限3条)**
| 异常项 | 详情 | 原因 | 判断 |
|--------|------|------|:--:|
| [?] | [?] | [?] | [?] |

**(2)利润口径锚定**
选择 **[? GAAP归母/扣非]**——[?理由]

**(3)现金口径**
选择 **[? 狭义/广义]**——[?依据]

### 模块一：资本消耗强度
| 指标 | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|------|:--:|:--:|:--:|:--:|:--:|
| Capex(M) | [?] | [?] | [?] | [?] | [?] |
| Capex/营收 | [?]% | [?]% | [?]% | [?]% | [?]% |
| D&A(M) | [?] | [?] | [?] | [?] | [?] |
| Capex/D&A | [?]x | [?]x | [?]x | [?]x | [?]x |
判断:[? capital-light/capital-hungry/mixed],理由:[?]

### 模块二：收款模式
| 收款比率 | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|------|:--:|:--:|:--:|:--:|:--:|
| True/Reported | [?] | [?] | [?] | [?] | [?] |
判断:[? 先款后货/先服务后收费/垫资],理由:[?]

### 模块三：竞争格局与护城河
**3.1 市场结构**:[? 1-2句]

**3.2 非技术护城河**:
| 类型 | 存在 | 强度 | 证据 | 趋势 |
|------|:--:|:--:|------|:--:|
| 品牌/声誉 | [?] | [?] | [?] | [?] |
| 规模效应 | [?] | [?] | [?] | [?] |
| 切换成本 | [?] | [?] | [?] | [?] |
| 成本优势 | [?] | [?] | [?] | [?] |
| 监管/牌照 | [?] | [?] | [?] | [?] |

**3.3 技术护城河**:[?]

**3.5 定量绑定**:
| 指标 | 当前 | 趋势 |
|------|:--:|:--:|
| 第三方占比 | [?]% | [?] |
| 新签非住宅 | [?]% | [?] |

**3.5-bis 同业对标**:
| 公司 | 代码 | 营收(M) | 毛利率 | ROE | MC(M HKD) |
|------|------|:--:|:--:|:--:|:--:|
| **本公司** | — | [?] | [?]% | [?]% | [?] |
| [? 头部可比1] | [?] | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| [? 头部可比2] | [?] | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
⚠️ 行业头部数据需外部获取

**3.6 定价权**:[?]
**3.7 产业链议价**:上游[?]/劳动力[?]/下游B端[?]/C端[?]
**3.8 侵蚀风险**:[?]
**3.9「租来的护城河」**:[?]
**3.10 护城河vs价值陷阱**:[?]
**护城河评级:[? Strong/Moderate/Weak/None],置信度:[?]**

### 模块四：周期性
| 指标 | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 | CV |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 营收增速 | [?]% | [?]% | [?]% | [?]% | [?]% | [?] |
| NP增速 | [?]% | [?]% | [?]% | [?]% | [?]% | [?] |
判断:[? 强周期/弱周期/非周期],理由:[?]

### 模块五：人力与组织
判断:[? 系统型/人才型],理由:[?]

### 模块六：管理层与治理
控股:[?] | 关联方透明:[?] | 审计:[?]
评级:[? Excellent/Adequate/Concerning],理由:[? 3-5条]

### 模块七：MD&A可信度
| 管理层说法 | 实际数字 | 一致 |
|-----------|---------|:--:|
| [?] | [?] | [?] |
可信度:[? High/Medium/Low]

### 模块八：控股折价
类型:[? 央企/民企/外资] | 关联方占比:[?]%
判断:[?]

### 模块九：魔鬼代言人
逐条引用 value_trap_signals:
**⚠️信号1:[?]**
- 做空:[?]
- 反驳:[?]
- 判断:[? ✅/🟡WARN/🔴严重WARN]

**⚠️信号2:[?]**
- 做空:[?]
- 反驳:[?]
- 判断:[?]

**⚠️信号3:[?]**
- 做空:[?]
- 反驳:[?]
- 判断:[?]

综合:[? X/3信号无法完全反驳]

## 三、因子1C：增量增长检验

### 3.1 营收增长轨迹
Rev CAGR:3y=[?]%,5y=[?]%。
| FY | 营收(M) | YoY | 在管面积/关键KPI |
|----|:--:|:--:|:--:|
| FY2021 | [?] | [?]% | [?] |
| FY2022 | [?] | [?]% | [?] |
| FY2023 | [?] | [?]% | [?] |
| FY2024 | [?] | [?]% | [?] |
| FY2025 | [?] | [?]% | [?] |

### 3.2 利润增长vs营收增长
| 指标 | FY2022 | FY2023 | FY2024 | FY2025 |
|------|:--:|:--:|:--:|:--:|
| 营收增速 | [?]% | [?]% | [?]% | [?]% |
| NP增速 | [?]% | [?]% | [?]% | [?]% |
| 增速差 | [?]pp | [?]pp | [?]pp | [?]pp |

### 3.3 增量ROIC
| 时期 | ΔNP(M) | ΔRev(M) | 增量ROIC | 分类 |
|------|:--:|:--:|:--:|:--:|
| FY2019-2021 | [?] | [?] | [?]% | [?] |
| FY2023-2025 | [?] | [?] | [?]% | [?] |

### 3.4 增长类型分类
| 来源 | 类型 | 占比 | 判断 |
|------|:--:|:--:|------|
| [?] | A/B/C | [?]% | [?] |
增长质量:[?]

### 3.5 同业对标
⚠️ 需外部数据(Tushare/Wind)

## 四、因子2：穿透回报率粗算
⚠️ 数字来自 compute_bundle.json:factor2。

### 4.1 方法适用性
OCF/NP=[?]>0.8→[✅适用/⚠️边际/🔴不适用]

### 4.2 参数与OE
NP₃y=[?]M, OE₃y=[?]M, M=[?]([?]来源)

### 4.3 穿透回报率
```
R(NP)税前 = NP₃y / MC_RMB × 100 = [?] / [?] × 100 = [?]%
R(OE)税前 = OE₃y / MC_RMB × 100 = [?] / [?] × 100 = [?]%
```
| 指标 | 税前 | 税后(Q=[?]%) | vs II([?]%) |
|------|:--:|:--:|:--:|
| R(NP) | [?]% | [?]% | [?]x |
| R(OE) | [?]% | [?]% | [?]x |

### 4.4 Q税率敏感性
| Q | R(NP)税后 | vs II |
|:--:|:--:|:--:|
| 0% | [?]% | [?]x |
| 10% | [?]% | [?]x |
| 20% | [?]% | [?]x |

### 4.5 否决门
s2=[?], s4-1=[?], s4-2=[?]

## 五、因子3：穿透回报率精算
⚠️ 数字来自 compute_bundle.json:factor3。

### 5.1 AA序列
| FY | OCF(M) | Capex(M) | AA(M) | YoY |
|----|:--:|:--:|:--:|:--:|
| FY2021 | [?] | [?] | [?] | — |
| FY2022 | [?] | [?] | [?] | [?]% |
| FY2023 | [?] | [?] | [?] | [?]% |
| FY2024 | [?] | [?] | [?] | [?]% |
| FY2025 | [?] | [?] | [?] | [?]% |
AA₃y=[?]M, AA₅y=[?]M

### 5.2 收款比率
| FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|:--:|:--:|:--:|:--:|:--:|
| [?] | [?] | [?] | [?] | [?] |

### 5.3 AP超额融资
ap_finance=[?], 判断:[?]

### 5.4 B类惩罚
b_penalty=[?]%, g_adj=[?]%

### 5.5 GG三档
| 情景 | GG | vs II([?]%) |
|------|:--:|:--:|
| 悲观 | [?]% | [?] |
| **基准** | **[?]%** | **[?]** |
| 乐观 | [?]% | [?] |

### 5.6 Lambda
λ_neutral=[?]M, λ_conservative=[?]M

### 5.7 否决门
s11=[?], ap_finance=[?]

## 六、因子4：DDM三轨估值与仓位

### 6.1 合理PE
```
合理PE = min(1/II=[?]x, 行业中位数=[?]x, 历史中位数=[?]x) = [?]x
```
当前PE=[?]x, PE缺口=[?]%

### 6.2 DDM三轨
| 轨 | 构成 | 5年预期年化 | 10%达标价(HKD) | 置信度 |
|:--|:--|:--|:--|:--|
| A轨(保守) | 股息+g | [?]% | [?] | 高 |
| B轨(+PE修复) | 股息+g+PE回归 | [?]% | [?] | 中 |
| C轨(GG) | GG本身 | [?]% | — | 最高 |

### 6.3 GG-DDM分歧度
```
分歧度 = |B轨 - GG| = [?]%
[?]灯: 分歧[?]5pct, GG([?]%) [?] II → 仓位×[?]
```

### 6.4 结论(GG分档为主)
| GG分档 | 结论 |
|:--|:--|
| GG>II | **优先买入** |
| II×0.5~II | **观察/轻仓** |
| GG<II×0.5 | **否决** |
本标的:GG=[?]% vs II=[?]% → **[?]**

### 6.5 阶梯买入
| 阶梯 | A轨价格 | B轨价格 | 当前价状态 |
|:--|:--|:--|:--|
| 当前价([?]) | [?] | [?] | — |
| 积极(10%) | [?] | [?] | [?] |
| 中性(15%) | [?] | [?] | [?] |

### 6.6 仓位
基准=[?]%, 调整:[?], 最终=[?]%

### 6.7 综合输出
| 因子 | 评分 | 要点 |
|------|:--:|------|
| 1A | [?] | [?] |
| 1B | [?] | [?] |
| 1C | [?] | [?] |
| 2 | [?] | R(NP)=[?]% |
| 3 | [?] | GG=[?]% |
| 4 | [?] | DDM [?] vs [?] |

**综合结论:[? 通过/谨慎通过/不通过]**

### 6.8 风险矩阵
| 风险 | 概率 | 影响 | 应对 |
|------|:--:|:--:|------|
| [?] | [?] | [?] | [?] |

### 6.9 关键跟踪
| 指标 | 当前 | 预警线 | 退出线 |
|------|:--:|:--:|:--:|
| 毛利率 | [?]% | [?]% | [?]% |
| 营收增速 | [?]% | [?]% | [?]% |
| GG | [?]% | <II | <Rf |
| DPS | [?] | [?] | [?] |

### 6.10 Executive Summary(回填C1)
[ES_REPLACE]
[公司]([代码])。[一句话业务]。FY2025营收[rev]M(+[X]%),NP[np]M(+[X]%)。四因子:**[结论]**。DDM [V]HKD [>/<] [price]([±X]%)。[建议]。
[/ES_REPLACE]"""
}


def load_json(path):
    if not os.path.exists(path): return {"_missing": True}
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except: return {"_missing": True, "_error": "parse_failed"}

def load_chain_context(stock_dir):
    path = os.path.join(stock_dir, "chain_context.json")
    return load_json(path) if os.path.exists(path) else {}

def save_chain_context(stock_dir, ctx):
    os.makedirs(stock_dir, exist_ok=True)
    with open(os.path.join(stock_dir, "chain_context.json"), "w") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False, default=str)

def extract_chain_context_from_output(text):
    m = re.search(r'\[CHAIN_CONTEXT\]\s*(\{.*?\})\s*\[/CHAIN_CONTEXT\]', text, re.DOTALL)
    if not m:
        m = re.search(r'CHAIN_CONTEXT:\s*\n```json\n(.*?)\n```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: return {}
    return {}

def update_chain_context_from_outputs(stock_dir, parts):
    ctx = load_chain_context(stock_dir)
    for p in parts:
        extracted = extract_chain_context_from_output(p)
        if extracted:
            for k, v in extracted.items():
                if k not in ("agent", "ts_code", "generated_at"):
                    ctx[k] = v
    save_chain_context(stock_dir, ctx)
    if ctx:
        new_keys = [k for k in ctx if k != "_updated"]
        print(f"  🔗 chain_context updated: {new_keys}")
    return ctx

def build_agent_context(agent_id, stock_dir, ts_code):
    agent = AGENTS[agent_id]
    chain_ctx = load_chain_context(stock_dir)
    context = {"_meta": {"ts_code": ts_code, "agent": agent_id, "generated_at": datetime.now().isoformat()}, "_chain_context": chain_ctx}
    for fname in agent["allowed_inputs"]:
        key = fname.replace(".json", "")
        data = load_json(os.path.join(stock_dir, fname))
        if fname in _ZONE_J_FILES: data = _strip_zone_j_narrative(data)
        context[key] = data
    return context

def build_agent_prompt(agent_id, context):
    agent = AGENTS[agent_id]
    prompt = agent["task"].format(context=json.dumps(context, indent=2, ensure_ascii=False, default=str))
    contract = context.get("analysis_contract")
    if contract and contract.get("effective_years"):
        years = contract["effective_years"]
        defaults = [("FY2021 | FY2022 | FY2023 | FY2024 | FY2025", " | ".join(f"FY{y}" for y in years)), ("FY2021", f"FY{years[0]}"), ("FY2025", f"FY{years[-1]}")]
        for old, new in defaults: prompt = prompt.replace(old, new)
    return prompt

def assemble_report(stock_dir: str, ts_code: str) -> str:
    """Original V7-style assembly: concatenate agent outputs, replace ES placeholder."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
    name_cn = ts_code.replace(".HK","").replace(".SH","").replace(".SZ","")
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT name_cn FROM stocks WHERE ts_code=?",(ts_code,)).fetchone()
        conn.close()
        if row: name_cn = row[0]
    except: pass

    parts = []
    for aid in ["C1","C2","C2b","C3","C3b","C4"]:
        p = os.path.join(stock_dir, f"zone_c_{aid}_output.md")
        if os.path.exists(p):
            with open(p) as f: parts.append(f.read().strip())

    if not parts: return ""

    # Chain context update
    update_chain_context_from_outputs(stock_dir, parts)

    # V9.3: Prefer C_FULL single-agent output if it exists
    c_full = os.path.join(stock_dir, "zone_c_C_FULL_output.md")
    if os.path.exists(c_full):
        with open(c_full) as f: report = f.read().strip()
        print(f"  📄 使用 C_FULL 输出: {len(report):,} chars")
    else:
        report = "\n\n".join(parts)
    report = re.sub(r'\nCHAIN_NEXT:\\w+\\s*', '', report)

    # ES replacement: fill C4_PLACEHOLDER from C4 agent output
    if "C4_PLACEHOLDER" in report:
        c4_path = os.path.join(stock_dir, "zone_c_C4_output.md")
        if os.path.exists(c4_path):
            with open(c4_path) as f: c4 = f.read()
            m = re.search(r'\[ES_REPLACE\]\s*(.*?)\s*\[/ES_REPLACE\]', c4, re.DOTALL)
            if m:
                report = report.replace("【C4_PLACEHOLDER】", m.group(1).strip())
                print("  ✅ C4 ES 已回填")

    # V9.3: Template validation — check required sections (relaxed: partial match)
    required = [
        ("报告元信息", "报告元信息"),
        ("Executive Summary", "Executive Summary"),
        ("财务趋势", "财务趋势"),
        ("因子1B", "因子1B"),
        ("因子1C", "因子1C"),
        ("因子2", "因子2"),
        ("因子3", "因子3"),
        ("因子4", "因子4"),
    ]
    missing = [label for label, keyword in required if keyword not in report]
    if missing:
        print(f"  ⚠️ 缺失章节: {missing}")

    out_path = os.path.join(stock_dir, f"{name_cn}_{ts_code.replace('.','')}_分析报告_v7_final.md")
    with open(out_path, "w") as f: f.write(report)
    print(f"  ✅ 报告已组装 → {out_path}")
    print(f"  📊 {len(report.split(chr(10)))} 行 / {len(report.encode('utf-8'))/1024:.1f} KB")
    return out_path


def load_template(template_path: str = None) -> "TemplateLayout":
    """加载并解析报告模板。

    Args:
        template_path: 模板文件路径，默认为 templates/report_template_v10.md。

    Returns:
        解析后的 TemplateLayout 对象。

    Raises:
        FileNotFoundError: 模板文件不存在。
        ValueError: 模板解析失败。
    """
    from template_parser import parse_template

    path = template_path or os.environ.get("TURTLE_TEMPLATE", DEFAULT_TEMPLATE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"模板文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        md = f.read()

    return parse_template(md)


def build_chapter_prompt(
    chapter: "TemplateChapter",
    context: dict,
    stock_dir: str,
    company_name: str = "",
) -> str:
    """为单个章节构建 LLM prompt。

    将章节骨架中的 {placeholders} 替换为 context 中的实际值，
    并附加章节合约作为写作指令。

    Args:
        chapter: 模板章节对象。
        context: 已加载的数据上下文（JSON 数据字典）。
        stock_dir: 股票输出目录（用于日志）。
        company_name: 公司名称。

    Returns:
        完整的章节写作 prompt 字符串。
    """
    # 1. 用 context 数据填充骨架中的占位符
    skeleton = _fill_placeholders(chapter.skeleton, context, company_name)

    # 2. 构建写作指令
    instructions = _build_writing_instructions(chapter)

    # 3. 构建数据附录（仅包含本章需要的数据）
    data_appendix = _build_chapter_data_appendix(chapter, context)

    # 4. 组装完整 prompt
    parts = [instructions, "\n---\n\n## 章节模板\n", skeleton]

    if data_appendix:
        parts.extend(["\n---\n\n## 数据附录\n", data_appendix])

    return "\n".join(parts)


def _fill_placeholders(text: str, context: dict, company_name: str = "") -> str:
    """替换模板中的基础占位符。

    Args:
        text: 模板文本。
        context: 数据上下文。
        company_name: 公司名称。

    Returns:
        替换后的文本。
    """
    # 简单的 {key} 替换
    result = text

    # 公司名和代码
    meta = context.get("analysis_contract", {})
    result = result.replace("{company_name}", company_name or str(meta.get("company_name", "?")))
    result = result.replace("{ts_code}", str(context.get("_meta", {}).get("ts_code", "?")))
    result = result.replace("{analysis_date}", datetime.now().strftime("%Y-%m-%d"))
    result = result.replace("{currency}", "HKD" if ".HK" in str(context.get("_meta", {}).get("ts_code", "")) else "RMB")

    # 年份替换
    years = meta.get("effective_years", [2021, 2022, 2023, 2024, 2025])
    for i, year in enumerate(years[:5]):
        result = result.replace(f"{{fy_year_{i+1}}}", str(year))

    return result


def _build_writing_instructions(chapter: "TemplateChapter") -> str:
    """构建章节写作指令部分。

    Args:
        chapter: 模板章节对象。

    Returns:
        写作指令文本。
    """
    lines = [
        "# 写作指令",
        "",
        f"## 章节：{chapter.title}",
    ]

    if chapter.chapter_goal:
        lines.extend(["", "### 本章目标", chapter.chapter_goal])

    contract = chapter.chapter_contract
    if contract.narrative_mode:
        lines.extend(["", f"### 叙事模式：{contract.narrative_mode}"])

    if contract.must_answer:
        lines.extend(["", "### 必须回答的问题"])
        for i, q in enumerate(contract.must_answer, 1):
            lines.append(f"{i}. {q}")

    if contract.must_not_cover:
        lines.extend(["", "### 禁止涉及"])
        for item in contract.must_not_cover:
            lines.append(f"- {item}")

    if contract.required_output_items:
        lines.extend(["", "### 最低输出要求"])
        for item in contract.required_output_items:
            lines.append(f"- {item}")

    # 添加证据引用要求
    lines.extend([
        "",
        "### 证据引用规则",
        "- 每个数据断言必须附带证据来源锚点，格式：`[source: 文件名]`",
        '- 来源示例：`[source: compute_bundle.json]`、`[source: mda.json]`、`[source: moat_assessment.json]`',
        "- 缺失数据标注 `⚠️ 数据不可用`，禁止编造",
    ])

    return "\n".join(lines)


def _build_chapter_data_appendix(chapter: "TemplateChapter", context: dict) -> str:
    """为章节构建精选数据附录（仅包含本章需要的 JSON）。

    Args:
        chapter: 模板章节对象。
        context: 完整数据上下文。

    Returns:
        JSON 格式的数据附录文本。
    """
    # 基于章节标题判断需要哪些数据
    title = chapter.title
    needed_keys: set[str] = set()

    if "元信息" in title or "参数锚定" in title:
        needed_keys = {"compute_bundle", "analysis_contract", "financial_trends", "industry_context"}
    elif "Executive Summary" in title:
        needed_keys = set()  # 由其他章节摘要输入，不直接加载数据
    elif "财务趋势" in title:
        needed_keys = {"financial_trends", "segments", "compute_bundle", "industry_context"}
    elif "因子1" in title:
        needed_keys = {"audit", "governance", "mda", "segments", "moat_assessment", "industry_context", "financial_trends"}
    elif "因子2" in title or "因子3" in title or "穿透回报率" in title:
        needed_keys = {"compute_bundle", "compute_bundle_precise", "financial_trends", "moat_assessment", "capex_classification"}
    elif "因子4" in title or "DDM" in title or "估值" in title or "仓位" in title:
        needed_keys = {"compute_bundle", "compute_bundle_precise", "industry_context", "data_discount"}
    elif "风险" in title:
        needed_keys = {"audit", "governance", "mda", "risks", "moat_assessment"}
    elif "决策" in title or "投资决策" in title:
        needed_keys = set()  # 使用章节摘要而非原始数据
    elif "来源" in title:
        needed_keys = set()  # 自动生成，无需 LLM

    if not needed_keys:
        return ""

    lines = ["以下为本章分析所需的结构化数据（JSON 格式）：", ""]
    for key in sorted(needed_keys):
        if key in context and not (isinstance(context[key], dict) and context[key].get("_missing")):
            data = context[key]
            # 对 Zone J 文件做叙事剥离
            if key in _ZONE_J_FILES or key in {k.replace(".json", "") for k in _ZONE_J_FILES}:
                data = _strip_zone_j_narrative(data)
            lines.append(f"### {key}.json")
            lines.append("```json")
            lines.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="zone_c_chain.py — V10 Template-Based Report Generation")
    p.add_argument("--code", required=True, help="Stock code")
    p.add_argument("--output", help="Output directory")
    p.add_argument("--agent", help="Generate prompt for specific agent (V9 legacy)")
    p.add_argument("--save-prompts", action="store_true", help="Save all prompts (V9 legacy)")
    p.add_argument("--save-chapter-prompts", action="store_true", help="Save per-chapter prompts using V10 template")
    p.add_argument("--assemble", action="store_true", help="Assemble final report from outputs")
    p.add_argument("--pipeline", action="store_true", help="Use V10 write_pipeline (delegates to write_pipeline.py)")
    p.add_argument("--legacy", action="store_true", help="Force V9 legacy C_FULL single-agent mode")
    p.add_argument("--template", help="Custom template path (default: templates/report_template_v10.md)")
    args = p.parse_args()
    
    stock_dir = args.output
    if not stock_dir:
        code_base = args.code.replace(".HK","").replace(".SH","").replace(".SZ","")
        for name in os.listdir(OUTPUT_DIR):
            if name.startswith(code_base) and os.path.isdir(os.path.join(OUTPUT_DIR, name)):
                stock_dir = os.path.join(OUTPUT_DIR, name)
                break
        if not stock_dir:
            print(f"ERROR: No output dir for {args.code}", file=sys.stderr)
            return 1

    if args.pipeline:
        # V10: 委托给 write_pipeline.py
        pipeline_script = os.path.join(SCRIPTS_DIR, "write_pipeline.py")
        if not os.path.exists(pipeline_script):
            print(f"ERROR: write_pipeline.py not found. Run Phase 2 first.", file=sys.stderr)
            return 1
        cmd = [VENV_PYTHON, pipeline_script, "--code", args.code]
        if args.output: cmd.extend(["--output", args.output])
        if args.template: cmd.extend(["--template", args.template])
        import subprocess
        return subprocess.call(cmd)

    if args.assemble:
        assemble_report(stock_dir, args.code)
        return 0

    if args.save_chapter_prompts:
        # V10: 按模板章节生成独立 prompt
        try:
            layout = load_template(args.template)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        # 加载全量上下文
        ctx = build_agent_context("C_FULL", stock_dir, args.code)
        company_name = _get_company_name(args.code)

        for ch in layout.chapters:
            prompt = build_chapter_prompt(ch, ctx, stock_dir, company_name)
            safe_title = re.sub(r'[^\w]', '_', ch.title)[:40]
            out = os.path.join(stock_dir, f"zone_c_ch{ch.index:02d}_{safe_title}_prompt.txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"✅ Ch{ch.index:02d} {ch.title} → {out}")
            print(f"   Prompt: {len(prompt):,} chars")
        return 0

    if args.agent:
        agent = AGENTS.get(args.agent)
        if not agent:
            print(f"ERROR: Unknown agent {args.agent}", file=sys.stderr)
            return 1
        ctx = build_agent_context(args.agent, stock_dir, args.code)
        prompt = build_agent_prompt(args.agent, ctx)
        out = os.path.join(stock_dir, f"zone_c_{args.agent}_prompt.txt")
        with open(out, "w") as f: f.write(prompt)
        missing = [k for k,v in ctx.items() if isinstance(v,dict) and v.get("_missing")]
        print(f"✅ {args.agent} ({agent['name']}) → {out}")
        print(f"   Context: {len(json.dumps(ctx)):,} chars, Target: {agent['target_lines']} lines")
        if missing: print(f"   Missing: {missing}")
        return 0

    if args.save_prompts:
        for aid in ["C1","C2","C2b","C3","C3b","C4"]:
            ctx = build_agent_context(aid, stock_dir, args.code)
            prompt = build_agent_prompt(aid, ctx)
            out = os.path.join(stock_dir, f"zone_c_{aid}_prompt.txt")
            with open(out, "w") as f: f.write(prompt)
            print(f"✅ {aid} ({AGENTS[aid]['name']}) → {out}")
            print(f"   Context: {len(json.dumps(ctx)):,} chars, Target: {AGENTS[aid]['target_lines']} lines")
            missing = [k for k,v in ctx.items() if isinstance(v,dict) and v.get("_missing")]
            if missing: print(f"   Missing: {missing}")
        return 0

    print("V10 Usage:")
    print("  --pipeline              Use V10 chapter-parallel writing pipeline")
    print("  --save-chapter-prompts  Generate per-chapter prompts from template")
    print("  --assemble              Assemble final report from outputs")
    print("V9 Legacy:")
    print("  --agent C_FULL          Generate C_FULL prompt (legacy single-agent)")
    print("  --save-prompts          Save all 6-agent prompts (legacy)")
    print("  --legacy                Force V9 C_FULL mode")
    return 0


def _get_company_name(ts_code: str) -> str:
    """从数据库获取公司中文名称。

    Args:
        ts_code: 股票代码。

    Returns:
        公司中文名称，若找不到则返回代码本身。
    """
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT name_cn FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")

if __name__ == "__main__":
    sys.exit(main())
