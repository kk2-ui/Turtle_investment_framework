# 泛微网络 direct judgment calibration：独立结果前审阅

> reviewer：独立于 judgment owner 与未来 outcome custodian
>
> reviewed freeze：commit `ff2e3fe`
>
> FY2019 outcome、价格与后续材料：`UNREAD`
>
> 最终裁决：`ACCEPT`

## 首轮退回为何材料

首轮根因为 `REASONING`，不是资料不足。原合同会让一个无经济规模的 eteams 客户、不可比的
研发分类变化、信用放宽形成的收入，或仅剩极少流动性的 adjusted cash 改变管理层、owner cash、
永久损失与估值方向。这些不是“保守误差”，而是会同时制造虚假乐观和虚假悲观。

## 四项修复验收

1. **eteams 必须具有经济材料性。** 命名的重复收入、ARR 或贡献至少达到可比集团收入 `1%`，
   才能单独触发方向性更新。单个客户、logo、无规模客户数或定性 SaaS 描述只进入 mixed。
2. **C2 先处理真实事件，再处理口径。** 直接材料产品事件优先；无直接事件时，无法重建同合并
   范围收入和同分类 R&D 的结果进入 `MEASUREMENT_ONLY`，不下调公司；普通负类只能使用同口径序列。
3. **现金改善必须守住两个端点和流动性。** adjusted endpoint 需增长至少 `10%`，法定
   `OCF-capex` 至少保持 FY2018 的 `90%`，同定义 eligible net liquidity 至少保持 `80%`。
4. **交付杠杆不能由信用放宽制造。** 正面类要求应收收入比不得上升 `5pp` 或以上，且无材料
   信用损失或客户事件。预收下降本身仍是双向信号，不机械判负。

## 反例验收

- 新增一个 eteams 付费客户但无收入/贡献规模：mixed，不上调；
- eteams 客户 `10→8`，但无材料经济规模：mixed，不下调；
- eteams 重复收入占集团 `2%` 且增长 `20%`：positive；
- 材料 eteams ARR 占集团 `2%` 且下降 `15%`：negative；
- 合并范围或研发分类变化且无法重建、无直接产品失败：`MEASUREMENT_ONLY`；
- 收入 `+20%`、两项费用率各降 `3pp`、应收收入比升 `8pp`：mixed；
- adjusted cash `+15%`，但法定现金下降 `90%` 且净流动性接近零：mixed；
- adjusted cash `+15%`、法定现金和同定义净流动性均守住材料下限：positive。

三个业务 cell 的概率各自合计 `1.00`。每个业务结果类均预先绑定 management、owner cash、
permanent loss、scenario 与 valuation direction。`MEASUREMENT_ONLY` 是局部观察状态，不占业务
概率，也不取消整家公司判断。

## Outcome custodian 最小合同

Custodian 只可读取一份授权窗口内的发行人 FY2019 官方完整年报，结算客户/交付、核心 R&D 与
eteams、集团现金与可逆融资三个 cell。必须报告连续事实，不得用分类标签替代结果。

缺失 eteams 披露只限制产品选择权；不能取消已经观察到的客户吸收、核心研发和集团现金。
Custodian 不判断管理层、normalized owner cash、永久损失、情景、估值方向或训练成效。

## 权限

本裁决只允许签发 outcome access authorization。不授予 `TRANSFER_VALIDATED`、
`METHOD_FROZEN`、Comparative、CJO、正式估值、BuyBand、报告发布或投资权限。
