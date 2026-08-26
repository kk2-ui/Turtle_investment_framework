# Turtle 选择训练：材料性与同行反事实协议

状态：`CURRENT / V4_PEER_PANEL_ADMISSION_AND_SETTLEMENT_PROTOCOL / LAYERED_MIGRATION_PENDING`

更新：2026-08-25

上位目标：[历史优先训练架构](TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)

适用范围：本文只定义 `RELATIVE_CAUSAL / V5_PEER_PANEL`。Industry History Universe、Teaching/Lifecycle Case 不需要通过本文的行动、五年 target 或 peer-panel 门；它们也不得取得本文的方向性 learning 权限。当前 H1/H2 roster 仍按既有 validator 关闭，未来 append-only carrier registry 只在[历史训练体系重构](TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)的迁移完成后生效。

## 1. 要解决的错误

历史企业判断不能因为某项关厂、扩产或提价“看起来很大”就把之后的公司利润和现金归因给它。先前的候选筛查暴露了两个相反但同样严重的错误：

1. 用项目投资、减值、预计收入、预计利润或任意“五年回收”直接生成 D3/D4 阈值；
2. 用公司收入、利润或现金改善来证明一个单品、子公司或共同产业周期的效果。

`JUDGMENT_SELECTION_ADMISSION_V4` 因此把**行动暴露**、**结果可区分性**和**项目归因**明确分开。它只允许在发行人/严格同口径责任单元层面判断一项预先冻结的竞争机制是否得到相对支持；没有项目级现金流时，项目 IRR、回收期及“项目导致了现金改善”仍必须是 `UNKNOWN`。

## 2. 三个独立门

```text
已实施且同边界的行动暴露
  ├─ 只证明该问题足以进入黄金报告级训练
  ├─ 不换算为项目利润、项目现金或回收期
  └─ 不得是计划、贷款、CIP、设计产能或管理层预测

行动前的发行人 D3 与保守 D4 历史波动
  ├─ 分别产生 D3 / D4 的绝对可区分性阈值
  ├─ D4 只由 OCF、全部长期资产购建现金和现金营运资本构成
  └─ D3 阈值、利润或是否通过都不能替代 D4

预先冻结的同行面板
  ├─ 让未来目标公司的变化与同业中位变化比较
  ├─ 是共同周期的反事实近似，不是因果处理效应估计
  └─ 少一个成员、替换成员或口径断裂即中央结论 NOT_DIAGNOSTIC
```

只有绝对 D3/D4 与相对同行 D3/D4 同方向支持 H-A 或 H-B，才产生该层的方向性判定。绝对与相对结果相冲突是 `MIXED`；任何缺失、定义变化或同行无法取得是 `NOT_DIAGNOSTIC`，不能用存活、收入、行业均值或另一层的结果补足。

## 3. V4 冻结对象

### 3.1 行动暴露

行动必须在 cutoff 前已经实施或进入不可逆、已确认的责任状态，且由研究目标的同一合并责任单元承担。它还必须有官方证据证明这是**发行人范围的、增量且自主的经营决策**，而不是小项目、维护替换或被动合规支出；V4 只判断发行人层机制，绝不把它改写成项目 IRR 或项目现金归因。允许的证据是已支付现金、已确认资产/负债风险，或已经执行的净价变化乘以行动前已披露的实际销售量；每个输入均需同一发行人、同一合并边界的官方来源、发布日期、字段位置和口径。控制集团标签也必须由 cutoff 前官方来源逐项确认，不能把名称相似的发行人当作独立同行。

下列内容始终禁止作为行动暴露或材料性锚：项目 IRR/预计利润、预计销售、设计产能、CIP 余额、贷款到账、事后披露和“正常经营影响不重大”的行动。行动暴露只证明问题规模，不折算成未来 D3/D4。

### 3.2 绝对 D3/D4 可区分性

目标责任单元至少需要五个行动前年度、同口径的 D3 与 D4 重建值；每期都由同一发行人、同一合并边界的官方审计年报原始字段重算，且目标公司的字段发布日期早于行动。D3 为冻结的经营贡献公式；D4 为：

```text
OCF − 全部长期资产购建现金 − max(期初现金营运资本 − 期末现金营运资本, 0)
```

对每层分别计算行动前基线和稳健离散度：

```text
step = 1.4826 × median(|x_t − median(x)|)
```

`step` 必须大于零；D3/D4 的 H-A、H-B 分别是自己的基线加减自己的 `step`。该规则预先锁定，不能在某个 outcome 出现后改变窗口、分母、乘子或阈值。行动暴露必须至少达到 D3 的预先计算 step，作为“足以值得训练”的门，而不是利润/现金预测。

### 3.3 同行面板

面板包含目标公司和二至七家同产业、非同一控制集团的发行人（即至少三家总成员）。目标、每家同行、其 `issuer_id`、控制集团及控制权来源必须冻结且逐项绑定；每家同行必须在同一合并口径、同一货币和同一 D3/D4 公式下有至少三个 cutoff 前年度的官方审计年报原始字段重建记录。成员顺序、纳入宇宙、排除理由、reference period 和替换禁止均在 outcome 前冻结。

未来 D3/D4 的相对指标为：

```text
(目标公司 outcome margin − 目标公司 reference margin)
  − median(每家冻结同行 outcome margin − 同行 reference margin)
```

`margin` 的分母是同一成员的合并营业收入。D3 和 D4 各使用自己的 ratio 阈值：`max(target absolute step ÷ target reference revenue, 同一 target-minus-peer-median 指标在至少三个共同 action 前期间的 scaled-MAD)`。因此不能把目标公司自身波动误当作同行反事实的噪声边界。绝对 threshold、reference revenue、共同期间、两项 ratio 输入或 D3/D4 公式任一不一致，注册即拒绝。每个成员还要以 action 前官方来源确认同一产品/服务、地理和客户终端市场暴露；`industry_id` 只是索引标签，不能单独证明共同冲击。这里的同行比较仅排除“全行业同向变化”这一竞争解释；不估计处理效应，不生成显著性、胜率、概率或股票回报。

### 3.4 先分诊、后重采集

五年 target、同行三年及控制权档案的采集昂贵，不能对每个“关厂”“调价”标题都展开。当前真实入口先由 curator 只交无 action/target/outcome/hypothesis 的 H1 static-PDF package，并运行：

```bash
.venv/bin/python scripts/judgment_selection_discovery.py --cohort-only <curator_stage0_static_package.json>
```

它只校验当前 Stage-0 cohort receipt：至少五家 control-independent、披露充分的 feasibility carriers，以及每家控制集团来源和 D2/D3/D4 字段可得性必须在行动选择前形成。该 package 不是完整行业宇宙，也不是最终 peer panel。当前 runtime 中，H1 通过后 curator 只能一次性提交绑定 receipt 的 H2 extension，不能增加公司或在 screen 后追加来源。分层迁移完成后，H1 receipt 仍不可修改，但可在 outcome 读取和 Comparative Panel Freeze 前按冻结 eligibility predicate 追加独立 static peer-recruitment batch；具体 target、最终 peers、排除理由、顺序和结果合同在 panel freeze 后关闭。两种 runtime 都禁止动态 CNINFO、结果后补源、自由挑选同行或把 source feasibility 冒充比较资格。`NO_PRIMARY` 返回字段级缺口并停止或降级到低权限 Teaching/Lifecycle；只有完整 Comparative admission 才能创建 episode，仍不给提前 outcome access、learning、方法冻结、留出或报告使用权。

### 3.5 可比性、现金桥与成本链

所有 target/peer 选定窗口都必须有合并范围、会计列报、经营 perimeter 三维 comparability register。任何结构性断裂必须移出窗口；“规模大致相近”或正文说明不能代替同口径。D4 的 OCF、全长期资产现金、现金营运资本和行动相关现金构成完整 bridge；未建模的材料现金项、把重组现金设为零、或把 D3 改善换算成 D4 都是 `NO_PRIMARY`。

若机制是纯成本/网络重构，candidate 必须显式选择 `COST_RESTRUCTURING_CHAIN`：D2 被标为非投票且禁止客户吸收结论；D1→成本驱动→D3→D4 仍须同边界、三期重复、两条相反机制符号和独立审阅。若 H-A 主张客户吸收，则只能使用 `CUSTOMER_RESPONSE_CHAIN`，不能事后降级 D2。

## 4. 结果采集与结算

同行不是新的 claim 或训练样本。它们只是 D3/D4 两个既有 claim 的强制原始输入。

独立 outcome custodian 必须为目标和每名冻结同行提供同一结果期间的逐字段官方来源：

- D3：营业收入、营业成本、税金及附加、销售费用、管理费用；
- D4：OCF、长期资产购建现金、期初/期末应收、预付、存货、应付、预收/合同负债。

校验器重新计算目标 D3/D4、每家同行的 margin、目标变化、同行中位变化及相对值，并把 candidate、source、measurement、outcome 的发行人、控制集团、成员顺序、reference 和公式逐项绑定。custodian 不能提交相对 verdict、评分或已算好的结果来代替原始字段。任一同行缺失、会计边界变化、零收入、来源类型错误、发行人/控制集团替换或字段替换时，D3/D4 中央结论均降为 `NOT_DIAGNOSTIC`；契约在注册前不一致则直接拒绝。

## 5. 独立审阅

独立 reviewer 必须复算而不只勾选：

1. 行动暴露是 cutoff 前已实施、同边界且未被官方标为不重大；
2. 五年 target D3/D4 基线、MAD step 与绝对阈值；
3. D4 基线确为保守 owner cash，未将 D3 结果转换为 D4；
4. target 与同行的发行人、控制集团、控制权来源、同行宇宙、成员、排除理由和历史披露重复；
5. source/measurement/outcome contract 的成员顺序、issuer、reference period、原始字段、绝对/ratio threshold 和不替换规则一致；
6. 没有使用 post-cutoff 校准、项目预测、市场价格或事后挑选同行。

任何材料性修订都建立新 admission version 和新 freeze；旧 outcome 只能作为探索性或边界材料，不能和新版本的确认性结论混合。

## 6. 方法学依据与边界

- [Hernán 等，Target Trial Emulation](https://pmc.ncbi.nlm.nih.gov/articles/PMC11936718/)说明预先明确 protocol 可减少设计歧义，却不能补足数据或把观察性比较变成因果证明；本协议因此不把 issuer-level 结论升级为项目回报。
- [Bernal 等，Interrupted Time Series](https://pmc.ncbi.nlm.nih.gov/articles/PMC5407170/)强调时间序列的历史趋势、数据质量和短序列限制；五年 target 历史与同行字段门是最低可判别性，而非精确估计承诺。
- [AEA Registry FAQ](https://www.socialscienceregistry.org/site/faq)和[Ofosu & Posner 的预分析计划综述](https://www.cambridge.org/core/journals/perspectives-on-politics/article/preanalysis-plans-an-early-stocktaking/94E7FAE76001C45A04E8F5E272C773CE)支持在结果前固定 outcome、样本、编码和修改历史，并区分确认性与探索性工作。
- [FDA 非劣效试验指南](https://www.fda.gov/media/78504/download)要求预先定义 margin 并结合历史变异与条件可比性，反对从历史结果中挑取最大效果；Turtle 仅借用“预先定义且历史可比”的纪律，不把临床 margin 机械移植为企业回收率。

该协议提升的是判断训练的可审计性，不是统计证明、项目估值或投资建议。
