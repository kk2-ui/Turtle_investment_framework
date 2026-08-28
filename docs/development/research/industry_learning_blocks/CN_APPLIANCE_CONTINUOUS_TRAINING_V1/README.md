# 家电持续训练 V1：苏泊尔结果前冻结

> 状态：`PREOUTCOME_INDEPENDENT_REVIEW_REQUIRED`
>
> cutoff：`2018-09-30T23:59:59+08:00`
>
> 对象：浙江苏泊尔股份有限公司（`CN:002032`）
>
> 权限：历史训练与研究议程；无方法迁移、CJO、估值、报告、BuyBand 或投资权限。

## 投资者要训练什么

本轮不再训练“发行人收入会不会增长”这一条会计趋势，而是训练更容易导致错误归因的区别：

> 发行人增长是否穿透到一个明确的产品责任边界；即使穿透，发行人现金是否足以支持对普通股 owner cash 的判断？

Round 10 已有六个发行人层字段完成机械结算，但外部审阅仍是 `NO_MATERIAL_UTILITY`。原因不是结算失败，而是发行人收入、经营现金流和资产不能识别客户响应、单位经济、行动效果或普通股现金。本轮保留这个负面结论，不把它洗成方法胜利。

## 结果前判断

同一份 FY2017 官方年报显示：

- 公司同时经营炊具、电器以及内外销业务，产品责任边界不同；
- 产品创新、下沉渠道和电商建设已经开展，但年报叙述不能证明它们造成了结果；
- 炊具毛利率下降，电器毛利率大体稳定，产品库存增长快于销售；
- 发行人收入增长而经营现金流下降；发行人现金仍不是普通股 owner cash；
- 消费升级、SEB 订单转移、原料与人工成本、共同渠道变化都是可复制结果的反方解释；
- 上海赛博收购在年报发布时仍处于工商变更办理阶段，结果期须重新确认合并范围。

因此，公平 Baseline 是 `CONTINUE_OPERATING_UNDERWRITING`；八维 Enhanced 的结果前处理是 `CONDITIONAL_PRODUCT_QUALITY_UNDERWRITING`。这只是预先冻结的材料处理差异，不是方法效用结论。

## 冻结的可结算字段

| 角色 | FY2017 基线 | FY2018 合同 | 结果前方向 | 解释边界 |
|---|---:|---|---|---|
| 发行人规模背景 | 合并营业收入 | `CONSOLIDATED_REVENUE_RMB` | `INCREASE` | 不能证明产品客户响应 |
| 产品区分字段 | 电锅类收入 | `PRODUCT_REVENUE_RMB:电锅类` | `INCREASE` | 是产品信号，不是忠诚度或行动因果 |
| 发行人现金背景 | 合并经营现金流净额 | `CONSOLIDATED_OPERATING_CASH_FLOW_RMB` | `STABLE` | 不能替代普通股 owner cash |

三个字段分别使用现有 Minimal Historical Episode 的 Decision、Technical Route、Measurement、Static Evidence 和 Prediction 合同。后续 acquisition 可逐字段返回 `OBSERVED`、`MEASUREMENT_MISMATCH` 或 `UNKNOWN`；一个字段不得拖停其他字段。

## 证据与隔离

唯一事实来源是 cutoff 前官方静态 PDF：

- `CNINFO:002032:ANN:20180331:1204552803`
- `https://static.cninfo.com.cn/finalpage/2018-03-31/1204552803.PDF`
- 物理页：11、12、13、16、21、34。

候选资格按 `角色 × 公司 × cutoff × 实际输入` 判断，不使用公司级黑名单。本轮 static-curator 与 forecaster 是同一历史训练会话中的顺序功能角色，不冒充独立 holdout：curator 形成 FY2017 字段包，forecaster 消费该包；两者都没有读取 FY2018 年报、结果字段、价格或既有 custody 内容。最终 custodian 仍必须是新的隔离角色。

## 下一合法步骤

1. 独立 reviewer 只复核 cutoff、PDF 页、责任边界、三项字段合同、Baseline/Enhanced 公平性和防御性写作；
2. 审阅通过后才授权一个新的 outcome-only custodian；
3. custodian 只取得 FY2018 官方静态年报并逐字段机械结算；
4. 只有产品字段使 Enhanced 预先避免 Baseline 方向错误，或实际改变材料处理时，才生成一次方法效用候选；否则记录 `NO_MATERIAL_UTILITY`。

本轮不运行未来 holdout，也不进入另一 Agent 的历史 `3+2+1` roster。
