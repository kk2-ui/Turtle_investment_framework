# 报告生成架构设计：从 V4 到 V5

> 目标：解决 V4 报告“可复现但信息密度低”、V3 报告“信息丰富但证据链弱”的结构性矛盾。

---

## 1. 背景

本次对比对象：

- V3 报告：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/01502_金融街物业/金融街物业_01502_分析报告_v3.md`
- V4 报告：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/01502_金融街物业/金融街物业_01502_分析报告_v4.md`
- 定量 bundle：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/01502_金融街物业/compute_bundle.json`
- 结构化财务输入：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/01502_金融街物业/input_data.json`
- 市场数据包：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/01502_金融街物业/data_pack_market.md`
- PDF sections：
  - `pdf_sections_2024.json`
  - `pdf_sections_2025.json`

核心问题：

- V4 主要依赖 `stock_analysis.db + compute_bundle.py`，所以计算可复现、口径一致，但报告信息密度明显不足。
- V3 大量利用年报 PDF 信息，运营、治理、审计、MDA、股价位置等内容更丰富，但证据链、结构化程度、复现性较弱。

结论：**问题不是“V4 没读 PDF”这么简单，而是当前系统把“确定性计算”和“年报叙事/运营事实”割裂了。**

正确方向不是让 LLM 在写报告时重新读 PDF，而是把 PDF 中有价值的信息结构化为可追溯、可校验的 `report_context` / evidence layer，再让报告生成器读取它。

---

## 2. V3 与 V4 的本质差异

### 2.1 V4 的优势

V4 最大优点是：

1. **定量指标统一来自 `compute_bundle.py`**
   - 因子 2/3/4 的 GG、DDM、仓位、否决门一致。
   - 不容易出现“报告正文算一个数、表格又是另一个数”的问题。

2. **计算路径可复现**

   ```text
   stock_analysis.db → compute_bundle.py → 报告
   ```

3. **篇幅短，决策信息集中**
   - V4 约 344 行；V3 约 1453 行。
   - V4 更容易扫读。

但 V4 的缺陷也很明显：**它丢掉了年报里的经营事实。**

---

### 2.2 V3 的优势

V3 信息密度明显高很多，尤其包括：

| 信息类型 | V3 有 | V4 基本没有 |
|---|---:|---:|
| 控股股东、最终实控人 | ✅ | 弱 |
| 审计师、审计意见 | ✅ | ❌ |
| 52 周、10 年股价位置 | ✅ | 弱 |
| PE / PB 估值锚 | ✅ | ❌ |
| 在管面积、合同面积、项目数 | ✅ | ❌ |
| 第三方面积占比 | ✅ | ❌ |
| 物业类型结构 | ✅ | ❌ |
| 收入结构、毛利率分业务 | ✅ | ❌ |
| 商誉减值说明 | ✅ | 弱 |
| 应收账款账龄 | ✅ | ❌ |
| MDA 管理层叙述 | ✅ | ❌ |
| 董监高履历、治理变化 | ✅ | ❌ |
| 重大收购、所得款用途 | ✅ | ❌ |

这些信息对物管公司非常重要。比如金融街物业，投资判断不能只看 GG/DDM，还要看：

- 在管面积是不是继续增长；
- 第三方拓展能力是否增强；
- 商务物业 vs 住宅/公建结构是否恶化；
- 毛利率下滑是不是结构性；
- 应收账款是不是恶化；
- 商誉减值是不是并购失败信号；
- 控股股东依赖是否下降；
- 审计意见是否稳定。

这些都不是 `compute_bundle.py` 擅长的内容。

---

## 3. 根本问题：目前只有“财务事实库”，没有“报告事实库”

v3.0 架构解决了一个核心问题：

> 定量计算不要交给 LLM，交给 Python。

这是正确的。

但报告写作需要两类输入：

```text
A. 定量计算事实：GG、DDM、AA、λ、仓位、否决门
B. 年报上下文事实：运营、治理、股权、审计、MDA、行业、风险、市场位置
```

现在 V4 只有 A，没有 B。

所以 V4 变成了：

```text
compute_bundle.json → LLM 写报告
```

而 V3 更接近：

```text
PDF sections + 人工/LLM 阅读 → 长报告
```

问题是：

- V3 虽然丰富，但缺乏稳定的结构化证据链；
- V4 虽然稳定，但信息太瘦。

正确目标应该是：

```text
stock_analysis.db
  + compute_bundle.json
  + report_context.json / report_facts tables
  + evidence store
  → LLM 写报告
```

---

## 4. 关键发现：PDF sections 已经有大量信息，但不能直接信任

以 `pdf_sections_2025.json` 为例，里面确实有非常丰富的信息。

### 4.1 运营数据

2025 年 MDA 中有：

- 在管面积 50.62 百万平方米；
- 项目数 396 个；
- 合同面积 51.998 百万平方米；
- 第三方在管面积 29.82 百万平方米；
- 第三方占比 58.91%；
- 金融街关联方开发物业面积 20.80 百万平方米；
- 非住宅业态占比 56.96%。

这些都是 V4 应该使用的。

---

### 4.2 毛利率分业务

2025 年 MDA 有：

| 业务 | 2025 毛利率 | 2024 毛利率 |
|---|---:|---:|
| 物管及相关服务 | 14.75% | 15.28% |
| 商务物业 | 22.60% | 20.51% |
| 非商务物业 | 8.08% | 9.57% |
| 多元经营 | -0.08% | -5.05% |
| 总计 | 14.19% | 14.42% |

这比 V4 里简单说“毛利率下滑”有用得多。

---

### 4.3 商誉减值

2025 年 P3 里有：

- 商誉从 93.618M 降至 74.790M；
- 置佳物业服务确认减值 18.828M；
- 原因是相关业务收入增长不及预期；
- 可收回金额、贴现率、五年收入增长率都有披露。

这是判断并购质量的重要证据。

---

### 4.4 应收账款账龄

2025 年 P3 里有：

- 应收账款总额 395.502M；
- 减值准备 46.206M；
- 净额 349.296M；
- 一年内 297.166M；
- 一至两年 41.733M；
- 两至三年 24.172M；
- 三年以上 32.431M。

这可以支持“回款风险是否恶化”的判断。

---

### 4.5 但 PDF sections 不能直接信任

`pdf_sections_2025.json["financials"]` 中存在明显错位：

```json
"营业收入": 2392.57,
"归母净利润": 1344.07,
"少数股东权益": 1344.07
```

这明显不对：

- 2392.57 实际是资产总计；
- 1344.07 实际是归母权益；
- 归母净利润正确值应该是 107.35M。

这说明“候选层 + evidence + gate”非常必要。

**PDF sections 可以用，但必须分层：STMT 财务数值要严校验；MDA/运营事实也要结构化和溯源。**

---

## 5. 目标架构：从 compute-first 升级为 compute + context 双引擎

### 5.1 当前 V4

```text
stock_analysis.db
  → compute_bundle.py
  → compute_bundle.json
  → LLM 写报告
```

### 5.2 目标 V5

```text
stock_analysis.db
  → compute_bundle.py
  → compute_bundle.json
        │
PDF sections / data_pack_market / 年报文本
  → context_extract.py
  → report_context.json / report_facts tables
        │
quality_gate / evidence_gate
        │
report_input_bundle.json
        │
LLM 写报告
```

核心是新增一个中间产物：

```text
report_input_bundle.json
```

它由两部分组成：

```json
{
  "quantitative": {
    "source": "compute_bundle.json",
    "data": {}
  },
  "context": {
    "source": "report_context.json",
    "data": {}
  },
  "evidence": {
    "coverage": {},
    "warnings": [],
    "blocked_fields": []
  }
}
```

LLM 不再自己到处读 PDF，而是只读这个 bundle。

---

## 6. 数据库/证据层新增设计

当前已有财务候选层设计：

- `financial_observations`
- `field_evidence`
- `quality_findings`
- `curation_decisions`

这个方向对财务字段是对的。

但 V3 缺失的信息很多不是传统三表字段，所以还需要一个更泛化的事实层。

---

## 6.1 fact_observations：非财务事实候选表

用于存运营、治理、审计、市场、MDA 等事实。

```sql
fact_observations
- fact_id
- ts_code
- fiscal_year
- domain
  -- operations / governance / audit / market / mda / segment / risk / capital_allocation
- fact_name
  -- managed_area_m_sqm / third_party_area_pct / auditor / audit_opinion / brand_value_rmb_bn
- raw_value
- normalized_value
- unit
- value_type
  -- number / percent / text / enum / date / json
- source_type
  -- pdf_section / data_pack_market / yfinance / manual_fix / web
- source_path
- confidence
- status
  -- candidate / accepted / rejected / needs_review
```

这样可以把 V3 的“运营信息”结构化。

---

## 6.2 fact_evidence：非财务事实证据表

```sql
fact_evidence
- evidence_id
- fact_id
- document_path
- pdf_file
- page_no
- section_key
  -- MDA / P3 / STMT / DAN / SEG / data_pack_market §11
- raw_text
- table_name
- row_label
- column_label
- extraction_method
- confidence
```

示例：

```json
{
  "fact_name": "managed_area_m_sqm",
  "normalized_value": 50.62,
  "unit": "million_sqm",
  "evidence": {
    "pdf": "01502_2025_年报.pdf",
    "page": 13,
    "raw_text": "总在管建筑面积为50.62百万平方米..."
  }
}
```

这样 V4 可以引用运营数据，但不会变成“LLM 随口说”。

---

## 6.3 report_context_snapshots：报告上下文快照

每次生成报告前生成一个 context snapshot。

```sql
report_context_snapshots
- snapshot_id
- ts_code
- generated_at
- source_years_json
- context_json
- evidence_coverage_json
- warnings_json
- blocked_facts_json
```

它对应一个可落地文件：

```text
output/01502_金融街物业/report_context.json
```

---

## 7. report_context.json 结构建议

以金融街物业为例，`report_context.json` 应包括：

```json
{
  "meta": {
    "ts_code": "01502.HK",
    "company": "金融街物业",
    "years": [2021, 2022, 2023, 2024, 2025],
    "context_version": "v1"
  },
  "company_profile": {
    "controlling_shareholder": {},
    "ultimate_controller": {},
    "listing_date": {},
    "auditor": {},
    "audit_opinion": {}
  },
  "market_position": {
    "price_latest": {},
    "week_52_high_low": {},
    "ten_year_high_low": {},
    "price_percentile": {},
    "pe_ttm": {},
    "pb": {}
  },
  "operations": {
    "managed_area": {},
    "contracted_area": {},
    "project_count": {},
    "third_party_area": {},
    "third_party_area_pct": {},
    "related_party_area": {},
    "property_type_mix": {},
    "geographic_mix": {}
  },
  "business_segments": {
    "revenue_by_segment": {},
    "gross_margin_by_segment": {},
    "business_model": {}
  },
  "governance": {
    "board_changes": [],
    "management_bios": [],
    "related_party_transactions": [],
    "connected_transactions": []
  },
  "risk_events": {
    "goodwill_impairment": [],
    "receivable_aging": [],
    "pledges": [],
    "contingent_liabilities": [],
    "post_balance_sheet_events": []
  },
  "mda_summary": {
    "growth_drivers": [],
    "cost_pressure": [],
    "management_outlook": [],
    "technology_green_operations": [],
    "brand_awards": []
  }
}
```

每个字段都带证据：

```json
"managed_area": {
  "FY2025": {
    "value": 50.62,
    "unit": "million_sqm",
    "source": "pdf_sections_2025.json:MDA",
    "page": 13,
    "confidence": 0.95,
    "quote": "总在管建筑面积为50.62百万平方米..."
  }
}
```

---

## 8. 报告生成输入设计

未来报告生成器应该明确读取三个输入：

```text
1. compute_bundle.json
   - 只负责定量计算
   - GG / DDM / AA / λ / 仓位 / 否决门

2. report_context.json
   - 只负责年报事实
   - 运营 / 股权 / 审计 / MDA / 风险 / 股价位置

3. qualitative_assessment.json
   - 只负责定性判断
   - 护城河 / 管理层 / 周期 / 竞争格局 / 会计质量
```

也就是说：

```text
LLM = writer + judge
Python = calculator + extractor + gatekeeper
DB = facts + evidence + contract
```

这比“让 LLM 重新读 PDF 写长文”稳定得多。

---

## 9. V4 应如何恢复 V3 的信息密度

不是简单把 V3 复制进去，而是给每个报告章节分配来源。

### 9.1 报告元信息

来源：

- `stocks`
- `data_pack_market.md §1/§2/§11`
- `fact_observations.audit`
- `fact_observations.governance`

应恢复：

- 控股股东；
- 最终控制人；
- 审计师；
- 审计意见；
- 52 周最高/最低；
- 10 年最高/最低；
- PE/PB；
- 股价历史分位。

---

### 9.2 财务趋势速览

来源：

- `annual_financials`
- `input_data.json`
- `compute_bundle.json`

保留 V4 的可复现性。

但增加：

- 毛利率分业务；
- 应收账款账龄；
- 商誉减值；
- 受限现金；
- 关联方应收/收入占比。

这些来自 `report_context.json`。

---

### 9.3 因子 1B

这是 V4 最弱的地方。

应该由 `qualitative_assessment.json` + `report_context.json` 支持。

至少包含：

- 商业模式；
- 资本消耗强度；
- 收款模式；
- 护城河来源；
- 第三方拓展能力；
- 毛利率压力；
- 管理层与治理；
- 关联交易风险；
- 会计质量；
- 价值陷阱定性检查。

---

### 9.4 风险提示

V4 的风险提示偏泛。

应该由结构化 facts 生成：

- 毛利率连续下行；
- 非商务物业占比提高；
- 第三方拓展虽然增强但毛利较低；
- 商誉减值扩大；
- 贸易应收账款账龄拉长；
- 母公司/关联方收入占比；
- 所得款用途和未用资金；
- 审计师变化或无变化；
- 董事会变化。

---

## 10. 事实分层原则

所有报告信息分成三层。

---

### 10.1 Layer 1：硬财务事实

这些进入 `annual_financials` / `compute_bundle`。

例如：

- revenue
- n_income_attr_p
- OCF
- Capex
- total_assets
- total_liab
- equity
- DPS
- shares_m

特点：

- 数字严校验；
- 影响 GG/DDM/仓位；
- 错了会直接导致买入建议错误；
- 必须 BLOCK gate。

---

### 10.2 Layer 2：运营/治理事实

这些进入 `fact_observations` / `report_context`。

例如：

- 在管面积；
- 合同面积；
- 项目数；
- 第三方面积占比；
- 品牌价值；
- 审计师；
- 审计意见；
- 控股股东；
- 董事变动；
- 商誉减值原因；
- 应收账款账龄；
- 关联方收入占比。

特点：

- 不直接进入 GG/DDM；
- 但强烈影响定性判断；
- 错了会影响风险判断；
- 应该 WARN / needs_review，而不是随便丢弃。

---

### 10.3 Layer 3：MDA 叙事与判断

这些进入 `mda_claims` 或 `qualitative_assessment`。

例如：

- 管理层说市场化拓展增强；
- 管理层说毛利率企稳；
- 管理层说行业竞争加剧；
- 管理层说绿色运营、数字化转型；
- 管理层说未来聚焦一二线城市。

特点：

- 不能当作事实直接相信；
- 需要和数字交叉验证；
- LLM 可以做判断，但必须引用原文和反证数据。

---

## 11. 落地路线

### Phase 1：先生成 report_context.json，不急着入 DB

先做文件级中间产物。

新增脚本：

```text
scripts/build_report_context.py
```

输入：

```text
output/{code}_{company}/
  ├── pdf_sections_*.json
  ├── data_pack_market.md
  ├── input_data.json
  ├── compute_bundle.json
```

输出：

```text
output/{code}_{company}/report_context.json
```

先覆盖这些模块：

1. company_profile
2. market_position
3. operations
4. business_segments
5. audit
6. risk_events
7. mda_summary

这样马上可以让 V4 丰富起来。

---

### Phase 2：把 report_context 接入报告生成 prompt

报告生成时明确要求：

```text
- 因子2/3/4 所有数值只能引用 compute_bundle
- 财务趋势只能引用 annual_financials/input_data
- 运营事实只能引用 report_context
- 定性判断必须引用 report_context.evidence
- 如果 report_context 缺失，不得编造
```

然后 V4 就会变成：

```text
V4.1 = compute_bundle 精算 + report_context 信息密度
```

---

### Phase 3：把 report_context 重要字段入库

等文件级跑通后，再把它拆进 DB：

- `fact_observations`
- `fact_evidence`
- `report_context_snapshots`

这样不会一开始就把 DB schema 搞复杂。

---

### Phase 4：建立 context gate

对非财务事实做门禁。

#### BLOCK

- 控股股东/股本/审计意见与硬事实冲突；
- 运营指标年度错位；
- 单位错位 1000 倍；
- 同一字段跨年不合理跳变且无解释。

#### WARN

- 缺少审计师；
- 缺少在管面积；
- 缺少业务结构；
- MDA 有表述但无数字支撑；
- 管理层说“质量提升”，但毛利率继续下滑。

---

## 12. 金融街物业案例：V4 应补充的结构化 facts

### 12.1 市场位置

来自 `data_pack_market.md`：

- 最新价 1.96 HKD；
- 52 周高低 2.55 / 1.94；
- 10 年最高 14.32；
- 10 年最低 1.94；
- 股价历史分位 1.0%。

这些应该进入 `market_position`。

---

### 12.2 运营规模

来自 `pdf_sections_2025.json:MDA`：

- 在管面积 50.62 百万平方米；
- 合同面积 51.998 百万平方米；
- 项目数 396；
- 覆盖 25 个省市自治区及特别行政区；
- 非住宅业态占比 56.96%。

---

### 12.3 第三方拓展

来自 `pdf_sections_2025.json:MDA`：

- 金融街关联方开发物业面积 20.80 百万平方米；
- 第三方开发物业面积 29.82 百万平方米；
- 第三方占比 58.91%；
- 第三方项目数 258；
- 2024 年第三方占比 56.80%。

这比 V4 里的“依赖母公司”判断更细。

---

### 12.4 业务结构和毛利率

来自 2025 MDA：

- 物管收入 1,607.795M；
- 增值服务 307.199M；
- 租赁 8.527M；
- 多元经营 75.717M；
- 商务物业毛利率 22.60%；
- 非商务物业毛利率 8.08%；
- 多元经营毛利率 -0.08%。

这能解释为什么营收增长但毛利率承压。

---

### 12.5 商誉减值

来自 P3：

- 2025 商誉减值 18.828M；
- 2024 商誉减值 9.253M；
- 主要来自置佳物业服务；
- 原因是业务收入增长不及预期。

这应该进入 `risk_events.goodwill_impairment`。

---

### 12.6 应收账款质量

来自 P3：

- 贸易应收总额 395.502M；
- 减值准备 46.206M；
- 三年以上应收 32.431M；
- 关联方应收 59.831M；
- 第三方应收 335.671M。

这应进入 `risk_events.receivable_aging`。

---

### 12.7 审计师和审计意见

来自 STMT 的独立核数师报告：

- 致同（香港）会计师事务所有限公司；
- 日期 2026-03-26；
- 报告未见保留意见；
- 可结构化为标准无保留或至少“未发现保留/强调事项”。

---

## 13. 报告生成规则

最终报告生成不应该是：

```text
read compute_bundle → write report
```

而应该是：

```text
read compute_bundle
read report_context
read qualitative_assessment
read analysis_contract
→ write report
```

并在 prompt 中规定：

```text
硬规则：
1. 因子2/3/4 数字只许引用 compute_bundle。
2. 财务历史表只许引用 annual_financials/input_data。
3. 运营、股权、审计、MDA 只许引用 report_context。
4. 每个关键定性结论必须有 evidence_id 或 source path。
5. 缺失字段必须写“数据不可用”，不得补脑。
6. 如果 context gate 为 DEGRADED，报告必须在元信息中标注。
```

---

## 14. 对当前问题的直接判断

### 14.1 不应该回到 V3 那种“LLM 读 PDF 写长文”的模式

因为 V3 虽然丰富，但不可控：

- 哪些数字来自 PDF？
- 哪些来自 LLM 归纳？
- 哪些有页码？
- 哪些经过校验？
- 哪些可能是错提取？

这些都不够清晰。

---

### 14.2 也不能停留在 V4 这种“只用 compute_bundle”的模式

因为 V4 过度收缩，丢掉了投资判断必需的上下文。

对物管公司尤其严重，因为关键变量很多在三表之外：

- 在管面积；
- 项目数；
- 第三方面积占比；
- 物业类型结构；
- 商务/非商务毛利率；
- 应收账款账龄；
- 商誉减值原因；
- 控股股东依赖；
- 管理层变化。

---

### 14.3 正解是 V5：compute_bundle + report_context + evidence

也就是：

```text
V3 的信息密度
+
V4 的确定性计算
+
数据库/evidence 的可追溯性
```

---

## 15. 建议最终产物

短期建议定义三个文件：

```text
output/01502_金融街物业/
  ├── compute_bundle.json          # 定量计算
  ├── report_context.json          # 运营/治理/审计/MDA/市场事实
  ├── report_input_bundle.json     # 报告生成统一输入
```

其中：

```text
report_input_bundle.json
=
compute_bundle.json
+ report_context.json
+ analysis_contract
+ evidence summary
```

以后所有报告都从这个 bundle 生成。

---

## 16. 一句话总结

V4 的问题不是“写得短”，而是它只接入了 **计算事实**，没有接入 **年报事实**。

V3 的问题不是“写得长”，而是它把年报事实直接交给 LLM 消化，缺少结构化、证据化、门禁化。

所以整体设计应该升级为：

```text
财务数据 → annual_financials → compute_bundle
年报上下文 → fact_observations/report_context → evidence
两者合并 → report_input_bundle
LLM 只基于 bundle 写报告
```

这样未来报告才能同时做到：

- 数字可复现；
- 信息密度足够；
- 年报事实可追溯；
- 错误提取可拦截；
- LLM 不再浪费 token 读整份 PDF；
- 投资建议有清晰证据链。

---

## 17. GG 人工拆分：不要把数据缺口塞给 Zone J

### 17.1 问题边界

GG 的难点之一，不是公式本身，而是某些行业的人力成本无法靠结构化数据库精确拆分。

典型问题：

- CSMAR/DB 能告诉我们“公司一共支付了多少工资”
- 但不能稳定告诉我们这笔钱里，多少是直接人工，多少是管理人工，多少对应销售端
- 对外包密集行业，还存在“很多运营人工其实根本不走工资，而是走供应商付款”的现实

所以这里的问题本质上不是“Zone J 调参不够聪明”，而是**纯 DB 路径拿不到附注级事实**。

---

### 17.2 物业公司案例：招商积余类问题

物业公司是最典型的失真场景之一。

原因不是模型不会算，而是会计呈现方式与制造业不同：

- 大量保洁、保安、工程维护等现场人工，可能外包给第三方服务商
- 这部分在现金流和资产负债表里更接近供应商付款或应付账款，而不是应付职工薪酬
- 内部员工更多是区域管理、总部中后台、招商主管理等管理型岗位

因此，对这类公司：

- `cash_paid_employees` 不等于全部运营层 direct labor
- `admin_exp + sell_dist_exp` 也不一定完整覆盖所有管理性薪酬
- `cash_paid_employees - admin_exp - sell_dist_exp` 只能算保守估计，不是附注确认后的真相

这意味着某些物管公司的低 GG，可能不是“算错”，而是这种商业模式在保守穿透口径下本来就回报偏低。

---

### 17.3 正确架构：Agent 取证，compute_bundle 结算

这一块不能继续让写报告的 Agent 在正文里边读边猜。职责必须拆开：

1. `compute_bundle.py` 先跑纯 DB 路径，给出默认 GG
2. 若命中 GG 敏感行业或低置信度条件，则触发 `PDF extraction agent`
3. `PDF extraction agent` 读取年报附注，提取职工薪酬按职能拆分、外包服务成本等事实
4. Agent 产出 `gg_override.json`
5. `compute_bundle.py` 再按固定优先级重算 GG
6. `report agent` 只消费最终结果和依据，不自行重算

也就是说：

- 写报告的 Agent 不负责最终数字
- 负责读 PDF 的 Agent 只负责把事实结构化
- 最终结算权始终在 `compute_bundle.py`

---

### 17.4 gg_override.json 的定位

`gg_override.json` 不是“另一个 compute_bundle”，而是**附注事实承接层**。

它应承接的是这类信息：

- 直接人工
- 管理人工
- 销售人工
- 外包服务成本
- 对应页码
- 提取依据
- 置信度

它不应直接写：

- 最终 GG
- 最终建议仓位
- 对 Zone J 的主观判断

因为一旦 override 文件直接携带结论，系统就又会退回“Agent 直接改数字”的旧问题。

---

### 17.5 固定优先级与降级语义

GG 人工拆分必须采用固定优先级：

```text
pdf_override > industry_heuristic > db_proxy
```

对应语义：

- `pdf_override`：有附注事实，最高优先级
- `industry_heuristic`：行业兜底估计，仅用于少数特殊行业
- `db_proxy`：通用数据库代理法，最保守但最不精确

若落在后两层，报告必须降级表述，例如：

- “基于数据库代理口径估计”
- “未取得职工薪酬附注分职能拆分，结论存在口径不确定性”
- “该 GG 更适合视为保守穿透回报率，而非精确经济回报率”

不能写成：

- “公司 direct labor 为 X”
- “已经精确拆分管理人工和运营人工”

除非确实有附注证据支撑。

---

### 17.6 对 report_context 设计的影响

这件事说明 `report_context` 不只是为了补运营/治理/审计信息，也要承担一类新的职责：

> 把 PDF 中对定量计算有决定性影响、但 DB 不具备的附注事实，结构化并可审计地交给计算层。

因此，未来 `report_context` / evidence 层除了在管面积、商誉减值、应收账龄这些经营事实，还应支持：

- 职工薪酬分职能披露
- 外包服务成本披露
- 人工/外包混合成本的附注说明
- 管理层对成本结构变化的解释

这部分不是让 LLM 写得更花，而是让系统在需要时能够**有证据地修正 GG 输入**。
