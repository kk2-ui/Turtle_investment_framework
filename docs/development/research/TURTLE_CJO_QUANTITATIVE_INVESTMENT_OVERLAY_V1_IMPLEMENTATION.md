# Turtle CJO-to-Quantitative Investment Overlay v1

> 状态：`SYNTHETIC_ACCEPTED / CANDIDATE_ONLY / PRODUCTION_PENDING`
>
> 日期：2026-08-25

## 1. 结论

`CJO-to-Quantitative Investment Overlay v1` 已将冻结企业判断单向投影到三个估值身份、价格隐含经营要求、`ExpectationGap` 和条件化 `BuyBand`：

```text
Frozen CJO (read-only)
  + CJO-bound normal-earnings / owner-cash ranges
  + independent synthetic price snapshot
  + cash accessibility, capital burden, permanent-loss assessment
  -> asset / earnings / owner-cash identities
  -> price-implied operating requirements
  -> ExpectationGap
  -> conditional BuyBand + reversal conditions
```

实现只在 synthetic/offline fixture 上验收。它没有接纳真实公司估值、生成生产 BuyBand、修改企业判断或授予报告发布、交易、仓位或投资授权。

## 2. 权限边界

`scripts/cjo_quantitative_investment_overlay.py` 只导入 `enterprise_judgment_core`，并首先验证 Frozen CJO 与 `quantitative_read_allowed`。它不读取也不依赖 Forecast、Measurement Contract、settlement、outcome、learning note 或训练样本；请求中出现这些字段会被拒绝。

```text
Frozen CJO              -> quantitative overlay (read-only)
independent price       -> quantitative overlay only
quantitative overlay    -> report read projection only

quantitative overlay -X-> Frozen CJO mutation
quantitative overlay -X-> training mutation
quantitative overlay -X-> report truth mutation
quantitative overlay -X-> trading authorization
```

结果恒定标记为：

```text
overlay_status       = CANDIDATE_ONLY
production_status    = PRODUCTION_PENDING
may_authorize_trading = false
```

旧 `enterprise_judgment_quantitative_adapter.py` 保留为轻量 synthetic directionality probe；它现在提供 `compile_cjo_to_quantitative_investment_overlay` 作为通向专用 v1 编译器的兼容入口，不改变旧 probe 的含义。

## 3. 数值输入与价值身份

Frozen CJO v1 有经营方向和 trace，但有意不把估值数字写入 enterprise truth。因此 `normal_earnings`、`owner_cash` 和资产数值位于独立的 Overlay request 中，并且每一项必须带有效的 Frozen CJO trace ID 与完全匹配的 CJO direction。数值改变仍是一次新的 Overlay request，而不是对 CJO 的编辑。

三个身份同时输出：

1. `ASSET_TO_COMMON_EQUITY`：非现金普通股权益 + **可达**普通股现金 − 资本负担。`book_cash` 只是披露字段；即使数额很大，也不会直接加入普通股价值。
2. `NORMAL_EARNINGS_CAPITALIZATION`：正常利润按明确 capitalization rate 的范围化价值。它不能取代 D4 owner-cash 闭合。
3. `OWNER_CASH_CAPITALIZATION`：只有 `d4_status=CLOSED` 时才可用来设置条件化 BuyBand。

每个 request 还要有独立价格快照、回报期限/要求回报、年度分配范围、普通股现金可达性、资本负担状态和永久损失评估。价格快照不能早于自己标明的 `valuation_as_of`；无论价格日期如何，它都不会回写历史 CJO。

## 4. ExpectationGap 与 BuyBand

价格先反解各可用的 earnings / owner-cash 经营要求。若多个 CJO 一致的身份都可以解释同一价格，则输出：

```text
EXPECTATION_GAP_UNKNOWN_MULTIPLE_PLAUSIBLE_PARAMETER_SETS
```

而不是选择一个对投资结论有利的参数组。`NO_PRIMARY`、`UNKNOWN`、`MIXED` 或 D4 未闭合也会关闭方向性预期差。

正常的 `PRIMARY + D4 CLOSED + ACCESSIBLE + capital burden CLOSED` 路径才给出：

- `research_zone`：值得继续研究的上限，非投资授权；
- `safety_margin_zone`：在保守 owner-cash 回报上限之外再扣安全边际；
- `conditional_buy_zone`：同一价格上限加上 CJO、D4、现金可达性和永久损失的持续条件；
- `data_insufficient_zone`：D4、资本负担或现金可达性未闭合时激活；
- `permanent_loss_closure`：`HIGH` 或 `UNKNOWN` 时关闭 BuyBand。

当前价格会改变 `ExpectationGap` 和 `current_price_position`，但不会改变 CJO reference 或金融传导。正常利润范围的改变会沿 earnings value 和 research boundary 以正确经济方向传播；它不反向证明中心路径。

## 5. 报告读取

`judgment_generation_handoff.py` 的 `INVESTMENT_ENRICHMENT` 增加显式 `investment_overlay_path` / `--investment-overlay`。报告只读取通过验证的 Overlay，并核对公司和 cutoff 身份。输出的报告投影不含市场价格快照，保留：

- Frozen CJO identity 与 resolution；
- 价值身份；
- 价格隐含经营要求；
- `ExpectationGap`；
- BuyBand、翻转条件和研究问题；
- `report_read_only=true`、无修改权和无交易权。

没有传入该路径时，既有 report-local `INVESTMENT_ENRICHMENT` 读取行为不变。

## 6. Synthetic acceptance

`tests/test_cjo_quantitative_investment_overlay.py` 覆盖：

1. PRIMARY Frozen CJO 生成 asset / earnings / owner-cash 三身份和 candidate-only Overlay；
2. 只变价格，CJO 与财务输入不变，而预期差和当前 BuyBand 位置改变；
3. CJO-bound 正常利润范围增加时，earnings identity 和研究边界随之增加；
4. 不可达 book cash 不能直接进入普通股价值，BuyBand 关闭；
5. D4 未闭合降级，HIGH permanent-loss 关闭；
6. `NO_PRIMARY` / `MIXED` 不生成无条件投资增强；
7. 多个可行参数身份解释价格时保留 `EXPECTATION_GAP_UNKNOWN`；
8. 报告 projection 和现有 report handoff 只读 Overlay；
9. Forecast / outcome 输入被拒绝，schema 可解析。

这些是合成工程验收，不是任何真实公司的价值、预期差、买入区间或投资结论。
