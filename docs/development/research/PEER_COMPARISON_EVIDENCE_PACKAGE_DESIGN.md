# 同行竞争对照证据包：PIT 契约

状态：`PRE_REGISTERED / NOT_ACTIVATED / CONTEXT_ONLY_ZERO_SAMPLE`  
用途：仅为格力的竞争机制提供受限外部对照；不是同行报告、不是参考类案例、不是估值比较，也不应立即下载任何同行正文。

## 为什么不能直接使用现有同行工具

现有 `industry_context.json`、`get_peer_comparison` 与 `get_global_benchmarks` 没有逐源 `published_at`、原始响应、PIT cutoff 或可比性合同；后两条路径还会引入实时网页、同行 PE/PB 和当前市场数据。它们会把后来的同行经营或价格混入格力经营盲轨，因此不能作为本包的来源或验收证据。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`，经济影响是将后视同行数据或相对估值伪装为竞争机制。格力公司盲轨在没有合格同行包时仍可继续；竞争层须诚实保留 `UNKNOWN` 或范围受限的观察。

## 对象与用途限制

```text
各同行独立官方 PIT source package
        ↓ 只读、带各自 allowlist 与 cutoff
PCEP：仅回答格力一个竞争机制问题
        ↓
格力 financial_driver_bridge.competitive_context
        ↓
格力竞争解释 / mechanism chain / 自己的 forward judgment
```

最小 `peer-comparison-evidence-package.v1` 应有：

```json
{
  "package_id": "PCEP:000651.SZ:<gree-cutoff>:competition.v1",
  "status": "NOT_ACTIVATED|PRE_REGISTERED_SELECTION|REVIEWABLE",
  "target": {
    "company_id": "000651.SZ",
    "cutoff_at": "...",
    "research_question_ids": ["DQ-GREE-COMPETITIVE-NORMALIZATION"],
    "financial_driver_ids": ["FDBDRV:..."]
  },
  "use_policy": {
    "purpose": "GREE_COMPETITION_CONTEXT_ONLY",
    "allowed_consumers": ["financial_driver_bridge.competitive_context", "thesis_test.competitive_tests"],
    "forbidden_consumers": ["valuation_direct_input", "price_or_relative_multiple", "baseline", "forward_judgment_outcome", "investment_decision", "base_rate_context", "case_or_episode_registration"]
  },
  "counting": {
    "statistical_role": "CONTEXT_ONLY",
    "base_rate_eligible": false,
    "independent_sample_increment": 0
  }
}
```

## 预注册选择规则

1. 先冻结格力的竞争问题、主/竞争机制、市场定义、客户替代和需要判别的 metric，后选择同行；美的、海尔等名称目前只是候选，不因规模或常识自动入选。
2. 每个同行单独建立完整官方 inventory，并以**格力同一 cutoff**运行现有 Phase10 admission。日期精度同日、cutoff 后披露、后续修订和当前 restatement 都必须保留在拒绝记录中。
3. 每个被物化的同行 source 必须写明格力 `comparison_id`、`driver_id`、服务的机制问题、预期字段、可比较口径、可证明边界和不可证明边界；发现支持/反对格力结论后不得临时加料。
4. 最小对照不是“一家同行的一份年报”，而是：一条格力已验证 observation、一条同 cutoff 的同行一手披露或官方行业统计、以及明确产品/地区/渠道/客户/期间和 sell-in/sell-out 边界。
5. 只要存在单一同行 KPI，最多形成狭义的渠道或产品对照；要主张广泛竞争位置，须有同口径官方行业观察或预选的近似反例。

## 可比性与引用身份

同行事实不复制为格力事实。应使用只读 `PCOBS:<package>:<observation>` 引用，其中带同行发行人、source ID、manifest/selection 身份、页码、measurement basis 与 period。格力 `competitive_context` 另设 `comparison_evidence_refs`；本地 `comparison_observation_ids` 只保留格力自己的 `OBS:`。

每个对照问题应冻结：

- `market_definition`、客户替代和目标机制；
- 格力/同行各自所需 measure 与共同 measurement basis；
- 期间对齐和口径漂移规则；
- `scope_limit` 与禁止推断；
- `strongest_near_miss`：为何表面相近但结果相反会挑战格力机制。

同行资料只能作为格力竞争 driver 的 `QUALITATIVE_GUARDRAIL` 或明确 sensitivity 边界；不得直接成为格力收入、毛利、owner cash、终值、估值倍数、概率或 action 的数值输入。

## 生命周期与接纳

| 状态 | 条件 | 可否引用 |
|---|---|---|
| `NOT_ACTIVATED` | 只有路线设计；无同行 inventory、无正文。 | 否。 |
| `PRE_REGISTERED_SELECTION` | 完整元数据 inventory、候选角色、逐源理由与选择时间已审。 | 否。 |
| `REVIEWABLE` | 同行 package 已物化；`PCOBS` 通过页级验证、PIT 和可比性审阅。 | 仅指定的格力竞争 context。 |
| `ACCEPTED_FOR_GREE_COMPETITION_CONTEXT` | 独立审阅确认冻结身份已写入格力 snapshot，且没有越权消费者。 | 仅格力指定 competition driver/test。 |
| `INSUFFICIENT` | 口径不符、无可审计发布时间或无官方材料。 | 否；格力层保留 `UNKNOWN`。 |

验收必须拒绝：使用 `get_peer_comparison`、`get_global_benchmarks`、web 实时数据、同行 PE/PB、cutoff 后或同日无时刻披露；把 `PCOBS:` 写成格力 `OBS:`；以多份同行公告增加样本数；或把对照升级为 `CASE:`、`MEP:`、`base_rate`/outcome 字段。

## 可复用模块

- `phase10_acquisition.py`：同行各自的 inventory、admission、`source_package_selection.v2` 和逐源理由；
- `phase10_pit_runner.py`：成员包 allowlist、来源身份和 read audit；
- `evidence_documents.py`、`evidence_facts.py`：同行包内的页级事实验证；
- `financial_driver_bridge.py`：市场定义、客户替代、范围和模型/决策绑定；
- `base_rate_case_library.py`：只用其现有独立性约束，PCEP 本身不得调用 case/episode 注册。

本包的价值不是“增加同行报告数”，而是把同行材料永久限制为一个可审阅的竞争问题的外部上下文，避免它变成前视信息、相对估值捷径或伪基准率样本。
