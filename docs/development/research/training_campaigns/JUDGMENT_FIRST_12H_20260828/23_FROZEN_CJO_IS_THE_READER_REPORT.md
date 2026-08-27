# Frozen CJO 是公司判断报告的唯一真源

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`ONE_COMPANY_JUDGMENT / DETERMINISTIC_READER_ARTIFACT`

## 被纠正的问题

旧的 company-judgment-only 路径先读取 Frozen CJO 摘要，再生成十五章自由正文。摘要可以判断“渠道
重置改善经营引擎”，正文却写成“渠道重置破坏客户留存、收入结构性恶化”；只要章节主题和来源
格式齐全，两种相反判断仍可能一起进入最终产物。

这不是普通写作瑕疵。它让 canonical 企业判断退化成开头的免责声明，并奖励 Agent 用更多章节
生成第二套结论。

## 当前运行路径

当分析合同为 `COMPANY_JUDGMENT_ONLY` 且绑定 Frozen CJO 时，普通模式和 PIT 模式都只允许：

```text
读取报告合同
    -> 读取当前 JUDGMENT_SYNTHESIS handoff
    -> 确定性组装 COMPANY_JUDGMENT_RESEARCH
```

运行时不加载十五章模板，不读取或拼接自由章节与技术附录，不调用估值、买价、决策或交易工具；
stale/unready handoff 直接阻断，不回落自由写作。最终正文必须逐字等于 canonical renderer，额外
添加一段相反结论也不能完成。

## 读者实际得到什么

确定性报告从同一个 Frozen CJO 呈现：

- 公司、cutoff、独立复核与责任边界；
- 产品/服务、客户任务、竞争机制及其责任单元；
- 经营变量、状态与状态变化；
- 管理层决策事件、记录状态及 `from_status -> to_status` 执行序列；
- 每条机制所属的责任单元和经营场；
- 当前中心路径、前瞻公司判断、翻转条件和 trace；
- 正常盈利、owner cash、永久损失三个独立传导轴；
- 最强反方、局部 UNKNOWN、closing evidence 与监控信号；
- trace/source 对照与证据边界。

自由正文不能补洞。若旧 Frozen 对象没有新投影，报告只在对应区块写“未冻结”；若没有观察到
状态变化或管理决策，仍保留其余企业判断，并明确不能区分 no-action 与未披露。系统不会为了让
报告完整而虚构行动、事件或来源。

## 复核与局部证据语义

新 shape 的 reader projection 必须存在于独立 review receipt，并与当前 Frozen 对象逐字段相等。
删除该复核副本不能把新对象伪装成 legacy；事后改写客户任务、状态值或管理决策，即使重新录入
handoff receipt，也无法完成。

证据要求复用上游经济语义：直接 `OBSERVATION` 和有方向的金融传导需要证据；`INFERENCE`
mechanism 以及 `UNKNOWN/NONE` 传导可以没有直接引用，只要保持其推理/未知身份。这样既阻止
事后改写，也不把推理和局部未知重新变成补字段硬门。

## 权限边界

产物身份是 `COMPANY_JUDGMENT_RESEARCH`，`published=false`，publication/investment authority
均为 false。该路径解决的是“一家公司只能有一个读者可见判断”，不授予 CJO 方法冻结、正式
估值、BuyBand、完整投资报告发布或投资权限。
