# Turtle 财务数据库规范

> 状态：`CURRENT / CANONICAL_DATABASE_CONTRACT`
>
> 更新：2026-08-19

## 1. 单一数据库

Turtle 的财务数据真源是仓库根目录 `stock_analysis.db`。正常研究和报告生成只读取这个数据库，不依赖仓库外的 CSV、Parquet、XLSX、DTA 或 ZIP 目录。

数据库有两层：

- `annual_financials`、`stocks`：供现行研究代码读取的规范化读模型；
- `source_*`、`source_imports`、`source_file_archives`：随库保存的结构化源表、导入清单和无法等价展开的压缩源包。

金额统一为报表币种的百万元；每股值和百分比不缩放。A股报表币种为人民币，港股报表币种按源文件记录并由 `stocks.currency` 暴露。`fiscal_year` 必须来自报告期截止日，不能使用 Tushare 港股接口中代表月份的同名字段。

## 2. 数据源优先级

规范化读模型按以下顺序构建，后者的非空字段覆盖前者：

1. A股、港股 Tushare 数据作为覆盖与缺口兜底；
2. CSMAR A股年度面板覆盖对应年度字段；
3. CSMAR 港股利润表、资产负债表、现金流量表及披露指标覆盖对应年度字段；
4. `gross_profit`、`fcf`、最新股本等只在源字段齐备后确定性派生。

不再允许脚本分别对活动数据库执行局部导入。以下旧入口已退役：

- `import_csmar.py`
- `import_csmar_hk_full.py`
- `import_hk_shares.py`
- `rebuild_hk_data.py`
- `migrate_a_share_to_db.py`

它们会拒绝执行，避免重新引入混合单位、错误财年或旧 observations 管线。

## 3. 重建与切换

外部源数据只在取得新批次、需要重建数据库时临时出现。统一入口：

```bash
.venv/bin/python scripts/consolidate_financial_database.py build \
  --template-db stock_analysis.db \
  --output-db /absolute/path/stock_analysis.staging.db \
  --data-root /absolute/path/to/data-root
```

构建永远写入新库，不修改活动库。只有验证为 `PASS` 后才允许切换：

```bash
.venv/bin/python scripts/consolidate_financial_database.py promote \
  --staging-db /absolute/path/stock_analysis.staging.db \
  --active-db stock_analysis.db
```

删除外部源目录必须使用同一脚本；它会检查活动库已经嵌入结构化源表、压缩源包并拥有当前 `PASS` 验证：

```bash
.venv/bin/python scripts/consolidate_financial_database.py purge-sources \
  --db stock_analysis.db \
  --data-root /absolute/path/to/data-root
```

## 4. 验收门

数据库切换前必须同时满足：

- SQLite `quick_check` 通过；
- `(ts_code, fiscal_year, report_type)` 无重复；
- 未完成财年的年度记录不进入规范化读模型；
- 不存在资产负债不闭合且数量级超过一万倍的硬单位错误；
- 格力电器 `000651.SZ` FY2024 八项年报抽样一致：营业收入、归母净利润、经营现金流、总资产、总负债、归母权益、股本和全年DPS；
- `source_imports`、结构化 `source_*` 表与压缩源包齐备。

源数据自身存在的极端负净资产或资产负债不闭合记录不做猜测性修值。它们保留在源表，规范化记录标记为 `suspect_balance_sheet_identity` 或 `suspect_extreme_unit_ratio`，研究端应降级该年度或回到年报复核。

## 5. 2026-08-19 重建发现

旧库曾包含三类实质问题：

- A股 CSMAR 元值部分未除以一百万，造成同一行元/百万元混写；
- 港股 `fiscal_year` 曾误用月份值，产生财年 `1/2/3`；
- 港股DPS曾固定乘汇率，而其他报表字段保留本币，造成同一记录币种不一致。

这些问题不能靠在旧库上继续 UPSERT 修复，因此现行流程采用“新库重建—年报抽样—验证—原子切换”。
