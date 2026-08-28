# Historical Holdout 材料投资处理评价

日期：2026-08-28  
状态：`LOCAL_EVALUATION_CONTRACT / METHOD_NOT_VALIDATED`

## 要回答的问题

Historical Holdout 只回答一个问题：在同一公司、同一 cutoff、同一资料预算下，只增加冻结
Method Pack，是否让 Enhanced 在看到结果前采取了比公平 Baseline 更好的材料投资处理。

它不评价谁写得更长、字段更多、引用更多或预测概率更准。它也不把独立 reviewer 的积极措辞
直接当成训练效用。

## 结果前冻结

Baseline 与 Enhanced 都必须先完成 judgment-first 企业判断并冻结六个处理轴：

- 管理层执行信用；
- 正常盈利；
- parent owner cash；
- 永久损失约束；
- 内在价值方向；
- 唯一 rank-1 下一研究动作。

`UNKNOWN` 不是处理代码。证据不足时仍要回答当前如何处理，例如不计入 parent owner cash、
维持永久损失约束或暂不提高正常盈利。这样，过度保守也能被历史结果识别，而不是获得免费
退出。

两臂 treatment snapshot、机械差异、outcome cell 并集、forecaster 身份和 Method Pack 身份由
`historical-holdout-treatment-pair.v1` 一次冻结。Baseline 只能收到共同 judgment-first 合同；
Enhanced 的唯一额外输入是冻结 Method Pack。

## 结果后结算

独立 custodian 对 outcome cell 并集逐项结算：

- `OBSERVED`：合同匹配结果足以评价该 cell；
- `LOCAL_UNKNOWN`：值或归属缺失，只限制相关轴；
- `MEASUREMENT_MISMATCH`：责任边界、期间或定义不匹配，只限制相关轴。

独立 reviewer 只能评价结果前确实不同的轴，并必须引用与该轴直接绑定、状态为 `OBSERVED`
的 settlement cell。局部未知或口径不匹配不能被积极 reviewer 标签升级成效用。

机械裁决为：

- 两臂材料处理相同：`NO_MATERIAL_UTILITY`；
- 结果支持 Enhanced、反对 Baseline：`MATERIAL_UTILITY_CANDIDATE`；
- 结果支持 Baseline、反对 Enhanced：`HARMFUL`；
- 不同轴分别支持两臂：`MIXED_NOT_VALIDATED`；
- 结果不能区分：`NOT_DIAGNOSTIC`。

一个正向轴即可形成候选，因为 owner cash 或永久损失上的单个材料错误可能足以改变投资处理；
但候选仍只获得 `CANDIDATE_ONLY`，`TRANSFER_VALIDATED` 固定为 false。

## 不计训练效用

以下变化一律不计：

- ID、措辞、篇幅、引用和字段数量；
- 仅把机制解释得更清楚；
- 新增 outcome dependency 或多结算一个 cell；
- 概率、Brier 或方向预测更准确；
- 同一 treatment 下更精确的数字或更强语气；
- 结果后补写的 treatment delta；
- 公平 Baseline 本来也会采取的处理；
- reviewer 自报 `MATERIAL_IMPROVEMENT`。

## 权限

该合同不连接 J2/J3/J4 adapter，不产生 CJO、正式估值、BuyBand、报告或投资权限。它只是四阶段
历史训练中评价 Method Pack 是否产生材料增量的局部实验载体。
