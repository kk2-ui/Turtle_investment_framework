# Course 2B 结果封存与 Custodian 交接

> 状态：`TWO_EPISODES_FROZEN / CUSTODIAN_OUTCOME_OPEN_AUTHORIZED`

## 封存对象

结果窗口固定为 FY2018—FY2020，且必须分成两层：

1. 行业层：全国需求/产量、价格、收入、利润、利润率、供给纪律和过剩耐久性；
2. 公司传导层：上峰水泥的区域暴露、销量/产品结构、盈利、经营现金、长期资产投入、受限现金/债务、扩张资本和价值路线。

结果期公司 PDF 已仅保存在 git 忽略的 `output/000672_上峰水泥/course2b_source_vault/`，不在任一训练合同 allowlist。结果期行业资料同样不进入训练合同。合同运行器只读 allowlist，因此两臂无法读取这些对象。

## 开封条件

只有以下条件同时成立后，Custodian 才能生成结果反馈：

- Baseline 与 Enhanced 各自的一次模型 run 已完成；
- 两份 `enterprise_underwriting_episode.json` 均通过各自合同绑定验证；
- 两份投资者读本均由相应冻结 Episode 单向生成；
- 两臂产物不再修改；
- reviewer 映射只由 custodian 保存，Fresh Reviewer 先收到匿名 `Arm A` / `Arm B`。

## 结果反馈约束

行业层不得用上峰单家公司结算；公司层不得用全国量价替代上峰区域价格、成本或现金。每一层都要说明：实际观察、支持/反驳的预注册命题、仍不可区分的事实、对正常盈利/owner cash/永久损失/价值路线的经济影响。

Custodian 不评价写作风格，也不选择胜者。Fresh Reviewer 必须先做结果前推理比较，再读取两层结果；最终裁决根因必须归为 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 或 `WRITING`，并给出禁止假设、可执行修复和下一轮接受条件。
