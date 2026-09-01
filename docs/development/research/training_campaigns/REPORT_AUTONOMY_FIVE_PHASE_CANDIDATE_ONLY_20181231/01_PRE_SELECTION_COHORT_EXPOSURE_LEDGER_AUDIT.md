# 阶段 5：真实发行人暴露账本回执

> 状态：`PRE_SELECTION / LOCAL_ONLY / OUTCOME_BLIND / NO_TEST_ACQUISITION`

## 结论

本回执登记了 **39** 个本地可辨认的发行人记录：当前候选池十个代码、第二轮 scout 的
十二个候选侦察代码、八个家电 Pack-building 种子、一个本地 consumer-durables discovery
记录，以及八个当前唯一
`TRAINING_READY` 水泥 Pack / Course 目标冲突记录。账本通过结构校验，但它不是样本名单：
没有任何发行人被标为 `TEST_ACQUISITION`，没有 cohort 被选择或冻结。

当前十个候选中，`CN:002035` 与 `CN:002508` 已由本地 Round 10 roster 证明有训练
campaign 暴露，因此明确 `EXCLUDED`。`CN:002543` 只有 `RESERVED_NOT_OPENED` 记录；
这不是实际输入暴露，故保留 `UNASSIGNED`，并列明其版本和发行人身份缺口。其余候选也只
是 `UNASSIGNED` 的 source-acquisition 线索，不能因本账本通过而变为未见测试公司。

## 账本范围与角色

| 记录组 | 数量 | 账本处理 | 本地依据 |
| --- | ---: | --- | --- |
| 当前 candidate-only 发行人 | 10 | 2 个已知 campaign `EXCLUDED`；其余 `UNASSIGNED` | `sources/00_CURATORIAL_RECEIPT.md` 与十份 cutoff-only source-package drafts |
| 第二轮 candidate reconnaissance | 12 | 全部 `UNASSIGNED / CANDIDATE_RECONNAISSANCE_ONLY`；三份 CNINFO 年报 metadata 不构成 issuer identity 或测试资格 | `REPORT_AUTONOMY_FIVE_PHASE_SECOND_UNSEEN_ISSUER_OFFICIAL_SOURCE_SCOUT.md` |
| 家电风险集 / Pack-building 种子 | 8 | 3 个 `PACK_BUILDING`，其余已有 teacher/target/holdout/campaign 暴露而 `EXCLUDED` | national appliance source register、Course 1 rosters、Round 10 / continuous-training cutoff-before metadata |
| Consumer-durables discovery | 1 | `UNASSIGNED`，不把 discovery 误写成 source completion 或未见性通过 | `TURTLE_COMPARATIVE_NATIONAL_CONSUMER_DURABLES_2018_STATIC_SOURCE_PACKAGE_V1.json` |
| 既有 cement Pack / Course 冲突 | 8 | 全部 `EXCLUDED` | Cement Pack V3 identity catalog / Pack metadata，Course 1/2 rosters |

`PACK_BUILDING` 只是未来若完成独立 multi-period source and identity review 后可用于
构建 Pack 的意向；不是一个已经建立的 Pack，更不是测试侧选择。账本的所有 `reference`
都是本地路径，不含 URL，也没有读取所指对象之外的市场、结果或报告材料。

## 身份边界

现有 candidate-only drafts 大多明确要求下游 curator 在年报封面和证券资料页重建法定
发行人、名称连续性、版本和证券映射；因此账本的 `legal_entity_id` 统一显式标为
`LEGAL_ENTITY_UNCONFIRMED:<security>`。这是防止误把短名称、当前名称或同代码假定为
独立法定实体，而不是新增法律实体断言。别名列保持空：例如 `CN:002614` 的“蒙发利”历史
简称虽在 source draft 出现，但该 draft 本身要求独立 bridge，故不写成已确立 alias。

下一步只有在同一 cutoff 的官方来源完成封面/版本/实体桥后，才可将一条 `UNASSIGNED`
记录转入任何正式分配；若该过程发现与本账本任一已知实体、别名或重组经济主体重合，应
先更新账本为 `EXCLUDED`，而不是补写测试 cohort。

## 读取边界

本工作只读取本地 cutoff-before source-package 标题/元数据、第二轮 scout metadata、IndustryLearningBlock
成员 metadata 和 training-campaign rosters，用于身份及角色冲突。未读取 outcome、
settlement、市场价格、回报、估值、既有目标报告或外部网页；也未调用外部模型 API。
