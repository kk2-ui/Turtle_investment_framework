# V3 首份读者报告协议

> 状态：`FROZEN_BEFORE_V3_EPISODE_BINDING`

每一臂只有在其原始 Episode 通过该臂 `run --agent-response` 正式绑定后，协调者才可用 `compile-reader-brief` 从已持久化的 `enterprise_underwriting_episode.json` 机械生成 `reader_briefs_v3/<arm>.json`。brief 是唯一可以交给作者的报告输入；它不包含训练合同、匿名映射、其他 arm、结果期、价格、回报、估值数值或内部 validator 语言。

同一生成该臂 Episode 的 fresh Agent 将收到一次 follow-up，只读取这份 brief，输出一份首次中文读者报告（最多 14,000 CJK 字符）到 `reader_reports_v3/<arm>.md`。报告必须：

- 以投资者能挑战的因果顺序说明行业路径、公司传导、生存/适应、正常盈利、普通股现金、永久损失、价值路线、最强反方和翻转观察；
- 只转述 brief 已有的判断和来源约束，不读取、引入或推断 brief 外事实；
- 不写价格、回报、估值数值、BuyBand、行动指令、结果期或 arm 身份；
- 不把 `UNKNOWN`、字段名、模型名、validator、token、任务或训练过程暴露给读者；
- 不重写、不增补 Episode，也不因写作需要改变任何经济处理。

不提供重写、评分反馈或第二版。若任一 Episode 绑定失败，则该臂没有读者报告，四臂也不得进入匿名审阅或结果开封。
