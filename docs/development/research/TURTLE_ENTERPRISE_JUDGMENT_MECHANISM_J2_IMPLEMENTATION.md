# Turtle EnterpriseJudgmentEpisode J2 机制线程实现

> 状态：`IMPLEMENTED / PRE_OUTCOME_ONLY / LOCAL_PERMISSION_PROJECTION / SYNTHETIC_REGRESSION_VERIFIED`
>
> 日期：2026-08-26
>
> 顶层语义：[企业判断与训练系统顶层架构](TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md) §3.1、§3.2、§10.1。

## 1. 交付物与对象边界

J2 将 J0 已冻结的机制线程骨架补成可执行的局部研究合同，并把其来源、责任边界和 operating loop 解析到 J1 reconstruction。它仍是只读组合层，不新增企业事实或平行账本。

- schema：`schemas/enterprise_judgment_mechanism_thread.schema.json`；
- validator/compiler：`scripts/enterprise_judgment_mechanism.py`；
- 定向回归：`tests/test_enterprise_judgment_mechanism.py`。

公开 API 为：

```python
validate_mechanism_thread_set(
    thread_set,
    episode_manifest=j0_manifest,
    reconstruction_read_model=j1_reconstruction,
    reconstruction_inputs=j1_compilation_inputs,
    reconstruction_registry=frozen_j1_registry,
)

compile_mechanism_thread_projection(
    thread_set,
    episode_manifest=j0_manifest,
    reconstruction_read_model=j1_reconstruction,
    reconstruction_inputs=j1_compilation_inputs,
    reconstruction_registry=frozen_j1_registry,
)
```

`reconstruction_inputs` 闭合保存 J1 spec、SourcePacketReceipt、SourcePackage、EnterpriseSystemModel、DecisionLedger 与 DecisionContract。J2 调用 J1 的 `validate_compiled_reconstruction` 重新编译并逐对象比较；提供 registry 时还要求 reconstruction 与 inputs 等于已登记的 Frozen J1 bundle。J3/J4 公共入口强制提供该 registry，因此不能让一份同步篡改 receipt/source 的 J1 read model 自证来源。两者均为 pure/offline API，不读网络、结果包、Forecast 或 Comparative，也不修改 J0/J1 输入；registry 仅作调用方提供的只读 trust root。

## 2. 闭合线程合同

一个 J2 set 必须有且仅有一个 `PRIMARY` 与 2--4 个 `SUPPORTING` thread。每个 thread 必须显式保存：

1. J0 `thread_id`、依赖 claim、角色与完全相同的 H-A/H-B；
2. `DESCRIPTIVE_STRUCTURE`、`WITHIN_CASE_MECHANISM`、`LIFECYCLE_TRANSITION` 或 `RELATIVE_CAUSAL` claim type；
3. 单一 `responsibility_unit_id × arena_id` 责任边界，以及 J1 loop refs；
4. 同时写明 H-A/H-B 预期观察的 evidence discriminator；
5. `opens_at >= cutoff` 且 `due_at > opens_at` 的 observation clock；
6. J0 outcome-cell refs 与 J1 source refs；
7. source 的 cutoff 前 `available_at` 与 `CUTOFF_VISIBLE` information role；
8. thread-local status、`CONTEXT / TEACHING / MECHANISM` evidence ceiling、独立 permitted outputs；
9. 是否明确请求 E3 Comparative；
10. 仅对 `RELATIVE_CAUSAL / E3`，在 J4 前冻结
    `comparative_projection_contract`：H-A/H-B 的同一机制身份、每个 J0 outcome
    cell 对应的一份完整 V5 measurement contract，以及 J1/J2/V5 来源链。

J2 不允许声明 `COMPARATIVE` 或 `TRANSFERRED` evidence ceiling。`RELATIVE_CAUSAL` 与 `e3_comparative_requested=true` 必须成对出现；该布尔值只记录路由请求，不代表 E3 已准入或执行。

Comparative contract 不是调用 J4 时临时填写的解释表。J2 要求 V5 hypothesis
ID/机制文本与 J2 的 H-A/H-B 完全一致；每个 outcome cell 只绑定一份完整 V5
measurement contract，且 `metric_id` 必须等于 J0 已冻结的
`measurement_contract_ref`；J1 receipt 与 J2 source refs 也必须原样进入来源链。
V5-owned measurement/source 对象由 J2 保存但不重复解释，最终仍由现有 V5
validator 裁决。

## 3. 硬拒绝与局部降级

以下属于合同本身失真，validator 直接拒绝整个 J2 set：

- schema、数量、唯一 primary、H-A/H-B、日期或 permission 形状错误；
- J1 reconstruction 不能由所绑定的完整 J1 输入精确重放；
- source 在 cutoff 后可得，或 information role 为 outcome/post-cutoff；
- pre-outcome narrative 引用股价、股票/股东回报、实际结果、post-cutoff 或 later survival；
- 输出中加入 Forecast、Comparative、估值或投资权限；
- 把局部线程写成企业整体、普遍或永久的高质量升级。

以下属于局部解析失败，不令其他 thread 或 claim 失效：

- J0 中缺少该 detailed thread，或角色、claim、H-A/H-B、clock、outcome cell 不匹配；
- J1 loop/source 不存在；
- loop 或 source 不覆盖 thread 的责任边界；
- source 为 `EVIDENCE_INELIGIBLE`；
- local status 为 `UNKNOWN`、`EVIDENCE_INELIGIBLE` 或 `NOT_APPLICABLE`。

缺失、篡改或不完整的 `comparative_projection_contract` 只关闭该 thread 的 J4
资格；它写入独立的 `comparative_contract_findings`，不改变 J2
`resolution_status`、E0--E2 claim 权限、其他 thread 或 IndustryLearningBlock。

compiler 对这些 thread 输出 `resolution_status=BOUNDARY_ONLY`、具体 `binding_findings` 与 `permitted_outputs=[RESEARCH_AGENDA]`。只有 J0 明确挂在该 thread 上的 claim 被降级；无依赖 claim 保留 J0 权限，其他 resolved thread 继续保留自己的 `TEACHING_ONLY` 或 `MECHANISM_CANDIDATE`。因此局部缺失不会生成 episode 级 `PASS/FAIL`。

## 4. 权限与 J3/J4 路由标记

线程权限由 local status 与 evidence ceiling 机械决定：

| evidence ceiling | active thread permitted outputs |
|---|---|
| `CONTEXT` | `RESEARCH_AGENDA` |
| `TEACHING` | `MECHANISM_VIEW`、`TEACHING_ONLY`、`RESEARCH_AGENDA` |
| `MECHANISM` | `MECHANISM_VIEW`、`TEACHING_ONLY`、`MECHANISM_CANDIDATE`、`RESEARCH_AGENDA` |

blocking local status 或引用解析失败只保留 `RESEARCH_AGENDA`。

`j3_forecast_eligible` 是 J2 的路由标记，不是 Forecast：只有 resolved、active、非 `RELATIVE_CAUSAL` 且其 J0 claim 未被自身 cell 阻断的 thread 才标记为 true。`j4_comparative_eligible` 也只是路由标记：它还要求 exact `RELATIVE_CAUSAL`、显式 E3 请求、`MECHANISM` ceiling 和有效的预冻结 Comparative contract。read model 同时保留 H-A/H-B、责任边界、outcome-cell refs、已解析 source refs 与该 contract，供 J3/J4 逐项复核，不能由下游只翻转一个 eligibility boolean。`e3_comparative_requested` 原样保留显式请求；projection 同时固定：

```text
forecast_performed = false
comparative_performed = false
forecast_authorization = NOT_AUTHORIZED
comparative_authorization = NOT_AUTHORIZED
investment_authorization = NOT_AUTHORIZED
```

E3 缺失不会阻断 J2。J2 也不会从 Forecast 生成因果结论，或从 E3 request 生成 comparator/panel/estimand。

## 5. 无行动 E1

J2 没有 action ID、implementation status 或 comparator 前置条件。一个 J1 reconstruction 可以合法保留 `NO_MATERIAL_DECISION_OBSERVED` 和空 decision ledger；只要 thread 描述的是 cutoff-visible company state 或局部 operating mechanism，并满足自己的来源、边界、H-A/H-B 与 observation clock，它仍可形成 J2 read model。

若某个 J0 claim 明确采用 `ACTION_DEPENDENT`，J0 已负责将无行动路线局部标记为 `NOT_APPLICABLE`。J2 继承该 claim blocker，不把它扩散到其他企业状态或机制线程，也不把“没有观察到行动”改写成行动。

## 6. 验收覆盖

定向回归覆盖：

1. 一个 primary 与两个 supporting thread 的独立 evidence ceiling 和 permissions；
2. `NO_MATERIAL_DECISION_OBSERVED` 与空 ledger 下的合法 J2 projection；
3. unknown source 和缺失 detailed thread 只阻断依赖 claim；
4. 每条 thread 的 J3 eligibility 与显式 E3 request 标记，且不执行两者；
5. cutoff 后 source、价格/证券回报/结果 narrative、普遍公司质量升级的硬拒绝，同时允许 ROIC/经营资本回报等正常经营语言；
6. H-A/H-B、permission 和 E3 request/claim type 配对的负例；
7. 同步篡改 J1 receipt/source 仍因完整重放不等而拒绝；
8. Comparative contract 缺失只关闭 J4，且机制、测量或来源漂移不能替换 J2
   已冻结的问题；
9. schema 闭合、3--5 thread 数量约束与无 Forecast/Comparative 输出。
