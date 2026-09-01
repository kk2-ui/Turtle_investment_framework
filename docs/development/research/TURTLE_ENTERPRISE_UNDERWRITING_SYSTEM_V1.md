# Turtle 企业投资承保系统 V1

> 状态：`TOP_LEVEL_DESIGN_AUTHORITY / UNDERWRITING_KERNEL_IMPLEMENTED / WORKED_CASE_ONLY / BLIND_REPLAY_PENDING`
>
> 日期：2026-08-29（Asia/Shanghai）
>
> 中心目标：训练 Agent 形成可帮助投资者判断一家企业能否长期生存、怎样恢复或复利、正常情况下能产生多少普通股现金、哪里可能发生永久损失，以及什么价格才值得承担这些风险的能力。

## 0. 投资者结论

Turtle 当前不是缺少更多字段、更多训练 lane 或更严格的验证器。真正缺少的是一个对象，能够从头到尾拥有这条投资推理：

```text
宏观与行业处境
  -> 周期波动还是结构性毁灭
  -> 客户和价值链怎样把变化传给公司
  -> 公司竞争位置、管理行动和适应能力
  -> 流动性、负债和生存能力
  -> 正常盈利、资本需求和 owner cash
  -> 永久损失路径
  -> 适用的价值路线
  -> 当前价格、安全边际和研究/买入处理
```

本文把这个对象定义为 **`EnterpriseUnderwritingEpisode`（企业投资承保 Episode）**。

这里的“承保”不是保险术语移植，也不是给企业打分。它回答的是：投资者愿意依赖哪些未来经济能力、哪些只能作为选择权、哪些必须从基准情景排除，以及在什么价格和翻转条件下才愿意承担风险。

现有 PIT、来源、责任边界、EnterpriseSystemModel、ManagementDecisionLedger、Judgment Experience Memory、Frozen CJO、估值和报告系统全部保留。V1 不建立第二个事实库；它把这些能力收束为一条投资者可读、训练可反馈、下游可复用的完整主张。

## 1. 为什么现有架构仍未达到中心目标

现有系统已经具备很强的工程底座，也完成了真实反馈、经验调用和局部判断纠正。但它仍把完整投资问题拆散在：

- 七个系统层；
- 八维企业判断问题；
- E0--E3 与 J0--J4 准入/投影；
- Teaching、Blind、Holdout、Prospective 多种样本身份；
- CJO、正常盈利、owner cash、估值和报告多个 handoff。

这些对象各自合理，组合后的奖励却容易偏离：Agent 可以完成大量字段、receipt、mismatch 和局部门禁，却没有一个对象对“这家公司是否值得在某个价格承担风险”负责。

真实训练已经给出同一诊断：

- 多轮 paired experiment 为 `NO_MATERIAL_UTILITY`；
- Round 10 增加维度后没有证明材料投资效用；
- CN601933 holdout 为 `NOT_DIAGNOSTIC`，因为公平 Baseline 已能作出同样保守处理；
- 招商银行、隆基、口子窖、家家悦产生了有用的局部判断或规则修正，但仍没有形成一套完整、可迁移的企业承保能力；
- 经验调用已经可以改变福莱特的研究顺序和保守现金处理，但尚未拥有从行业处境到价格处理的整条投资论证。

根因不是样本绝对数量单独不足。更根本的是训练任务经常只要求局部字段或局部规则，反馈也只回到局部字段；即使增加样本，系统也可能只更熟练地完成局部合规任务。

## 2. 麦格纳案例揭示的正确任务

本仓书籍笔记中的麦格纳案例给出了更接近中心目标的完整示范：

1. 先识别 2009 年汽车行业和核心客户的危机处境；
2. 先排除即时破产和长期行业永久毁灭，而不是先算增长；
3. 判断公司是否能活过周期并回到正常利润率；
4. 认识到它没有可持续特许权，因此不为成长价值付费；
5. 用资产价值和 EPV 交叉约束保守价值；
6. 最后才比较市场价格与可生存企业的保守价值。

这不是固定要求每家公司先写 GDP。宏观变量只有在存在明确传导时才进入：

```text
GDP / 利率 / 房地产 / 信贷 / 技术 / 政策
  -> 行业需求、供给、价格、成本或融资条件
  -> 公司具体客户、产品、区域和资本结构暴露
  -> 销量、价格、利润、现金和生存
```

没有公司暴露和传导机制的宏观章节只是背景文字，不能改变企业判断。

## 3. 唯一顶层对象：EnterpriseUnderwritingEpisode

### 3.1 定义

```text
EnterpriseUnderwritingEpisode
  = company x cutoff x investor decision
  + situation and industry regime
  + enterprise survival and adaptation thesis
  + normalized economics and owner-cash thesis
  + permanent-loss paths
  + value-route choice
  + price-facing treatment
  + rival explanation and reversal observations
  + experience invocation and later feedback
```

它是组合读模型和判断主对象，不复制官方事实、财务结果或价格数据。每个材料判断必须指向现有 source/evidence、EnterpriseSystemModel、ManagementDecisionLedger、CJO 或 valuation object。

### 3.2 两个严格分开的投影

同一个 Episode 内部保留两个投影，避免价格反写企业事实：

```text
UnderwritingThesis（价格前）
  企业处境、生存、适应、正常化、owner cash、永久损失、价值路线

InvestmentTreatment（价格后）
  市场隐含要求、安全边际、最高可接受价格、BUY/WATCH/RESEARCH 处理
```

价格可以改变投资处理和研究优先级，不能改变 `UnderwritingThesis`。新证据只能追加一个新 cutoff 或正式 amendment，不能静默改写旧判断。

### 3.3 Episode 必须拥有的经济内容

这些内容构成连续论证，不是九张独立表或评分项：

1. **Decision Frame**：用户要决定什么、持有期限、最怕的永久损失和本轮可输出什么；
2. **Situation Model**：当前宏观/行业阶段、周期与结构分叉、公司暴露和传导链；
3. **Business Position**：公司怎样赚钱、客户为何选择它、竞争约束、资本占用和当前位置；
4. **Survival Case**：流动性、债务期限、融资依赖、索取权、经营自救空间及生存条件；
5. **Adaptation Case**：管理层看见了什么、实际做了什么、资源怎样部署、客户是否吸收、何时调整；
6. **Normalization Case**：周期/转型后可持续的量、价、利润率、维护资本、营运资本和普通股 owner cash 范围；
7. **Permanent-Loss Map**：哪些路径只是波动，哪些会不可逆损害竞争位置、资产、融资或普通股索取权；
8. **Value Route**：为什么采用资产价值、EPV、特许权/复利、分部、期权或清算路线，哪些路线不适用；
9. **Investment Treatment**：当前价格要求公司实现什么、保守价值与价格的关系、何时研究/等待/进入；
10. **Strongest Rival And Reversal**：最强竞争解释、最早异常信号和会使当前处理翻转的观察。

### 3.3.1 IndustryFutureThesis：Situation Model 的方向性内核

`IndustryFutureThesis` 不是新数据库、独立行业报告或固定章节。它是
`Situation Model` 中必须由同一个 Episode 拥有的价格前判断：在与投资问题匹配的
3--5 年或更长时域内，行业利润池最可能怎样变化，这家公司将怎样承受、适应或利用
这种变化，以及它会把正常盈利、owner cash 和永久损失推向哪里。

该主张不能只靠目标公司 Agent 临时搜索两三家同行后现写。形成主张前，系统先把现有
`IndustryLearningBlock`、官方行业观察、已审阅机制、公司 archetype、完整案例和 near
miss 编译成 `IndustryUnderwritingContext`。上下文给出行业 reference class、结构 epoch、
利润池、异质公司路径和机制角色同行；目标公司的证据再决定哪些部分适用。上下文是同一
`Situation Model` 的派生输入，不是新的事实库，也不能直接成为本公司事实或估值参数。

一条完整主张必须连续回答：

```text
最可能的行业 regime 与最强竞争解释
  -> 需求、供给、竞争、价格、成本、监管或融资怎样改变利润池
  -> 目标公司的客户、产品、区域、渠道、产能和资本结构暴露
  -> 管理层已经采取或现实可采取的适应动作
  -> 正常量价、利润率、资本需求、owner cash 与生存边界
  -> 永久损失、价值路线和当前不应支付的未来能力
  -> 最早会使主张翻转的可观察事实
```

报告不能以行业现状、趋势清单、三组并列情景或一个监控 KPI 代替这条判断。没有可校准
基准率时，使用低/中/高置信或保守范围，不填写分析师直觉概率。只有两个仍可信的行业
regime 会材料性改变投资处理、且当前证据确实不能区分时，才允许保留 `NO_PRIMARY`；
此时仍须给出两条路径共同成立的生存/现金下界、当前不为哪项成长付费，以及哪项观察
能够完成区分。

多行业控股公司不强行制造一个共同周期。它应分别判断材料分部的未来 regime，再说明
各分部对普通股现金、资产价值和永久损失的权重。有限期限资产则把租约、供需、续租、
资本开支和法律到期共同放入时域，不能只写终局瀑布。

### 3.4 Claim-local underwriting

Episode 不要求“整家公司通过”。每项未来经济能力使用以下处理之一：

```text
UNDERWRITE
  可进入基准正常盈利、owner cash 或价值路线

CONDITIONALLY_UNDERWRITE
  只在具名条件和范围内进入

SCENARIO_ONLY
  经济上可行，但不进入基准价值

EXCLUDE_FROM_BASE
  当前证据不足或风险过高，不支付基准价格

CANNOT_BOUND
  无法形成有意义范围，只限制依赖该项的处理
```

这不是分数。`UNKNOWN` 仍可作为事实状态，但投资处理必须说明它对应上述哪一种承保结果。一个产品、项目或字段 `CANNOT_BOUND` 不会自动关闭成熟核心、资产价值或整个公司研究。

## 4. 先识别承保路线，再决定研究深度

不同企业需要不同的主路线。下面是初始假设，不是固定分类；新证据可以改路由。

| 路线 | 首要问题 | 主要价值锚 | 代表性案例 |
|---|---|---|---|
| 困境周期型 | 会不会死，行业是否只是周期受压，利润能否正常化 | 资产价值 + EPV | Magna |
| 特许权复利型 | 客户粘性是否持久，增量资本能否高回报复投 | EPV + 经约束的成长/复利价值 | WD-40 |
| 结构转型型 | 旧核心是否被侵蚀，组织和资本能否完成迁移 | 衰退核心 + 经折价的转型选择权 | Intel 等技术转型 |
| 资产/索取权型 | 资产真实归属、可达性、负债和兑现路径 | NAV / 清算 / SOTP | 地产、控股、资源资产 |
| 金融/中介型 | 资产质量、负债稳定性、监管资本和可分配现金 | 经周期正常化的权益收益与可分配现金 | 银行、保险、平台中介 |

八维判断继续作为证据检查镜头，但不再决定报告结构或训练顺序。比如 Magna 路线首先需要生存与正常化；WD-40 路线首先需要特许权持久性和再投资；金融企业首先需要资产负债表和索取权。Agent 不应为填满八维而稀释真正决定投资处理的问题。

## 5. 一次完整研究怎样运行

### 5.1 Frame：先写投资问题

开始时用投资者语言冻结一条问题，例如：

> 当前低迷是会被资产负债表承受并恢复的周期，还是会永久削弱公司的客户位置和正常盈利？若能恢复，市场价格是否低于不计成长的保守价值？

如果新增资料不会改变生存、正常化、永久损失、价值路线或价格处理，就不优先取得。

### 5.2 Recognize：识别处境与路线

结合参考类、行业史、生命周期和历史经验，提出当前最可能的路线与一个 near miss。此时检索 Judgment Experience Memory，但历史案例只提供结构模式、异常信号和失效边界，不提供当前公司结论。

### 5.3 Simulate：运行主路径和最强反方

Agent 不枚举所有可能故事，而是运行两条最能改变处理的经济路径：

```text
当前最佳解释
  -> 关键中介变量
  -> 企业状态变化
  -> 正常盈利 / owner cash / 永久损失

最强竞争解释
  -> 不同中介变量
  -> 不同的最早可观察信号
  -> 不同投资处理
```

这是 Gary Klein 式“识别情境后做心理模拟”的受控版本；它仍受来源和责任边界约束，不把熟悉感当证据。

### 5.4 Underwrite Survival：先处理死亡与融资路径

对困境、周期和高杠杆企业，生存不是一个财务比率，而是一条时间化现金路径：

- 经营现金最差可能到哪里；
- 债务、租赁、担保和资本承诺何时到期；
- 哪些资产或融资来源真实可用；
- 客户、供应商、监管者或少数股东拥有什么优先权；
- 管理层能削减、出售、延后或再融资什么；
- 哪个事件会把暂时损失变成不可逆损失。

非困境企业可快速通过这一段，但不能完全省略普通股索取权和资本配置风险。

### 5.5 Normalize：估计可持续经营机器

正常化不是五年平均，也不是最新利润外推。它必须解释：

- 当前收入和利润中哪些来自周期高点、补贴、会计边界或一次性价格；
- 哪些客户、产品、产能和成本在正常状态仍存在；
- 维持当前竞争位置需要多少资本；
- 营运资本和少数股东怎样影响普通股现金；
- 管理行动是否改变了未来经营机器，而不只是完成建设。

可以给保守范围和情景，不要求虚假精确单点。

### 5.6 Route Value：价值方法服从企业状态

先判断企业是什么，再选方法：

- 生存但无特许权：资产价值与 EPV 双锚，成长价值从严；
- 稳定特许权：正常 owner cash 与增量资本回报决定复利价值；
- 转型：旧核心和新选择权分开，不把计划全部资本化；
- 资产/索取权：先做实体、负债、NCI 和可达性桥；
- 无法持续经营：切换清算或重组路线。

禁止把所有模型算完后平均或投票。

### 5.7 Price：最后处理买点

价格层回答：

- 当前价格隐含了什么正常利润、增长、资本回报或失败概率；
- 保守价值范围与价格之间是否有足够缓冲；
- 哪一项尚未承保的未来能力正在被市场收费；
- 买入、等待、继续研究或放弃各自需要什么条件。

没有足够范围时可以不给数值 BuyBand，但必须给出“不为哪项付费、什么事实会允许定价”的处理。这样不以假数字换取果断，也不以 `UNKNOWN` 逃避投资问题。

## 6. 证据纪律重新定位

### 6.1 证据是约束，不是产品

PIT、来源身份、责任边界和结果隔离继续是硬约束。它们定义哪些解可接受，但不决定可接受解中哪一个最有投资价值。

每次研究只问两个证据问题：

1. 这项证据能否 materially 改变承保主张或投资处理？
2. 它能否区分当前最佳解释与最强反方？

若答案都是否定，就停止扩展资料。

### 6.2 静态 PDF 不再是全系统的样本定义

- 发行人财报和公告优先使用可定位的官方静态文件；
- 行业和宏观可以使用官方时间序列、监管统计、行业协会材料及可验证的截止日前页面；
- 动态页面可用于发现；若要支撑材料主张，必须保存可复核的发布时间和内容定位；
- outcome-known Teaching 可以使用事后材料，但必须显式标为 demonstration，不得计入盲测成绩；
- Blind Replay 和 Prospective 继续严格执行 cutoff 和结果隔离。

因此“没有唯一静态公告”不再等于“没有训练价值”。它只限制需要该公告支持的主张。

### 6.3 Comparative 回到局部工具位置

只有当主张是“行动 A 相对替代行动 B 导致结果变化”时才需要严格 comparator、eligibility 和 estimand。它不再是企业重建、生存判断、正常化、价值路由或案例学习的前置阶段。

## 7. 训练系统：从字段练习改为完整承保练习

### 7.1 三种样本身份

| 身份 | 用途 | 反馈 | 不能证明什么 |
|---|---|---|---|
| `WORKED_CASE` | 快速学习完整推理、near miss 和价值路线 | 已知结果下解释正确/错误链 | 不计命中、校准或迁移 |
| `BLIND_REPLAY` | 在历史 cutoff 下独立完成完整承保 | 结果揭示后逐链结算 | 不能消除基础模型记忆污染 |
| `PROSPECTIVE_EPISODE` | 检验真实未来部署和买点处理 | 多时钟自然到期 | 少量样本不能证明普适收益 |

Comparative、Forecast、Teaching 和 Boundary 不再作为互相排斥的顶层 lane。它们是 Episode 内对某一主张可选的研究与反馈工具。

### 7.2 一个训练回合必须练完整任务

```text
DEMONSTRATE
  学习一个完整 worked case 及其 near miss

ATTEMPT
  在新公司/新 cutoff 独立形成 EnterpriseUnderwritingEpisode

CHALLENGE
  构造最强反方和失败预演

FREEZE
  冻结价格前承保主张、价值路线与可区分观察

REVEAL
  按不同经济时钟开放结果

DIAGNOSE
  定位是处境、行业、公司位置、生存、适应、正常化、现金、损失还是价值路线错误

REVISE / RETAIN
  收窄或保留经验边界

APPLY
  在结构相近但公司不同的 Episode 中调用
```

这与 Case-Based Reasoning 的 retrieve/reuse/revise/retain 循环一致，但 Turtle 必须同时保留最强 near miss，防止只检索支持当前故事的成功案例。

### 7.3 多时钟反馈，不等待一张年报决定全部

完整承保主张在不同时间成熟：

```text
数月：融资、流动性、订单、投产、客户/价格信号
1--2 年：利用率、单位经济、营运资本、适应动作
3--5 年：正常利润、owner cash、资本回报、竞争位置
更长：行业结构、永久损失、复利或衰退路线
```

一个时钟到期只更新对应链。短期销量没有权力结算长期护城河；项目投产没有权力结算资本回报；股价没有权力结算经营判断。

### 7.4 扩大有效样本而不伪造统计意义

下一阶段不再把每个样本都做成昂贵的完整 Comparative。建议的训练吞吐目标是：

- 先建立 12--20 个跨路线的高信息 worked cases，包含成功、失败、消失公司和 near miss；
- 再运行 8--12 个真正结果隔离的 Blind Replay；
- 保留 3--5 个异质 Prospective Episode 作为长期哨兵。

这些是研发容量目标，不是发布门或统计显著性声明。失败、破产、退市和消失公司对生存与永久损失训练尤其有价值，不能因不再上市或资料不整齐而删除。

### 7.5 经验记忆保存什么

现有 `JudgmentExperienceRecord` 继续复用，但优先从完整 Episode 投影：

- 初始处境与承保路线；
- 最容易误判的关键分叉；
- 主机制和 near miss；
- 最早有诊断力的信号顺序；
- 正常化和永久损失的错误模式；
- 价值路线为何适用或失效；
- 什么结构条件下可以迁移。

经验检索提供问题、路径和边界，不提供当前公司结论、概率、估值倍数或买点。

## 8. 怎样判断训练是否真的有效

### 8.1 首要评价单位是投资处理差异

同一 cutoff、同一证据和相近研究预算下，由独立投资者 reviewer 比较当前系统与承保系统：

- 是否更正确地区分周期受压与结构毁灭；
- 是否更早看见生存、融资或普通股索取权风险；
- 是否更合理地正常化盈利、维护资本和 owner cash；
- 是否识别管理层只是完成部署，还是已完成客户和经济吸收；
- 是否选择了更合适的价值路线；
- 是否避免为未承保的成长付费，或避免错过价格远低于可生存保守价值的机会；
- 是否提出真正会翻转处理的观察。

reviewer 只裁决 `MATERIALLY_BETTER / SAME / WORSE` 并说明具体决策差异，不产生总分。

### 8.2 字段和概率只作诊断

- 可观察、定义稳定、事前冻结的子预测可使用 calibration、resolution 或 Brier score；
- 字段结算用于定位哪条链错了；
- 报告长度、字段数、UNKNOWN 数、receipt 数和 validator 通过数没有训练信用；
- 公平 Baseline 已经做到的谨慎处理不计增量效用；
- 但 Baseline 和 Enhanced 都产出高质量完整判断，仍是产品成果，只是不能归因于新增方法。

### 8.3 防止“熟悉感就是能力”

Kahneman 与 Klein 指出，直觉质量取决于环境可预测性和是否有机会学习规律，主观熟悉感不可靠。企业投资环境反馈慢、噪声大、结构会改变，因此 Turtle 不能只积累故事：

- 对稳定、可重复的局部关系做校准；
- 对低有效性、长期结构判断保留机制、范围和翻转条件；
- 用 near miss 和反例测试迁移边界；
- 用 Prospective Episode 检验历史学习是否在真实未来仍有效。

## 9. 与现有系统的整合

| 现有对象 | V1 中的位置 | 变化 |
|---|---|---|
| Evidence/PIT/source controls | 证据底座 | 保留；不再主导顶层叙事 |
| EnterpriseSystemModel | 当前公司经营事实与机制 | 直接引用，不复制 |
| ManagementDecisionLedger | 管理行动与适应序列 | 直接引用，不给管理层总分 |
| 八维 EnterpriseJudgmentEpisode | 证据覆盖与局部反馈镜头 | 降为兼容视图，不再是读者主对象 |
| Forecast / Measurement | 可观察分叉的校准工具 | 只结算适合预测的子主张 |
| Comparative / V5 | 局部因果工具 | 不再充当完整训练入口 |
| Judgment Experience Memory | 条件化案例记忆 | 从完整承保 Episode 投影经验 |
| Frozen CJO | 价格前公司判断的受控投影 | 由同一 UnderwritingThesis 编译，不再另行综合 |
| Valuation Overlay | 价格与价值计算 | 消费 value route、正常化范围和损失情景 |
| Golden Report | 用户可读产品 | 直接编译同一 Episode，不从状态码重建故事 |

### 9.1 兼容期裁决

E0--E3、J0--J4、八维和现有 schema 在迁移期继续可用，避免重写已验收控制层。但新任务不得把完成这些阶段当作中心进度。投资者进度只报告：

1. 已完成哪家公司的完整承保判断；
2. 当前最合理的生存、正常化、永久损失和价值路线是什么；
3. 哪条真实反馈改变了下一次判断；
4. 当前价格处理是否比旧 Baseline 更有用。

该兼容缺口已在 kernel 层收窄：完整 Episode 若与 current-company source package、CJO company/cutoff、中心路径、最强反方和独立复核精确绑定，可以取得 `PRIMARY_ADMITTED`，由正式生产入口写入 `canonical_judgment_refs`，并进入运行时 valuation routing 与 `INVESTMENT_ENRICHMENT` 的价格前报告 handoff；不再要求整家公司先取得 `SELECTION_ADMITTED`。Comparative/selection 权限仍只约束真正依赖相对选择或因果方法的局部 claim。Legacy CJO 和旧局部训练对象继续可读，但不能再冒充完整训练主产品。

`UnderwritingThesis` 同时冻结 `normal_earnings / owner_cash / permanent_loss` 三条经济方向。Episode 存在时，CJO 的对应方向由它确定性派生，不能保留另一套相反叙事；价值路线也只能由同一投影进入估值。每家公司只需明确适用的 primary 估值模型，corroborative 与 stress 模型在不适用时可以为空，避免为了形式完整污染判断。

正式训练默认使用当前 Codex 会话编排的 fresh 子 Agent，不依赖仓库 API key：

```bash
.venv/bin/python scripts/enterprise_underwriting_training.py render-subagent-task \
  <training-contract.json> --output <temporary-task.json>

# 主 Agent 用 fork_turns=none 启动 fresh 子 Agent；它只读取 task packet，
# 并返回一个完整 Episode JSON 到 <agent-response.json>。

.venv/bin/python scripts/enterprise_underwriting_training.py run \
  <training-contract.json> --agent-response <agent-response.json> \
  --output-dir <fresh-output-dir>
```

`render-subagent-task` 把合同允许的 source-package 编译成一次性的精确任务包；主 Agent 负责用
`fork_turns=none` 建立认知隔离，子 Agent 必须一次产出完整 Episode。`run --agent-response` 只在
绑定校验通过后写入 Episode 和价格前下游 bundle。A/B 使用两个互不读取的 fresh 子 Agent，并由
第三个 fresh reviewer 比较材料性差异。外部 provider 仅在用户明确要求后通过显式 `--provider`
启用；认证失败不得阻断默认 Codex 子 Agent 路径，也不得把有效子 Agent 产物叫作 manual fallback。
`validate-episode` 仍只用于诊断，不能把任意预写 JSON 或旧 lane receipt 变成一次已完成训练。

## 10. 黄金报告怎样改变

报告的开头和中心论证直接来自 `EnterpriseUnderwritingEpisode`：

```text
一句话承保结论
-> 当前处境与周期/结构判断
-> 公司生存和适应能力
-> 正常盈利与 owner cash 范围
-> 永久损失与最强反方
-> 价值路线及不应支付的部分
-> 当前价格、安全边际和翻转条件
```

十五章可以继续作为导航，但每一章必须服务同一主张。报告不能把 CJO 状态、训练权限、schema 或 UNKNOWN 清单放在投资者结论之前；技术附录再承担来源、口径和可复做细节。

## 11. 路线图

### U0 顶层收口（本文）

冻结中心对象、既有组件映射、训练反馈和报告消费方式。完成不代表能力已经产生。

### U1 麦格纳式纵向切片

实现一个最小 `EnterpriseUnderwritingEpisode` 组合读模型和 adapter：

- 用 Magna worked fixture 验证困境周期型路线；
- 用现有 CN600585 海螺水泥教学证据生成一条真实、公司特定的完整承保读本；
- 从同一 thesis 投影 Frozen CJO candidate、valuation route request 和 Golden Report handoff；
- 不新建事实库，不新增全局 gate。

U1 的完成标准是投资者能读到一条连续企业判断，而不是 schema 或测试通过。

### U2 高信息案例课程

围绕五类承保路线建立 worked case、near miss 和 failure case。Magna、WD-40、Intel 只作方法示范；中国真实企业提供主要训练材料。允许失败和消失企业进入。

首个 U3 pilot 在 kernel 完成后先于 U2 批量扩样运行，用来验证主链确实练完整 Episode；否则 12--20 个新案例仍可能退回旧字段底座。Pilot 通过后再扩大 U2 覆盖。

### U3 Blind Replay

选择未用于 U1/U2 规则调试的公司/cutoff，冻结完整承保主张，再按多时钟揭示结果。反馈修改 Episode 的具体推理链和经验边界。

### U4 黄金报告与估值同源

kernel 接线已让 Frozen CJO、`JUDGMENT_SYNTHESIS`、确定性公司判断读者工件和 valuation runtime 消费同一价格前 UnderwritingThesis；报告本地 `thesis_test.json` 不能覆盖它。剩余 U4 产品验证是让一份真实黄金候选在合法 CJO/估值合同下消费该对象，并观察完整读者报告是否真正改善；当前 worked case 与 synthetic runtime test 不能替代这一步。

### U5 Prospective 与买点校准

在多个异质企业中保留真实未来 Episode，评价正常化、永久损失、价值路线和价格处理。Turtle 只输出研究/估值参考与条件化 BuyBand，真实计划和交易仍交给年糕与用户。

## 12. 立即停止的工作

- 不再为扩大字段完成率增加全局 gate；
- 不再以第二个机械结算样本、更多 mismatch 或更多 receipt 作为顶层进度；
- 不再把八维逐项填满当作企业判断；
- 不再要求完整企业研究先取得 Comparative；
- 不再用 Agent 数量、投票、星级或总分替代中心判断；
- 不再从报告章节和状态码重新拼装一条与 CJO/估值不同的公司故事；
- 不再因缺少精确值就拒绝给保守范围、价值路线或“不为此付费”的处理。

## 13. 架构成功标准

系统成功不是“永远判断正确”，而是后续未见公司中出现可复盘的改善：

1. 更早判断行业冲击是周期还是结构；
2. 更少错把短期困难当永久毁灭，或错把流动性缓冲当长期安全；
3. 更少用峰值利润、集团现金或投产事件替代正常 owner cash；
4. 更准确地区分管理层部署、客户吸收、经济回报和资本配置；
5. 更合理地选择 NAV、EPV、复利、转型或清算路线；
6. 在价格远低于可生存保守价值时敢于识别机会，在价格包含未承保成长时拒绝付费；
7. 黄金报告能直接、清楚、连续地回答以上问题。

## 14. 研究依据与可借鉴系统

### 14.1 决策与学习研究

- [Kolodner, 1991, Improving Human Decision Making through Case-Based Decision Aiding](https://doi.org/10.1609/aimag.v12i2.895)：人擅长用类比但不总能召回正确案例，计算机应增强案例记忆，最终判断仍需对当前问题作适配。对应 Turtle 的结构检索、near miss 和“经验不是当前事实”。
- [Aamodt & Plaza, 1994, Case-Based Reasoning: Foundational Issues, Methodological Variations, and System Approaches](https://doi.org/10.3233/AIC-1994-7104)：retrieve、reuse、revise、retain 为经验闭环提供经典结构。对应 Turtle 的检索、结果前调用、反馈收窄和版本保留。
- Gary Klein 的 Recognition-Primed Decision 模型：专家先识别情境、提取关键 cues 和 expectancies，再对一个可行路径做心理模拟。对应 Turtle 的承保路线识别、主路径/反方和最早异常信号；它不授权脱离证据的直觉。
- [Kahneman & Klein, 2009, Conditions for intuitive expertise](https://pubmed.ncbi.nlm.nih.gov/19739881/)：直觉质量取决于环境可预测性和学习机会，主观信心不可靠。对应 Turtle 的多时钟反馈、局部校准和结构变更边界。
- [Ericsson, Krampe & Tesch-Romer, 1993, The role of deliberate practice in the acquisition of expert performance](https://doi.org/10.1037/0033-295X.100.3.363)：能力来自针对表现改进的结构化、反复练习。对应 Turtle 的完整代表性承保任务，而不是只练容易评分的字段。
- [Mellers et al., 2014, Psychological strategies for winning a geopolitical forecasting tournament](https://pubmed.ncbi.nlm.nih.gov/24659192/)：概率训练、参考类、团队协作和追踪能改善 calibration 与 resolution。对应 Turtle 的 Outside View 和可观察子预测；它不证明复杂企业价值可压成一个概率。
- [Klein, 2007, Performing a Project Premortem](https://hbr.org/2007/09/performing-a-project-premortem)：在承诺前假设判断已经失败，有助于暴露被压制的失败路径。对应永久损失 map 与最强反方。
- [Hatalis, Christou & Kondapalli, 2025, Review of Case-Based Reasoning for LLM Agents](https://arxiv.org/abs/2504.06943)：CBR 可为 LLM Agent 提供显式案例知识、适配和可问责学习。它支持经验调用方向，不证明任何金融收益。

### 14.2 金融 Agent 与开源系统

- [FinMem](https://arxiv.org/abs/2311.13743) / [GitHub](https://github.com/pipiku915/FinMem-LLM-StockTrading)：证明分层记忆和决策模块可用于金融 Agent。Turtle 借用“记忆必须进入决策”的思想，但不采用交易回报作为企业判断训练标签。
- [FinRobot](https://arxiv.org/abs/2405.14767) / [GitHub](https://github.com/AI4Finance-Foundation/FinRobot)：提供金融任务分解、模型与数据工具链。Turtle 借用模块化编排，不把 Financial CoT 当作已验证企业洞察。
- [TradingAgents](https://arxiv.org/abs/2412.20138) / [GitHub](https://github.com/TauricResearch/TradingAgents)：展示基本面、情绪、技术、Bull/Bear 和风险角色协作。Turtle 保留 investigator、challenger、reviewer、synthesizer，但不以多 Agent 辩论或投票创造真相。
- [Qlib](https://github.com/microsoft/qlib) 与 [OpenBB](https://github.com/OpenBB-finance/OpenBB)：分别提供量化研究平台和数据平台能力。它们适合成为未来数据/计算底座，不解决长期企业承保主张。
- [ai-berkshire](https://github.com/xbtlin/ai-berkshire)：展示价值投资工作流、并行角色和对抗式研究的产品可用性。Turtle 可借用模块化 skill 与反方流程，但拒绝星级总分、名家人格投票和未经承保链传播的直接仓位建议。

这些研究和项目提供方法部件，不是 Turtle 有效性的外部背书。真正验收仍来自同一证据预算下的完整企业判断、真实反馈、跨公司调用和黄金报告改善。
