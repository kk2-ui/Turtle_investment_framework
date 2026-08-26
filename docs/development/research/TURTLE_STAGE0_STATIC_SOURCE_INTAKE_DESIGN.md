# Turtle Stage-0 静态来源包接收设计

状态：`IMPLEMENTED / V5_PEER_PANEL_RUNTIME / H1_RECEIPT_REGISTERED / H2_NOT_STARTED / REGISTRY_AWARE_RECRUITMENT_IMPLEMENTED`
更新：2026-08-25

适用范围：本文是当前 `RELATIVE_CAUSAL / V5_PEER_PANEL` 的运行时 H1/H2 契约，不是 Industry History Universe、Teaching Case 或 Lifecycle Case 的准入门。[历史训练体系重构](TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)已经设计 freeze 前 append-only carrier registry，但实现迁移前，本文的 closed-roster validator 仍是执行真源，禁止手工绕过。

## 1. 要解决的实际缺口

`COHORT:CN:CEMENT_LISTED:20180430` 的新 H1 static package 已通过 `STAGE0_FEASIBILITY_REVIEWABLE` 并登记 immutable receipt。五家 disclosure carriers 中，`600801` 与 `000401` 已有 material scope/control break，不能进入不匹配的 V4 最终 panel；其余三家不足以支持 target 加至少三家 peer。五家公司仍可进入 Industry History Universe，break 成员也可承载 Teaching/Lifecycle，不因 final-panel 权限不足而删除。

更重要的是，“中国水泥上市公司”只说明产品类别，并不说明与具体行动机制相符的共同竞争场、客户终端市场或同一外生冲击。因此补两家任意水泥上市公司不能解决最终 panel 的可比性问题。共同竞争场可为全国、区域、出口、细分市场或多区域组合；只有当机制是区域竞争时，地理重叠才是硬门。

因此该 H1 receipt 是有效的 source-intake 入口，但仍为 `INSUFFICIENT_FOR_V4_FINAL_PANEL`；原因是容量不足且尚未针对任一行动机制证明共同竞争场，并非“全国水泥”天然不合格。旧 feasibility prototype 的 `STAGE0_REJECTED` 不能覆盖新 receipt，新 receipt 的通过也不能冒充 final-panel 通过。

当前 runtime 不允许在 H2 增加公司，故不能手工向 receipt“补两家公司”。分层迁移完成后，原 receipt 仍不可修改，但 curator 可在 outcome 读取和 Comparative Panel Freeze 前按冻结 eligibility predicate 追加独立 static peer-recruitment batch；这不是扩写 receipt，也不能自由挑选同行。

已验证的 CNINFO Web 前端还会忽略日期 query 参数并先渲染当前公告。故 Stage-0 不能再以 issuer/fulltext/stock/detail 页面，或未验证参数生效的行业关键词页面作为来源发现入口。

## 2. 可执行的非 UI 接收边界

新的 curator 只交付一个离线的、cutoff-before 的 static-PDF identity package；研究 agent 不负责搜索、补全或猜测身份。该 package 是 H1 acquisition receipt，不是 V5 `selection_bundle`，不含 action、focal target、最终 peer、共同驱动结论或 outcome。

每一个候选成员须由 curator 提供以下原件 identity：

完整 root 仍须带 `cohort_id`、`industry_id`、`cohort_eligibility_as_of`（与 `selection_as_of` 完全相同）、`arena_family`、既有的 `universe` 和 **五个** `members[]`；每个 member 保留 `company_id`、`issuer_id`、`responsibility_unit_id`、`control_group_id`、listed-consolidated `boundary`、control/business evidence、三期 `d2_field_availability` 与五期 `annual_d3_d4_availability`。下列 `issuer` 是其中一个 member 的 identity 摘要；实际 package 将五个摘要及其字段记录放在 `members[]`，并让每个 member 的 `competitive_arena_id` 等于 root arena ID、`carrier_identity_source_ids` 引用其自身的 static PDF。

```json
{
  "schema_version": "judgment-selection-stage0-static-package.v1",
  "entry_kind": "CURATOR_SUPPLIED_CUTOFF_BEFORE_STATIC_CNINFO_PDF_PACKAGE",
  "selection_as_of": "2018-04-30T23:59:59+08:00",
  "cohort_eligibility_as_of": "2018-04-30T23:59:59+08:00",
  "arena_family": "CN:CEMENT:<mechanism-market-family>",
  "mechanism_topology": "CUSTOMER_RESPONSE | COST_RESTRUCTURING",
  "current_admission_assessment": {
    "status": "FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE",
    "reason": "At least five independent, continuous-perimeter issuers establish the stated mechanism-defined arena family before action selection."
  },
  "issuer": {
    "company_id": "CN:<code>",
    "issuer_id": "ISSUER:CN:<code>",
    "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:<code>",
    "control_group_id": "CONTROL:<ultimate-controller>",
    "boundary": {
      "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:<code>",
      "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
      "unit": "RMB"
    },
    "competitive_arena_id": "CN:CEMENT:<frozen-mechanism-market>",
    "carrier_identity_source_ids": ["CNINFO:<code>:ANN:<YYYYMMDD>:<announcement-id>"]
  },
  "competitive_arena": {
    "competitive_arena_id": "CN:CEMENT:<frozen-mechanism-market>",
    "market_scope_type": "NATIONAL | REGIONAL | EXPORT | SEGMENT | MULTI_REGION_PORTFOLIO",
    "product_or_service_scope": "CEMENT_AND_CLINKER",
    "geographic_scope": "<national, region, export destination, segment footprint or portfolio map>",
    "customer_end_market_scope": "INFRASTRUCTURE_AND_REAL_ESTATE",
    "evidence": [{"source_id": "<static source ID>", "field_ref": "<PDF p. N>"}]
  },
  "static_pdf_sources": [
    {
      "source_id": "CNINFO:<code>:ANN:<YYYYMMDD>:<announcement-id>",
      "url": "https://static.cninfo.com.cn/finalpage/<YYYY-MM-DD>/<announcement-id>.PDF",
      "published_at": "<YYYY-MM-DD>",
      "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
      "period_end": "<YYYY-12-31>",
      "issuer_id": "ISSUER:CN:<code>",
      "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:<code>",
      "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
      "unit": "RMB",
      "field_refs": ["control PDF p. N", "business PDF p. N", "D2 PDF p. N", "D3 PDF p. N", "D4 PDF p. N"]
    }
  ],
  "curator_attestation": {
    "issuer_code_or_name_submitted_to_cninfo_fulltext": false,
    "cninfo_issuer_stock_or_detail_page_opened": false,
    "post_identification_access": "PREDECLARED_CUTOFF_BEFORE_STATIC_CNINFO_PDF_PACKAGE_ONLY",
    "post_cutoff_metadata_or_body_read": false
  }
}
```

接收 agent 只做四件事：

1. 检查每个 URL 为 `https://static.cninfo.com.cn/finalpage/...PDF`，日期精度的发布日期严格早于 cohort `selection_as_of`；
2. 检查五年不同 period 的合并 D3/D4、三期候选 D2 或成本字段 identity，以及控制权、主营、`market_scope_type`、产品、客户和足以说明 arena family 的地理/市场暴露均有原件页码。每一条三期/五期 identity 的 `period_end` 必须等于其 static PDF declaration 的 `period_end`，不得用一份晚年报伪造历史容量。`CUSTOMER_RESPONSE` 必须提交 `d2_field_availability`；`COST_RESTRUCTURING` 必须提交经期次绑定的 `d2_field_availability`、`cost_field_availability={field_id,cost_driver_kind,definition,repetitions}` 之一或两者。存在成本字段时，`cost_driver_kind` 只能是 `ENERGY_INPUT_COST`、`LABOR_COST`、`LOGISTICS_COST`、`FIXED_COST`、`UNIT_OPERATING_COST` 或 `UTILIZATION`；后续 action screen 才决定 D2 是 `CENTRAL_VOTER` 还是成本字段仅为 `DIAGNOSTIC_NON_VOTER`。若后续采用区域机制，成员间的实际地理重叠只在 action-specific arena contract 中核验，H1 不新设 geography hard gate；行动特定的非机械性、共同驱动、成员 causal role 与最终 panel 留到 action screen；
3. 检查新增控制集团不与保留成员重复，并将已有 break 成员保持排除；
4. 以 `judgment_selection_discovery.py --cohort-only` 验证 H1 cohort receipt。该命令只读离线 JSON，不发网络请求；H2 action-screen extension 只在后续 candidate binding 中验证，不能作为 `--cohort-only` 输入。

没有原件 identity 或任一页码时，写 `INSUFFICIENT_STATIC_SOURCE_PACKAGE`；不得在 CNINFO UI、issuer API、搜索结果页或公司详情页补查。

## 3. 容量和共同市场的准入

对一个可能在 cohort 内选择的 target，H1 接收包至少应形成 **五家**披露成员，成员可为 `PENDING_ACTION_WINDOW_REVIEW` 或带 cutoff-before break 证据的 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK`。H1 显式记录 `current_admission_assessment.status = FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE`，只表示字段可得性 universe 可审查，不表示 target、final peer 或 V5 panel 已就绪。已知 break 成员保留为 disclosure-only，不能计入最终 peer 容量。H1 不执行 target 加三家 peer 的最终容量门；V5 canonical cohort 的最低容量和 action-specific 可比性仍在 H2/V5 判断。该 arena 必须有 source-bearing `market_scope_type`，并以产品、客户与足以说明 arena family 的地理/市场暴露支撑；它可以是 `NATIONAL`、`REGIONAL`、`EXPORT`、`SEGMENT` 或 `MULTI_REGION_PORTFOLIO`。对于区域 arena，运输半径、delivered price、客户终端市场和多区域资产重叠等机制证据在 H2 核验；同省不自动可比，跨省也不自动排除。最终 V5 action screen 才冻结三至七家 peer、共同驱动和排除理由。已有旧 V4 status 或缺少 strict package 字段的 cohort 会被 H1 intake 拒绝，不能作为遗留兼容输入。

成员数量只是在行动筛选前保证可行性，不代表最终 peer 已可比。收购、合并范围、会计列报、经营 perimeter 或地理/客户市场断裂，均由具体 action window 决定；一旦发生，移出该窗口，不得由文字解释覆盖。

## 4. 验收与不授予的权利

接收成功的输出只能是 `STAGE0_FEASIBILITY_REVIEWABLE`。它不授予 episode 注册、outcome access、方向性 learning、方法冻结或报告使用；唯一允许的下一步是由 curator 一次性提交绑定该 H1 receipt 的 cutoff-before action-screen static-PDF extension，再进行 `CANDIDATE_DECISION_SCREEN`。extension 可含 H1 禁止的行动原件，但不得新增 cohort 公司，screen 开始后不得再追加或替换来源。进入该内层 V4 contract 后，所有 pre-outcome 引文仍只可来自 H1∪H2 的闭合 static-PDF map：H1 年报目录负责 target/peer raw D3/D4、control、market、comparability 与现金历史，H2 只补该 screen 的行动、事实和 D2/cost；不得再以 V4 原始字段、现金桥或同行面板名义补源。V4 还必须逐页复现 H2 已筛选的行动陈述、implementation/bridge/specificity/exposure、cutoff facts 及每期 D2/cost observation；价格行动的 price delta 和 pre-action units field identity 不得另行改写。

当前离线 validator 已验证一个 H1 package 与闭合 H2 extension 的字段、来源和身份绑定。G2 最小 runtime receipt registry 现已在 `scripts/judgment_v5_control_plane.py` 实现：`register-h1-receipt` 先调用 strict H1 validator 并以 receipt id/version、cohort/time/curator 自然键固化原始 package；`register-h2-receipt` 只能引用已登记 H1，并从该 immutable payload 读取 H1 后调用 H2 validator。相同 receipt id/version 的不同内容、同一 H1 cohort/time/curator 的第二个 receipt、以及同一 H1 下同一 screen 的第二个 H2 均被拒绝。V5 canonical root 的 `source_provenance` 只保存 H1/H2 receipt ref 与快照；seal 在写入前解析 H1→H2 parent 并要求 `source_manifest` 完全属于其 H1∪H2 static-PDF map，而不是接受临时 V4 wrapper 或第二个 V5 root。

该实现已在 temporary SQLite synthetic 测试中验证，并已在隔离开发 namespace 登记水泥 H1：`H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1@1`。该 receipt 只固化 static package；未创建 freeze、event、H2 extension 或 outcome access。登记不是 H1 preflight 的自动副作用；后续只有 curator 提交绑定该 receipt 的 H2 extension，才可进入 H2 校验。

下一步只是在这一固定 cohort 的 static source package 内筛选“公司整体、已实施、可归因、非维护/非强制”的经营决策；若没有这样的行动，结论是 `NO_PRIMARY`，不是用项目 capex、行业景气、公司总现金或后来结果填空。
