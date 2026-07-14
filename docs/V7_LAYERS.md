# V7 架构层次

> V7 = V5.2 三区模型 + 输入富化层 + 规则注入层

## 输入层

| 组件 | 内容 | 产出 |
|------|------|------|
| `stock_analysis.db` | 3,488 港股，2005-2025，408 万条财务数据 | — |
| 年报 PDF × 5 年 | 下载至 `output/{CODE}/` | — |

## Zone A — Python 确定性计算（禁止 LLM 参与）

| 脚本 | 产出 | 关键字段 |
|------|------|---------|
| `compute_bundle.py` | `compute_bundle.json` | 因子2(R_NP/R_OE)/因子3(AA/GG/λ)/因子4(DDM/仓位/否决门) + calculation_trace |
| `build_financial_trends.py` | `financial_trends.json` | IS/BS/CF 表(5年) + 比率 + 趋势信号 |
| `zone_d_industry_context.py` | `industry_context.json` | 行业分位排名 + 5 家可比同行 |
| `compute_bundle_precise.py` | `compute_bundle_precise.json` | 基于 Zone J 参数的精算版(覆盖 compute_bundle.json 默认值) |

## Zone B — LLM 结构化提取（PDF 年报 → JSON）

| 步骤 | 脚本 | 产出 |
|------|------|------|
| PDF 切片 | `pdf_preprocessor.py` | `pdf_sections_{year}.json` (10 章节: MDA/SEG/P2/P3/P4/P6/P13/STMT/DAN/SUB) |
| 全文本 | `build_full_text.py` | `pdf_full_text.json` (5 年 × 8 节定性内容, ~190K chars, 段落评分过滤) |
| 提取器 ×5 | `zone_b_extractor.py` | `mda.json` / `segments.json` / `risks.json` / `governance.json` / `audit.json` |

## Zone B+ — WebSearch 补充

| 脚本 | 产出 | 内容 |
|------|------|------|
| `zone_b_plus_websearch.py` | `web_research.json` | 同业数据(PE/PB/股息率) / 管理层变动 / 行业动态 |

## Zone J — LLM 参数估算（证据 → 参数，禁止叙事结论）

| Agent | 产出 | 关键参数 |
|-------|------|---------|
| J1 moat | `moat_assessment.json` | b_penalty_final, g_base, g_scenarios, moat_evidence, value_trap_signals |
| J2 capex | `capex_classification.json` | mcapex_split_pct, growth_classification(A/B/C), incremental_roic |
| J3 earnings_quality | `earnings_quality.json` | ar_quality, ap_excess_check, non_recurring_items, ocf_quality_flags |
| J4 data_quality | `data_discount.json` | discount_factors, total_discount_pct, confidence_by_section |

## Zone C — 6-Agent 报告链（`scripts/zone_c_chain.py`）

| Agent | 章节 | 目标行数 | 主要数据源 | 关键规则数 |
|-------|------|:---:|------|:---:|
| C1 | 报告头+因子1A+1B(10模块) | 800-1200 | compute_bundle+financial_trends+mda+segments+governance+audit+moat+industry | ~45 条 |
| C2 | 因子1C:增量增长检验 | 300-500 | financial_trends+capex_classification+industry | ~15 条 |
| C2b | 因子2:穿透回报率粗算 | 400-600 | compute_bundle+financial_trends+earnings_quality | ~10 条 |
| C3 | 因子3:步骤1-7(AA→GG) | 400-600 | compute_bundle+financial_trends+earnings_quality+moat | ~15 条 |
| C3b | 因子3:步骤8-13(净现金→置信度) | 300-500 | compute_bundle+mda+risks+data_discount | ~10 条 |
| C4 | 因子4+综合输出+ES回填 | 800-1000 | compute_bundle+financial_trends+moat+audit+risks | ~35 条 |

## Zone V — 验证层

| 脚本 | 功能 |
|------|------|
| `citation_verifier.py` | 报告数字 vs 9 个 JSON 源文件 偏差>1% → WARN |
| `boundary_validator.py` | Zone B/J/A JSON Schema 校验 |
| `quality_gate.py` | 报告章节完整性 + 行数 + 关键词 校验 |

## 规则层（嵌入 Zone C 各 Agent prompt）

规则来源：旧版 `prompts/references/`（~233 条）+ `shared_tables.md`。

| 优先级 | 数量 | 注入位置 | 主要内容 |
|--------|:--:|------|------|
| P0 | 7 条 | C3, C4 | λ敏感性/AA拆解/AA负值/GG置信区间/三视角裁决/资产安全垫/价值陷阱 |
| P1 | 12 条 | C4 | DPS基期检测/支付率上限/动量检验/可持续拆解/B类惩罚/行业衰减/PE回归/止损/适配声明/仓位映射/回调锚定/观察仓 |
| P2 | 8 条 | C1, C2 | 监管政策/关联交易/国企特别关注/三重锁定/授权方战略/增长归因/非经常性清洗/回购置信度 |
| 进阶 | 20 条 | C1, C2, C4 | SOTP/关联交易5项评分/租来护城河5项检查/品牌溢价II折扣/大股东现金折价校准/观察期毕业/护城河定量绑定/仓位×价值陷阱表/弱周期交叉验证/审计变更分级/分红一致性/增长归因完整公式/跨因子参数传播/A类标注/非经常排除阈值/回购因子2/4差异/资产质量4级阈值/估值方法选择决策树/跨市场参数对照/组合换算公式 |

**规则吸收率**: ~85%（~200 / ~233 条）
