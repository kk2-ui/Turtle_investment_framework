# Historical Holdout 训练记忆修正

日期：2026-08-28  
裁决：`NO_METHOD_INPUT = NOT_EVALUABLE_FOR_TRAINING`

## 根因

根因是 `MODEL + REASONING`：此前把“新 Agent 没看过目标公司结果”误当成了“训练后的能力被独立检验”。
但当前系统没有修改模型权重；Agent 能继承训练的唯一机制，是在结果隔离后显式收到已经冻结的通用研究方法。
如果 Holdout forecaster 既没有会话记忆，也没有 Method Pack，它只能反映通用模型与判断优先提示词的当次表现，
不能回答课程是否让 Agent 变强。

经济影响是高估训练成效：一个没有接收训练产物的 single-arm 结果，即使方向正确，也不能证明 Blind 反馈、
Teaching 课程或候选规则产生了任何增量判断效用。

## 对天坛生物历史工件的处理

天坛生物 FY2024 的结果前判断、结算和投资者摘要仍是可读的公司研究记录，但它不再计入 Historical Holdout
训练样本、能力证据、方法效用或迁移证据。课程中的状态改为：

`ARCHIVED_NOT_EVALUABLE / NO_TRAINING_METHOD_SUPPLIED`

原因不是判断内容错误，而是实验没有把任何冻结训练方法交给 forecaster，也没有同 cutoff、同资料预算的公平
Baseline。它的 `METHOD_UTILITY=NOT_APPLICABLE` 应解释为“该实验不能评价训练效用”，而不是一种较弱的成功。
其结果后提出的正交经营—现金建议也不进入当前 Method Pack，避免用无效 Holdout 反过来训练同一方法版本。

## Agent 如何真正记住训练

正确的 Holdout 输入链是：

```text
已完成的 Teaching 与 Blind feedback
  -> 只抽象通用研究行为，不保留公司身份、结局或答案
  -> 冻结 Method Pack v1
  -> 选择尚未读取结果的独立公司与 cutoff
  -> fresh Baseline：共同 judgment-first 合同 + cutoff 前资料
  -> fresh Enhanced：完全相同输入 + Method Pack v1
  -> 两臂先冻结材料性投资处理
  -> 独立 custodian 揭示相同结果
  -> 比较管理层、正常盈利、owner cash、永久损失、估值方向和下一研究动作
```

隔离的是目标公司的结果、答案和结果后叙事，不是冻结的通用方法。Baseline 与 Enhanced 的唯一预定差异应是
Method Pack；两臂都不知道目标结果。

## 当前冻结的训练记忆

[`37_FROZEN_TRAINING_METHOD_PACK_V1.json`](./37_FROZEN_TRAINING_METHOD_PACK_V1.json) 只保留两个由 Blind
反馈产生的候选研究行为：

1. 规模、销量、收入或部署增长必须先穿过同责任边界的经常利润或单位经济桥，才允许进一步升级；
2. 利润增速落后收入、毛利率下降、资本开支快于利润同时出现时，保留已支持的优点，但暂停进一步升级，
   等待利用率、单位经常利润或现金回报解释增量资本。

二者都只是 `CANDIDATE_BEHAVIOR_NOT_VALIDATED`。Method Pack 不包含训练公司的身份、数值、结果摘要、
目标 Holdout 信息、估值答案或投资动作权限。

## 评价规则

- Enhanced 写得更长、字段更多、口径更细或语气更自信，不计效用；
- 两臂材料投资处理相同，结论是 `NO_MATERIAL_UTILITY`；
- Enhanced 更保守但没有避免真实错误，不计效用；
- 只有结果前处理不同、结果能区分两种处理，且 Enhanced 避免了 Baseline 的材料投资错误，才形成有界候选；
- 一个正例不等于 `TRANSFER_VALIDATED`，也不授予估值、BuyBand、报告或投资权限。

## 当前状态

课程的真实完成数是：15 个 Teaching、3 个 settled Blind、0 个可评价 Historical Holdout、2 个尚未完整
结算的 Prospective。当前 Method Pack 已冻结，但尚未在独立 Holdout 的公平双臂实验中使用，因此：

`METHOD_NOT_VALIDATED / TRANSFER_VALIDATED=0`

下一阶段仍以历史 Teaching 与 Blind 扩量为主；等候选方法更稳定后，再按本文双臂合同执行真正的 Historical
Holdout。packet builder 只准备输入，不证明 Agent 实际隔离；正式运行仍需两个 `fork_turns=none` fresh Agent
及各自 execution receipt。
