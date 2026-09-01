# Turtle V5 PIT 控制面迁移设计

> 状态：`SUPERSEDED_FOR_SLICE0_1 / SLICE2_REFERENCE_ONLY / V5_IMPLEMENTATION_NOT_STARTED / EXTERNAL_ACQUISITION_PAUSED`
>
> 日期：2026-08-24
>
> 范围：为 `JUDGMENT_SELECTION_ADMISSION_V5` 设计独立、追加式的 PIT 控制面。本文不修改代码、schema、真实数据库或 R-103/R-104 工件。
>
> 实施收口：本文第 1–2 节只保留为 V4/legacy 隔离审计背景；第 3–10 节只保留为未来 Slice 2 的思考材料。具体 Slice 0/1 state transition、R-103 时点、CLI 和表结构已由 [V5 最小实现工作包](TURTLE_V5_MINIMAL_IMPLEMENTATION_WORK_PACKAGE.md) 第 4、6 节完全取代。尤其不得从本文推导“首个 training outcome 前必须 reserve R-103”、逐组件注册、七表实现、一个 central metric 即可 freeze，或真实 case 的 pre-access outcome inventory；实现只能以后者为准。

## 1. 决策与边界

V5 不是 V4 的补丁，也不是把新的字段塞进既有 `judgment_training_program.py` 或 `judgment_feedback_control.py`。它在同一 `stock_analysis.db` 中使用独立的 `judgment_v5_*` 表和新的 CLI；旧表、旧 API、R-104、R-103 与所有 V3/V4/legacy artifact 均为只读历史。

这保留两件事：

- V4/R-104 的既有事实、`MIXED` 结论、feedback event 和 schema 永不重算或回写；
- R-103 仍是原始 legacy holdout。V5 只能创建一个只读的 reservation overlay，不能向它的 case、freeze、feedback claim 或结果文件写字段。

V5 首版也不写真实 DB。实施顺序是先加 schema、纯 validator、临时 SQLite acceptance tests，再显式批准 production `init`。不增加哈希、checksum、第二个长期数据库或通用迁移框架。

## 2. 现有系统审计：可复用与不可复用

| 现有接口 | 可复用的职责 | V5 不可直接复用的原因 | V5 处理 |
|---|---|---|---|
| `scripts/judgment_training_program.py`：`connect()`、时区解析、immutable contract registration、artifact snapshot、`reserve_holdout()`、`freeze_method()`、`reconcile()` | SQLite 单库、time-aware receipt、idempotency、lane/holdout 的 read-model 思路。 | `SELECTION_ADMISSION_VERSIONS` 只允许 V3/V4；episode 只有 `cutoff_at/outcome_not_before`，没有 epoch、Stage0、action/panel/metric/outcome identity graph。 | 新模块只复用这些模式；不扩展现有常量、表或 CLI。V5 另有 epoch/release/reservation 状态机。 |
| `scripts/judgment_feedback_control.py`：`judgment_feedback_events`、`append_event()`、outcome adapter、holdout pre-reveal receipt、exposure breach | 追加事件的 `effective_at/recorded_at/actor/idempotency_key/artifact_refs/payload` 结构；outcome package→reader→extraction 的顺序；holdout 违规为终态。 | claim key 被固定为 `episode_id + claim_id + stage_id`，selection registration 调用 V4 candidate/review，event type 与 D1--D5 的 V4 结算耦合。 | V5 建自己的 identity/freeze/access event ledger。待 V5 source/measurement contracts 落地后，才抽取无版本依赖的 acquisition/reader primitives；不能先把 V5 伪装成旧 feedback claim。 |
| `scripts/judgment_selection_candidate.py`：`validate_v4_cohort_feasibility_record()`、V3/V4 admission validators | cutoff-before evidence、Stage0 与 action binding、独立 review、`NO_PRIMARY` 的拒绝模式。 | `industry_id`、same-industry panel、V4 market equality 和 V4 raw-field/topology 都不是 V5 经济语义。 | 新建 V5 contract/validator；保持本文件不导入或修改 V4 validator。 |
| `scripts/judgment_selection_peer.py`：`validate_peer_contract_binding()`、raw-field validation | 固定 member order、同结果期、逐 raw field/source/perimeter/period 校验、调用方不能提交 derived peer verdict。 | 顶层 gate 是 `JUDGMENT_SELECTION_ADMISSION_V4`，字段固定为 5+12 D3/D4 和 V4 peer-median。 | V5 复用“field matrix 必须完整、source-bearing、由 control plane 重算”的原则，另实现 V5 metric matrix/causal-role validator。 |
| `scripts/judgment_selection_feedback.py` 与 `scripts/judgment_selection_post_outcome_review.py` | outcome 不能反写 freeze、联合 verdict、role-separated review、`UNKNOWN/NOT_DIAGNOSTIC` 不得制造方向性学习。 | 输入为旧 candidate/selection-resolution amendment 与 V4 claim registry。 | V5 新建 resolution/review schema；未来只抽纯 joint-verdict helper，不能直接调用旧 V4 pipeline。 |

现有测试也应作为迁移基线而非重写目标：`tests/test_judgment_training_program.py` 覆盖 immutable registration、pre-freeze holdout 与 method freeze；`tests/test_judgment_feedback_control.py` 覆盖 append-only/idempotency/事件次序；`tests/test_judgment_selection_feedback.py` 与 `tests/test_judgment_selection_control.py` 覆盖 outcome identity、raw fields、independent review。它们必须继续通过，且 V5 tests 另起文件。

## 3. V5 canonical identity graph

### 3.1 版本与职责

`method_epoch_id` 与 `method_release_id` 不能混用：

- `method_epoch_id` 冻结 V5 的原语、允许 topology、schema/policy 与 transition policy；它在第一个 cohort 前存在，不能由 outcome 修改。
- `method_release_id` 是该 epoch 中由合格 training learning 形成并冻结的可评估方法。只有它可打开已预留 R-103 的结果访问权。

每个 V5 selection freeze 必须绑定以下 identity；每份 contract 都有其自己的 `*_id`、`schema_version`、`recorded_at` 与不可变 artifact snapshot/ref：

```text
method_epoch
  └─ cohort_snapshot
       └─ action_identity
            ├─ counterfactual_panel
            ├─ measurement_bundle {central D3, central D4}
            └─ outcome_contract
                 └─ selection_freeze
                      ├─ pre-outcome review / freeze seal
                      ├─ outcome access authorization
                      ├─ outcome package / reader / extraction / resolution
                      └─ post-outcome review / learning / migration

method_epoch ── r103_reservation (legacy read-only overlay)
method_release ── r103_access_authorization ── r103_evaluation
```

`selection_freeze_id` binds exact H-A/H-B, thresholds, all preceding IDs, the pre-outcome review receipt and the `episode_collision_key`.

### 3.2 Required identity contracts

| Identity | Immutable minimum | Time/control rule |
|---|---|---|
| `method_epoch_id` | V5 admission version, primitive/policy version, permitted topology list, source-access policy, creator/recorded time. | Once registered, no policy amendment. A semantic change requires another epoch. |
| `cohort_snapshot_id` | `cohort_eligibility_as_of`, arena family, eligibility rule, member/exclusion ledger, carrier/control/field availability identities and Stage0 source refs. | No focal action, final peer role, common driver or outcome source may be carried in it. Every source is available no later than cohort-as-of. |
| `action_identity_id` | action id, decision scope, economic carrier, bridge type, implementation/rollout window, decision-observable source/time, action evidence. | Must bind the cohort and satisfy `cohort_as_of < action_effective_window.start` and `< decision_observable_at`. |
| `counterfactual_panel_id` | ordered target/member IDs, `CAUSAL_PANEL_ROLE` per member, competitive-arena binding, mechanism-dimension overlap claims/evidence, exclusions/no replacement. | Only `EXTERNAL_SHOCK_COMPARATOR` members enter the relative baseline; witness/falsifier members cannot enter its median. |
| `metric_contract_id` | metric identity, accounting perimeter/carrier, unit, raw field formula, bridge, source class, original/revision policy, central/diagnostic role. | A different field, formula, perimeter or bridge is a different metric identity. |
| `outcome_contract_id` | `outcome_window_id`, action exposure/minimum exposure rule, target/peer fiscal bridge, complete `member × metric × raw-field × period` matrix, permitted source class and original/revision policy. | Primary raw sources must be strictly post-cutoff; missing cell is `UNKNOWN/NOT_DIAGNOSTIC`, never a post-outcome substitute. |
| `selection_freeze_id` | epoch, all prior IDs, hypotheses, thresholds, `research_cutoff_at`, pre-outcome review, collision key and explicit failure disposition. | Material change creates a new freeze. A superseded freeze never inherits outcome access. |
| `r103_reservation_id` | legacy case/freeze references, holdout scope, reservation time, epoch, unexposed receipt and planned evaluation boundary. | It is an overlay only; it creates no V5 mutation of R-103. |

All timestamps are timezone-aware instants. `source_available_at` records initial/revised identity and the time the outcome custodian could access the original source; it is not the researcher’s local download time.

### 3.3 Collision key

`episode_collision_key` prevents the same economic treatment becoming multiple training hits or both training and holdout. Its canonical components are:

```text
target_company_or_cluster_id
action_identity_id
economic_carrier_id
decision_scope/bridge identity
primary outcome_window_id
```

The value is a deterministic readable identifier assembled from those frozen IDs; no content hash is required. One collision reservation may have at most one freeze that reaches `OUTCOME_ACCESS_AUTHORIZED` or later. A pre-access correction can create a successor freeze only after `FREEZE_VOIDED_PRE_ACCESS` on the old one; same collision cannot be registered in both `HISTORICAL_TRAINING` and an R-103 holdout overlay.

## 4. V5 append-only state machine

### 4.1 Events and derived state

All persistent state is derived from immutable identity records plus appended events. There is no mutable `status` column that becomes a second source of truth.

| Event | Preconditions | Effect / terminal rule |
|---|---|---|
| `EPOCH_REGISTERED` | V5 epoch contract validates. | Opens a new semantic epoch; does not grant outcome access. |
| `COHORT_SNAPSHOT_REGISTERED` | epoch exists; Stage0-only fields validate. | Records a pre-action feasibility cohort. |
| `ACTION_BOUND` | cohort exists and strict cohort/action clocks pass. | Creates action-specific scope/carrier binding. |
| `PANEL_REGISTERED` / `METRIC_CONTRACT_REGISTERED` / `OUTCOME_CONTRACT_REGISTERED` | action exists; all references validate. | Registers components; no outcome access. |
| `R103_OVERLAY_REGISTERED` | Slice 2 only: method release exists, legacy R-103 refs are read-only and unexposed. | Creates an evaluation-only overlay after method release, never before a V5 training outcome. |
| `SELECTION_FREEZE_SEALED` | all component identities exist; independent pre-outcome review accepts; source firewall receipt is clean. | Establishes `selection_freeze_id`. |
| `FREEZE_VOIDED_PRE_ACCESS` | freeze sealed but no access/reader/outcome event exists. | Terminal for that freeze; successor must have a new id. |
| `OUTCOME_ACCESS_AUTHORIZED` | sealed freeze, frozen outcome-access scope, designated custodian and no access breach; no actual outcome source inventory is visible yet. | Only transition that grants outcome reading; actual source inventory appears only in a later custodian receipt. |
| `OUTCOME_PACKAGE_REGISTERED` → `OUTCOME_READ_ATTESTED` → `OUTCOME_EXTRACTION_RECORDED` | existing package/reader/extraction order; all raw matrix cells satisfy outcome contract. | Provides source-bound material for resolution. |
| `OUTCOME_RESOLVED` | complete extraction and independent recomputation. | Emits `A_ONLY/B_ONLY/MIXED/NOT_DIAGNOSTIC/UNKNOWN`; never edits freeze. |
| `POST_OUTCOME_REVIEW_ACCEPTED` | resolution bound to original freeze and role-separated reviewer. | Required before any learning privilege. |
| `LEARNING_NOTE_ACCEPTED` / `METHOD_MIGRATION_ACCEPTED` | only joint `A_ONLY` or `B_ONLY`; target freeze is later, still sealed and different collision/company as policy requires. | Records a bounded method change/application. |
| `METHOD_RELEASE_FROZEN` | enough accepted migration(s); R-103 reservation still clean. | Produces `method_release_id`; locks method for evaluation. |
| `R103_ACCESS_AUTHORIZED` / `R103_EVALUATION_ACCEPTED` | matching reservation and method release; no breach. | Evaluation-only; no learning/migration event permitted afterwards in that release. |
| `PIT_ACCESS_BREACH_RECORDED` | evidence of prohibited access or ordering failure. | Terminally blocks affected freeze/reservation from learning or release. |

The normal path is:

```text
EPOCH_REGISTERED → COHORT_SNAPSHOT_REGISTERED → ACTION_BOUND
  → PANEL/METRIC/OUTCOME_CONTRACT_REGISTERED → SELECTION_FREEZE_SEALED
  → OUTCOME_ACCESS_AUTHORIZED
  → PACKAGE → READ_ATTESTED → EXTRACTION → RESOLVED → POST_OUTCOME_REVIEW
  → LEARNING/MIGRATION → METHOD_RELEASE_FROZEN
  → R103_OVERLAY_REGISTERED → R103_ACCESS_AUTHORIZED → R103_EVALUATION_ACCEPTED
```

`NO_PRIMARY` is an admission disposition before any freeze and creates no selection-freeze record. `MIXED` and `NOT_DIAGNOSTIC` are post-outcome terminals with no directional migration rights. An access breach is not repairable by a newer event on the same freeze.

### 4.2 Hard temporal invariants

The V5 validator must reject the bundle before any write unless all applicable assertions hold:

```text
cohort_eligibility_as_of < action_effective_window.start
cohort_eligibility_as_of < decision_observable_at
max(action_effective_window.start, decision_observable_at) <= research_cutoff_at
every pre-outcome source_available_at <= research_cutoff_at
every primary raw outcome source_available_at > research_cutoff_at
primary metric_economic_period satisfies its predeclared minimum exposure rule
target/peer primary outcome period is identical, or uses the frozen fiscal bridge
selection_freeze seal/review/access receipt precedes first outcome access
method_release seal precedes R-103 access
```

Cross-action periods may be captured only as `EARLY_ARROW_NON_VOTER`; they cannot fill a primary metric cell. A document issued after cutoff but reporting a pre-action period also fails the primary outcome contract.

## 5. New schemas, API and commands

### 5.1 New artifacts and schemas

Implement new files; do not change `schemas/judgment_selection_candidate.schema.json` or legacy artifact schemas:

```text
schemas/judgment_selection_admission_v5.schema.json
schemas/judgment_v5_control_plane.schema.json
schemas/judgment_v5_r103_reservation.schema.json
schemas/judgment_v5_outcome_resolution.schema.json
scripts/judgment_v5_control_plane.py
tests/test_judgment_v5_control_plane.py
tests/test_judgment_selection_v5_control.py
```

The V5 selection schema owns the economic identities. The control-plane schema owns event payloads and their permitted transitions. This avoids an oversized candidate JSON being used as both economic evidence and durable state machine.

### 5.2 Proposed Python API

```python
initialize_v5(conn) -> None
register_epoch(conn, epoch_contract, *, recorded_at) -> dict
register_cohort_snapshot(conn, cohort_contract, *, recorded_at) -> dict
bind_action(conn, action_contract, *, recorded_at) -> dict
register_panel(conn, panel_contract, *, recorded_at) -> dict
register_metric_contract(conn, metric_contract, *, recorded_at) -> dict
register_outcome_contract(conn, outcome_contract, *, recorded_at) -> dict
reserve_r103_holdout(conn, reservation_contract, *, recorded_at) -> dict
seal_selection_freeze(conn, freeze_bundle, *, recorded_at) -> dict
void_pre_access_freeze(conn, freeze_id, void_receipt, *, recorded_at) -> dict
authorize_outcome_access(conn, authorization, *, recorded_at) -> dict
record_outcome_package(conn, package_receipt, *, recorded_at) -> dict
record_outcome_reader_attestation(conn, reader_receipt, *, recorded_at) -> dict
record_outcome_extraction(conn, extraction_receipt, *, recorded_at) -> dict
resolve_outcome(conn, resolution, *, recorded_at) -> dict
accept_post_outcome_review(conn, review, *, recorded_at) -> dict
accept_method_migration(conn, receipt, *, recorded_at) -> dict
freeze_method_release(conn, release, *, recorded_at) -> dict
authorize_r103_access(conn, authorization, *, recorded_at) -> dict
accept_r103_evaluation(conn, receipt, *, recorded_at) -> dict
record_pit_access_breach(conn, receipt, *, recorded_at) -> dict
reconcile_v5(conn, *, epoch_id, as_of) -> dict
```

Each mutator performs validation before beginning its transaction, writes exactly one identity/event family atomically, and is idempotent only when the same immutable payload is supplied. Same idempotency key with different binding/payload is a conflict. `reconcile_v5()` is read-only.

### 5.3 Proposed CLI

```bash
.venv/bin/python scripts/judgment_v5_control_plane.py init --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py register-epoch --contract <epoch.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py register-cohort --contract <cohort.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py bind-action --contract <action.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py register-panel --contract <panel.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py register-metric --contract <metric.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py register-outcome-contract --contract <outcome.json> --recorded-at <ISO> --db stock_analysis.db
# Slice 2 only, after method release:
.venv/bin/python scripts/judgment_v5_control_plane.py reserve-r103 --contract <reservation.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py seal-freeze --bundle <freeze.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py void-pre-access-freeze --freeze-id <id> --receipt <void.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py authorize-outcome-access --contract <authorization.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py record-outcome-package --receipt <package.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py record-reader-attestation --receipt <reader.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py record-extraction --receipt <extraction.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py resolve-outcome --receipt <resolution.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py accept-post-outcome-review --receipt <review.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py accept-method-migration --receipt <migration.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py freeze-method-release --receipt <release.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py authorize-r103-access --contract <authorization.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py accept-r103-evaluation --receipt <evaluation.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py record-pit-access-breach --receipt <breach.json> --recorded-at <ISO> --db stock_analysis.db
.venv/bin/python scripts/judgment_v5_control_plane.py reconcile --epoch-id <id> --as-of <ISO> --db stock_analysis.db
```

No V5 command accepts a raw `--verdict`, arbitrary peer list, raw source URL, or legacy case path as a substitute for the frozen bundle. Resolution consumes an already authorized, source-bound extraction only.

## 6. Database design: one DB, new append-only namespace

`stock_analysis.db` remains the sole production control database. V5 `init` creates only new tables and never executes `ALTER`, `UPDATE`, `DELETE`, `REPLACE`, or writes to existing `judgment_training_*` / `judgment_feedback_*` rows.

| Table | Purpose | Key constraints |
|---|---|---|
| `judgment_v5_identity_records` | Immutable epoch/cohort/action/panel/metric/outcome identity snapshots. | `identity_id` PK; `identity_kind`; `epoch_id`; `contract_ref`; canonical JSON snapshot; `(identity_kind, identity_id)` unique. |
| `judgment_v5_selection_freezes` | Freeze registry and collision binding. | `selection_freeze_id` PK; `epoch_id`; `episode_collision_key`; `research_cutoff_at`; snapshot/ref; unique active collision enforced in validator from events, not mutable state. |
| `judgment_v5_freeze_bindings` | Exact freeze→identity graph. | `(selection_freeze_id, binding_kind)` PK; all seven required binding kinds exactly once. |
| `judgment_v5_collision_reservations` | Prevent duplicate training/holdout economics. | `episode_collision_key` unique; original reservation event/freeze; never reassigned. |
| `judgment_v5_control_events` | All transitions, including access/review/breach. | `event_id` PK; subject kind/id; event type; effective/recorded times; actor role/id; idempotency key unique; refs/payload JSON. |
| `judgment_v5_artifact_snapshots` | Ref plus compact JSON/text snapshot used by an identity/event. | `(owner_kind, owner_id, artifact_role)` unique; no raw PDF body or report/PDF archive. |
| `judgment_v5_r103_reservations` | Read-only overlay to R-103. | reservation id PK; epoch/release links; legacy refs; access state derived only from V5 events. |

The unique constraint prevents two origin collision reservations; transitions determine whether it is voided pre-access, settled, breached or evaluated. That preserves history without allowing a result-seen freeze to be replaced invisibly.

Every event payload includes:

```text
event_id, event_type, subject_kind, subject_id,
effective_at, recorded_at, actor_role, actor_id,
idempotency_key, artifact_refs, payload
```

`recorded_at` cannot be future; `effective_at <= recorded_at`; all referenced identities must already exist. Current state is derived by replay, as in the existing feedback control plane.

## 7. Access control and R-103 overlay

### 7.1 Freeze seal and outcome authorization

`SELECTION_FREEZE_SEALED` must carry:

- `selection_freeze_id`, all required binding IDs and a compact frozen snapshot;
- independent `pre_outcome_review_id`, reviewer identity/time and verdict;
- `pre_outcome_access_receipt_id`, attesting that outcome body and metadata were not opened;
- named `outcome_custodian_id`, distinct from the method designer and pre-outcome reviewer where role separation is required.

Only a later `OUTCOME_ACCESS_AUTHORIZED` event may grant the custodian a bounded inventory. It binds the freeze, outcome contract, source inventory, authorization time and custodian. An attempt to package/read/extract first, a source available at/before cutoff, or an access breach emits `PIT_ACCESS_BREACH_RECORDED` and blocks learning/release.

### 7.2 R-103

`reserve-r103` is a Slice 2 operation after a V5 method release has been frozen. The overlay contains R-103 legacy references and a no-exposure attestation but writes nothing beneath `experiments/R-103...` and nothing to old control-plane tables. Slice 0/1 fixtures and training inputs must not contain R-103 identity at all.

The overlay is `EVALUATION_ONLY`:

- it cannot receive `LEARNING_NOTE_ACCEPTED` or `METHOD_MIGRATION_ACCEPTED`;
- `authorize-r103-access` requires the exact reserved `method_epoch_id` and frozen `method_release_id`;
- R-103 access, settlement and reviewer receipts cannot be used to alter that release; a failed/mixed evaluation does not reopen the epoch;
- an R-103 exposure breach permanently bars its use for V5 report release.

## 8. Implementation phases

1. **Contracts and pure validation.** Add V5 schemas and no-DB validators for identity graph, strict time ordering, causal roles, metric matrix and collision key. No new candidate discovery or external collection.
2. **Temporary SQLite state machine.** Add `judgment_v5_control_plane.py`, new tables and event replay tests against `tmp_path`. The production database is untouched.
3. **Synthetic economics.** Build five V5 synthetic bundles: national appliance, regional cement, export manufacturer, segment B2B and cost restructuring. Include invalid mirrors.
4. **Production init approval.** After code review and full regression, run `init` once on the designated DB; this is the first permitted DB mutation.
5. **One unrevealed real candidate.** Register Stage0, action, panel and freeze but do not authorize outcome access until all pre-outcome gates pass. R-104 remains reference-only; R-103 is only reserved.

## 9. Acceptance matrix

| Area | Mutation / scenario | Expected result |
|---|---|---|
| Version isolation | V5 contract supplied to V3/V4 `register` or a V5 command given R-104 as a candidate. | Reject; no legacy row/artifact changes. |
| Epoch | Change topology/policy after epoch registration. | New `method_epoch_id` required; old epoch remains readable. |
| Stage0/action | Same-day or later cohort; action-specific driver/peer role inside Stage0. | Reject cohort/action binding. |
| Freeze graph | Omit panel, metric, outcome or pre-review binding; mutate one after seal. | Reject seal; material replacement needs new freeze with no inherited access. |
| Collision | Re-register same action/carrier/window as new training episode, or as R-103. | Reject collision/lane conflict. |
| Panel | Witness/falsifier enters relative baseline; comparator lacks required overlap/evidence. | Reject panel/outcome contract. |
| Metrics | D3 substitutes D4, raw field/perimeter/formula/revision differs, one target/peer matrix cell absent. | `UNKNOWN/NOT_DIAGNOSTIC` or seal rejection; no fallback. |
| Time | source at cutoff, period pre-action, cross-action primary period, target/peer calendar drift. | Reject authorization/extraction/resolution. |
| Access | package/read/extraction before authorization, wrong custodian, later freeze seal, breach recorded. | Reject transition; breach is terminal for learning/release. |
| Resolution | `MIXED`, `NOT_DIAGNOSTIC` or `UNKNOWN` attempts migration. | Reject migration/method release. |
| R-103 | outcome access before method release, same actor roles, attempt to write legacy R-103 or use it for learning. | Reject; legacy artifacts/DB rows unchanged. |
| Replay | Re-run every registration/event with identical payload; rerun with same idempotency key but changed payload. | First is idempotent; second conflicts; `reconcile` produces same state after reopen. |
| Legacy regression | Existing selection/training/feedback suites and R-104/R-103 read paths. | Existing results unchanged. |

Targeted future test files are `tests/test_judgment_v5_control_plane.py` for event/DB replay and `tests/test_judgment_selection_v5_control.py` for economic/PIT contracts. Existing V4 tests remain untouched except for an explicit regression that V5 cannot route into their APIs.

## 10. Definition of done for implementation

V5 may register one synthetic freeze only when all new validators, state-machine tests and existing V3/V4 suites pass. It may call `authorize-outcome-access` for a real case only after a sealed V5 freeze, clean access receipt, complete raw matrix and R-103 reservation exist. No “compatibility” flag, migration of R-104, overwrite of R-103, or direct DB insert is an acceptable shortcut.
