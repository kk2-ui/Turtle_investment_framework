# 独立工程审阅：现金可达、组件桥与 2×2 训练边界

**结论：RETURN。** 现金模型自身将可采用金额收敛至证据下限、价值桥会确定性重算输出、fresh task 的派生范围也总体保持狭窄；但以下三项缺口仍可实质改变可进入估值的现金、条件性盈利/价值路线的可信度，或使 2×2 盲审失效。因此不能以当前实现作为该验收目标的完成证据。

## 范围与方法

本审阅只读取以下实现、schema 及其对应测试：

- `schemas/cash_accessibility_model.schema.json`
- `schemas/enterprise_underwriting_episode_v1.schema.json`
- `schemas/valuation_value_bridges.schema.json`
- `scripts/cash_accessibility_model.py`
- `scripts/enterprise_underwriting_episode.py`
- `scripts/enterprise_underwriting_training.py`
- `scripts/valuation_value_bridges.py`
- `scripts/cutoff_official_fact_register.py`
- 对应测试，以及 `scripts/anonymous_preoutcome_review_packet.py` 和 `tests/test_anonymous_preoutcome_review_packet.py`（后者直接覆盖该传输边界）。

未读取 campaign V4 的 outcome、observation 或 review，也未读取 FY2018+ 的源材料。

以下目标已得到正向实现证据，但不足以抵消 RETURN 项：

- 现金模型仅把加总叶子现金作为 legal adopted value；诊断合并数只进入条件上限。存量现金、未来留存与关联方应收均以已证下限作为 `adopted_value`，并将未认可余量分开（`scripts/cash_accessibility_model.py:793-813`、`904-969`、`980-1056`、`1124-1253`）。
- 价值桥从 canonical input 重算现金模型，按 `adopted_value` 投影每股数字；输出验证会重算所有结果、数值 claim 和 reader slot，不能靠手工覆盖升级（`scripts/valuation_value_bridges.py:362-673`、`1235-1299`）。
- component decision summary 与 economic derivation summary 均由账本确定性派生；fresh materialization 只派生这两个 summary、把显式 UNKNOWN delta 同步为 UNKNOWN transmission，并补登记被动 excluded route。主动/排除路线冲突仍由验证器拒绝（`scripts/enterprise_underwriting_training.py:734-834`；`scripts/enterprise_underwriting_episode.py:741-898`）。
- 新执行要求 v2 合约；v1 仅允许与显式登记的冻结合约逐字相同的 replay，不能 render 新 task 或 run（`scripts/enterprise_underwriting_training.py:241-265`、`855-889`）。

## 阻断项

### 1. 现金的“VERIFIED”事实不是可审计的 cutoff 事实，任意金额可被标记后进入 adopted value

**根因分类：ACQUISITION_MODULE、DATA_COVERAGE。**

`cash_accessibility_model` 所有金额行只要求 `source_fact_ids` 出现在调用者给出的 `verified_facts=[{fact_id,status:"VERIFIED"}]` 中（`scripts/cash_accessibility_model.py:249-266`、`338-376`）。该载体没有 source、页码、可得时间、责任边界、单位或已验证数值；所以输入方可以自造一个 `VERIFIED` ID 并给现金、历史分配或应收回收行填任意金额，模型仍会把算出的下限写进 `adopted_value`。

`cutoff_official_fact_register` 虽然能独立校验静态 PDF URL、pre-cutoff 可得时间和页码（`scripts/cutoff_official_fact_register.py:118-217`），但它没有可被现金模型引用的 `fact_id`/数值绑定接口；两模块之间没有验证路径。`valuation_value_bridges` 的可选 `canonical_fact_bindings` 仅出现在 schema，输入验证和编译都不消费它（`schemas/valuation_value_bridges.schema.json:89-106`；`scripts/valuation_value_bridges.py:166-339`）。当前“事实已验证”的结论因此只是调用者声明，而非可复现的证据门槛。

**经济影响。** 已证下限是存量超额现金和关联方应收的可加 equity bridge 输入；未经 cutoff、责任边界和原始观测约束的虚高数值会直接抬高普通股价值。即使区间选择 low endpoint，也不能修复 low 本身没有被证据证明的问题。

**缺失事实。** 每个被采用金额或比例缺少到 cutoff-safe official observation 的可解析绑定：source id、页码/定位、可得时间、数值、单位、责任边界和所消费输入路径。

**禁止假设。** 不得把调用者自填 `status="VERIFIED"` 或未消费的 `canonical_fact_bindings` 当成金额、资金来源、连续性条件或回收率已获证据支持。

**可执行修复。** 先完善可复用 acquisition/validation 接口，再让现金和价值桥消费它：

1. 将 fact register 扩展为带稳定 `fact_id` 的 canonical observation（包含 source/page、available_at、数值或公式输入、unit、responsibility boundary）。
2. 让现金输入的每个 `source_fact_ids` 解析至该 register；对金额、期间、币种/单位、资金来源和适用性布尔判断分别验证输入路径与 observation 的一致性。移除未使用的 `canonical_fact_bindings`，或把它改为这一强制的路径到 `fact_id` 绑定并实际验证。
3. 只有上述校验通过的 cash model 才可传入 valuation bridge；bridge 不应重新接受无来源的“verified”标签。

**验收标准。** 新增回归覆盖：伪造 `VERIFIED` ID、缺 register observation、post-cutoff source、页码/单位/责任边界不匹配、以及 observation 数值与消费现金输入不一致时，cash compile 和 value bridge 均必须失败；完整 pre-cutoff official register 的合法输入仍应生成相同的 adopted low endpoint 和确定性 bridge 输出。

### 2. 有界 driver sensitivity 的金额 delta 没有证据绑定，可凭 prose 与组件权限写入读者/估值请求

**根因分类：REASONING、MODEL。**

normal-earnings bridge 的每一行要求 `evidence_ids`，但 sensitivity 的 `delta` shape 只有 status、范围和 unit（`schemas/enterprise_underwriting_episode_v1.schema.json:617-649`）。实现仅校验它有限、带符号、包含零，及 DIRECT 是否拥有 base/conditional component authority（`scripts/enterprise_underwriting_episode.py:934-966`、`1207-1231`）；没有要求任何 evidence id 支撑“driver 变化会带来 -X 到 +Y earnings/owner-cash”的幅度。`input_cases` 的 evidence 只支持 driver case，本身不能证明 transmission delta（`901-931`）。

随后该 delta 会进入 compiler-owned summary 和 reader brief，并绑定到 valuation route（`scripts/enterprise_underwriting_episode.py:498-573`、`1916-2021`）。因此，只要组件已有 base/conditional 权限，任意正向 `range_high` 都可作为一个看似可承保的敏感性呈现，而无须证明单位利润、销量、经营杠杆、维护资本或普通股现金转换。

**经济影响。** 未经证实的正向 delta 可抬高对正常盈利、owner cash 或相连价值路线的条件性上行印象；这会改变价值区间、永久损失判断和后续研究/买入处理，即使最终模块不直接生成价格。

**缺失事实。** 缺少对 delta magnitude 的证据，而不仅是对 driver 取值的证据：公司传导关系、同责任边界单位经济、期限和（若为 owner cash）维护资本/现金转换证据。

**禁止假设。** 不得以 `basis` 自由文本、driver input case 的证据，或组件的已授权 use，替代对量化 earnings/owner-cash delta 的证据。

**可执行修复。** 在 schema 和 validator 中为 BOUNDED delta 加必填 `evidence_ids`（或可解析的 canonical bridge-row/计算 claim 引用），并验证其存在于 `evidence_trace`、与 component/metric/unit/horizon 相容。DIRECT 正常盈利或 owner-cash delta 应当被其证据或已验证的算式明确约束；无法证实幅度时只能是 UNKNOWN delta/UNKNOWN transmission。同步更新 fresh-task 的 schema requirements 和 prompt，而不是由 materializer 补数或升级状态。

**验收标准。** 增加负例：base/conditional component + 任意 BOUNDED delta 但无 magnitude evidence 必须 INVALID；不相容的 evidence、单位或 horizon 也必须 INVALID。正例要证明有相同组件/责任边界的计算绑定时可通过；UNKNOWN delta 仍不产生数值归因、reader 不将其叙述为直接影响。

### 3. 匿名包允许 caller label 携带 arm mapping；自检的词界规则没有抓住该泄露

**根因分类：MODEL。**

`build_packet` 只要求 label 以 `ANON_` 起始（`scripts/anonymous_preoutcome_review_packet.py:68-72`）。`_assert_anonymous` 对 `A00` 等短 arm token 使用“前后不得为字母/数字/下划线”的正则（`52-60`），所以 `ANON_A00` 中的 `A00` 因前导 `_` 被当作词内内容而放行。针对该精确输入运行 `_assert_anonymous({"label":"ANON_A00"})` 的结果为 `ACCEPTED_LABEL_CONTAINS_A00`。

**经济影响。** label 可以直接把匿名臂映射回 baseline/enhanced treatment，污染 pre-outcome reviewer 的比较，令 paired test 的独立性和任何后续经济结论不可解释。该问题不要求产生价格或 outcome 才具有实质性。

**缺失事实。** 不适用；缺的是对 transport artifact 中 mapping 元数据的完整匿名化验证。

**禁止假设。** 不得假设 caller 总会选安全的 `ANON_*` label，或词界扫描就等于“无 arm mapping”。

**可执行修复。** 对输入 labels 做明确的 deny-list/sub-string 校验（至少拒绝任何包含 `ARM_IDENTIFIERS` 的 label），并让最终 packet 采用不含 arm token 的内部 label。将 `_assert_anonymous` 改为能检测整个序列化 packet 中每个已知 identifier 的严格检查；对 shared source ref/content 的潜在 mapping token 亦应拒绝或在进入 packet 前去除。

**验收标准。** 四臂输入中任一 label 为 `ANON_A00`、`ANON_A01_INDUSTRY_ONLY`，或 shared source ref/content 含已知 arm token，必须失败；现有 `ANON_COBALT/Fern/Ivory/Topaz` 正例仍通过。测试还应断言输出不含每个完整 arm 名和每个短 arm token。

## 测试证据

在不读取上述排除材料、禁用 pytest cache 与字节码写入的条件下运行：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_cash_accessibility_model.py \
  tests/test_enterprise_underwriting_episode.py \
  tests/test_enterprise_underwriting_training.py \
  tests/test_valuation_value_bridges.py \
  tests/test_cutoff_official_fact_register.py \
  tests/test_anonymous_preoutcome_review_packet.py
```

结果：**151 passed in 2.65s**。这些通过项证明已有回归覆盖了 leaf-only cash、三期/连续性门槛、确定性重算、component/route 冲突、fresh materialization 的既有三项窄操作、冻结 v1 replay 和常规 arm 替换；它们没有覆盖上面的 register-to-cash binding、delta-magnitude evidence binding，或 `ANON_A00` 标签泄露反例。

## 重新提交条件

完成三个阻断项的 schema/可复用 acquisition validator/实现/回归测试后，重新运行上述测试集，并额外运行每项验收标准中的负例与正例。重新审阅应确认：每一个进入 adopted cash/equity bridge 的金额可回溯到 pre-cutoff canonical observation；每个可量化敏感性 delta 有责任边界一致的证据；匿名 packet 在 caller label、来源引用与内容三个表面均无法恢复 arm mapping；同时 legacy frozen replay 的字节级合约兼容性保持不变。
