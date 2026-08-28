# 中国家电四阶段训练 V1

> 状态：`E0_E1_FROZEN / E2_PREOUTCOME_FROZEN / E3_NOT_ADMITTED`

本工件把已经存在的家电行业块、五家公司 J2 重建以及苏泊尔 R11 结果前对象，投影到最新的四级证据架构。它不复制行业事实、来源库、结算引擎或 Comparative 控制面。

投资者当前得到的不是“六家公司谁更好”，而是三项更窄、但可检验的认识：

1. 全国家电风险集包含不同产品、渠道和资本边界，不能把它们自动当成同质同行；
2. 苏泊尔必须把发行人增长、电锅产品收入和发行人经营现金分开观察；
3. 下一轮结果只能判断三者是否同向或背离，不能单凭年度字段证明渠道和产品行动造成了公司改善。

四阶段的当前状态：

- `E0_CONTEXT`：已冻结。复用五家公司、两个 cutoff 的行业块，并把苏泊尔作为 C2 的独立扩展对象；
- `E1_RECONSTRUCTION`：已冻结。复用五家公司现有重建，并绑定苏泊尔的八维责任边界与局部 UNKNOWN；
- `E2_MECHANISM_PROBE`：结果前冻结和独立审阅已通过，等待 contract-only custodian 逐字段结算；
- `E3_COMPARATIVE_LAB`：未准入，但不阻断前三层。只有另行冻结产品级 estimand、机制相容 panel、公平基线与独立结果合同后才可启动。

允许输出仅为 `STATE_VIEW / DECISION_VIEW / MECHANISM_VIEW / TEACHING_ONLY / RESEARCH_AGENDA`。方法迁移、CJO、估值、报告、BuyBand 和投资权限全部关闭。

结果侧工件保持追加式：`03_e2_acquisition_attempt_1.json` 保留第一次
value-free mismatch；`04_e2_acquisition_recovery_preoutcome_receipt.json` 只记录修复
公告分类后对已验收结果前对象的等值控制器重放。后者没有打开 outcome access，
也没有改写预测、Measurement Contract 或第一次失败收据。

`05_e2_acquisition_attempt_2.json` 保留第二次独立 custody 的字段级终态。它证明
官方原始年报已可唯一选中，但三个字段仍分别被 metric identity、产品收入表定位和
现金流量表续页规则阻断。对应修复只扩展既有 acquisition catalogue 和机械 verifier，
不改变任何训练判断。
