# 益丰药房 revised-rule replication：独立结果前审阅

> reviewer：独立于 judgment owner 与未来 outcome custodian
>
> FY2018 outcome：`UNREAD`
>
> 最终裁决：`ACCEPT`

## 首轮退回及根因

首轮裁决为 `RETURN`，根因是 `REASONING + WRITING`，不是数据量或 acquisition module：

1. baseline 没有显式获得 enhanced 同样的 organic/acquired cohort 结果字段，可能因结果事实预算
   不同制造假 utility；
2. 公司级条件树把任意微小毛利或费用波动机械当作降级，重新把企业判断变成字段门槛；local
   tree 的正负分支也可能重叠；
3. cohort locality、group funding 责任边界和“一期负资金端点不等于误配”都已存在于原始
   baseline，却被误写成反馈后学习 delta。

经济影响是可能虚构成长价值、资本配置信用或永久损失的改善，并把非材料噪声或原 baseline
能力错误归功于新规则。结果开放前必须修复。

## 修复后的验收

### 同一事实预算

Baseline 和 enhanced 现在共同获得 `02∪03` 的一次性 outcome settlement。Organic 和 acquired
cohort 的收入/同店、店级利润、OCF/回收期、关闭/减值/处置字段对两臂都开放；原 narrative
没有结构化某个字段，不能阻止公平 baseline 注意到它。字段结构不再制造 utility。

### 经济材料性而非微小阈值

Custodian 只结算原始变化、责任边界和可比性；paired reviewer 结合收入、坪效、毛利、费用、
客户/监管事实和最强反方直接判断经济材料性。1 个基点毛利下降或费用增速高 0.1 个百分点，
不能机械撤销其他材料经营吸收。

Local cohort tree 唯一顺序为：

```text
material conflict
  → negative
  → positive
  → deployed-economics unavailable
  → unavailable
```

同一 cohort 的正利润和材料减值共存只能为 `MIXED`，不会同时落入 positive 与 negative。

### 真正学习干预已隔离

Cohort locality、group-funding scope、管理层分层和一期资金限制被标为
`SHARED_PREEXISTING_BASELINE_CONTROL`，禁止获得 utility。唯一前瞻干预是
`SIGNED_BOUNDED_UNCERTAINTY`：若 FY2018 有金额不完整但符号已知的非重叠战略现金，保留
符号并计算可行区间。

若 FY2018 没有这类材料性 incomplete term，或两臂得到相同投资处理和研究动作，必须结算
`NO_MATERIAL_UTILITY`。

## 现金责任边界

FY2017 的四个冻结端点算术正确：

- `OCF−capex = +RMB 110,475,305.46`；
- 调整已列营运资本后、扣全 capex：`+RMB 181,147,316.58`；
- statutory deployment endpoint：`-RMB 164,088,195.08`；
- post-working-capital group funding endpoint：`-RMB 93,416,183.96`。

后两者都只是一期集团资金端点，不是 normalized owner cash、cohort 回报、并购失败或资本误配
证明。

## Outcome custodian 最小合同

- 只读取一份截至 `2019-05-01` 已发布的发行人官方 FY2018 完整年报；
- 只结算 `02∪03` 共同事实预算的报告边界、原始同比、局部 cohort 披露、现金项目、已知符号
  与机械端点；
- 若非重叠战略支出事件存在但金额不完整，只记录责任边界、符号和可证明区间；不得把未知设零
  或发明上下界；
- 不访问价格、回报、后续年度、外部评论或已有结果结论；
- 不判断企业成功、管理层信用、资本误配、永久损失、估值方向或 paired utility；
- 公司网络某条趋势不比较时只局部降级，不取消其他公司判断；
- 产出一个 settlement，供两臂共同使用。

## 权限

本裁决只允许提交结果授权。`TRANSFER_VALIDATED`、method freeze、Comparative、CJO、正式
估值、BuyBand、报告发布和投资权限均不授予。
