# Judgment-First 企业承保训练第一期课程

> 状态：`12_WORKED_CASES_COMPLETED / 4_BLIND_OUTCOME_FEEDBACK_COMPLETED / FIRST_FAIR_A_B_ENHANCED_WORSE / METHOD_NOT_VALIDATED`
>
> 冻结基线：本地受保护主线 `main@eadaae9dedbf4cf1c3ac621031bb18fd0f4d49f0`
>
> 训练 kernel：由该基线直接提供；不得从其祖先 `a115456` 或已分叉的
> `origin/main` 恢复课程

> 结果反馈独立审阅：[`PASS_WITH_LOCAL_NARROWING / COURSE_METHOD_NOT_VALIDATED`](outcomes/05_INDEPENDENT_OUTCOME_REVIEW.md)

## 中心任务

本课程训练一条连续的企业判断，而不是字段完成率：

```text
行业环境
-> 公司位置
-> 生存与适应
-> 正常盈利与 owner cash
-> 永久损失
-> 价值路线
-> 未见公司黄金报告判断层
```

第一阶段按 `01_FROZEN_WORKED_CASE_ROSTER.json` 的顺序完成十二个结果已知
`WORKED_CASE`。四个行业各保留优势公司、普通或转型公司、失败或 near-miss
公司。结果已知只用于学习机制，不计能力、迁移或方法优越性。

第二阶段按 `02_FROZEN_BLIND_REPLAY_ROSTER.json` 的顺序完成四个
`BLIND_REPLAY`。每个 Episode 在结果揭示前冻结，并在揭示后分别诊断行业未来、
公司位置、生存、适应、正常化、owner cash、永久损失和价值路线。不得以单字段
命中率代替判断反馈。

第三阶段只保留真实改变下一家公司研究问题、证据顺序、参考类别或投资处理的机制。
最后对一个未见公司做同 cutoff、同证据、相近研究预算的 Baseline 与
Training-Enhanced A/B，并让增强后的 `IndustryUnderwritingContext` 进入黄金报告
判断层。只有企业处理、正常盈利、owner cash、永久损失、价值路线或同口径经济范围
发生有理由的材料变化，才算训练增量。

## 反防御性写作约束

- `UNKNOWN` 只限制相应主张；每案仍须给出最佳当前方向、最强反方、投资处理和翻转事实。
- 缺精确维护资本时给出保守范围或条件性 owner-cash 处理，不得终止整家公司。
- 扩产、投产、并购、收入或利润改善都不是经济成功；继续追踪客户、利用率、单位经济、
  现金吸收和资本回报。
- 未证明的增长不进入基准，但保留为具名情景，不把它写成零价值或企业失败。
- 不因 mismatch、缺同行或 Comparative 新增全局 gate。
- 课程成功不由文件数、字段数、收据数、validator 数或“没有犯错”定义。

## 权限

本课程只产生研究训练、反馈、条件化经验和黄金报告候选判断层。除非未见公司 A/B
确实改善材料性投资处理，不授予 CJO freeze、正式数值估值、BuyBand、发布或投资权限；
无论结果如何，均不得标记 `TRANSFER_VALIDATED` 或 `METHOD_VALIDATED`。
