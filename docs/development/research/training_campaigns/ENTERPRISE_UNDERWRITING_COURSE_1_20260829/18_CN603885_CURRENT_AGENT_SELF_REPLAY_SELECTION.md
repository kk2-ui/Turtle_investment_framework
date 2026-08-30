# 吉祥航空当前 Agent 自训练 Replay 选择

> 状态：`FROZEN_BEFORE_SOURCE_ACQUISITION`

| 项目 | 冻结内容 |
| --- | --- |
| 公司 | `CN:603885`，上海吉祥航空股份有限公司 |
| cutoff | `2019-05-01T00:00:00+08:00` |
| 训练轨道 | `BLIND_REPLAY / CURRENT_AGENT_SELF_REPLAY` |
| 结果状态 | `SEALED`，完整 Episode 验证前不读取 FY2019 及以后材料 |
| 截止日前材料 | 官方 FY2018 年报与截至 cutoff 的 FY2019 一季报/重大公告 |
| 反馈时钟 | FY2019、FY2021、FY2023 年报 |

选择前对整个仓库（排除历史档案和 Git 元数据）精确查询
`603885|吉祥航空|Juneyao Air`，没有命中。宋城演艺仍保留为已冻结但 `ACQUISITION_MODULE`
路线未解析的候选；不重复同一 CNINFO 查询，也不把这次替换解释为结果筛选。

## 训练目的

吉祥航空使课程进入客户需求、运力、航线网络、客座率/票价、燃油、租赁/机队资本、融资与
现金共同决定经济性的航空服务行业。当前 Agent 必须把行业冲击穿过公司位置和适应，区分运营
完成、客户/单位经济吸收、维护后现金、全部机队资本压力和增长机队回报；不能把任何既有
品牌、渠道、重整或制造经验直接替代该公司的承保。

这是 current-Agent 自训练，不构成独立模型或方法验证；不新建 gate，不创建
`TRANSFER_CANDIDATE`、`TRANSFER_VALIDATED` 或 `METHOD_VALIDATED`，也不授予 CJO、估值、
黄金报告或投资权限。
