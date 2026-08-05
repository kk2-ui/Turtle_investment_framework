# 数据库规范 (V12.18)

> **目标读者**：接手本项目的 AI Agent。读完本文了解数据全貌，避免踩坑。
> **DB 文件**：`stock_analysis.db`（162K 行，~124 MB）
> **最后更新**：2026-07-20（新增坑13-14：CSMAR应付/负债字段映射、实体变更数据混合）

## 数据源

| 数据源 | 市场 | 年份 | 格式 | 导入脚本 |
|--------|------|------|------|---------|
| CSMAR A股面板 | A股 (SH/SZ) | 2000-2025 | xlsx (265列) | `import_csmar.py` |
| CSMAR HK 利润表+BS+CF+披露指标 | 港股 | 2005-2025 | xlsx (多个文件) | `import_csmar_hk_full.py` |
| Tushare HK CSV | 港股 | 2005-2025 | CSV (LONG格式) | `rebuild_hk_data.py` |
| Tushare HK parquet | 港股 | 2005-2025 | parquet | `import_hk_shares.py` |

**数据优先级**：CSMAR > Tushare parquet > Tushare CSV。CSMAR 是学术数据库，数据质量最高。

## 坑和注意事项

### 坑1：港股 NP 归属口径混乱

**问题**：Tushare CSV 的"股东应占溢利"有时是合并净利润（含少数股东），有时是归母净利润。CSMAR B0024 才是真归母。

**修复**：全部港股 `n_income_attr_p` 已用 Parquet 的 `holder_profit` 覆盖（经 00506.HK 年报验证一致）。

**不要**：直接用 Tushare CSV 的 NP 值，除非 CSMAR 和 Parquet 都没有数据。

### 坑2：HK Capex 被拆分

**问题**：Tushare HK CSV 把资本支出拆成"购建固定资产"和"购建无形资产及其他资产"两项，但 `HK_CASHFLOW_MAP` 只映射了后者（通常只有 2-3M），漏了主体（通常 500-700M）。

**修复**：CSMAR CF 的 C002006 是全额 capex（不拆分），已覆盖全部港股。`rebuild_hk_data.py` 也同时映射了两个 Tushare capex 字段。

**验证**：FY2024 HK capex 覆盖率 95%（2,614/2,738）。

### 坑3：fiscal_year 是月份不是年份

**问题**：Tushare `hk_fina_indicator` parquet 的 `fiscal_year` 字段存的是期间月份（12=年报，6=中报），不是日历年。用 `end_date[:4]` 取年份。

**修复**：`import_hk_shares.py` 已修正。

### 坑4：港股股本全部为 NULL

**问题**：Tushare `hk_basic` API 不提供港股总股本，`stocks.shares_m` 全为空。`hk_basic` CSV 也没有股本字段。

**修复**：CSMAR 披露指标的 `IssueCapPE`（发行股数）已导入 → `base_share`，港股股本覆盖率 96%。

**A股股本**：CSMAR `share_capital`（实收资本，单位百万元）→ `base_share`（百万股），面值1元，数值相等。覆盖率 98%。

### 坑5：COALESCE 顺序反了

**问题**：`import_hk_shares.py` 初版 `COALESCE(excluded.col, annual_financials.col)` 导致 parquet 值覆盖了 CSV 权威值。

**修复**：改为 `COALESCE(annual_financials.col, excluded.col)`——保留已有值，只填 NULL。后来发现 NP 修正需要反向逻辑，已单独处理。

**原则**：写 UPSERT 时先确认哪个源更权威，再决定 COALESCE 顺序。不要默认一个方向。

### 坑6：observations 管线是僵尸数据

**问题**：`financial_observations`（2,400万行）、`field_evidence`（1,780万行）、`curation_decisions`（270万行）是旧版 `migrate_to_db.py` 管线的中间产物。管线被绕过（直接 UPSERT `annual_financials`）后，这些表变成僵尸数据，占 12.6 GB。

**修复**：已清空并 VACUUM。**不要再启用管线导入**。所有数据导入走直接 UPSERT 脚本。

### 坑7：单位混用

| 数据 | 单位 | 说明 |
|------|------|------|
| CSMAR xlsx | 元 | 导入时除以 1,000,000 → 百万元 |
| Tushare HK CSV | 元 | 同上 |
| DPS | 元/股 | **不需要**除 SCALE |
| EPS | 元/股 | **不需要**除 SCALE |
| 股本 (IssueCapPE) | 股 | 除以 1,000,000 → 百万股 |
| 股本 (share_capital, A股) | 百万元 | 面值 1 元，数值 = 百万股 |

### 坑8：A股 share_capital 直接等于 base_share

**问题**：CSMAR A股 `share_capital`（实收资本）单位是百万元，面值 1 元/股，所以数值直接等于百万股。不需要再除 1,000,000。

**验证**：茅台 share_capital=1,256（百万元）= 12.56 亿元 / 1 元 = 12.56 亿股 = 1,256 百万股 ✅

### 坑9：CSMAR HK 字段映射错误（2026-07-18 发现并修复）

**问题**：`import_csmar_hk_full.py` 的 `BS_FIELDS` 和 `CF_FIELDS` 中有 5 处 CSMAR 字段代码映射错误，导致导入的 BS/CF 数据语义完全错误。

**错误的映射**：

| CSMAR 字段 | 错误映射到 DB 列 | CSMAR 实际含义 | 正确映射 |
|-----------|-----------------|---------------|---------|
| `A001212` | `total_assets` | **固定资产净额** | `fix_assets` |
| `A001` | （未映射） | **资产总计** | `total_assets` |
| `A001213` | `goodwill` | **在建工程净额** | （移除） |
| `A001220` | （未映射） | **商誉净额** | `goodwill` |
| `C0021` | `n_cashflow_inv_act` | **投资活动现金流入小计** | `C002`（净额） |
| `C0031` | `n_cash_flows_fnc_act` | **筹资活动现金流入小计** | `C003`（净额） |

**影响**：
- `total_assets` 存的是固定资产净额（而非总资产）→ 所有断点检测、GG/DDM 计算均受影响
- `goodwill` 存的是在建工程净额（而非商誉）→ 商誉跳升检测全部误判
- `n_cashflow_inv_act` 存的是投资现金流入（而非净额）→ 恒为正数，无法反映真实投资活动

**修复**：`import_csmar_hk_full.py` 字段映射已修正。DB 中 BS 和 CF 数据已用修正后的映射重新导入。受影响的分析合约（`analysis_contract.json`）需删除后重新运行 Phase 0。

**教训**：CSMAR 字段命名有规律但易混淆——`A001`（资产总计）、`A001212`（固资净额）、`A001213`（在建工程）、`A001220`（商誉）都挤在 `A0012xx` 范围。导入时必须对照 `[DES][xlsx].txt` 文件逐一核对，不要凭直觉猜测字段含义。

## 表结构

### annual_financials（核心表）

- **行**：一只股票 × 一个财年 × 一个报表类型（annual/semiannual）
- **UNIQUE 约束**：`(ts_code, fiscal_year, report_type)` —— 保证不重复
- **217 列**，实际有数据的 ~140 列（A股有、港股无的互斥）
- 所有金额单位为**百万元**（RMB 或 HKD，取决于股票上市地）

### stocks

- `shares_m`：总股本（百万股）。港股 81% 有数据，A股 98%

## 关键字段覆盖率（FY2024）

| 字段 | HK | A股 | AA 用途 |
|------|-----|------|---------|
| revenue | 100% | 100% | Step 1 |
| n_income_attr_p | 57%* | 74% | GG 分子 |
| n_cashflow_act | 67% | 81% | Step 7 |
| c_pay_acq_const_fiolta | 95% | 100% | Step 5 |
| total_assets | 98% | 100% | Step 8 |
| total_hldr_eqy_exc_min_int | 93% | 100% | Step 6 |
| d_a | 100% | 100% | OE |
| cash_paid_employees | 4% | 100% | W2 L1 |
| base_share | 100% | 98% | EPS/分红 |
| dps | 42% | 68% | M 系数 |

> *HK NP 57%：CSMAR 覆盖 54% + Parquet 兜底。剩余 NULL 是退市/停牌/新股。

## 导入脚本说明

| 脚本 | 作用 | 幂等？ | 耗时 |
|------|------|--------|------|
| `rebuild_hk_data.py` | Tushare HK CSV → 覆盖利润表+BS+CF | ✅ UPSERT | ~2min |
| `import_hk_shares.py` | Tushare parquet → EPS/DPS/股本/PE/PB | ✅ COALESCE | ~30s |
| `import_csmar_hk_full.py` | CSMAR HK xlsx → 全部覆盖（V12.15 已修正字段映射） | ✅ OVERWRITE | ~5min |
| `import_csmar.py` | CSMAR A股 xlsx → 补充字段 | ✅ UPSERT | ~2min |

数据导入统一用上面四个脚本。`import_hk_bulk.py`（旧 observations 管线）已于 V12.15 删除。

### 坑10：A股 CSMAR 面板单位不统一（2026-07-19 发现并修复）

**问题**：`import_csmar.py` 不做单位转换，直接 `round(v,2)` 写入 DB。但 CSMAR A股面板 xlsx 中，不同列使用不同单位：
- `total_assets`、`total_liab`、`revenue`、`oper_cost` 等汇总字段 → **万亿元**
- 部分中小票的 `revenue` → **百万元**（与上一条互斥）
- `n_income_attr_p`、`goodwill`、`fix_assets` 等明细字段 → **百万元**或元

**影响**：格力 total_assets=0.39（万亿元）与 goodwill=1324（百万元）在同一行，goodwill/total_assets=340,000%，所有年份都被标记为商誉跳升断点，`effective_years=[]`。

**修复**：三步精准修复——
1. 对 `total_assets<100` 的 A 股，乘 1M
2. 回退不需要乘的列（fix_assets、money_cap 等）
3. 用 `revenue>total_assets×20` 检测被误乘的 revenue，回退

**教训**：不要假设同一数据源的所有列使用同一单位。导入时必须对照 DES 文件和已知股票财报做交叉验证。

### 坑11：A股 shares_m 全部为 0.01（2026-07-19 发现并修复）

**问题**：`stocks.shares_m` 对 248 只 A 股存储为 0.01（百万股=1万股）。格力市值=39.95×0.01=0.4 百万，GG=420 万%。

**修复**：用 `annual_financials.share_capital`（实收资本，单位百万元=百万股，面值1元）覆盖 `stocks.shares_m` 和 `annual_financials.base_share`。修复了 106 只有 share_capital 的 A 股。

### 坑12：Zone B mda.json 分红提取错误（2026-07-19 发现）

**问题**：Zone B LLM 从年报 PDF 提取 `mda.json` 时，将金融街物业 2025 年分红误读为 `"建议末期股息每股 0M"`（实际 DPS=0.145）。Agent 引用 Zone B 数据时传播了错误结论。

**修复**：事实对账器新增规则——章级别（5f）和报告级别（6c）扫描"零分红/DPS=0/股息每股 0"等关键词，与 `compute_bundle.params.dps_fy` 交叉验证。

### 坑13：CSMAR 应付/负债字段映射错误（2026-07-19 发现并修复）

**问题**：同坑9，`import_csmar_hk_full.py` 的 BS 映射中还有 3 处错误：
- `A002113`（应交税费）→ 映射到 `acct_payable`（应为 `A002108` 应付账款）
- `A002115`（应付股利）→ 映射到 `contract_liab`（CSMAR 无专用合同负债字段）
- `A002117`（不存在于 DES）→ 映射到 `adv_receipts`（应为 `A002109` 预收款项）

**影响**：金融街物业 AP 显示为 11M（实际 785M），交易性金融负债被当成应付账款。

**修复**：字段映射已修正，港股 BS 全量重新导入。

### 坑14：CSMAR 实体变更混合数据（2026-07-20 发现）

**问题**：港股存在同一代码在不同时期代表不同实体的情况。如 00816.HK 在 2018 年前是金茂控股（开发商，资产 112B），2018 年后是金茂服务（物业公司，资产 2-4B）。CSMAR 将两个实体的数据混合在同一 `ts_code` 下，revenue 从 16B 骤降到 575M。

**影响**：`pre_analysis_phase` 检测到断点并正确约束窗口。但 `validate.py` 仍检查全量数据，导致 readiness=DEGRADED。

**修复**：`pre_analysis_phase` 的结构性断点检测已正确处理此类变更。`compute_bundle_db` 不再因 DEGRADED 返回 ok=False。
