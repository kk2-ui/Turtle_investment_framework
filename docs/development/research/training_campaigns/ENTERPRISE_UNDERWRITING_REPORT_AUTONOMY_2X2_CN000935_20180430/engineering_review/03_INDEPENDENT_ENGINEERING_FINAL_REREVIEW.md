# 第二次独立工程复审：现金/价值桥、derivation v2 与匿名包

**结论：PASS。**

原审阅和第一次复审的三项阻断均已关闭。现金采用额及每股权益桥的所有会影响数值的 operand 都有 cutoff-safe canonical official fact binding；新 derivation-v2 的非 PRESERVED BOUNDED delta 必须从所引用 `evidence_trace` 的结构化 `sensitivity_magnitude_observation` 反查并逐项验证元数据；冻结 v1 只保留只读 replay 路径，新的执行只能使用 v2；匿名 packet 不再允许 caller label、共享来源或 arm 内容保留已知 arm mapping token。未发现会实质改变条件性正常盈利、普通股现金、价值路线或 2×2 盲审独立性的遗留缺口。

## 范围与方法

按 `01_INDEPENDENT_ENGINEERING_REVIEW.md` 与 `02_INDEPENDENT_ENGINEERING_REREVIEW.md` 的清单，只检查当前 cash/fact-register/value-bridge、episode/training schema 与 validator、anonymous packet 及其定向测试。未读取 campaign outcome、observations、任何 final review 或 FY2018+ 材料。

## 复核结果

1. **adopted cash 是 canonical official fact 的受约束结果：通过。** `cash_accessibility_model` 强制使用 v2 official register；register observation 必须具备 stable `fact_id`、数值、单位、责任边界、source/page 和 cutoff-safe 可得时间。每个可影响现金金额、比例、布尔适用性或资金身份的 factual operand 都必须有唯一 binding，逐项核对 observation 值、单位、责任边界与就近声明的 fact id；漏绑、伪造 `VERIFIED`、非 canonical id、post-cutoff source、值/单位/边界错配均为 INVALID。现金 bridge 再重算 model，并要求全局 canonical binding ledger 消费同一数值 cash operand、shares 与（如需）FX official observation，故 adopted amount 不能通过 free-copied input 进入 ordinary-equity per-share bridge。

2. **derivation-v2 的 BOUNDED delta 以 evidence trace metadata 取证：通过。** schema 将 `sensitivity_magnitude_observation` 置于 canonical `evidence_trace` entry。对于 v2 的非 PRESERVED BOUNDED normal-earnings/owner-cash delta，validator 用 `magnitude_evidence.evidence_ids` 查回该 entry，并与 sensitivity 的 component ids、responsibility boundary、driver metric/unit、horizon、affected axis、delta unit 和 calculation inputs 逐项比较。`magnitude_evidence` 内的重复字段仍受形状一致性检查，但不能替代 trace metadata；任何一个 trace metadata 错配、缺 observation 或重用 driver-case evidence 均会 INVALID。PRESERVED `[0,0]` 和 UNKNOWN 保持原有的非数值处理。

3. **v1 frozen replay 与 v2 新执行边界：通过。** legacy contract 及 derivation-interface v1 均须与明确定义的仓库 canonical contract 完全相等；`validate-episode`/`compile-bundle` 保留 replay，`render-subagent-task` 和 `run` 被明确拒绝。当前默认 derivation interface 为 v2，并在 training episode validation 中开启严格 magnitude-evidence/trace-metadata 校验。

4. **anonymous mapping：通过。** packet 在输入 label 阶段拒绝任一完整或短 arm identifier（包括 `ANON_A00`）；生成后在整份序列化 payload 上扫描所有 identifiers，覆盖 anonymous arms、共享 `source_ref` 与 content。arm material 内的 identifier 仅会替换为匿名 label，且最终 packet 再作无泄露断言。

## 定向测试

在禁用 pytest cache 和字节码写入的条件下运行：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_cash_accessibility_model.py \
  tests/test_cutoff_official_fact_register.py \
  tests/test_valuation_value_bridges.py \
  tests/test_value_bridge_chain_integration.py \
  tests/test_enterprise_underwriting_episode.py \
  tests/test_enterprise_underwriting_training.py \
  tests/test_anonymous_preoutcome_review_packet.py
```

结果：**213 passed in 4.46s**。

新增/现有针对性回归覆盖：cash self-declared verified fact、canonical observation 缺失/截止日/值/单位/责任边界错配、cash-to-equity bridge 绑定；v2 trace metadata 的 component/boundary/metric/unit/horizon/axis/delta-unit/calculation-input 错配；冻结 derivation-v1 raw response replay 与新 task 拒绝；以及 `ANON_A00` 与 shared source content arm-token 泄露。
