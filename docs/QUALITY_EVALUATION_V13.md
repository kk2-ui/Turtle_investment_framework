# V13 质量评估：历史防退化与绝对质量

> 评分卡的完整算法、阈值、词表、已知逃逸口和待裁决问题，见 `docs/QUALITY_SCORECARD_V2_AUDIT_SPEC.md`。
>
> V3 已在其外层增加跨章决策身份硬门；规范见 `docs/QUALITY_SCORECARD_V3_SPEC.md`。V2 A/B/C/D 继续只作诊断，不能覆盖 V3 的 `INVALID/INCOMPLETE`。

## V3 发布前置门

新 unified run 会生成 `decision_ledger_policy.json` 并强制要求 `decision_ledger.json`。价格、三种 GG、II、V_final、λ、要求回报率、护城河衰减、双安全边际、仓位和触发器必须有 canonical identity，正文以 `[decision: entry_id]` 绑定。

- 无解释的跨章/跨版本冲突：`INVALID`，阻断发布；
- 缺关键身份、来源或正文绑定：`INCOMPLETE`，阻断发布；
- 明确 scenario/date/basis 的多值：允许；
- 明确 deprecated 且指向替代值的旧版本：不进入最终动作；
- frozen ledger 的局部改写：拒绝并记录 `decision_diff.json`。

存量目录既无 policy 也无 ledger 时暂时 `SKIP`，只用于迁移兼容。

## 两套评估不能混用

### 历史参考防退化

历史较优稿可能仍有冗余、空泛或错误，因此只承担保险丝作用：检测新稿是否大量丢失旧稿已有的主题、分析、推导或证据。它不提供质量真值，也不要求复制旧稿。

- `FAIL`：信息保留率低于硬阈值，阻断发布。
- `WARN`：相对旧稿减少，仅供检查。
- `SKIP`：该公司没有历史参考。

配置：`config/legacy_reference_regression.json`

### 硬契约 + 软质量雷达

质量评估不读取任何旧报告。V2 将“能否发布”和“写得多好”拆开，避免启发式文本分数冒充硬事实。

硬契约只处理可重现的客观失败：

1. 章节文件缺失；
2. `[source: ...]` 存在无法解析的来源组件；
3. 开启 `source_deepening` 后，`research_execution.json` 显示未实际读取该章规定的年报章节。

此外，原有 completion contract 仍独立硬阻断结构缺失、深度不足、audit 失败、估值推导缺失与决策身份冲突。

软质量雷达直接检查当前章节是否完成研究任务：

1. 研究问题回答 15%；
2. 事实→机制→财务→估值/决策的因果闭环 20%；
3. 数字断言与附近证据的相邻性 20%；
4. 一手年报、结构化真源和已读网页的来源质量 10%；
5. 支持证据与最强反证 10%；
6. 可量化、可证伪的更新阈值 10%；
7. 公式、情景和口径推导 10%；
8. 重复与空泛话术控制 5%。

等级为 A（≥85 且无维度预警）、B（≥72）、C（≥60）、D（<60）。数字只用于排序修复优先级，对外只应解读等级、维度和具体证据，不应声称“76 分比 75 分客观更好”。

## 片段级样例

`quality_examples/reasoning_fragments.json` 只保存推理结构，例如因果闭环、反证、可证伪触发器和估值冲突裁决。样例不是公司事实，不允许原样填充报告，也不引用旧报告全文。

## 自动管线接入

- `--unified` 和 `analyze.sh` 默认开启来源深化；仅调试或兼容时显式使用 `--no-source-deepening`。
- 来源门按章节研究计划执行：例如 Ch2/Ch8 要求有效 `web_search + web_fetch`，纯估值章不为凑工具调用强制无关网搜。
- `read_report_contract_pack` 同时返回逐章 `research_plan` 与适用的推理结构样例。
- 每次真实的 `read_section/search_report/web_search/web_fetch` 会落盘到 `research_execution.json`；台账与当前 pipeline `run_id` 绑定，不能沿用上一轮读取记录，正文里写出工具名也不能伪造完成。
- `report_completion.py` 分别运行历史参考、硬契约和软质量雷达。
- 机器产物：`legacy_reference_regression.json`、`absolute_quality_scorecard.json`。
- 人读产物：同名 Markdown 文件。

## 当前边界

雷达使用确定性文本信号，优点是可复现、可回归；它仍不能完全理解隐含因果、表格级共享引用或同义表达。关键词必须与有数字、来源或因果影响的实质内容共现，但任何静态规则仍可被刻意游戏化。因此语义缺口只保持 WARN，后续应用多行业人工盲评样本继续校准。
