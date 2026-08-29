# 课程一期结果后研究议程

> 状态：`ACTIVE_FOR_CURRENT_AGENT_SELF_REPLAYS`
>
> 依据：四份 Blind outcome feedback、独立审阅、广州酒家第二次 A/B 与玲珑轮胎 self replay
> [`PASS_WITH_LOCAL_NARROWING / COURSE_METHOD_NOT_VALIDATED`](outcomes/05_INDEPENDENT_OUTCOME_REVIEW.md)

第二次公平 A/B 已经完成；其 current-Agent 结果见
[`06_CN603043_CURRENT_AGENT_SELF_RUN_OUTCOME_FEEDBACK.md`](outcomes/06_CN603043_CURRENT_AGENT_SELF_RUN_OUTCOME_FEEDBACK.md)。
随后在轮胎制造这个结构不同、仓库零命中的公司上，玲珑 replay 再次显示：全资本开支后的
现金压力、维护后 owner cash 与增长资本回报会给出不同答案；参见
[`07_CN601966_CURRENT_AGENT_SELF_REPLAY_OUTCOME_FEEDBACK.md`](outcomes/07_CN601966_CURRENT_AGENT_SELF_REPLAY_OUTCOME_FEEDBACK.md)。
这使三笔资本账成为 current Agent 的实际研究顺序，但因为这些均不是认知隔离的外部 A/B，
并不提升方法验证状态。

## 这次反馈改变什么

首个公平 A/B 的负结果是一个明确的 `REASONING` 错误，不是资料数量、PIT、
Comparative 或谨慎程度的问题。顺丰 Enhanced 把“增长资本的回报尚未证明”推成了
“维护资本后的 owner cash 接近零或为负”。这既不由 FY2018 的经营现金，也不由全部
资本开支推出；它会把核心价值错误地压低，并夸大永久损失。

因此，下一次训练的变化不是多加检查项，而是改变判断顺序和可允许的推导：

```text
公司资本与现金事实
-> 分开维护资本、全部资本开支、增长资本后续回报
-> 再判断正常 owner cash、融资压力和永久损失
```

维护资本未知时，结论仍必须继续：给出条件式、将全资本开支后的现金压力作为真实事实，
并把增长资本回报的未证实性留在资本配置和永久损失路径；不得创造一个看似精确的
维护后现金点估计或窄区间。

## 四案写回的条件化经验

这些经验只可改变另一家公司的问题、证据顺序、最强反方和条件化处理，不能作为该公司的
事实或估值结论。

| 来源 | 处理 | 下一家公司先问什么 | 禁止的错误推导 |
| --- | --- | --- | --- |
| 天山股份 | `KEEP / NARROW` | 若公司边界发生并购或重组，原股东的普通股权益、每股现金、债务和资产回报如何桥接？ | 用重组后集团总量结算重组前企业，或把 dilution 本身等同于永久损失。 |
| 九阳股份 | `NARROW` | 历史利润区间代表周期下沿、产品红利，还是尚未被验证的正常中枢？毛利、费用、投资收益和现金分别怎样变化？ | 用短期历史利润直接设定保守下沿，或用一个较弱后期直接宣布永久新中枢。 |
| 顺丰控股 | `RETIRE / KEEP` | 经营现金、维护资本、全部资本开支和增长资本的回报，分别说明什么？服务与客户入口是否真正穿过同边界成本和资本责任？ | 把增长回报未证明或全部资本开支，偷换为维护资本或维护后现金的符号。 |
| 桃李面包 | `KEEP / NARROW` | 具体区域、产品或网络 cohort 的利用率、利润和现金是否支持复制？管理动作与结果之间是否有同边界中介证据？ | 用全国销量、单一成功 cohort、基地数或管理动作时序证明普遍复制或因果成功。 |

## 第二次公平 A/B 的实际研究顺序

第二个候选必须先通过“仓库零命中”筛选：在新资料进入仓库前，股票代码、中文名和常用
英文名均不得在仓库既有研究、测试、数据或文档中出现。选择不得读取结果窗口、价格、
回报，或按预期 Enhanced 胜率挑选。

对选出的单一公司，两个 arm 都按以下顺序完成一份完整
`EnterpriseUnderwritingEpisode`：

1. 用截止日前公司源包重建行业未来、利润池与公司责任位置；
2. 找出一个材料性经营矛盾及最强相反解释，而不是先找一个易结算字段；
3. 当资本或现金对承保重要时，分别列出经营现金、全部资本开支和可观察的维护/增长边界；
4. 以同一责任边界连接客户吸收、单位经济、正常盈利、owner cash 与永久损失；
5. 给出当前最佳处理、最强反方和最早翻转事实，即使局部维护资本、分部利润或 cohort
   数据仍未知；
6. 只在 Episode 验证并冻结后打开结果窗口。

Baseline 只读公司结果前源包；Enhanced 在相同公司源包、同 cutoff、同 schema 和相近预算
之外，读取本议程和 [`08_CAPITAL_AND_BOUNDARY_REASONING_REVISION.md`](08_CAPITAL_AND_BOUNDARY_REASONING_REVISION.md)。
这两份训练材料是问题设计，不是公司证据，不能写入 `evidence_trace`。

## 第二次 A/B 的材料性标准

Enhanced 只有在下列任一项基于**当前公司截止日前材料**发生可解释的变化时，才可能优于
Baseline：行业利润池传导、公司责任位置、正常盈利的中心或边界、owner cash 的条件化
处理、永久损失路径、价值路线，或最早能区分两个解释的观察。仅增加文字、UNKNOWN、
问题数、保守扣减或把所有增长放入悲观情景，都不是改善。

即使 Enhanced 出现材料变化，独立结果后审阅仍可判为 `WORSE`、`NO_MATERIAL_UTILITY` 或
局部有用。第二次 A/B 只能测试修订后的推理是否值得继续；它不授予
`TRANSFER_VALIDATED`、`METHOD_VALIDATED`、CJO、估值、报告发布或投资权限。
