# CN600161 天坛生物 × 2024-05-01 独立结果前审阅

## Verdict

**RETURN**

**FY2024 outcome access authorization：NOT AUTHORIZED。** 当前退回只针对会 materially change 企业处理的 outcome 结算逻辑；没有以格式、措辞或仓库整洁度阻断。

审阅仅使用 `FORECASTER_PACKET.json`、FY2021/FY2022/FY2023 年报和 `29_CN600161_HOLDOUT_PREOUTCOME_JUDGMENT.json`。未接触 FY2024、价格、回报、前案、Teaching、feedback 或其他派生材料。

## 结果前产品判断

企业判断主体达到“明确、可反驳、非防御性”的标准。2021—2023 年收入、营业利润、归母扣非利润、采浆量、项目进度、集团现金代理、成都蓉生 NCI 和母公司现金边界均能在允许的年报中找到对应载体：

- 收入由 41.12 亿元升至 51.80 亿元，归母扣非利润由 7.56 亿元升至 11.04 亿元；2023 年营业利润约 18.05 亿元、营业利润率约 34.8%，相对 2022 年提高约 1.2 个百分点。以收入、营业利润、归母扣非利润和持续费用共同判断新增供给的初步经济吸收，责任边界基本正确。
- 79 家在营浆站、2,415 吨采浆、102 家浆站总数和三个设计产能 1,200 吨的基地没有被直接资本化；文本明确要求经常营业利润、归母扣非利润、折旧、费用和存货共同验证。这部分通过。
- 2023 年集团 OCF 约 23.94 亿元、购建长期资产现金约 10.78 亿元，约 13.16 亿元被正确称为 `GROUP_CASH_PROXY`；成都蓉生 25.995% NCI、约 4.00 亿元合并少数股东损益，以及母公司现金中包含大额筹资流入和其他应付款的事实均被识别。`COUNT_CONDITIONALLY` 合理，没有把集团现金直接等同于母公司 owner cash。
- 质量监管风险有召回、长期停产、GMP 重大缺陷、许可证暂停/撤销、批签发持续失败等观察载体；缺失披露本身不触发 adverse，`LOCAL_UNKNOWN`/`MEASUREMENT_MISMATCH` 的 `axis_updates` 为空。这部分不是风险清单式拒绝。
- 当前 `POSITIVE_CREDIT / RAISE / COUNT_CONDITIONALLY / MAINTAIN_CONSTRAINT / UP` 的快照在 cutoff 证据下可辩护；`UP` 由经费用责任边界验证的经常盈利支持，没有消费市场价格。

因此，本次不是要求重写企业判断；只需修复以下材料性结算缺陷。

## Material return 1：NCI/母公司上划事实越界，破坏局部未知

**根因分类：REASONING。**

### 为什么低于标准

`FY2024_ECONOMIC_ABSORPTION` 和 `FY2024_QUALITY_AND_REGULATORY_TAIL` 的每个 `valid_input_first_match` 都要求：

- `required_nci_scope_at_settlement = CLOSED 或 IMMATERIAL_WITH_EVIDENCE`
- `required_parent_access_at_settlement = EVIDENCED`

但这两个 cell 都把 `owner_cash` 列为 preserved axis，且明确声称不消费母公司上划事实。归母扣非利润已经提供上市公司股东盈利归属载体；质量事件的发生、材料性和可逆性也不依赖母公司是否收到子公司现金。把 NCI/母公司上划设成所有分类的前置门槛，会使 owner-cash 的局部未知阻断 management、normal earnings、permanent loss 和 valuation direction，和 cell 自己的责任边界相矛盾。

### 经济影响

即使 FY2024 销量、收入、经常营业利润、费用和归母扣非利润完整，或核心主体的许可证事件已经被明确观察，只要母公司非融资性上划没有披露，当前结构仍无法合法结算相应 cell。其结果是拒绝本来可以形成的盈利/质量判断，或诱使结算者把“上划未知”错误传播为其他轴的恶化，直接削弱 forecast 的可反驳性和投资用途。

### 缺失事实

不是 packet 缺少更多历史数据。缺的是 cell 级别的责任边界声明：

- 经济吸收只需同责任边界收入/销量、经常利润、持续费用及归母归属；母公司现金可达性不是前提。
- 质量监管只需事件主体、产品/浆量材料性、停产/许可影响和可逆性；NCI 与母公司上划不是事件分类前提。
- NCI 分配、集团现金代理和母公司上划只在 owner-cash/capital-burden cell 内闭合。

### 禁止假设

- 禁止把 `parent_access=UNKNOWN` 当成盈利吸收或质量事件无法分类的理由。
- 禁止把 `nci_scope=OPEN` 自动传播成 normal earnings、management、quality 或 valuation 的 adverse。
- 禁止因为年报未证明现金上划，就否定已经由归母扣非利润闭合的上市公司股东盈利方向。

### 最小可执行修复

从经济吸收和质量监管 cell 的 settlement scope 中移除 NCI 与 parent-access 前提，或明确标为 `NOT_REQUIRED_FOR_THIS_CELL`；只在 owner-cash cell 保留 `CLOSED/IMMATERIAL_WITH_EVIDENCE` 与 `EVIDENCED/BLOCKED_WITH_EVIDENCE` 的归属要求。经济吸收若使用合并营业利润率，继续用归母扣非利润和少数股东损益作归属交叉检查即可，不得要求现金已经上划。

### 可机械验收反例

1. 输入完整且可比：血液制品收入 +12%、归母扣非利润 +12%、经常营业利润率 34.5%、持续费用全部进入责任边界；`nci_scope=OPEN`、`parent_access=UNKNOWN`。必须命中吸收 cell 的有效数值分类，owner-cash cell 单独 `LOCAL_UNKNOWN`；不得令吸收 cell unknown。
2. 已观察到核心生产主体许可证被暂停且预计跨期恢复，`parent_access=UNKNOWN`。必须命中质量 adverse；不得因母公司上划未知拒绝结算。
3. 除 owner-cash cell 外，任何 cell 的 `scope_requirements` 不得机械要求母公司非融资性上划证据。

## Material return 2：first-match 不互斥，完整的明确恶化可落入 NEUTRAL

**根因分类：REASONING。**

### 为什么低于标准

经济吸收 cell 至少存在两类可机械复现的问题：

1. `ABSORPTION_FAVORABLE` 与 `ABSORPTION_MIXED` 可同时成立。比如收入和归母扣非利润均增长 12%，营业利润率为 34.5%：它满足 favorable 的“不低于 34.3%”，但相对 2023 年约 34.8% 又属于 mixed 所写的“利润率恶化”。数组顺序替代了经济定义，分类并不互斥。
2. adverse 要求收入至少下降 5%、归母扣非利润至少下降 10%、利润率降至 32.8% 或以下三项同时出现。完整、同向且有负面载体的材料恶化可能因为只差一个阈值而进入 residual。例如收入 -8%、归母扣非利润 -15%、利润率 33.4%，且真实销量下降；它不满足三项合取，也不是“方向冲突”的 mixed，最终落入 `ABSORPTION_NEUTRAL_RESIDUAL`，得到 `POSITIVE_CREDIT / UNCHANGED / UP`。这不是中性剩余，而是被门槛漏掉的明确负面经济载体。

owner-cash cell 也有语义重叠风险：`OWNER_CASH_FAVORABLE` 的“可持续覆盖母公司费用与股东分配”和 mixed 的“可上划比例仍有限但未被阻断”可以同时为真；“有限”没有一个排除 favorable 的机械边界。

### 经济影响

同一完整 outcome 可能因列表顺序得到不同处理；更严重的是，销量、利润和利润率同向下降且已观察到负面载体时，仍可保留正面管理信用和向上估值方向。这可 materially 高估 normal earnings、内在价值方向并低估需求吸收失败。

### 缺失事实

缺少的是分类定义，不是更多年报字段：

- “利润率恶化”是否要求材料阈值；
- adverse 的多指标合取/析取规则，以及载体与严重度的对应关系；
- owner cash 的“上划有限”相对“足以覆盖”的排他边界；
- residual 只容纳经济上无材料方向变化的输入，而不是所有未过严格阈值的输入。

### 禁止假设

- 禁止把 first-match 的数组先后当成互斥性的替代品。
- 禁止把“未同时穿越三个 adverse 阈值”解释成经济中性。
- 禁止把完整输入的 residual 默认保留 `POSITIVE_CREDIT` 和 `UP`，除非已证明剩余补集只包含无材料变化。

### 最小可执行修复

把三个数值分类写成显式排他的集合：favorable 先定义材料改善；adverse 以明确观察到的负面载体加“材料的同向盈利恶化”定义，不应机械要求三个指标全部穿阈值；mixed 只处理经过材料阈值后的方向冲突，并显式排除 favorable/adverse；residual 仅容纳完整、可比且无材料变化的剩余。owner-cash mixed 需明确“可上划但不足以持续覆盖母公司费用与股东分配”，从而排除 favorable。

### 可机械验收反例

1. 收入 +12%、归母扣非 +12%、利润率 34.5%：在同一 cell 中恰好命中一个 class，不能同时满足 favorable 与 mixed。
2. 收入 -8%、归母扣非 -15%、利润率 33.4%，并观察到真实销量下降：不得命中 `NEUTRAL_RESIDUAL`，不得输出 `POSITIVE_CREDIT / UP`。
3. 收入、利润和利润率字段任一缺失：必须在数值分类前命中局部 `LOCAL_UNKNOWN`，`axis_updates={}`，不得命中 adverse。
4. 集团现金代理充足、上划可持续覆盖母公司费用与股东分配：不得同时满足 owner-cash favorable 与“上划有限”的 mixed。

## Material return 3：三个 cell 对全局轴互相覆盖，且严重质量事件漏掉 normal earnings

**根因分类：MODEL、REASONING。**

### 为什么低于标准

三个 cell 都会写 `valuation_direction`；owner-cash 与质量 cell 都会写 `permanent_loss`；经济吸收与质量 cell 都会写 `management_execution`，但草案没有任何跨 cell 的聚合、优先级、冲突或联合结算规则。

这不是形式问题。当前可同时产生：

- 吸收 favorable：`valuation_direction=UP`
- owner cash structural adverse：`permanent_loss=TIGHTEN_CONSTRAINT, valuation_direction=DOWN`
- quality neutral：`permanent_loss=MAINTAIN_CONSTRAINT, valuation_direction=UP`

如果按数组后写覆盖，quality neutral 会抹去已观察到的结构性现金吞噬；如果按先写覆盖，质量 thesis-blocking 又可能被现金 favorable 抹去。任何一种隐含顺序都可能改变永久损失和估值结论。

此外，`OWNER_CASH_FAVORABLE` 仅闭合资本负担，却把全局 `permanent_loss` 设为 `RELAX_CONSTRAINT`。当前 permanent-loss 约束同时包含质量监管、浆站合规、价格/采浆成本和需求吸收，资本现金改善不能单独放松整条约束。反向地，质量 cell 的 thesis-blocking 分支包含核心主体长期停产、许可证暂停/撤销等会直接破坏持续供给和未来经常利润的载体，却把 `normal_earnings` 作为 preserved axis；这会留下 `THESIS_BLOCKING` 与 `normal_earnings=RAISE` 并存而没有解释的状态。

### 经济影响

最终 enterprise treatment 不唯一，并会随实现顺序而变。它可把核心质量事件降格、把持续现金吞噬抹平，或在核心供给资格受损后仍维持上调的 normal earnings，直接改变永久损失判断、内在价值方向和下一步研究结论。

### 缺失事实

缺少的不是 outcome 数据，而是：

- 跨 cell 对同一全局轴的确定性聚合规则；
- `THESIS_BLOCKING`、`TIGHTEN_CONSTRAINT`、`MAINTAIN_CONSTRAINT`、`RELAX_CONSTRAINT` 的支配关系及适用范围；
- 中性 cell 是“保持当前状态”而非重新写入一个可覆盖其他 cell 的方向代码；
- 核心质量/许可载体到 normal earnings 的直接因果桥。

### 禁止假设

- 禁止依赖 JSON 数组顺序或实现的 last-write/first-write 行为解决投资处理冲突。
- 禁止让一个 cell 的 neutral 结果覆盖另一个 cell 已观察到的 adverse 载体。
- 禁止因现金转换改善就推定质量、价格、需求吸收等永久损失载体一并缓解。
- 禁止在核心长期停产或许可证能力受损时，仅因年度利润尚未量化而保持 `normal_earnings=RAISE`。

### 最小可执行修复

增加明确、可机械执行的跨 cell 聚合规则，或把 cell 输出改成局部证据/增量后只在一个联合结算器中生成全局 treatment。至少应满足：

- `THESIS_BLOCKING` 不可被任何 neutral/favorable cell 覆盖；已观察到的结构性 cash adverse 不可被 quality neutral 覆盖。
- neutral 只保持进入该 cell 前的轴状态，不产生跨 cell 的有利升级。
- owner-cash favorable 最多放松“资本负担/上划”这一局部约束；只有其余材料永久损失载体也闭合，才可把全局轴改为 `RELAX_CONSTRAINT`。
- 将 normal earnings 纳入严重质量分支的 direct effect：核心、跨期且难逆的停产/许可证损害应 `LOWER`；非材料且快速整改事项与无事件 residual 不得自动下调。

### 可机械验收反例

1. absorption favorable + owner-cash structural adverse + quality neutral：联合结算必须唯一；quality neutral 不得把 `TIGHTEN_CONSTRAINT/DOWN` 改回 `MAINTAIN_CONSTRAINT/UP`。
2. quality thesis-blocking adverse + owner-cash favorable：最终必须保留 `THESIS_BLOCKING` 和 `DOWN`；不得因 cash favorable 变成 `RELAX_CONSTRAINT/UP`。
3. 核心主体许可证被撤销并造成跨期供给中断：最终 normal earnings 不得继续为 `RAISE`，即使当年报表利润尚受库存销售支撑。
4. 三个 cell 以任意执行顺序输入同一事实集，最终五个 treatment codes 必须完全一致。

## Acceptance gate for resubmission

仅需重交修复后的 judgment JSON；无需改写已通过的企业判断主体。再次审阅的机械门槛是：

1. NCI、group cash 与母公司上划未知只局部影响 owner-cash/capital-burden，不阻断经济吸收或质量监管分类。
2. 每个 cell 的完整可比 first-match 条件互斥且穷尽；`LOCAL_UNKNOWN`/`MEASUREMENT_MISMATCH` 先于数值分类并保持空更新；adverse 必须由已观察负面载体触发，完整输入的 residual 不得吞入材料恶化。
3. 多 cell 对相同全局轴有顺序无关、唯一且经济上保守的联合结算；neutral 不覆盖 adverse，局部现金改善不放松未闭合的其他永久损失载体。
4. 核心、跨期、难逆的质量/许可损害同时进入 normal earnings 的直接因果桥；轻微或缺失披露不传播为恶化。
5. 以上反例全部通过后，才可 **ACCEPT** 并授权创建 FY2024 outcome access authorization。

---

## 第二轮独立结果前复审

### Second-round verdict

**RETURN**

**FY2024 outcome access authorization：NOT AUTHORIZED。**

本轮只复审当前 `29_CN600161_HOLDOUT_PREOUTCOME_JUDGMENT.json` 与本文件，没有读取 FY2024、价格、回报、前案或其他材料。原三项材料性退回已经实质修复，但合法输入穷尽检查发现新的可达空档；在补齐前，结果后结算仍可能没有唯一合法 class。

### 原退回项逐个重放

以下修复均通过，不再构成阻断：

| 重放输入 | 当前命中/联合结果 | 复审 |
|---|---|---|
| 吸收 `+12% / +12% / 34.5%`，NCI open、parent access unknown | 只命中 `ABSORPTION_FAVORABLE`；吸收 cell 不消费 cash scope | PASS |
| 吸收 `-8% / -15% / 33.4%`，已观察真实销量下降 | 三项中收入、归母扣非两项过负面阈值且有载体，命中 `ABSORPTION_ADVERSE` | PASS |
| 吸收利润率字段缺失、无口径冲突 | 在数值分类前命中 `LOCAL_UNKNOWN`，空更新 | PASS |
| 核心许可证暂停、跨期且难逆，parent access unknown | 命中 `QUALITY_THESIS_BLOCKING_ADVERSE`，包含 `normal_earnings=LOWER` | PASS |
| group cash 强、归母桥闭合且 parent distributable cash 足额覆盖 | 只命中 `OWNER_CASH_FAVORABLE`；LIMITED 分支明确要求低于覆盖需求 | PASS |
| absorption favorable + cash structural adverse + quality neutral | neutral 空更新；联合结果保留 `TIGHTEN_CONSTRAINT / DOWN` | PASS |
| quality thesis-blocking + cash favorable | 联合结果保留 `NEGATIVE_CREDIT / LOWER / THESIS_BLOCKING / DOWN` | PASS |

跨-cell 聚合使用逐轴固定风险优先序，neutral 不提交更新，两个给定联合反例在任意执行顺序下结果相同。现金 favorable 也不再直接 `RELAX_CONSTRAINT`。原审阅的 NCI/parent-access 越界、给定 first-match 重叠、neutral 覆盖 adverse、严重质量事件漏掉 normal earnings 四个具体问题均已关闭。

## Second-round material return：三个 cell 仍未穷尽合法输入

**根因分类：MODEL、REASONING。** 不属于 `DATA_COVERAGE` 或 `ACQUISITION_MODULE`；所需 outcome 字段可以全部存在，缺的是模型分支。

### 为什么低于标准

#### 1. 吸收 cell 在 FAVORABLE/ADVERSE 之外只接“正负冲突”，单向但不足两票的材料信号无 class

`ABSORPTION_ADVERSE` 现在合理地要求三项中至少两项过负面阈值，并要求已观察载体；`ABSORPTION_MIXED` 却又要求至少一个材料正向信号和至少一个材料负向信号。于是下列完整、可比输入均不满足任何 class：

- 收入下降 6%、归母扣非下降 5%、利润率 34.5%，并观察到真实销量下降：只有一个量化负面阈值，没有材料正向信号；不是 adverse，不是 mixed，也不能满足“未出现材料负向”的 neutral residual。
- 收入下降 8%、归母扣非下降 15%、利润率 34.0%，但没有观察到条件列举的匹配载体：量化上有两票负面，但 adverse 因载体缺失必须不触发；没有正向信号又无法进入 mixed；它也不是无材料方向的 neutral。
- 收入增长 12%、归母扣非增长 5%、利润率恰为 33.8% 且有成本载体：favorable 不成立，adverse 只有一票；mixed 的利润率负面条件写成“33.8%以下”，没有覆盖 adverse 所用的“33.8%或以下”，neutral 又不能接材料正向/负向输入。

此外，favorable 以“不存在材料负面需求或单位经济载体”排除一部分输入，但 mixed 的负面信号只认收入、归母扣非和利润率。例如财务指标向好但真实销量材料下降、靠提价补足的完整输入，可能被 favorable 排除，却没有 mixed 去承接。

#### 2. owner-cash cell 没有承接“集团现金非正、非结构性、cash scope open”

`OWNER_CASH_GROUP_POSITIVE_SCOPE_OPEN` 只承接正的 group proxy；`OWNER_CASH_REVERSIBLE_OR_MIXED` 的两个 OR 分支共用 `NCI=CLOSED/IMMATERIAL`、`parent access=EVIDENCED`。因此，集团现金桥完整、proxy 为轻微负值或零、原因可逆/不满足结构性 adverse，但 NCI 或 parent distributable cash 尚未闭合时：

- 不触发 `LOCAL_UNKNOWN`，因为集团现金核心字段都已披露；
- 不触发 structural adverse；
- 不满足 group-positive-scope-open；
- 又因 cash scope open 无法进入 reversible/mixed 或 neutral residual。

这是本公司的受支持核心边界，不是冷门构造：group proxy 可以先结算，而 NCI/母公司上划仍保持 open。局部化 unknown 的目的正是允许这两个层次分开。

#### 3. 质量 cell 在 thesis-blocking 与“非材料短期整改”之间缺少材料但可逆分支

`QUALITY_THESIS_BLOCKING_ADVERSE` 要求核心/材料事件跨期且难逆；`QUALITY_CONTAINED_MIXED` 又限定影响主体/产品不材料。若已观察到材料性召回或核心主体短期停产，但在报告期内完成整改、没有跨期许可证能力损失：

- 不是 thesis-blocking；
- 不是“不材料”的 contained；
- 不是 local unknown/mismatch；
- 也绝不能进入“未观察到负面载体”的 neutral residual。

材料但可逆的质量事件会影响管理执行信用，是否影响 normal earnings、permanent loss 或 valuation 则应由持续性和实际经济载体决定；不能因它不够严重到 thesis-blocking 就没有分类。

### 经济影响

这些空档会让完整 FY2024 输入无法结算，迫使结果后执行者在没有预先规则时临时选择 `LOCAL_UNKNOWN`、`NEUTRAL` 或 `ADVERSE`：

- 单一材料吸收负信号可能被错误视为 neutral，或在没有观察载体时被错误升级为 adverse，改变 management、normal earnings 与 valuation direction。
- 非结构性负 group cash 可能因 NCI/上划未闭合而丢失已观察到的集团现金事实，或越界传播到 permanent loss。
- 材料但可逆的召回/停产可能被错误升级为 thesis-blocking，或被 neutral 忽略，直接改变永久损失与估值结论。

### 缺失事实

无需新增任何 outcome 数据字段。缺的是三个明确分支：

1. 吸收：完整输入中，存在材料信号但不足以满足 favorable/adverse，或量化恶化没有匹配 adverse carrier 时的 `MIXED` 承接规则。
2. owner cash：group proxy 非正但不构成结构性 adverse、同时 NCI/parent scope open 时的局部条件计入规则。
3. 质量：已观察、材料但短期可逆且没有持续许可/供给损害的事件分支。

### 禁止假设

- 禁止把“一项材料负面但不足 adverse 两票”当作“无材料方向变化”。
- 禁止仅凭两项量化下降、在没有已观察经济载体时触发 adverse；这类输入应由 mixed/待归因分支承接，不能由缺失触发恶化。
- 禁止因 group cash 非正就要求 NCI 与 parent access 必须先闭合，或把 open scope 当作结构性现金 adverse。
- 禁止把所有材料质量事件等同于跨期难逆，也禁止把材料但可逆事件塞入 neutral。
- 禁止依赖 first-match 数组顺序填补没有条件覆盖的集合。

### 最小可执行修复

1. 将 `ABSORPTION_MIXED` 扩为完整输入的材料非决定性补集：在显式排除 favorable/adverse 后，承接正负冲突、只有一个材料方向信号、以及达到量化 adverse 门槛但没有匹配观察载体的输入；最后的 neutral residual 才能严格等于“无材料信号”。统一 `33.8%` 的包含边界，并把会排除 favorable 的材料销量/需求/单位经济载体纳入 mixed 的负向定义。没有载体的量化下降不得输出 adverse updates。
2. 把 `OWNER_CASH_REVERSIBLE_OR_MIXED` 的两个 OR 路径拆开：集团轻微负值/零值且可逆的路径允许 `NCI/parent=OPEN`，只更新或保持 `owner_cash=COUNT_CONDITIONALLY`；“归母桥已闭合但 distributable cash LIMITED”的路径继续要求 closed/evidenced。也可新增等价的 `OWNER_CASH_GROUP_NONSTRUCTURAL_SCOPE_OPEN`，但不得更新 permanent loss 或 valuation。
3. 新增 `QUALITY_MATERIAL_REVERSIBLE_MIXED`：要求已观察材料事件、整改与恢复可验证、没有跨期停产或持续许可证能力损失；至少更新 management execution，其他轴只在存在各自直接载体时更新。保持它与 thesis-blocking、非材料 contained、neutral residual 互斥。

### 可机械验收反例

1. 吸收桥完整：收入 -6%、归母扣非 -5%、利润率 34.5%，观察到真实销量下降。必须恰好命中一个非 adverse、非 neutral 的 class；不得无 class。
2. 吸收桥完整：收入 -8%、归母扣非 -15%、利润率 34.0%，没有观察到匹配负面载体。不得命中 adverse，也不得无 class；`axis_updates` 不得把缺失载体当恶化。
3. 吸收桥完整：收入 +12%、归母扣非 +5%、利润率恰为 33.8% 且有匹配成本载体。必须恰好命中一个 class；`33.8%` 不得成为集合边界空档。
4. group proxy 为负 1 亿元，集团现金桥完整且负值由近完工一次性项目解释，`NCI=OPEN`、`parent access=UNKNOWN`。必须命中局部 owner-cash mixed/conditional 分支，不得 local unknown、structural adverse 或无 class；permanent loss 与 valuation 保持。
5. 已观察到材料性产品召回并造成核心主体停产两个月，但整改、恢复生产和许可证有效性均在报告期内确认，没有跨期供给损害。必须命中材料可逆质量分支，不得 thesis-blocking、neutral 或无 class。
6. 修复后重新重放本轮上表七项原反例，均须继续通过；三个 cell 的完整合法输入集合须各自恰好命中一个 first-match class，跨-cell 聚合在任意执行顺序下保持相同结果。

以上空档关闭前，第二轮仍为 **RETURN**；关闭并通过机械反例后，方可 **ACCEPT** 并只授权创建 FY2024 outcome access authorization。

---

## 第三轮独立结果前复审

### Third-round verdict

**RETURN**

**FY2024 outcome access authorization：NOT AUTHORIZED。** 本轮不授权直接读取任何 outcome。

本轮只读取当前 `29_CN600161_HOLDOUT_PREOUTCOME_JUDGMENT.json`。未读取 FY2024、outcome、价格、回报、前案或其他材料。判断仅按是否可能改变 management execution、normal earnings、owner cash、permanent loss 或 valuation direction；未做格式审计。

### 既定机械反例重放

第二轮六项与原七项全部通过：

- `+12% / +12% / 34.5%` 且 cash scope open：只命中 `ABSORPTION_FAVORABLE`，不消费 NCI/parent access。
- `-8% / -15% / 33.4%` 且已观察销量下降：命中 `ABSORPTION_ADVERSE`。
- 吸收关键字段缺失：先命中局部 `LOCAL_UNKNOWN`，空更新。
- 核心许可证暂停、跨期且难逆：命中 `QUALITY_THESIS_BLOCKING_ADVERSE`，包含 `normal_earnings=LOWER`。
- group cash、归母桥及 parent distributable cash 全部满足 favorable：只命中 `OWNER_CASH_FAVORABLE`，不与 LIMITED 路径重叠。
- `-6% / -5% / 34.5%` 且销量下降：命中 `ABSORPTION_MIXED`。
- `-8% / -15% / 34.0%` 但无匹配观察载体：命中 `ABSORPTION_MIXED`，没有把缺失载体升级为 adverse。
- `+12% / +5% / 33.8%` 且有持续成本载体：命中 `ABSORPTION_MIXED`；`33.8%` 边界已闭合。
- group proxy 负 1 亿元、一次性可逆、NCI 与 parent access 均 open：命中 `OWNER_CASH_GROUP_NONSTRUCTURAL_SCOPE_OPEN`，只维持 `COUNT_CONDITIONALLY`。
- 材料召回、停产两个月且报告期内可验证恢复：命中 `QUALITY_MATERIAL_REVERSIBLE_MIXED`，只降低管理执行信用。
- absorption favorable + cash structural adverse + quality neutral：最终保留 `TIGHTEN_CONSTRAINT / DOWN`。
- quality thesis-blocking + cash favorable：最终保留 `NEGATIVE_CREDIT / LOWER / THESIS_BLOCKING / DOWN`。

固定逐轴风险优先序对参与更新的集合做选择，neutral/unknown 均为空更新；因此上述两个跨-cell 反例不依赖执行顺序。吸收格在桥字段完整可比时，favorable/adverse 先匹配，其余任何列明的材料信号进入 mixed，没有材料信号才进入 neutral residual；当前受支持输入已互斥穷尽。

## Third-round material return 1：owner-cash 的“任一 scope open”条件与 scope requirements 冲突

**根因分类：MODEL、REASONING。**

### 为什么低于标准

`OWNER_CASH_GROUP_POSITIVE_SCOPE_OPEN` 和 `OWNER_CASH_GROUP_NONSTRUCTURAL_SCOPE_OPEN` 的 condition 都写明：NCI 归属、母公司上划或 `PARENT_DISTRIBUTABLE_CASH` **任一**未闭合即可进入；但两类的 `scope_requirements` 同时要求：

- `required_nci_scope_at_settlement = OPEN_OR_UNKNOWN`
- `required_parent_access_at_settlement = UNKNOWN_OR_PARTIAL`

这把 condition 的 OR 变成了 scope 层的 AND。合法且常见的部分闭合输入因此无 class：

1. group proxy 为正、无结构性 adverse，`NCI=CLOSED`、`parent access=UNKNOWN`；
2. group proxy 为正、`NCI=OPEN`、parent access 已 evidenc​​ed，但 `PARENT_DISTRIBUTABLE_CASH` 金额仍未闭合；
3. group proxy 非正但非结构性 adverse，`NCI=CLOSED`、`parent access=UNKNOWN`。

这些输入不属于 group-core `LOCAL_UNKNOWN`，不能 favorable，也不满足 closed-scope mixed/neutral；按当前 scope 前提无法完成唯一 first-match。

### 经济影响

部分归属已经闭合、另一部分仍 open 时，正确处理应稳定为 `owner_cash=COUNT_CONDITIONALLY`。当前空档使实现者可能拒绝结算，或自行落入 closed residual/favorable，从而在 `COUNT_CONDITIONALLY` 与 `COUNT_IN_PARENT_OWNER_CASH` 之间改变 owner-cash 处理，并可能错误传播 valuation direction。

### 缺失事实

不缺 outcome 字段。缺的是 scope 组合语义：condition 已经声明“至少一项 open”，scope requirements 却没有允许另一项已经 closed/evidenced。

### 禁止假设

- 禁止假设 NCI open 与 parent access unknown 必须同时发生。
- 禁止因 NCI 已闭合就把 parent access unknown 当成整体 cash bridge 已闭合，反之亦然。
- 禁止用 first-match 顺序绕过 scope requirement 不成立。

### 最小可执行修复

将两个 scope-open class 的单项 scope requirements 改为允许各自 `ANY`，并增加联合约束“`NCI / parent access / PARENT_DISTRIBUTABLE_CASH` 至少一项 OPEN、UNKNOWN 或 PARTIAL”；或按 NCI-open、parent-open、amount-open 拆成互斥分支。无论采用哪种写法，只要任一必要归属尚未闭合，就只能 `COUNT_CONDITIONALLY`，不得更新 permanent loss 或 valuation。

### 可机械验收反例

1. group proxy 正、无结构性 adverse，`NCI=CLOSED`、`parent access=UNKNOWN`：恰好命中 `OWNER_CASH_GROUP_POSITIVE_SCOPE_OPEN`，输出 `COUNT_CONDITIONALLY`。
2. group proxy 正、`NCI=OPEN`、parent access evidenc​​ed、distributable amount unknown：恰好命中 scope-open class，不能 favorable/neutral。
3. group proxy 负 1 亿元且非结构性，`NCI=CLOSED`、`parent access=UNKNOWN`：恰好命中 `OWNER_CASH_GROUP_NONSTRUCTURAL_SCOPE_OPEN`，不更新 permanent loss/valuation。

## Third-round material return 2：已观察材料质量事件但恢复状态未知时无局部 UNKNOWN

**根因分类：REASONING。**

### 为什么低于标准

质量 `LOCAL_UNKNOWN` 只承接“是否发生、主体或材料性”不能确认；没有承接事件已经确认且材料，但恢复时间、后续批签发、许可证有效性、跨期供给或信任损害仍未知的输入。

这类输入不能命中：

- thesis-blocking，因为跨期且难逆尚未被观察；
- material reversible，因为报告期内恢复尚未得到确认；
- contained，因为事件材料；
- neutral，因为已经观察到负面载体。

同理，已观察非材料事项但是否完成整改、是否持续影响生产未知时，也没有明确局部承接分支。

### 经济影响

材料召回、停产或许可证事项的恢复状态未知，正是 `THESIS_BLOCKING / LOWER / DOWN` 与仅降低管理信用、甚至暂不更新之间的分界。没有局部 unknown 会迫使执行者把未观察的持续性当成严重恶化，或反过来把已观察事件当成 neutral，可直接改变 management execution、normal earnings、permanent loss 与 valuation direction 四个轴。

### 缺失事实

缺的不是新数据源，而是将以下尚未披露事实声明为该质量 cell 的局部 unknown：恢复完成与否、恢复时点、后续批签发/生产、许可证有效性、跨期供给影响和持续信任损害。

### 禁止假设

- 禁止从“已发生材料事件”直接假设其跨期难逆。
- 禁止从年报没有给出恢复细节推定已经恢复。
- 禁止让该局部未知传播到 owner cash 或拒绝整个企业判断。

### 最小可执行修复

扩展质量 `LOCAL_UNKNOWN` 的 condition：若事件发生、主体或材料性，以及一旦观察到事件后的恢复/持续性关键字段中任一不能确认，均先局部结算为 `LOCAL_UNKNOWN`，`axis_updates={}`；已明确跨期难逆才 adverse，已明确报告期内恢复才 material-reversible/contained。为保持 first-match 互斥，thesis-blocking 与 reversible class 必须要求各自持续性事实已经观察，而不是由缺失推断。

### 可机械验收反例

1. 已确认核心主体发生材料召回，但恢复时点、后续批签发和许可证状态均未披露：命中质量 `LOCAL_UNKNOWN`，空更新；不得 adverse、reversible 或 neutral。
2. 已确认非材料检查缺陷，但是否完成整改及是否影响后续生产未知：命中质量 `LOCAL_UNKNOWN`，空更新。
3. 同一输入下，吸收与 owner-cash cell 仍按各自完整字段独立结算；质量 unknown 不得吞掉企业快照或传播到其他轴。

### 第三轮再提交门槛

只需关闭上述两个部分信息组合空档并重放新增六个反例；本轮已经通过的十三项必须保持通过，跨-cell 聚合须继续顺序无关。修复前维持 **RETURN**，不授权 outcome access；全部通过后方可 **ACCEPT**，且只授权创建 outcome access authorization，不等于授权直接读取 outcome。

---

## 第四轮独立结果前复审

### Fourth-round verdict

**RETURN**

**FY2024 outcome access authorization：NOT AUTHORIZED。** 本轮不授权直接读取任何 outcome。

本轮只读取当前 `29_CN600161_HOLDOUT_PREOUTCOME_JUDGMENT.json`，没有读取 FY2024、outcome、价格、回报或前案。owner-cash partial combination 已按 `ANY + joint_open_requirement` 修复；第三轮新增的三个 owner-cash 反例均唯一命中预期 scope-open class。吸收格、其余质量反例和跨-cell 风险优先聚合也保持通过。

不过，质量 `LOCAL_UNKNOWN` 的新条件过宽，会吞掉已经具备充分 adverse 观察事实的输入，导致原十三项中的许可证反例不再通过。这会直接改变四个投资处理轴，不能按格式问题放行。

## Fourth-round material return：质量 LOCAL_UNKNOWN 从局部缺口扩大成 adverse 覆盖器

**根因分类：REASONING。**

### 为什么低于标准

质量 first-match 把 `LOCAL_UNKNOWN` 放在 severe adverse 之前，并规定：事件确认后，恢复完成、恢复时点、后续批签发/生产、许可证有效性、跨期供给影响或持续信任损害中 **任一**关键持续性事实不能确认，即命中 `LOCAL_UNKNOWN`。

这会错误覆盖已有充分严重证据的情况。原机械反例是“核心生产主体许可证被暂停、影响跨期且难逆”。该输入已经满足 `QUALITY_THESIS_BLOCKING_ADVERSE` 的核心主体、许可证损害、跨期和难逆四个必要事实；但只要没有另行披露持续信任损害或后续批签发，当前 first-match 仍会先命中 `LOCAL_UNKNOWN` 并空更新。

同理，若已观察到核心主体长期停产且恢复需跨期重新认证，缺少一个不影响 severe 结论的附属字段也会撤销 adverse。UNKNOWN 应承接“现有事实不足以区分 severe 与 reversible”的局部缺口，不能要求所有列举字段同时完备，更不能覆盖已经闭合的严重路径。

### 经济影响

该错误会把本应为：

- `management_execution=NEGATIVE_CREDIT`
- `normal_earnings=LOWER`
- `permanent_loss=THESIS_BLOCKING`
- `valuation_direction=DOWN`

的已观察严重许可证/长期停产事实改为空更新，并保留结果前的 `POSITIVE_CREDIT / RAISE / MAINTAIN_CONSTRAINT / UP`。这是直接、材料性的投资结论反转。

### 缺失事实

不需要新增 outcome 字段。缺的是“充分事实”判断：

- 已观察到任一条完整 severe 路径时，不应再要求与该路径无关的持续信任、批签发或其他字段全部齐备。
- 只有现有事实既不足以确认 severe、也不足以确认 material-reversible/contained 时，恢复或持续性缺口才应进入局部 `LOCAL_UNKNOWN`。

### 禁止假设

- 禁止把不相关附属字段缺失当作撤销已观察 severe carrier 的理由。
- 禁止要求“跨期难逆许可证损害”和“持续信任损害”同时闭合；当前 adverse condition 本身使用的是替代路径。
- 也禁止反向从事件发生推定 severe；若跨期、难逆或恢复事实确实不足，仍应保持局部 UNKNOWN。

### 最小可执行修复

收窄质量 `LOCAL_UNKNOWN`：增加“且当前已观察事实不足以满足 `QUALITY_THESIS_BLOCKING_ADVERSE`、`QUALITY_MATERIAL_REVERSIBLE_MIXED` 或 `QUALITY_CONTAINED_MIXED` 任一完整路径”的前提；或先机械判断是否已有完整 severe/reversible/contained 路径，再仅对无法归类的剩余输入结算局部 UNKNOWN。不要简单把所有事件都前置 adverse；恢复/持续性真正未知的输入仍须空更新。

### 可机械验收反例

1. 核心许可证暂停，已确认影响跨期且难逆；持续信任损害和后续批签发未披露：必须命中 `QUALITY_THESIS_BLOCKING_ADVERSE`，不得 `LOCAL_UNKNOWN`。
2. 核心主体长期停产，已确认需跨期重新认证；许可证以外的附属字段未披露：必须命中 severe adverse。
3. 已确认材料召回，但是否恢复、是否跨期和许可证状态均未知：必须命中 `LOCAL_UNKNOWN`，空更新，不得 severe 或 reversible。
4. 已确认材料召回且报告期内恢复、后续生产和许可证有效性已闭合，无跨期损害：必须命中 `QUALITY_MATERIAL_REVERSIBLE_MIXED`。
5. 上述质量 UNKNOWN 仅空更新本 cell；吸收和 owner-cash 仍独立结算。
6. 修复后必须重新通过此前全部十九项反例及两个跨-cell 顺序反例；任意执行顺序的最终 treatment codes 保持一致。

第四轮除这一材料逻辑外没有新增问题。关闭该覆盖关系并通过上述反例后，才可 **ACCEPT**，且只授权创建 outcome access authorization，不等于授权直接读取 outcome。

---

## 第五轮最终独立结果前复审

### Final verdict

**ACCEPT**

**授权范围：仅授权创建 FY2024 outcome access authorization。此 ACCEPT 不直接授权读取、打开或消费 FY2024 outcome。**

本轮只读取当前 `29_CN600161_HOLDOUT_PREOUTCOME_JUDGMENT.json`，没有读取 FY2024、outcome、价格、回报或前案，也没有进行格式审计。

### 最终机械结算结果

第四轮六项、此前全部既定反例以及两个跨-cell 顺序反例均通过：

- 质量 severe 完整路径不再被无关附属 UNKNOWN 覆盖。核心许可证暂停且影响跨期、难逆，即使持续信任损害或后续批签发未披露，仍命中 `QUALITY_THESIS_BLOCKING_ADVERSE`；跨期重新认证反例同样命中 severe。
- 材料事件的恢复、许可证状态和跨期影响确实不足以区分路径时，先命中质量 `LOCAL_UNKNOWN`，`axis_updates={}`；它不假设已经恢复，也不把缺失升级为 adverse。
- 材料事件在报告期内完成整改、恢复生产并确认许可证有效时，唯一命中 `QUALITY_MATERIAL_REVERSIBLE_MIXED`；非材料且完成短期整改的事项唯一命中 contained；完整披露且无观察载体才进入 neutral residual。三条事件路径与局部 UNKNOWN 现已排他。
- 质量 UNKNOWN 为空更新，吸收和 owner-cash 仍按各自字段独立结算，结果前企业快照不会因局部缺口被撤回。
- Owner-cash 两个 scope-open class 现使用单项 `ANY` 加联合 `joint_open_requirement`。`NCI=CLOSED / parent=UNKNOWN`、`NCI=OPEN / parent=EVIDENCED / amount=UNKNOWN` 及非结构性负 group cash 的部分闭合组合均唯一命中预期 class，只维持 `COUNT_CONDITIONALLY`，不越界更新 permanent loss 或 valuation。
- 吸收格对完整可比输入保持互斥穷尽：favorable 与有载体的两票 adverse 优先；其余任何材料财务、销量、价格、成本、折旧或存货信号进入 mixed；没有材料信号才进入 neutral。字段缺失和口径不匹配先局部结算且为空更新。
- 跨-cell 聚合只消费各 class 的非空更新，按固定逐轴风险优先序合并。`absorption favorable + cash structural adverse + quality neutral` 始终保留 `TIGHTEN_CONSTRAINT / DOWN`；`quality thesis-blocking + cash favorable` 始终保留 `NEGATIVE_CREDIT / LOWER / THESIS_BLOCKING / DOWN`。交换任意 cell 执行顺序不改变最终 treatment codes。

### Product-materiality conclusion

当前结果前企业判断明确、可反驳且不以未知拒绝公司；浆源/采浆/产能通过同责任边界的经常利润和持续费用验证需求吸收；group cash、NCI 与母公司上划保持在 owner-cash 边界；质量风险由观察载体结算；UNKNOWN/MISMATCH 局部且不触发 adverse；management execution、normal earnings、owner cash、permanent loss 与 valuation direction 的跨轴传播均有直接桥和顺序无关聚合。

未发现仍会 materially 改变投资结论、永久损失判断或估值方向的真实问题。此前各轮 RETURN 均由本轮 **ACCEPT** 关闭。下一步仅可创建 FY2024 outcome access authorization；在该授权被另行创建前，不得直接读取 outcome。
