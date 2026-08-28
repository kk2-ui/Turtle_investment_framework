# CN600549 厦门钨业 × 2024-05-01 独立结果前审阅

## 审阅结论

**RETURN**

结果访问授权：**NOT AUTHORIZED**。本次退回不授权读取 FY2024 年报、任何 post-cutoff 材料、价格、回报或旧派生报告。

本结论按 Product Materiality 作出。退回原因不是格式或非材料字段缺失，而是三处会改变 normal earnings、owner cash、permanent loss 或 valuation direction 的机械结算缺陷。根因分类均为 **REASONING**；现有 FY2021—FY2023 资料足以修复，不是 `DATA_COVERAGE` 或 `ACQUISITION_MODULE` 问题。

## 输入边界

本审阅的企业事实与规则依据限于：

- `FORECASTER_PACKET.json`；
- `FY2021.pdf`、`FY2022.pdf`、`FY2023.pdf`；
- `21_CN600549_PREOUTCOME_JUDGMENT.json`；
- 为判断上一轮行为变化而读取的 `19_CN601598_FEEDBACK_RECEIPT.json`。

未使用 FY2024 结果、post-cutoff 材料、价格、回报或旧派生报告。下文 FY2024 数字均为明确标注的**合成验收反例**，不是已观察结果。

## 已达到标准的部分

草案不是防御性拒绝。它给出了明确的整体企业判断和五个投资处理：钨钼深加工是当前最可信的利润引擎；电池材料与稀土保留规模和复苏期权但不能把规模当盈利质量；集团现金改善不等于母公司 owner cash；管理层仅获局部、有条件信用；normal earnings 与 valuation direction 小幅向上而 permanent-loss 约束不放松。四项 UNKNOWN 也都局部限制具体主张，没有把整家公司改写为 UNKNOWN。

授权年报支持大部分历史锚：FY2023 钨钼报告分部营业利润约 26.54 亿元、对外主营毛利率 28.73%，且年报明确披露钨钼利润剔除联营企业投资收益后同比增长 57.10%；电池材料与稀土 FY2023 报告分部营业利润分别约 5.60 亿元和 1.44 亿元，分部资本性支出分别约 14.16 亿元和 3.34 亿元；FY2023 合并 OCF 约 42.86 亿元、现金资本开支约 21.04 亿元，少数股东权益约 78.59 亿元。草案没有把这些不同口径混成一个事实。

上一轮 CN601598 的行为变化也**真实进入了结果前研究**：本稿新增同一钨钼报告分部的销量/收入—分部利润—资本负担桥，把管理层信用明确限制在钨钼边界，并在电池材料/稀土格保留 management execution，不再用规模增长直接授予公司级执行信用。但该规则只进入了研究叙述和 bridge 元数据，尚未完整进入可机械执行的 first-match 条件，这是下述第一项退回原因。

## 材料退回项 1：经常利润与责任边界没有真正进入所有触发条件

**根因分类：REASONING**

### 为什么低于标准

`normal_earnings_bridge` 列出了持续资本负担和非经常项目排除，但多个数值分支仍直接以原始“报告分部营业利润”触发投资轴更新：

- 钨钼格的 `FAVORABLE_FULL_EXECUTION_BRIDGE` 明确要求剔除联营投资收益和一次性项目；较弱的 `FAVORABLE_EARNINGS_BRIDGE_ONLY` 却只要求原始分部营业利润、毛利率和销量阈值，仍可直接给出 `normal_earnings=RAISE`、`valuation_direction=UP`。
- 电池材料/稀土格的 FAVORABLE、ADVERSE 和 NEUTRAL 分支都按两个报告分部原始营业利润之和及合计利润率结算，没有把其自己列出的资产减值、非持续补助、投资收益、折旧摊销、资本性支出和利用率要求写入触发条件。
- 电池材料与稀土是两个不同报告分部、不同定价和资本循环。可以在各自经常利润桥闭合后为集团 normal earnings 求和，但当前条件允许一个分部的改善抵销另一个分部的恶化，并把结果命名为 `FAVORABLE_DUAL_RECOVERY`，并未证明“双恢复”。

这不是理论上的口径洁癖。FY2023 年报一方面在报告分部表中单列资本性支出、折旧摊销和资产减值，另一方面又专门披露钨钼利润“剔除联营企业投资收益后”的增速，说明原始分部营业利润不能天然等同于已排除非经常项、已消费持续资本负担的经常利润。

### 经济影响

一次性投资收益、补助、处置或可逆减值可以使原始分部利润跨过阈值，从而错误上调或下调 normal earnings，并让 valuation direction 同步误传。电池与稀土合并后，资本效率恶化或其中一个板块的结构性下滑还可能被另一个板块的利润抵销，导致新增资本被按正常盈利资本化。该缺陷足以改变内在价值方向和永久损失判断的输入，不是表述问题。

### 缺失事实

- 钨钼、能源新材料、稀土三个报告分部分别可复算的 adjusted recurring operating profit；
- 各分部联营投资收益、处置、非持续补助、一次性停产/搬迁、资产减值等排除或保留依据；
- 各分部折旧摊销、资本性支出、利用率及持续费用负担如何进入阈值；
- 若要把钨钼管理层信用从 CONDITIONAL 升至 POSITIVE，至少一个核心深加工产品扣除持续费用后的单位经常利润。

### 禁止假设

- 禁止假设“报告分部营业利润 = 经常利润”。
- 禁止因为销量、毛利率和原始分部利润同向，就假设持续费用和资本负担已经被消费。
- 禁止假设电池材料与稀土合计利润改善等于两个责任边界均恢复。
- 禁止以 `normal_earnings_bridge` 中列出字段为由，假设 first-match 结算者会自行把未写入 condition 的调整补进去。

### 最小可执行修复

1. 将三个分部各自定义为可复算的 `adjusted_recurring_segment_profit`；每个数值分支必须明确使用该指标，而不是原始分部营业利润。
2. 把非经常排除和持续资本负担写入 condition。若所需调整无法从结果年年报闭合，进入局部 `LOCAL_UNKNOWN`，不得更新 normal earnings 或 valuation direction。
3. 电池材料与稀土无需一定拆成两个 outcome cell，但必须先分别完成经常利润与资本负担桥，再求和。若仍使用 “DUAL_RECOVERY”，必须要求两边各自的 adjusted recurring profit/利润率不恶化；否则改为准确的 aggregate/mixed 类，保留局部恶化。
4. 钨钼 `FAVORABLE_EARNINGS_BRIDGE_ONLY` 至少应与 full 分支共享“联营投资收益和一次性项目已剔除”的前提；产品单位利润未披露只限制 management credit 升级，不应放松 normal-earnings 口径。

### 验收反例

- **合成反例 A：**FY2024 钨钼原始分部营业利润 30.0 亿元、毛利率和销量满足 favorable 阈值，但其中 2.0 亿元来自联营投资收益或一次性处置，调整后经常利润仅 28.0 亿元。现有逻辑会命中 `FAVORABLE_EARNINGS_BRIDGE_ONLY` 并上调 normal earnings/valuation；修复后不得命中 favorable。
- **合成反例 B：**电池材料利润大幅上升、稀土利润降至接近零，合计利润和两组销量仍跨过当前 favorable 阈值，同时两分部资本性支出翻倍、利用率下降。现有逻辑可命中 `FAVORABLE_DUAL_RECOVERY`；修复后不得把它结算为“双恢复”，也不得在未消费资本负担时自动上调 valuation direction。

验收标准：上述两个反例均不能产生当前错误更新；完整可比且已调整的剩余补集只能落入 NEUTRAL/MIXED，缺少调整输入时只落入局部 UNKNOWN 且 `axis_updates={}`。

## 材料退回项 2：GROUP_CASH_PROXY 到 parent owner cash 的转换仍会跨轴误传

**根因分类：REASONING**

### 为什么低于标准

现金格正确声明 `cash_proxy_scope=GROUP`、`nci_scope=OPEN`、`parent_access=UNKNOWN`，但 favorable 条件只要求集团现金代理为正、两年累计不低于 20 亿元、NCI “范围关闭”和存在稳定分红/上划能力证据，便更新为 `COUNT_IN_PARENT_OWNER_CASH`。它没有要求复算出属于上市公司母公司股东、且实际可分配/可上划的现金金额。

FY2023 年报显示少数股东权益约 78.59 亿元，相对归母权益约 112.12 亿元并不轻微；厦钨新能、虹鹭、金鹭、金龙稀土均有材料 NCI。证明某子公司曾分红或具备上划能力，只能关闭“能否上划”的一部分，不能把包含 NCI 全额现金流的 GROUP_CASH_PROXY 直接转换成 parent owner cash。

### 经济影响

该分支可能把属于少数股东、留存在子公司、受融资/法定限制或仅有很小上划比例的现金算给母公司股东，夸大可分配 owner cash，进而低估永久损失约束并在后续估值中给出不应有的现金信用。

### 缺失事实

- 重要非全资子公司按归属比例调整后的 owner-cash 贡献；
- 实际分红/上划金额、稳定性、法定和融资限制；
- 母公司层现金收支及为维持集团经营必须回投的现金；
- 一个明确、可复算的 `parent_distributable_owner_cash` 金额，而不只是 access 状态。

### 禁止假设

- 禁止假设 NCI scope 标记为 CLOSED 就等于 parent owner cash 为正。
- 禁止假设存在分红或上划能力就等于 GROUP_CASH_PROXY 全额或大部分归母。
- 禁止用集团两年累计现金阈值替代母公司股东可支配现金阈值。

### 最小可执行修复

保留 GROUP_CASH_PROXY 作为集团信号，但将 `COUNT_IN_PARENT_OWNER_CASH` 的 favorable 条件改为：NCI 归属已量化、母公司 access 有证据、并复算出正的且材料的 `parent_distributable_owner_cash`；处理代码只能针对该归母金额，不能把集团代理整体改名。若只证明 access 而金额未闭合，继续 `COUNT_CONDITIONALLY`。

### 验收反例

**合成反例：**FY2024 GROUP_CASH_PROXY 为 +5 亿元、2023—2024 累计超过 20 亿元，重要子公司确有连续分红；但复算后母公司当年只获得 0.1 亿元可支配现金，其余现金属于 NCI、留存在子公司或需要回投。现有 favorable 条件可能升级为 `COUNT_IN_PARENT_OWNER_CASH`；修复后必须保持 `COUNT_CONDITIONALLY`，直到归母金额达到预设材料阈值。

验收标准：任何 owner-cash 升级必须展示集团代理、NCI 归属、上划和母公司可分配金额四步桥；缺一项不升级。

## 材料退回项 3：声明过的结构性上划阻断没有 severe 分支

**根因分类：REASONING**

### 为什么低于标准

packet 明确要求：材料且持续的结构性上划阻断同时是 permanent-loss 载体，必须预设 severe 分支。本稿 `permanent_loss_bridge.risk_carrier` 也写了“或重要子公司现金上划被明确阻断”，但所有 first-match 数值分支中没有这条路径：

- `ADVERSE_SEVERE_PERSISTENT_CASH_CARRIER` 只接受负 GROUP_CASH_PROXY、资本开支不降和债务增长三项同时满足；
- `NEUTRAL_POSITIVE_GROUP_PROXY_SCOPE_OPEN` 没有处理明确 `BLOCKED`；
- 正集团现金但 parent access 明确 BLOCKED 会落到 `MIXED_COMPLETE_RESIDUAL`，维持 `owner_cash=COUNT_CONDITIONALLY`、`permanent_loss=MAINTAIN_CONSTRAINT`；
- 负集团现金但不满足三项 severe、同时上划明确 BLOCKED，也只会更新 owner cash，永久损失仍维持。

因此 bridge 文本识别了风险载体，机械结算却保证它不能触发 permanent-loss 更新。

### 经济影响

核心经营子公司即使产生集团现金，若归母现金被材料且持续地阻断，上市公司母公司仍可能无法服务自身债务、分红或重新配置资本。当前 residual 会把这种已观察结构性载体误写成普通 scope open，直接低估永久损失风险；这是对投资结论有材料影响的漏判。

### 缺失事实

- 被阻断子公司对集团/归母现金贡献的材料性；
- 阻断的法律、融资、监管或少数股东机制；
- 持续期、解除条件和可逆性；
- 母公司自身流动性、债务和其他可替代现金来源。

### 禁止假设

- 禁止因为 GROUP_CASH_PROXY 为正或债务未增长，就假设结构性上划阻断不构成 permanent-loss 载体。
- 禁止把明确 `BLOCKED` 降级成 `UNKNOWN/OPEN`。
- 禁止把单次未分红当作结构性阻断；必须有已观察机制、材料性和持续/可逆性测试。

### 最小可执行修复

在集团现金数值分支之前增加一个明确、已观察的 `ADVERSE_STRUCTURAL_PARENT_ACCESS_BLOCK` first-match 分支，或把它作为与三项负现金载体并列的 severe 路径。要求同时满足：上划阻断有证据、影响归母现金材料、持续期/解除机制达到预设阈值。触发时至少 `owner_cash=DO_NOT_COUNT`、`permanent_loss=TIGHTEN_CONSTRAINT`；只有不可逆性和母公司偿债/存续影响进一步闭合时才可 `THESIS_BLOCKING`。资料未披露仍是局部 UNKNOWN，不能假装恶化。

### 验收反例

**合成反例：**FY2024 GROUP_CASH_PROXY 为正、债务下降，但贡献大部分现金的核心非全资子公司因明确融资契约在未来 18 个月不得分红或上划，且母公司自身现金不足以覆盖债务与必要支出。现有逻辑会进入 residual 并维持 permanent-loss 约束；修复后必须命中结构性阻断 severe 分支并收紧约束。

验收标准：明确 BLOCKED 与 UNKNOWN/OPEN 互斥；正集团现金不能覆盖材料、持续、已观察的归母上划阻断；单次少分红且无结构机制又不得触发 ADVERSE。

## first-match 完整性补充

三个 outcome cell 的 LOCAL_UNKNOWN 与 MEASUREMENT_MISMATCH 均位于数值分类之前且 `axis_updates` 为空，UNKNOWN/MISMATCH 的总体设计是局部的；完整可比剩余补集也都使用 MIXED，而不是把 ELSE 写成 ADVERSE。这部分方向正确。

但钨钼格仍不穷尽：`LOCAL_UNKNOWN` 只列分部收入、营业利润或毛利率缺失，后续所有有效数值分支又依赖硬质合金、切削工具和细钨丝销量。若结果年披露前三项但缺少一个必需销量，既不满足 LOCAL_UNKNOWN，也不能满足任何要求完整输入的数值/残余类。LOCAL_UNKNOWN 与 MEASUREMENT_MISMATCH 在“既缺字段又发生不可重述口径变化”时也可同时为真，只是依赖数组顺序 first-match，并非严格互斥。

这项不单独决定 RETURN，但必须随上述材料修复一并关闭，避免结果访问后由 custodian 临场补规则。最小修复是：LOCAL_UNKNOWN 覆盖每一个数值分支必需输入（含 adjusted recurring profit、销量及资本负担）；MEASUREMENT_MISMATCH 限于字段已披露但不可重述，或明确写出优先级排除条件。合成验收反例是“分部收入/利润/毛利率齐全但细钨丝销量未披露”：只能命中 LOCAL_UNKNOWN，`axis_updates={}`。

## 再提交验收条件

以下条件全部满足后方可 ACCEPT：

1. 三个业务边界的数值条件实际使用 adjusted recurring profit，并在 condition 中消费非经常排除及持续资本负担；电池与稀土先分边界桥接再汇总。
2. GROUP_CASH_PROXY 与 parent owner cash 之间存在可复算的 NCI 归属、上划和母公司可分配金额桥；仅 access 有证据不得升级。
3. 结构性 parent-access BLOCKED 有独立 severe 分支，并通过材料性、持续性和可逆性测试；UNKNOWN 仍保持局部且无轴更新。
4. 三格 first-match 对所有所需输入互斥穷尽；所有合成反例得到上述预期处理。
5. 保留当前明确、非防御性的 enterprise view、局部管理层信用和轴间 preserved 设计，不因修复结果格而把整家公司退回 UNKNOWN。

在这些条件关闭前，不授权写结果访问授权。

---

## 第二轮验收

### 第二轮结论

**RETURN**

本轮只复审修订后的 `21_CN600549_PREOUTCOME_JUDGMENT.json` 与本文件第一轮意见，未读取 FY2024 或任何其他结果材料。结果访问授权仍为 **NOT AUTHORIZED**。

四项原修复中，parent owner cash 四步桥与“5 亿元且不低于正 GROUP_CASH_PROXY 的 20%”材料阈值、结构性 parent-access block severe 分支、LOCAL_UNKNOWN 对必需销量/资本负担输入的覆盖，以及 UNKNOWN 与 MISMATCH 的区分都已真实进入 first-match。企业整体判断仍然明确，局部 UNKNOWN 没有撤回钨钼利润引擎、电池/稀土资本效率谨慎和集团现金边界判断。

但第二轮重放发现：adjusted recurring profit 的比较基线未冻结，企业层 flip/scenario 仍保留旧口径，且电池/稀土 adverse 的单边分支新增了跨责任边界误传。这三项都能改变 normal earnings、valuation direction 或 outcome settlement，故不能 ACCEPT。

### 五个 preoutcome 反例逐项重放

| case_id | 重放结果 | 当前 first-match 结果 |
|---|---|---|
| `TUNGSTEN_RAW_PROFIT_ONEOFF_DOES_NOT_UPGRADE` | **NOT DETERMINATE** | 原始 30 亿元不再直接触发 favorable，这一修复有效；但 `21` 没有冻结 FY2023 钨钼 adjusted recurring profit 基线，且输入只说“未增长 10%”，没有说明是否落在 ±5% neutral 区间。因此可能命中 `NEUTRAL_HOLD`，也可能命中 residual，不能机械证明 expected class。 |
| `BATTERY_UP_RARE_EARTH_DOWN_IS_NOT_DUAL_RECOVERY` | **PASS only if rare-earth profit remains positive** | 稀土“接近零但仍为正”且任一资本负担恶化时，favorable 和 neutral 均失败，进入 `MIXED_COMPLETE_RESIDUAL`。若“接近零”实际为轻微负值，则当前 adverse 的 OR 分支会命中并把集团 normal earnings/valuation 一并下调；反例没有冻结符号和数值。 |
| `POSITIVE_GROUP_PROXY_TINY_PARENT_CASH_STAYS_CONDITIONAL` | **PASS** | 0.1 亿元低于 5 亿元材料阈值，favorable 失败，进入 `NEUTRAL_POSITIVE_GROUP_PROXY_SCOPE_OPEN`；集团现金未被整体改名为 parent owner cash。 |
| `STRUCTURAL_PARENT_BLOCK_OVERRIDES_POSITIVE_GROUP_CASH` | **PASS** | 18 个月、至少 30% 贡献、母公司替代流动资源不足满足新增 severe 分支，先于正集团现金分支命中，得到 `DO_NOT_COUNT` 与 `TIGHTEN_CONSTRAINT`。 |
| `MISSING_ONE_CORE_VOLUME_IS_LOCAL_UNKNOWN` | **PASS** | 在不存在定义冲突时，缺细钨丝销量直接命中 `LOCAL_UNKNOWN`，`axis_updates={}`，不落入 MISMATCH 或数值方向。 |

机械 validator 的 `valid` 只能证明当前结构可解析；上述两个 `NOT DETERMINATE/conditional PASS` 表明它尚未证明阈值可复算或反例具有唯一 first-match。

## 第二轮材料退回项 1：缺少冻结的 FY2023 adjusted recurring 基线

**根因分类：DATA_COVERAGE、ACQUISITION_MODULE**

### 为什么低于标准

三个业务边界都改为比较 FY2024 与“可比 FY2023”的 adjusted recurring segment profit，但 `21` 只保留原始 FY2023 报告分部营业利润和钨钼“剔除联营投资收益后同比增长 57.10%”等锚，没有给出：

- `TUNGSTEN_FY2023_ADJUSTED_RECURRING_SEGMENT_PROFIT`；
- `BATTERY_FY2023_ADJUSTED_RECURRING_SEGMENT_PROFIT`；
- `RARE_EARTH_FY2023_ADJUSTED_RECURRING_SEGMENT_PROFIT`；
- 两个非钨钼分部的 FY2023 adjusted recurring margin，以及计算资本负担状态所需的冻结分母/比率。

因此 “+10%”“-15%”“±5%”“合计 +25%”等阈值没有可复算分母。公式虽然写入 cell，但哪些 FY2023 补助、投资收益、处置或负损失被排除仍可能在看到结果后才判断。当前 validator 对相对阈值没有要求冻结 denominator，故结构 `valid` 仍放过了实质数据缺口。

### 经济影响

结算者只能在三种错误选择中选一：用原始 FY2023 分部利润冒充 adjusted baseline；在结果解封后回头裁量 FY2023 调整项；或把大量结果退入 UNKNOWN。前两种可直接翻转 favorable/adverse 和 normal earnings/valuation，后一种会让本次修复退化为防御性拒绝。

### 缺失事实

三个分部 FY2023 adjusted recurring profit 的逐项调整表、adjusted margin、资本开支和折旧摊销相对 adjusted profit 的冻结基线；无法归属的调整项应明确为哪个局部 UNKNOWN，而不是留给结果后裁量。

### 禁止假设

- 禁止把 FY2023 原始报告分部营业利润视为 adjusted recurring profit。
- 禁止因定义公式已存在就假设 denominator 已冻结。
- 禁止在结果解封后利用 FY2024 叙事反向决定 FY2023 哪些项目“持续”或“一次性”。
- 禁止假设“adjusted profit 未增长 10%”必然进入 residual；它仍可能位于 ±5% neutral 区间。

### 最小可执行修复

先改 reusable acquisition/schema/validator：为每一个相对 adjusted-profit 或 adjusted-margin 阈值强制要求 `baseline_value`、逐项 adjustment schedule、scope 和 source reference；若 baseline 无法从 pre-cutoff 资料闭合，validator 必须拒绝该相对阈值，改用明确局部 UNKNOWN 或不依赖缺失分母的保守分支。完成这一步并取得 FY2023 证据后，再回填 `21`，不能只改文案。

### 验收反例与标准

将钨钼反例补成完整数值：冻结 FY2023 adjusted baseline、FY2024 adjusted value、毛利率、三项销量和资本负担状态。它必须唯一命中一个 class。对电池和稀土分别做相同复算；validator 对删除任一 baseline/adjustment 字段的 mutation 必须失败。

## 第二轮材料退回项 2：flip facts 与 scenario 仍使用修复前口径

**根因分类：REASONING、WRITING**

### 为什么低于标准

outcome cell 已改用 adjusted recurring profit、分边界资本负担和 parent-distributable owner cash，但企业层的 flip facts 与 scenario discriminating facts 仍写：

- 钨钼原始“分部营业利润增长/下降”阈值；
- 电池材料与稀土原始合计分部营业利润与合计利润率阈值；
- 正 GROUP_CASH_PROXY 加“可观察分红/上划证据”即可支持 optimistic owner-cash 路径。

这不是无害的文字滞后。相同的结果可在 cell 中因一次性收益或资本负担进入 MIXED，却在 optimistic scenario 中被视为 favorable；也可因 parent cash 仅有很小分红而在 cell 中保持 conditional，却被 enterprise scenario 读成 owner cash 升级。

### 经济影响

后续 investor readout 可选择较宽松的企业层 flip/scenario 覆盖较严格的机械结算，从而重新产生 normal earnings、valuation 和 parent owner cash 跨轴误传，并破坏盲测冻结的一致性。

### 缺失事实

无新增外部事实缺口；缺的是 `21` 内同一判断在 judgment、scenario 与 outcome cell 三处使用同一冻结经济口径。

### 禁止假设

- 禁止把 raw segment profit flip fact 解释成 adjusted recurring profit。
- 禁止把“存在分红”解释成四步 parent-cash 桥已闭合或达到 5 亿元/20% 阈值。
- 禁止认为 outcome cell 会自动覆盖上层 scenario；两者都是要求交付的企业判断。

### 最小可执行修复

不撤回 enterprise view，只同步改写三个 judgment 的 flip facts 和三套 scenario discriminating facts：利润路径使用冻结后的 adjusted recurring metric 与资本负担状态；owner-cash optimistic 路径明确要求四步桥和材料阈值；结构性 block 纳入 pessimistic 路径。management credit、normal earnings、owner cash 和 permanent-loss 的当前 treatment 保持不变。

### 验收反例与标准

- 原始钨钼利润因 2 亿元一次性收益跨过 +10%，但 adjusted profit 未跨阈值：cell、flip fact 和 scenario 必须一致地不判 favorable。
- GROUP_CASH_PROXY 为正且曾分红，但 parent-distributable cash 仅 0.1 亿元：cell 与 optimistic scenario 均必须保持 owner cash conditional。

## 第二轮材料退回项 3：单一分部转负可错误下调合计 normal earnings

**根因分类：REASONING**

### 为什么低于标准

电池/稀土 `ADVERSE_CONTINUED_COMPRESSION` 有两条 OR 路径：合计 adjusted profit/利润率材料下降，**或**任一分部 adjusted profit 转负且该分部资本负担恶化。第二条一旦成立，统一写入 `normal_earnings=LOWER`、`valuation_direction=DOWN`，没有检查另一分部是否以更大、已调整且资本负担良好的利润改善完成经济抵销。

这把“一个责任边界的真实恶化”错误传播成“两个分部合计正常盈利下降”。分边界桥已经计算，却在 axis update 时又被合回去了。

### 经济影响

若电池材料 adjusted profit 大幅改善而稀土轻微转负，合计正常盈利可以显著上升；当前 first-match 仍会因稀土单边条件先命中 ADVERSE，机械下调集团 normal earnings 和 valuation。方向可被直接翻转。

### 缺失事实

并非数据缺失；需要在 class 中同时消费两个分部的 adjusted profit 变化、资本负担和合计经济方向。

### 禁止假设

- 禁止假设任一小分部转负必然使合计 normal earnings 下降。
- 禁止用另一个分部的改善否认该局部恶化；应保留为 MIXED/local adverse，而不是把任一方向抹掉。
- 禁止从单边分部资本效率恶化直接传播到 permanent loss；该轴仍应由已冻结的 severe carrier 结算。

### 最小可执行修复

保留“合计 adjusted profit 下降至少 25%且 margin 下降”的 ADVERSE→LOWER/DOWN 路径。将“任一分部转负且资本负担恶化”拆成独立 local-adverse/MIXED 分支：只有合计 normal earnings 同时恶化时才 LOWER；若另一分部完成材料抵销，保留局部风险并根据合计 adjusted direction 给出 UNCHANGED/MIXED，不得自动 DOWN。

### 验收反例与标准

新增精确反例：电池材料 FY2024 adjusted recurring profit 较冻结基线上升 100%、资本负担 NOT_DETERIORATED；稀土为小额负值且资本负担 DETERIORATED；两者合计 adjusted profit 明显高于 FY2023。现有逻辑命中 ADVERSE；修复后必须进入明确的 MIXED/local-adverse 分支，不能把合计 normal earnings 更新为 LOWER。

## 第二轮再提交验收条件

1. acquisition/schema/validator 强制冻结三个 FY2023 adjusted recurring profit 基线、调整表、margin 与资本负担分母；mutation 缺一项即 invalid。
2. judgment flip facts、scenario discriminating facts 与 outcome cell 使用同一 adjusted-profit、资本负担和 parent-cash 口径。
3. 电池/稀土单边转负分支不再无条件下调合计 normal earnings/valuation，并通过新增精确反例。
4. 五个既有反例补齐足以产生唯一 first-match 的数值和符号；逐个重放均与 expected class 一致。
5. 保持当前 enterprise view 和各 treatment，不因 baseline 或局部项未闭合把整家公司退回 UNKNOWN。

上述条件关闭前，第二轮最终结论仍为 **RETURN**，不授权创建 outcome access authorization。

---

## 第三轮验收

### 第三轮结论

**RETURN**

本轮只复审当前 `21_CN600549_PREOUTCOME_JUDGMENT.json`、本文件、`scripts/historical_judgment_first_draft.py` 和 `tests/test_historical_judgment_first_draft.py`。未读取 FY2024 或其他结果材料。结果访问授权仍为 **NOT AUTHORIZED**。

当前 `21` 已把三个 FY2023 baseline schedule、adjusted margin、资本负担分母、flip facts、三情景、四步 parent cash 和单边分部 offset 分支写入同一口径。`.venv/bin/pytest -q tests/test_historical_judgment_first_draft.py` 实际返回 **20 passed**，当前 `21` 也通过 validator。五个 preoutcome 反例按已给数值均能命中预期 class。

但 reusable validator 没有强制多分部 cell 的完整 scope 集合；同时钨钼 adjusted baseline 将集团权益法收益全额扣入钨钼分部，却没有冻结同责任边界的归属证据。前者直接违反第二轮要求的“删除任一 baseline 即 invalid”，后者仍允许集团汇总跨边界替代分部经常利润。这两项都可能改变 favorable/adverse 阈值，故不能 ACCEPT。

### 五个反例机械重放

| case_id | 复算 | first-match |
|---|---|---|
| `TUNGSTEN_RAW_PROFIT_ONEOFF_DOES_NOT_UPGRADE` | `28 / 26.038989 - 1 = +7.531%`，高于 neutral `+5%`、低于 favorable `+10%`；其他输入完整，资本负担未恶化。 | `MIXED_COMPLETE_RESIDUAL`，PASS。 |
| `BATTERY_UP_RARE_EARTH_DOWN_IS_NOT_DUAL_RECOVERY` | 电池 `+100%`，稀土 `-0.10亿元` 且资本负担恶化；合计约 `11.107636亿元`，较冻结合计 `7.047329亿元` 增长约 `57.6%`，不是 aggregate adverse。 | `MIXED_LOCAL_SEGMENT_ADVERSE_OFFSET`，PASS；不更新合计 normal earnings/valuation。 |
| `POSITIVE_GROUP_PROXY_TINY_PARENT_CASH_STAYS_CONDITIONAL` | 归母可分配现金 `0.1亿元` 同时低于 `5亿元` 和正集团代理的 `20%`。 | `NEUTRAL_POSITIVE_GROUP_PROXY_SCOPE_OPEN`，PASS。 |
| `STRUCTURAL_PARENT_BLOCK_OVERRIDES_POSITIVE_GROUP_CASH` | 阻断 `18个月`、贡献至少 `30%`、母公司 12 个月替代流动资源不足。 | `ADVERSE_STRUCTURAL_PARENT_ACCESS_BLOCK`，PASS，先于正集团现金分支。 |
| `MISSING_ONE_CORE_VOLUME_IS_LOCAL_UNKNOWN` | 细钨丝销量缺失、无定义冲突。 | `LOCAL_UNKNOWN`，PASS，`axis_updates={}`。 |

第二个反例的 `input` 文本写“合计 10.64 亿元”，但给定两数 `11.207636 - 0.10` 的正确合计为 **11.107636 亿元**。这不改变 expected class，按 Product Materiality 不单独阻断；为保证所谓“机械重放”名实相符，仍应更正。

## 第三轮材料退回项 1：validator 未强制多分部 baseline scope 完整

**根因分类：ACQUISITION_MODULE**

### 为什么低于标准

`_validate_adjusted_profit_baselines` 只要求 `baseline_adjusted_profit_schedules` 是非空列表，并检查现存 schedule 的字段、算术和 `scope_id` 不重复；它不知道一个 cell 预期有哪些 scope。因此，针对当前 `21` 做内存 mutation，删除电池/稀土 cell 的 `SEGMENT:RARE_EARTH` 整份 schedule 后，`validate_preoutcome_draft` 仍返回 `[]`。

现有两个新增测试覆盖“完全没有 schedules”、删除 `source_refs` 和篡改 adjusted profit 算术，却没有覆盖“多 scope cell 少一整份 schedule”。所以 **20 passed** 与当前 gate 的完整性主张并不等价。

### 经济影响

后续任何双分部 relative-threshold 草案都可只冻结一个分部 baseline 而通过 validator。结果 custodian 随后只能用原始利润、结果后裁量或 UNKNOWN 补另一个分部，足以翻转 aggregate favorable/adverse、normal earnings 和 valuation direction。

### 缺失事实

缺少机器可读的每个 cell 所需 baseline scope 集合及其精确匹配关系。例如本 cell 必须声明并验证：

- `SEGMENT:BATTERY_MATERIALS`；
- `SEGMENT:RARE_EARTH`。

### 禁止假设

- 禁止因为当前 `21` 恰好有两份 schedule，就声称 validator 已强制两份。
- 禁止把“列表非空、scope_id 不重复”当作“所需 scope 齐全”。
- 禁止用现有 20 tests 代替未执行的整份 schedule deletion mutation。

### 最小可执行修复

在 opt-in bridge 中增加如 `required_baseline_scope_ids` 的冻结字段；validator 要求实际 schedule scope 集合与 required 集合**完全相等**，拒绝缺失、额外或重复 scope。为单 scope 与双 scope 分别增加测试，并直接对当前双分部 fixture 删除任一 schedule，期望 specific finding。

### 验收反例与标准

对当前 `21` 的内存副本依次删除 `SEGMENT:BATTERY_MATERIALS`、`SEGMENT:RARE_EARTH` 或钨钼 schedule：三个 mutation 均必须 invalid；未修改的 `21` 必须 valid；既有非 opt-in 案例仍须通过。

## 第三轮材料退回项 2：钨钼 adjusted baseline 仍使用集团汇总替代分部归属

**根因分类：DATA_COVERAGE、REASONING**

### 为什么低于标准

钨钼 schedule 从报告分部营业利润 `2,654,306,141.57` 元中扣除 `50,407,227.86` 元“权益法核算联营企业投资收益”，得到 adjusted baseline `2,603,898,913.71` 元。其 rationale 明写“按同年**合并权益法投资收益金额**保守剔除”。当前 schedule 虽引用 FY2023 p.15 与 p.286，却没有列出联营企业、说明该 5,040.72 万元是否全部属于钨钼责任边界、也没有证明该合并金额已全部包含在钨钼报告分部营业利润中。

“年报描述钨钼利润剔除联营收益后增长”能证明该类调整方向真实，不能自动证明合并权益法收益的绝对金额应 100% 从钨钼报告分部扣除。当前做法仍是用集团汇总财务替代同责任边界已观察经济。

### 经济影响

该扣除约占原始钨钼分部利润 `1.9%`，把 favorable `+10%` 门槛从约 `29.197亿元` 降至约 `28.643亿元`，差约 `0.554亿元`；adverse 门槛也随之移动。处于这段区间的 FY2024 adjusted profit 可因未经证明的集团归属假设改变 first-match，并直接更新 management credit、normal earnings 与 valuation direction。

### 缺失事实

- FY2023 权益法收益按联营企业列示的金额；
- 每家联营企业所属责任边界；
- 该收益是否、以及以多少金额进入钨钼报告分部营业利润；
- 与 FY2024 使用同一定义的可复算 allocation schedule。

### 禁止假设

- 禁止假设集团权益法收益全部属于钨钼。
- 禁止假设“保守多扣”不会改变方向性 class。
- 禁止以同比增长 57.10% 推导未披露的绝对分部调整额。
- 禁止仅因 source ref 非空就认为责任边界已闭合。

### 最小可执行修复

先从 cutoff 前证据取得联营企业逐项金额与分部归属，写入 allocation schedule，并证明扣除额包含于钨钼报告分部利润；validator/schema 至少要求跨报表层级调整有 `allocation_scope`、`included_in_reported_profit` 和 source reference。若无法闭合，不得全额使用集团数字：冻结一个明确标注边界限制的 raw segment proxy，或把该相对 adjusted 阈值局部设为不可复算；不能在结果后补归属。

### 验收反例与标准

合成反例：5,040.72 万元集团权益法收益中只有 1,000 万元属于并计入钨钼分部，其余属于其他责任边界。修复后的 baseline 只能扣 1,000 万元；在“当前 +10% 门槛”和“正确 +10% 门槛”之间的结果不得继续按当前 schedule 命中 favorable。验收必须展示逐项归属，而不是再次引用集团合计。

## 第三轮非阻断修正

- 将电池/稀土反例合计由 `10.64亿元` 更正为 `11.107636亿元`。
- `GROUP_CASH_PROXY_AND_SEVERE_CARRIER.direct_axis_links.permanent_loss` 仍只描述负现金 severe 路径，建议同步加入已实际存在的结构性上划阻断路径；first-match 已正确处理，故不单独阻断。

## 第三轮再提交验收条件

1. validator 对 required baseline scope 做精确集合验证，删除任一整份 schedule 的 mutation 均失败。
2. 钨钼权益法收益调整取得同责任边界逐项归属与“已进入 reported segment profit”证据；无法取得则撤销集团合计替代。
3. 修正电池/稀土反例算术文字，并保留五个反例当前正确 first-match。
4. 当前 `21` valid、targeted tests 通过，且新增 scope-deletion tests 真正覆盖上述 gate；非 opt-in 案例不受影响。
5. 保持当前 enterprise view 与六轴 treatment，不因修复局部 baseline 撤回整体企业判断。

上述条件关闭前，第三轮最终结论仍为 **RETURN**，不授权创建 outcome access authorization。

---

## 第四轮最终验收

### 最终结论

**ACCEPT**

本轮只复审当前 `21_CN600549_PREOUTCOME_JUDGMENT.json`、本文件以及本次 validator/tests；未读取 FY2024 或其他结果材料。第三轮两项材料阻断均已关闭，没有发现新的材料性跨轴传播、first-match 不穷尽或企业判断撤回问题。

### 第三轮阻断关闭证据

1. `required_adjusted_profit_scope_ids` 已成为 opt-in bridge 的必需精确集合。钨钼 cell 要求一个 scope；电池/稀土 cell 要求两个 scope。validator 比较 required 与实际 schedule scope 集合，拒绝缺失、额外或重复 scope。
2. 当前 `21` 通过 validator，`findings=[]`；`.venv/bin/pytest -q tests/test_historical_judgment_first_draft.py` 实际结果为 **21 passed**。
3. 对当前 `21` 内存 mutation 删除 `SEGMENT:RARE_EARTH` 整份 schedule，validator 返回 `baseline_adjusted_profit_scopes_incomplete`，关闭了“列表非空但 scope 不完整”漏洞。
4. 钨钼 FY2023 baseline 改为报告分部利润 `26.543061亿元`。集团权益法收益因无分部归属证据采用 `amount_removed=0`、`UNALLOCATED_GROUP_ITEM_NOT_REMOVED`；只有有证据证明已进入并归属于钨钼分部的项目才允许调整，集团无归属项目不得结果后分配。flip facts、scenario、management bridge 与 counterexample 已同步该定义。
5. 电池/稀土反例合计已更正为 `11.107636亿元`。

### 五个反例最终重放

| case_id | 唯一 first-match | 验收 |
|---|---|---|
| `TUNGSTEN_RAW_PROFIT_ONEOFF_DOES_NOT_UPGRADE` | `28 / 26.543061 - 1 ≈ +5.49%`，高于 neutral `+5%`、低于 favorable `+10%`，进入 `MIXED_COMPLETE_RESIDUAL`。 | PASS |
| `BATTERY_UP_RARE_EARTH_DOWN_IS_NOT_DUAL_RECOVERY` | 稀土转负且资本负担恶化，但电池改善使合计利润显著上升，进入 `MIXED_LOCAL_SEGMENT_ADVERSE_OFFSET`。 | PASS |
| `POSITIVE_GROUP_PROXY_TINY_PARENT_CASH_STAYS_CONDITIONAL` | `0.1亿元` 未达到 `5亿元`/正集团代理 `20%` 双材料阈值，进入 `NEUTRAL_POSITIVE_GROUP_PROXY_SCOPE_OPEN`。 | PASS |
| `STRUCTURAL_PARENT_BLOCK_OVERRIDES_POSITIVE_GROUP_CASH` | 18 个月明确阻断、至少 30% 贡献、母公司替代流动资源不足，进入 `ADVERSE_STRUCTURAL_PARENT_ACCESS_BLOCK`。 | PASS |
| `MISSING_ONE_CORE_VOLUME_IS_LOCAL_UNKNOWN` | 缺细钨丝销量且无定义冲突，进入 `LOCAL_UNKNOWN`，`axis_updates={}`。 | PASS |

### Product Materiality 结论

- 企业判断仍明确且非防御性：钨钼历史改善、管理层局部有条件信用、电池/稀土资本效率谨慎、集团现金与 parent owner cash 分离、永久损失维持约束均未被局部 UNKNOWN 撤回。
- 三个业务责任边界先分别形成 segment-attributed adjusted recurring profit 与资本负担判断，再进行允许的合计结算；单边稀土恶化不再自动传播为合计 normal earnings/valuation 下调。
- GROUP_CASH_PROXY、parent-distributable owner cash 与结构性上划阻断分别结算；四步桥、材料阈值和 severe 分支没有互相覆盖。
- LOCAL_UNKNOWN/MISMATCH 局部且无 axis updates，完整可比剩余补集为 NEUTRAL/MIXED；五个反例均给出唯一预期 class。
- validator 的 opt-in 设计不影响既有非 relative-threshold 案例，同时已对本案所需的 baseline、逐项调整、margin、资本负担字段、source refs、算术对账和 scope 完整性形成真实失败门。

### 授权边界

本 **ACCEPT 仅授权创建本 episode 的 outcome access authorization**。

它不直接授权读取 FY2024、post-cutoff 材料、价格、回报或其他 outcome，也不授权结算、投资处理更新、方法学习声明、提交或其他文件修改。后续访问必须由独立创建的 outcome access authorization 明确授予并受其范围约束。
