# Graham 估值流水线整合规格（Phase 8）

> ## 理念脊梁（综合派 · 唯一裁决哲学）
> **格林沃尔德估值定"这门生意值多少"(内在价值 IV);GG 定"这价值能不能变成落进小股东口袋的现金"(兑现值 V_cash);VCF + 护城河 + 治理 决定被留存的那部分算不算数(兑现信用 λ)。**
> 三者是正交问题，不是同一问题的两个答案，所以不"互压门槛"。它们经**唯一合成公式**汇成一个数：
> `V_final = V_cash + λ ×(IV − V_cash)`，λ∈[0,1]。
> λ→1：留存资本创造价值且终将兑现 → V_final=IV（纯格林沃尔德）。
> λ→0：留存是幻觉/被截留 → V_final=V_cash（纯 GG 落袋）。
> 这是全系统唯一的价值合成规则；三视角权重只作方向/置信度校验，不再另算价值（消除"两套哲学并存"的裂缝）。

> **Phase 8 产出**。把 Phase 1-6 的执行器接进 `phase3_分析与报告.md` 的执行流，并把**两条流水线汇成一个买/卖/仓位裁决**。
> 上游全部执行器：Phase1 `factor_资本成本与正常化盈利`、Phase2 `factor_EPV盈利能力价值`、Phase3 `factor_资产价值重置成本`、Phase4 `factor1.5_估值路由`、Phase5 `factor_R5回报率分解`、Phase6 `factor_VCF成长价值`。
> 现行方法权限见 `docs/turtle_valuation_routing_and_investor_styles.md`；历史迁移推导见 `docs/History/graham_migration/turtle_graham_deepening_roadmap.md` 与 `docs/History/graham_migration/turtle_graham_migration_plan.md` §VII。

---

```
Step 1  因子1A 五分钟快筛                    （不变）
Step 2  因子1B 深度定性（护城河/陷阱/franchise_type/治理）  （不变，产出路由输入）
Step 3.1 ★共享输入：Phase1 资本成本 r* + 正常化盈利 E_norm   【新】
          → 产出 r*(三档)、E_norm(三档,已归母)、AA(转传)
Step 3.2 ★Phase2 EPV + Phase3 资产价值 AV                    【新，可并行】
          → EPV_op、EPV_equity、AV_going、AV_liq、EPV/AV 比
Step 3.3 ★因子1.5 估值路由（Q4 定案位置）                     【新】
          → 吃 EPV/AV + 1B 评级 → valuation_route R1-R6 + route_confidence
          ├─ R1 → 主估值 = AV_liq（清算）
          ├─ R2 → 主估值 = AV_going（重置成本）
          ├─ R3 → 主估值 = EPV 主 + GG 辅（Q3 降权20%）
          ├─ R4 → 主估值 = AV 打折 + EPV 封顶，禁成长溢价
          ├─ R5 → 主估值 = Phase5 回报率分解（+Phase6 VCF/成长价值）
          └─ R6 → 各分部分别路由 → SOTP
Step 3.5 因子1C 增量增长检验 + ★Phase6 VCF（R3/R5 激活）     （1C不变，VCF新挂）
Step 3.6 ★D2 管理层资本配置评估（R5 激活，其余路由可选）       【D2 新增】
          → 读 factor1C C类特征/减值历史 + §5 Capex/并购/回购历史
          → 产出 cap_alloc_score（优/中/差/劣）+ gov_priced_in（已/部分/未定价）
          → 传 factor_VCF 关卡①a（成长价值准入）、λ③（综合合成）、Factor4（买点注释）
Step 4  因子2 穿透回报率粗算                  （不变，喂 R 给 HH 对比）
Step 5  因子3 穿透回报率精算 GG               （不变，R3/R5 的 GG 辅视角）
Step 5.5 ★Phase5 R5 回报率分解（仅 route=R5 激活）            【新】
          → R_total、safety_margin、decay、临界买入价
Step 6  因子4 估值与安全边际 + ★统一裁决                       （升级）
          → 按 route 选主估值 + 两条流水线三视角汇总 + gov_priced_in 买点注释
Step 7  生成报告（含★买点结论块）                             （升级模板）
```

> **兼容策略**：新执行器以"加载参考文件"方式插入，不改因子1A/1B/2/3 的既有逻辑。路由决定哪些新执行器激活——非 R5 标的不跑 Phase5，节省算力。

---

## 二、统一裁决（两条流水线汇一处）

> 核心原则（Phase7 校准确认）：**估值流水线用 r*，回报率流水线用 II，两者不互压门槛。** 两条流水线经理念脊梁的 λ 合成公式汇成 `V_final`，再按路由决定视角侧重与置信度。

```
按 valuation_route 选主估值 + 汇总：

R1 困境：
  主 = 清算 AV_liq/市值。买点 = 市价 << AV_liq（深度折价）。回报率流水线不适用。

R2 重置成本：
  主 = AV_going/市值（重置成本安全垫）。EPV≈AV 佐证无护城河。GG 作现金回报参考。

R3 稳定低增长：
  IV = EPV。→ 套唯一合成公式（V_cash=分红率×IV）得 V_final。
  裁决锚 = V_final/市值 vs（1 + §6.5-A 安全边际地板）。AV 层作 V_final 下限兜底。
  EPV 达标但 GG 不达标 → GG兑现闸门压 λ，λ 打分决定留存信几分，报告显式列 ①②③。

R4 陷阱/毁灭价值：
  主 = AV 打折。EPV 封顶（<AV）。成长溢价=0。
  多数 → 排除 或 深度观望（要求极大折价）。

R5 特许经营：
  IV = EPV + 成长价值（Phase6；VCF≤1 → 成长溢价=0，IV 封顶 EPV）。
  → 套唯一合成公式（V_cash=分红率×IV）得 V_final。
  裁决锚 = V_final/市值；并叠 Phase5 硬门槛：safety_margin < §6.5-A 地板 → 一票否决（即使 V_final/市值 达标也不买，回报率不够即出局）。
  三视角权重 60/20/20 仅校验方向：与 V_final 裁决相反 → 降置信度、复核 λ。

R6 特殊情形：
  各分部按自身路由算 → SOTP 加总 → 对比市值。

★ 唯一合成公式（R3/R5 强制；R1/R2/R4/R6 见下方特例）：

  IV       = 主估值（R3:EPV；R5:EPV+成长价值；已归母、已过资产负债调整），折现率 r*
  分红率    = min(dps/EPS归母, 1.0)   —— dps>EPS 记为 1.0 并标"分红超盈利⚠️"
  V_cash   = 分红率 × IV              （被"已派现金"背书的那部分内在价值 = 干净地板，与 IV 同用 r*）
  IV − V_cash = (1−分红率) × IV       （留存盈利价值 = λ 要裁决的对象）
  V_final  = V_cash + λ ×(IV − V_cash) = IV ×[分红率 + λ×(1−分红率)]
  裁决锚   = V_final / 市值   （>1+安全边际→买；≈1→观望；<1→排除）

  ⚠️ 铁律：V_cash 与 IV 必须同用 r* 折现（V_cash=分红率×IV），否则 V_cash 会因 II<r* 反超 IV、
     令 λ 方向颠倒。II 只进"GG 兑现闸门"（见下），绝不作 V_cash 的折现率。

  ── GG 兑现闸门（II 在此登场，realization gate，不重算价值只调 λ）──
     GG_base ≥ II            → 派现回报已过小股东门槛，λ 不额外惩罚
     GG_base < II            → 派现回报未达门槛 → λ 封顶 0.3（连落袋回报都不够，留存更不可信）
     dps > EPS归母（超额分红）→ 分红率记 1.0 但标⚠️，V_final≈IV，另在报告提示"分红不可持续风险"

  ── λ 兑现信用打分（确定性，基线 0.5，三项相加，clip 到 [0,1]）──
    ① 价值创造 VCF（Phase6）：
         VCF≥1.3 → +0.25 | 1.1≤VCF<1.3 → +0.15 | 0.9≤VCF<1.1 → 0
         0.7≤VCF<0.9 → −0.15 | VCF<0.7（毁灭价值）→ −0.25
    ② 护城河半衰期（Phase5 优先级1-3 已算）：
         ≥30yr → +0.15 | 15–30yr → +0.05 | 8–15yr → −0.05 | <8yr → −0.15
    ③ 治理/资本配置（D2 factor_管理层资本配置 · 书第8/9章）：
         【优先读 D2 执行器的 cap_alloc_score + gov_priced_in；若 D2 未执行，退回旧规则†】
         cap_alloc_score=优                          → +0.10
         cap_alloc_score=中                          →  0（基线）
         cap_alloc_score=差                          → −0.15
         cap_alloc_score=劣（系统性错配+已证实减值）→ −0.25
         gov_priced_in 叠加（仅差/劣 时）：
           已定价 → 再+0.05（市场已部分反映，⚠️若治理持续恶化恢复全额）
           未定价 → 不调整（λ惩罚是唯一下行保护）
         最终 λ③ = base + gov调整，clip 到 [−0.25, +0.10]

         † 旧规则（D2 未执行时 fallback）：
           干净+高分红意愿 → +0.10 | 一般 → 0
           有截留/侵占史 or 少数股东>30%且分红吝啬 → −0.25
    λ = clip(0.5 + ①+②+③, 0, 1)

  ── λ 语义（自检用）──
    λ≥0.8：信留存 → V_final≈IV，赌格林沃尔德"留存复利"论
    λ≤0.2：不信留存 → V_final≈V_cash，只认 GG 落袋，IV 溢价视为纸面富贵
    背离越大（|IV−V_cash|/市值 越高）λ 越关键 → 必须在报告显式列出 ①②③ 打分

  ── 三视角权重（R5 60/20/20、R3 EPV主+GG20%）：仅作方向校验 ──
    若 V_final 裁决与三视角多数方向相反 → route_confidence 降一级并强制复核 λ 打分
    route_confidence=低（路由靠降级/冲突裁决）→ 最终裁决再降一级
```

### R1/R2/R4/R6 合成特例（无双流水线，不套 λ）
```
R1 困境  ：V_final = AV_liq（清算），λ 不适用（无持续盈利现金流）
R2 重置  ：V_final = AV_going，GG 仅作现金回报参考（EPV≈AV 已证无护城河，IV 无溢价可留存）
R4 毁灭  ：V_final = min(AV×折价, EPV)，成长溢价强制=0，λ 上限 0.3（留存大概率毁灭）
R6 特殊  ：各分部按自身路由算 V_final → SOTP 加总
```

---

## 三、买点结论块（报告模板新增，对齐迁移计划 §VII 文件6）

```
【买点结论】
  估值路由：R? （置信度 高/中/低）— {route_reasoning}
  主估值法：{按路由}
  ── 估值流水线 ──
    资产价值 AV = X（每股 X）| EPV = X（每股 X）| 内在价值(含成长) = X
    内在价值/市值 = X.XX → {低估/合理/高估}
  ── 回报率流水线（R3/R5）──
    GG = X% vs II = X% | R_total = X%（R5）| safety_margin = X pct vs 地板(3-4pct)
  ── 综合合成（唯一裁决）──
    IV = X（每股 X）| 分红率 = X%（dps X / EPS归母 X）{超额分红⚠️?}
    V_cash = 分红率×IV = X | 留存价值 IV−V_cash = X
    GG闸门：GG_base X% vs II X% → {过/未过→λ封顶0.3}
    λ = 0.XX ← 基线0.5 ①VCF {+/−X} ②半衰期 {+/−X} ③治理 {+/−X}
    V_final = IV×[分红率 + λ×(1−分红率)] = X（每股 X）
    V_final/市值 = X.XX → {低估/合理/高估}
    λ 语义：{信留存→赌复利 / 不信→只认落袋 / 中性}
  ── 买点 ──
    目标买入价 = V_final ×(1 − 安全边际X%) = X 元
    R5 附加门槛：safety_margin = X pct vs 地板(3-4pct) → {通过/一票否决}
    当前价 X → {买入/观望/排除}，距买点 X%
    仓位建议：{position_cap，保留5%上限，护城河越持久越接近上限}
  ── 卖点（Q 定案：回报率法只解买点，卖点另论）──
    参考：估值回归内在价值 / 25×PE 上限 / 基本面恶化触发
```

---

## 四、Phase 7 遗留数据缺口的处置（决策）

> Phase7 发现 data_pack 缺 EPV/AV/VCF 所需字段。决策：**优先靠降级阶梯，不强求补 data_pack 字段。**

```
理由：
  - 执行器的降级阶梯（Phase1-6 每个都有）已保证缺字段时给近似估算+⚠️，不空
  - 补 data_pack 字段需改 pdf_preprocessor（重活），且散户源数据本就缺（重置成本/分部）
  - 符合用户"估算优先于空着"原则

分级处置：
  能从现有 §字段推导的（投入资本=有息负债+权益−超额现金；EBIT=归母+税+财务费用）
    → 执行器内直接算，无需新字段
  §17 预计算能加速的（正常化盈利、λ）
    → 若 §17.x 存在则引用，缺则手算（沿用 factor3 §17 模式）
  散户源数据本就缺的（分部并购回报、重置成本明细）
    → 走降级阶梯（Phase6 商誉拆分近似、Phase3 三类无形资产估算），标⚠️给区间

仅当某字段被 ≥3 类路由反复手算且口径易错 → 才考虑加 data_pack 预计算（留待实跑积累后决定）
```

---

*龟龟投资策略 · Graham 深化 Phase 8 · 整合规格*

