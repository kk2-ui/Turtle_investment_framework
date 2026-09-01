# CN600323 paired historical holdout 独立 pre-outcome 审阅

## 结论

**RETURN — 发回 Enhanced arm；Baseline arm 的冻结判断可保留。**

这是一个 outcome-blind 结论。我只读取了成对包、两臂的 forecaster packet、pre-outcome judgment、execution receipt、Enhanced 的冻结方法包，以及 Baseline 目录中的 FY2021—FY2023 三份共同官方年报；未读取 FY2024、价格、回报、settlement、互联网或仓库旧公司报告，也没有从任务文字推断结果。

Baseline 不是稻草人。它形成了强而非防御性的结果前判断：明确把垃圾焚烧及剔除工程后的固废运营利润作为主要盈利锚，同时没有把燃气、现金流或杠杆的未知扩大成整案否定；它给出 `CONDITIONAL_CREDIT / EXCLUDE_COMPONENT / COUNT_CONDITIONALLY / TIGHTEN_CONSTRAINT / UNCHANGED`，每一项都有可观察机制、竞争解释、投资后果和翻转事实。尤其是，它的永久损失收紧来自已经观察到的应收、现金吸收和债务载体，不是来自 parent access 的 `UNKNOWN`。

Enhanced 同样不是“资料不足所以不判断”的防御稿，也正确识别了垃圾焚烧存量运营的强度、NCI/母公司上划边界以及新增资本不能共享核心运营信用。但它目前的两个材料代码和两个 outcome-cell 传播规则不符合自己获得的方法包：

1. `normal_earnings=UNCHANGED` 把 FY2023 全部 14.07 亿元扣非归母利润当作正常盈利锚，实际上把仅有一年恢复、主要受采购气价回落驱动的能源利润 1.57 亿元完整正常化；
2. `permanent_loss=MAINTAIN_CONSTRAINT` 用垃圾焚烧运营好、资产负债率小幅下降和利息保障倍数改善，抵消了集团层面已经观察到的持续应收累积、一次性回款后的负现金代理及净债务上升；
3. Enhanced 的经营 outcome cell 可在“能源重新亏损且集团扣非利润下降”时把全集团 `management_execution` 直接改成 `NEGATIVE_CREDIT`，没有要求管理层责任匹配的负面载体；
4. Enhanced 的现金/资产负债表 outcome cell 可把政府结算延长本身传播为全集团管理层负面信用。

这些不是文字多少、字段多少或自信语气差异，而会改变正常盈利、永久损失、管理层判断和估值方向。因此当前 pair 不能作为已通过的 pre-outcome 材料进入结算。

## 共同事实与经济机制复核

### 1. 固废和垃圾焚烧责任边界

共同年报支持以下边界：

- FY2021 固废处理净利润 7.17 亿元；FY2022 固废处理净利润 9.07 亿元，剔除工程与装备后净利润 8.13 亿元；FY2023 固废处理净利润 9.86 亿元，工程与装备净利润 0.73 亿元，所以“剔除工程与装备后的固废净利润约 9.13 亿元”算术和口径成立。
- FY2023 生活垃圾焚烧业务（不含工程与装备）收入 32.68 亿元、净利润 7.66 亿元，分别同比增长 15.57% 和 11%，毛利率 44.70%；产能利用率从 110% 升至 119%，垃圾焚烧量增长 20.85%。
- 吨垃圾发电量和上网电量分别下降 4.10% 和 3.02%，年报解释为供热拓展；与此同时，垃圾焚烧利润增速低于收入和处理量增速、毛利率由 47.7% 降至 44.7%，所以“核心运营已验证”与“新增项目单位经济仍须保留”可以同时成立。
- Baseline 的 9.13 亿元是“全部固废扣除工程与装备”口径，包含垃圾焚烧以外的餐厨、环卫、危废等运营；Enhanced 的 7.66 亿元是“生活垃圾焚烧”口径。两者没有算术冲突，但不能互称同一个指标。两臂 outcome cells 已分别写明各自口径，因此该差异本身不是 blocker；后续方法效用不得把不同责任范围的数值直接横比。

Baseline 没有因为工程收入下降就判断核心恶化，也没有把 9.13 亿元误称为 7.66 亿元的垃圾焚烧利润。Enhanced 则更明确地把正面执行信用限定在垃圾焚烧存量运营，这是冻结方法包的可观察行为之一。

### 2. 能源业务不能由单年修复直接正常化

FY2021、FY2022、FY2023 能源净利润依次约为 0.36 亿元、-0.65 亿元、1.57 亿元。FY2023 天然气销量仅增长 1.22%，能源毛利率从 1.45% 升至 9.76%；年报明确把改善主要归因于天然气采购气价回落、进销价差提高，并仍表示要继续与政府沟通“理顺天然气价格机制”。

集团扣非归母利润从 FY2022 的 11.07 亿元增至 FY2023 的 14.07 亿元，约增加 3.00 亿元；能源利润同比改善约 2.22 亿元，解释了其中大部分。以三年能源利润的简单均值约 0.43 亿元作粗略、非正式的中周期参照，FY2023 能源利润高出约 1.14 亿元，约占 FY2023 集团扣非归母利润的 8%。这不证明正确中周期值就是 0.43 亿元，但足以证明“完整 1.57 亿元均为正常盈利”需要额外的同责任边界桥。

因此 Baseline 的 `EXCLUDE_COMPONENT` 是强而非防御性的处理：它只排除 FY2023 能源利润高于保守中周期的部分，不排除固废核心，也没有把下一年未披露当恶化。Enhanced 的 `UNCHANGED` 则把公司对未来“正常盈利”的展望和单年采购成本回落，当成了完整正常化的经济证据；这不满足方法包的 `SAME_BOUNDARY_RECURRING_ECONOMICS_FIRST`。

### 3. 现金、应收和债务是已观察载体，不是披露缺口

- 应收账款加合同资产从 FY2021 的约 21.93 亿元，升至 FY2022 的约 38.74 亿元，再升至 FY2023 的约 48.87 亿元。年报将变化与可再生能源补贴未回收、政府结算延后、环卫和污水等业务确认联系起来；FY2023 信用减值损失约 1.03 亿元。
- 按两臂采用的债务口径，估算净有息债务从 FY2021 约 99.5 亿元升至 FY2022 约 130.8 亿元、FY2023 约 137.1 亿元。
- FY2023 剔除解释第 14 号分类影响后的经营现金流约 27.38 亿元，减公司披露约 23 亿元资本性支出，只剩约 4.38 亿元 `GROUP_CASH_PROXY`；其中又含 9.88 亿元债权转让回款和约 2 亿元污水处理费集中回收。仅为观察经常现金承载力而扣除这两项集中回款后，代理约为 -7.50 亿元。
- FY2021 剔除解释第 14 号影响后的经营现金流约 20 亿元，而资本性支出约 32 亿元；FY2022 报表经营现金流约 4.22 亿元而资本性支出约 32 亿元。资本开支已在 FY2023 降到约 23 亿元，且公司预计 FY2024 新增项目资本支出约 13.8 亿元，这支持风险可逆和“不升级为 thesis blocking”，但不能抹去截至 cutoff 已经发生的集团现金吸收和举债。
- FY2023 资产负债率从约 65.15% 降至 64.13%，利息保障倍数升至 4.36；这说明再融资风险尚未成为 thesis blocker。它们不能单独否定应收、现金和净债务的同向载体。

所以 Baseline 的 `TIGHTEN_CONSTRAINT` 有责任匹配的经济载体，parent access `UNKNOWN` 只被用于 `owner_cash=COUNT_CONDITIONALLY`，没有被误当作恶化。Enhanced 也没有把 parent access 未披露误判为 `DO_NOT_COUNT`，但其 `MAINTAIN_CONSTRAINT` 对已观察的集团载体处理过轻；局部核心运营好不能替集团现金和负债风险作证。

## Baseline 公平性与非防御性

Baseline 满足公平基线要求：

- receipt 显示只读取共同 forecaster packet 和 FY2021—FY2023 三份 PDF，`outcome_read=false`、`method_pack_received=false`；Enhanced 除同源材料外只多收到冻结方法包。
- 两臂 cutoff、公司、source budget、judgment-first contract 和 outcome seal 相同。两份 forecaster packet 的实质差异仅是 arm 身份、方法包输入及相应 instruction。
- Baseline 的正文反而比 Enhanced 更长，且它自行完成了经营/现金边界、局部未知、可逆/严重分支和 first-match 设计；不存在通过减少推理、制造空洞 UNKNOWN 或故意犯低级错误来衬托 Enhanced。
- Baseline 给固废运营有条件信用，承认资本开支下降、付款机制改善和 NCI 较小等反证；`TIGHTEN_CONSTRAINT` 明确停在非 thesis-blocking，故不是“只要有债就拒绝公司”。
- Baseline 的 rank-1 action 与 Enhanced 在经济上是同一个问题：集团现金代理、应收/资本开支/债务、NCI 和母公司上划。`CASH_CONVERSION_AND_PARENT_ACCESS` 与 `PARENT_OWNER_CASH_CONVERSION_BRIDGE` 的命名不同、decision-axis 字符串不同，不构成独立的方法效用。

Baseline outcome cell 的 favorable 盈利分支把整体管理层信用升到 `POSITIVE_CREDIT`，而现金桥仍未闭合，确有比 Enhanced 更宽的传播；但它同时要求集团扣非利润与剔除工程后的固废利润均增长至少 10%、持续费用不吞噬增量，且只在核心责任载体上归因。鉴于固废贡献约三分之二集团利润，这属于可以由结果检验的、偏积极但非稻草人的普通判断差异，不足以在 outcome 前替 Baseline 改写答案。

## 冻结方法包是否真正造成材料差异

可直接追溯到方法包的行为是：Enhanced 明确拆开垃圾焚烧运营、能源采购/定价、经营现金、融资和新增资本配置；保留已经验证的垃圾焚烧信用，又不把该信用传给危废、环卫、海外和新项目。这与 `SCOPED_MANAGEMENT_EXECUTION_BEFORE_ENTERPRISE_MERGE` 和 `CONVERSION_TRIAD_RETAIN_AND_NARROW` 一致。

但当前两个材料代码不能作为该方法行为的合法产物：

- `UNCHANGED` 不是“保留已验证核心”的必然结果，因为可以同时保留垃圾焚烧盈利、并排除未经同责任桥验证的燃气高点。Baseline 已经做到了这一点。
- `MAINTAIN_CONSTRAINT` 也不是“局部 MIXED 不升级成企业失败”的必然结果，因为本案已经有企业层面的现金、应收、债务载体。方法包明确允许在观察到向 owner cash 或 permanent loss 的传输时作企业更新。
- 两臂 rank-1 action 经济实质相同；不能按 action-family 字符串或 decision-axis 字段数量声称方法产生了材料差异。

所以冻结方法包确实改变了 Enhanced 的结构化推理方式，但 `UNCHANGED` / `MAINTAIN_CONSTRAINT` 目前更像对规则的错误应用，而不是可接受的方法增益。修复后即使两臂材料代码趋同，也必须接受“本 episode 没有产生材料方法效用”这一可能结果，不能为了保留差异而保留错误处理。

## Outcome cells 的 first-match 与可结算性

### 已通过的部分

- 两臂都把 `LOCAL_UNKNOWN` 和 `MEASUREMENT_MISMATCH` 设为无 axis update，并由共同 contract 要求在数值分类前先结算；未披露或不可比不会落入 adverse residual。
- 每个数值单元都有明确 favorable、adverse 和完整可比 residual。盈利单元的升/降阈值相反；现金单元的正/负阈值相反；因此主分支互斥。Baseline 的 severe balance-sheet 分支排在普通 worsens 分支之前，first-match 能处理两者的嵌套。
- 两臂的 residual 都是 `MIXED` 或 `NEUTRAL`，不是 adverse；整体上穷尽了完整可比输入。
- FY2024 官方年报原则上能用同一份审计财务报表结算集团扣非利润、经营现金、资本开支下限、应收、合同资产和债务；若业务叙述延续相同口径，还能结算固废/垃圾焚烧和能源经常利润。母公司上划若仍未披露，会停在 local unknown/conditional，不会被一臂错判 adverse。
- Baseline 9.13 亿元“固废剔除工程”与 Enhanced 7.66 亿元“垃圾焚烧”是不同但已明示的责任范围。同一 FY2024 年报可分别结算；结算者不得以一个指标替代另一个。

### 阻断问题

Enhanced 的 `ADVERSE_CORE_RECURRING_DETERIORATION` 把两条经济路径放在同一个 management update 中：

1. 垃圾焚烧利润下降并伴随利用率、单价、停运或成本载体；
2. 能源重新亏损且集团扣非经常利润下降至少 10%。

第一条可以责任匹配地更新管理层；第二条可能只是受监管终端价未及时覆盖外部采购成本。当前 first-match 虽然形式上互斥和穷尽，却会在第二条把 `management_execution` 直接改为 `NEGATIVE_CREDIT`，违反方法包的责任边界。

Enhanced 的 `ADVERSE_PERSISTENT_CASH_ABSORPTION` 也把“政府结算延长”列为足以触发全集团 `management_execution=NEGATIVE_CREDIT` 的载体。政府延付足以收紧 permanent loss、压低 valuation，不能在没有可控回款、资本配置或融资失误证据时自动归责管理层。

因此同一 FY2024 官方年报可以机械完成分类，但当前分类会产生责任不匹配的材料更新，尚不算公平可结算。

## Blocking returns

### Return 1 — Enhanced normal earnings 锚

- **Root cause:** `REASONING`
- **经济影响:** 将 FY2023 单年高价差能源利润完整资本化为正常盈利，可能把正常盈利和内在价值锚高估约一个材料但非整案级的能源高点；仅相对三年简单均值，差额约 1.14 亿元，约占 FY2023 扣非归母利润 8%。
- **缺失事实:** 在采购气价不再明显回落时仍可重复的进销价差和经常利润；正式可执行的顺价，或已实现的供应组合改善对利润的责任匹配桥。这里不是要求新增字段，而是承认现有三份年报没有闭合该事实。
- **禁止假设:** 公司预计“保持正常盈利”即等于 FY2023 的 1.57 亿元全部可持续；单年采购成本回落即等于管理层已建立可重复优势；垃圾焚烧运营好可以替能源正常化作证。
- **最小修复:** Enhanced 将 `normal_earnings` 改为 `EXCLUDE_COMPONENT`；保留 FY2023 固废/水务经常利润，排除能源利润高于保守中周期的部分，不制造精确中周期值。同步把 enterprise view、第二项 judgment、scenarios 和盈利 outcome cell 中“能源不低于 1.3 亿元即支持升级”的表述改为同口径采购价、终端售价、销量、经常利润和持续费用的桥。
- **验收反例:** 若 FY2024 天然气销量稳定、采购价不再下降而能源利润仍约 1.3—1.6 亿元，并有可执行顺价/供应结构证据，允许恢复该组件；若采购价再升、受监管售价未覆盖、能源再亏而垃圾焚烧稳定，只更新能源正常盈利/估值，不得据此把垃圾焚烧或全集团管理层改成负面。

### Return 2 — Enhanced permanent-loss 处理

- **Root cause:** `REASONING`
- **经济影响:** 对已经观察到的集团现金吸收、应收累积和净债务上升约束不足，可能放宽可接受估值/融资风险边界，并掩盖利润不能转成 owner cash 的永久损失载体。
- **缺失事实:** 常态而非债权转让的一般性政府回款机制、经常经营现金覆盖总资本开支、净债务开始下降。现有证据只证明资本开支有退坡可能和偿债尚可，不证明载体已经解除。
- **禁止假设:** 119% 垃圾焚烧利用率、64.13% 资产负债率或 4.36 倍利息保障可以跨责任边界抵消应收/合同资产、一次性回款后的负现金代理和债务上升；parent access 未披露本身也不得作为风险恶化证据。
- **最小修复:** Enhanced 将 `permanent_loss` 从 `MAINTAIN_CONSTRAINT` 改为 `TIGHTEN_CONSTRAINT`，仍明确“不达到 THESIS_BLOCKING”；保持 `owner_cash=COUNT_CONDITIONALLY` 和 `valuation_direction=UNCHANGED`。同步调整第三项 judgment 和 base/pessimistic scenario 的当前起点，不需新增 gate 或字段。
- **验收反例:** 即使核心垃圾焚烧继续增长，只要应收加合同资产继续材料增加、扣除集中回款后的集团现金代理为负且净债务上升，就维持/进一步收紧；只有常态回款、资本开支后的现金为正和债务不增或下降共同出现，才回到 `MAINTAIN` 或 `RELAX`。

### Return 3 — Enhanced outcome-cell 责任传播

- **Root cause:** `REASONING`
- **经济影响:** 同一 FY2024 事实可能被错误结算为企业管理层负面信用，污染 management、normal earnings、valuation 及后续方法效用判断；这是材料结论而非 schema 或措辞问题。
- **缺失事实:** 能源路径中管理层可控的采购/顺价执行失败；现金路径中可控回款、资本配置、建设支出或融资执行失败。外部气价、限价和政府支付延后只能证明经济风险，不能自动证明管理失职。
- **禁止假设:** 能源亏损等于集团运营管理失败；政府延付等于管理层现金执行失败；最弱局部轴可覆盖已验证的垃圾焚烧运营信用。
- **最小修复:** 在 Enhanced 现有 cells 内拆开责任路径，不加新 gate：能源外生亏损路径保留 `management_execution=CONDITIONAL_CREDIT`，但可按经常性和材料性更新 normal earnings/valuation；只有垃圾焚烧责任匹配恶化或明确可控的能源采购/定价执行失败才改 `NEGATIVE_CREDIT`。现金 adverse 路径对 permanent loss/valuation 保持更新，但只有观察到可控的资本配置、回款或融资执行载体才把 management 改为 `NEGATIVE_CREDIT`。
- **验收反例:** （a）能源因外部采购价上涨和限价转亏、集团扣非下降 10%，垃圾焚烧稳定——management 不得变为负面；（b）政府结算延长、现金代理低于 -5 亿元、应收增长 16%，但无可控管理失败——permanent loss 收紧、management 保留条件信用；（c）垃圾焚烧利润下降超过 10%并伴随非计划停运或可控成本上升——允许 management 负面。

## 最终验收条件

只需 Enhanced 完成上述三项局部修复，不改 Baseline、不增加字段、不增加新 gate，也不需要在 pre-outcome 阶段索取 FY2024。复核通过标准是：

1. 固废/垃圾焚烧正面判断被保留，能源高点不被完整正常化；
2. 已观察的集团现金/应收/债务载体得到 `TIGHTEN_CONSTRAINT`，但不夸大为 thesis blocking；
3. local unknown 和 parent access `UNKNOWN` 仍无 adverse update；
4. 能源外生冲击、政府延付、核心运营恶化三条责任路径不会落入同一个全集团 management update；
5. first-match 仍保持互斥、完整可比 residual 穷尽且非 adverse；
6. 后续只能用两臂 outcome cells 的材料处理变化评价方法，不能用篇幅、字段数、confidence tone 或 action-family 字符串差异评价方法。

---

## Final re-review（Enhanced 修复后）

### 最终结论

**ACCEPT。**

本次复审继续保持 outcome-blind，只读取 current pair 的 pre-outcome 材料、Enhanced receipt 与上文既定验收条件；没有读取 FY2024、结果、价格、回报或 settlement。Enhanced 已完成原 RETURN 的三项材料修复，validator valid 与本次实质复核结论一致，但 ACCEPT 不依赖 validator 本身。

### 原三项 RETURN 的闭环

1. **Normal earnings 已闭环。** Enhanced 当前为 `EXCLUDE_COMPONENT`：保留固废/水务经常利润，只排除 FY2023 能源利润高于保守中周期的未经验证部分；没有制造精确中周期值。favorable outcome 不再以“能源利润不低于 1.3 亿元”作机械门槛，而要求采购价不再明显下降、可执行顺价或已实现供应结构改善、稳定销量、持续费用后经常利润共同闭合。
2. **Permanent loss 已闭环。** Enhanced 当前为 `TIGHTEN_CONSTRAINT`，依据应收账款加合同资产连续上升、扣除集中回款后的负集团现金代理及净有息债务上升；同时用稳定市政需求、核心高利用率、64.13% 资产负债率和 4.36 倍利息保障把结论限制在非 `THESIS_BLOCKING`。这既没有用局部运营好转冲掉集团风险，也没有把 parent access `UNKNOWN` 当成恶化。
3. **责任传播已闭环。** Enhanced 已把垃圾焚烧/可控能源执行恶化、外生能源经济冲击、可控现金执行失败、外部政府延付与现金负担拆成互斥 first-match 路径。管理层负面信用只在责任匹配的可控载体出现时更新；外生载体仍可更新 normal earnings、permanent loss 或 valuation，但不擦除已经验证的核心运营信用。

### 三项验收反例机械重放

#### 反例 A：外生气价上涨、限价未覆盖，垃圾焚烧稳定

给定：能源因外部采购价上涨和受监管售价未及时覆盖而亏损；集团扣非经常利润同比下降至少 10%；垃圾焚烧没有责任匹配的材料恶化；没有可控采购组合、已具备条件的顺价执行或费用控制失败证据。

- 不满足 `ADVERSE_RESPONSIBILITY_MATCHED_EXECUTION_DETERIORATION`，因为该分支的能源路径明确要求可控失败证据。
- 首先命中 `ADVERSE_EXTERNAL_ENERGY_ECONOMICS`。
- 更新为：`management_execution=CONDITIONAL_CREDIT`、`normal_earnings=LOWER`、`valuation_direction=DOWN`。

**结果：通过。** 外生能源冲击改变能源正常盈利和内在价值，不把集团管理层错误改为负面。

#### 反例 B：政府延付、集团现金代理低于 -5 亿元、应收增长 16%

给定：政府结算延长；可比经营现金流减现金资本开支低于 -5 亿元；应收账款加合同资产增长 16%；没有可控回款管理失误、无回报资本开支/收购超支或可避免融资执行失败。

- 不满足 `ADVERSE_CONTROLLABLE_CASH_EXECUTION_FAILURE`，因为缺少可控失败证据。
- 首先命中 `ADVERSE_EXTERNAL_PAYMENT_AND_CASH_BURDEN`。
- 更新为：`management_execution=CONDITIONAL_CREDIT`、`permanent_loss=TIGHTEN_CONSTRAINT`、`valuation_direction=DOWN`。

**结果：通过。** 政府延付作为真实现金和永久损失载体被消费，但不被误写成管理层失职。

#### 反例 C：核心垃圾焚烧利润下降并伴随非计划停运或可控成本恶化

给定：同口径垃圾焚烧经常利润同比下降至少 10%，并伴随非计划停运或可控持续成本上升。

- 首先命中 `ADVERSE_RESPONSIBILITY_MATCHED_EXECUTION_DETERIORATION`。
- 更新为：`management_execution=NEGATIVE_CREDIT`、`normal_earnings=LOWER`、`valuation_direction=DOWN`。

**结果：通过。** 核心运营恶化沿同责任边界传播，且没有等待外生能源或 parent-cash 证据。

### Baseline 公平性复核

Baseline 仍是公平、强而非防御性的基线，原结论不变：同公司、同 cutoff、同三份官方年报和同一 judgment-first contract；receipt 显示未收到方法包、未读取 outcome。Baseline 没有用 `UNKNOWN` 拒绝公司，也没有把未披露的母公司上划当作永久损失恶化；其 `EXCLUDE_COMPONENT` 与 `TIGHTEN_CONSTRAINT` 均来自明确经济载体，同时保留固废核心、资本开支退坡、付款机制改善与偿债尚可等竞争事实。它独立完成了较完整的责任边界与 outcome cells，不是为了衬托 Enhanced 而人为削弱的 strawman。

### 修复后真正的材料差异

当前 material-treatment snapshot 已没有真实代码差异：两臂均为 `CONDITIONAL_CREDIT / EXCLUDE_COMPONENT / COUNT_CONDITIONALLY / TIGHTEN_CONSTRAINT / UNCHANGED`。两臂的 rank-1 action 经济上也相同，都是闭合集团现金代理、应收/资本开支/债务、NCI 和母公司上划；`CASH_CONVERSION_AND_PARENT_ACCESS` 与 `PARENT_OWNER_CASH_CONVERSION_BRIDGE` 的 action-family 名称、target 文字和 decision-axis 字符串差异 **不算材料差异**。

仍然存在、且可由同一 FY2024 官方年报公平结算的真实预承诺差异在 outcome treatment：

- Baseline 的盈利 favorable 分支以集团扣非利润和“全部固废剔除工程与装备”利润均增长至少 10%为主，并可把企业管理执行升至 `POSITIVE_CREDIT`；Enhanced 聚焦“垃圾焚烧”同责任边界的利润、毛利率、利用率及能源价差桥，即使 favorable 也把企业管理执行保留在 `CONDITIONAL_CREDIT`，避免核心运营替现金、融资和新增资本回报背书。
- Baseline 对外生能源亏损通常落入完整可比 residual，维持 `EXCLUDE_COMPONENT / UNCHANGED`；Enhanced 预设 `ADVERSE_EXTERNAL_ENERGY_ECONOMICS`，当外生能源亏损使集团扣非经常利润下降至少 10%时，降低 normal earnings 和 valuation，但保持管理层条件信用。
- Baseline 的资产负债表 worsens 分支要求应收加合同资产、净有息债务和负现金代理共同跨阈值；Enhanced 区分可控失败与外部支付载体，在负现金代理与应收或债务载体闭合时可以更早下调 valuation，同时只对可控失败负向归责管理层。

这些差异来自责任边界、经济桥和传播规则，而不是篇幅、字段数、confidence tone 或 action 命名。两臂的 `LOCAL_UNKNOWN` / `MEASUREMENT_MISMATCH` 仍为空更新，完整可比 residual 仍非 adverse；同一 FY2024 官方年报若缺少局部分项，会对相应 arm 局部冻结而非被解释为恶化。因此 current pair 已具备公平、可反驳、可结算的 pre-outcome 比较条件。
