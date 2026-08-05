# Turtle Investment Framework 换账号交接文档

> 用途：当前 Codex/OpenAI 账户额度不足时，在另一账户的新会话中无损续接框架优化工作。
>
> 更新时间：2026-08-02（Asia/Shanghai）
>
> 仓库：`/Users/xiami/workspace/analy/Turtle_investment_framework`
>
> 当前分支/提交：`main` / `390a88bdad0aec1081ccf6a8485c66bb9ad53084`

---

## 0. 新 agent 先执行什么

不要立即改代码、不要重跑报告。先按顺序完成：

1. 完整阅读本文件。
2. 阅读仓库根目录 `AGENTS.md`。
3. 阅读 `output/01502_金融街物业/HANDOFF_v13.md`，尤其第 9–15 节。
4. 阅读 `docs/QUALITY_SCORECARD_V2_AUDIT_SPEC.md`。
5. 阅读 `docs/QUALITY_EVALUATION_V13.md`。
6. 检查 `git status --short --branch` 与 `git diff --stat`，但不要清理工作树。
7. 运行本文第 12 节的定向回归，确认接手时基线仍成立。
8. 从第 10 节“下一实施阶段”继续，不要重新讨论已经裁决的问题。

---

## 1. 用户真正要解决的问题

用户正在把 Turtle Investment Framework 优化成一个自动运行、但以投资研究质量为第一优先级的报告管线。

核心目标不是“生成更长的报告”或“获得更高文本分数”，而是：

- 自动读取年报、结构化数据和必要的公开市场资料；
- 当既有提取不足时，必须回到 `read_section`/年报原文深化，不得根据缺失数据擅自推断；
- WebSearch 必须服务于行业、竞争、治理和外部事实，不得只留下搜索动作而未读取有效正文；
- 保持单一作者的公司全局认知、核心 thesis、估值身份和最终决策；
- 防止跨章参数漂移、版本混用和“格式合规但结论矛盾”；
- 报告最终仍由完整自动管线生成，不能依赖用户逐章手工修稿；
- 一次至少完成一个清晰阶段，不要让用户反复确认零碎动作；
- 可以优化 token，但质量退化时一票否决。

用户明确认为旧版也不是金标准，只是“矮个里面的高个”。格力 Stage 7 是当前相对认可的质量参照，不是不可修改的标准答案。

---

## 2. 不得违反的工作原则

### 2.1 质量优先于 token

- 不得为了达到 token 降幅而降低语义深度、证据密度、推导密度或年报阅读量。
- token、调用次数和 cache hit 只能作为成本指标，不能覆盖质量退化。
- “完成契约通过”不等于“投资结论可信”。

### 2.2 保持单 Agent 全局上下文

历史多 Agent 分章写作已经试过，章节作者缺少公司整体信息，导致洞察、叙事连续性和估值裁决退化。因此：

- 不得恢复多 Agent 分章写作；
- 不得把每章隔离成只有局部事实包的任务；
- 同一写作 Agent 应持续持有公司全局记忆、thesis、identity ledger 和 decision state；
- 可以压缩重复工具 payload、机械框架说明和已落盘全文，但不得压缩核心公司事实和跨章推理链。

仓库根 `AGENTS.md` 中仍保留早期“chain mode mandatory”的旧要求，它与本项目后续真实 A/B 结论冲突。对本轮质量优化，应以用户较新的明确裁决和 `HANDOFF_v13.md` 第 12–15 节为准：继续单 Agent 全局上下文方案。若未来要修改根规则，应先做最小范围、可回归的文档对齐，不能悄悄切回多 Agent。

### 2.3 研究不足时必须补资料

- `read_section`、`search_report` 和年报 Markdown/PDF 是主要事实来源。
- 没提取出的关键事实，要回年报原文查，不得用“未发现”推成“不存在”或“规模极小”。
- Ch2/Ch8 的 WebSearch 需要有效搜索和正文读取；Ch4/Ch9 需要报告内跨年搜索。
- 资料来源存在不等于来源支持主张，V3 必须继续解决“主张—证据支持关系”。

### 2.4 自动化边界

- 硬契约可自动阻断。
- 软评分目前只能用于诊断、排序和建议，不得自动重写已确认的关键数字、参数、估值和决策。
- 自动修复必须冻结已验证的数值、来源身份和 decision ledger。
- 每轮修复要有预算上限和 decision diff。

---

## 3. 已完成的主干阶段

完整细节见 `output/01502_金融街物业/HANDOFF_v13.md`，这里仅保留接手必需结论。

### Stage 1：完成契约与身份真源

- 15/15 章、语义深度、审计账本、GG 推导、质量门和决策 manifest 纳入完成契约。
- 修复股息、GG、DDM 和最终决策身份漂移。
- 金融街物业决策保持 `Hold Review / 1.5% / watch`。

### Stage 2：证据身份与来源清单

- 复合来源锚点归一为 canonical identity。
- 金融街物业未知来源由 333 降为 0。
- GG(AA/base)、GG(FCFE)、GG(Normalized) 分离，避免错误对账。
- 引用验证器排除了情景假设和百分位等伪数值冲突。

### Stage 3：语义深度与叙事效率

- `scripts/chapter_depth.py` 取代机械非空行数门。
- 深度按实质字符、数字声明、分析/因果、推导、来源和小节覆盖判断。
- `scripts/report_prose.py` 只整理展示文本，不修改章节真相源。

### Stage 4：生成契约、修复预算与冷启动

- 生成 prompt 注入语义深度合同。
- 修复预算按阻断章节动态计算。
- 落盘章节后压缩重复工具全文。
- `analyze.sh` 增加 `--output` 与 `--validation-only`。
- 分众传媒零状态冷启动验证质量门可工作，但成本很高。

### Stage 5：单 Agent 上下文保真

- 新增一次性章节合同包和 `company_context_memory.json`。
- 冻结已通过章节，repair fresh context 重新注入全局公司记忆。
- token 有下降，但证据锚点和覆盖率退化，因此只 `PARTIAL ACCEPT`。

### Stage 6：证据密度恢复

- 删除“同一来源全报告最多出现三次”的错误限制。
- 证据门改为动态密度合同。
- 全局 evidence coverage 硬门提升到 45%，unknown source 阻断发布。
- 分众传媒隔离样本恢复到 53% 覆盖，引用/数值审计零失败。

### Stage 7：格力数据丰富档冷启动

- 首个候选虽然通过旧门，但正文只有认可基线约 51%，被主动判为退化。
- 增加 data-rich profile，提高实质字符、数字、因果、推导和小节要求。
- 最终格力报告恢复到可接受量级，完成契约与独立审计通过。
- 结论是 `ACCEPT_QUALITY_REJECT_COST`：质量路径修好，但累计成本过高。

### 后续已存在的工程层

- `scripts/legacy_reference_regression.py`：历史参考防退化。
- `scripts/research_plan.py`：逐章问题、年报章节和工具计划。
- `scripts/absolute_quality_scorecard.py`：V2 硬契约 + 软质量雷达。
- `scripts/report_completion.py`：聚合完成契约、历史参考和绝对质量。
- `tests/test_stage9_gold_regression.py`：研究计划及历史参考回归。
- `tests/test_stage10_absolute_quality.py`：V2 评分卡对抗与接入测试。

这些代码目前属于大工作树中的未提交成果。不要把“Stage 编号缺少单独测试文件”理解成代码可以删除。

---

## 4. V2 评分卡的准确定位

当前规范：`docs/QUALITY_SCORECARD_V2_AUDIT_SPEC.md`。

V2 已经是一套有价值的：

- 研究执行审计器；
- 来源身份检查器；
- 文本质量退化雷达。

但它还不是“价值投资分析质量评分卡”。主要原因：它更多测量报告是否具备研究形式，没有充分测量结论正确性、模型适用性、跨章一致性和动作一致性。

当前 V2 的软雷达为 15 章等权，八个维度：问题覆盖、因果、邻近证据、来源质量、反证、可证伪、推导和效率。内部 A/B/C/D 只能用于诊断，不得升级为发布总门。

已知真实样本校准（来自规范，不代表当前重新运行）：

- 格力 Stage 7：B / 76；
- 金融街物业：C / 62。

这些数字不能解读成客观投资研究百分制。

---

## 5. 用户对 V2 的最终审计裁决

用户已经逐项审计并给出明确方向。接手 agent 不要再从“是否需要 V3”开始讨论。

### 5.1 最严重缺口：跨章一致性

格力报告出现过多套互相冲突的：

- `V_final`；
- `lambda`；
- 要求回报率 `r*`；
- 护城河衰减；
- 价格与回报安全边际；
- 仓位建议；
- 首次买入条件。

这类错误会改变投资动作，严重性高于因果词、字符数或公式数量。V3 第一优先级必须建立全报告唯一的 `decision_ledger.json`，为价格、估值、GG、II、lambda、增长、要求回报率、仓位和触发点提供 canonical ID。

同一指标不同值只有在明确标注以下身份时才允许共存：

- 不同情景；
- 不同日期；
- 不同计算口径；
- 旧值已废弃。

无法解释的冲突直接 `INVALID/FAIL`。

### 5.2 评分对象必须拆层

不得再用一个加权总分混合并互相抵消：

1. 数据完整性；
2. 推理有效性；
3. 估值与决策；
4. 表达质量。

前三层的关键失败不可被“写得清晰”抵消。总分可以用于展示，但不能单独决定发布资格。

### 5.3 从“有来源”升级为“来源支持主张”

重大主张应有结构化证据链：

```text
主张
→ 原始事实
→ 中间推理
→ 替代解释
→ 适用条件
→ 置信度
→ 对估值/仓位的影响
```

来源评分至少要区分：权威性、时间有效性、口径匹配、直接支持程度、交叉验证，以及是否只是报告内部循环引用。

### 5.4 估值模型适用性必须成为硬检查

不能因公式多就加分。需要检查：

- DDM/DCF/EPV/资产价值是否适合公司；
- 折现率是否对应决策主体；
- 名义/实际、税前/税后、股权/企业价值是否一致；
- `r > g` 是否有足够安全距离；
- 终值依赖和输入敏感性；
- 输出是否被误当作目标价；
- 多模型是否真正独立；
- 小幅参数变化是否令动作翻转。

### 5.5 反证要升级为竞争性解释测试

不再数“但、然而”。核心论点至少要有一条完整竞争性解释，包含：

1. 最强替代解释；
2. 支持替代解释的证据；
3. 能区分两种解释的观察指标；
4. 结论翻转条件；
5. 翻转后的估值和仓位动作。

### 5.6 精确阈值必须有依据

阈值质量应按以下结构评估：

```text
阈值质量 = 可观测性 × 依据充分性 × 区分能力 × 动作映射清晰度
```

没有历史波动、同行基准或模型敏感性依据的精确数字属于“伪精确”，不应得分，必要时应预警。

### 5.7 概率必须标注身份

区分：

- 频率概率；
- 历史基准率；
- 分析师主观概率；
- 仅用于情景权重的工作假设。

主观概率必须说明依据和不确定性；长期应记录预测结果用于 Brier Score/校准曲线。

### 5.8 取消 15 章等权发布逻辑

使用“门控 + 分层”，而不是靠提高关键章权重：

```text
数据与身份
→ 关键事实通过？否则 INVALID
→ 推理与竞争性解释
→ 估值及决策一致？否则 INVALID
→ 表达质量评级
```

### 5.9 深度门不得制造冗长

- 保留防空壳下限；
- 取消以高字符、推导单元数量作为质量目标的激励；
- 深度改为“关键决策问题是否闭环”；
- 不得为满足计数制造公式、重复阈值和重复段落。

### 5.10 来源使用二维评级

- 维度一：来源权威性；
- 维度二：与主张的距离。

同时记录日期、数据截止日、利益冲突、可复核性、同源转载去重和同行口径可比性。报告内部章节不得形成循环证据。

### 5.11 历史参考不再默认硬阻断

- 全文/主题覆盖下降：WARN；
- 已验证核心事实或有效证据无解释丢失：FAIL；
- 删除旧结论并记录变更原因：PASS；
- 发布时生成 decision diff，不做“只能增加不能删除”的全文相似度锁定。

### 5.12 建立后验校准

记录当时可见信息，分别评估：

- 过程校准：数据错误率、冲突率、概率校准、触发器有效性；
- 决策校准：预期/实际回报偏差、下行情景覆盖、thesis 翻转时效。

不得直接以短期股价涨跌评价报告，也不得完全忽略后验结果。

---

## 6. V3 建议状态机与模块

### 6.1 状态机

- `INVALID`：事实、口径、模型或决策存在关键错误；
- `INCOMPLETE`：关键决策问题尚未闭环；
- `REVIEWABLE`：可以交给人工研究员审阅；
- `DECISION_READY`：假设、估值、风险与动作一致；
- `MONITORING`：发布后进入预测和触发器跟踪。

状态由硬门和闭环程度决定，不由总分单独决定。

### 6.2 展示模块

权重只用于展示，不允许跨模块抵消关键失败：

| 模块 | 展示权重 | 关键失败可阻断 |
|---|---:|---:|
| 数据真实性与时效性 | 15% | 是 |
| 口径及跨章一致性 | 20% | 是 |
| 主张—证据支持关系 | 15% | 是 |
| 因果与竞争性解释 | 15% | 部分 |
| 估值模型适用性 | 15% | 是 |
| 情景、敏感性与不确定性 | 10% | 部分 |
| 决策可执行性 | 5% | 是 |
| 表达效率 | 5% | 否 |

---

## 7. 当前代码与 V3 之间的真实差距

以下内容尚未实现，不能在新会话中误报为完成：

- 没有全报告 `decision_ledger.json` canonical schema；
- 没有通用的跨章参数冲突硬门；
- 现有 `decision_manifest.json` 只覆盖部分最终动作，不等于完整 ledger；
- 没有主张级 claim/evidence graph；
- 来源解析主要验证身份存在，不验证来源是否真的支持主张；
- 没有估值模型适用性和脆弱性检查器；
- 没有完整竞争性解释对象；
- 没有阈值依据/伪精确检查；
- 没有概率 provenance 和校准记录；
- 历史参考 `FAIL` 当前仍会在 `report_completion.py` 阻断；
- V2 的复合来源逃逸口尚在：一个合法组件可能掩盖同锚点中的虚假组件；
- V2 的无数字断言邻证仍默认 100%；
- 表格共享来源、语义重复和主张支持关系仍未解决；
- 通用 topic 词表仍混入“小米/美的/格力钛”等公司特定词。

---

## 8. 工作树与安全状态

当前仓库不是干净工作树：

- 本地 `main` 相对远端：ahead 2、behind 9；
- 当前粗略状态：61 个 modified/staged、8 个 deleted、109 个 untracked；
- 大量框架成果仍未提交；
- `.env`、`analyze.sh` 和其他本地配置可能含 API key 或私密端点。

因此接手后：

- 不要 `git pull`；
- 不要 `git reset --hard`；
- 不要 `git checkout --`；
- 不要 `git clean`；
- 不要批量删除 untracked 文件；
- 不要覆盖用户已有修改；
- 不要把 `.env`、`analyze.sh` 内容、认证文件或密钥粘贴到聊天/日志/交接文档；
- 运行 DeepSeek 管线时沿用 `analyze.sh` 的密钥加载方式，不把 key 放在命令行。

如需同步远端，必须先由用户确认，并先制作可恢复快照或明确 commit 边界。

---

## 9. 接手后必须先读的文件

### 核心状态

- `docs/HANDOFF_ACCOUNT_SWITCH_2026-08-02.md`（本文件）
- `output/01502_金融街物业/HANDOFF_v13.md`
- `docs/QUALITY_SCORECARD_V2_AUDIT_SPEC.md`
- `docs/QUALITY_EVALUATION_V13.md`
- `AGENTS.md`

### V2/V3 改造入口

- `scripts/absolute_quality_scorecard.py`
- `scripts/report_completion.py`
- `scripts/legacy_reference_regression.py`
- `scripts/enhanced_quality_gate.py`
- `scripts/audit_rules.py`
- `scripts/evidence_citation.py`
- `scripts/research_plan.py`
- `scripts/chapter_depth.py`
- `scripts/turtle_agent/tools/write_tools.py`
- `scripts/turtle_agent/tools/read_tools.py`
- `scripts/turtle_agent/agent_loop.py`
- `scripts/turtle_agent/run.py`

### 测试

- `tests/test_stage1_identity_contract.py`
- `tests/test_stage2_evidence_contract.py`
- `tests/test_stage3_narrative_contract.py`
- `tests/test_stage4_generation_budget.py`
- `tests/test_stage5_context_fidelity.py`
- `tests/test_stage9_gold_regression.py`
- `tests/test_stage10_absolute_quality.py`
- `tests/test_auto_repair_pipeline.py`
- `tests/test_completion_contract_v13.py`

### 真实样本

- `output/000651_格力电器_stage7_coldstart/`
- `output/002027_分众传媒_stage4_coldstart/`
- `output/002027_分众传媒_stage5_context_ab/`
- `output/002027_分众传媒_stage6_evidence_density/`
- `output/01502_金融街物业/`

不要修改旧样本作为新结果。新验收必须使用隔离输出目录。

---

## 10. 已完成阶段：V3 Phase A+B

> 2026-08-02 已完成实现。以下保留原始交付契约与验收条件，实际结果见第 16 节。

下一轮不要只写规划，也不要只改一个正则。至少完整交付以下一个阶段：

### Phase A：冻结 V3 契约

1. 新增 `docs/QUALITY_SCORECARD_V3_SPEC.md`，把第 5、6 节裁决写成明确机器行为。
2. 新增 schema，建议至少包括：
   - `schemas/decision_ledger.schema.json`；
   - `schemas/claim_evidence.schema.json`；
   - `schemas/competitive_explanation.schema.json`。
3. 定义 canonical metric IDs、scenario/date/basis/version/status 字段。
4. 明确哪些冲突 `INVALID`，哪些缺口 `INCOMPLETE`，哪些只 WARN。
5. 明确 V2 软雷达保留为诊断器，不再决定 V3 发布资格。

### Phase B：实现跨章一致性硬门

1. 实现 `decision_ledger` 生成/读取/验证器。
2. 首批至少覆盖：
   - market price/as-of；
   - GG base/FCFE/Normalized；
   - II；
   - `V_final` 与主要估值输出；
   - lambda/护城河衰减；
   - 要求回报率；
   - 价格安全边际与回报安全边际；
   - 仓位；
   - 买入/减仓/退出触发点。
3. 同值复用 canonical ID；不同值必须携带 scenario/date/basis/version 或 deprecated 解释。
4. 无解释冲突进入 `report_completion.py`，报告状态转 `INVALID`。
5. 生成 `decision_diff.json`，记录旧值、新值、原因、影响章节和是否改变动作。
6. 冻结通过验证的 ledger，普通局部 repair 不得改写。
7. 增加对抗测试：复现格力多版本 `V_final/lambda/r*/仓位/买点` 混用，并确认硬阻断。
8. 既有金融街物业与格力身份回归不得退化。

建议 Phase A+B 在同一轮完成，因为只有 schema 没有验证器没有实际价值；但不要在这一轮同时扩展到所有 claim graph 和后验校准，以免爆炸式改动。

### Phase A+B 验收条件

- 新 schema 有合法/非法 fixture 测试；
- 无解释的跨章冲突稳定失败；
- 明确情景、日期或口径差异稳定通过；
- deprecated 旧值不会污染最终动作；
- Ch0/Ch14/报告正文/decision manifest 的动作一致；
- 局部 repair 不能漂移 frozen ledger；
- V2 现有 94 项定向回归仍通过；
- 不真实调用 DeepSeek，不烧 API token；
- 完成后再选择一个隔离样本做 validation-only；真实重跑放到下一阶段，除非用户明确要求同轮执行。

---

## 11. V3 后续阶段路线

每轮至少完成一个阶段，避免把用户拖入零碎确认。

### Phase C：主张—证据支持关系

- 建立重大主张注册表和 claim/evidence graph；
- 复合来源逐组件验证，关闭合法来源掩盖虚假组件的逃逸口；
- 来源权威性 × 与主张距离二维评级；
- 加入日期、口径、利益冲突、同源转载去重和循环引用检测；
- 无数字断言改为 N/A，不自动满分；
- 支持表格级来源映射。

### Phase D：估值模型与决策有效性

- 模型适用性；
- 口径一致性；
- `r-g` 安全距离；
- 终值依赖；
- 参数脆弱性和动作翻转；
- 多模型独立性；
- 估值结果到仓位/买点的动作映射。

### Phase E：竞争性解释、阈值和概率

- 核心 thesis 的完整替代解释；
- 区分性观察和翻转条件；
- 阈值依据与伪精确检查；
- 概率 provenance、互斥完备和不确定性表达。

### Phase F：历史参考、表达和后验校准

- 历史全文退化降为 WARN，核心事实无解释丢失才 FAIL；
- decision diff 取代全文相似度锁定；
- 表达只评效率，不抵消硬错误；
- 建立过程与决策后验记录；
- 多行业人工盲评校准。

### 最终真实验收

完成 V3 硬门后，用新的隔离零章节样本跑一次完整 unified 管线。验收顺序：

1. 数据、身份和研究执行；
2. 跨章一致性；
3. 主张—证据；
4. 模型适用性和敏感性；
5. 竞争性解释和动作映射；
6. 人工阅读质量；
7. 最后才看 token 和调用数。

---

## 12. 当前可复现测试基线

本交接文档生成前实际运行：

```bash
.venv/bin/python -m pytest -q \
  tests/test_stage1_identity_contract.py \
  tests/test_stage2_evidence_contract.py \
  tests/test_stage3_narrative_contract.py \
  tests/test_stage4_generation_budget.py \
  tests/test_stage5_context_fidelity.py \
  tests/test_stage9_gold_regression.py \
  tests/test_stage10_absolute_quality.py \
  tests/test_auto_repair_pipeline.py \
  tests/test_completion_contract_v13.py
```

结果：`94 passed in 3.51s`。

这是定向基线，不代表全仓测试全绿。历史上全仓测试曾因删除的旧 coordinator、缺少 `tushare`、旧 prompt/refresh/cache 测试与现实现漂移而失败；接手 agent 不得把定向 94 passed 宣称成全仓全绿。

---

## 13. 新账号可直接复制的启动提示

```text
请接手 /Users/xiami/workspace/analy/Turtle_investment_framework。

先完整阅读：
1. docs/HANDOFF_ACCOUNT_SWITCH_2026-08-02.md
2. AGENTS.md
3. output/01502_金融街物业/HANDOFF_v13.md（重点第9-15节）
4. docs/QUALITY_SCORECARD_V2_AUDIT_SPEC.md
5. docs/QUALITY_EVALUATION_V13.md

然后只读检查 git status、git diff --stat，并运行交接文档第12节的94项定向回归。不要 git pull/reset/checkout/clean，不要读取或输出 .env/analyze.sh 中的密钥，不要恢复多 Agent 分章写作，也不要为了省 token 降低质量。

确认基线后，从交接文档第11节继续完整实施 V3 Phase C：主张—证据支持关系、复合来源逐组件验证、二维来源评级、无数字断言 N/A 和表格级来源映射。一次完成该阶段，不要只给方案；冻结 decision ledger，不要真实调用 DeepSeek。完成后报告改动、测试和剩余风险。
```

---

## 14. 换账号恢复方式

在当前账户退出前保存本文件。切换账户后，在同一仓库尝试：

```bash
codex logout
codex login
cd /Users/xiami/workspace/analy/Turtle_investment_framework
codex resume --last
```

若恢复的不是本会话：

```bash
codex resume --all
```

若跨账户线程不能恢复，直接新建会话并粘贴第 13 节提示。项目文件和工作树都在本机，不依赖旧账号；本文件用于替代无法继承的隐藏会话上下文。

---

## 15. 交接完成定义

新 agent 只有在以下内容都理解后才算接手完成：

- 知道质量优先、自动生成、单 Agent 全局上下文三条不可退让原则；
- 知道 V2 是审计器，不是最终投资质量评分卡；
- 知道 V3 第一优先级是跨章参数和决策一致性；
- 知道 V3 Phase A+B 已实现、Phase C–F 尚未实现，不能沿用 V2 总分替代硬门；
- 知道当前工作树巨大且分叉，不能清理或同步；
- 能复现 111 项定向测试；
- 能从 Phase C 直接开始实施，而不是让用户再重复背景。

---

## 16. 2026-08-02 V3 Phase A+B 完成

### 已落地

- 新增 `docs/QUALITY_SCORECARD_V3_SPEC.md`，冻结 V3 状态机、门控关系、canonical IDs、冻结/diff 和后续 claim/model/competition 边界。
- 新增三份 Draft 2020-12 schema：
  - `schemas/decision_ledger.schema.json`；
  - `schemas/claim_evidence.schema.json`；
  - `schemas/competitive_explanation.schema.json`。
- 新增 `scripts/decision_ledger.py`：
  - 新 unified run 绑定 `decision_ledger_policy.json`；
  - 验证 15 类关键价格、回报、估值、衰减、仓位和触发器身份；
  - 相同 metric 只有在 scenario/date/basis 不同或旧值 deprecated 时才允许多值；
  - 正文关键值用 `[decision: entry_id]` 绑定；
  - manifest、ledger 和正文仓位/动作对齐；
  - frozen fingerprint 防止局部修复静默漂移；
  - `decision_diff.json` 记录 INITIALIZED/NO_CHANGE/REJECTED_FROZEN，以及动作和影响章节。
- `report_completion.py` 接入 V3：冲突映射 `INVALID`，缺失映射 `INCOMPLETE`，两者都禁止正式发布。
- `write_tools.py` 新增 LLM 工具 `write_decision_ledger`；不完整 ledger 不能冻结，冻结 ledger 也会反向保护 `decision_manifest.json`。
- `agent_loop.py` 和 `run.py` 已接入自动生成顺序、非决策 repair 双冻结和 V3 repair target 路由。
- `templates/report_template_v12.md` 要求关键参数同时带 source 与 decision identity。
- 修复 λ 身份边界：V_final 的护城河 λ 不会再与 Factor 3 的经营敏感度 λ 用一个宽泛正则混为一谈。

### 对抗验证

- 同一 V_final 同情景/日期/口径出现 49.68 与 70.4：`INVALID`。
- V_final 的 bear/base、不同日期或 EPV-only basis：允许。
- r*=7.5% 作为明确 deprecated 旧口径并指向 r*=10%：不污染 active 决策。
- 正文引用 ledger ID 但数字不符：`INVALID`。
- 正文出现关键参数但未绑定 decision ID：`INCOMPLETE`。
- 新 unified policy 下缺 ledger：`INCOMPLETE`。
- frozen ledger 的 V_final 漂移：拒绝写入，保留原值并生成 `REJECTED_FROZEN` diff。
- frozen ledger 同样拒绝 manifest 仓位/动作漂移。
- Ch0 + Ch14 + manifest + ledger 一致时可到 `COMPLETE`。
- 存量目录没有 policy/ledger 时为 `SKIP`，没有误杀旧报告。

### 测试基线

本阶段新增 `tests/test_stage11_decision_ledger.py`，并扩充自动修复测试。Stage 1–11、自动修复和完成契约定向回归：`111 passed`。Python 语法检查及三份 JSON 文件语法检查通过。

没有调用 DeepSeek，没有改动任何真实报告或旧样本，没有运行真实 cold start。当前未完成的是 Phase C 的 claim—evidence 支持关系、Phase D 的模型适用性和 Phase E 的竞争性解释/阈值/概率；不得把 Phase A+B 宣称为整个 V3 已完成。

下一阶段从第 11 节 Phase C 开始。

---

## 17. 2026-08-02 V3 Phase C 完成

### 已落地

- 新增 `scripts/claim_evidence.py`，实现 policy、重大主张账本、validation、freeze fingerprint 与 rejected diff。
- 重大主张用 `[claim: claim_id]` 绑定正文，并闭环原始事实、推理步骤、竞争解释、适用条件、概率身份及对估值/仓位/动作的影响。
- evidence 使用二维 `authority × claim_distance`；同时记录发布时间、数据截止日、口径匹配、利益冲突和同源组。
- 直接支持若来自报告内部循环、来源未知或口径 mismatch，状态为 `INVALID`；必要链条或章节绑定缺失为 `INCOMPLETE`。
- `scripts/evidence_citation.py` 已关闭“一个真来源掩盖复合锚点中伪来源”的逃逸路径。
- 无数字断言的邻证维度改为 `N/A`，评分按实际适用维度重新归一，不再白送 100%。
- 新增 `[table-source: X]`，紧邻 Markdown 表格即可映射整表，并进入验证、来源清单和脚注。
- completion、unified policy、自动 repair 路由、Agent 写作顺序和 `write_claim_evidence_ledger` 已接入。
- 决策账本仍冻结；重大主张账本冻结后也只允许幂等写入，局部 repair 不能静默漂移 thesis。

### 对抗验证

- `compute_bundle.json + invented_database`：未知组件保留并硬失败。
- 无数字断言：coverage 与 scorecard adjacency 均为 `N/A`。
- 表格级锚点：一次来源映射覆盖整表数字行。
- 报告内部自引作为直接支持或 `basis_match=mismatch` 却声明 direct support：`INVALID`。
- 多个网页复述同一原始来源：独立来源组仍为 1，并产生 warning。
- 正文未知 claim ID 或未知 decision entry：`INVALID`。
- 新 unified policy 缺 claim ledger：completion `INCOMPLETE`。
- frozen claim ledger 内容漂移：拒绝写入并记录 `REJECTED_FROZEN`。
- 存量目录无 policy/ledger：`SKIP`，没有误杀旧报告。

### 测试基线与边界

新增 `tests/test_stage12_claim_evidence.py`。Stage 1–5、9–12、自动修复和完成契约定向回归：`130 passed in 2.97s`；相关 Python 文件语法检查通过。

没有调用 DeepSeek，没有修改真实报告或旧样本，没有做真实 cold start。本次验收证明框架门控和自动调用链成立，不等于证明 LLM 首次生成就能稳定产出合格 claim ledger；该能力需要在 Phase D/E 完成后用金融街物业 cold start 验证。

下一阶段是 Phase D：模型适用性与脆弱性硬门。至少覆盖 DDM/DCF/EPV/资产价值适用条件，股权/企业价值与税前/税后、名义/实际口径，`r-g` 安全距离、终值依赖、敏感性翻转、多模型共享假设，以及估值输出与仓位/动作的一致映射。不得回退到“公式数量多就得高分”。
