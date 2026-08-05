# 因子1.5：估值路由（R1–R6）

> **Phase 4 产出 · Q4 定案新建的独立因子**。整个"路由→选法→计算"重构的枢纽。
> 位置：`phase3_分析与报告.md` 在 Step 3（Factor1B）后、原 Factor1C 前，插入**新 Step 3.3（Factor1.5）**，后续编号顺延。
> 上游：Factor1B（moat_rating / trap_rating / franchise_type）、Phase 2 EPV、Phase 3 AV。下游：Factor4（valuation_route + route_reasoning 决定用哪条估值法）。
> 母版 `_executor_template.md`；路线图 `docs/turtle_graham_deepening_roadmap.md`。
> **全局原则**：输入缺失给近似判断 + ⚠️，绝不"无法路由"。路由必须落到一条 R。

---

## 定位与指令

> **定位**：在计算估值**之前**先判断"这只股票该用哪种估值法"。Greenwald 的核心方法论——不同生意用不同价值锚（资产/EPV/成长），选错锚 = 估值全错。本因子只做**分流**，不算数值。
> **上游依赖**：Factor1B（护城河/陷阱/特许经营类型）、Phase 2（EPV_op、EPV/市值）、Phase 3（AV_going、AV_liq、EPV/AV 比）。
> **下游消费**：Factor4 按 valuation_route 选估值流水线；Factor_EPV / 资产价值 / factor3 各自被对应路由激活。

**指令**：路由由**两个信号**决定——① EPV/AV 比（客观勾稽）② Factor1B 定性评级（护城河/陷阱）。两者冲突时按边界规则裁决，不含糊。输出唯一路由 + 理由。

---

## 六路由定义（钉死）

| 路由 | 名称 | 触发 | 主估值法（下游执行器） |
|---|---|---|---|
| **R1** | 困境/清算 | distress/持续亏损/资不抵债风险 | 清算价值 NCAV（Phase 3 AV_liq） |
| **R2** | 实体资产无护城河 | 重资产 + EPV≈AV + 无franchise | 重置成本（Phase 3 AV_going） |
| **R3** | 稳定低增长 | 有盈利稳定性 + EPV≈AV + 弱增长 | EPV + GG（Phase 2 EPV 主 + factor3 GG 辅） |
| **R4** | 成长陷阱/毁灭价值 | ROIC≤WACC 或 EPV<AV 或 陷阱≥2项 | 资产地板，g=0（Phase 3 AV 打折 + EPV 封顶） |
| **R5** | 经济特许经营 | 有护城河 + EPV>AV + franchise确认 | 回报率分解 D/M+g（factor3 升级版，Phase 5） |
| **R6** | 特殊情形 | 分部差异大/控股/重组/周期极端 | SOTP 分部加总 |

---

## 关卡 ① 数据源逐行锚定（路由输入）

| 输入 | 来源 | 用途 |
|---|---|---|
| moat_rating | Factor1B | 护城河有无/强弱 |
| trap_rating | Factor1B | 价值陷阱特征计数 |
| franchise_type | Factor1B | 特许经营类型（成本/需求/网络/无） |
| EPV_vs_AV_ratio | Phase 3（EPV_op/AV） | 客观护城河信号（核心分流依据） |
| EPV/市值 | Phase 2 | 是否已透支增长 |
| AV_liq/市值 | Phase 3 | 清算保护强度 |
| ROIC vs WACC | Factor1B/1C + Phase1 r* | 增长是否创造价值 |
| 分部收入结构 | Factor1B/§3 附注 | 是否需 SOTP |

---

## 关卡 ①b 路由决策树（按序判断，先中先出）

```
Step A — R1 困境优先筛（一票进入）：
  若 资不抵债风险 或 持续亏损≥2年 或 现金流恶化警报（factor3）
     或 EPV_op≈0（正常化盈利≤0）
  → R1，主估值 = AV_liq（清算），结束

Step B — R6 特殊情形筛：
  若 分部间商业模式/盈利能力差异极大（单一法失真）
     或 控股结构复杂 或 正在重组/分拆
  → R6，主估值 = SOTP（对各分部分别路由再加总），结束

Step C — 核心分流（EPV/AV 比 × 定性评级）：
  读 EPV_vs_AV_ratio (= EPV_op / AV_going)：

  ├─ 比值 < 0.8（EPV < AV，毁灭价值）：
  │    → R4，主估值 = AV 打折 + g=0
  │    （管理层用高于回报的资本再投资，或行业衰退）
  │
  ├─ 比值 0.8–1.2（EPV ≈ AV，竞争均衡，无护城河）：
  │    再看盈利稳定性：
  │      稳定（收入CV<15% + 弱周期）→ R3（EPV+GG）
  │      不稳定/重资产为主          → R2（重置成本）
  │
  └─ 比值 > 1.2（EPV > AV，存在超额盈利）：
       必须与 Factor1B 交叉确认（见关卡③冲突处理）：
         moat_rating≥中 且 franchise_type≠无 → R5（回报率分解），特许经营价值=EPV−AV
         moat 判无 但 EPV>AV                 → 冲突！走③裁决（多半 R4 或存疑 R3）

Step D — 增长价值门槛（R5 二次确认）：
  进入 R5 后核 ROIC vs WACC：
    ROIC > WACC（增量正） → R5 成立，增长创造价值
    ROIC ≤ WACC          → 降级 R4（增长不创造价值，即使有护城河也不能给成长溢价）
```

---

## 关卡 ② 数据缺失降级阶梯

```
EPV_vs_AV_ratio 缺（Phase 2/3 未算全）：
  优先2：仅有 EPV → 用 EPV/市值 + moat_rating 定性路由（moat有→R5候选，无→R3）
  优先3：EPV/AV 都缺 → 纯靠 Factor1B：
         护城河强→R5；无护城河稳定→R3；重资产→R2；陷阱≥2→R4；亏损→R1
         标"⚠️ 路由基于定性评级，缺 EPV/AV 客观勾稽，可靠性中"

franchise_type 缺：
  用 moat_rating 代理（moat强≈有franchise），标 ⚠️

禁止：输出"无法路由"。信息再少也落到一条 R（最保守默认：不确定且有资产→R2；不确定且亏损→R1）。
```

---

## 关卡 ③ 边界情形（冲突裁决——本因子重心）

| 冲突 | 表现 | 强制裁决 |
|---|---|---|
| **EPV>AV 但 moat 判无** | 客观有超额盈利，定性没找到护城河 | 优先信客观：标"⚠️ 疑似隐性护城河，重审 Factor1B"（对齐 factor3 步骤11"因子3优于因子1预期"）；暂定 R3，若复核确认护城河升 R5 |
| **moat 判强 但 EPV<AV** | 定性说有护城河，客观在毁灭价值 | 优先信客观：降 R4，标"护城河存疑或正被侵蚀，或管理层错配资本" |
| **陷阱≥2 但 EPV>AV** | 有陷阱特征却超额盈利 | R4 优先（陷阱一票压制成长溢价），GG<II×1.5 则排除（对齐 phase3 S2） |
| **ROIC>WACC 但无护城河** | 高回报但不可持续 | R3 而非 R5（无护城河的高 ROIC 会被竞争抹平，不给永续成长价值） |
| **周期股当前亏损** | EPV 当期为负 | 不进 R1，用正常化 EPV（Phase1 E_norm 全周期），按正常化后比值路由 |
| **净现金>市值** | 类现金壳 | R6/R1 边缘，标资金占用风险，估值以 AV 为主 |

> **裁决总原则**：客观勾稽（EPV/AV）与定性（Factor1B）冲突时，**优先信客观数字 + 强制回标复核定性**，不让定性单方面推翻计算。

---

## 关卡 ④ 强制敏感性

```
路由稳健性检验（禁止单点路由）：
  EPV/AV 比用三档（Phase2/3 的 low/base/high 组合）：
    若三档落在同一路由区间 → 路由稳健
    若三档跨路由（如 base=R3, high=R5）→ 标"⚠️ 路由边界标的"，
      主路由取 base，附路由列出，Factor4 需两条都算并对比
  边界值特判：EPV/AV ∈ [1.1, 1.3]（R3/R5 分界）或 [0.7, 0.9]（R2/R4 分界）
    → 强制标"临界路由"，输出双路由估值区间
```

---

## 关卡 ⑤ 裁决联动

```
路由直接决定下游一切：
  R1 → Factor4 用 AV_liq，安全边际对清算价值
  R2 → Factor4 用重置成本，g=0
  R3 → Factor4 用 EPV 主 + GG 辅（Q3：GG 降权~20%）
  R4 → Factor4 用 AV 打折 + EPV 封顶，禁止成长溢价，多数→排除或深度观望
  R5 → Factor4 用回报率分解 D/M+g（Phase5 升级版），可给成长价值
  R6 → 各分部分别路由 → SOTP 加总

传递字段（给 Factor4）：
  valuation_route = R?（主）
  alt_route = R?（临界时的附路由，否则 none）
  route_reasoning = [EPV/AV=X.XX + moat=X + 触发的决策树分支 + 冲突裁决记录]
  franchise_value = EPV−AV（仅 R5）
  route_confidence = [高/中/低]（客观+定性一致=高；靠降级=中；冲突裁决=低）
```

---

## 执行器输出

```
【因子1.5 估值路由】
  输入：EPV/AV = X.XX | moat = X | trap = X项 | franchise = X | ROIC vs WACC = X
  决策树路径：Step A[过] → B[过] → C[比值X.XX落入…] → D[…]
  冲突裁决：[无 / 具体冲突 + 裁决记录]

  ★ valuation_route = R?（置信度：高/中/低）
    alt_route = R?（若临界）
    route_reasoning = [一段话]
    franchise_value = X 百万元（仅R5）

  路由稳健性：EPV/AV 三档 = [低R?, 基准R?, 高R?] → [稳健/边界标的]

传递至 Factor4：valuation_route、alt_route、route_reasoning、franchise_value、route_confidence
```

---

*龟龟投资策略 · Graham 深化 Phase 4 · 因子1.5 估值路由*

