# R-23：2006 年结果复盘——流程图不能代替可收回的应收

前置冻结卡：[2006 年宏盛科技海外贸易链信用治理判断卡](01_2006_pre_outcome_enterprise_judgment_card.md)。

状态：`RESULT_KNOWN_TEACHING / OUTCOME_RESOLVED_FOR_MECHANISM / AUDIT_QUALIFIED / NO_TOTAL_COMPANY_VERDICT`。

## 1. 结果只回答冻结问题

| 观察 | 2006 年结果 | 对机制的意义 |
|---|---:|---|
| 合并经营现金流 | -3,183 万元；净利润为 6,074 万元。 | 盈利没有转成经营现金。 |
| 前五客户/供应商占比 | 客户 99.73%，供应商 99.99%。 | 高度集中并未因流程文件而消失。 |
| 审计核心事项 | 年末境外应收中 17,399.29 万美元（折合 13.59 亿元、占总资产 37.28%）超过合同期未收回；审计师无法实施替代程序取得充分适当证据认定其可收回程度，因而出具保留意见。 | 直接击中“保险/保理/共管可确保回款”的冻结箭头。 |
| 审计边界 | 保留意见不自动等于全部应收为零，也不单独证明哪一笔 P/O、保险或管理动作失败。 | 不能将保留意见升级为个人品格或总公司经济性的判决。 |

来源：[宏盛科技 2006 年年度报告](https://finance.sina.com.cn/stock/company/sh/600817/9_17.shtml)，公告日 2007-04-30。审计报告明确限定的是境外应收可收回性的证据，不使用后来的重组、媒体、价格或回报扩展本结论。

## 2. 逐箭头结算

| 冻结箭头 | 结果 | 结算 |
|---|---|---|
| 早期：信用链能否确保合同期收款 | 巨额境外应收超过合同期未收回，审计师无法取得其可收回程度的充分适当证据。 | `SUPPORTS_RIVAL_FOR_COLLECTION_CONTROL`。无论流程在纸面上多完整，结果没有支持“已锁定公司回款”。 |
| 经营现金：增长能否穿过信用链 | 净利润为正而 OCF为负。 | `SUPPORTS_RIVAL_FOR_CREDIT_TO_CASH`。在冻结维度上，账面盈利不能证明该信用结构产生 owner cash。 |
| 风险工具：保险/保理/共管是否有效 | 结果期没有将每项工具、保额、索赔、实际到账与逾期应收逐项对齐；审计保留意见反而使公司数值解释受限。 | `UNKNOWN_FOR_INSTRUMENT_EFFICACY`。不能说保险/保理必然无效，只能说它们没有被结果包验证为足以确保该应收可收回。 |
| 管理决策质量 | 公司当时有公开的流程选择与相反预测；但结果没有逐笔订单、执行人、保单与因果反事实。 | `NO_MANAGER_MORAL_OR_SKILL_VERDICT`。本案评估的是机制，不给个人贴道德或能力标签。 |
| 公司总经济性 | 审计限制、供应链集中、融资与其他业务均可能影响公司。 | `UNKNOWN / NO_TOTAL_COMPANY_VERDICT`。 |

## 3. 对企业家判断的实际学习

1. **“终端大客户”不是公司现金权。** 中间经销商、保理机构、保险人、银行与最终零售商共同出现时，必须逐段问谁承担取消、价格、退货、回款和追索；不能把最终品牌名往回投射为公司资产质量。
2. **控制文件的存在不是控制已生效。** 保险、共管账户、L/C 和流程图是机制假设的输入；合同期内回款、独立审计证据和现金流才是输出。
3. **高度集中会放大链条的任一断点。** 本案前五客户/供应商均接近全部交易，故看起来每一步“可控”仍无法替代对实际单据、收款和可收回性的验证。
4. **审计保留意见要改变结论的强度。** 它不是“坏账已经全部发生”，也不是可忽略的脚注；正确处理是把工具效果、正常盈利和公司总经济性降为 `UNKNOWN`，但仍让逾期应收反驳“回款已锁定”这一个窄命题。

## 4. 飞轮更新

R-23 将 R-21/R-22 的四项信用工具拆分进一步改为一个可操作顺序：

`counterparty_chain_identity → contractual_control → realized_collection → independent_verification → cash_conversion`。

只有前一项可验证，后一项才可被用作机制输入；公司自己的流程描述只能进入 `contractual_control` 候选，不可跳到 `realized_collection` 或 `independent_verification`。未来正例必须显示同一链条中的第三方回款/保单/审计证据，而非只增加流程说明。

根因：`REASONING + DATA_COVERAGE`。将复杂贸易结构、保险、共管或知名终端当作资产可收回性，会高估正常盈利和 owner cash；将保留意见直接翻成全部欺诈、全额坏账或公司必败，同样越过证据。缺失事实是逐订单 P/O、保单额度和索赔、共管账户流水、经销商与终端的权利责任；禁止用后续故事、价格或回报填补。验收是下一张信用正例在 cutoff 前和结果期均能逐项穿透这一链条；否则仅作为边界教学，不计算准确率。

本案最终判断：`EARLY_MECHANISM = SUPPORTS_RIVAL_FOR_COLLECTION_CONTROL`；`TERMINAL_OPERATING = SUPPORTS_RIVAL_FOR_CREDIT_TO_CASH`；`INSTRUMENT_EFFICACY = UNKNOWN_FOR_INSTRUMENT_EFFICACY`；`SELECTION = MECHANISM_SELECTION_ADMITTED`；`DECISION_LOGIC = NO_MANAGER_MORAL_OR_SKILL_VERDICT`；`TOTAL_COMPANY_ECONOMICS = UNKNOWN`。
