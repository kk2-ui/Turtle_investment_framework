# R-56｜红队复核与下一关

状态：`RED_TEAM_COMPLETE / NO_PRIMARY_CONFIRMED / OUTCOME_UNREAD`。

## 红队结论

R-56 的价值不是找到一个“扩产会成功/失败”的预测，而是检验企业系统图能否阻止四种看似合理、实则越界的判断。

| 红队攻击 | 为什么材料性 | 冻结后的处理 |
|---|---|---|
| H-C：复苏、项目融资与补贴可独立推动需求 | 出货、收入乃至合并毛利改善都可能与一体化无关。若忽略，会把行业状态误归给企业能力。 | D1/D2/D3 没有产品级价格—成本—现金闭环时一律不裁决 H-A/H-B。 |
| H-A 可把 2009 负 OCF 解释为过渡 | 负 OCF 不是自动的长期资金依赖；强行以此选择 H-B 会制造 selection evidence。 | 明确 `NO_PRIMARY`，D4 只结算未来 cash arrow。 |
| H-B 可在短期内也出现正 OCF | 经营现金可由应付、存货释放或一次性预收变化改善，不等于信用风险消失。 | 正 OCF 必须与 AR/第三方客户预收方向共同满足；否则 `MIXED`。 |
| 资本回收没有责任单元资本、折旧、税与替代路径 | 将 CAPEX、融资和合并现金拼成“企业家投资回报”会直接误判永久损失。 | D5 恒为 `CAPITAL_RETURN_UNKNOWN`；只能描述资本吸收边界。 |

## 方法裁决（结果前）

`RETAIN_AS_SYSTEM_SCOPE_GATE / NO_PRIMARY_AS_CORRECT_OUTPUT`。

本轮使研究者能在阅读结果前新增的区分是：

```text
capacity completed ≠ customer absorption
customer absorption ≠ product economics
product economics ≠ cash conversion
cash conversion ≠ capital return
```

它还强制把 H-C 留在假设空间中：只要 H-C 仍会材料性改变产出、单位经济或现金解释而没有可分叉观察，H-A/H-B 不能被包装成完整企业判断。

## 下一关与迁移

1. **R-56 outcome resolution：**只按 02/03 的合同读取 FY2010 20-F；最高产出是分层 verdict，不是公司结论。
2. **near-miss 入场：**寻找另一家中国制造扩产公司，在 cutoff 前同时具备产品能力、客户/价格状态、AR/预收/库存现金桥和同一年度一手结果文件；它必须只翻转一个上游中介（例如客户预收结构或产品性能带来的有效供给），不能按后续结果选择。
3. **boundary replication：**在相同 resource-commitment 问题下，仅改变外部约束（如补贴依赖、渠道交易点或技术有效供给）的一家不同公司，重新冻结同一 D1–D5 顺序。

此前 R-56 不能向 P-102、R-07 或任何选择准确率输入输出“支持”；它只提供一个完整企业系统的、可被 outcome-resolution 推翻的研究动作。
