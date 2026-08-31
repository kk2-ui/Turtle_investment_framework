# Turtle 训练基线对齐（2026-08-31）

> 状态：`CURRENT / AUTHORITATIVE_TRAINING_BASELINE_INDEX`
>
> 集成起点：`main@4109caa`
>
> 目的：把已合入的训练能力、已完成但历史分支承载的课程结论，以及当前可执行训练入口收敛到一个索引；不把旧分支重新当作开发基线。

## 结论先行

Turtle 的唯一训练开发基线仍是干净的本地 `main`，不是若干课程分支的并集。历史分支中有可保留的经济学习，但它们携带的旧 runtime、旧 Episode、旧合同和过期状态不能倒灌到当前主线。

本次对齐将它们按证据强度写回当前基线：可复用的是**问题顺序与适用边界**；不能写成已经具备的能力是跨公司迁移、行业前景预测或投资授权。新的训练一律使用当前 `enterprise_underwriting_training.py`、完整 `EnterpriseUnderwritingEpisode` 和 fresh Codex 隔离流程。

## 当前可执行基线

| 层级 | 当前真源 | 已证明的范围 | 不能声称的范围 |
| --- | --- | --- | --- |
| 统一工程基线 | `main@4109caa`、`AGENTS.md`、`scripts/enterprise_underwriting_training.py` | 当前 Codex + `fork_turns=none` fresh Agent，v2 合同、组件下游用途与独立审阅均可执行 | 不因 runtime 可执行就等于判断能力已验证 |
| 首条经验调用纠偏 | `CN601865@2024-04-01` 的 outcome review 与 investor readout | 新增产能不能仅凭投产、总现金或集团叙事进入 normal owner cash；先检查现金资本吸收、客户吸收、价格/价差、维护/增长资本和可回收性 | 该正现金 observation 为 `NOT_DIAGNOSTIC`，不验证 transfer 或 method |
| Course 1 | `ENTERPRISE_UNDERWRITING_COURSE_1_20260829/14_COURSE_1_COMPLETION_AUDIT.md` | Worked case、blind replay 和完整 Episode 链可运行；局部未知不应中止公司承保 | 唯一认知隔离 A/B 为 `ENHANCED_WORSE`，不能称方法有效 |
| Course 2B | `ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/15_COURSE_2B_COMPLETION_AUDIT.md` | 水泥 Pack 和未见公司公平 A/B 的负结果可约束后续合同：组件必须明确接入正常盈利、owner cash、融资、永久损失和价值路线 | `NO_MATERIAL_UTILITY`，不验证行业判断或迁移 |
| Course 2C | `ENTERPRISE_UNDERWRITING_COURSE_2C_CN600720_20180430/10_COURSE2C_FINAL_UTILITY_REVIEW.md` | 在祁连山未见公司上，成熟核心、会计控制边界、生命周期 cohort 与资本责任的组件化传导改善了公司层处理 | 行业路径没有材料差异；单一正样本仅为 `TRANSFER_CANDIDATE`，不构成 method release、估值或投资权限 |

## 从历史训练分支迁入的结论

下表把仍有用的最终结论纳入当前训练索引。分支与其完整工件保持原样以供追溯，但不作为运行入口，也不直接合并。

| 历史来源 | 最终状态 | 保留的经济学习 | 当前处置 |
| --- | --- | --- | --- |
| `feat/judgment-first-independent-validation@77da233` | `PASS / MATERIAL_UTILITY_SUPPORTED — CASE_LOCAL` | 在牧原，不能把扩张期的总投入后现金缺口或融资需求误写成维护资本后的 owner cash；核心运营、维护现金、总资本吸收、融资责任与 cohort 回报必须分开。美年的应用仅改变问题顺序。 | 作为实体资本责任的条件化经验；不升 `TRANSFER_CANDIDATE`。 |
| `feat/judgment-first-underwriting-countercondition@d011a44` | `PASS / SUPPORTED — OBJECT_BOUNDARY_ONLY` | 银行的存贷款和金融头寸使经营现金流正负切换，不可套用工业 `OCF - capex` 模板；改由“盈利—信用—资本/流动性—普通股分配”承保链。 | 保留为模板适用性反向条件；不证明另一家银行或工业公司的结论。 |
| `feat/judgment-first-enterprise-underwriting-course-4@da793a4` | `PASS / COURSE_COMPLETE / METHOD_NOT_VALIDATED` | 宝信补齐第三个真正零命中 blind；公司级盈利韧性不能因一个项目 cohort 缺口被机械压低，但项目回报仍须以同责任边界的吸收、单位经济、维护资本和现金回收确认。 | 保留其 `KEEP / NARROW / RETIRED` 研究顺序；三次公平 A/B 均为 `NO_MATERIAL_UTILITY`，不构成训练优势。 |
| `feat/judgment-first-course5-material-normalization-v2@ffd013a` | `METHOD_NOT_VALIDATED / THREE_AB_TESTS_NO_MATERIAL_UTILITY` | owner cash、渠道责任、资本组与普通股索取权必须按责任边界分开；“会多分一层账”本身不算训练效用。 | 其有效 owner-cash 纠偏补丁已在当前 main 保留；其余旧课程工件只作历史来源。 |

## 不迁移的分支与原因

- `feat/course2b-cement-unseen-ab@787a875` 只是结果前 WIP；当前 main 已拥有同一 campaign 的正式双臂、结果和收口，故不迁。
- 家电、早期 enterprise-judgment、historical PIT 与早期设计/审阅分支未继承最低基线 `eadaae9`；它们只能经逐项能力映射后迁移，不能合并。
- `docs/training-capability-reproduction-design-20260830` 是 `DESIGN_ONLY`，`fix/full-test-suite-baseline-20260830` 是历史工程修复；两者都不是当前训练基线。

## 后续执行规则

1. 新训练从当前 `main` 建立 linked worktree；禁止从本页列出的历史 branch 继续开发。
2. 经验只能提供参考类别、问题顺序和适用边界；目标公司的暴露、适应、现金和价值路线仍须由自身 cutoff 前证据建立。
3. 正负历史结果都要约束下一轮：历史的 `NO_MATERIAL_UTILITY` 防止把更多结构、篇幅或悲观误作能力；Course 2C 的正结果只允许在另一未见公司或时间 holdout 上复验同一公司传导机制。
4. 不删除历史 worktree 或 branch。本页完成的是当前真源对齐，而不是清除审计出处。

## 投资者读出

训练现在更清楚地知道三件事：不要把增长资本或项目建设提前资本化为 owner cash；不要把局部项目资料缺口扩大成整家公司无法判断；也不要把工业现金公式套到银行等不同经济对象。Course 2C 进一步显示，组件化责任边界能在一间未见重资产公司改善正常盈利、现金、损失和价值路线的处理。

但这还不是“行业会判断”或“方法已经普遍有效”。行业主路径在 Course 2C 没有胜出，历史的三次公平 A/B 也没有胜出。对投资者最有价值的当前状态是：研究顺序和错误边界变得更可靠；任何具体公司的行业前景、normal owner cash 和价值仍要由该公司的证据重新承保。
