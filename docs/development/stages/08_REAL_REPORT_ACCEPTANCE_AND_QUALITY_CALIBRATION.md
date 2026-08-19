# Phase 08：真实报告验收与质量校准

> 状态：VALIDATING ｜ 优先级：P0 ｜ 依赖：Phase 01–07 ｜ 最后更新：2026-08-19
>
> **2026-08-19 执行覆盖：**本文件原有的“01502主候选、02669冻结后控制样本、单黄金契约”样本篮子与顺序已成为历史设计。当前 Phase 08 采用多报告 `Golden Set v1`，并在 G1 后新增 G1.5 格力行业经验工厂：24 份黄金级公司/PIT/行业/宏观产物验证“公司 → 行业 → 宏观传导 → 公司”的双向层级研究。当前仍只有 G1 为 `IN_PROGRESS`；G1.5 尚未激活，不得因路线图落库而提前生产报告。当前案例、状态、顺序和完成定义以仓库根 `GOALS.md` 及 `docs/development/GOLDEN_REPORT_BIDIRECTIONAL_RESEARCH_ROADMAP.md` 为准；本文件其余技术门与历史记录仅在不冲突时继续适用。

## 1. 核心问题

前七阶段解决了证据、身份、估值、决策、监控和运行治理，但“技术上可发布”不等于“具有优秀投资洞见”。本阶段用真实公司验证自动系统能否选对问题、读到关键资料、形成有区分力的因果判断，并把判断一致地传递到估值和动作。

### 1.1 本阶段服从的用户目标

Phase 08是对完整价值投资报告可靠性的验证，不是报告产品的重新定义。它必须服务于以下目标：Agent在充分读取公司与行业上下文后，按格雷厄姆到巴菲特的完整思想，自动形成包含商业、护城河、财务、治理、现金兑现、估值、安全边际、反方和动作的完整报告；操作人审阅成稿是否符合其投资体系以及最终结论，不参与中间候选动作审批。

本阶段尤其不得把“信息效率”理解为删去有效研究内容。摘要只能承担导航和决策入口，不能代替完整报告。盲评、机器门和黄金契约用于发现事实、推理、估值和动作的可靠性问题；如果它们促使系统追求更容易评分的短报告，而不是更完整可靠的研究，说明阶段实现偏离了总目标，应修正验收与生成方式。

现金判断继续遵守用户的核心认识：现金全额可达尚未验证，只能限制额外加回的幅度，不能直接把现金价值归零；普通分红、回购、利息、母公司可分配储备和子公司上划记录属于真实兑现证据。企业属性也必须进入证据权重与估值路线，但央企或国企身份不能替代对少数股东兑现路径的验证。

## 2. 不可变原则

1. 先冻结协议再看候选结果，禁止为迁就现有报告修改标准。
2. 机器门只能判定可复核性和硬错误，不能自动授予“洞见优秀”。
3. 不采用可补偿总分；表达清晰不能抵消事实、推理、模型或动作错误。
4. 字符数、公式数、因果词、来源数量只作空壳诊断，不代表研究深度。
5. 黄金基线保存结构化不变量和独立评审，不把旧报告全文变成不可删除的模板。
6. 缺报告、缺账本或缺研究记录必须显示 `NOT_ASSESSABLE/INCOMPLETE`，不得跳过后给高分。
7. 关键结论必须回到原始年报、公告或可复核外部正文；搜索摘要不能作为最终证据。
8. 估值层、论点层或洞见层的动作只能作为内部工作假设；人工审阅对象是完成契约通过后的整份报告、投资体系一致性和最终结论，不是中间候选动作。

## 3. 样本篮子

| 样本 | 原型 | 角色 | 初始状态 |
|---|---|---|---|
| 01502 金融街物业 Phase K | 港股物业、治理与现金可得性 | 已完成主候选 | 技术 COMPLETE，洞见 COMPETENT |
| 000651 格力电器 | A股成熟制造、资本配置 | 历史基线 | 有报告，缺完整 V3 账本 |
| 000651 格力电器 Phase08 | A股成熟制造、资本配置 | 隔离重跑候选 | validation-only，不复用旧报告正文 |
| 002027 分众传媒 | A股轻资产、周期与成长价值 | 待生成样本 | 缺正式 v13 验收对象 |
| 02669 中海物业 | 港股物业同行 | 保留控制样本 | 缺正式 v13 验收对象 |

规则调试不得使用中海物业的人工评价结果；它只在规则冻结后用于控制样本验证。

## 4. 状态机

```text
NOT_ASSESSABLE
  → TECHNICALLY_BLOCKED
  → READY_FOR_BLIND_REVIEW
  → BENCHMARK_CANDIDATE
  → BENCHMARK_APPROVED
```

- `NOT_ASSESSABLE`：报告或关键身份缺失。
- `TECHNICALLY_BLOCKED`：完成契约、事实、证据、估值或动作硬门未通过。
- `READY_FOR_BLIND_REVIEW`：机器契约通过，但尚未完成独立洞见评审。
- `BENCHMARK_CANDIDATE`：至少两份有效独立评审完成，无未解决致命问题，至少一份评为 `INSIGHTFUL`，且没有 `FRAGILE`。
- `BENCHMARK_APPROVED`：候选经人工批准并冻结黄金不变量。

任何自动步骤最高只能到 `READY_FOR_BLIND_REVIEW`。人工批准不能覆盖机器硬失败。

中间研究不得插入“动作审批”状态。若估值工作假设与旧canonical动作冲突，应进入`INTERNAL_SYNTHESIS_REQUIRED`并继续构建完整报告；只有全文机器门闭环后，才可进入面向操作人的投资体系一致性审阅。

## 5. 六个独立评审维度

每个维度只能填 `STRONG/MIXED/WEAK/NOT_ASSESSABLE`，必须写依据和报告定位：

1. `decisive_question_quality`：是否选中了真正价值敏感且可区分的问题。
2. `evidence_discrimination`：证据是否能区分主解释与最强替代解释。
3. `causal_depth`：事实是否穿透到机制、现金流、估值和动作。
4. `valuation_judgment`：模型是否适用，脆弱假设与拒绝路线是否清楚。
5. `action_coherence`：估值、仓位、触发器和论文翻转是否一致。
6. `information_efficiency`：是否以较少重复表达保留必要推导和反证。

总裁决沿用 `INSIGHTFUL/COMPETENT/FRAGILE/NOT_ASSESSABLE`，不转成数字平均分。

## 6. 机器验收范围

- 报告和15章身份；
- completion与V3各账本状态；
- 决定性问题计划及结论闭环；
- `research_execution.json` 中实际 `read_section/search_report/web_search/web_fetch` 记录；
- 两个财年原始资料读取；
- 模型适用性、竞争解释、阈值与动作一致性；
- 独立挑战者结果和未解决脆弱跳跃；
- 表达重复、空壳主题和邻证信号，仅用于排定人工复核优先级。

## 7. 黄金不变量

黄金基线只冻结：

- 公司/期间/信息截止日；
- 1–3个决定性问题身份及入选理由；
- 最强竞争解释和区分信号；
- 必须保留的原始证据身份；
- 估值模型角色及禁止模型；
- canonical决策身份与动作翻转关系；
- 已知易错模式；
- 独立评审结论和人工批准记录。

它不冻结字符数、段落顺序、措辞或旧目标价。事实更新和结论变化只需留下有来源的变更理由。

## 8. 工作包

1. 建立真实样本注册表、验收schema和只读聚合器。
2. 生成首轮机器基线，诚实暴露不可评估和阻断项。
3. 为可审阅候选生成去版本标识的盲评包。
4. 完成至少两份独立评审和人工批准流程。
5. 对格力、分众、金融街物业重跑；中海物业作为冻结后控制样本。
6. 只修复跨样本重复出现的框架问题，不给单只报告打补丁。
7. 重跑主干回归和真实样本对照，形成黄金不变量。

## 9. 完成标准

- [x] 验收配置、结果、独立评审、黄金契约及批准预览均有schema或机器契约。
- [x] 聚合器不会把缺失报告、旧报告、旧版本评审或软分提升为高质量。
- [x] 至少一个A股和一个港股完成真实统一管线 validation-only。
- [ ] 至少三种商业/风险机制进入独立评审。
- [ ] 中海物业控制样本在规则冻结后运行。
- [x] 跨样本框架修复有对抗测试，主干回归不退化。
- [ ] 至少一份报告成为 `BENCHMARK_APPROVED`；若没有，阶段保持 `VALIDATING`，不得降低标准。

## 10. 当前已知基线

- 金融街物业 Phase K：结构化账本完整，completion `COMPLETE`，独立挑战者为 `COMPETENT`，因此最多进入 `READY_FOR_BLIND_REVIEW`。
- 格力：存在正式报告，但缺少完整 V3 决策、证据、估值、论点和洞见账本，当前不可作为黄金报告。
- 分众、中海物业：当前没有正式 v13 验收报告，必须真实生成，不能用章节目录冒充完整候选。

## 11. 已实现的验收防作弊边界

- 评审与当前报告SHA-256派生的`variant_id`绑定；报告变化后旧评审自动失效。
- 黄金契约同时绑定`variant_id`、完整报告哈希和当前有效独立评审身份，不能跨版本复用。
- 人工批准采用两步流程：先生成包含完整契约的批准预览及指纹，再用相同指纹和审批人显式确认；程序不能自动授予批准。
- 只有机器硬门通过的候选才进入盲评包索引；`TECHNICALLY_BLOCKED`报告不会消耗人工评审资源。
- 规则未冻结时，控制样本不进入聚合结果，也不生成盲评包；当前基线明确显示注册5个、可见4个、留置1个。
- 真实运行受ADR-008预算预检、墙钟/未缓存token硬限制和无进展熔断约束。

## 12. 当前验证出口

只读基线为：4个可见样本中1个`NOT_ASSESSABLE`、3个`TECHNICALLY_BLOCKED`，中海物业控制样本仍被留置，0个黄金批准。该结果意味着验收器已能诚实拒绝旧产物，但Phase 08尚不能标记`COMPLETE`。下一出口不是降低标准，而是经预算预检完成一个A股和一个港股的真实`validation-only`运行，使其先进入`READY_FOR_BLIND_REVIEW`。

### 2026-08-03 格力隔离实跑进展

- A股候选已真实推进到 claim、valuation、thesis 三个账本均为 `DECISION_READY`，证明估值路由、拒绝模型身份与前置依赖链能够在真实模型调用中工作。
- 运行在 `write_decisive_question_findings` 暴露首个新框架缺陷后立即中止：该工具缺精确嵌套契约、失败验证不落盘且未进入同错熔断。没有用重复调用继续试错，也没有给格力报告做单例补丁。
- 已统一修复为：`read_structured_ledger_contract(ledger=decisive)` 返回入选问题及合法 signal/explanation/OBS ID；工具 schema 约束完整嵌套类型；最近尝试验证独立落盘；连续两次相同阻断立即结束真实轮次。
- 阶段回归为 `377 passed`。下一步须重新取得长实跑批准，从现有隔离候选断点继续验证 findings → insight → review → validation-only assembly；在成功前A股完成标准仍不勾选。
- 第四次断点续跑中，findings 在第一次提交即成为 `DECISION_READY`；契约可见性修复得到真实验证。随后 insight 被依赖守卫误拦截：守卫读取问题计划的 `decisive_question_validation.json=REVIEWABLE`，而非已通过的 `decisive_question_findings_validation.json=DECISION_READY`。运行当即停止，本轮共5次调用、102,146个未缓存输入token，无重试。
- 依赖文件名已修正，并加入“findings READY 即放行”和“只有计划、缺 findings 即阻断”的双向测试；当前阶段回归为 `379 passed`。下一断点为 insight → review → validation-only assembly。
- 第五次断点续跑已使 insight 成为 `DECISION_READY`。随后 judgment review 连续三次因五个维度状态大小写错误被拒绝：验证器要求小写，但工具只说“state与basis”，且 judgment 尚未纳入统一同错熔断。运行立即中止；本轮8次调用、83,963个未缓存输入token，无provider重试。
- judgment 现已加入精确结构契约，维度枚举明确为`strong/mixed/weak/not_assessable`，工具 schema 在调用前约束嵌套字段，并进入连续同错熔断；失败尝试与canonical validation分离保存。阶段回归为`382 passed`。下一断点只剩 judgment review → research plan → validation-only assembly。
- 第六次断点续跑中 judgment review 首次即成为`REVIEWED`，随后生成3项有界研究任务；JR002完成了年报`search_report + read_section`回读，但模型两次在complete调用中漏传`task_id`，工具只能返回`task_not_active`。运行中止时JR002仍保持ACTIVE，研究调用和证据身份均保留；本轮15次调用、191,048个未缓存输入token，无provider重试。
- complete工具现可仅在“恰有一个ACTIVE任务”时从执行账本安全补全ID，显式冲突仍拒绝；finding获得完整嵌套schema，重复completion拒绝纳入统一熔断。阶段回归为`384 passed`。下一次从JR002 ACTIVE断点提交finding，随后执行JR003/JR004和最终综合。
- 第七次续跑复用了JR002既有来源调用，并在任务允许范围内根据新证据写回Ch12；第一次complete被正确保留为repairable，指出错误机器source ID、MIXED证据关系不足和chapter_update与实际Ch12变更不一致。随后发现fresh-context恢复器虽保存这些信息却未注入下一提示，运行立即中止；本轮7次调用、143,421个未缓存输入token，无provider重试。
- 恢复器现会注入`last_submission_errors`、合法source ID及工具参数、previous_finding和actual_changes，强制在旧finding上逐项修正。定向回归71项、阶段回归`386 passed`；JR002仍为ACTIVE且Ch12变更已保留。
- 第八次续跑已正确注入恢复包，但provider连续两次漏掉顶层`outcome`；工具级同错熔断虽触发，外层却误把它当作普通上下文耗尽并开启新付费context，运行随即人工中止。本轮5次调用、67,654个未缓存输入token，无provider重试；JR002仍为ACTIVE，之前finding和Ch12 diff未丢失。
- outcome现仅在可由finding.resolution唯一映射时确定性补全并记录inferred；工具级熔断同时向外层真实运行传播，禁止fresh-context复活。阶段回归为`387 passed`。
- 第九次续跑完成JR002、JR003、JR004，三项任务均为`COMPLETE`且零violations；独立综合第二次提交成为`REVIEWED`。validation-only assembly最终诚实返回`INVALID`，没有发布报告。本轮22次调用、228,563个未缓存输入token，无provider重试。
- 最终阻断揭示两个跨阶段缺口：重建decisive plan造成已完成findings指纹漂移；JR002写回Ch12时章节审计未即时检查canonical关键值与decision ID，导致自由GG/II/λ/V_final值及错误绑定拖到assembly才发现。
- 已增加兼容语义身份的确定性findings重绑；语义ID变化仍拒绝。`write_chapter`及研究task completion现在即时检查变更章节的decision绑定并返回精确缺口。阶段回归为`390 passed`。下一次无需重跑三项研究，只需修复completion路由中的Ch12/决策绑定并重新validation-only assembly。
- 第十次续跑真实验证了decisive findings确定性重绑，completion只路由Ch12；但`write_chapter`已经返回19项binding错误时，Agent Loop仍仅按旧audit/depth把该章判为通过并继续来源深化。本轮在首个框架缺陷处中止，共26次调用、326,828个未缓存输入token，无provider重试；候选仍为`INVALID`，未发布。
- 章节通过条件现同时要求工具结果、audit、depth和decision binding全部通过。仅剩decision ledger/compiler身份错误时自动进入binding-only最小修复：关闭年报/网页/计算和账本变更工具，读取精确canonical值与验证错误，只允许最小章节锚点修订；Ch0/Ch14不再误判为只读结构化综合轮。阶段回归为`394 passed`。依照ADR-008，下一次付费续跑须重新批准。
- 第十一次续跑确认binding-only未重新取证，但暴露三项控制流/契约缺口：即时检查漏掉错误D-id，目标通过后没有立即交棒，且模型为了改锚点仍需重输整章。运行在确认缺陷后中止，共21次调用、330,404个未缓存输入token，无provider重试；旧manifest保持`INCOMPLETE`。
- 框架现以确定性程序先删除不支持其值的D-id并补canonical引用；复合`[source:]`中由同一来源引出的分号字段可继承来源身份，但未知文本来源仍阻断；`r*+decay`合计值不再误判为第二个衰减率。binding-only同时实现目标完成即退出、参数级工具限制和研究执行账本保护。
- 格力实际候选经零模型确定性修复后，completion、decision ledger/compiler、absolute quality及全部V3硬门通过；随后用0次LLM调用、0个输入/输出token完成幂等validation-only收口。新run manifest为`COMPLETED`，publication为`VALIDATED_NOT_PUBLISHED`，验收状态进入`READY_FOR_BLIND_REVIEW`，variant=`e5a1ff14f775d183`。当前阶段回归为`403 passed`。
- 该结果完成了Phase 08的A股机器验收子目标，但不自动宣称报告洞见优秀：独立判断上限仍为`COMPETENT`，尚缺两份有效盲评；港股真实validation-only与控制样本冻结条件也仍未完成。

### 2026-08-03 金融街物业港股迁移验收

- 对Phase K候选启用当前全部硬门后，旧`COMPLETE`被诚实重验为`INVALID`：旧账本尚未绑定官方观察、当前估值路由、决定性问题finding及问题身份，另有一项action-changing decision diff等待人工批准。这是契约迁移缺口，不允许把旧完成状态直接继承为新发布资格。
- 首次实跑暴露`repair-only`控制流缺陷：本地重验发现新阻断后仍沿用重验前的`COMPLETE`把修复轮设为0。调度器现只依据最新确定性completion决定是否开放有界修复，并有回归覆盖。
- 真实修复又暴露成本与证据防作弊缺口：模型可穿插调用下游writer逃逸同错熔断，并曾尝试把整体毛利率/在管面积的VERIFIED身份借给商务毛利率、GG和现金主张。框架现按claim→valuation→thesis→decisive→insight只开放首个未通过writer；每个fresh context最多两次提交，非frontier调用累计熔断；直接证据行的每个实质数字必须存在于绑定观察的原文或规范值，复合事实必须拆分。
- 三轮受控实跑均未覆盖canonical claim ledger；只新增两条程序验证观察（FY2025商誉减值18.83M、受限银行存款69.08M）。最近一轮在claim两次失败后自动停止，未进入valuation及后续账本。失败候选与精确验证现会落盘，下一轮可从小上下文修正，不再重复盲试。
- 当前定向回归`64 passed`，阶段测试`351 passed`；验收聚合为1个`READY_FOR_BLIND_REVIEW`、2个`TECHNICALLY_BLOCKED`、1个`NOT_ASSESSABLE`，控制样本仍留置。港股出口尚未完成，且不得以降低证据门或自动批准decision diff换取通过。
- 离线证据平台现新增通用港股披露提取：业务/非业务/多元经营毛利率、归母利润、商誉减值、分红率、现金与受限资金、关联方存款及控股股东身份；括号会计负数和带小数千分位数值均有对抗测试。金融街候选VERIFIED观察由59增至70。
- 新增`claim_evidence_migration.py`：复合旧证据按精确数字、文档年份和业务域拆成原子OBS行；未验证直接支持降为context并写入未解决frontier。脚本只生成candidate/report，不修改冻结canonical账本。金融街candidate已无INVALID，C001/C002/C005获得可复用绑定，实质直接支持缺口仅剩C003/C004/C006。
- `read_structured_ledger_contract(ledger=claim)`现会返回完整现有claim或确定性迁移底稿与未解决frontier，不再只给ID列表迫使fresh-context模型重建主张。本轮阶段回归`353 passed`。
- 本轮未启动DeepSeek：目前验证契约要求所有direct support绑定官方OBS，而C003/C004/C006是`compute_aa`/`compute_gg`派生结果；把计算结果伪装成年报事实或继续付费重试都不合理。下一最小阶段是建立带输入指纹、工具身份和数值支持校验的derived-computation observation，再执行一次有界claim修复。
- 派生计算证据阶段已完成：`computation_evidence.py`仅允许`compute_aa`/`compute_gg`，对每个数值生成绑定输入文件哈希、完整工具输出哈希和路径的`CALC:`身份。claim直接支持必须在官方`OBS:`与派生`CALC:`中二选一；后者必须标记`verified_calculation`，绝不冒充审计披露。输入、工具、数值或产物被篡改均会阻断。
- unified证据预检现会在旧claim缺身份时自动生成迁移候选；仅当候选`REVIEWABLE`、当前账本指纹未变、主张/推理/决策语义逐项不变且每个direct row恰有一个验证身份时，才自动升级冻结账本。
- 01502真实重建生成105条已验证计算观察；C003的净现金、C004的GG/II/HH及输入、C006的GG/II已全部原子绑定。确定性升级后`claim_evidence=DECISION_READY`，0项INVALID、0项INCOMPLETE，未调用DeepSeek，未发布报告。当前completion首要阻断已转移到decisive旧观察身份和valuation route迁移；decision diff批准仍保持人工边界。阶段回归`354 passed`。
- decisive观察迁移审计确认：当前失效ID实际位于`decisive_question_plan.json`，findings尚未生成。旧实现会先覆盖plan再检查findings兼容性，如问题语义改变则旧研究边界无法恢复。现改为candidate-first刷新：只有输入指纹和观察集合变化时才自动替换；问题、机制、信号方向、优先级或决策传导变化时保留旧plan，落盘candidate和差异并要求重新研究。
- 观察集合不再按整个大域全量塞入每个问题；现按机制词过滤owner return、operating transition和cash realization所需事实，避免把无关的已验证数字冒充当前支持/反证。01502三个问题的语义身份全部不变，3个失效旧OBS已清除；decisive状态由`INVALID`收敛为`INCOMPLETE: decisive_question_findings_missing`。这是真实未完成研究，不再是身份技术故障。
- 本阶段未调用DeepSeek、未改估值或决策、未发布报告；阶段回归`356 passed`。依赖frontier下一项是valuation model路由迁移，完成后才允许thesis及decisive findings执行。

### 2026-08-03 金融街物业估值路由保守迁移

- 新增通用`valuation_model_migration.py`并接入统一管线。旧估值账本先生成candidate/report，只补公司原型、route/registry身份、可无歧义绑定的`route_model_id`和路由明确拒绝的模型；不会在迁移中覆盖canonical账本。
- 自动提升必须同时满足：候选估值门为`REVIEWABLE`、没有语义frontier、所有active模型语义与synthesis逐项不变、decision ledger及decision diff指纹不变。模型角色、现金流口径、独立组或折现率类型需要判断时，系统保留旧账本并转入定向估值研究，不用改名伪装兼容。
- `read_structured_ledger_contract(ledger=valuation)`现向后续修复完整暴露迁移candidate、现有synthesis、安全绑定、路由拒绝及语义frontier，并明确禁止把`normalized_earnings`直接改称`normalized_owner_earnings`，或仅为过门改变模型角色。
- 01502真实离线迁移安全绑定了EPV、DDM、RETURN_DECOMPOSITION三个route模型，并在candidate中补记拒绝DCF_FCFF；canonical估值、动作、仓位与两个决策文件均未改变。
- 候选被正确判为`INVALID`，剩余五项估值门失败对应六项显式语义frontier：EPV owner earnings定义；DDM独立组口径；RETURN_DECOMPOSITION的primary/stress角色、独立组、owner-return口径和required-return类型。这些是需要证据和模型判断的真实研究问题，不再属于机械迁移。
- canonical不变性已由指纹复核：`valuation_model.json=d2da1439…09633`、`decision_ledger.json=3bb442d1…e475`、`decision_diff.json=26e35b19…2873`。定向估值/路由测试`48 passed`，全部`tests/test_stage*.py`为`361 passed`；未调用DeepSeek，未发布报告。
- 因此估值身份迁移工作包已完成，但01502 valuation gate仍保持`INVALID`。Phase 08下一最小工作包是一次有预算上限的定向估值研究/修复，先解决owner earnings定义和RETURN_DECOMPOSITION角色，再重验valuation；通过后才按依赖顺序进入thesis和decisive findings。

### 2026-08-03 估值定向实跑的结构化边界修复

- 本次真实run经批准后采用单个fresh context、最多12次LLM调用、估算2.4分钟、validation-only且关闭来源泛搜；预定在同一frontier两次失败、无进展或首个新框架缺陷时立即停止。
- 运行正确识别valuation语义frontier并保留canonical账本，但调度器把下游`Quality hard contract: failure in Ch0,Ch14`误认成正文阻断，导致本应为`synthesis_only`的轮次开放了`write_chapter`。模型在第9次调用越界重写Ch14，尚未提交valuation ledger；运行随即人工中止，共9次调用、90,236个未缓存输入token，无provider重试、未发布。
- Ch14已从本次运行前的最新draft快照机械恢复，失败版本保存在`/tmp/01502_ch14_failed_20260803_1800.md`供审计；恢复章重新审计为0 error。canonical `valuation_model.json`、`decision_ledger.json`及`decision_diff.json`的SHA-256与运行前完全一致。
- 调度器新增结构化frontier优先判定：只要claim→valuation→thesis→decisive→insight任一账本未通过，且修复目标只含Ch0/Ch14，就必须保持`synthesis_only`并硬冻结正文。只有全部结构化账本通过后，真实Ch0/Ch14章节阻断才允许重新开放正文写作。
- 新增正反对抗测试覆盖“估值INVALID时即使质量门提到Ch0/Ch14也冻结正文”和“结构化账本全通过后真实Ch14深度失败可重开正文”。相关回归`115 passed`，全部`tests/test_stage*.py`为`363 passed`。
- 本次已使用一次真实基线额度且在首个框架缺陷处停止，依照ADR-008不得在同一工作包自动重试。下一断点仍是valuation writer；重新启动前须获得新的昂贵运行批准，运行上限继续限制为单context/12次调用。

### 2026-08-03 估值语义研究防伪门

- 经重新批准的单context run正确保持`synthesis_only`，Ch0/Ch14未被改写；valuation writer在第2次调用一次提交并被旧validator判为`DECISION_READY`，估值结果、区间、动作和仓位表面保持不变。
- 质量审计否决了该结果：提交内容只是逐项把`normalized_earnings`改名为`normalized_owner_earnings`、把分组名称改成route词汇，并将RETURN_DECOMPOSITION从stress改为primary；没有建立owner earnings定义、现金可得性证据或模型角色为何改变的研究链。这证明“路由一致”仍可被机械改字段伪造。
- 假通过账本和diff已保存在`/tmp/01502_valuation_fake_pass_20260803.json`及对应diff供审计；canonical估值已由运行前candidate可逆重建，字节级恢复SHA-256 `d2da1439…09633`。decision ledger、decision diff及Ch14哈希未变，报告未发布。
- 新增`valuation-semantic-research`硬门：每项semantic frontier必须提交一条精确resolution，包含VERIFIED `OBS:`/`CALC:`、研究依据、机制、估值影响和决策影响；必须恰好覆盖全部frontier。owner earnings要求`compute_aa`及官方所有者利润/现金事实，owner return及RETURN_DECOMPOSITION主锚要求`compute_gg`和官方分配/治理事实，DDM distribution要求官方分红证据。
- 防伪门以deterministic migration candidate为变更白名单：除已声明frontier外，任何active模型、结果、假设、synthesis、动作或仓位变化均在写canonical前拒绝。失败稿重放现稳定返回六项`semantic_resolution_missing`，不会覆盖旧账本。
- 同一context随后前进到thesis时还暴露嵌套类型异常：畸形字符串导致`'str' object has no attribute 'get'`。validator已增加概率集和flip condition类型守卫，错误参数现在返回精确INVALID findings而非Python异常。
- 本次manifest记录8个完成调用、194,007个未缓存输入token、0次provider重试，状态`INCOMPLETE/NOT_PUBLISHED`。相关回归`103 passed`，全部`tests/test_stage*.py`为`367 passed`。
- 当前valuation仍为`INVALID`是有意结果。下一次真实run必须在精确工具schema下提交六项证据支持的semantic resolutions；再次启动仍需新的明确批准，禁止恢复已否决的假通过账本。

### 2026-08-03 估值语义证据上下文与第三次有界实跑

- 实跑前确认valuation契约虽列出70个VERIFIED观察ID，却没有暴露这些ID的事实身份，也没有暴露`compute_aa/compute_gg`的CALC身份。框架新增紧凑`semantic_research_evidence`：只给出与六项frontier直接相关的官方所有者利润、现金、受限现金、分红、资本配置、治理事实及AA/GG确定性计算，避免模型靠猜ID或重新泛搜。
- 预检确认六项frontier、42条相关官方观察、33条相关计算均可见，Ch0/Ch14保持`synthesis_only`，五个canonical文件哈希与基线一致。经明确批准后启动单context、最多12次调用、估算2.4分钟的validation-only修复。
- 第一次提交完整覆盖六项resolution，但四项无证据、EPV缺少AA与官方所有者现金联合证据，并包含越界模型变更；防伪门正确拒绝且未覆盖canonical。
- 模型随后调用`compute_aa/compute_gg`并修复。第二次提交的六项resolution已全部绑定VERIFIED证据，越界模型变更消失；仍因M003只填写`discount_rate.kind`而缺`value_pct/tax_basis/inflation_basis`，以及四条估值/决策影响仅写“无变化”而被拒绝。后者属于有效质量拒绝，前者暴露迁移任务没有就地明示完整伴随字段。
- 同错熔断在第二次writer失败后自动终止，共6次调用、83,190个未缓存输入token、0次provider重试，未继续消耗至12次上限。估值、decision ledger、decision diff、Ch14及thesis哈希全部未变，报告未发布。
- valuation契约现紧邻migration candidate明示required-return完整对象规则：`value_pct`必须等于既有`required_return_pct`，`tax_basis`必须等于模型basis，`inflation_basis`必须为有依据的nominal/real；只提交kind必定失败。短而空洞的“无变化”仍不放宽，必须说明为何不改变既有估值和动作。
- 当前下一断点仍是同一valuation writer，而非进入thesis或decisive。再次真实运行必须重新取得批准；预期只修复完整discount-rate对象和四条影响链，仍不得改变模型结果、synthesis、动作、仓位或待人工批准的decision diff。

### 2026-08-03 估值语义第四次实跑与跨运行恢复包

- 新批准的单context运行继续保持12次调用上限和Ch0/Ch14只读边界。第一次提交因证据组合不足、短影响说明及模型/synthesis越界被拒；第二次提交已消除全部INVALID，只剩3项INCOMPLETE：M003 cash-flow scope的估值/决策影响说明过短，以及independence group缺`compute_gg + 官方分配/治理`联合证据。
- 同错熔断在第二次writer失败后停止，共6次调用、52,971个未缓存输入token、0次provider重试。五个canonical哈希均与基线一致，报告未发布。
- 与上一轮对照发现fresh context会忽略磁盘上的最佳拒绝稿并重新构造全部六项resolution，造成已解决问题跨运行回归。该问题属于通用structured-writer恢复缺口，不是01502单例内容问题。
- valuation契约现暴露`rejected_research_resume`：仅在frontier键完全一致、source ledger未漂移时，返回最近/最佳拒绝candidate、全部resolution和精确validation findings；明确要求保留已有效证据与文本，只修listed findings，且所有内容仍会被完整重验，不能借恢复包获得权威。
- writer新增`valuation_semantic_resolution_best_rejected.json`，按INVALID数量、缺失frontier数量、总INCOMPLETE数量和VERIFIED证据覆盖择优保存；后续较差提交不得覆盖更接近通过的研究底稿。兼容旧last-rejected文件时会绑定同次semantic candidate，但它仍只是可丢弃草稿。
- 阶段回归为`369 passed`。下一次仍从valuation writer继续，理论最小修复已收敛为一条联合证据和两条有理由的影响说明；再次真实运行需重新批准。

### 2026-08-03 估值语义第五次实跑与补丁式提交

- 经新批准继续同一valuation断点。契约成功暴露最佳拒绝稿，模型读取后只调用`compute_gg`并核对估值章节，没有泛搜或改写正文。
- 第一次writer调用却为空payload；第二次带回完整candidate但仅提交3条resolution。两次均被全量替换接口正确拒绝，同错熔断在第5个完成调用停止；本轮未缓存输入37,870 tokens、0次provider重试，canonical与正文哈希全部未变。
- `valuation_semantic_resolution_best_rejected.json`保护机制通过真实验证：本轮空稿和3行退化稿没有覆盖上一轮`0 INVALID / 3 INCOMPLETE / 6 resolutions`的最佳研究底稿。
- 根因是恢复提示要求“只修listed findings”，而原writer仍要求调用方重传完整candidate和全部6行，接口语义相互冲突。模型的partial submission不应被当作完整替换，也不应迫使重复输出已验证的大对象。
- `write_valuation_model_ledger`现支持`resume_best_rejected=true + semantic_resolution_patches`：程序验证source ledger和frontier身份，从最佳非canonical稿恢复candidate，以`(model_id, field)`确定性合并仅有的修正行，再对全部模型、synthesis和六项resolution执行原有完整防伪验证。越界patch、陈旧底稿或身份不全仍失败关闭。
- valuation契约和工具schema均给出精确调用方式，明确patch模式不重传company profile/models/synthesis。阶段回归`370 passed`。下一次真实运行只需提交当前3项对应的完整resolution patch；仍须重新批准。

### 2026-08-03 估值语义第六次实跑通过

- 经新批准验证补丁式writer。模型读取最佳稿和路由后，只补充核对官方证据及估值章节；第3次LLM调用提交patch，`write_valuation_model_ledger`首次即`written=true`。六项semantic resolution达到`REVIEWABLE/PASS`，0项INVALID、0项INCOMPLETE，8个VERIFIED OBS/CALC身份被完整保留。
- 本轮共3次调用、44,303个未缓存输入token、0次provider重试。为避免同一context自动扩展到thesis，valuation写入成功后人工停止；Ch0/Ch14、decision ledger、decision diff及旧thesis均未被改写。
- 停止时点早于模型的第二阶段freeze调用，导致账本暂为REVIEWABLE。随后用确定性`promote_reviewable_valuation_model`完成冻结；valuation现为`DECISION_READY/PASS`，仅保留非阻断警告`M001:fragile_primary_model`。
- 生命周期审计同时发现semantic resolution凭证原本绑定冻结前fingerprint。promotion现仅在旧凭证确实匹配冻结前账本且semantic validation为REVIEWABLE时，同步为冻结后fingerprint；不匹配或陈旧凭证不会被自动重绑。当前valuation freeze fingerprint与semantic resolution fingerprint完全一致。
- 重算completion后，valuation阻断已消失。真实剩余顺序为：thesis旧`resolution_due`无效、decisive findings缺失、insight旧question identity缺失；action-changing decision diff仍等待人工批准，框架没有绕过。阶段回归`370 passed`。
- 至此01502估值路由迁移与语义研究工作包完成。下一阶段转入thesis candidate-first迁移/修复，不再继续重跑valuation。

### 2026-08-03 Thesis candidate-first 截止日迁移

- 审计旧thesis发现两个竞争解释、5个阈值、PS001三情景概率、翻转后的估值/仓位/动作及全部正文锚点均通过；唯一错误是旧PS001没有`resolution_due`。因此没有调用DeepSeek重写整套论文测试。
- 新增通用`thesis_test_migration.py`。迁移先生成candidate/report，canonical保持不变；只有空缺截止日、所有estimate `as_of`与报告`period_end`一致、报告口径受支持且不存在其他INVALID/INCOMPLETE时，才允许按下一可比披露窗口确定性补齐。annual报告映射到下一中报期末后三个月，interim报告映射到下一年报期末后四个月。
- 竞争解释、替代证据、区分观察、阈值、概率值/区间、估值、仓位、动作和decision IDs全部属于protected semantics。任何非截止日变化、旧账本其他验证错误、预测as-of漂移、未知报告口径，均落入semantic frontier并禁止自动覆盖。
- promotion同时绑定source thesis SHA/fingerprint、decision ledger SHA和valuation model SHA；任一依赖在candidate生成后变化即拒绝。迁移已接入unified pipeline，但只在valuation为`DECISION_READY/MONITORING`时运行，并具备已兼容账本的幂等no-op。
- 01502实际candidate仅新增`PS001.resolution_due=2026-09-30`，依据`next_interim_period_end_plus_three_months`；candidate为`REVIEWABLE`且semantic frontier为空。零模型promotion后thesis达到`DECISION_READY/PASS`，decision、valuation、decision diff及Ch14哈希不变。
- 重算completion由`INVALID`降为`INCOMPLETE`，thesis阻断消失；剩余为decisive findings缺失、旧insight question identity缺失及decision diff待人工批准。阶段回归`375 passed`。下一依赖frontier正式转为3个decisive findings的有界执行。

### 2026-08-03 决定性问题首轮实跑与估值迁移幂等修复

- 经批准启动3个decisive findings的单context有界运行，上限12次调用、关闭来源深化，并约定首个新框架缺陷立即停止。模型完成2次调用后已进入第三次计算读取，但尚未提交findings；人工中止后的manifest记录2次完成调用、30,216个未缓存输入token、0次provider重试。没有生成`decisive_question_findings.json`，没有改章节、决策账本或decision diff，也没有发布报告。
- 停止原因是统一管线在已经兼容的估值账本上仍重复执行route-identity promotion。虽然估值结果、synthesis和动作未变，但生命周期时间戳会改变估值身份并迫使decisive plan重复刷新，违反迁移幂等要求；同时“无需迁移”分支会误打印成存在估值语义frontier。
- `valuation_model_migration.py`现以排除生命周期/时间戳/freeze元数据的迁移主体判断`migration_required`；已兼容账本返回`already_compatible`且不再promotion。只有凭证精确绑定旧估值fingerprint且仍为REVIEWABLE时，才允许在首次安全迁移后同步semantic-resolution fingerprint。运行器仅在确有迁移时提升，只有真实semantic frontier才打印阻断提示。
- 对01502连续复验确认：估值文件SHA-256稳定为`b71d8cbe…dd5c`，valuation fingerprint与semantic resolution完全一致；decisive plan连续输入fingerprint稳定为`abe15c80…16a7`。计划文件的审计时间戳可更新，但findings只绑定稳定输入fingerprint，不会形成研究身份漂移。
- 全部阶段回归现为`376 passed`。按ADR-008，本次批准额度已被一次真实基线使用且在首个框架缺陷处停止；下一次仍从3个decisive findings开始，但必须取得新的明确付费运行批准，不能在本工作包自动重试。

### 2026-08-03 决定性问题第二轮实跑与路由依赖环修复

- 新批准的有界运行在预检时确认decisive输入fingerprint为`abe15c80…16a7`，但统一管线启动后变为`1147c51e…1654`。模型完成2次调用、进入第三次读取但尚未提交findings时，运行按首个框架缺陷立即中止。manifest记录41,878个未缓存输入token、0次provider重试；没有生成findings、改正文、改估值/thesis/决策或发布报告。
- 根因并非估值账本再次迁移，而是valuation routing把下游`decisive_question_plan.json`纳入公司原型输入，同时decisive plan又依赖公司原型和估值路由，形成`plan → archetype → route → plan`反向依赖环。官方证据重建还会刷新`report_context.meta.generated_at`，旧routing hash把该时间戳误当作研究输入变化。
- 公司原型现只依赖其实际使用的上游文件，删除对下游decisive plan的输入与路径映射；`report_context.json`直接绑定证据平台已有的稳定`meta.context_fingerprint`。事实、行业身份、计算和估值路由的真实变化仍会改变指纹，只有运行时间戳和下游派生产物不再反向污染身份。
- 完整上游链以不同run ID连续重建两次，decisive输入fingerprint均为`b6c1734e…750`，逐文件输入源零差异。canonical估值、thesis、decision ledger、decision diff及Ch14哈希均与运行前一致；completion仍诚实为`INCOMPLETE`，阻断未变。
- 全部阶段回归现为`377 passed`。本次付费批准已消耗，下一frontier仍是同3个decisive findings；再次真实执行须取得新的明确批准。

### 2026-08-03 决定性问题第三轮实跑与空账本伪成功修复

- 启动前以真实管线顺序执行两次完整确定性预检，decisive fingerprint均为`b6c1734e…750`、逐文件零漂移、五个canonical哈希不变；第三轮真实运行启动后读取到同一fingerprint，证明前两轮身份漂移缺陷已经关闭。
- 第2次LLM调用耗时129秒并调用`write_decisive_question_findings`，工具返回`written=true`；运行按“findings写入即停止”在第3次调用开始时人工中止。独立验收发现实际payload为`findings: []`，validation是`INCOMPLETE`且三个问题均`research_task_not_completed`。本轮共2次完成调用、41,268个未缓存输入token、0次provider重试。
- 根因是persist层只拒绝`INVALID`，错误地允许`INCOMPLETE`覆盖canonical并返回成功；工具schema也没有禁止空数组。这会让控制流把“成功保存失败对象”误认成研究完成，是发布生命周期缺陷，不是文字质量问题。
- persist层现仅允许`DECISION_READY`写入canonical并返回`written=true`；`INVALID`和`INCOMPLETE`都只写`decisive_question_findings_last_attempt.json`及独立validation，保留精确失败稿但不获得权威。工具schema新增`minItems=1`，空数组会在进入writer前被拒绝。
- 本轮错误空canonical已转存为last-attempt审计并从canonical位置移除；估值、thesis、decision ledger、decision diff及Ch14哈希未变，报告未发布。全部阶段回归`378 passed`。
- 下一frontier仍是3个decisive findings；后续模型必须提交覆盖全部入选问题且通过验证的数组，才能进入`DECISION_READY`。本次批准已消耗，再次真实运行仍需明确批准。

### 2026-08-03 决定性问题第四轮实跑与主张支持硬门

- 启动前确认最终provider schema已包含`findings.minItems=1`和全部嵌套必填字段；真实运行读取稳定fingerprint `b6c1734e…750`。模型在第4次调用提交3条非空finding，旧结构validator给出`DECISION_READY`；输出到达时第5次调用已完成、第6次刚开始，运行立即中止。本轮manifest记录5次完成调用、106,701个未缓存输入token、0次provider重试。
- 独立质量审计否决该结构通过。明确错误包括把FY2023–2025 DPS `0.173→0.157→0.145`写成“稳定在0.145”；用最高利息4.43M除以最高每日余额373.77M推成年化1.19%，分子分母时点口径不匹配；把维持性Capex约70.6M与实际Capex约11M并列后仍称后者为“最保守口径”。另有分部面积、单位物业费、指导价约束、不可逆性和多个推导比率未绑定直接OBS/CALC。
- 这暴露了V3审计意见所指出的核心风险：全局堆放一批真实OBS只能证明“来源存在”，不能证明某一信号中的每个数字和推断由这些来源支持。原validator只校验OBS身份存在，无法阻止真实来源替错误句子背书。
- decisive finding契约现新增`evidence_calculation_ids`，每个signal必须单独提交`evidence_ids`。硬门逐信号检查：身份必须在该finding声明且VERIFIED；每个实质数字必须直接出现在对应OBS原文/规范值或精确CALC值中；派生数字没有CALC身份即拒绝。解释basis、估值/仓位/动作影响和结论中的数字还会与本finding证据及canonical decision/valuation/thesis交叉核对。
- 该稿在新门下稳定返回15项INVALID和6项INCOMPLETE，已转存为非权威last-attempt并移除canonical身份。契约仅在plan fingerprint一致时暴露`rejected_research_resume`，下一fresh context可保留被支持部分、删除错误推导并补逐信号证据，不必从零重写；失败稿仍无权威且必须全量重验。
- canonical估值、thesis、decision ledger、decision diff及Ch14哈希未变，报告未发布；completion仍为`INCOMPLETE`。全部阶段回归`379 passed`。下一frontier仍是3个findings的证据约束修订，本次批准已消耗。

### 2026-08-03 决定性问题第五轮实跑与计算身份可用性

- 新批准运行正确读取同fingerprint恢复包，并只调用`compute_gg`、`compute_aa`和`compute_ddm`核对数值，没有来源泛搜、正文写入或下游writer。两次完整findings提交均被主张支持硬门拒绝，同错熔断在第4次完成调用后自动停止；manifest为`FAILED`，57,759个未缓存输入token、0次provider重试。
- 拒绝结果证明硬门没有误放：模型把指标名和值拼成`CALC:compute_gg:gg_base=6.2`等可读字符串，而真实防篡改身份是`CALC:befd4568…`；还引用不在allow-list的`compute_ddm`、裸`CALC:compute_aa`及临时算式`CALC:4.43/373.77=1.19%`。这些均不得冒充验证计算。候选仍保留上一轮的利率口径错误、无证据治理断言和面积/费率推导，并将维持性Capex写成70.6M，而真实`compute_gg`值为102.19M。
- 根因是计算证据可见但可用性差：decisive契约原样暴露105条CALC，未强调ID必须复制不透明哈希，模型转而自造可读别名。契约现压缩为31条与现金、AA、GG、II、Capex直接相关的精确查找表，并明确禁止可读别名、裸工具名和非allow-list计算；验证仍只接受原始哈希身份。
- 数字支持器同时修复一个离线发现的假失败边界：先剥离`OBS:`/`CALC:`身份再提取研究数字，避免把以数字开头的哈希片段误当成主张数值；真实正文数字仍逐项核验。
- 最新三问题稿继续作为同fingerprint非权威恢复候选，canonical findings保持缺失。估值、thesis、decision ledger、decision diff和Ch14哈希不变，completion仍为`INCOMPLETE`，未发布报告。全部阶段回归`381 passed`。下一frontier仍是使用31条精确CALC映射修订三问题稿，本次批准已消耗。

### 2026-08-03 决定性问题第六轮实跑与最佳失败稿保护

- 启动前确认31条decisive CALC均为精确`CALC:<24位哈希>`、恢复包与plan fingerprint一致。真实运行只读取契约/计划/证据，没有搜索、重新计算、正文或下游调用。第一次大对象提交被硬门拒绝；第二次提交退化为`findings: []`，writer正确返回`INCOMPLETE`，同错熔断在第3次完成调用后停止。manifest为`FAILED`，56,921个未缓存输入token、0次provider重试。
- 本轮暴露的是失败稿生命周期缺口：`last_attempt`按时间覆盖，第二次空稿抹掉了第一次更完整的研究稿。虽然没有污染canonical，但会让下一fresh context失去更接近通过的底稿，重复消耗上下文。运行缓存和审计目录未保留第一次payload，无法安全恢复，因此没有凭记忆手工重建单例报告。
- decisive writer现新增`best_rejected`择优保存，排序首先最小化缺失问题数，其次最小化INVALID数和INCOMPLETE数；完整但有错的三问题稿优先于零错误表象的空稿。plan fingerprint变化时旧best不得参与比较或恢复。`last_attempt`继续保留最新诊断，恢复契约优先读取同fingerprint `best_rejected`并标明来源。
- 对抗测试已验证：先提交覆盖全部问题但有一项类型错误的候选，再提交空数组，best仍保留完整候选，契约恢复3/3问题。全部阶段回归`382 passed`。
- 当前真实输出因保护机制部署在运行结束后，只有空last-attempt而无可恢复best；canonical findings仍缺失。估值、thesis、decision ledger、decision diff和Ch14哈希不变，completion仍为`INCOMPLETE`，未发布报告。下一运行须重新生成一次完整候选，但从那以后退化稿不再能覆盖研究进展；本次批准已消耗。

### 2026-08-03 决定性问题第七轮实跑与精确缺数诊断

- 本轮从空恢复稿重建完整候选：先在本地2025年报回读受限存款、分红、资本开支和非商务毛利率原因，再核对financial trends与AA；没有网页搜索、正文写入或下游writer。两次提交均被硬门拒绝，同错熔断在第6次完成调用后停止。manifest为`FAILED`，63,244个未缓存输入token、0次provider重试。
- `best_rejected`首次通过真实运行验证：第一次3/3候选被保存，第二次提交未能覆盖它；最佳稿当前为0个缺失问题、13项INVALID、0项INCOMPLETE。canonical findings保持缺失，恢复契约可在下一fresh context直接读取完整3条。
- 逐数字复核发现两项硬门误报：官方规范值1509.025M/117.166M按报告精度写成1509.03M/117.17M被精确比较拒绝；“年报p.26”的页码被当成事实数字。数字支持器现允许最大0.00501的展示舍入，并在解析前去除`p.26`/`第82页`页码；不影响差额、比率、阈值和口径错误的拒绝。重验后分红治理signal通过，INVALID由14降至13。
- 其余13项均为真实未支持内容，包括受限存款54.09/14.99M分项、490.94M与28.9%聚合、1.19%错误利率、NAV 4.04、临时60%/7%/8.5%/14.5%阈值、Capex/D&A错误身份及无CALC的变化差额。
- validator现在把精确缺数写入finding，例如`unsupported=54.09|14.99`，不再只返回笼统`numeric_support_mismatch`；同一best payload在validator升级后可刷新诊断而不改变候选。全部阶段回归`383 passed`。
- canonical估值、thesis、decision ledger、decision diff和Ch14哈希未变，completion仍为`INCOMPLETE`且报告未发布。下一frontier是按13条精确缺数删除无支持数字或补合法OBS/CALC，本次批准已消耗。

### 2026-08-03 决定性问题第八轮实跑与逐引用语义校准门

- 新批准运行复用3/3最佳失败稿，只读取计划、证据和AA/GG计算；第4次完成调用提交候选并被旧门判为`DECISION_READY`，第5次调用开始后立即人工中止。manifest准确记录4次完成调用、64,366个未缓存输入token、0次provider重试；未进入insight、正文或发布。
- 独立研究审计再次否决机器表面通过：`Normalized GG=6.2%`紧邻引用的`CALC:061512…`实际是`aa_norm_3y=96.92M`，只是同段另一个CALC恰好为6.2而被集合式数字对账借用；利息4.43M与Rf 4.0%被直接比较，量纲错误；11.24M全额Capex与102.19M维持性Capex并列后仍称“均远低于折旧”，逻辑不成立；“唯一、排除、确保、充分折价、控制所有重大决策”等绝对断言没有绑定能直接支持其强度的证据。决策影响还引用GG 6.2%、FCFE 8.0%和回报安全边际-2.7pct，却没有绑定对应D002/D003/D011。
- decisive gate现新增逐引用数字身份核对：每个紧邻`[OBS/CALC:id]`的显示数字必须由该ID自身支持，不能再从同段证据池借数。新增量纲比较守卫，金额与百分比的高低比较直接拒绝；新增校准门，绝对化断言必须在绑定原始证据中有直接表述，否则降为INVALID；`decision_entry_ids`必须是active且决策文字中出现的canonical数值必须绑定至少一个对应entry。
- 计算观察的单位推断同时修复：`gg_normalized.maintenance_capex/full_capex_3y/aa_norm_3y`等金额不再因路径包含`gg_`被误标为`pct_or_pct_point`；GG、II、HH仍保留百分比身份。canonical重新验证为16项INVALID，读取工具在validation非`DECISION_READY/MONITORING`时不再向下游暴露研究finding；动态重验会同步刷新findings validation，避免旧PASS文件静默残留。
- 本轮没有再次调用DeepSeek修稿。完整阶段回归为`453 passed`。Phase 08仍为VALIDATING，报告未发布；下一frontier仍是同3个finding的补丁式语义修订，重点是正确CALC身份、单位一致性、弱化无证据绝对断言、保留真实不确定性并绑定正确decision entries。再次真实运行须重新明确批准。

### 2026-08-03 决定性问题第九轮实跑、补丁恢复与推断披露门

- 付费运行前先修复恢复排序：旧`best_rejected`仍携带旧验证器的5项错误分数，但当前重验实际为21项，导致较新的16项候选无法成为恢复真源。persist现每次比较前都用当前validator重验best并刷新诊断；最新候选因此正确成为恢复底稿。decisive writer同时新增`resume_best_rejected=true + finding_patches`，只按精确question_id替换指定顶层字段，禁止新增问题/越界字段，合并后仍对全部3个finding全量重验。
- 新批准运行上限8次调用。模型读取恢复包后定向回读有息负债、抵押、回购及财务报表；第8次调用首次提交补丁，writer正常合并但返回`INVALID`，管线按上限停止，没有自动加轮。manifest记录8次完成调用、50,786个未缓存输入token、0次provider重试；未进入insight或发布。
- 补丁在旧语义门下把错误从16项降到9项，正确修复了Normalized GG的CALC身份和D002/D003/D004/D011绑定，但仍把`4.43M÷373.771M=1.19%`当成年化利率，继续混用年度最高利息与期末/最高余额；还把搜索`0 hits`写成“无负债/无抵押/无回购”的事实，并保留“无法用周期解释、结构性驱动、真实且可持续、理论上可分配”等未由原始证据直接陈述的因果判断。maintenance Capex段还引用未声明OBS/CALC及旧D&A 83.16M，且与102.19M维持性Capex自相矛盾。
- 这证明仅扩充绝对词表会重演V2的正则游戏。新门改查推断身份：零搜索命中不得证明不存在；文档未披露必须标记`[negative-evidence]`，非原始来源直接陈述的因果/解释性判断必须标记`[inference]`，两者都必须在`unresolved`保留具体待验证问题。它不声称自动证明因果正确，只确保事实、计算、推断和负面证据不会被混成同一证据等级。
- 最新最佳失败稿按新门为23项INVALID、0项INCOMPLETE；增加的项目是原先隐藏的推断身份，而非报告退化。canonical decisive gate仍为`INVALID`，下游不读取该稿；估值、thesis、decision、decision diff和Ch14哈希保持不变。完整阶段回归`458 passed`。本次批准已消耗，下一frontier仍为同一best稿的字段补丁：删除伪年化率和0-hit事实，纠正Capex逻辑及声明身份，并把必要推断显式降级、填写未决验证项；再次实跑须重新批准。

### 2026-08-03 决定性问题第十轮实跑与结构化推断审计

- 运行前给恢复契约增加确定性`local_patch_no_new_research`路由：当错误只涉及数字/身份/量纲/推断披露且没有研究缺口时，明确禁止search_report、read_section、财务趋势和Web搜索，要求立即提交finding patches。离线回归后启动最多6次调用的真实run。
- 模型第3次和第4次调用各提交一次补丁。第二稿把23项旧门错误收敛到4项，删除伪年化率、0-hit事实、无身份数字和错误Capex/D&A比较，并保留对应unresolved；同错熔断在第4次完成调用后停止，没有消耗剩余2次上限。manifest记录66,983个未缓存输入token、0次provider重试，未进入insight或发布。
- 剩余4项首先暴露标签语法假失败：模型使用`[inference: 理由]`，旧解析器只认字面`[inference]`。但独立审计不允许仅放宽语法就获得DECISION_READY：稿件仍把“商誉减值比Capex更威胁GG”“四年趋势证明结构恶化”“非商务恶化驱动3.2%衰减”等有争议推断贴标签后直接使用，且operating confidence从0.68升到0.85。披露推断身份不等于证明推断有效。
- inference gate现升级为结构化审计。正文必须使用`[inference:I001]`；每个ID要有`inference_audit`，包括claim、已声明VERIFIED evidence、最强替代解释、区分观察和判断错误时的决策影响。裸标签、多义标签、未知ID或无证据audit全部失败关闭；存在推断时`confidence_after`相对before最多上调0.05，仍须保留具体unresolved。`[inference:自由理由]`现在被识别为标签而非“未标注”，但不会冒充正式审计ID。
- 当前best在新结构门下为13项INVALID、3项INCOMPLETE，恢复路由仍为`local_patch_no_new_research`；这些主要是把自由理由迁移为少量正式inference audit及降低operating confidence，不需要重新搜索。canonical decisive gate仍INVALID，五个核心哈希保持不变。完整阶段回归`460 passed`。本次批准已消耗，下一run须重新批准。

### 2026-08-03 决定性问题第十一次实跑、成功停点与前提结算门

- 新批准run最多5次调用。第2次提交完成三问题inference audit但仍有局部错误；第3次补丁首次使旧门达到`DECISION_READY/written=true`。模型随后在第4–5次开始读取judgment/insight契约，直到迭代上限才停；manifest记录5次完成调用、150,788个未缓存输入token、0次provider重试，报告仍因下游未完成而INCOMPLETE，未发布。
- 控制流缺陷已离线修复：synthesis-only pass在启动时冻结唯一initial structured frontier；该writer首次`written=true`且validation为`DECISION_READY/MONITORING`后设置`frontier_completed`，主循环在同一tool batch后立即停止，不再自动扩张到下一账本。回归测试直接验证decisive成功后不会继续insight。
- 独立审计没有因旧门通过而接受候选。owner-return问题的计划敏感前提明确包括`gg_discounted=5.3%`与`II=5.5%`，正文却只用AA 6.2%、FCFE 8.0%和Normalized 6.2%得出“三种口径均跨越”，没有裁决决定动作的折价口径；现金问题也未结算31.8年分红覆盖，经营问题未结算收入+14.14%、利润-7.51%及lambda不稳定。这是问题选择与最终结论脱节，不是推断标签格式问题。
- decisive finding现条件性要求`resolution_assessment`：逐项覆盖plan `sensitivity_basis`的每个scalar leaf，复制plan_value，绑定证据，并标`SUPPORTS_A/SUPPORTS_B/NEUTRAL/UNKNOWN`；A和B同时出现时`net_support`必须为MIXED，UNKNOWN或INSUFFICIENT不得以RESOLVED收口，同时必须说明decision consistency。
- 为避免这些计划前提再次成为无身份数字，`calculation_observations`新增`decisive_plan`确定性来源。当前11个敏感前提均获得稳定opaque CALC身份，包括31.8年、折价GG 5.3%、误差区间5.6–7.6、收入/利润增长及categorical `lambda_reliability=unstable`；不改变原105个计算ID，当前总计116项VERIFIED。计划落盘后会自动刷新这些身份，契约只在同plan fingerprint下暴露。
- 旧canonical按新门降为`INCOMPLETE`：0 INVALID、14 INCOMPLETE（3个assessment及11个premise row缺失），并成为最佳可恢复稿；路由为`local_patch_no_new_research`。这不是内容回退，而是阻止“回答了容易的口径、跳过真正翻转决策的前提”获得权威。五个核心哈希和decisive fingerprint不变。完整阶段回归`464 passed`，本次批准已消耗；下一run只需补3个resolution assessment，不得搜索，须重新批准。

### 2026-08-03 决定性问题第十二次实跑与前提诊断语义门

- 新批准run上限4次调用且禁止搜索。模型第2次调用提交的assessment被旧门拒绝，第3次调用写入成功；`frontier_completed`在同一tool batch立即停止，没有进入insight、judgment或正文。manifest记录3次完成调用、49,107个未缓存输入token、0次provider重试，证明“目标writer成功即停”已通过真实运行。外层因decision diff尚待人工批准及insight缺question identity保持`INCOMPLETE`，报告未发布。
- 独立审计再次否决机器表面`DECISION_READY`。现金问题把31.8年分红覆盖判为支持“合理时间兑现”，混淆了支付能力与分配意愿；又把净现金/市值244.6%判为支持“现金受控”，理由是市场深度折价，形成以价格反推现金可达性的循环论证。多个premise row也未引用此前为其建立的唯一`decisive_plan` CALC，而是用同值旧计算替代前提身份。
- plan现为每个scalar premise生成`premise_assessment_policy`，明确诊断角色、解释规则、允许方向及唯一前提CALC要求。现金规模只能说明研究重要性，不能单独裁决可达或受控；高分红覆盖年数不得因“支付能力充足”判为支持快速兑现；折价GG低于II不得支持A，II本身及单独收入增速只能是中性标尺/信号。finding validator逐项要求metric path、plan value及opaque CALC身份完全一致，并拒绝违反plan policy的方向。
- 兼容plan fingerprint刷新会确定性重绑旧/新premise CALC，无需模型改写；validator升级导致旧canonical降级时，会把完整稿保存为非权威repair frontier。best-rejected排序改为先保证问题覆盖，再最小化总修补数，避免退回缺少全部assessment的旧稿；恢复契约新增premise本地修补说明，仍禁止搜索。
- 新门已在真实输出复现人工结论：当前稿自动降为`INVALID`，精确剩余6项（现金2项方向错误、现金1项及owner-return 3项缺唯一前提CALC），恢复源为最新3/3完整稿，模式`local_patch_no_new_research`。估值、thesis、decision ledger、decision diff及Ch14五个核心哈希不变；阶段回归`467 passed`。本次付费批准已消耗，下一run只允许修这6个本地字段，须重新明确批准。

### 2026-08-03 决定性问题第十三至十四次实跑与assessment证据闭环

- 操作人改为持续付费授权；框架仍在每次运行前公开调用上限和停点。第十三次run上限4次、零搜索，第3次调用把旧6项修至旧门`DECISION_READY`并立即停点；manifest记录3次调用、64,104个未缓存输入token、0次provider重试。外层仍因decision diff与insight阻断而未发布。
- 独立审计发现`resolution_assessment`此前未进入数字、引用、绝对断言、负面证据和推断身份扫描，模型可在新字段中无审计地写“政府指导价导致结构恶化”“并购流出导致AA波动”“已充分体现”。validator现把decision_consistency及每条premise assessment纳入完整叙事门；premise使用自己的局部evidence_ids，不能借全局证据池。否定性认知边界如“不能单独证明现金可达”不会被误报成正向推断。
- 新门把刚通过的稿件降为11项INVALID；第十四次run仍限定4次和零搜索。第一次writer因`resume_best_rejected=true`与完整findings接口冲突未进入验证，第二次补丁把11项压到4项；连续两次writer失败熔断在第3次调用。manifest记录3次调用、66,189个未缓存输入token、0次provider重试，没有进入下游或发布。
- writer接口已离线修复：恢复模式同时支持受约束patch和完整候选全量验证；二者同时非空才拒绝，`findings`在工具schema中改为可选，避免严格provider被迫重传大对象后又收到`finding_patches_empty`。对抗测试验证完整重传仍须全量通过才能canonical。
- 当前best-rejected为3/3完整稿、4 INVALID/0 INCOMPLETE，剩余仅为无身份临时算式：关联存款合计490.937M出现两次、6.2%-5.5%=0.7pp及5.6%-5.5%=0.1pp；恢复路由仍为`local_patch_no_new_research`，应删除临时差值或绑定正式计算，不得搜索。两次运行合计130,293个未缓存输入token。五个核心哈希不变，阶段回归`470 passed`；Phase 08继续VALIDATING。
- 下游只读预检确认：旧frozen insight ledger的唯一当前结构错误是`question_basis.question_id_missing`，其问题文本与已选`cash_value_realization`同义，可在decisive正式通过后做候选优先的确定性身份迁移，不应再调用模型重写洞见。`decision_diff_approval_pending`则不是框架缺陷：D014/D015确实改变减仓/退出动作，继续保留人工批准门，不因持续付费授权而自动放行。

### 2026-08-04 决定性问题第十五次实跑、依赖调度与洞见身份迁移

- 首次3-call有界run把best-rejected从4项收敛到2项，但完整恢复重传顺手改动了已通过问题。writer现先用当前validator确定精确question frontier，补丁或完整重传都只能修改仍有错误的问题；越界修改直接拒绝。该run为66,582个未缓存输入token、零搜索、零provider重试。
- 旧frozen insight的唯一缺口已实现零模型candidate-first身份迁移：只有当唯一错误为`question_basis:question_id_missing`、问题主题唯一匹配且decisive正式就绪时才可promotion。01502候选唯一匹配`DQ:cash_value_realization:873b9ad2562988`，候选自身为`DECISION_READY`，但因decisive仍未通过而保持`READY_TO_PROMOTE`，canonical完全不变。
- 第二次3-call验证暴露外层调度缺陷：completion同时列出结构化阻断和派生的Ch12/Ch14/Ch0时，旧路由进入普通章节修复，54,161个未缓存输入token只做读取和审计。调度现严格遵守依赖顺序：任一结构化frontier未通过即冻结全部章节；结构化门全部通过后，真实章节缺陷才重新开放。真实输出的`(12,14,0)`已确定性路由为`synthesis_only=True`。
- 修复后第三次3-call真实验证直接进入decisive writer，没有读取章节或搜索。第一次补丁因validator路径`premise_resolution[...]`与工具只接受外层`resolution_assessment`不一致被拒；第二次完整候选仍剩2条未登记推断，随即同错熔断。manifest为64,700个未缓存输入token、零provider重试，未发布。工具现增加安全`premise_resolution`补丁别名，只替换该问题的前提数组并保留net support与decision consistency，减少大对象重传和路径误用。
- 本批三次运行共9次调用、185,443个未缓存输入token。best-rejected仍为3/3完整、2 INVALID/0 INCOMPLETE；剩余是operating assessment的一项数字身份与一项推断身份，不构成新研究缺口。五个核心哈希保持不变，阶段回归`474 passed`。Phase 08继续`VALIDATING`；下一frontier只使用新别名修这两个字段，不搜索、不改正文、不自动批准decision diff。

### 2026-08-04 决定性问题第十六次实跑与前提行局部合并

- 新3-call有界run继续直接进入decisive writer，无Web搜索、无章节读取和正文写入；模型只读取已有financial/operations/governance evidence context。第3次调用使用新`premise_resolution`别名，但仅提交需修改的两行及部分字段。旧实现仍按整数组替换，导致未重传的`plan_value`、`direction`和另一前提行丢失；last-attempt退化为8 INVALID/2 INCOMPLETE，best-rejected保护生效并保持原2项错误。manifest为61,700个未缓存输入token、零provider重试，报告未发布。
- 接口现把别名改为真正的premise-keyed局部合并：每行必须命中当前问题已有`premise_key`，只覆盖显式提交字段，其余plan value、方向、证据、说明及未提交行全部保留；重复键、未知键和未知字段直接拒绝。该语义与validator返回的`premise_resolution[n].field`路径一致，避免模型为改一句说明重传完整assessment。
- 阶段回归`475 passed`；五个核心哈希不变，insight迁移仍为`READY_TO_PROMOTE`。下一frontier仍是best中的同2项，但现在可以用两条真正局部的premise patch完成，不需要搜索、回读年报或改正文。

### 2026-08-04 决定性问题第十七次实跑、洞见晋升与人工动作门

- 新3-call有界run直接进入decisive writer。第2次候选未通过，第3次使用premise-keyed局部补丁后`written=true`，3个问题完整达到`DECISION_READY`；控制流在同一tool batch立即停点，没有搜索、章节修改或跨入新模型任务。manifest为68,970个未缓存输入token、零provider重试。
- decisive正式通过后，旧insight的唯一问题身份候选自动晋升，`insight_validation`达到`DECISION_READY`。核验发现canonical已经写入但migration lifecycle仍停在`READY_TO_PROMOTE`；promotion现按candidate精确fingerprint幂等恢复并记录`PROMOTED/canonical_fingerprint/promoted_at`，不能靠语义近似补状态。实际记录已收口为`PROMOTED`，研究正文未改变。
- completion已从`INVALID`变为仅含`decision_diff_approval_pending`的`INCOMPLETE`。该diff修改D014减仓窗口与D015退出条件，属于真实投资动作变化而非技术迁移；持续模型费用授权不能替代人工审批。阶段回归`475 passed`，报告继续未发布。下一步必须由人工明确批准或拒绝D014/D015，框架不得自行越过。
- 正式请求审批前在30MB临时副本中模拟批准与compiler传播，发现受保护区块虽会更新，旧正文仍保留“大股东减持>5%立即平仓/平仓/事件止损”，并有仓位、衰减、要求回报率、退出条件4项自由关键值。模拟完成契约因此保持`INVALID`，证明审批门成功拦住了一个尚未完整传播的动作版本。
- compiler现于审批判断之前执行全文关键值和manifest动作冲突扫描；manifest明确为“重估”的事件若仍出现直接平仓/清仓/立即退出/事件止损且没有重估条件，返回`stale_action_conflict`。新增两类确定性迁移：按manifest把旧直接退出词降为重估；只对唯一labelled table/bold summary从冻结ledger单向重写并绑定ID。自由分析不自动改写，未知映射继续阻断。
- 01502正式候选已零模型迁移3处大股东减持旧动作，Ch0仓位统一为1.5%并绑定D012，Ch12的r*=10%与decay补绑定，Ch14退出条件由D015单向重写。compiler重验为0 INVALID，仅剩`decision_diff_approval_pending`；阶段回归`478 passed`。现在才进入真实人工动作审批节点。

### 2026-08-04 人工动作批准、双层候选收口与港股机器验收

- 操作人明确批准D014/D015，approval绑定当前ledger fingerprint、TH003/TH005及2025年报。compiler写入受保护区块后，完成契约暴露两个跨validator语义差异：`decay=-3.2%`与canonical 3.2、`r*=0.10`与canonical 10%。decision ledger现与compiler共享身份感知等价规则，仅对moat decay允许绝对值符号、仅对percent entry允许小数比例表达；其他数值仍严格匹配。
- Ch0因compiled decision block未携带来源而只计10/12个证据锚点。保护区块现逐条传播ledger原始`source_ids`，不是用内部章节循环引用凑数。重组后completion=`COMPLETE`、全部quality gate PASS；evidence coverage 344锚点/19个唯一来源、ratio 0.57，唯一非阻断警告为base-rate样本0<5。
- 双层validation-only候选现同时落盘memo draft与约157KB technical draft，memo链接同批次技术稿。此前只写memo draft会链接旧正式technical，现已由对抗测试封住。验收variant改为memo+technical组合hash，盲评包同时包含两层；技术附录任一变化都会令旧评审失效。
- 零模型管线收口记录0 calls并生成`COMPLETED / VALIDATED_NOT_PUBLISHED` manifest。该run暴露validation-only仍调用tracking materializer、覆盖`最新_分析报告`别名；现已完全跳过versioned/latest正式物化，被误写的别名从自动归档恢复，主正式文件始终未覆盖。验收器同时以run manifest的validation-only身份优先选择当前draft，不能被较新的旧正式别名劫持。
- Phase08聚合结果现为：金融街物业`READY_FOR_BLIND_REVIEW`（variant `45a455f8b3eeaafa`）、格力Phase08同为`READY_FOR_BLIND_REVIEW`，其余1个TECHNICALLY_BLOCKED、1个NOT_ASSESSABLE、控制样本继续留置。A股+港股机器验收子目标完成；阶段仍为`VALIDATING`，因为金融街洞见上限为`COMPETENT`、尚无两份独立盲评、控制样本未打开且0个BENCHMARK_APPROVED。完整阶段回归`483 passed`。

### 2026-08-04 独立盲评 V2 身份与工件绑定

- 旧盲评契约只校验三项自我声明和不同`reviewer_id`，无法证明评审看的是当前候选，也无法识别同一评审上下文或候选生成模型复用。盲评现升级为`independent-report-review.v2`：每份评审必须绑定完整盲评包SHA-256、actor/provider/model/context身份，并声明上下文隔离和生成者身份不重叠。
- 验收器从当前及归档run manifest保守汇总已知生成身份；01502候选识别为`deepseek_oa:deepseek-v4-pro`。同一provider/model的评审会因生成者重叠失效，不同评审名字复用同一context也只能计一份。由于历史manifest不能证明全部人工改动，保障等级明确写为`VERIFIED_ARTIFACT_AND_DECLARED_PROCESS`，不冒充密码学或完整作者证明。
- 候选仍为variant `45a455f8b3eeaafa`，当前盲评包hash为`c9a1c535…7202`；V2模板已重建，旧V1评审会自动失效。定向回归`20 passed`，聚合状态保持2个`READY_FOR_BLIND_REVIEW`、0个`BENCHMARK_APPROVED`。下一出口仍是真正隔离的两份盲评，不允许主流程自行伪造评审身份。

### 2026-08-04 首轮双盲结果与不可补偿退回

- 两个全新OpenAI Codex上下文只读取hash绑定的01502盲评包和空模板，互不读取对方结论；生成者记录身份为DeepSeek。两份提交均通过V2的工件、身份、context去重和结构校验，保障等级为`VERIFIED_ARTIFACT_AND_DECLARED_PROCESS`。
- 两名评审独立给出`FRAGILE`，合计5条fatal finding，其中两项形成交叉共识：Ch12的`V_cash=605M`是分配价值，Ch14却把同名指标写成`1,695M`净现金；主估值链因此无法闭合。其他重大问题包括：2025-12-31价格被当作2026-08-04即时动作输入；1.98 HKD买入线仅满足10% DDM而没有满足报告优先采用的10%+3.2%衰减门；λ及多个动作阈值缺乏经验校准，并有市场折价反向参与内在价值折价的循环风险。
- 盲评过程同时暴露两项契约问题：模型会使用自由`FAIL/PASS/PARTIAL`状态，且Python validator未检查`fatal_findings`数组元素类型。V2校验器现拒绝非字符串fatal finding和非法reviewer limit；评审员只做枚举/序列化修正，basis、位置和实质结论未改。定向回归`22 passed`。
- 验收状态机新增不可补偿的`REVISION_REQUIRED`：达到最低独立评审数后，只要存在fatal finding或`FRAGILE/NOT_ASSESSABLE`裁决，就不得停留在“继续找评审”的`READY_FOR_BLIND_REVIEW`，也不得用更多票数稀释。验收产物新增结构化`independent_review_outcome`，保留评审数、verdict分布和逐评审fatal finding。01502现正式退回`REVISION_REQUIRED`；聚合为1个READY、1个REVISION_REQUIRED、1个TECHNICALLY_BLOCKED、1个NOT_ASSESSABLE，0个BENCHMARK_APPROVED。阶段回归`419 passed`。
- 下一修复工作包必须落在通用框架而非01502正文：①市场数据as-of与动作时效硬门；②canonical metric命名空间，区分净现金与分配价值并禁止同名异义；③买入触发与全部active return hurdle一致性；④主导估值参数/阈值的依据与脆弱性门；⑤决定性问题需要的primary read/research execution从优先级提示升级为适用性硬门。完成后重跑validation-only形成新variant，旧盲评自动失效，再进行第二轮双盲；控制样本仍不打开。

### 2026-08-04 首轮盲评缺陷升级为发布硬门

- `decision_compiler_policy`现绑定`decision_as_of`和`max_market_age_days`（默认7天）。`market.price.current.as_of`晚于决策日或超过有效期直接INVALID；PIT回测可显式传历史决策截止日，不能用今天日期误伤历史报告，也不能把年报期末价冒充实时价格。
- compiler新增可扩展的canonical symbol语义扫描。当前首先覆盖盲评真实命中的`V_cash`：对表格与赋值式提取同一符号的最终值，同值重复允许，同名不同值返回`metric_identity_conflict`。解析器忽略来源标签和只讨论折现口径、未声明数值的句子，避免把`M=0.5047`或`r*=10%`误抓成V_cash。
- 动作一致性增加两道不可补偿门：当canonical`margin.return<0`时，`trigger.buy`的value/basis/rationale必须明确要求回报安全边际、综合回报或`r*+decay`重新达标；当Hold候选当前价高于买入触发价却仍建议正仓位时，仓位必须明确限定为既有持仓，不能把“观察”偷换成未持有者买入。
- 四个对抗用例分别覆盖市场价过期、V_cash同名异义、买点忽略综合门和未触发买点却给正仓位；加上validation-only候选身份保留回归，阶段回归由419增至`424 passed`。01502零写入预检精确命中4项：市场价过期216天、买点忽略综合门、正仓位缺既有持有人范围、V_cash 605M/1,695M冲突。
- 零模型completion重算后旧`COMPLETE`诚实降为`INVALID`；除新compiler四项外，还暴露旧正文把decision ID当普通来源引用、但同一行没有陈述该ID canonical值的7处既有错误。验收聚合曾因completion降级误切换到旧正式稿，造成已评审variant和两份盲评暂时消失；`find_report`现规定`COMPLETED/VALIDATED_NOT_PUBLISHED`始终锁定同批draft身份，规则升级只改变机器状态，不改历史评审对象。
- 01502仍绑定variant `45a455f8b3eeaafa`及两份有效`FRAGILE`评审，但机器状态进一步降为`TECHNICALLY_BLOCKED`；当前聚合为1 READY、2 TECHNICALLY_BLOCKED、1 NOT_ASSESSABLE，0 BENCHMARK_APPROVED。下一frontier是让自动修复安全刷新市场快照、拆分V_distribution与净现金措辞、重建买点/持有人动作，并清理decision ID泛引用；修复产生新variant后才允许复盲。

### 2026-08-04 年糕行情事实源与重算边界

- 行情获取不再在Turtle内另造provider链。自动定量阶段通过`niangao_market_bridge.py`以SQLite只读方式消费独立年糕系统的watchlist快照，要求正价格、provider身份、抓取时间和最新成功刷新批次，并固化快照hash及历史副本；缺失、过期、未来时间或代码不匹配均失败关闭。
- `compute_bundle.py --market-snapshot`会验证工件hash与交易代码，将价格、抓取时间、as-of、年糕provider和快照hash写入market provenance。`compute_bundle_db`已删除“沿用旧bundle股价”的静默缓存路径；普通当前时点运行拿不到新鲜年糕快照即停止。PIT历史回测明确不得调用该当前行情入口。
- 对已冻结报告，`market_refresh.py`只生成`compute_bundle.market_candidate.json`和依赖frontier，不改canonical ledger或正文。价格变化会确定性重算市值、AA/FCFE/Normalized三种GG、股息率与P_base；回报安全边际、仓位和买卖动作保持人工/模型判断frontier，不允许仅替换D001后发布。
- `market_refresh_validation=RECOMPUTE_REQUIRED`已进入completion硬门，防止刷新候选存在时旧报告被误放行。01502真实只读验证得到年糕价1.99 HKD（stock-sdk，2026-08-04），相对旧2.02使GG base/FCFE/Normalized分别由6.2/8.0/6.2变为6.3/8.1/6.3，并明确列出六项动作判断待重建；正式账本与章节哈希未被刷新脚本修改。
- 新增5项A/H代码、只读/哈希/归档、过期失败关闭、冻结账本不变和仅时间戳刷新不重开动作判断测试；Phase主干回归为`429 passed`。全仓无筛选收集仍受既有可选`tushare`依赖缺失和两套`tests.conftest`同名冲突影响，本阶段不通过安装依赖或重排旧测试目录掩盖该环境问题。

### 2026-08-04 行情依赖决策候选与估值符号命名空间

- `V_cash`不再被允许作为可发布的模糊符号：即使全文只有一个值也返回`ambiguous_metric_symbol`；同名多值继续返回更严重的`metric_identity_conflict`。明确命名空间现区分`V_distribution`（分红率加权内在价值）、`net_cash_broad`（广义净现金）和`cash_and_bank_balances`（现金及银行结余），并分别检查同名多值。
- 新增保守的`metric_namespace_migration.py`。它只在同一章节/同一行语义足以证明身份时改名；若净现金表格同行已有`net_cash=...`来源锚，还会同步采用该规范值，否则保持阻断。01502已将Ch12的605M改为`V_distribution`，将Ch14的错误`V_cash=1,695M`修为`net_cash_broad=1,724.75M`；旧V_cash冲突已归零。
- 行情刷新现在不仅重算compute bundle，还生成完整`decision_ledger.market_candidate.json`、action-changing diff、章节传播frontier和指纹绑定的审批预览。对01502，1.99 HKD年糕价使价格MOS变为28.9%、回报安全边际变为-2.6pct；综合回报买点按`(DPS_native+g×V_final)/(r*+decay)`得到1.5992 HKD，规范取1.60，而旧1.98仅是忽略decay的10% DDM门槛。
- 候选保持统一决策Hold、V_final=2.80、r*=10%、decay=3.2%、减仓和退出规则不变；1.5%仓位被明确限定为既有持有人上限，未持有者在1.60以上为0%。由于买点与适用人群发生动作语义变化，自动批准被禁止。当前审批预览验证为`READY_FOR_APPROVAL`，fingerprint=`ef270eff…ec6`。
- 批准前传播审计已一次定位全部边界：Ch0/4/7/9/11/12/13/14，30项关键旧值锚和61项decision引用缺口。批准后只能在该范围内区分`P_DDM=1.98`理论门槛与`P_buy=1.60`综合回报买点、重编保护区块并生成新validation-only variant；不得借行情刷新重写财务事实或估值判断。
- 新增命名空间歧义、来源值同步、综合回报公式和既有持有人范围等对抗测试；Phase主干回归为`432 passed`。本阶段未调用DeepSeek，canonical decision ledger仍保持原hash，报告继续`INVALID/RECOMPUTE_REQUIRED`，没有伪装为已完成。

### 2026-08-04 行情审批晋升、全依赖传播与新候选收口

- 操作人批准指纹`ef270eff…ec6`后，框架以可恢复归档晋升年糕1.99 HKD快照及行情候选：canonical买点为1.60 HKD；1.5%只适用于已持有人，未持有人在触发价以上为0%；其他投资判断未扩张。行情门达到`CURRENT`。
- 新增通用结构化依赖刷新和章节传播：按工具与metric path重建全部116个CALC身份，并同步claim、decisive findings、valuation、thesis、insight及15章市场派生值。传播器保护步骤编号，区分理论`P_DDM=1.98`与操作`P_buy=1.60`，连续执行幂等。
- decision compiler新增非canonical动作价格硬门；report audit修复FCFE标签误识别；决定性问题刷新会递归重绑嵌套说明及推断审计中的CALC身份。零修复轮不再读取陈旧completion，而是强制重新组装和评估当前工件。
- 真实`analyze.sh --repair-only --repair-passes 0 --validation-only`已成功完成：manifest=`COMPLETED`、publication=`VALIDATED_NOT_PUBLISHED`、LLM calls/tokens均为0；completion=`COMPLETE`，唯一警告为base-rate样本不足。技术报告抽样审计11/11 PASS，引用核验34 PASS、0 WARN/FAIL。
- 新组合variant为`90d0830770a28cf6`，机器状态重新进入`READY_FOR_BLIND_REVIEW`；旧variant的两份FRAGILE评审因variant和盲评包hash不匹配自动失效，不能跨版本复用。当前聚合为2个READY、1个TECHNICALLY_BLOCKED、1个NOT_ASSESSABLE，0个BENCHMARK_APPROVED；控制样本仍留置。
- 当前阶段回归`447 passed`。Phase 08仍为`VALIDATING`：下一出口是对新variant进行两份真正隔离的复盲；若无fatal finding，再冻结规则并打开中海物业控制样本，之后才可能进入人工黄金批准。

### 2026-08-04 新variant第二轮双盲与深层质量退回

- 两个全新隔离上下文只读取variant `90d0830770a28cf6`的hash绑定盲评包和空模板，互不读取对方、旧评审或仓库资料。两份工件均通过variant、packet hash、context、reviewer及生成者隔离校验，保障等级为`VERIFIED_ARTIFACT_AND_DECLARED_PROCESS`。
- 两份评审再次独立给出`FRAGILE`，分别记录7项和4项fatal finding。共同结论不是行情刷新失败，而是更深层的研究闭环不足：决定性现金可达问题没有法律实体/限制/运营资金/可分配储备/兑现时间表；λ由未校准加减分产生且受市场PE反向影响；DDM以5.5%折现却与10%要求回报主模型宣称交叉验证；动作没有在联合悲观假设下闭环。
- 其他客观一致性问题包括：GG/Normalized/FCFE公式可复核性不足，FY2024 DPS出现0.145/0.157双值，财务公司收益率用年度利息除最高余额，Ch14 `λ/0.625≈1.69`算术不成立，市场隐含λ约15%/17%并存，以及升级条件与“两年资本配置证据”要求冲突。
- 状态机已不可补偿地将01502退回`REVISION_REQUIRED`；当前聚合为1 READY、1 REVISION_REQUIRED、1 TECHNICALLY_BLOCKED、1 NOT_ASSESSABLE，0 BENCHMARK_APPROVED。规则不冻结、02669控制样本继续留置，不能用机器硬门PASS覆盖研究判断失败。
- 盲评模板连续两轮诱发模型使用自由PASS/FAIL枚举。模板现内嵌合法dimension/verdict枚举、fatal finding字符串格式和禁止自由枚举说明；本轮只做序列化映射，所有basis、位置和fatal finding保持不变。定向验收回归`34 passed`。
- 下一修复阶段必须先落通用框架：现金可达性结构化bridge、λ参数依据与循环输入门、模型折现率可比性、GG公式经济含义和单位/重复扣减审计、联合压力情景与动作优先级。完成跨样本对抗测试后才允许生成第三个variant复盲。

### 2026-08-04 第三variant可靠性重建与决策修订事务门

- 两轮FRAGILE共同指出的现金可达、参数校准、模型可比性、联合压力和动作优先级已转为非补偿结构门，而不是继续靠报告字数或提示词修补。`decision_reliability.py`现在区分法律储备上限、母公司现金位置和实际分配流；未验证现金必须100%折价，NAV无折现率不得伪造0%比较差，负回报安全边际禁止Buy，联合压力采用最差动作。
- valuation writer改为可靠性先于canonical持久化。完整失败稿保留动态重验的best/last candidate，恢复时必须保持完整模型ID集合；可靠候选若只与已批准manifest的动作、仓位或V_final冲突，不写canonical，而生成指纹绑定的`valuation_decision_revision_proposal.json`。completion把该状态显示为`PENDING_APPROVAL`，模型循环立即停点，付费权限不能替代投资动作批准。
- 真实DeepSeek运行先暴露一次调度误判：`report_overstates_noncomparable_model`来自`synthesis.decision_rule`却被当作正文缺陷，3次调用只读九章。错误现带`report/synthesis/model_comparison`来源身份，路由复验为`synthesis_only=True`；后续正确路径首轮输入约28k且只开放4个工具。proposal成功不再计入连续writer失败熔断。
- 独立复核拒绝了模型表面通过的Hold候选：它把`retained_value_realization=0`与正文`λ=0.70`并列，EPV equity bridge为8.15 HKD却直接输出3.22 HKD，NAV每股桥也未对账。新门要求正文λ与主模型兑现率一致；任何equity bridge结果差异必须有可复算的价值兑现桥；综合值必须等于主模型或合法的加权/兑现桥；兑现桥的派息率必须绑定同值VERIFIED原始事实；回报增长项按留存兑现率缩放。旧proposal会按当前validator实时重验，不能依靠历史PASS继续审批。
- 自动模型在最后一次两调用上限内仍试图保留旧3.22锚，管线停止且未覆盖canonical。随后用同一writer确定性组装了保守候选：FY2025核验派息率50.45%（`OBS:6367fd7099daa2b32164`）、母公司可验证现金0、留存兑现率0；EPV经营价值3.7786 HKD/股经兑现桥得到`V_final=1.9062926934`，当前1.99 HKD对应价格安全边际-4.39%，回报安全边际-7.0pct。候选动作因此为`Avoid / 0%`，不再用GG>II或NAV/DDM诊断值抵消两个负安全边际。
- 当前proposal指纹为`24d4b580d4f9176d11550f4235f941f698b29faf5959967eb9bec8027c293b29`，实时结构验证除`action/position/V_final`三项已批准决策冲突外无其他缺口，decision reliability为`DECISION_READY`。旧`Buy / 3.5% / 3.22`账本、manifest和正式报告未改变，validation-only未发布。下一步只能由人工明确批准或拒绝该完整指纹；批准后还需生成decision diff、传播D006/D007/D009-D012及触发器、重建下游账本和Ch14/Ch0，再产生第三variant复盲。
- 定向主干回归最新为`164 passed`；扩展Phase套件为`680 passed / 3 failed`，三项失败均来自仓库现存硬编码Tushare token使隔离`.env`测试被真实本地配置短路。全仓无筛选收集另受可选`tushare`未安装和两套`tests.conftest`同名冲突影响。本阶段未迁移密钥，也未用安装依赖掩盖既有环境问题。

### 2026-08-04 书本式价值拆分与 EPV 兑现语义

- 按《价值投资：从格雷厄姆到巴菲特》的资产、盈利能力、获利成长三分法，新增通用`separate_value_components` synthesis bridge：经营 EPV、已证明留存成长和可及现金不得再由单一`λ`混合折算。
- 未证明高回报再投资可以令`retained_growth_per_share`为零，但不得把已存在的经营 EPV 按当期派息率整体压缩为“仅分红价值”。这避免将“成长没有证据”误写成“现有赚钱机器没有价值”。
- 为维持现金可达性硬门，bridge 当前强制`accessible_cash_per_share=0`；任何现金进入每股价值仍须先通过独立现金桥的法律主体、分配路径及可复算换算验证，不能借新方法加入未核验现金。
- 新增对抗测试覆盖：经营价值与成长增量可审计分离；未核验现金无法通过该桥注入。`tests/test_stage13_valuation_model_gate.py`与`tests/test_stage34_decision_reliability.py`定向回归`60 passed`。01502 的 canonical 账本、现有`Avoid/0%`待审批候选和报告正文均未改写；书本式重估仅作为非 canonical 研究备忘，等待完整决策 diff 与人工审批边界。

### 2026-08-04 01502 公司本体现金位置来源复核

- 对原始年报而非既有抽取摘要的复核发现，p160「公司财务状况报表」已披露上市公司本体现金及等价物1,033.070M RMB、三个月以上存款117.166M RMB及受限制银行存款34.538M RMB；p58已核验可供分配储备299.190M RMB，p85还披露向本公司拥有人派付股息58.640M RMB。
- 因此“合并现金位置未验证”不能泛化为“可验证母公司现金为零”。这不代表全部公司现金可立即加入估值：运营资金、受限金额、关联方财务公司资金构成及法定分配路径仍必须逐项桥接。
- 现有`Avoid/0%` proposal 的零可及现金前提需要以公司本体报表重新验证，原 fingerprint 不得批准或复用；canonical账本和正文保持不写入。已落盘非 canonical 原始来源审计与书本式重估修订，下一frontier是补齐现金桥结构化事实后生成新的决策差异预览。

### 2026-08-04 公司本体现金提取与候选实时失效

- 官方事实提取器新增公司本体财务状况表识别，产生与合并口径隔离的`company_only_cash_and_cash_equivalents_rmb_m`、`company_only_term_deposits_rmb_m`及`company_only_restricted_bank_deposits_rmb_m`；同一模式适用于任何年报，不依赖01502路径或固定页码。
- 可靠性门现要求：一旦有已验证公司本体现金观察，现金桥必须显式引用并处理该法律实体位置。它仍不能证明自由分配，但遗漏它会把“已知公司现金”错误降级为“无母公司现金观察”。
- 01502 FY2025新事实为公司本体现金1,033.070M RMB（`OBS:484dcc7ff193d5df6135`）、三个月以上存款117.166M RMB（`OBS:318ba851cd76a0b82090`）及受限存款34.538M RMB（`OBS:dbe51d07e3e743b80304`）。旧Avoid proposal未桥接前一事实，实时`decision_reliability=INVALID`，completion为`INVALID/FAIL: proposal_decision_reliability_not_ready`；原审批指纹已自动失效，不能被批准。
- 定向官方证据、估值和可靠性回归`78 passed`。canonical账本、manifest、报告正文及交易动作保持不写入；下一步是按公司本体现金、关联方资金、受限资金、运营资金和法定储备逐项重建新cash bridge，再生成新的非canonical decision diff预览。

### 2026-08-04 决策修订原子预览

- 当时曾把书本式 R3 `Hold / 0%`描述为待批准结论；后续人工边界修订已明确将其降为内部工作假设。操作人不审批估值层动作，只审阅完成报告的体系一致性和最终结论。
- 新增非持久化`preview_decision_revision`：在写 manifest 或 ledger 前构造完整候选 ledger、action-changing diff 与正文一致性验证。它绝不写入 canonical 文件；正文旧值、缺章或未绑定数字会返回`CONTENT_PROPAGATION_REQUIRED`，禁止形成半更新状态。
- 01502 预览列出 D006、D007、D009–D015 的九项动作相关变化，并定位30处旧正文数值冲突；Ch0/Ch14及 thesis/insight 仍缺失。正式传播必须先在候选区完成全文与下游账本，再原子提交。

### 2026-08-04 人工边界改为完整报告体系审阅

- 操作人明确指出，中间候选动作没有独立审批价值；其需要判断的是完整报告是否遵循格雷厄姆—巴菲特式投资体系，以及最终结论是否由充分上下文支持。
- valuation proposal新写入状态改为`INTERNAL_SYNTHESIS_REQUIRED / NOT_REQUESTED_AT_VALUATION_STAGE`。旧`READY_FOR_DECISION_REVISION / PENDING`工件兼容读取时也降级为内部综合缺口，不再向用户显示`PENDING_APPROVAL`。
- completion现在返回`FULL_REPORT_SYNTHESIS_REQUIRED: valuation_hypothesis_requires_full_report_synthesis`。候选仍不能覆盖canonical，但其下一出口是自动完成thesis、insight、章节传播和全文一致性，而不是让操作人审批估值层动作。
- 面向操作人的最终界面只保留：投资体系一致性、关键偏离、完整报告最终结论、主要证据及翻转条件。报告生成、内部候选和差异传播继续自动化。

### 2026-08-04 最新收口：书本式完整综合与第三候选复盲入口

- 01502已按“经营资产/盈利能力/成长价值/额外现金分开”的格雷厄姆—巴菲特路线完成全文综合。公司身份按官方资料确认为北京市西城区区属国企；国企属性进入持续经营、治理和兑现概率判断，但不替代少数股东现金兑现验证。
- 基准值采用不含成长的经营EPV `3.148815 HKD/股`；额外现金在缺少最低营运资金、法律可分配储备、资金上划和分配时间表桥接时不加入基准，但明确列为未计入上行，不再被解释为经济价值为零。留存成长价值在高回报再投资未获证明时为0。
- 当前价`1.99 HKD`对应价格安全边际约`36.8%`，税前股息率约`7.8%`，但所有者回报安全边际为`-7.0pct`。价格便宜不能补偿回报门不足，完整报告最终结论因此为`Hold / Cautious Watch`，未持有人仓位`0%`；观察区间为`1.55 / 3.1488 / 4.52 HKD`。
- 内部valuation proposal已在完整manifest、decision ledger、估值、thesis、insight、触发器和正文语义一致后自动解析为`RESOLVED/PASS`。普通报告不再要求操作人逐个批准中间动作；操作人只审阅完整报告的投资体系一致性、偏离和最终结论。
- validation-only真实入口以0次模型调用完成，manifest=`COMPLETED / VALIDATED_NOT_PUBLISHED`，completion=`COMPLETE`。组装器同时补上了从稳定`report_context.meta.issuer`恢复公司名的通用兜底，避免断点验证生成空标题。当前组合variant为`806b7d884e741856`，blind packet SHA-256为`08bc62b26d96a9c7ca467c2fb7274350989c0a09834f74ab238e09cf5f39d782`，机器状态`READY_FOR_BLIND_REVIEW`。旧四份评审均因variant/hash不匹配失效，当前有效票`0/2`。
- 完整阶段测试为`489 passed`。Phase 08仍为`VALIDATING`，不是因为报告动作待批准，而是因为机器流程不得自签独立质量结论。下一合法序列只有：两份真正隔离的当前variant盲评；若无`FRAGILE`/fatal finding则冻结规则；随后运行02669控制样本；最后对首个黄金契约进行一次阶段级人工指纹批准。该批准不扩展为普通报告逐份审批。

### 2026-08-04 第三候选当前状态

- 上一variant的两份隔离盲评均为`FRAGILE`，命中EPV正常化、价值到回报桥、触发器语义、伪增量ROIC和业务结构口径。上述问题均已进入通用代码门或结构化账本。
- 修订后01502以三年税后OCF-Capex正常化得到EPV `2.9604679507 HKD/股`，并建立五年无收敛/收敛/压力IRR桥。现金依旧按“存在—可达—可分配—时间”分层，未观察额外分配不进基准，但经济价值不归零。
- 真实零修复轮达到`COMPLETE`，阶段测试`503 passed`。当前variant=`cb77a9de88918fe7`，packet SHA-256=`3b0754b6ae376ff89f44c452f2630c2464721a932b0f34d38c6702f99af8486b`，验收器状态`READY_FOR_BLIND_REVIEW`，有效当前票`0/2`。
- 下一步必须是两个未参与生成、互不可见的新评审actor；主流程或旧评审context不得自评或复用。只有两票无`FRAGILE`/fatal finding才能冻结规则并打开02669控制样本。

### 2026-08-04 洞见升格门的真实验证

- variant `cb77a9de88918fe7`的两份新评审均为有效、独立的`COMPETENT`，fatal finding为0。状态仍未升为`BENCHMARK_CANDIDATE`，证明“无致命问题”不会被误当为“洞见优秀”。
- 客观剩余缺口修复后生成variant `ae7c524e3a3a988f`：packet SHA-256=`90065985b066ef2674b4be14d6403d0be51a43be40a79c94f6501091b6392145`，completion=`COMPLETE`，阶段测试`503 passed`。当前需要两个全新隔离actor复盲，旧评审不可复用。

### 2026-08-04 第二组复盲与证据边界收口

- variant `ae7c524e3a3a988f`的两份全新隔离评审均为有效`COMPETENT`，fatal finding为0。两票共同将决定性问题和动作一致性评为强，同时共同将信息效率评为弱；证据判别和因果深度因项目级利润率缺失、若干口径相加及主观归因而未达到强。
- 收口坚持“降低主张，不补造证据”：删除第三方项目低毛利的确定性归因；把员工福利35.7%与分包成本分列；禁止将财务公司存款、IPO余额和受限存款相加为可控现金；删除70%/20%/10%原因分摊；洞见只保留面积与收入CAGR均约10.9%、单位面积利润4.12元降至2.12元的直接观察。
- Ch11已从重复技术附录缩为GG历史诊断，明确AA、M、Q、历史市值、归母比例、HH/AP/λ和当前持有期IRR的边界；语义深度门为`PASS`，零修复轮completion重新为`COMPLETE`。
- 全阶段回归`503 passed`。当前variant=`4d425612a81c40cc`，packet SHA-256=`a93d09a52c5cc747fa6dabc07e0dd7e581100ebf48e37d1fd4c4283b994edcac`，状态`READY_FOR_BLIND_REVIEW`，有效票`0/2`。下一步必须由两个新的隔离actor评审；未获操作人授权前不启动，且此授权不构成投资结论审批。

### 2026-08-04 BENCHMARK_CANDIDATE与冻结后控制样本

- 操作人授权后，两个全新隔离actor只读取variant `4d425612a81c40cc`的盲评包与空模板。两票均通过独立性和hash校验，裁决均为`INSIGHTFUL`且fatal finding为0；验收状态升为`BENCHMARK_CANDIDATE`。
- 预定冻结条件满足后才将`config/real_report_acceptance.v1.json`的`rules_frozen`改为true。冻结后的聚合首次包含02669控制样本，防止用控制结果反向调门。
- 02669当前返回`NOT_ASSESSABLE`，因为旧输出缺少completion、runtime manifest、official evidence及Phase 08各结构化账本；该状态不代表控制样本报告被判差，而是要求用同一冻结流程真实生成。
- 预算预检估算控制运行上限约320次LLM调用、64分钟，并要求显式`--approve-expensive-run`。阶段在此等待操作人预算批准；之后仍须控制样本通过，再生成首个黄金契约的一次性人工指纹批准预览。

### 2026-08-04 控制样本完成与最终一次批准门

- 02669已在冻结规则后完成，正式variant为`347019c3e490c2e2`，packet为`01a96d66…f97af8`；两份有效独立评审分别为`INSIGHTFUL`与`COMPETENT`，fatal finding为0，状态=`BENCHMARK_CANDIDATE`。
- 报告以普通DPS、10%绝对要求回报和2%长期净增长形成2.42港元买入线；合并现金按“普通兑现已验证、额外全额上划未验证”分层，不把零额外加回解释为零经济价值。
- 旧AA双口径、EPV算术、价格止损冲突、衰减重复扣减、持有人动作和不可复算NAV均已从当前variant清除。
- 框架新增真实中位数计算和下行减仓价不得高于唯一买入价的硬门；定向回归`131 passed`。
- 01502和02669当前均为`BENCHMARK_CANDIDATE`。首个黄金契约预览绑定01502 variant `4d425612a81c40cc`及两份有效盲评；批准指纹为`5e1e00ae0d28d058d0f08410592debcccc614016a0c551cc8dedac895e74a45a`。
- 完成标准现在只差该一次人工指纹确认。它确认benchmark不变量和验收规则，不代表以后每份报告需要人工批准。
