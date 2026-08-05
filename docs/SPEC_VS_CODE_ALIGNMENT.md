# V12 代码 vs v0.15 参考 Spec — 公式对齐分析

> **对比基准**：Turtle Framework v0.15 Phase 3 | **最终更新**：2026-07-17
> **最终状态**：Spec v0.15 全部 30+ Step 完整覆盖 ✅。三数据源（CSMAR A股 + CSMAR HK + Tushare HK），DB 159K 行 × 200+ 列。

## 修复历程

| 版本 | 日期 | 内容 |
|------|------|------|
| **V12.5-V12.12** | 07-16~17 | 公式对齐+W半逐项+EV双轨+三数据源 (见V12_MANUAL) |
| **V12.13** | 07-18 | 报告压缩(全局去重, 20-30% size reduction) + 写作密度规则(跨章引用/禁冗余句式) |
| **V12.14** | 07-18 | A股CSMAR单位修正(元→百万, 1.8M cells) + 同行匹配修复 |
| **V12.17** | 07-18 | web_search + web_fetch (DuckDuckGo, 免费无API key) — 补充行业新闻/竞争动态 |

## Spec 覆盖状态

| Spec 章节 | 步骤数 | 状态 | 覆盖方式 |
|----------|--------|------|---------|
| Module 0(8) 参数预提取 | 8 | ✅ 全部覆盖 | M_signal, EV双轨, 现金保护层, G系数, 派息可持续 |
| Factor 2 粗算GG | 8 + Gate | ✅ 全部覆盖 | 穿透R(NP), 融资CF否决, 可预测性P; 1项Zone B(上游障碍) |
| Factor 3 精算GG | 11 | ✅ 全部覆盖 | 7项程序化 + 3项Zone B(AR核查/准则差异/现金储备) + 1项CSMAR数据 |
| Factor 4 估值 | 4 + 3扩展 | ✅ 全部覆盖 | II子类, 价值陷阱, 动态仓位, P_base, DDM年化, 三视角裁决 |

## 数据架构（V12.12）

| 数据源 | 市场 | 覆盖 | 导入脚本 |
|--------|------|------|---------|
| CSMAR A股面板 | A股 (SH/SZ) | 2000-2025, 265字段 | `import_csmar.py` |
| CSMAR HK | 港股 | 2005-2025, 利润表+BS+CF+披露指标 | `import_csmar_hk_full.py` |
| Tushare HK CSV | 港股 | 2005-2025, income/BS/CF | `rebuild_hk_data.py` |
| Tushare parquet | 港股 | EPS/DPS/股本/PE/PB | `import_hk_shares.py` |

数据流（简化）：
```
CSMAR/Tushare → 直接 UPSERT → annual_financials (162K行, 124MB) → compute_bundle.py
```
> ⚠️ observations/curation 管线已废弃并清空（从 12.7GB 减至 124MB）。

## 附录：compute_bundle.py 快速查阅

| 想知道什么 | 去哪里看 |
|-----------|---------|
| GG 最终值 | `compute_bundle.py` Factor 3 L730-770 |
| AA 逐年序列 | `compute_bundle.py` L555-641 |
| M 系数 + M_signal | `compute_bundle.py` L436-480 |
| 否决门 | `compute_bundle.py` L496-508 |
| DDM 公允价 + P_base | `compute_bundle.py` L850-874, L1185-1210 |
| 价值陷阱 + 动态仓位 | `compute_bundle.py` L881-912, L1184-1212 |
| EV 双轨 + λ 敏感性 | `compute_bundle.py` L1000-1050 |
| 外推可信度 | `compute_bundle.py` L940-970 |
| II 门槛 | `turtle_thresholds.py` L33-172 |
| 周期分类 | `pre_analysis_phase.py` L378-490 |
