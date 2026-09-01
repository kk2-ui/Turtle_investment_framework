# 报告自治：判断账本→确定性编译→完整报告最小协议

版本：`staged-judgment-ledger.v1`；状态：`DESIGN_ONLY / NO_CODE_CHANGE`。

## 目标与非目标

当前 fresh Agent 一次性生成完整 `EnterpriseUnderwritingEpisode v2`，同时承担公司/行业
判断、组件权限、正常盈利桥、owner cash、永久损失、路线绑定、敏感性和证据定位，导致
23/32 次执行在结构闭合前终止。下一版拆为：

```text
cutoff 前证据 + 训练记忆 → price-free 判断账本 → 确定性编译器
→ EnterpriseUnderwritingEpisode v2 → 现有 reader/CJO handoff
```

账本不存事实正文、价格、估值、回报、BuyBand、评级、仓位、动作或 outcome；编译器只
复制、排序、分桶和校验，不替 Agent 推理或把 `UNKNOWN` 改成零/负面。

## 责任边界

- Evidence owner 提供官方来源、PIT 时间、责任实体；账本只引用现有 evidence id/locator。
- Industry Learning Block、Experience Pack 与 Expert Correction Package 是
  `TRAINING_MEMORY`，只能改变问题顺序、反方检查和条件性处理，不能成为目标公司证据。
- Agent 提交经济语义；compiler 负责机械映射和诊断；reader writer 只解释已编译判断。

## 最小 price-free 账本

顶层固定字段（`additionalProperties:false`）：`schema_version`、`ledger_id`、
`company_id`、`company_name`、`cutoff_at`、`sample_identity`、`status`、
`decision_frame`、`underwriting_route`、`claims`、`components`、`industry_future`、
`reversal_observations`、`evidence_refs`、`diagnostics`。

每条 claim 固定为：`claim_id`、`surface`、`statement`、`direction`、`mechanism`、
`treatment`、`evidence_ids`、`strongest_rival`、`reversal_observations`、`unknown`。
surface 至少覆盖 survival、business position、adaptation、normalization、permanent
loss、value route、industry future、investment treatment；direction 仅允许
`IMPROVES/DETERIORATES/MIXED/UNKNOWN/NONE`。`unknown` 必须是 `reason`、
`conservative_treatment`、`next_observation`、`materiality` 的完整对象，不能用空值冒充。

每个 component 固定记录 `economic_scope`、`treatment`、normal earnings/owner cash 用途、
financing pressure、permanent-loss 用途、`valuation_use`、显式 route bindings、
`reason`、`promotion_test`、`invalidation_test`。若合同声明 economic-derivation v2，才
允许增加 normal-earnings bridge 与 driver sensitivities；没有证据的幅度用 `UNKNOWN`。

账本状态：`DRAFT`（不可下游）、`FROZEN`、`COMPILED`、`DIAGNOSTIC_ONLY`、`REJECTED`。
身份、价格边界、来源越权、主 claim 缺失、反方/翻转缺失和不兼容路线是 material blocking；
局部未知只降级其依赖组件，不阻断无关判断。

## J0/J1/J2 分阶段接口

| 阶段 | Agent 只提交 | Compiler 只做 |
| --- | --- | --- |
| J0 context | 身份、组件、行业—公司问题、证据索引 | cutoff/allowlist 绑定与字段可回答性 |
| J1 economics | 组件权限、正常盈利/owner cash/永久损失方向、路线、UNKNOWN、翻转条件 | decision summary、route requirements、bridge/sensitivity 结构与诊断 |
| J2 thesis | 中心路径、最强反方、监测和反转叙事 | price-free reader bridge 与字段投影 |

只有 J0/J1/J2 accepted 且 compiler 通过，才投影为严格 Episode；每阶段保存输入、输出、
compiler 版本、diagnostics 和 `PENDING/READY/ACCEPTED`。

## 确定性映射及禁止事项

身份和截止时间逐字复制；industry future、claims、components、evidence refs、rival 和
reversal 逐字段映射到 Episode；component summary、route 分桶、覆盖检查、敏感性形状、
price-free reader bridge 由现有纯函数派生。编译器不得选择组件、补写收益基准、估计敏感性、
升级 scenario/excluded 为 base、改变路线经济角色、生成价格/回报/行动。

任何无法安全映射的缺口返回 `JUDGMENT_INCOMPLETE` 或 `EVIDENCE_INSUFFICIENT`，并写入
`staged-ledger-diagnostics.v1` sidecar：`path`、`code`、`severity`、`root_cause`、
`economic_impact`、`missing_fact`、`prohibited_assumption`、`remediation`、
`acceptance_criterion`。不把诊断墙写进读者正文。

## 公平性与验收

四臂仍共享 cutoff、common source、模型、时间/调用预算、J0/J1/J2 schema 和 compiler；
industry/expert memory 只作为 company-free 提示。每臂一次 fresh run、无 retry/rewrite；
invalid 不记为最差质量。至少一个公司四臂完整冻结并匿名审阅 PASS 后才可开 outcome gate，
不足则 `UNIDENTIFIABLE`。

离线测试必须覆盖 schema/validator parity、确定性、price firewall、UNKNOWN locality、
route/component 绑定、memory 边界、projection continuity、负例诊断和 100% JSON 可解析。
在新 cohort 中，Enhanced 只有在不新增事实/越权错误的前提下减少一项改变投资处理的材料错误，
才可声称自主性增益；否则保留 `NO_MATERIAL_UTILITY`。

本文件只规定最小协议，未授权真实模型运行、后验结算、跨公司迁移或生产发布。
