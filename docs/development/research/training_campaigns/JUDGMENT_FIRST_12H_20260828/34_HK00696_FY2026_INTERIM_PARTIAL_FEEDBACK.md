# HK00696 FY2026 中报：局部反馈记录（非正式结算）

> 状态：`PARTIAL_FEEDBACK_RECEIVED / NO_FORMAL_SETTLEMENT`
>
> 对应结果前判断：`FUTURE_HOLDOUT:HK00696:20260501:FY2026:V1`
>
> 本记录不读取价格或回报，不修改冻结判断，不产生 transfer、CJO、估值或投资权限。

## 目的与边界

FY2026 中报已经公开。本记录只把中报能够直接支持的事实接回结果前判断，区分“已观察到的方向”和“仍未关闭的经营传导”。中报不是冻结的 FY2026 完整年报 outcome contract，因此不把局部事实包装成完整 settlement，也不因资料不全把整家公司重置为 `UNKNOWN`。

## 可以更新的事实

### 客户/服务轴：服务向量确实出现分化

- 平台服务收入同比下降约 1.7%；结算服务收入同比增长约 11.4%；机场数字化收入同比增长约 43.5%。
- 这与结果前对“ETD、平台、结算和机场项目不能合并”的关注一致：机场项目的增长可能由验收节奏驱动，不能代替核心平台的客户吸收；结算增长也不能覆盖平台服务下降。
- 因而可将当前观察更新为：`MIXED_SERVICE_VECTORS_OBSERVED`。平台服务已出现负向收入方向，结算和机场数字化出现正向收入方向；不能据此推出整体定价能力改善或恶化。

### 机场项目轴：验收型增长仍需与回款和项目经济分离

机场数字化收入回升是可记录的经营事实，但仅凭中报收入不能判定项目回报改善、客户持续吸收或现金收回。该事实应把“项目收入方向”从原来的等待观察更新为 `REVENUE_UP / ECONOMIC_RETURN_UNSETTLED`，而不是把收入增长写成经营质量升级。

### 报表结果轴：利润/收入不能替代 owner cash

中报显示总收入和净利润增长，但目前没有足够信息完成结果前合同要求的：

`reported OCF → 扣结算 pass-through → 扣系统长期资产投入 → 扣 NCI / 维护需求 → parent-accessible owner cash`

所以只能更新为“报表结果出现改善信号”；不能更新为 `operating_cash_ex_pass_through=POSITIVE`、`post_system_capex_and_nci_proxy=POSITIVE` 或 normalized parent owner cash 改善。

## 仍不能正式结算的事项

以下主张保持局部未结算，而不是扩散成全公司否定：

- ETD 处理量、结算交易量及各自可比 monetization 的完整桥接；
- 平台收入下降究竟来自价格、客户组合、服务组合还是交易量；
- 机场项目的验收、应收/合同资产和回款是否共同改善；
- 结算代收代付 pass-through 与经营现金的调和；
- maintenance 与 growth capex、NCI 分配及母公司普通股东现金可达性；
- 新管理安排是否同时维持系统可靠性、商业纪律和资本效率；
- 系统/网络安全、监管、客户关系或金融资产是否出现永久损失载体。

中报也没有授权读取价格来反推市场评价；因此不更新估值方向、最高可接受买价或投资处理。

## 下一 cutoff 的研究行为变化

结果前动作已经因首轮反馈采用 `perimeter-first`：先确认责任边界和可比轴，再谈增长或现金。这是测量方法修正，不是对 HK00696 企业质量的事后洞察。中报使下一次研究动作进一步具体化：

1. 先分别抓取 ETD、结算交易、平台收入、结算收入和机场项目收入，不以总收入或利润作替代；
2. 将机场收入拆成验收、应收/合同资产与收现，不能用单期收入增长完成项目经济判断；
3. 先建立结算 pass-through 的现金桥，再处理系统 capex、NCI 与 parent access；
4. 将平台服务下降作为必须解释的负向事实，不能让结算或机场正向事实覆盖它；
5. 只有完整 FY2026 年报满足冻结 cell 的 first-match 条件时，才由独立 custodian 正式结算。

## 反馈性质与防御性写作检查

本记录没有把“无法正式结算”当作结论，也没有把部分正向数据当作升级理由。事实层面已有局部更新；经济传导尚未闭合的地方保留在对应 cell。该中报目前改变的是下一次研究顺序和拆分方式，尚未证明 Enhanced treatment 改变了 material investment treatment，因此：

`current_feedback_credit=NONE`

`learning_authorization=NONE`

`transfer_candidate=NONE`

`transfer_validated=NONE`

待完整结果窗口到达后，独立 custodian 只结算合同匹配的经营或现金 cell；若某一 cell 发生 measurement mismatch，仅局部降级并保留其他已观察事实。
