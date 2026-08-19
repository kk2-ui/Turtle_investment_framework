# EPV 盈利能力价值执行器

> **Phase 2 产出**。书的头号估值锚点。`EPV = 正常化盈利 / r*`，再做资产负债表调整得股权 EPV。
> 上游：Phase 1（`factor_资本成本与正常化盈利.md` 给 r* 与 E_norm/AA）。下游：Phase 4 路由（EPV↔资产价值勾稽判护城河）、Factor4 安全边际。
> 母版 `_executor_template.md`；现行方法权限见 `docs/turtle_valuation_routing_and_investor_styles.md`，迁移历史见 `docs/History/graham_migration/turtle_graham_deepening_roadmap.md`。单位百万元。
> **全局原则**：拿不到精确数据给近似估算 + 方法 + ⚠️，绝不空着。

---

## 定位与指令

> **定位**：算"假设公司零增长、仅维持当前盈利能力"下的股权内在价值。这是 Greenwald 三价值来源里的**次可靠锚**（比资产价值不可靠、比成长价值可靠），也是判护城河的一条腿（EPV vs 资产价值）。
> **上游依赖**：Phase 1 的 r*（三档）、E_norm（三档）、AA（并列口径）；§4 资产负债表（现金/投资/负债）。
> **下游消费**：Phase 4 Factor1.5（`EPV/AV` 差额 → 护城河 → 路由）；Factor4（`EPV/市值` → 安全边际）；R3 路由的主估值。

**指令**：EPV 假设**零增长**——不预测未来、不折现增长，只把可持续盈利按资本成本还原为永续价值。这是它比 DCF 可靠的根源（Greenwald 核心论点）。Q1 定案：`EPV_norm` 与 `EPV_AA` 两口径并列。全程保守。

---

## 关卡 ① 数据源逐行锚定

| 变量 | 含义 | 数据源（§X 行项） | 单位 |
|---|---|---|---|
| E_norm | 正常化税后经营盈利（三档） | Phase 1 输出 | 百万元 |
| AA | 现金还原基准（并列口径） | factor3 步骤7 / Phase 1 转传 | 百万元 |
| r* | 资本成本（三档） | Phase 1 输出 | % |
| Cash_excess | 超额现金（非经营所需） | §4 货币资金 + 交易性金融资产 − 经营所需现金 | 百万元 |
| Invest_noncore | 非经营投资资产 | §4 长期股权投资 + 其他非流动金融资产 + 投资性房地产 | 百万元 |
| D_debt | 有息负债（扣除时用） | §4 短期借款+长期借款+应付债券+一年内到期非流动负债 | 百万元 |
| Minority | 少数股东权益 | §4 少数股东权益 | 百万元 |
| Shares | 总股本 | §11 | 百万股 |
| E_mktcap | 股权市值 | §11 | 百万元 |

> **经营所需现金**估算：拿不到精确值时用「营业收入 × 2%」或「§17 若有预计算」近似，标 ⚠️。超额现金 = 总现金 − 经营所需，负则取 0。

---

## 关卡 ①b 主计算（EPV 三步，Greenwald 口径）

```
第1步 经营价值（永续，零增长）：
  EPV_op_norm = E_norm / r*          （规范化口径，主。E_norm 已归母，见 Phase1 ⑤）
  EPV_op_AA   = AA / r*              （现金还原口径，并列，Q1 定案）
    ⭐ AA 取值（v2 校准修正）：若 factor3 标 ap_finance=warn 或 AP超额融资贡献/AA>30%
      → EPV_op_AA 必须用 AA_ap_adjusted（AP 超额融资调整后），非报表 AA
      （否则 EPV_AA 继承 AP 账期拉长的虚高现金，与 GG 精算 AP-adjusted 口径不一致。
        中国食品例：ap_finance=warn，须用调整后 AA）
    ⭐ AA 已是归母口径（factor3 minority_adjustment 已 ×归母比例），与 E_norm 归母对齐

第2步 资产负债表调整 → 企业价值转股权价值：
  EPV_equity = EPV_op
             + Cash_excess           （超额现金归股东）
             + Invest_noncore        （非经营资产按可回收值，见边界③）
             − D_debt                （偿债）
             − Minority              （剔除少数股东占份）

  两口径各算一份：EPV_equity_norm、EPV_equity_AA

第3步 每股 EPV 与安全边际：
  EPV_per_share = EPV_equity / Shares
  EPV/市值比 = EPV_equity / E_mktcap
    >1 → 市价低于零增长价值（有安全垫）
    <1 → 市价已包含增长预期（买入需 R5 回报率流水线佐证增长真实）
```

> **口径差解释（强制）**：EPV_norm 与 EPV_AA 差异 = 规范化 EBIT 与现金还原的口径差。
> - AA < E_norm（常见）：现金口径扣了全额 Capex/营运资金占用，更保守 → EPV_AA 为下沿
> - AA > E_norm：可能有大额非现金利润被现金口径加回，需核查
> 报告并列两值，取 **较低者为主锚**（保守），另一者为上沿。

---

## 关卡 ② 数据缺失降级阶梯

```
E_norm 缺（Phase 1 未产出）：
  优先级2：用 AA 单口径算 EPV_AA，标"⚠️ 仅现金口径，缺规范化交叉验证"
  优先级3：E_norm ≈ 近3年归母净利润中位 × (1 − 一次性占比)，标 ⚠️ 粗估

Cash_excess / Invest_noncore 明细缺：
  优先级2：超额现金 = max(0, 货币资金 − 收入×2%)；非经营投资按 §4 账面值全额，标"账面值近似，未做可回收性折扣"
  优先级3：连投资明细都缺 → 只做现金调整，非经营资产标"⚠️ 未计入，EPV_equity 为下沿估计"

经营所需现金比例缺：
  用行业近似（重资产 1%/一般 2%/零售 3%）× 收入，标 ⚠️
禁止：任何一项留空。缺 → 给近似 + ⚠️。
```

---

## 关卡 ③ 边界情形

| 情形 | 触发 | 强制处理 |
|---|---|---|
| E_norm ≤ 0（正常化亏损） | Phase 1 E_norm<0 | EPV_op = 0（无盈利能力价值），标"EPV 归零，估值退回资产价值（Phase 3）" |
| 非经营投资含水分 | 长期股权投资/投资性房地产大额 | 按可回收值：上市股权用市值、投资性房地产打 7-8 折、联营按账面，标口径 |
| 净现金 > 市值 | Cash_excess+Invest > E_mktcap | 标"⚠️ 类现金壳，需查大股东资金占用/分红意愿（关联 factor3 步骤13 控股股东资金池折价）" |
| 高成长企业 | Phase 1 已标 EPV 不适用 | EPV 仅作**资产下限**报告，主估值转 R5，标注 |
| r* 触天花板 | r*>13% | EPV 极低，标"高不确定性，EPV 参考价值有限" |
| 少数股东占比大 | Minority/总权益 >10% | EPV_equity 必须扣 Minority，输出归母口径（对齐 factor3 步骤10b-少数） |

---

## 关卡 ④ 强制敏感性 / 置信区间

```
EPV 天然带区间（E_norm 三档 × r* 三档）：
  EPV_low  = E_norm_low  / r*_high   + 资产调整   （分子小、分母大 → 下沿）
  EPV_base = E_norm_base / r*_base   + 资产调整
  EPV_high = E_norm_high / r*_low    + 资产调整   （上沿）

强制输出矩阵（3×3 简化为对角三档 + 并列口径）：
| 情景 | E_norm | r* | EPV_equity | EPV/市值 | 每股 |
| 悲观 | low    | high | X | X | X |
| 基准 | base   | base | X | X | X |
| 乐观 | high   | low  | X | X | X |
| AA基准 | AA   | base | X | X | X |

裁决含义：
  EPV_low/市值 > 1 → 零增长下市价即有安全垫，稳健
  EPV_high/市值 < 1 → 即便乐观，市价已透支增长 → 必须靠 R5 证明增长
  区间跨 1 → 灰区，看 R5 与资产价值
```

---

## 关卡 ⑤ 裁决联动

```
EPV 的两大裁决用途：
① 护城河判定（传 Phase 4）：
   EPV_op / 资产价值(AV, Phase 3) 比值：
     ≈1（0.8-1.2）→ 无护城河，竞争均衡 → R2/R3
     >1.2         → 有护城河，(EPV−AV)=特许经营价值 → R5
     <0.8         → 毁灭价值/衰退 → R4
② 安全边际（传 Factor4）：
   EPV/市值 → 无增长价值锚；配合 §6.5-A 安全边际地板 3-4%

仓位联动：EPV/市值 越高（越便宜）→ 结合护城河 → position_cap（保留 5% 上限链条，关联 position-limit-per-stock）
GG 双验：R3 路由下 EPV 为主，GG 穿透回报率为辅（Q3 定案 GG 降权~20%）

传递字段：EPV_op_norm/AA、EPV_equity(low/base/high)、EPV/市值、EPV_per_share、EPV_vs_AV_ratio(待Phase3)
```

---

## 执行器输出

```
【EPV 盈利能力价值】
  经营 EPV：EPV_op_norm = E_norm/r* = X（EPV_op_AA = X，主锚取较低者 = X）
  资产调整：+超额现金 X +非经营资产 X −有息负债 X −少数股东 X
  股权 EPV：EPV_equity = X 百万元
    三档区间 = [悲观 X, 乐观 X]，AA 口径 = X
  每股 EPV = X 元 | EPV/市值 = X.XX
  口径差解释：EPV_norm vs EPV_AA 差 X%，原因：...

  护城河信号（待 Phase 3 AV）：EPV_op/AV = [待勾稽] → 初判路由 R?
  安全边际（vs 市值）：EPV/市值 = X.XX → [有垫/透支增长]

数据折价：[列 ⚠️ 与折价 pct]
传递至 Phase 4：EPV_op、EPV_equity 三档、EPV/市值、每股 EPV
```

---

*龟龟投资策略 · Graham 深化 Phase 2 · EPV 盈利能力价值*
