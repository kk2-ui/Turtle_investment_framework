# 吉比特 direct judgment calibration：独立结果前审阅

> reviewer：独立于 judgment owner 与未来 outcome custodian
>
> reviewed freeze：commit `9d27f70`
>
> FY2019 outcome、价格与后续材料：`UNREAD`
>
> 最终裁决：`ACCEPT / PREOUTCOME_CALIBRATION_COHERENT_AND_MATERIAL`

## 为什么前两版被退回

首轮根因为 `REASONING + WRITING`。原合同会把产品级披露缺失解释为核心经营恶化，也会把单个
非《问道》产品退出解释为组合失败。这两条都会在没有材料经营证据时下调 normal earnings、
owner cash 与永久损失保护，属于防御性低估，不是“保守一点没有代价”。

第二轮还剩一个同类缺口：年报若明确把自营收入的小幅变化归因于《问道》，但变化未达到
`+5%` 支持阈值，catch-all 会把它误写成冲突。该问题已由
`NONDECISIVE_ATTRIBUTED_PROXY` 修复。

## 最终验收

### 核心 IP：缺少精度不再等于恶化

核心 cell 仍保持三种主类，但 mixed 被局部区分为：

- `DISCLOSURE_ONLY`：没有责任匹配的《问道》指标，也没有明确的自营变化归因；
- `NONDECISIVE_ATTRIBUTED_PROXY`：明确归因，但变化在 `(-5%, +5%)`，不足以支持或反驳；
- `CONFLICTING_OBSERVED_SIGNALS`：观察到的责任匹配指标真正冲突，或温和负向结果需要谨慎。

前两类只降低产品归因置信，不下调集团现金、核心 normal earnings 或永久损失保护。只有观察到
的冲突和材料负向证据才允许下调企业判断。

### 产品组合：退出本身保持双向

单一上线、退出、授权收入下降、排名或注册只结算为 mixed。负类需要非《问道》聚合经济指标
材料下降、退出伴随相对研发投入材料的减值/未吸收资源损失，或研发强度上升且游戏总收入材料
下降。健康组合清理不再被机械惩罚。

### 固定资本：能自筹与值得投入继续分开

净债务使用现金缓冲，毛债不会在净现金状态下自动触发资金压力。OCF、capex、办公楼与园区
使用里程碑只回答资金承受和部署，不能证明不动产式资本配置的经济回报。

## 七个反例验算

| 反例 | 唯一结算 | 投资处理 |
| --- | --- | --- |
| 无《问道》产品披露、无明确自营归因 | core mixed / `DISCLOSURE_ONLY` | 只降归因置信 |
| 《问道》充值 `+6%`、活跃 `-7%` | core mixed / `CONFLICTING` | 允许局部谨慎更新 |
| 自营 `+10%`，但未明确归因《问道》 | core mixed / `DISCLOSURE_ONLY` | 不把模式增长冒充核心产品增长 |
| 无直接指标、自营 `+3%` 且明确归因《问道》 | core mixed / `NONDECISIVE_ATTRIBUTED_PROXY` | 不降管理层、现金或永久损失 |
| 单一非《问道》产品退出且无材料损失 | portfolio mixed | 不惩罚可能健康的清理 |
| 产品退出且减值达到研发费用 `5%`、无正向重复信号 | portfolio negative | 只下调非核心组合范围 |
| 责任匹配的非《问道》重复贡献且游戏收入、研发强度满足条件 | portfolio positive | 允许有限成长研究，不资本化产品数量 |

七个反例均按 first-match 得到唯一分类。三个 cell 与三情景概率均合计 `1.00`，九个主结果类
均预先冻结 management、owner cash、permanent loss、scenario 和 valuation direction 更新。

## Outcome custodian 最小合同

Custodian 只可读取一份在授权窗口内发布的发行人 FY2019 官方完整年报，只结算 03 已冻结的
产品、运营模式、研发、现金与固定资本字段和直接计算。

没有披露产品级活跃、充值或收入只限制核心归因，不得使集团现金、资本或整家公司判断变为
UNKNOWN。Custodian 不判断管理层、normalized owner cash、永久损失、情景、估值方向或训练
有效性；这些由 fresh reviewer 按结果前映射综合。

## 权限

本裁决只允许提交最小 outcome access authorization。不得标记或授予
`TRANSFER_VALIDATED`、`METHOD_FROZEN`、Comparative、CJO、正式估值、BuyBand、报告发布或
投资权限。
