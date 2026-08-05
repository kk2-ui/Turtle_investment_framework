# Turtle × Graham 完整迁移规划方案

> **版本**: v1.0 | **日期**: 2026-07-30 | **规划者**: Claude Opus | **执行者**: GPT  
> **目标**: 将 Turtle Investment Framework 的判断引擎按《价值投资：从格雷厄姆到巴菲特》重建，保留 GG 计算纪律  
> **粒度**: 具体到「改哪个文件的哪一节」，所有概念必须落到可计算的变量

---

## §I 迁移结论（先读这一节）

> **来源声明（2026-07-30 升级）**：§VI 全部公式与 §6.5 全部阈值已核校至原书原文（EPUB 文件 `0034–0058.xhtml`：第5章 EPV + 案例二麦格纳 0038、第8章回报率框架 0049–0058 + 案例四英特尔 0060），非 GPT 二手摘要。落地目标是复现原书两条估值流水线：**EPV/资产价值流水线（麦格纳式，无护城河）** 与 **回报率分解流水线（英特尔式，有护城河成长股）**。买点问题由"路由 + 回报率分解 + 安全边际阈值"闭环解决。

### 1.1 核心判断

**这是判断引擎的顺序重建，不是 Prompt 话术升级。**

现有框架的根本缺陷（已在 `docs/turtle_valuation_routing_and_investor_styles.md` 中明确指出）：

- **当前顺序（错误）**: `compute_gg → compute_ddm → assess_moat`
- **正确顺序**: 先路由 → 再选法 → 再计算

**含义**: GG 现在是"默认计算"，路由之后才应判断 GG 是否是合适的方法。对于 R1（困境/清算）、R2（实物资产）、R4（价值陷阱）路由，GG 要么不适用，要么只是次要校验。

### 1.2 保留什么

| 类别 | 保留内容 |
|------|---------|
| **GG 计算纪律** | 4层（reported/normalized/conservative/adjusted）、AA shareholder-level、11步精算 |
| **数据管线** | Phase1 数据采集、Phase2 PDF解析、所有 Tushare/CSMAR 字段 |
| **四因子骨架** | Factor1A/1B/1C/2/3/4 结构和 phase3.md 工作流不变 |
| **否决门系统** | Factor1A 6条 Kill Switch 不动，Factor4 IV 型止损不动 |
| **3视角裁决** | GG层 + DDM层 + Asset层 三视角统一裁决框架保留 |
| **仓位上限系统** | 护城河/陷阱 → position_cap 联动保留 |

### 1.3 改变什么

| 类别 | 改变内容 |
|------|---------|
| **计算触发顺序** | 硬编码 GG-first → 路由驱动条件计算 |
| **护城河作用升级** | 当前：影响 b_penalty；新增：影响 valuation_route（R3/R5分叉点） |
| **Factor4 的入口** | 从"直接计算"改为"先读路由，再分支" |
| **GG 的角色定位** | 从"必算"改为"R3/R5路由下主力，其他路由次要或不适用" |
| **新增 Factor1.5 因子** | 独立估值路由因子，产出 valuation_route（Q4 定案） |

### 1.4 MVP 边界

**Phase 1（最小可验证版本）**:
- 文件改动：`factor_interface.md`, `factor1_资产质量与商业模式.md`, `factor4_估值与安全边际.md`, `phase3_分析与报告.md`
- 核心交付：valuation_route 字段在 Factor1B 末尾输出，Factor4 开头读取并条件分支
- 不需要改 Python 代码（agent_loop.py 可选，Phase 5 再做）

---

## §II 对项目目标的理解

### 2.1 旧框架 vs 新框架：问的问题变了

| 旧框架问的问题 | 新框架问的问题 |
|--------------|--------------|
| "GG 是多少？" | "这家公司属于哪一类资产？" |
| "DDM 是否支持买入？" | "对这类公司用哪种估值方法才合理？" |
| "护城河评级是几级？" | "是否具备**经济特许权（franchise）**？" |
| "GG − M 折价多少？" | "回报率拆解 D/M + g 是多少？真实回报是多少？" |
| "Factor4 统一裁决" | "路由驱动的条件裁决（不同路由不同标准）" |

### 2.2 用户真正想要的（不是"书的所有概念都进框架"）

1. **先路由**：防止对 A 类公司用 B 类方法（当前最大风险）
2. **升级 R5 路由**：franchise 公司的回报率拆解（书 Ch8 核心）
3. **明确 GG 的角色边界**：在每个路由里 GG 是主力 / 辅助 / 不适用
4. **不做冗余**：资产法和收益法不并列计算，由路由决定用哪个为主

### 2.3 不做什么

- 不推倒 GG 计算引擎重写（GG 的严谨性是资产，保留）
- 不引入无法用现有数据计算的概念（见 §VIII 缺口清单）
- 不改数据采集层（Phase1/Phase2 不动）

---

## §III 框架现状理解（精确文件角色）

### 3.1 判断链条当前的物理位置

| 文件 | 角色 | 关键定位 |
|------|------|---------|
| `prompts/phase3_分析与报告.md` | 主工作流 | Step1→2(1A)→3(1B)→3.5(1C)→4(F2)→5(F3)→6(F4)→7(报告) 线性管线，**无路由** |
| `prompts/references/factor1_资产质量与商业模式.md` | Factor1 规格 | 1A 快筛（6条否决）+ 1B 深度定性（9模块）；模块三=护城河 |
| `prompts/references/factor1C_增量增长检验.md` | Factor1C 规格 | 增量增长检验（incremental growth check） |
| `prompts/references/factor2_穿透回报率粗算.md` | Factor2 规格 | Top-Down ROIC 粗算，OE = C + D − H |
| `prompts/references/factor3_穿透回报率精算.md` | Factor3 规格 | Bottom-Up ROIC 精算，11步，AA→GG |
| `prompts/references/factor4_估值与安全边际.md` | Factor4 规格 | DDM ladder + GG裁决 + 3视角裁决（现~1500行） |
| `strategies/turtle/references/factor_interface.md` | 因子间接口 | 定义 Factor1B→Agent C 传递的参数 schema |
| `templates/report_template_v12.md` | 报告模板 | COMPANY_FACET_CATALOG 标签 + Ch1-7定性 + Ch11-12量化 |
| `turtle_framework/scripts/turtle_agent/agent_loop.py` | V11 引擎 | `_build_system_prompt` 硬编码工具调用顺序（约240-280行） |
| `scripts/zone_j_agent.py` | Zone J 参数 | 管理量化裁决区参数 |

### 3.2 现状的致命问题

`phase3.md` 的 Step6（Factor4）直接进入 GG/DDM 计算，**没有任何"这家公司该不该用 GG"的前置判断**。护城河（模块三）虽然影响 b_penalty，但只在报告写作层起作用，不影响"选哪种估值方法"。

---

## §IV 结构设计：目标架构

### 4.1 目标判断链条

```
Factor1A 快筛（否决门，不变）
   ↓
Factor1B 深度定性（9模块，不变；模块三新增 franchise_type 判断）
   ↓
【新增因子】Factor1.5 估值路由  ← 本次核心插入点（独立因子，Q4 定案）
   ├─ 输入：Factor1B 的 moat_rating / trap_rating / franchise_type
   ├─ 输出 valuation_route (R1-R6)
   └─ 输出 route_reasoning
   ↓
Factor1C / Factor2 / Factor3（ROIC 计算，基本不变，Factor1C 增强 incremental_roic + growth_verdict）
   ↓
Factor4 §0 读路由 → 条件分支：
   ├─ R1 → 清算价值法（GG 不适用）
   ├─ R2 → 重置成本法（GG 辅助）
   ├─ R3 → EPV + GG 主力（现有 DDM ladder 全套）
   ├─ R4 → 资产底 + 增长归零（GG 需惩罚）
   ├─ R5 → 回报率拆解 D/M+g（GG 交叉校验）
   └─ R6 → SOTP/PMV（GG 分部适用）
   ↓
3视角统一裁决（保留）→ 报告（保留）
```

### 4.2 六路由决策树（写入新因子 Factor1.5）

| 路由 | 触发条件 | 主方法 | GG 角色 |
|------|---------|--------|---------|
| **R1 困境/清算** | 持续亏损 + 净现金<0 + 资不抵债风险 | 清算价值（NCAV/变现资产） | 不适用 |
| **R2 实物资产无franchise** | 重资产 + ROIC≈WACC + 无定价权 | 重置成本 | 辅助校验 |
| **R3 稳定低增长** | 盈利稳定 + 弱护城河 + g<5% | EPV + GG 主力 | **主力** |
| **R4 竞争性增长/价值陷阱** | 增长但 ROIC≤WACC 或陷阱高 | 资产底，增长按0计 | 需惩罚 |
| **R5 经济特许权** | franchise=true + ROIC>WACC 持续 | 回报率拆解 D/M+g×(V/M) | 交叉校验 |
| **R6 特殊/催化剂** | 分拆/重组/多业务 | SOTP/PMV | 分部适用 |

### 4.3 路由与现有系统的映射关系

- **路由不替代护城河评级**：护城河（模块三）→ 判断 franchise_type → 影响 R3 vs R5 分叉
- **路由不替代陷阱评级**：陷阱评级 → 触发 R4 的关键输入
- **路由不替代 position_cap**：position_cap 仍由护城河/陷阱决定（§V 保留联动）

---

## §V 变量字典

### 5.1 现有沿用（不改语义）

| 变量 | 含义 | 产出位置 |
|------|------|---------|
| `AA` | shareholder-level 穿透利润锚 | Factor3 |
| `GG` | AA × (1+λ)^n / r 的估值 | Factor3/Factor4 |
| `II` | 内在价值区间 | Factor4 |
| `R` | 折现率 / 要求回报率 r* | Factor2/4 |
| `Q` `M` `O` | 数量/市值/其他锚点 | Factor2/4 |
| `lambda` (λ) | 增长率参数 | Factor3 |
| `moat_rating` | 护城河评级（优质/中性/负面） | Factor1B 模块三 |
| `trap_rating` | 价值陷阱评级（高/中/低） | Factor1B |
| `position_cap` | 仓位上限 | Factor1B 绑定规则 |

### 5.2 重定义（保留名称，明确边界）

| 变量 | 旧含义 | 新含义 |
|------|--------|--------|
| `GG` | "默认估值输出" | "R3/R5 路由下的主/辅估值，其他路由不作为主输出" |
| `moat_rating` | 影响 b_penalty | **额外**驱动 franchise_type 判断（优质→检验是否够 franchise） |

### 5.3 新增变量（本次迁移核心）

| 变量 | 类型 | 含义 | 产出位置 | 传递到 |
|------|------|------|---------|--------|
| `valuation_route` | enum R1-R6 | 估值路由 | **Factor1.5**（新因子） | Factor4 §0 |
| `route_reasoning` | text | 路由判断理由 | **Factor1.5** | 报告 |
| `franchise_type` | enum(none/weak/strong) | 经济特许权类型 | Factor1B 模块三 | Factor1.5 / Factor4 R5 |
| `growth_verdict` | enum(value_creating/neutral/value_destroying) | 增长是否创造价值 | Factor1C | Factor4 |
| `incremental_roic` | pct | 增量投入资本回报率 | Factor1C | Factor4/vcf |
| `vcf` | ratio | 价值创造因子 = incremental_roic / r* | Factor1C | Factor4 |
| `decay_rate` | pct | 年衰减率 ≈ 72/half_life | Factor4 | 安全边际 |
| `half_life` | years | 竞争优势半衰期 | Factor1B/4 | decay_rate |
| `r_b` | pct | 基础回报率 = D/M + g | Factor4 R5 | 真实回报 |
| `true_return` | pct | 真实回报 = D/M + g×(V/M) | Factor4 R5 | 安全边际 |
| `china_trap_adjustments` | list | 中国市场陷阱调整项 | Factor1B/4 | 报告 |
| `kill_switches` | list | 触发的否决条件 | 各因子 | 裁决 |

### 5.4 删除/弱化

- **无删除**：所有旧变量保留，保证向后兼容与历史报告可复现

---

## §VI 公式层

### 6.1 新增公式（原文 Ch5/Ch8 核心 · 已按原书校订）

> 来源全部核对至原书章节（文件 `0034–0058.xhtml`），非二手摘要。r* = 资本成本，V = 内在价值，M = 市值，D = 总现金回报，d = 每股股息，g = 盈利增长率。

| 公式 | 定义 | 用途 | 原文出处 |
|------|------|------|------|
| `EPV = 可持续盈利 / r*` | 盈利能力价值（零增长） | R3 基准值 | Ch5「盈利能力价值与资本成本估计」0036 |
| `r_b = D/M + g` | 基准回报率 = 现金回报率 + 增长率（假设 V=M） | R5 回报拆解起点 | Ch8「回报率计算公式」0053 |
| `r = D/M + g×(V/M)` | 真实回报（内价/市值比加权增长），公式3 | R5 真实回报 | Ch8「假设市值等于内在价值的影响」0054 |
| `r − r_b = g×(V/M − 1)` | 真实回报与基准回报之差（公式6） | 低估→r>r_b 证明 | Ch8 0054 |
| `V/M ≈ r_b / r*` | 内价/市值比 ≈ 基准回报/资本成本 | 消除 V/M 不可测 | Ch8 附录 0058 / 0054 脚注 |
| `r_b2 = D/M + g×(r_b/r*)` | 二次迭代精修基准回报（可继续迭代，边际递减） | R5 精修 | Ch8 0054 脚注 |
| `safety_margin_R5 = r_b − r* − decay_rate` | R5 净安全边际（衰减不含在 g 内时） | R5 裁决 | Ch8「经济特许权衰减」0052 |
| `decay_rate ≈ 72 / half_life` | 72法则：半衰期→年衰减率 | 衰减折价 | Ch8 0052 |
| `vcf = 增量投资创造价值 / 增量投资额` | 价值创造因子（=增量ROIC/r*，>1 才创造价值） | 增长门控 | Ch8「估计成长股的回报率」0050 |
| `积极投资回报 = 留存可积极投资额 × vcf / M` | 三段回报第③部分 | R5 回报拆解 | Ch8 0050 |
| `V2 = b·V1 / [1−(1−b)·V1]` | 二次再投资 VCF（b=派息比例，情形2） | VCF 保守性说明 | Ch8「价值创造因子」0056 脚注 |

**R5 三段回报分解（英特尔/联合通用主线，原文 Ch8 0050）**：
```
总回报 = ① 现金回报率 D/M
       + ② 有机增长回报（组织增长 g_organic，经 V/M 修正）
       + ③ 积极投资回报（留存收益 × vcf / M）
再减：  − decay_rate（经济特许权衰减，若未含在 g 内）
判据：  总回报 − r* ≥ decay_rate  → 通过（有安全边际）
```

### 6.2 保留公式（不动）

- `GG = AA × (1+λ)^n / r` — Factor3 原始公式，纪律不变
- DDM ladder（Factor4 §II-IV）— DPS CAGR 三档、Terminal Value、买入价阶梯
- OE = C + D − H（Factor2 粗算）
- S-T-U 现金收入还原（Factor3 精算 Step1）

### 6.3 重写公式（语义升级）

| 公式 | 旧逻辑 | 新逻辑 |
|------|--------|--------|
| 安全边际 | 只算 GG − M 折价 | R3 用折价法；R5 用回报差 `true_return − r* − s` |
| 增长贡献 | 直接把 g 计入价值 | **先过 vcf>1 门控**，vcf≤1 时 g 归零（R4） |

### 6.4 公式冲突点（GPT 执行时必须注意）

1. **EPV ≠ GG**：书的 EPV = 规范化盈利/r*（无增长），GG = AA×(1+λ)^n/r（含增长）。R3 路由下两者都要给，但 EPV 是"零增长底"，GG 是"含增长值"，不可混用。
2. **franchise_type=strong ≠ moat_rating=优质**：franchise 要求 ROIC>WACC **持续可验证**，标准比护城河评级更严。moat=优质 只是 franchise 的必要非充分条件。
3. **decay_rate 与 λ 的关系**：λ 是名义增长率，decay_rate 是竞争优势衰减，两者在 R5 下需同时作用（net_growth 公式）。

### 6.5 硬阈值表（原文给出的可落库数字规则 · 摘要版全缺）

> 以下阈值全部来自原书，是让报告"可执行"而非"概念化"的关键。GPT 落地时应把这些做成常量/查表，而非自由裁量。

**(A) 安全边际下限**（Ch8 0052）
- 格雷厄姆-多德对特许权成长股要求 **最低 3%–4%** 净安全边际，用于覆盖计算误差 + 意外事件。

**(B) 半衰期 → 衰减率查表**（Ch8 0052，72法则）

| 半衰期(年) | 年衰减率 | 定性 | 典型公司 |
|------|------|------|------|
| 80 | 0.9% | 可忽略 | 可口可乐 |
| 50 | 1.5% | 3–4% 边际可覆盖 | 高度稳定环境 |
| 40 | 1.8% | 长期持有可接受 | — |
| 25 | ≈3% | **值得严肃对待** | — |
| 20 | 3.6% | 吃掉整个安全边际 | 成熟科技（英特尔/苹果 15–20年档） |
| 18 | 4% | 严重 | — |

判据：**半衰期 ≤ 25 年 → 衰减率 ≥ 3% → 必须显式扣减，不可忽略**。

**(C) VCF 经验规则**（Ch8 0056，无逐笔并购数据时的兜底）

| 情形 | VCF 取值 | 规则 |
|------|------|------|
| 派息 > 75% | 不必精算 | 大体判断即可（VCF±0.25 对回报影响 <0.4%） |
| 留存 ≥ 1/3 且主要靠有机增长 | ≈ 0 | 除非有明确资本配置改善证据 |
| 持有现金 / 偿还债务 | ≈ 0.8 | 税务拖累（利息被税、税盾降低） |
| 最坏：破坏价值的投资 | < 0.5 | — |
| 效率提升投资（回收期 6–24 月） | 5+ | 税前年回报 50%–200%，但占资本预算比例小 |
| 非特许权范围内的扩张/收购 | ≤ 1 | 竞争性市场金融投资 VCF=1，双重征税 <1 |
| 特许权内扩张（地理/产品维度） | > 1 | 仅此类 + 效率投资 VCF 才 >1 |

**(D) 资本成本 r* 定性分档**（Ch5 0036）

| 风险档 | 股权成本 | 典型行业 |
|------|------|------|
| 低风险 | 6%–8%（≈7%） | 公用事业、稳定非耐用消费品（可口可乐） |
| 中风险 | 8%–10%（≈9%） | 一般非金融服务（UPS） |
| 高风险 | 11%–13%（≈12%） | 周期工业、大宗商品 |
| 股权成本下限 | 6% | = 投资级债(BAA+)收益率 5% + 1% |
| 风险资本上限 | 13%–14% | VC 融资成本（历史 18%–20%） |

- **债务比例保守上限 ≈ 30%**：实际杠杆超 30% 时，用 30% 而非真实比例算 WACC（避免低估高杠杆企业真实资本成本）。
- CAPM/β 法：原文明确"区间太宽无实用价值"，**优先用上表定性分档**。

**(E) 增长合理性检验**（Ch8 0051 / 0057）
- 长期 g > 15%，或长期显著超过名义 GDP（3%–4%）→ **不现实，拒绝**（否则该公司将占据整个经济）。
- 快速增长期无法永续，迟早回落到"名义 GDP + 几个百分点"。

**(F) 卖点原则**（Ch8 0057，回报率法只解决买点）
- 回报率法**不解决卖点**（无内在价值可比）。卖点用武断规则：巴菲特"永不卖" / 可持续盈利 25 倍 PE 上限。

---

## §VII Prompt 层改造计划（具体到文件与节）

> **改造总顺序**（依赖关系）：先接口 → 再产出端(Factor1B) → 再消费端(Factor4) → 再工作流(phase3) → 再增强(Factor1C) → 最后报告模板 → 可选 Python。

### 文件 1: `strategies/turtle/references/factor_interface.md`

- **改哪一节**：`Factor1B → Agent C` 参数传递表（量化 + 定性参数区）
- **操作**：在现有参数列表末尾**新增字段定义**（不删旧字段）
- **新增字段**：
  ```
  valuation_route: enum(R1|R2|R3|R4|R5|R6)   # 估值路由
  route_reasoning: string                     # 路由理由（≤200字）
  franchise_type: enum(none|weak|strong)      # 经济特许权类型
  growth_verdict: enum(value_creating|neutral|value_destroying)
  incremental_roic: float (pct)               # 增量ROIC
  vcf: float                                  # 价值创造因子
  half_life: float (years, 可空)              # 竞争优势半衰期
  china_trap_adjustments: list<string>        # 中国市场陷阱调整
  ```
- **验收**：接口表能明确列出 8 个新字段的类型、取值域、是否可空。

### 文件 2: `prompts/references/factor1_资产质量与商业模式.md`

> Q4 定案：路由判断**不再**放这里，迁移到新文件 Factor1.5（见文件 2b）。本文件只保留 franchise 判断与 binding rule。

- **改动 A — 模块三（护城河）增加 franchise_type 判断**
  - 在护城河评级后新增一步：若 moat=优质，进一步检验 franchise 三条件（定价权/ROIC>WACC持续/进入壁垒），全中→strong，部分→weak，否则→none
  - 输出：`franchise_type`（传给 Factor1.5 做路由分叉）
- **改动 B — 保留 binding rule**：护城河/陷阱 → position_cap 联动规则原样保留，不动
- **验收**：Factor1B 输出包含 franchise_type + 三条件检验结果。

### 文件 2b（新建 · Q4 定案）: `prompts/references/factor1.5_估值路由.md`

- **操作**：新建独立路由因子文件
- **输入**：Factor1B 的 `moat_rating` / `trap_rating` / `franchise_type` + Factor1A 财务基本面
- **内容**：R1-R6 决策树（照抄 §IV.2 表格触发条件）
  - 决策顺序：先查 R1（困境）→ R6（特殊）→ R4（陷阱）→ R2（实物无franchise）→ R5（franchise）→ R3（兜底稳定）
- **输出**：`valuation_route` + `route_reasoning` + `half_life`（R5 路由时必估）+ `decay_rate`（由 §6.5-B 查表得出）
- **R5 附加产出**：命中 R5 时，须同时输出半衰期估计 → 经 72 法则得 decay_rate。半衰期 ≤ 25 年（decay ≥ 3%）须在 route_reasoning 里显式标注"衰减吃边际"警示（原文 Ch8 0052）
- **增长合理性前置**：路由前先跑 §6.5-E 检验——若声称长期 g>15% 或远超名义 GDP，强制降级（不得进 R5，转 R4/R3）
- **兜底**：判断不出时默认 R3 + 告警（对齐 §VIII.3 规则4）
- **验收**：给定测试股票，Factor1.5 输出唯一 valuation_route + 理由；R5 路由必带 half_life 与 decay_rate。

### 文件 3: `prompts/references/factor4_估值与安全边际.md`

- **改动 A — 开头新增 §0 路由条件读取节**
  - 内容：读取 Factor1.5 的 `valuation_route`，按路由跳转到对应计算节
  - 规则：**若 valuation_route 缺失 → 报错并默认走 R3（保守）+ 标注 ⚠️**
- **改动 B — 现有 §III 改名并加路由前置**
  - 现有"GG Terminal Value / Required Return"节 → 更名 `§III [R3路由] EPV基准 + GG主力`
  - 前置条件：`if valuation_route == R3`
  - Q1 定案：**并列给两个 EPV** —— `EPV_AA = AA/r*` 和 `EPV_norm = normalized_earnings/r*`，与 GG 三者并列展示，并解释口径差
- **改动 C — 新增 §III-R5 节：经济特许权回报率拆解**（原文英特尔/联合通用主线 Ch8 0050–0054）
  - 前置：`if valuation_route == R5`
  - **三段回报分解**（按 §6.1 顺序，逐段可审计）：
    1. 现金回报率 = `D/M`（可持续盈利 × 派息率 ÷ 市值）
    2. 有机增长回报 = `g_organic`（先按 V=M，后经 V/M 修正）
    3. 积极投资回报 = `留存可积极投资额 × vcf / M`（vcf 取 Factor1C 实测或 §6.5-C 兜底）
  - **基准 → 迭代 → 安全边际**：
    - `r_b = D/M + g`（g = 有机 + 积极对应增长 − decay_rate）
    - 一次迭代 `V/M = r_b/r*` → `r_b2 = D/M + g×(r_b/r*)`（原文 0054 脚注；实务一次迭代即足够）
    - `safety_margin = r_b − r* − decay_rate`
  - **裁决**：`safety_margin ≥ 3%–4%`（§6.5-A）→ 通过；半衰期 ≤25年时须确认边际能盖住 decay（§6.5-B）
  - GG 在此节退为"交叉校验"，不作主输出
- **改动 D — 新增 §III-R4 节：价值陷阱/增长归零**
  - 前置：`if valuation_route == R4`
  - 规则：g 归零（除非 vcf>1），以资产底为主，GG 打惩罚系数
- **改动 E — 新增 §III-R1/R2 节：清算/重置成本**（原文麦格纳主线 Ch5 0038）
  - R1：NCAV / 变现资产法，GG 不计
  - R2：重置成本估算 = 净资产账面值 + 逐项再生产价值调整（固定资产按剩余寿命×年降价率；无形资产三类分算：客户名录=可持续收入×7.5%、员工=分档获取成本、产品组合=研发投入×周期年数）；数据不足 → 标 ⚠️（见 §VIII 缺口）
  - **三值交叉验证**（原文麦格纳精髓）：AV≈EPV 且无护城河 → 情形 B（能干管理层、成长不创造价值）；AV>>EPV → 情形 A（管理层破坏价值）。安全边际以"企业价值 ÷ 内在价值"表达（麦格纳仅 5%）
- **改动 F — §III-E 三视角裁决保留**，增加"按路由加权"说明
  - Q3 定案：R5 下 GG 视角**保留但降权**（默认 ~20%），主权重给回报拆解；三视角框架不删
- **验收**：6 条路由各有独立计算节，Factor4 §0 能正确分派。

### 文件 4: `prompts/phase3_分析与报告.md`

- **改动 A — Step 3（Factor1B）末尾**
  - 新增指令："输出 franchise_type + 三条件检验结果，传给 Factor1.5"
  - 字段校验：franchise_type 必填
- **改动 B — 新增 Step 3.3（Factor1.5 估值路由）**（Q4 定案：Factor1B 与 Factor1C 之间插入）
  - 新增指令："调用 factor1.5_估值路由，读入 moat/trap/franchise_type，产出 valuation_route + route_reasoning"
  - 字段校验：valuation_route 必填，缺失阻断进入后续步骤（兜底 R3+告警）
  - **后续步骤编号顺延**：原 Step 3.5→3.6，原 Step 4→保持逻辑但确认编号，全文步骤引用同步更新
- **改动 C — Step 3.5/3.6（Factor1C）**
  - 新增指令："计算 incremental_roic 和 vcf，产出 growth_verdict（vcf>1→value_creating；≈1→neutral；<1→value_destroying）"
- **改动 D — Step 6（Factor4）开头**
  - 新增指令："进入 Factor4 前先读 valuation_route，按 factor4 §0 分派到对应路由计算节，禁止无条件 compute_gg"
- **改动 E — 修正硬编码顺序描述**
  - 若文中有"compute_gg → compute_ddm → assess_moat"字样 → 改为"route → select_method → compute"
- **验收**：工作流出现 Step 3.3 路由步骤，Step 6 入口要求先读路由，步骤编号无断层。

### 文件 5: `prompts/references/factor1C_增量增长检验.md`

- **改哪一节**：增量增长检验主计算节
- **操作**：升级 incremental_roic 计算，新增 vcf 与 growth_verdict 产出
  - `incremental_roic = ΔNOPAT / Δ投入资本`（增量口径，非存量 ROIC）
  - `vcf = incremental_roic / r*`
  - `growth_verdict` 三档判定（同 §VI.1）
- **数据不足时的兜底**（原文 Ch8 0056，散户拿不到分部级并购数据时必用）：
  - 派息 > 75% → 不精算 VCF，取 1（影响 <0.4%）
  - 留存 ≥ 1/3 且主要靠有机增长 → VCF ≈ 0（除非有资本配置改善证据）
  - 完整兜底查表见 §6.5-C
- **注意**：Factor1C 的 growth_verdict 是 Factor4 R4/R5 增长门控的关键输入
- **验收**：Factor1C 输出 incremental_roic + vcf + growth_verdict 三字段；无实测数据时能引用 §6.5-C 规则并注明来源。

### 文件 6: `templates/report_template_v12.md`

- **改动 A — Ch3（护城河章）**
  - 新增输出字段：franchise_type + franchise 三条件检验结果
- **改动 B — Ch11-12（量化/估值章）**
  - 新增：valuation_route + route_reasoning 显示
  - 按路由条件显示对应估值结果（R5 显示 r_b/true_return；R3 显示 EPV/GG）
  - **买点结论块**（对齐第二个核心诉求"买点问题"）：显式给出
    - R5：`r_b` / `r*` / `decay_rate` / `safety_margin` 四值 + 通过判定（≥3–4%）
    - R1/R2/R3：内在价值（AV 或 EPV）/ 市值 / 折价率 + 买入价阶梯
    - 增长合理性检验结果（§6.5-E 是否触发降级）
    - 半衰期→衰减率（§6.5-B）与"衰减是否吃掉边际"警示
- **改动 C — COMPANY_FACET_CATALOG**
  - 可选：将现有 60+ 商业模式标签与 R1-R6 路由建立映射提示（辅助路由判断，非强制）
- **验收**：报告能展示路由 + 对应路由的估值口径。

### 文件 7（可选，Phase 5）: `turtle_framework/scripts/turtle_agent/agent_loop.py`

- **改哪一节**：`_build_system_prompt` 方法（约 240-280 行）的工具调用顺序描述
- **操作**：将系统提示中"compute_gg → compute_ddm → assess_moat"的顺序，改为"assess_moat/route → 条件 compute"
- **注意**：这是 V11 single-agent 引擎；若实际执行走 phase3.md 工作流，则本文件为文档一致性修正，非功能阻断项
- **验收**：system prompt 不再无条件把 compute_gg 放在最前。

---

## §VIII 风险与缺口

### 8.1 不能直接迁移的概念（4个）

| 书中概念 | 为何不能直接映射 | 处理方案 |
|---------|----------------|---------|
| **经济特许权 franchise** | ≠ moat_rating=优质，标准更严（需 ROIC>WACC 持续可验证） | 新建 franchise_type 三条件检验（文件2 改动B） |
| **EPV（盈利能力价值）** | ≠ GG。EPV=规范化盈利/r*（零增长）；GG=含增长 | R3 路由下两者并列，EPV 作"零增长底" |
| **资产重置成本** | 现有框架完全缺失，财报无重置成本数据 | R2 路由：能估则估，数据不足标 ⚠️（见 8.2） |
| **回报率拆解 r_b=D/M+g** | 现有 GG 体系无此拆解 | R5 路由新建（文件3 改动C），用现有 D/M/g 组装 |

### 8.2 数据缺口

> 读原文后确认：原书那种深度依赖三类散户拿不到的颗粒度数据。这不是框架缺陷，而是数据可得性的硬边界——必须诚实标注，不可编造。

| 缺口 | 原文如何拿到（我们拿不到的部分） | 影响路由 | 缓解 |
|------|------|---------|------|
| **资产重置成本**（麦格纳式） | 原文打电话问当地评估师、查设备年降价率 4.7%、逐项算无形资产三类 | R2 | 港股/A股拿不到评估师颗粒度 → 标 ⚠️，退回账面净资产 + 说明；能估的科目（土地/设备年降）尽量估 |
| **VCF 实测**（英特尔式） | 原文靠逐笔并购收购后财报回溯（McAfee 0.20/Altera 0.40/Mobileye 7%） | Factor1C / R5 第③段 | 分部级并购数据够不到 → 用 §6.5-C 经验规则兜底，注明"规则估算" |
| **可持续利润率 / half_life** | 原文用 10 年经营史 + 定性行业判断 | R3 EPV / decay_rate | 港股披露参差 → 给区间估计（乐观/中性/悲观），非点值 |
| 增量 CAPEX vs 维持 CAPEX 不分 | 原文按"收入微降年份 CAPEX≈维持性"倒推真折旧 | Factor1C incremental_roic | 用 ΔNOPAT/Δ投入资本近似，标注口径 |
| 规范化 EBIT 需单独算 | — | R3 EPV | 用现有 normalized 层数据推导 |

### 8.3 逻辑冲突（执行时需保持一致）

1. **护城河 → b_penalty 链条必须保留**：新增 franchise_type 不能破坏现有 moat→b_penalty→Zone J 链条。
2. **R5 下 GG 降级**：GG 从主输出变交叉校验，但 3视角裁决框架仍需 GG 层——保留但降权，不删。
3. **"听起来对 ≠ 可计算"**：所有新字段（尤其 r_b/true_return/vcf）必须能用现有数据算出，否则标 ⚠️ 而非编造。
4. **路由缺失的兜底**：valuation_route 缺失时默认 R3 + 告警，绝不静默跳过路由。

---

## §IX 分阶段实施步骤

### Phase 1 — 路由层（最高优先级）

| 步骤 | 文件 | 改哪节 | 验收标准 |
|------|------|--------|---------|
| 1.1 | `factor_interface.md` | Factor1B→Agent C 参数表 | 8 个新字段有定义 |
| 1.2 | `factor1_资产质量与商业模式.md` | 模块三 franchise 判断 + 保留 binding rule | 输出 franchise_type |
| 1.3 | **新建** `factor1.5_估值路由.md` | R1-R6 决策树（Q4 定案） | 输出唯一 valuation_route |
| 1.4 | `factor4_估值与安全边际.md` | 新增 §0 路由读取 + 拆分 R1-R6 节 | Factor4 按路由分派 |
| 1.5 | `phase3_分析与报告.md` | 新增 Step 3.3 + 编号顺延 + Step6 入口 | 工作流出现路由步骤 |

**Phase 1 端到端验收**：跑一只测试股票（如 00506），报告能输出 valuation_route 且 Factor4 走对应路由，不再无条件 compute_gg。

### Phase 2 — 增长门控与 R5 拆解

| 步骤 | 文件 | 改哪节 | 验收标准 |
|------|------|--------|---------|
| 2.1 | `factor1C_增量增长检验.md` | 主计算节 | 输出 incremental_roic + vcf + growth_verdict |
| 2.2 | `factor4_估值与安全边际.md` | §III-R5 节 | R5 股票输出 r_b + true_return |
| 2.3 | `factor4_估值与安全边际.md` | §III-R4 节 | R4 股票 g 归零 + 资产底 |

**Phase 2 验收**：franchise 股票走 R5 输出三段回报拆解（D/M + 有机 + 积极）+ `r_b2` 迭代值；ROIC≤WACC 股票走 R4 增长归零；VCF 无实测时能引用 §6.5-C。

### Phase 3 — 衰减与资产法

| 步骤 | 文件 | 改哪节 | 验收标准 |
|------|------|--------|---------|
| 3.1 | `factor4_估值与安全边际.md` | §III-R5 衰减 | decay_rate 由 §6.5-B 查表得出；half_life ≤25 年触发"吃边际"警示 |
| 3.2 | `factor4_估值与安全边际.md` | §III-R1/R2 节 | R1 清算法 / R2 重置成本三类无形资产分算（或 ⚠️）+ 三值交叉验证情形 A/B |

**Phase 3 验收**：R5 安全边际 = `r_b − r* − decay_rate` 且判定 ≥3–4%（§6.5-A）；R1/R2 有独立资产法输出并给出内价/市值折价率。

### Phase 4 — 报告模板与风格（可后置）

| 步骤 | 文件 | 改哪节 | 验收标准 |
|------|------|--------|---------|
| 4.1 | `report_template_v12.md` | Ch3 + Ch11-12 | 报告展示路由 + 对应估值 |
| 4.2 | `report_template_v12.md` | COMPANY_FACET_CATALOG | 标签→路由映射提示（可选） |

### Phase 5 — Python 一致性（可选）

| 步骤 | 文件 | 改哪节 | 验收标准 |
|------|------|--------|---------|
| 5.1 | `agent_loop.py` | `_build_system_prompt` ~240-280 | 顺序改为 route-first |

---

## §X 决策点（已定案 · 2026-07-30）

> 以下 5 项已由用户拍板，GPT 执行时按"定案"办，无需再问。

### Q1 — EPV 计算口径 → **两者都算并列**

R3 路由同时给出两个 EPV 并在报告中并列展示：
- `EPV_AA = AA / r*`（复用 shareholder-level 锚点）
- `EPV_norm = normalized_earnings / r*`（书标准口径，需规范化 EBIT）
- 两者差异需在报告中解释（口径差 = 规范化调整的影响）。

### Q2 — R2 资产重置成本 → **能估则估，否则标 ⚠️**

- 能从现有数据估算（固资原值 + 土地 + 存货重置等）→ 给估算值并标注口径与假设
- 数据不足以估算 → 标 ⚠️「重置成本不可用」并退回账面净资产 + 说明
- 逐案判断，禁止用无依据的系数硬凑。

### Q3 — R5 下 GG 角色 → **保留但降权**

- GG 保留在 3视角统一裁决中，但权重下调（默认 ~20%，主权重给回报拆解 D/M+g）
- 保持 GG层 + DDM层 + Asset层 三视角框架完整，不删 GG 视角。

### Q4 — 路由位置 → **新建 Factor1.5 独立路由因子**（⚠️ 改变原方案结构）

- 新建文件 `prompts/references/factor1.5_估值路由.md`（不再嵌入 Factor1B §V）
- `phase3_分析与报告.md` 在 Step 3（Factor1B）后、Step 3.5（Factor1C）前插入 **新 Step 3.3（Factor1.5 路由）**，后续步骤编号顺延
- Factor1.5 消费 Factor1B 的 moat_rating/trap_rating/franchise_type，产出 valuation_route + route_reasoning 给 Factor4
- **注意**：这使 §VII 文件2 的"改动A（Factor1B §V）"迁移到新文件 Factor1.5；文件2 只保留"改动B franchise_type 判断"和"改动C binding rule 保留"。

### Q5 — 本轮范围 → **Phase 1-5 全做**

- Phase 1-3（判断引擎核心）+ Phase 4（报告模板 + 风格 S1-S11）+ Phase 5（agent_loop.py 顺序修正）全部纳入本轮
- 按 §IX 顺序推进，每 Phase 完成后自检验收。

---

> **执行提示给 GPT**：按 §IX 的 Phase 顺序执行；每个 Phase 完成后用 §IX 的验收标准自检；遇到 §VIII 的数据缺口时按 §X 的建议处理或回问用户；所有新字段务必"可计算或标 ⚠️"，禁止编造数值。
