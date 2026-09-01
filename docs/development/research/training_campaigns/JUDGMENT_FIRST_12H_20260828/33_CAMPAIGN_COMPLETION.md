# Judgment-First 12 小时训练迭代：最终交付

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 当前结论：`STOPPED_BY_USER / PARTIAL_REAL_EFFECT / METHOD_NOT_VALIDATED / TRANSFER_VALIDATED=0`
>
> 本文不使用证券价格或回报，不构成正式估值、BuyBand、报告发布或投资行动。

## 结论先行

这轮训练不是“完整方法已经有效”。它取得了三个更窄、但真实的成果：

1. 在口子窖直接纠正了企业判断：核心实物吸收比预期弱，省外收入、销量、毛利和渠道广度比预期强；
2. 在家家悦发现并废弃了一条有害规则：精确金额未知时先写 `UNKNOWN` 会擦除已经确定的负现金方向；
3. 通过四次公平 baseline 的零结果，确认更多字段、更细分类和更清楚解释本身没有投资效用。

```text
直接企业判断纠正          1  CN603589 口子窖
有害规则                  1  CN603708 家家悦
NO_MATERIAL_UTILITY       4  CN002080 / CN600570 / CN603939 / HK00184
TRANSFER_VALIDATED        0
```

因此方向没有错，但此前系统确实长期奖励错了东西。当前最可信的改进不是“Agent 更会证明安全”，
而是它能在同一家公司内同时保留正面经营证据、负面现金载体和局部未知，并允许结果向上或向下纠正。

用户在原十二小时下限到达前主动停止 Goal，因此本工件不宣称满足十二小时持续窗口。停止不撤回已经
完成的六轮反馈、运行时修复和两个 future holdout，也不把未完成时长包装成训练成果。

## 六轮后投资者真正学到什么

### 中材科技

锂膜已经从建设进入客户和收入吸收，但责任单元营业利润仍负、现金变弱。管理层建设执行中高，客户与
商业化有证据改善，资本配置仍为低条件性。集团付得起二期不等于项目值得投入；锂膜不进入基准成长
价值。Enhanced 与公平 baseline 同处理，效用为零。

### 家家悦

成熟零售网络仍有经营基础，跨区域、并购与物流经济性未证明。扩张资金端点即使保留未知项，最乐观
方向仍为负，因此不能写成 `UNKNOWN`。管理层开店、并购和接入执行可信，但新域资本配置信用下调；
核心可研究正常盈利，新域成长价值为零并提高永久损失折价。这一案真实否决了 `UNKNOWN-first`。

### 恒生电子

成熟金融 IT 核心吸收为正，仍受监管需求周期约束；AI、区块链和云有部署，没有独立重复经济性。
集团现金方向代理为正，但战略资金残差可跨零，不能写成 core owner cash，也不能把跨零区间强写成负。
新增 options 只保留选择权，不给独立基准成长价值。Enhanced 没有改变公平 baseline。

### 益丰药房

网络和并购部署成功，当前单位吸收混合；经营网络正现金不足以覆盖完整收购扩张需求。管理层部署能力强，
cohort 回报和资本纪律未证明；新增或收购 cohort 不给基准成长价值，债务、商誉和重复负资金提高永久损失
折价。两臂处理相同，效用为零。

### 口子窖

安徽成熟核心仍强，但增量更依赖价格和结构，高档实体销量没有同步证明；省外出现比结果前判断更真实的
收入、销量、毛利和渠道广度。管理层省外执行上调为中高条件性，省外只获得有限成长选择权。强 OCF 和
零有息债务只降低融资型下行，不取消品牌、区域重复性、陈化库存和固定资本风险。当前下一期情景为
`30% / 58% / 12%`；旧 `30% / 62% / 8%` 与粗粒度 score 已明确 superseded。

### 激成投资

FY2022 不是“只有重开”：八家固定酒店中六家同时出现 occupancy、ADR 与同物业本币 RevPAR 改善；
受控酒店 recurring EBIT 和 pre-D&A 均由负转正，酒店经营执行应上调。集团扣 reported capex、OCF 外
利息和 NCI 股息后的方向代理约为正 `HK$191.8m`，但 maintenance 与 parent access 未闭合，不能称
normalized parent owner cash。一年内或按要求偿还银行债约 `HK$1,359.3m`，waiver 依赖仍在，永久损失
保持中等、条件性。公平 baseline 会作出同样处理，因此效用仍为零。

## 管理层判断怎样变得更有用

训练不再给管理层一个总分，而是区分证据所在的层级：

```text
建设 / 开店 / 并购 / 上线 / 重开
    -> 客户采用与量价吸收
    -> 责任单元利润和现金
    -> 投入资本回报与普通股价值
```

中材、家家悦、益丰、恒生和激成都证明部署能力不能替经济吸收或资本回报投票。口子窖省外则提供了
一个向上纠正实例：当收入、销量、毛利和渠道广度共同改善时，不能继续用“资料不够”维持过度悲观。

## 仍然 UNKNOWN，但没有终止公司判断

- 中材锂膜二期的责任匹配订单、单位经济和成熟项目回报；
- 家家悦新域、维客与物流的独立利润/现金及未知外部投入精确金额；
- 恒生新增技术的重复收入、利润和战略投资回报；
- 益丰新建与收购 cohort 的成熟期单位经济和 normalized owner cash；
- 口子窖终端动销、省外改善重复性与陈化库存 cohort 回报；
- 激成酒店的真实 maintenance、集团现金上游与已完成再融资；
- 吉比特和泛微 FY2019 outcome，仍因浏览器任务空间被用户接管而封存。

这些未知只限制相应项目价值、归因、现金正常化或永久损失主张，不撤回成熟核心、已知现金方向、
管理层部署事实或当前资产负债表判断。

## 训练行为已经怎样改变

1. 先作当前最合理企业判断，再让证据纪律服务该判断；不能用 gate、receipt 或字段状态替代结论。
2. Baseline 必须拥有同一事实预算和普通投资者能力；强 baseline 已会做的事情不计学习。
3. `known negative endpoint - X, X>=0` 保留负方向；只有区间确实跨零才写 mixed。
4. 经营、owner cash、资本配置和永久损失分别沿责任匹配轴传播，一个轴不能替另一个轴投票。
5. 缺披露、市场输入、同行资格或局部 measurement mismatch 只关闭依赖它的主张或动作。
6. 缺失信息只有在会改变当前判断时才获得研究预算；`NEEDS_CURATOR` 不是免费出口。
7. Forecast 弃权、正确预测、modal tie、相同 baseline 或无法机械识别的错误不产生学习 policy。
8. 当前 decision-utility schema 没有可比较的材料投资处理载体，因此新增 outcome cell、概率差异、
   OBSERVED 结果和 reviewer 积极标签都只能 `NOT_DIAGNOSTIC / NONE`。
9. bound Frozen CJO 直接确定性生成公司判断研究产物，不再先写十五章自由结论再与 canonical 结论并列。

## 真正未来的检验已经冻结

为停止围绕已知历史结果优化，本轮在完整 FY2026 结果客观不存在时冻结了两个异质 holdout：

- `CN601899 紫金矿业`：检验上产与并购能否穿过同口径单位经济、项目资本、NCI 和资金期限，形成
  可持续归母现金；当前判断为生产部署强、经济吸收条件性、集团现金强但 normalized parent owner cash
  未闭合、永久损失 `LOW_TO_MEDIUM_CONDITIONAL`。
- `HK00696 中国民航信息网络`：检验交易量与网络位置能否穿过定价、项目验收、客户结算 pass-through、
  系统再投资和资金限制，形成平台经济与普通股现金；当前判断为客户位置强、monetization 条件性、
  reported 现金改善但 ex-pass-through owner cash 未闭合、永久损失 `LOW_CONDITIONAL`。

两家公司均已独立结果前审阅，outcome 保持 `SEALED`，不计当前反馈、transfer 或方法有效。FY2026 完整
年报存在前不读取中报提前结算，不按结果重选公司、cell 或 first-match。

## 仍未证明与权限

- 没有任何完整 Enhanced 方法获得 prospective transfer validation；
- 一次直接判断纠正和一次有害规则发现不能证明跨公司普适；
- 六轮没有使用价格或回报，不能证明实际投资收益改善；
- runtime validator、测试和确定性报告只证明已知奖励错位被移除，不等于投资能力；
- J2/J3/J4 adapter、`GOALS.md` 与 `docs/CURRENT_DOCUMENTS.md` 在本 campaign 净变更中保持不变；
- 不授予 Comparative、CJO 方法冻结、正式估值、BuyBand、报告发布或投资行动权限。

## 工件与验证

主要工件：

- 六轮总结：`25_SIX_REAL_FEEDBACK_AND_RUNTIME_REWARD_RESOLUTION.md`；
- 第六轮投资者读本：`episodes/EJE_HK00184_20220501/prospective_local_contingency_v1/08_INVESTOR_READOUT.md`；
- 紫金 future holdout：`27`、`28`、`29`；
- 民航信息网络 future holdout：`30`、`31`、`32`。

代码集成验证已经覆盖本 campaign 实际改动的 active agent、CJO、Forecast/control、decision utility、
research routing、quality 与 valuation-localization 路径：campaign 变更测试集 `467 passed`；
decision-utility/Forecast 定向复验 `65 passed`；恢复 J3 adapter 后运行时边界 `48 passed`。后两组与前一组
存在重叠，不能相加冒充测试数量。最终 HEAD 的项目守卫与 merge-check 在提交本文件后执行；原十二小时
Goal 已由用户停止，不以时长作为完成声明。
