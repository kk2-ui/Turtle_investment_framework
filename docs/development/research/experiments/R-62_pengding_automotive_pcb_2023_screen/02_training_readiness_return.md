# R-62 历史训练准入返回

状态：`RETURNED / NOT_READY_FOR_CONTROL_REGISTRATION`

更新时间：2026-08-23

## 结论

R-62 当前不能作为已冻结的历史选择训练 episode 执行。现有 `01_pre_outcome_admission_screen.md` 仍明确记录 `NO_PRIMARY / NOT_FROZEN / OUTCOME_BODY_UNREAD`：它是结果前筛查，不是完整 PIT case，也没有获得 `SELECTION_ADMITTED`。把它直接注册为选择训练并开始学习，会把“资料不足导致的弃权”误记成可迁移的主路径判断。

本返回不否定 R-62 的训练价值。R-62 可以继续作为历史机制训练输入，检验系统是否会拒绝把项目审批、认证、集团收入或集团经营现金流当成项目成功；但在补齐可结算的责任单元和公平反方之前，不能生成正式 method learning，也不能满足方法冻结门。

因此，训练计划只登记 R-62 的身份和结果隔离，不登记任何 `freeze_ref`。现有筛查页是准入返回，不是冻结工件；把它写入 `freeze_ref` 会让控制面在注册时错误地把 R-62 投影为已冻结。

## 根因与经济影响

根因分类：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。

| 缺口 | 对投资判断的经济影响 | 禁止替代 |
|---|---|---|
| 没有结构化 PIT case、冻结报告和独立 review receipt | 无法证明所有判断只使用 2023-03-30 前信息，也无法重放冻结身份 | 不得把现有筛查 Markdown 当作完整 case |
| 汽车/服务器项目没有项目专属客户吸收、订单/量产接口和同口径量价成本 | 无法区分“认证/扩产会形成可吸收经济”与“集团其他业务或行业景气带来的共同变化” | 不得使用认证数量、合并收入、公司 IRR 或行业规模填补 |
| 没有责任单元营运资本现金桥和实际资本范围 | 无法判断新增资本是否转成普通股可达现金、是否造成永久损失 | 不得使用集团 OCF、合并毛利或计划投资额代替 |
| 没有冻结 H-A/H-B、简单基线和结果合同 | 后续结果即使出现，也不能区分主机制、反方和延续基线 | 不得先读结果再补写预测 |

## 可执行修复

1. 由 acquisition owner 在不读取结果包的前提下补齐同一责任单元的项目范围、客户/量产接口、产品级量价成本、营运资本桥和实际资本边界；每个字段必须绑定 cutoff 前官方来源。
2. 由 judgment owner 重新建立 H-A/H-B、最强反方和简单延续基线。若没有至少一项非共同方向证据使三者对同一结果观察给出不同预测，保持 `NO_PRIMARY`，只登记为机制训练。
3. 只有上述材料闭合后，才建立真实 `HBTCASE`/CJO PIT freeze、结果合同、独立 reviewer receipt，并把结果访问保持为 `PIT_OUTCOME_SEALED`。
4. 若 R-62 经补证仍为 `NO_PRIMARY`，将其结算为机制边界学习；另从历史资料中选择一条具有合格选择证据的不同公司 replay，才可启动跨公司 method learning 和 `freeze-method`。

## 接纳标准

R-62 只有在以下条件全部满足时，才可回到 `READY_FOR_CONTROL_REGISTRATION`：

- 结构化 case 通过 `validate_case(..., allow_test_fixtures=False)`；
- `selection_status`、H-A/H-B、简单基线、观察窗口和结果来源合同在结果读取前冻结；
- D1--D5 至少有可归属的项目/责任单元字段，不能用集团代理；
- 独立 reviewer 确认来源、泄漏边界、反方和未知项；
- 结果包只在冻结后打开，且每层允许 `UNKNOWN / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`；
- 若仍为 `NO_PRIMARY`，系统明确把它排除在 method learning 和选择评价之外。

在这些条件满足前，R-62 不计选择正确性、方法优势、概率、胜率、投资收益或组合收益。
