# 龟龟投资框架 — 数据库设计文档

> v3.1 | 2026-07-08 | 计算优先 + 字段级质量门禁架构

---

## 1. 概述

### 1.1 设计目标

旧架构的核心问题是：91 个 JSON 文件 × 6 种 schema × 3 套命名 × 2 种单位，导致 Agent 每次分析前都要猜数据格式、猜字段口径、猜单位。

v3.0 的方向是：

> 1 个 SQLite 数据库 → 1 套 schema → 1 套命名 → 1 种单位 → 确定性计算。

但年报数据天然不规则，尤其港股 PDF、Tushare fallback、LLM 抽取和人工修复可能出现：

- 字段互换：如 `revenue` 被写成 `total_assets`。
- 单位错误：元、千元、百万元混用。
- 口径错误：归母净利、少数股东损益、总权益混淆。
- 年度错位：2023 数据写入 2024。
- 股本缺失：导致市值、DDM、仓位全部失真。
- 现金流符号错误：Capex 正负号、已付股息口径错误。

因此数据库不能只是“存储层”，还必须成为：

> **数据进入分析前的裁判。**

目标架构是：所有抽取结果先作为“候选字段值”进入数据库，经过字段级证据、质量门禁、跨源对账和 curation 后，才进入 `annual_financials` 成为可供计算的事实数据。LLM 报告阶段只读取 curated 数据和 analysis contract，不再临时判断原始年报数据是否可信。

### 1.2 核心原则

1. **所有金额统一百万元 RMB**  
   入口处转换，不存在“这个值是元还是百万元”的歧义。

2. **字段名统一 Tushare 英文命名**  
   `revenue`, `n_income_attr_p`, `n_cashflow_act` 等，一个概念一个名字。

3. **候选数据与最终事实分离**  
   PDF、Tushare、input_data、人工修复先进入候选层，不直接污染 `annual_financials`。

4. **字段级证据优先于行级日志**  
   核心字段必须能追溯到来源、页码、表名、原始文本、单位转换规则和置信度。

5. **验证在入库前，评估在计算前**  
   脏数据不进入最终事实表；`validate.py` 先判断能不能分析，再决定是否运行 `compute_bundle.py`。

6. **分析契约硬阻断**  
   open BLOCK 存在时，不生成完整投资建议，只输出数据问题和修复建议。

---

## 2. 当前已实现数据库 Schema

### 2.1 当前表结构

```text
stock_analysis.db
├── stocks                    # 标的基本信息
├── annual_financials         # 年度财务数据（当前核心事实表）
├── thresholds                # 买入门槛参数
├── computed_metrics          # 定量计算结果
├── rejection_checks          # 否决门逐条记录
├── data_quality_log          # 数据质量日志
├── audit_log                 # 入库审计日志
```

### 2.2 stocks — 标的基本信息

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | TEXT PK | 01502.HK, 600519.SH |
| name_cn | TEXT | 金融街物业 |
| name_en | TEXT | Financial Street Property |
| market | TEXT | HK / A / US |
| industry | TEXT | 物管 |
| shares_m | REAL | 总股本（百万股） |
| currency | TEXT | 默认 RMB |
| is_soe | INTEGER | 是否央企/国企 |

**已知问题**：`shares_m` 对港股经常为 NULL。Tushare 对港股不稳定返回股本数据，`hk_report_fallback.json` 也不一定包含此字段。当前可通过 `compute_bundle.py --shares` 手动传入，但这会导致计算结果依赖 CLI override，难以审计。

### 2.3 annual_financials — 年度财务数据（当前核心表）

唯一键：`(ts_code, fiscal_year, report_type)`

#### 利润表字段（百万元 RMB）

| 字段 | 来源字段名 | 说明 |
|------|-----------|------|
| revenue | revenue | 营业收入 |
| oper_cost | oper_cost | 营业成本 |
| gross_profit | gross_profit | 毛利 |
| gross_margin | gross_margin | 毛利率 % |
| n_income_attr_p | n_income_attr_p | 归母净利润 |
| minority_profit | minority_profit | 少数股东损益 |
| pretax_profit | pretax_profit | 税前利润 |
| income_tax | income_tax | 所得税 |
| d_a | depr_fa_coga_dpba | 折旧摊销合计 |

#### 资产负债表字段（百万元 RMB）

| 字段 | 来源字段名 | 说明 |
|------|-----------|------|
| money_cap | money_cap | 货币资金 |
| cash_broad | cash_broad | 广义现金 |
| accounts_receiv | accounts_receiv | 应收账款 |
| acct_payable | acct_payable | 应付账款 |
| contract_liab | contract_liab | 合同负债 |
| total_assets | total_assets | 资产总计 |
| total_liab | total_liab | 负债总计 |
| total_hldr_eqy_exc_min_int | total_hldr_eqy_exc_min_int | 归母权益 |
| minority_int | minority_int | 少数股东权益 |
| goodwill | goodwill | 商誉 |
| st_borr | st_borr | 短期借款 |
| lt_borr | lt_borr | 长期借款 |

#### 现金流量表字段（百万元 RMB）

| 字段 | 来源字段名 | 说明 |
|------|-----------|------|
| n_cashflow_act | n_cashflow_act | 经营活动现金流 OCF |
| c_pay_acq_const_fiolta | c_pay_acq_const_fiolta | 资本支出 Capex（存绝对值） |
| fcf | — | 自由现金流 = OCF - Capex |
| dividends_paid | dividends_paid | 已付股息总额 |

#### 每股数据

| 字段 | 说明 |
|------|------|
| eps | 每股收益 |
| dps | 每股股息 |

#### 当前元数据

| 字段 | 说明 | 可选值 |
|------|------|--------|
| data_source | 数据来源 | tushare / tushare_hk_fallback / pdf_verified / manual |
| data_quality | 数据质量 | verified / estimated / fallback / suspect |

### 2.4 当前数据库约束

```sql
CHECK (revenue IS NULL OR revenue > 0)
CHECK (total_assets IS NULL OR total_assets > 0)
CHECK (n_income_attr_p IS NULL OR ABS(n_income_attr_p) < revenue * 1.5 OR revenue IS NULL)
UNIQUE (ts_code, fiscal_year, report_type)
```

设计决策：SQLite 不支持 `ALTER TABLE ADD CHECK`，所以 CHECK 必须在 `CREATE TABLE` 时定义。当前约束是软约束：允许 NULL，只检查非 NULL 值的合理性。

### 2.5 当前视图

| 视图 | 用途 |
|------|------|
| `v_latest_metrics` | 每支标的最新一次计算结果 |
| `v_stock_snapshot` | 标的 + 门槛 + 计算结果的联合视图 |
| `v_data_completeness` | 每支标的字段覆盖率 |

`v_data_completeness` 已能评估字段覆盖率、usable_pct 和 BS 偏差，是后续 readiness contract 的基础。

---

## 3. 当前数据流程

### 3.1 数据采集层

```text
A股: Tushare API → tushare_collector.py → data_pack_market.md
港股: Tushare API / PDF → pdf_preprocessor.py → populate_hk_fallback.py → hk_report_fallback.json
```

### 3.2 数据迁移层（当前 migrate_to_db.py）

```text
现有 JSON 文件
  │
  ├─ hk_report_fallback.json（备用，单位可能为元）
  │     └─ import_hk_fallback() → 单位转换 → annual_financials
  │
  ├─ input_data.json（优先，PDF验证数据，单位=百万元）
  │     └─ import_input_data() → annual_financials
  │
  ├─ threshold.json → thresholds
  ├─ compute_bundle.json → computed_metrics + rejection_checks
  └─ fix_plan.json → data_quality_log
```

当前导入顺序：fallback 先，input_data 后。高质量来源通过 `INSERT OR REPLACE` 覆盖低质量来源。

### 3.3 当前单位转换

所有 monetary 字段在入库时统一转换为百万元 RMB：

| 来源 | 原始单位 | 转换 | 检测逻辑 |
|------|---------|------|---------|
| input_data.json | 百万元 | 无需转换 | — |
| hk_report_fallback.json | 元或百万元 | 大数 ÷1,000,000 | `abs(val) > 100,000` → 元 |
| Tushare A-share | 元 | ÷1,000,000 | 同上 |

---

## 4. 当前验证体系

### 4.1 七层门禁现状

```text
数据到达
  │
  ├─ ① 单位检测 (db_gate.detect_and_fix_unit)
  │     · 元→百万元自动转换
  │     · 负值检测
  │     · 字段互换初筛
  │
  ├─ ② 业务规则 (db_gate.validate_financial_row)
  │     · BLOCK: 关键字段 NULL
  │     · BLOCK: NP > 1.5× revenue
  │     · BLOCK: revenue ≈ total_assets
  │     · WARN:  BS identity 偏差 10-30%
  │     · WARN:  YoY revenue 跳变 > 10x
  │
  ├─ ③ DB CHECK 约束
  │     · revenue > 0
  │     · total_assets > 0
  │     · ABS(NP) < revenue × 1.5
  │
  ├─ ④ 完整性评分 (v_data_completeness)
  │     · 核心字段覆盖率
  │     · usable_pct
  │     · bs_deviation_pct
  │
  ├─ ⑤ data_gate.py 细粒度门禁（当前未完全并入 DB 链路）
  │     · PDF 重复/缺失
  │     · 核心字段覆盖
  │     · 资产字段覆盖
  │     · BS identity
  │     · 现金/商誉/无形资产 sanity
  │
  ├─ ⑥ 跨源对账（当前仅存在性检测）
  │     · fallback vs verified 同时存在 → 标记
  │
  └─ ⑦ 审计日志 (audit_log / data_quality_log)
        · INSERT / BLOCK 记录
        · 质量日志记录
```

### 4.2 validate.py 当前输出

```bash
python3 scripts/validate.py --code 01502.HK
python3 scripts/validate.py --code 01502.HK --json
python3 scripts/validate.py --all
```

当前三维评估：

1. `data_completeness`：字段覆盖率、usable_pct、BS 偏差、被 gate 拦截行数。
2. `compute_confidence`：股本来源、M 来源、D&A 可用性、DPS 可用性。
3. `analysis_readiness`：ready / degraded / insufficient。

### 4.3 当前已知拦截案例

| 标的 | 拦截行数 | 原因 |
|------|:---:|------|
| 00696.HK | 6/6 | total_assets / equity 全部 NULL |
| 01522.HK | 5/5 | n_income_attr_p / equity 全部 NULL |
| 01502.HK | 4/5 | revenue ≈ total_assets（字段互换，来自 populate_hk_fallback.py bug） |

---

## 5. 目标顶层架构：候选层 → 证据层 → 质量层 → 最终事实层

### 5.1 目标数据流

```text
PDF / Tushare / input_data / 人工修复
  │
  ▼
raw_import_batches                 # 一次导入一个 batch
  │
  ▼
financial_observations             # 候选字段值，一字段一记录
  │
  ▼
field_evidence                     # 页码、表名、原文、单位转换、置信度
  │
  ▼
quality_findings                   # 字段/行/年度/跨源 BLOCK/WARN/INFO
  │
  ▼
curation_decisions                 # 为什么采用这个值
  │
  ▼
annual_financials                  # 已核准年度事实表
  │
  ▼
analysis_contracts / v_analysis_readiness
  │
  ▼
compute_bundle.py --from-db
  │
  ▼
LLM 写报告 + 定性判断
```

### 5.2 设计重点

- `annual_financials` 不再是原始抽取入口，而是最终事实表。
- PDF、Tushare、input_data、manual fix 均先进入候选层。
- 同一字段允许多个候选来源。
- 所有核心字段都应能追溯证据。
- 数据质量问题统一进入 `quality_findings`。
- 最终采用值必须有 `curation_decisions`。
- 分析前必须生成 readiness contract。

---

## 6. 建议新增表设计（目标架构）

> 本节是目标设计，不代表当前代码已经全部实现。

### 6.1 raw_import_batches — 导入批次表

记录一次导入动作，支持重跑、回滚、审计和增量更新。

| 字段 | 类型 | 说明 |
|------|------|------|
| batch_id | TEXT PK | 导入批次 ID |
| ts_code | TEXT | 标的代码 |
| company_name | TEXT | 公司名称 |
| market | TEXT | HK / A / US |
| fiscal_year | INTEGER | 财年，可为空表示多年度批次 |
| source_type | TEXT | pdf_extract / tushare / input_data / manual_fix / compute_bundle / threshold |
| source_path | TEXT | 来源文件路径 |
| source_hash | TEXT | 来源文件 hash |
| importer_version | TEXT | 导入器版本 |
| imported_at | TEXT | 导入时间 |
| status | TEXT | imported / validated / blocked / partially_curated / curated |
| notes | TEXT | 备注 |

### 6.2 financial_observations — 字段级候选值表

每个候选字段值一条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| observation_id | TEXT PK | 候选值 ID |
| batch_id | TEXT | 所属导入批次 |
| ts_code | TEXT | 标的代码 |
| fiscal_year | INTEGER | 财年 |
| report_type | TEXT | annual / interim |
| statement_type | TEXT | income / balance_sheet / cashflow / market / dividend |
| field_name | TEXT | Tushare 英文字段名 |
| raw_value | TEXT | 原始值 |
| normalized_value | REAL | 标准化值 |
| unit | TEXT | RMB_million / shares_million / percent / ratio / text |
| currency | TEXT | RMB / HKD / USD / unknown |
| sign_convention | TEXT | positive_outflow / raw_statement / normalized |
| source_type | TEXT | pdf_extract / tushare / input_data / manual_fix / legacy_db |
| source_priority | INTEGER | 来源优先级 |
| confidence | REAL | 候选值置信度 |
| extraction_method | TEXT | agent_pdf / tushare_api / fallback_parser / manual |
| status | TEXT | candidate / accepted / rejected / superseded / needs_review |
| rejection_reason | TEXT | 拒绝原因 |
| created_at | TEXT | 创建时间 |

设计收益：

- `input_data.json` 不再静默覆盖 fallback。
- 可以保留 PDF、Tushare、manual fix 的多个候选值。
- 字段级质量可追踪，不再只能行级 BLOCK。

### 6.3 field_evidence — 字段级证据表

记录候选值来自年报哪里、如何被规范化。

| 字段 | 类型 | 说明 |
|------|------|------|
| evidence_id | TEXT PK | 证据 ID |
| observation_id | TEXT | 对应候选字段 |
| document_path | TEXT | PDF 或来源文件 |
| document_hash | TEXT | 文档 hash |
| page_no | INTEGER | 页码 |
| table_name | TEXT | 表名 |
| row_label | TEXT | 行标签 |
| column_label | TEXT | 列标签 |
| raw_text | TEXT | 原始文本片段 |
| nearby_text | TEXT | 上下文文本 |
| extraction_prompt_version | TEXT | 抽取 prompt 版本 |
| extractor_model | TEXT | 抽取模型 |
| value_before_normalization | TEXT | 标准化前值 |
| normalization_rule | TEXT | 单位/符号转换规则 |
| unit_detected | TEXT | 检测到的单位 |
| unit_multiplier | REAL | 单位换算倍数 |
| evidence_confidence | REAL | 证据置信度 |

核心字段建议必须有 evidence 才能自动 accepted：

- `revenue`
- `n_income_attr_p`
- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`
- `n_cashflow_act`
- `c_pay_acq_const_fiolta`
- `shares_m`

### 6.4 quality_findings — 统一质量问题表

承接 `db_gate.py` 与 `data_gate.py` 的所有检查结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| finding_id | TEXT PK | 问题 ID |
| batch_id | TEXT | 批次 ID |
| ts_code | TEXT | 标的代码 |
| fiscal_year | INTEGER | 财年 |
| field_name | TEXT | 字段名，可为空表示年度/股票级问题 |
| observation_id | TEXT | 关联候选值 |
| check_name | TEXT | 检查名称 |
| severity | TEXT | BLOCK / WARN / INFO |
| scope | TEXT | field / row / year / stock / cross_source |
| expected | TEXT | 期望值或规则 |
| actual | TEXT | 实际值 |
| message | TEXT | 说明 |
| fix_status | TEXT | open / accepted_risk / fixed / false_positive / superseded |
| fix_observation_id | TEXT | 修复候选值 |
| created_at | TEXT | 创建时间 |
| resolved_at | TEXT | 解决时间 |

### 6.5 curation_decisions — 字段采用决策表

记录最终值为什么被采用。

| 字段 | 类型 | 说明 |
|------|------|------|
| decision_id | TEXT PK | 决策 ID |
| ts_code | TEXT | 标的代码 |
| fiscal_year | INTEGER | 财年 |
| field_name | TEXT | 字段名 |
| accepted_observation_id | TEXT | 被采用的候选值 |
| previous_observation_id | TEXT | 被替换的旧值 |
| decision_type | TEXT | auto_accept / manual_accept / manual_override / reject_all / accept_with_warning |
| decision_reason | TEXT | 决策理由 |
| decided_by | TEXT | system / user / agent |
| decided_at | TEXT | 决策时间 |

### 6.6 analysis_contracts — 分析前契约表

用于防止错误数据进入 LLM 分析。

| 字段 | 类型 | 说明 |
|------|------|------|
| contract_id | TEXT PK | 契约 ID |
| ts_code | TEXT | 标的代码 |
| generated_at | TEXT | 生成时间 |
| readiness_status | TEXT | READY / DEGRADED / BLOCKED |
| readiness_score | REAL | 就绪评分 |
| blocking_reasons_json | TEXT | BLOCK 原因 |
| warning_reasons_json | TEXT | WARN 原因 |
| usable_years_json | TEXT | 可用年份 |
| missing_core_fields_json | TEXT | 缺失核心字段 |
| degraded_fields_json | TEXT | 降级字段 |
| analysis_scope_json | TEXT | 允许的分析范围 |
| data_snapshot_hash | TEXT | 数据快照 hash |

`analysis_scope_json` 示例：

```json
{
  "full_analysis_allowed": false,
  "valuation_allowed": true,
  "ddm_allowed": false,
  "position_sizing_allowed": false,
  "dividend_analysis_allowed": "degraded"
}
```

---

## 7. annual_financials 的目标定位调整

### 7.1 新定位

`annual_financials` 应定位为：

> 已核准的年度财务事实表，供 `compute_bundle.py` 和报告生成使用。

它不再承担：

- 原始 PDF 抽取落地点。
- 多来源候选值存储。
- 字段级置信度存储。
- 字段级证据存储。

这些职责转移到：

```text
curation_decisions → financial_observations → field_evidence
```

### 7.2 建议新增行级元数据

未来可在 `annual_financials` 增加少量行级质量字段：

| 字段 | 说明 |
|------|------|
| curation_status | curated / partial / blocked / legacy_import |
| curation_batch_id | 最近一次 curation 批次 |
| quality_score | 年度数据质量评分 |
| has_blocking_issue | 是否存在未解决 BLOCK |
| warning_count | WARN 数量 |
| evidence_coverage_ratio | 字段证据覆盖率 |
| last_validated_at | 最近验证时间 |

不建议在 `annual_financials` 中为每个字段增加 `xxx_source`、`xxx_confidence`，否则表会膨胀且难以支持多来源候选。

---

## 8. 质量门禁规则（目标）

### 8.1 BLOCK 优先规则

这些规则优先实现，因为它们最容易导致错误买入意见。

| 检查 | 规则 | 处理 |
|------|------|------|
| 核心字段缺失 | revenue / NP / assets / equity / OCF / Capex 缺失 | BLOCK |
| 收入/资产非正 | `revenue <= 0` 或 `total_assets <= 0` | BLOCK |
| 净利异常 | `abs(n_income_attr_p) > revenue * 1.5` | BLOCK |
| 收入资产互换 | `revenue ≈ total_assets` | BLOCK |
| 净利权益互换 | `n_income_attr_p ≈ total_hldr_eqy_exc_min_int` | BLOCK |
| BS 恒等式严重偏差 | `abs(A - E - MI - L) / A > 30%` | BLOCK |
| 单位异常 | 数量级异常且无法自动修复 | BLOCK |
| 股本缺失 | `shares_m` 缺失且需要估值/仓位 | BLOCK |
| 核心跨源冲突 | 同字段跨源差异 >5% 且无人工确认 | BLOCK / needs_review |

### 8.2 WARN / DEGRADED 规则

| 检查 | 规则 | 影响 |
|------|------|------|
| BS 偏差 | 10%-30% | WARN，资产质量降级 |
| 现金大于资产 | `money_cap > total_assets` | WARN |
| OCF 异常 | `abs(n_cashflow_act) > revenue * 2` | WARN |
| 同比跳变 | revenue/assets/shares >10x | WARN / needs_review |
| DPS 缺失或单位可疑 | 少于 3 年有效 DPS | DDM 降级或禁用 |
| D&A 缺失 | 少于 3 年有效 D&A | OE / 维护性 Capex 降级 |
| 应收应付缺失 | AR/AP/合同负债覆盖不足 | 营运质量判断降级 |
| 商誉/无形资产缺失 | goodwill/intangible 缺失 | 资产质量判断降级 |

### 8.3 跨源对账规则

按 `(ts_code, fiscal_year, field_name)` 对比多个候选来源：

| 相对差异 | 处理 |
|----------|------|
| <=1% | 自动一致 |
| 1%-5% | WARN，可按来源优先级接受 |
| >5% | 核心字段 BLOCK 或 needs_review |

推荐来源优先级：

#### 港股

```text
manual_fix（有证据）
  > PDF 年报核心三表（有 field_evidence）
  > input_data verified
  > Tushare HK fallback
  > legacy_db
```

#### A 股

```text
manual_fix（有证据）
  > Tushare 标准财务字段
  > PDF 年报对照
  > input_data verified
  > legacy_db
```

---

## 9. 目标视图设计

### 9.1 v_curated_financials_for_compute

供 `compute_bundle.py --from-db` 读取。

要求：

- 只包含 curated / partial 数据。
- 排除存在 open BLOCK 的年度。
- 附带 quality_score 和 warning_count。
- 字段结构尽量兼容当前 `annual_financials`。

### 9.2 v_field_quality_summary

字段级质量总览。

建议字段：

| 字段 | 说明 |
|------|------|
| ts_code | 标的代码 |
| fiscal_year | 财年 |
| field_name | 字段名 |
| accepted_value | 最终值 |
| source_type | 来源 |
| confidence | 置信度 |
| evidence_count | 证据数量 |
| block_count | BLOCK 数 |
| warn_count | WARN 数 |
| fix_status | 修复状态 |

### 9.3 v_analysis_readiness

分析前快速判断。

建议字段：

| 字段 | 说明 |
|------|------|
| ts_code | 标的代码 |
| readiness_status | READY / DEGRADED / BLOCKED |
| usable_years_count | 可用年度数 |
| core_missing_count | 缺失核心字段数 |
| open_block_count | 未解决 BLOCK 数 |
| open_warn_count | 未解决 WARN 数 |
| ddm_allowed | DDM 是否允许 |
| valuation_allowed | 估值是否允许 |
| position_sizing_allowed | 仓位建议是否允许 |
| last_validated_at | 最近验证时间 |

### 9.4 v_source_conflicts

跨源冲突视图。

建议字段：

| 字段 | 说明 |
|------|------|
| ts_code | 标的代码 |
| fiscal_year | 财年 |
| field_name | 字段名 |
| source_a | 来源 A |
| value_a | 值 A |
| source_b | 来源 B |
| value_b | 值 B |
| relative_diff | 相对差异 |
| severity | BLOCK / WARN / INFO |

---

## 10. 分阶段实施路线图

> 本节为后续实施建议，不代表当前已经完成。

### Phase 1：新增候选层和审计结构

修改 `scripts/db_init.py`：

- 新增 `raw_import_batches`。
- 新增 `financial_observations`。
- 新增 `field_evidence`。
- 新增 `quality_findings`。
- 新增 `curation_decisions`。
- 增加必要索引。

修改 `scripts/migrate_to_db.py`：

- 每次导入创建 batch。
- 将 `hk_report_fallback.json`、`input_data.json` 财务字段写入 `financial_observations`。
- 暂保留现有 `_validate_and_upsert()` 兼容路径。
- 输出候选字段数、证据数、BLOCK/WARN 数、最终写入年度数。

验收标准：

- 同一字段可存多个候选来源。
- 核心字段可查看来源、原始值、标准化值、置信度。
- 原有分析流程不被破坏。

### Phase 2：统一数据门禁落库

修改 `scripts/db_gate.py`：

- 保留 `detect_and_fix_unit()`。
- 保留 `validate_financial_row()`。
- 新增结构化 `QualityFinding` 输出。
- 增加 field / row / year / cross_source 四类检查。

整合 `scripts/data_gate.py`：

- 将 PDF 重复/缺失、字段覆盖、BS identity、现金>资产、商誉/无形资产等检查映射到 `quality_findings`。
- 不再让 `data_gate.py` 与 `db_gate.py` 形成两套互相隔离的判断。

验收标准：

- 错误抽取字段进入候选层，但不进入最终事实表。
- 所有 BLOCK/WARN 可通过 SQL 查询。

### Phase 3：自动 curation 和最终事实生成

新增 curation 逻辑：

- 按 `ts_code/fiscal_year/field_name` 分组。
- 排除 BLOCK 候选。
- 按市场和来源优先级选择 accepted observation。
- 写入 `curation_decisions`。
- 更新 `annual_financials`。
- WARN 字段可入库，但标记 `partial` 或降低 `quality_score`。

验收标准：

- 每个最终字段值可解释“为什么选它”。
- `input_data` 覆盖不再丢失审计信息。
- 核心跨源冲突会阻断或进入人工复核。

### Phase 4：分析前 contract 硬门禁

修改 `scripts/validate.py`：

- 从 `quality_findings`、`curation_decisions`、`annual_financials` 生成 readiness。
- 输出 `READY / DEGRADED / BLOCKED`。
- 输出 `analysis_scope`。
- 可先 JSON 输出，后续落表到 `analysis_contracts`。

规则：

- 存在 open BLOCK → `BLOCKED`。
- 核心字段不足 3 年 → `BLOCKED`。
- 核心可用但 DPS/D&A/应收应付等关键辅助字段缺失 → `DEGRADED`。
- 关键字段齐全且无 open BLOCK → `READY`。

### Phase 5：compute_bundle.py 只读 curated 数据

修改 `scripts/compute_bundle.py`：

- `compute_from_db()` 开始前检查 readiness contract。
- `BLOCKED` 直接退出。
- `DEGRADED` 按 contract 禁用或降级模型。
- `shares_m`、D&A、DPS 警告不再只写 stderr，应结构化进入 contract 或 `quality_findings`。
- `load_from_db()` 改读 `v_curated_financials_for_compute`。

### Phase 6：历史数据和人工修复闭环

历史数据：

- 当前 `annual_financials` 标记为 `legacy_import`。
- 可生成 synthetic observation，source_type=`legacy_db`。
- 不伪造 evidence。
- 对高价值标的优先补证。

人工修复：

- 支持 JSON/CSV 修复输入：`ts_code`、`fiscal_year`、`field_name`、`corrected_value`、`unit`、`reason`、可选 evidence。
- 修复写入 `financial_observations`，source_type=`manual_fix`。
- 写入 `curation_decisions`，decision_type=`manual_override`。
- 关闭相关 `quality_findings`，fix_status=`fixed`。

---

## 11. 推荐 MVP

为尽快减少 token 浪费，优先实现最小闭环：

1. 新增五张表：
   - `raw_import_batches`
   - `financial_observations`
   - `field_evidence`
   - `quality_findings`
   - `curation_decisions`

2. `migrate_to_db.py` 改为：
   - 先写候选。
   - 再运行 gate。
   - 再写 `annual_financials`。

3. 统一以下 BLOCK：
   - 核心字段 NULL。
   - 单位异常。
   - 字段互换。
   - NP > 1.5× revenue。
   - BS 偏差 >30%。
   - shares_m 缺失。
   - 核心跨源差异 >5%。

4. `validate.py` 有 open BLOCK 即输出 `BLOCKED`。

5. `compute_bundle.py --from-db` 在 `BLOCKED` 时停止。

MVP 目标：先挡住最常见、最昂贵、最影响投资结论的错误。

---

## 12. 验证方案

### 12.1 Gate 单元验证

构造输入，验证 `quality_findings`：

| 场景 | 期望 |
|------|------|
| `revenue == total_assets` | BLOCK |
| `abs(n_income_attr_p) > revenue * 1.5` | BLOCK |
| BS identity 偏差 >30% | BLOCK |
| BS identity 偏差 10%-30% | WARN |
| `money_cap > total_assets` | WARN |
| `abs(n_cashflow_act) > revenue * 2` | WARN |
| shares_m 缺失且需要估值 | BLOCK |

### 12.2 导入验证

选择真实 output 子目录：

- dry-run 检查 batch、候选字段和质量统计。
- 正式导入后检查 `financial_observations` 数量。
- 检查核心字段 evidence 覆盖率。
- 确认 BLOCK 字段未进入 `annual_financials`。
- 确认 WARN 字段进入但有 `warning_count` / `quality_score` 反映。

### 12.3 跨源验证

准备同一股票同一年度 PDF 与 Tushare 值：

| 差异 | 期望 |
|------|------|
| <=1% | 自动 accepted |
| 1%-5% | WARN |
| >5% | 核心字段 BLOCK 或 needs_review |

### 12.4 分析前验证

测试三态：

| 状态 | 条件 | 行为 |
|------|------|------|
| READY | 核心字段齐全，无 open BLOCK | 允许完整 `compute_bundle.py --from-db` |
| DEGRADED | DPS/D&A/应收应付等缺失 | 禁用或降级部分模型 |
| BLOCKED | shares_m 缺失、BS 严重失衡、核心字段冲突 | 停止分析，不生成投资建议 |

### 12.5 回归验证

- `scripts/migrate_to_db.py --dry-run` 仍能扫描 output。
- `scripts/validate.py --code <code> --json` 能输出 readiness。
- `scripts/compute_bundle.py --from-db --code <code>` 对 READY 标的仍能生成 bundle。
- `v_latest_metrics`、`v_stock_snapshot`、`v_data_completeness` 保持兼容或有替代视图。

---

## 13. 关键文件

| 文件 | 当前职责 | 目标职责 |
|------|----------|----------|
| `scripts/db_init.py` | 创建当前表和视图 | 增加候选/证据/质量/决策/契约表 |
| `scripts/db_gate.py` | 单位检测 + 行级验证 | 统一字段/行/年度/跨源质量发现生成器 |
| `scripts/data_gate.py` | PDF 与 markdown 细粒度门禁 | 规则迁入或映射到 `quality_findings` |
| `scripts/migrate_to_db.py` | JSON → `annual_financials` | 来源 → 候选 → gate → curation → 最终事实 |
| `scripts/validate.py` | 三维 readiness 评估 | 生成 analysis contract，硬阻断 BLOCK |
| `scripts/compute_bundle.py` | 定量计算，支持 `--from-db` | 只读 curated 视图，按 contract 降级/退出 |
| `prompts/phase2_PDF解析.md` | 年报字段抽取规则 | 字段等级与 evidence 要求来源 |
| `prompts/references/shared_tables.md` | Q/M/II/组合上限等规则 | 分析 contract 的字段依赖依据 |
| `strategies/turtle/references/factor_interface.md` | 因子参数接口 | 定量/定性字段契约依据 |
| `shared/qualitative/references/output_schema.md` | 定性输出 schema | 定性字段未来入库依据 |

---

## 14. 当前已知问题和改进方向

### 14.1 数据源问题

1. **shares_m 港股经常为 NULL**  
   需要从年报、行情源或人工修复补入，并作为估值/仓位的 BLOCK 级依赖。

2. **hk_report_fallback 字段互换 bug**  
   当前已被 `db_gate.py` 部分拦截，但根源仍需修复；目标架构中应通过字段级候选和跨源对账阻断。

3. **DPS 数据不可靠**  
   港股 Tushare 分红数据经常单位错误或缺失；目标架构中 DPS 不可靠时 DDM 应降级或禁用。

4. **A 股 data_pack_market.md 未结构化入库**  
   A 股数据可能存在 markdown 中但未进入 `annual_financials`。后续应增加 markdown → observations 的导入器。

### 14.2 验证体系问题

1. **data_gate.py 与 db_gate.py 并存**  
   `data_gate.py` 更细，但未完全并入 DB 链路；应统一输出到 `quality_findings`。

2. **跨源对账过浅**  
   当前主要检测两个来源是否同时存在；目标应逐字段差异对账。

3. **字段级证据不足**  
   当前 `annual_financials` 只有 `data_source` 和 `data_quality`，无法解释每个字段来自哪里。

4. **stderr 警告不可审计**  
   `compute_bundle.py` 对 shares_m、D&A 等缺失的警告应结构化进入 readiness/quality 表。

### 14.3 架构问题

1. **migrate_to_db.py 偏批量导入**  
   后续需要 batch 化和增量更新。

2. **compute_bundle → DB 回写不完整**  
   当前 compute 输出 JSON 后需再次 migrate 才能入库；后续应直接结构化写入 `computed_metrics` 和 `rejection_checks`。

3. **历史数据缺少证据**  
   不能伪造 evidence，应标记 `legacy_import`，并逐步补证。

---

## 15. 最终设计原则

数据库不要只是“存分析需要的数据”，而要成为“数据进入分析前的裁判”。

LLM 不应在报告阶段重新判断原始年报数据是否可信；它应只读取：

1. 经过 curation 的 `annual_financials`。
2. 明确 READY / DEGRADED / BLOCKED 的 analysis contract。
3. 必要时可追溯的字段级证据。

这样可以系统性避免错误年报抽取浪费 token，并让股票买入意见建立在清晰、可追溯、可修复的数据基础上。
