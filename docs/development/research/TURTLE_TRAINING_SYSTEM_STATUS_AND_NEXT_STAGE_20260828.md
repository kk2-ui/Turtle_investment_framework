# Turtle 训练系统最新进度与下一阶段协调计划

> 状态日期：2026-08-28（Asia/Shanghai）  
> 工件身份：`COORDINATION_STATUS / NEXT_STAGE_PLAN`  
> 隔离基线：`dd688820c10d`（家电 Round 10 V2 外部审阅完成）  
> 本工件不授予训练方法、CJO、估值、报告、BuyBand 或投资权限。

## 一、投资者视角的当前结论

Turtle 已经证明两件重要但有限的事情：

1. 它可以在未知结果时冻结公司、cutoff、证据、判断和测量合同，随后由独立角色读取官方静态年报并逐字段结算；
2. 它可以诚实拒绝把“资料更多、解释更完整、UNKNOWN 更多”写成方法胜利。

它尚未证明最关键的一件事：**训练方法能够稳定纠正一项会改变投资处理的企业判断，并在另一家公司上保留这种改进。**

因此，当前瓶颈不再是能否读取年报或写出 episode，而是能否取得一条材料性判断纠正，并把它转化为下一轮更好的提问、证据要求和责任边界。

## 二、已完成能力与证据等级

| 训练能力 | 当前证据 | 投资含义 | 当前权限 |
|---|---|---|---|
| 行业与企业经营系统重建 | 家电行业块覆盖五家公司；E0/E1、J2/J3/J4 只读模型和 Teaching drills 已存在 | 能把产品、渠道、成本、现金和行动放进同一经营系统，不必先找到因果行动 | Teaching / research only |
| 结果前冻结 | 多轮历史对象和家电 Round 10 已冻结 cutoff 前来源、Baseline、Enhanced、测量合同与固定 roster | 研究题目和样本顺序可以先于结果固定 | Pre-outcome training only |
| 官方结果采集与字段级结算 | Minimal lane 已证明单字段机械结算；Round 10 的 9 个字段中 6 个完成机械结算，3 个保持 `MEASUREMENT_MISMATCH` | 单一字段错配不会拖停其他公司或字段，也不会被误写成经营变差 | Mechanical settlement only |
| 方法效用审阅 | Round 10 外部审阅为 `NO_MATERIAL_UTILITY` | 八维框架保住了责任边界，但没有证明改变材料性投资处理或避免 Baseline 方向错误 | No method transfer |
| 局部学习与迁移 | 水泥只存在窄范围 perimeter-first measurement learning；企业判断方法迁移仍未建立 | 目前只能说局部测量纪律改善，不能说企业判断能力已泛化 | Narrow research agenda only |
| Comparative / 因果行动 | 工程合同和 V5 路径存在，但当前无真实 `SELECTION_METHOD_ELIGIBLE` 样本 | 因果行动案例仍是高级、低频支线，不是训练总入口 | No release |
| CJO、估值与报告消费 | Frozen CJO、Overlay 和报告只读接线已有工程能力 | 下游能够受控读取判断，但训练结果不能自动改写投资结论 | No real training-derived authorization |
| 公司轴与时间轴 holdout | 控制合同存在；未来 holdout 已保留 | 可用于未来方法发布，不应阻断当前历史训练 | Reserved / not active |

Round 10 的正式投资者读出见
[家电 Round 10 V2 独立结果后读出](industry_learning_blocks/CN_APPLIANCE_ROUND10_V2_POSTOUTCOME/04_investor_readout.md)。

## 三、当前最重要的未完成事实

### 1. 管线完成不等于训练有效

六个真实字段完成结算，只证明 issuer-level revenue、operating cash flow 和 total assets 可以机械复盘。它们没有唯一测量产品客户响应、管理层行动效果、单位经济或普通股 owner cash，因此不能证明八维方法优于合理的 Baseline。

### 2. UNKNOWN 需要局部保留，也需要防止成为防御性写作

证据不够时保留 UNKNOWN 是正确的；但 episode 仍必须回答当时最值得押注或回避的材料问题，并冻结什么事实会推翻判断。若只罗列边界和缺口、不形成材料投资处理快照，训练无法产生纠正价值。

### 3. 当前缺少第一条企业判断层面的材料纠正

系统尚缺一条被独立确认的链条：

```text
结果前材料判断
→ 下一期官方结果
→ 明确的错误归因、虚假确定性或责任边界纠正
→ 下一家公司预冻结判断发生材料变化
```

未来 holdout 只用于验证这种变化能否泛化，不再作为当前训练的样本出现门。

## 四、并行工作租约：避免与历史封存 Agent 冲突

另一位 Agent 已独占以下“历史封存训练主线”，本工作线不得重复：

- 污染名单与外部历史样本选择规则；
- `3+2+1` 历史 roster、首家公司 cutoff 前材料包；
- 结果前企业判断和六项材料投资处理快照；
- 防御性写作/结果前合同审阅；
- outcome-only custodian、下一期结果揭示和真实纠正结算；
- 将一项窄学习应用到不同公司；
- 未来 holdout 的保留与身份维护。

在该主线提交独立 completion/review receipt 前，本工作线明确禁止：

- 搜索、选择或替换任何历史样本；
- 打开其 outcome、年报结果页、预测或 custody 数据；
- 修改其 roster、episode、measurement、settlement、learning-application 或 holdout 工件；
- 修改共享的 `enterprise_judgment_episode`、`enterprise_judgment_source_packet`、`judgment_decision_utility`、Minimal acquisition/settlement 或 training-program 控制面；
- 修改主工作树现有未提交的 `GOALS.md`、`docs/CURRENT_DOCUMENTS.md`、cohort register、顶层架构或真实训练 Goal。

本分支当前唯一写入租约就是本协调文档。

## 五、本工作线的下一阶段：历史训练课程收口 V1

### 中心目标

在历史封存 Agent 完成一轮真实纠正后，把经独立审阅的结果转化为**可复用、但不过度推广的课程变化**：明确以后 Agent 应改变哪个问题、证据要求或责任边界，同时继续拒绝把单次成功升级为方法发布。

本阶段不再寻找新公司、不读取新结果、不运行 holdout，也不创建第二套控制面。

### 输入

只接受以下不可变、独立审阅后的工件：

1. Round 10 completion 与 `NO_MATERIAL_UTILITY` review；
2. 历史封存主线未来交付的 roster identity、pre-outcome freeze、settlement、material-correction review 和 cross-company application review；
3. 既有 training-program 中的权限和 holdout reservation 状态，只读使用。

原始 outcome 数值、预测方向、价格、CJO、估值和报告不是本阶段输入。

### 原子步骤

1. **区分四类证据**  
   将现有工件严格分为：管线可运行、字段可结算、材料判断被纠正、跨公司应用有效。前两类不得替代后两类。

2. **重建材料纠正链**  
   只从独立审阅工件回答：原判断是什么、哪项官方证据推翻或收窄了它、如果不纠正会怎样影响经营质量/owner cash/永久损失判断、下一公司具体改变了什么。

3. **裁定唯一课程变化**  
   每轮至多产生一项课程变化。它必须改变未来 episode 的问题、最小可区分证据或材料投资处理字段；“增加维度、增加说明、增加 UNKNOWN”本身无效。

4. **检查防御性写作**  
   判断结果前对象是否用 UNKNOWN/NO_PRIMARY 逃避材料判断，或只列证据边界却不解释投资损失。修复优先落在任务目标、课程提示和审阅标准，不新增 admission gate。

5. **生成未来训练课程候选**  
   输出一份只面向未来 episode 的窄课程修订。不得回写既有冻结对象，也不得自动修改 CJO、估值、报告或投资权限。

6. **独立课程审阅**  
   Reviewer 只判断这项变化是否由已接受的材料纠正支持、是否在第二家公司产生了可观察的预冻结变化、是否被重复计功。证据不足时返回 `NO_CURRICULUM_CHANGE`。

### 验收出口

本阶段成功需要同时满足：

- Round 10 的 `NO_MATERIAL_UTILITY` 被保留为负面方法证据，不被后续文字洗成成功；
- 历史封存主线至少提供一项独立确认的材料纠正，否则诚实退出 `NO_CURRICULUM_CHANGE`；
- 课程变化具体到一个未来问题、证据要求或责任边界；
- 同一纠正在多家公司只计一次，不把应用次数当方法胜率；
- 未来 holdout 仍保持独立和未揭示，但不阻断课程候选；
- 不产生 method release、CJO、估值、报告、BuyBand 或投资权限。

## 六、后续顺序

```text
历史封存 Agent 完成真实纠正与跨公司应用
→ 本工作线完成课程收口与独立审阅
→ 用课程修订启动下一批未见历史 episode
→ 累积多次材料纠正后冻结方法候选
→ 最后才启用已保留的公司轴/时间轴 holdout
```

### 暂不启动

- 新一轮家电、建材或其他行业 roster；
- 新 acquisition/measurement schema；
- Comparative/H2/V5 样本生产；
- prospective shadow 的结果揭示；
- CJO、估值、BuyBand、黄金报告或交易接入；
- 为了“看起来完整”而新增状态机、哈希、兼容层或治理门。

## 七、仓库状态说明

- 主工作树 `main@b9ff632` 存在用户/其他 Agent 的未提交文档，未被本工作线读取为完成事实，也未被修改、暂存、清理或提交；
- 家电 Round 10 V2 位于独立、干净、merge-ready 的 `dd688820c10d`，尚不能因本协调工件自动视为已合入 main；
- 历史封存训练主线当前记为 `IN_PROGRESS_EXTERNAL_AGENT / ARTIFACTS_NOT_YET_CONSUMED`；在其独立 completion/review 到位前，本工作线只维护协调计划。
