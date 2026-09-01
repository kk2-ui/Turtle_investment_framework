# Judgment-First 企业承保课程一期：完成审计

> 审计结论：`COURSE_1_COMPLETED / CURRENT_AGENT_BEHAVIOR_REINFORCED / METHOD_NOT_VALIDATED`
>
> 基线：本地 `main@eadaae9dedbf4cf1c3ac621031bb18fd0f4d49f0` 的独立分支

## 结论先行

课程一期已经完成“完整企业判断的历史训练闭环”：结果已知教学案例建立参照系；四个原始
Blind 和六次当前 Agent 结果后回放将完整 Episode 冻结在结果前，再反馈到研究议程。当前
Agent 已不再将 `UNKNOWN`、维护资本未拆、perimeter 变化或未完成 Comparative 当作整家公司
拒绝判断的理由，也没有把“更保守”自动判成更好。

但这**不是方法能力验证**。唯一具认知隔离的公平 A/B 是顺丰，裁决为 `ENHANCED_WORSE`；
广州酒家和其后的五次回放只显示已知反馈改变了当前 Agent 的研究顺序，不能证明独立模型、
独立基线或黄金报告已经更好。因此所有方法、迁移与投资权限继续为零。

## 要求—证据—裁决

| 课程要求 | 当前证据 | 裁决 |
| --- | --- | --- |
| 12 个跨行业 `WORKED_CASE` | `worked/` 下 12 个已验证 Episode；第 12 个麦格纳困境周期案例通过正式训练入口，提交 `a0459d8` | `COMPLETED`；仅教学，不计能力。 |
| 结果前完整企业承保对象 | 4 个原始 Blind、广州酒家 A/B 两臂、玲珑、晨光、贵人鸟、上海家化、吉祥航空均有完整 Episode；各对象含行业未来、位置、生存、适应、正常化、owner cash、永久损失和价值路线 | `COMPLETED`。 |
| 真实历史结果反馈 | `outcomes/01–04` 及 `06–11`，均在相应 Episode 冻结后才读取官方年度资料 | `COMPLETED`。 |
| 反防御性写作 | 天山 perimeter、九阳正常化、桃李维护资本、贵人鸟融资、航空外生冲击均只局部限制主张，仍形成公司判断、反方和翻转条件 | `COMPLETED`。 |
| 条件化机制和研究议程写回 | `07_POSTOUTCOME_RESEARCH_AGENDA.md` 已写入资本三账、轻资产资源责任、原普通股权利、品牌渠道效率和航空运力/融资边界 | `COMPLETED`。 |
| 未见公司改善的诚实判断 | 顺丰公平 A/B 为 `ENHANCED_WORSE`；广州酒家仅为 `CURRENT_AGENT_SELF_RUN_MATERIAL_RESEARCH_IMPROVEMENT` | `COMPLETED_WITH_NEGATIVE_METHOD_VERDICT`。 |

## 实际学到的企业判断

课程保留的不是“扩张危险”“消费品轻资产”或“危机必死”这些口号，而是条件化顺序：

```text
行业利润池与公司位置
→ 成熟核心、增长 cohort 与融资/普通股边界
→ 客户、单位经济、营运资本与资产/租赁责任
→ 正常盈利、owner cash、永久损失与价值路线
```

该顺序在制造、品牌渠道、服务/收购、融资困境和航空五类结构中都避免了同一种错误：把实施、
总量或单个现金字段替代经济吸收。它同样要求在证据支持时承认核心现金与恢复可能，不能因
增长尚未结算就将公司整体写成负 owner cash 或失败。

## 未完成与权限

| 事项 | 状态 | 原因与后续 |
| --- | --- | --- |
| `TRANSFER_CANDIDATE` / `TRANSFER_VALIDATED` | `0` | self run 没有认知独立性；未来需要新的隔离 Agent/基线。 |
| `METHOD_VALIDATED` | `0` | 顺丰 Enhanced 更差，第二次 A/B 非独立；不能用更多 self 回放覆盖负结果。 |
| CJO freeze、正式估值、BuyBand、黄金报告发布、投资权限 | 未授予 | 课程输出只到 price-free 训练候选。 |
| 宋城演艺历史源包 | `ACQUISITION_MODULE` 未解析 | 深交所/CNINFO 查询未返回资料；已保留选择并改用吉祥航空完成异质训练，不增加 gate。 |

## 下一阶段

不再扩建课程控制层或重复 self replay。若启动课程二期，唯一有材料性的验证应是一个由认知
隔离 Agent 完成的同 cutoff、同证据、相近预算 A/B；它必须改变当前公司正常盈利、owner cash、
永久损失或价值路线之一，并经独立结果审阅确认。若仍无材料效用，应修改 `REASONING` 或
`MODEL`，而不是增加 gate、字段、收据或 `UNKNOWN`。
