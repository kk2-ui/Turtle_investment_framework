# V4 行动标题发现法辅助试点

状态：`HISTORICAL / SUPERSEDED_BY_H1_STRICT_CURATOR_INTAKE / NO_RUNTIME_AUTHORITY`

更新：2026-08-24

上位目标：[历史优先训练架构](TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)

## 1. 要回答的问题

这是一份已停止的历史试点记录，**不授权标题、公司名称、行业关键词或公告页面搜索，也不授权产生真实 V4 candidate**。它原本要检验一个很窄的 acquisition 问题：是否能仅靠公告标题高效发现 V4 的公司整体经营行动；该问题不回答、也不得外推为“中国公开资料是否足够训练”。当前唯一真实入口是 [strict H1 curator static-PDF intake](TURTLE_STAGE0_STATIC_SOURCE_INTAKE_DESIGN.md)，随后必须有绑定 receipt 的 H2 action-screen extension。

V4 的要求见[材料性与同行反事实协议](TURTLE_SELECTION_MATERIALITY_AND_PEER_COUNTERFACTUAL_PROTOCOL.md)。它不用于并购整合、资本配置或资本结构；那些问题若要训练，必须另建拓扑，不能通过降低 V4 门槛混入。

## 2. 有界设计与退出规则

批次固定为十二条线索，每个原型四条：

1. 公司整体生产网络收缩／整合；
2. 近乎单一主业公司的已商业运行工艺替换；
3. 单一业务／品牌发行人的全面、已执行价格或渠道条款重置。

以下仅保留为历史试点设计，不得执行。当前不允许把标题生成的 manifest 运行成 `DISCOVERY_READY`；只有 strict H1 receipt 与 H2 extension 绑定通过，才可进入后续 V4 采集，且仍不创建 episode。

批次结束时：

- 至少两条 `DISCOVERY_READY`：将它们加入行业 cohort-first 主线，按既定 V4 full acquisition 取得最强一条的 case freeze；
- 少于两条 `DISCOVERY_READY`：仅裁定 `ACTION_TITLE_DISCOVERY_LOW_RECALL`，停止扩大标题枚举。转入行业 cohort-first：先选披露丰富的五家公司、建立行动前 D2/D3/D4 面板，再从 cutoff 前年报、公告和经营叙事定位真实行动；不放宽 D2、责任边界、五年 D3/D4、同行或 firewall。

“至少两条”不是胜率检验，只是避免因为单一异常披露就把一条昂贵采集管线误判为可持续。

## 3. 固定初始批次

| # | 原型 | 线索 | 当前截止前状态 | 已知停止点 |
|---|---|---|---|---|
| 1 | 网络整合 | 史丹利 002588 老厂线关停 | `NO_PRIMARY` | 董事会决定不等于实际停产；一厂老线未覆盖合并边界。 |
| 2 | 网络整合 | *ST 爱富 600636 吴泾装置关停 | `NO_PRIMARY` | 区域装置与业务退出／转型混杂，无法映射合并边界。 |
| 3 | 网络整合 | 中泰化学 002092 西山搬迁 | `NO_PRIMARY` | 搬迁完成，但西山生产区覆盖率与合并现金边界未知。 |
| 4 | 网络整合 | 恒天天鹅 000687 粘胶长丝关停通知 | `TITLE_STOP` | 政府通知及“逐步关停”不构成已实施商业行动。 |
| 5 | 工艺替换 | 神剑股份 002361 设施技改完成 | `NO_PRIMARY` | 技改完成但未覆盖合并边界；无实际暴露、三期独立 D2 或可注册反方。 |
| 6 | 工艺替换 | 老板电器 002508 吸油烟机技改 | `TITLE_STOP` | 单项目／单品类。 |
| 7 | 工艺替换 | 九九久 002411 头孢产线恢复 | `TITLE_STOP` | 单一生产线。 |
| 8 | 工艺替换 | 瓦轴 B 200706 滚子轴承工厂技改 | `TITLE_STOP` | 工厂单元。 |
| 9 | 价格／渠道 | 涪陵榨菜 002507 主力产品调价 | `NO_PRIMARY` | 主力产品与合并边界未闭合，D2 不独立。 |
| 10 | 价格／渠道 | 片仔癀 600436 主导产品提价 | `NO_PRIMARY` | 产品与合并边界未闭合，D2 与同行反事实缺失。 |
| 11 | 价格／渠道 | 中核钛白 002145 钛白粉调价 | `NO_PRIMARY` | 产品与合并边界、真实暴露及第三家同行缺失。 |
| 12 | 价格／渠道 | 齐峰新材 002521 主营产品调价 | `TRIAGE_PENDING` | 标题不足以证明实际执行、全面边界和独立 D2。 |

所有线索只来自 cutoff 前官方标题／公告；精确来源和禁止替代见[选择训练准入发现台账](SELECTION_ADMISSION_DISCOVERY_LEDGER.md)。旗滨、青岛啤酒和贵州茅台已因 source-access exposure 永久排除，不得替补进本批次。

## 4. 执行纪律

以下为停止时的历史纪律记录，不能被解释为当前命令、source access 或 candidate 许可；当前授权只以 H1 strict receipt 与 H2 extension 的绑定校验为准。

1. 不进入 CNINFO 个股默认页、公告 detail 页或任何全文检索页（包括发行人代码／名称和行业关键词）；实测日期筛选无法阻止这些页面先自动渲染当前卡片。只使用已知 cutoff 前、逐份进入 allowlist 的 `static.cninfo.com.cn` PDF package。详见[历史 PIT 发现入口政策](TURTLE_PIT_DISCOVERY_ENTRY_POLICY.md)。
2. 不读 chosen cutoff 后标题、元数据、正文或价格；一旦暴露，立即永久排除该对象并记录到台账。
3. `TITLE_STOP` 不为凑数量扩读年报；`NO_PRIMARY` 不建 episode、不读结果、不用后续材料补洞。
4. `DISCOVERY_READY` 只授权按[V4 候选采集工作包](templates/TURTLE_V4_CANDIDATE_ACQUISITION_WORK_PACKAGE_TEMPLATE.md)取得完整 source package；它不授权 outcome access、learning、方法冻结、R-103 或报告使用。

## 5. 当前裁决边界

截至停止时，本试点未产生可接纳的 `DISCOVERY_READY`；它只显示标题发现法低召回，不证明 V4 不可行、公开资料不足或训练已经产生选择能力。不得把已拒绝线索重新包装为黄金报告经验。

旧 [CN 水泥上市公司 cohort](cohorts/COHORT_CN_CEMENT_LISTED_20180430_feasibility.json) 仍不能直接作为 strict H1 输入：它是旧的 `judgment-selection-cohort-feasibility.v1` 记录，缺 curator attestation、逐页 static-PDF identity 和机制定义 arena。记录中的两名 scope/control break 成员应保留为 disclosure-only，三名其余成员也只能在 H2 重新审查，不能把旧记录直接升级为 H1、H2 或 V5。不得在这份旧记录上定位行动，也不得以补两家公司、标题筛选或旧 manifest 重新激活；新的独立 curator H1 package 才是唯一重新开始的入口。
