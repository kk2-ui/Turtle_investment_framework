# Turtle Agent 企业判断系统 V3 设计验证

> 状态：DESIGN_AND_OFFLINE_RUNTIME_VALIDATED / REAL_PIT_AND_CANONICAL_ADOPTION_PENDING
>
> 日期：2026-08-24
>
> 配套设计：[TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md](./TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md)
> 与路线图：[TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md](./TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md)

## 1. 验证范围与结论

本次验证回答的是：V3 的上层对象和权限，能否在不同企业经济结构中表达经营系统、已实施决策、竞争范围、管理层判断、证据未知项，并把冻结后的驱动单向传到定量买点。

这不是第一条真实 PIT 训练、方法冻结、R-103 留出、生产 canonical CJO 绑定或黄金报告授权。V3 schema、状态机、evidence timestamp 与 lane/permission checks、局部 delta、scope bridge、TransportContract 以及 CJO→BuyBand directionality 已在离线 synthetic fixture 中运行验证；static source package、outcome access/isolation 属于 V5 control plane，且尚无合规真实 package，也没有将 V3 `cjo` 接入既有 Golden Report、ResearchBundle 或生产 read model，因此不能声称真实链路已经成立。

**结论：架构通过，但带一项实现前必须落实的模型澄清。**

- EnterpriseSystemModel、ManagementDecisionLedger、ResponsibilityUnit、CompetitiveArena、DecisionEpisode、LearningTransfer 能覆盖家电制造、重资产周期和多边平台三类不同结构。
- “共同市场”按客户任务、替代关系、竞争接口和共同冲击定义；地理可以是等同、重叠、暴露条件或不要求，不能作为普遍硬门。
- 结果已知的格力钛事件能被记录为真实管理决策，同时保留 ex-ante decision quality = INDETERMINATE；后续亏损或减值不会倒灌为 2021 年预测。
- 证据不足在三个 fixture 中都可以合法落在 UNKNOWN / MIXED / NOT_DIAGNOSTIC，不需要继续追加普遍性门槛。
- 平台案例要求实现者显式保存 actor_side、interface、cross_side_effect 和 arena 的多重性，否则会把平台错误压扁成“单一客户—单一市场”。这是 MODEL 层的通用澄清，不是新增对象或第四张图。

因此，当前“第一个正式方向性样本为 0”本身不是 V3 架构失败。正式 PIT 样本故意要求同一责任边界的 D3/D4 结算和对竞争假设有鉴别力的结果；候选缺少这些事实时应停止或降级。G1 的企业模型、管理决策、机制和边界训练仍可继续，不能被 G3 的等待状态拖住。

## 2. 验证问题与失败标准

### 2.1 需要通过的问题

1. 同一模型能否表达全国消费市场、运输半径约束的区域市场和跨地域的全球/平台市场。
2. 企业整体模型能否与单个 DecisionEpisode 分离，episode 只更新局部状态。
3. 管理层账本能否把当时判断、执行、外部冲击和结果分开。
4. 证据能否按假设鉴别力而非支持条数推动结算。
5. TransportContract 能否拒绝表面相似、接受关系结构相似且保留 moderator 的迁移。
6. 冻结 CJO 的经营驱动能否穿透正常利润、owner cash、价格隐含要求、预期差和条件化 BuyBand。

### 2.2 失败标准

若出现以下任一情况，才构成架构级失败：

- 为表达平台的多类参与者必须新增平台专用实体，或现有关系无法表达跨侧反馈；
- 只能以单一地域相同创建区域竞争场域，无法表达跨省但运输半径重叠的水泥竞争；
- 一个 episode 的结果只能写成整家公司质量或管理层质量；
- 账本无法在 outcome 已知时保留当时的不可判定；
- 迁移授权只依赖行业、地理、规模或名称相似；
- CJO 未冻结时仍能生成生产买点，或经营驱动断在 owner cash/普通股可达性后被静默补齐。

资料缺失、口径不匹配、结果只能得到 MIXED 或某条现金链保持 UNKNOWN，不属于架构失败；它们应进入 DATA_COVERAGE、ACQUISITION_MODULE 或 REASONING 返回。

## 3. 三类纸面 Fixture

这些 fixture 用于验证对象和权限，不授予任何公司的投资结论，也不替代正式 PIT source package。

### 3.1 家电制造：格力家用空调与格力钛决策

现有机制图把家用空调拆成需求/客户选择、终端 sell-out、安装服务、工厂供给、渠道 sell-in、渠道库存/返利、合同负债、销售费用、产品毛利和经营现金。它可以直接映射为：

```
客户任务与替代
  -> 终端选择/渠道接口
  -> 安装与服务兑现
  -> sell-out 与库存状态
  -> 量、价、成本、费用
  -> 经营现金与再投资
```

该模型没有把“门店多”“线上排名”“合同负债”直接命名为护城河。现有材料明确把库存归属、全渠道相对位置、ASP、返利、服务效果和 owner-cash conversion 保留为未知。来源底稿见 [GREE_HOME_AC_RESEARCH_MECHANISM_MAP.md](./GREE_HOME_AC_RESEARCH_MECHANISM_MAP.md)。

家用空调的客户任务和全国品牌/渠道竞争可以形成全国竞争经济体；家用、家庭中央、商用工程和出口应是不同的 arena 或 measurement scope。省份不是硬门，但渠道服务半径、交易点和价格体系仍可作为条件变量。这与“同省份才可比”不同，也不意味着所有家电公司天然可比。

格力钛 2021 控制权取得是可记录的已实施资本配置决策：cutoff 为 2021-10-31，取得 30.47% 股权并合计控制 47.93% 表决权，交易对价约人民币 18.28 亿元。账本可以保存当时目标、整合意图、约束和未知项；但现有材料没有给出足以区分 6–12 个月主/反机制的 metric、比较对象、阈值和观察窗，因此 ex-ante decision quality = INDETERMINATE。

后续 2022H1 亏损/现金、2023 年进一步取得少数股权和 2025 年项目减值可以分别进入 execution/outcome/external-shock overlay，但不能回填 2021 年的 measurable forecast。来源底稿见 [GREE_TITANIUM_2021_EPISODE_ELIGIBILITY_REVIEW.md](./GREE_TITANIUM_2021_EPISODE_ELIGIBILITY_REVIEW.md)。

**验证结果：通过。** 系统能表达真实决策、局部经营状态和 outcome bias 边界；资料不足正确降级为 OUTCOME_RICH / MIXED / NOT_DIAGNOSTIC，没有逼迫它生成方向性样本。

### 3.2 重资产周期：海螺水泥

这是来自既有跨案例裁决的纸面 fixture，不在本验证中重新取证。其经济结构至少需要：熟料/水泥产能和利用率、区域运输半径、价格和需求供给退出、能源/制造成本、经济维护资本、净现金、联营/金融资产可达性和留存资本配置。

```
有效产能与利用率
  -> 区域供给/运输半径/价格
  -> 单位成本与利润
  -> 维护资本与 owner cash
  -> 留存配置、金融/联营资产和普通股可达性
```

水泥的共同竞争经济体可以是跨省但运输半径重叠的区域，而不是行政省份。若两个基地服务不同市场、没有共同价格/运力/供给冲击，则不能仅因都叫水泥而进入同一 arena。这里需要 REQUIRED_OVERLAP 或 REQUIRED_EXPOSURE，而非 REQUIRED_EQUAL 的省份字段。

既有裁决把中周期价格、经济维护资本、联营/金融资产可达性、留存配置和需求/供给退出列为尚未完全闭合的边界；它没有用股息年化或峰值利润补齐这些未知。来源见 [CROSS_CASE_ADJUDICATION.md](../golden_set_v1/CROSS_CASE_ADJUDICATION.md) 与 [REGISTRY.md](../golden_set_v1/REGISTRY.md)。

**验证结果：通过。** stocks/flows、瓶颈、反馈、资本强度和 owner-cash bridge 能用现有对象表达。缺少中周期价格或维护资本不是模型缺失，而是 DATA_COVERAGE/UNKNOWN，不应成为新的行业普遍门。

### 3.3 多边平台：腾讯 2024 年报纸面 fixture

资料入口：腾讯官方 [Financial reports](https://www.tencent.com/investors/financial-reports/) 页面及其 [2024 Annual Report PDF](https://static.www.tencent.com/uploads/2025/04/08/1132b72b565389d1b913aea60a648d73.pdf)。本 fixture 只验证表达能力，不把年报中的公司自述自动升级为网络效应或护城河结论。

官方年报提供了足以压测模型的结构性材料：

- Weixin/WeChat 合并 MAU 为 13.85 亿，报告描述 Mini Shops、Video Accounts、Weixin Search 和广告技术平台的产品变化；
- 2024 年 Marketing Services 收入约人民币 1,213.74 亿元，年报把 Video Accounts、Mini Programs、Weixin Search 的广告需求列为重要驱动；
- FinTech and Business Services 收入约人民币 2,119.56 亿元，包含财富管理、商业支付、WeCom、云和电商技术服务；
- 集团资本开支约人民币 767.60 亿元，报告说明其中包括计算设备、在建工程、土地使用权和若干无形资产；
- 报告单列隐私、数据、反垄断、消费者保护、网络安全和不同司法辖区监管风险。

现有对象足以表示消费者/用户、商户/广告主、开发者/内容、支付与云客户、腾讯基础设施与资本配置、监管与治理等节点及其关系：

```
用户侧使用/时间/内容/交易接口
  -> 广告库存、商户交易和技术服务费
开发者/内容/支付/云客户
  -> 内容供给、分发、支付和企业服务需求
腾讯基础设施与资本配置
  -> 推荐/广告/AI/云能力、研发、Capex、分红和回购
监管与治理
  -> 数据权限、合规成本、产品可用性和竞争边界
```

**验证结果：通过，但需要模型澄清。** 这些关系不要求新增 PlatformModel。它们要求 EnterpriseSystemModel 支持一对多的 ResponsibilityUnit/CompetitiveArena，并在 node/edge 上保留 actor_side、interface、cross_side_effect 和 measurement scope。否则实现者可能把 MAU、广告收入、支付量和云收入压成一个“客户增长”字段，从而错误推断网络效应、定价权和 owner cash。

## 4. 对抗性迁移测试

### 4.1 表面相似但不得迁移

格力家电到海螺水泥：两者都是制造业、都有产能、渠道/客户和现金转换，但客户任务、替代品、运输约束、固定资产周期、价格形成和维护资本不同。TransportContract 必须拒绝把“产能被销量吸收”迁移成“增量资本回报成立”。该拒绝与 R-25/R-52 的既有教学结论一致。

格力钛并购到普通经营扩产：两者都可能出现“管理层投入资源—后续经营变化”，但并购控制权、整合、担保、NCI 和资本索取权使机制拓扑不同。不得把并购结果直接迁移成扩产管理能力。

### 4.2 表面不同但关系可能迁移

有赞变量云服务费到腾讯平台货币化接口：可以迁移的不是“互联网公司收费会成功”，而是一条受限关系：使用/交易接口变化可能改变收费基础和服务成本，必须同时观察客户/参与者 cohort、收费规则、服务成本和合同现金。

目标差异包括：腾讯有用户、商户/广告主、开发者和支付/云客户多个 side，跨侧反馈和监管约束更强；总 MAU、总广告收入或总毛利不能替代同一 side 的留存和现金。required_target_observations 应包括 side-specific retention/usage、收费和成本归属、现金时点及监管/合规成本；若只有集团总收入和 MAU，触发 break_condition，迁移降为 TEACHING_ONLY。

该 transfer 的允许改变只能是下一目标的冻结前字段，例如在 MeasurementContract 中强制登记 actor_side 和接口，不是把有赞的结论写入腾讯 CJO。来源教学见 [R-35 变量收费复盘](./experiments/R-35_youzan_2019_variable_cloud_fee/00_2019_2020_variable_cloud_fee_teaching_review.md)。

### 4.3 结论

TransportContract 能同时表达不迁移和受条件约束的迁移。行业、地理、规模和表面词汇不授予迁移权限；真正迁移的是关系、moderator、目标观察和停止条件。

## 5. CJO 到 BuyBand 的纸面传播

以下是合成数字，只验证方向和权限，不是任何公司的估值。

设冻结 CJO 只允许三种经营状态，要求回报率为 10%，持有三年，每年普通股现金分配为 5：

| 状态 | 税后正常经营利润 | 维护资本/其他必要投入 | owner cash | 10% 资本化价值 | 10% 回报要求下的价格上限（约） |
|---|---:|---:|---:|---:|---:|
| BEAR | 48 | 13 | 35 | 350 | 275 |
| BASE | 64 | 14 | 50 | 500 | 388 |
| BULL | 80 | 15 | 65 | 650 | 501 |

价格上限按三年现金流现值计算：

```
P_max = 5/1.10 + 5/1.10^2 + (V + 5)/1.10^3
```

若当前价格为 400，反向计算得到的市场要求约为 owner cash 52，略高于 BASE 的 50。因此系统不能只说“价值 500，高于价格 400”：当前价格要求经营结果至少接近 BULL/高端 BASE，而 CJO 的状态分支尚未完成选择。

正确传播是：

```
CJO driver（量/价/成本/利用率/留存）
  -> normalized earnings
  -> maintenance and necessary reinvestment
  -> owner cash
  -> value identity
  -> price-implied owner cash / operating requirement
  -> ExpectationGap
  -> conditional BuyBand
```

- BULL 分支约 P <= 501 才满足该假设下的 10% 回报；
- BASE 分支约 P <= 388；
- BEAR 分支约 P <= 275，但若该分支意味着永久损失或经营系统未稳定，不应把 275 当作无条件买入价；
- 在分支、永久损失约束或现金可达性未裁决时，输出应为条件化 BuyBand 或 EXPECTATION_GAP_UNKNOWN，不是把 275–501 合成一个目标价。

这验证了设计的中心方向：定量模块消费企业判断；价格只产生“市场要求何种经营结果”的研究问题，不能倒灌为已成立的 CJO。

## 6. 发现与根因分类

| 发现 | 分类 | 经济影响 | 缺少的事实/能力 | 禁止假设 | 可执行修复 | 验收标准 |
|---|---|---|---|---|---|---|
| 平台参与者和 arena 的多重性未在 V3 文字中明确为实现约束 | MODEL | 若被压成单一客户，可能高估网络效应、定价权、正常利润和 owner cash，影响永久损失与买点 | side-specific retention/usage、接口、跨侧反馈、监管成本的 typed 关系 | MAU 增长等于网络效应；广告收入等于用户锁定；总毛利等于可分配现金 | 在 EnterpriseSystemModel/关系边增加 actor_side、interface、cross_side_effect、measurement scope；允许一对多责任单元和 arena；不新增平台对象 | 腾讯 fixture 能保存多 side、多接口和跨侧边；每条边能独立为 UNKNOWN；CJO->quant 不读汇总替代字段 |
| 家电/水泥的关键现金、库存、维护资本和竞争反应不总能从同一责任单元获得 | DATA_COVERAGE | 错误拼接会高估渠道质量、周期正常利润和资本回报 | sell-out/库存归属、区域价格、经济维护资本、资产可达性、留存用途 | 收入、毛利、OCF 或股息年化自动等于 owner cash | 继续使用 scope bridge 和 typed UNKNOWN；缺口进入 Boundary/Teaching，不为行业新增硬门 | 不能用集团指标升级局部判断；缺失时返回 UNKNOWN/MIXED 并给翻转条件 |
| 表面相似迁移容易把“产能/收费/增长”当成机制 | REASONING | 将结果已知故事迁移到新公司，可能错误判断管理能力、竞争位置和价值 | target moderator、目标 side/运输半径/资本强度、可区分结果 | 行业、地域、规模相似就可迁移 | 强制 TransportContract、required observations、break conditions 和 application receipt | 表面相似 fixture 被拒，关系相似 fixture 只有取得目标观察后才改变冻结前字段 |
| 方向性样本准入较高，容易被误读为全系统阻断 | WRITING（状态表达风险，不是模型缺口） | 若把 G3 等同于全部训练，团队会为首样本放松边界或停止低成本能力建设 | 需要更清楚区分 G1 active 与 G3 waiting | 方向性样本为 0 等于系统没有进展 | 持续使用 lane/lifecycle/resolution/permission 四维状态；验证文档明确 G1_ACTIVE / G3_WAITING | R-104 仍是边界学习；G1 工件可运行；不得把 MIXED 计入方向性成绩 |

本次没有发现必须归类为 ACQUISITION_MODULE 的通用失败：已有家电/水泥底稿暴露的是事实边界，腾讯官方年报也足以作为纸面输入。实现阶段仍必须用静态 source package、source span 和 cutoff 测试验证采集器；本文件不替代该运行时测试。

## 7. 对中心目标的判断

### 7.1 对企业判断的帮助

V3 对中心目标有直接帮助，因为它把 Agent 最容易混淆的四件事拆开：

1. 公司怎样作为持续系统创造和获取价值；
2. 管理层在当时信息下做了什么选择；
3. 结果是机制兑现、外部冲击、执行问题还是不可归因；
4. 这条判断能否跨责任边界传到普通股现金。

它还把“停止”变成有权限的产物：正确返回 UNKNOWN、MIXED 或 NO_PRIMARY，能阻止 Agent 用集团收入、同行数量、公司自述或价格故事替代证据。这比为了得到第一个 A/B 标签而放松市场和结果边界，更接近企业家的经营判断和长期投资者的永久损失纪律。

### 7.2 对黄金报告和买点的帮助

黄金报告不再是训练真相，而是冻结 CJO、canonical financial ledgers 和 InvestmentGraph 的下游投影。具体改善是：

- 报告能说明公司靠什么经营、哪个瓶颈决定现金、管理层决定改变了哪条边；
- 正常利润和 owner cash 有经营驱动、维护资本、现金可达性和责任边界，而不是单年利润或 OCF 的直接改名；
- 价格章节可以回答市场已经要求什么经营结果，并把预期差和永久损失分支写成条件化 BuyBand；
- 当 CJO 或现金链仍未知时，报告会输出观察、翻转条件或 UNKNOWN，而不是伪造一个精确目标价。

这能改善买点的输入质量，但不等于已经证明买点更准。真正的效用验收仍需 paired task：比较旧流程与 V3 是否多发现材料性未知、少犯范围/归属/因果错误，或让用户改变价值区间、观察动作或不判断理由。

## 8. 已实现的离线验收与后续顺序

### 已完成的离线控制

1. 多 side、多 interface、多 arena/cardinality 已写入 EnterpriseSystemModel 和关系边的 schema；未新增 PlatformModel。
2. 全国家电、运输半径重叠水泥、跨侧平台三个 synthetic fixtures 及拒绝测试已覆盖。
3. 合成 CJO 的 driver -> owner cash -> expectation gap -> BuyBand 方向性扰动已验证；CJO 未冻结时生产买点接口关闭。

### 唯一允许的下一步

在独立 curator 交付合规的 cutoff-before static CNINFO PDF package 后，才可对其做 cohort-first Stage-0 preflight。H1 通过后，仍须由同一 curator 提交一次性、闭合且绑定 H1 receipt 的 action-screen static-PDF extension，才可筛选第一个真实 PIT episode；该 extension 可补充行动原件但不得增加 cohort company 或在 screen 开始后追加来源。若资料只支持局部链，继续保留 teaching/boundary 权限。Agent 不得搜索、补齐或挑选真实公司资料来绕过这项前置条件。

### 暂不做

- 不为首个样本新增地理硬门、公告硬门或行业专用门；
- 不把 R-104、水泥 cohort、格力钛或任何结果已知教学材料算作方向性成绩；
- 不在本验证之后提前启动方法冻结、R-103、黄金报告授权或生产买点；
- 不继续扩展论文/开源系统清单；外部研究已经足以支持当前设计选择。

## 9. 最终裁决

**架构层：PASS_WITH_MODEL_CLARIFICATION。**

**运行层：OFFLINE_RUNTIME_VALIDATED / REAL_PIT_NOT_VALIDATED。** V3 的 schema、状态转移、evidence timestamp、lane/permission、CJO 编译和 BuyBand directionality 已在真实代码的 synthetic tests 中工作；V5 的真实 static source package、outcome access/isolation 与 canonical production binding 尚未验证。

**训练层：ONE_REAL_H1_RECEIPT_REGISTERED / G2_PROVENANCE_IMPLEMENTED / H2_NOT_STARTED。** 水泥 H1 static package 已通过 strict preflight，并在隔离开发 namespace 登记为 immutable receipt；H2 的 closed-extension validator 与 V5 seal provenance 现已接线，但尚无 curator H2 extension。该 package 的两家 known break 使其只剩三家 pending，不能直接形成 target 加三名 peer。首个方向性样本暂时为 0 是当前证据边界的诚实结果，不是继续给架构加门的理由。下一步的高价值动作是接收绑定 H1 receipt 的 H2/`NO_PRIMARY` boundary，或接收容量合格的新 H1 cohort；任何新候选在缺少同责任边界 D3/D4 或鉴别性结果时，应立即转入边界学习并留下可迁移的失败原因。
