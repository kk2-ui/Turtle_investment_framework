# Phase 01：官方证据平台

> 状态：COMPLETE ｜ 优先级：P0 ｜ 依赖：当前基线 ｜ 最后更新：2026-08-02

## 1. 要解决的问题

当前管线已经能读取PDF、网页和内部数据包，但“找到文件—定位原文—抽取事实—确认口径—写入报告”还不是一条稳定、可复核的数据链。非财务事实尤其容易出现四类问题：搜索摘要替代原文、读取截断不可见、未找到被推断为不存在、同一事实的年份或单位冲突没有传播到结论。

本阶段把证据构建成独立平台，先解决事实身份和回读闭环，再提高写作密度。它是后续决定性问题、行业路由、决策编译和长期校准的共同地基。

## 2. 目标与非目标

目标：

1. 为每份原始文件建立稳定身份、哈希、期间、权威等级和本地缓存记录。
2. 将事实抽取拆成候选与验证两个状态；只有已验证事实可支持重大主张。
3. 每个已验证事实都能回到文件、页码/章节/表格位置和原文片段。
4. 显式传播缺失、冲突、读取截断和OCR不确定性，禁止静默降级。
5. 生成确定性的 `report_context.json`，供统一管线消费。

非目标：

- 本阶段不建设数据库服务，先使用版本化JSON契约和文件缓存。
- 不选择公司最重要的问题；该能力属于Phase 02。
- 不重写估值模型和关键章节；分别属于Phase 03、Phase 04。
- 不以增加搜索次数、引用数量或报告长度作为完成标准。

## 3. 当前基线

- `scripts/build_report_context.py` 已有文件级上下文拼装，但尚未形成完整事实身份和验证状态。
- `scripts/turtle_agent/tools/read_tools.py`、PDF预处理及 `search_report` / `read_section` 已支持基础读取与游标。
- claim evidence ledger、来源身份和截断元数据已有局部实现，可作为下游接口。
- `docs/REPORT_CONTEXT_DESIGN.md` 是本阶段的设计输入，不代表能力已完成。
- 主干定向回归基线为 `254 passed`；全仓测试存在已知的可选依赖和嵌套旧仓库收集问题。

## 4. 接口与数据流

```text
本地缓存/交易所/公司公告/官方统计
        ↓
document_manifest.json
        ↓
定位、OCR、表格抽取和候选事实
        ↓
fact_observations.json
        ↓
身份、期间、单位、口径和冲突验证
        ↓
report_context.json + unresolved_gaps
        ↓
研究代理、claim evidence ledger、发布门
```

### 4.1 文档身份

文档ID采用：

```text
DOC:{market}:{code}:{doc_type}:{period_end}:{sha256前12位}
```

`document_manifest.json` 的最小字段：

- `doc_id`、`report_id`、`issuer`、`code`、`market`
- `doc_type`、`fiscal_period`、`period_end`、`published_at`
- `authority`、`source_url`、`local_path`
- `sha256`、`mime_type`、`language`、`acquisition_status`

同一内容的转载不得算作多个独立来源。文件内容变化必须产生新ID，URL变化但内容相同可以合并来源别名。

### 4.2 事实观察

观察ID由 `doc_id + locator + fact_name + normalized_value` 的规范化表示确定性生成。`fact_observations.json` 的最小字段：

- `observation_id`、`fact_name`、`domain`
- `raw_value`、`normalized_value`、`unit`、`currency`、`basis`、`as_of`
- `doc_id`、`locator.page/section/table/row/column/char`
- `raw_text`、`extraction_method`
- `status`：`CANDIDATE | VERIFIED | REJECTED | CONFLICT`
- `confidence`、`conflict_ids`

模型可以发现 `CANDIDATE`，但不能自行把它升级成 `VERIFIED`。升级必须通过可重放的程序校验或明确的人工复核记录。

### 4.3 报告上下文

`report_context.json` 至少包含：

- `meta`：公司、截止日、生成器版本和输入指纹
- `documents`：本次实际使用的文档ID
- `domains`：按财务、治理、行业、客户、资本配置等组织的已验证事实
- `unresolved_gaps`：缺失事实、已尝试路径、失败原因和对决策影响
- `coverage`：关键事实覆盖，不以文件数替代覆盖率
- `manifest_hash`、`context_fingerprint`

相同输入必须产生相同指纹和稳定排序。旧版上下文可读取，但进入新发布路径前必须迁移或标记 `INCOMPLETE`。

### 4.4 来源与回读顺序

1. 已缓存且哈希匹配的官方文件。
2. 交易所、监管机构和公司官方端点。
3. 官方统计或权威行业原始数据。
4. 搜索仅用于发现候选来源，不得把摘要直接升级为已验证事实。

PDF读取优先使用文本层；定位失败时依次使用页级回读、表格解析和OCR。每次读取必须记录页码范围、游标、截断状态和提取方法。

## 5. 实施工作包

### WP1：契约与确定性身份

- 为三个产物增加schema、版本号和示例。
- 实现文档ID、观察ID、排序和指纹算法。
- 对非法期间、单位、状态和孤立引用 fail closed。

出口：schema测试和重复运行确定性测试通过。

### WP2：官方文档发现与缓存

- 新增 `scripts/evidence_documents.py`，复用现有下载能力。
- 统一官方来源优先级、内容哈希、缓存命中和下载失败记录。
- 保存来源URL和取得时间，不覆盖不同内容版本。

出口：同一文件不重复下载；变更文件产生新版本；来源失败可观察。

### WP3：PDF精确读取

- 把页码、章节、表格和字符位置统一为locator。
- 将 `search_report` 的命中结果交给 `read_section` 精确回读。
- 对跨页表格、无文本层、乱码和截断建立显式降级状态。

出口：给定 observation 能稳定返回原文；无法定位时不能标记 VERIFIED。

### WP4：候选事实与验证

- 新增 `scripts/evidence_facts.py`，抽取候选值和口径。
- 校验期间、单位、币种、合并/母公司、存量/流量、同比/绝对值。
- 同一 canonical fact 存在不可解释差异时生成冲突组。

出口：候选、已验证、拒绝和冲突四条路径均有对抗测试。

### WP5：上下文装配

- 升级 `scripts/build_report_context.py` 消费 manifest 和 observations。
- 只将 VERIFIED 事实放入可引用域；其余进入 gaps/conflicts。
- 输出覆盖情况、来源距离和输入指纹。

出口：上下文可重复生成，且没有内部章节循环引用。

### WP6：统一管线集成

- 在读取工具中暴露文档和事实身份，不只返回自由文本。
- claim evidence ledger引用 observation ID；重大主张禁止只引用 CANDIDATE。
- 将关键事实冲突接入完成契约和V3硬门。

出口：自动运行无需人工复制证据，失败码正确传到顶层。

### WP7：真实样本验证

- 主样本：01502、000651、002027。
- 控制样本：02669，不参与规则调试。
- 每只至少验证一项财务事实、一项治理/行业事实、一项缺失或冲突路径。

出口：三只主样本和控制样本均生成可回读上下文，旧正式快照未被覆盖。

## 6. 质量门与失败语义

`INVALID`：文档身份/哈希错误；公司或期间错配；单位或币种冲突未解决；重大主张引用非 VERIFIED 事实；locator无法回读却声称已验证。

`INCOMPLETE`：决定估值或核心论点的事实缺失；官方文件读取失败；关键冲突尚未裁决。

`WARN`：非关键补充资料缺失；OCR置信度偏低但未用于重大主张；搜索发现线索尚未验证。

正常降级只能减少结论置信度或留下缺口，不得把“未找到”转换为“不存在”“规模很小”或“已经定价”。

## 7. 测试与真实验证

- schema：必填字段、枚举、版本兼容、孤立引用。
- 单元：哈希、ID、单位、期间、排序和fingerprint。
- 对抗：转载去重、年份错位、百分比/百分点、千元/百万元、合并/母公司、OCR误读。
- 集成：下载/缓存→定位→事实验证→context→claim ledger。
- 断点恢复：下载失败、读取截断、缓存损坏和中途终止。
- 兼容：旧context只能降级读取，不能绕开新硬门。
- 真实验证：三个主样本加一个控制样本。

## 8. 完成标准

- [x] 三个JSON接口有稳定schema和版本策略。
- [x] 所有获准进入VERIFIED集合的事实均可回到原始文档和locator。
- [x] CANDIDATE无法通过任何路径支持重大主张。
- [x] 关键冲突会阻断发布，非关键缺失会留下可见gap。
- [x] 相同输入的context fingerprint完全一致。
- [x] 原主干254项及本阶段新增13项定向测试全部通过；同时单独报告全仓已知问题。
- [x] 三个主样本和一个控制样本通过证据平台validation-only。
- [x] 未执行正式发布，不覆盖此前报告快照。

## 9. 迁移、回滚与剩余限制

新平台先以旁路产物运行；确认无误后才使新上下文成为默认输入。可通过配置临时回退旧context读取，但回退运行必须标记为legacy，不可获得 `DECISION_READY`。本阶段不解决问题优先级、模型适用性和长期案例校准。

## 10. 阶段完成摘要

完成日期：2026-08-02。

实际交付：

- 新增 `document_manifest.json`、`fact_observations.json`、`report_context.json` 三个版本化接口及schema。
- 原始文件使用内容哈希生成 `DOC:` 身份；事实使用文档、locator、事实名和值生成 `OBS:` 身份。
- 下载器以后自动保存 `document_sources.json`，记录URL、发布日期、取得时间和provider；历史缓存没有URL时显式WARN。
- 自动抽取仅将带逐页原文的事实标记为VERIFIED；旧 `pdf_sections` 数字因单位和locator未解决，只保留为CANDIDATE。
- `search_report` 返回页码、文档身份和CANDIDATE状态；`read_section` 返回文档身份、精确页窗、截断和续读信息。
- 新增 `verify_official_fact`：只有quote逐字存在于指定文档/页面，且数值出现在quote中，才能程序化升级。
- unified入口自动构建证据链并绑定政策；完成契约和V3成绩单加入不可补偿的official evidence硬门。
- 新 unified run 的claim direct support必须引用VERIFIED observation，且 `source_id` 与其 `DOC:` 身份一致；旧目录没有政策时保持SKIP。

测试与真实验证：

| 样本 | 文档 | VERIFIED | CANDIDATE | 已验证域 | 状态 |
|---|---:|---:|---:|---|---|
| 01502 金融街物业 | 5 | 18 | 25 | audit、operations | REVIEWABLE |
| 000651 格力电器 | 13 | 16 | 46 | audit | REVIEWABLE |
| 002027 分众传媒 | 6 | 12 | 34 | audit | REVIEWABLE |
| 02669 中海物业（控制） | 8 | 10 | 42 | audit、operations | REVIEWABLE |

- 最终主干定向回归：`267 passed`。
- 另跑下载器与Phase 01组合回归：`47 passed`。
- 全仓仍有既存收集问题：可选`tushare`未安装、嵌套旧仓库测试包重名；未将其误报为全仓全绿。

与计划的偏差及剩余限制：

- 没有另造官方网络下载器，而是把来源sidecar接入现有CNINFO/HKEX/回退下载路径。
- 历史PDF大多缺原始URL和发布日期，因此保留WARN；后续新下载会自动记录。
- 自动财务事实仍停在CANDIDATE，直到单位、合并口径和表格行列都能逐项确认；这是有意的fail-closed，不是遗漏。
- 当前自动VERIFIED主要覆盖审计和部分运营事实。治理、行业及资本配置由下一阶段选出决定性问题后，通过定向回读补齐，避免无目标地抽取全部年报。
