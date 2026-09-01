# Runtime “不可得不等于负面”纠正

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`ACTIVE_MISSING_INPUT_STOP_AND_NEGATIVE_BIAS_REMOVED`
>
> 方法状态：`NOT_VALIDATED / NOT_FROZEN`

## 投资上的真实错误

前一轮已取消“披露缺失自动折价”，但活跃链还有四种同源偏置：

1. DPS、当前价或 canonical GG 缺失时，局部估值可能先返回 unresolved，随后又在计算轨迹中崩溃；
2. `compute_gg` 会用不同经济身份的 Factor2 盈利率重建伪 GG，`evaluate_decision` 再把缺失固定写成
   `Hold`；
3. 正式 decision/valuation/compiler 链只接受 Buy/Hold/Avoid 和数值仓位，迫使报告为完成结构而制造
   价格动作；
4. 来源深化固定要求两财年、两次 section read 和若干搜索调用；一份真实年报、一次 section extractor
   失败或一个外部 provider 故障，都可能终止整份企业判断。Zone B 也会因一个年度失败而丢弃其他年度。

它们表面上没有写负面公司事实，实质上却奖励两种防御行为：把不可得写成 Hold/Avoid，或者拒绝完成
当前企业判断。这会同时损害正常盈利、owner cash、永久损失和买价处理的可用性。

## 当前经济规则

`UNAVAILABLE` 只撤回依赖该输入的主张：

- canonical GG 不可用时，Factor2 只保留为具名盈利诊断，不能升级成 GG；
- 当前价或估值输入不可用时，企业经营判断继续，当前价格动作和仓位暂不承保；
- 企业事实已经独立形成永久损失否决时，即使估值 unresolved，仍可给出
  `Fundamental Avoid / 0%`，但不能伪造价值区间；
- 观察到的 canonical GG 恰好为零仍是负面结果，不会被当作缺失；
- 一项来源不可得只降低其责任匹配主张的置信度。至少有一份合格官方原文时可以形成有界判断；所有
  官方正文均未取得时仍阻断写章。

## 活跃运行时变化

- DDM calculation trace 对缺失输入输出 `result=null / steps=[] / reason`，完整 bundle 正常落盘；
- `compute_gg`、`compute_ddm`、`evaluate_decision` 传播 `UNRESOLVED_VALUATION`，不再生成伪 GG、
  Hold/Avoid 或数值仓位；
- rejection summary 将 unresolved 与 pass、block 分开；
- manifest、decision ledger schema、valuation ledger、reliability gate 和 decision compiler 共同接受
  `Research Only`。Ch0/Ch14 写“当前价格动作暂不承保”，不写 `None%`；
- `Abandon + unresolved` 机械合成为基于企业否决的 `Fundamental Avoid / 0%`；
- 行情 provider 暂时不可用时，统一管线写入显式 unresolved bundle，并继续企业研究、PDF 与综合阶段；
- source deepening 的年度要求按本地真实年报数量自适应，外部工具要求从固定调用数改为一次真实尝试；
- section extractor 失败只有在同章至少存在其他合格官方原文时才局部降级；全失败仍阻断；
- Zone B 只要至少一个年度成功就继续汇总，失败年度作为局部比较缺口返回。

没有增加新的全局 gate，也没有把“继续运行”解释为证据充分。低权威网页成功抓取不能冒充合格正文，
真实失败记录也不能支撑事实主张。

## 验收反例

定向回归覆盖：

- missing DPS 的完整 `compute()` 不崩溃且 overall 为 unresolved；
- canonical GG 缺失但 Factor2 数值存在时，三个活跃 calc tools 均不产生价格动作；
- Continue/Pause + unresolved 通过 manifest → schema/ledger → valuation/reliability → compiler，正文无伪数字；
- Abandon + unresolved 为 0%，观察到的 GG=0 仍为 resolved AVOID；
- 只有一份年报时不要求不存在的第二财年；
- 一项 section 失败且另有官方正文时局部继续，所有 section 均失败时仍阻断；
- 外部 provider 的真实失败不永久卡章，低权威成功结果仍不能满足来源要求；
- Zone B 两年中一年成功可继续，一年中零成功才停止。

这些修复只证明活跃系统不再把资料不可得机械转写成负面或全局停摆。它们不是跨公司效用验证，
不授予 transfer、method freeze、Comparative、CJO、正式估值、BuyBand、报告或投资权限。

## 独立审阅

两条独立审阅都给出 `ACCEPT`：

- missing-input 全链复验确认 valuation contract、真实 provider failure recorder、nullable proposal 完成器均已闭合；
- source/Zone B 复验确认真实失败可以局部结算，低权威成功不能冒充不可用，而全部官方正文失败仍会阻断。

本地合并定向回归为 `156 passed`。审阅结论只接纳上述活跃路径修复，不把结构完整或测试数量计作
投资判断效用。
