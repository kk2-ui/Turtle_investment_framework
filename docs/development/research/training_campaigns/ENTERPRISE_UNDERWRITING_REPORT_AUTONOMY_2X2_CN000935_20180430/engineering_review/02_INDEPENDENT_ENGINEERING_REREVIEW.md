# 独立工程复审：现金/权益桥、v2 幅度证据与匿名传输

**结论：RETURN。**

现金/权益桥和匿名传输的原阻断项已具备可执行的闭环；历史 derivation-v1 也已被限制为精确冻结 replay，不能再 render 新任务或 run。剩余的 v2 BOUNDED sensitivity delta 虽新增了 `magnitude_evidence`，但其“同责任边界的幅度证据”仍只是与 sensitivity 重复填写的一组自述字段，未从被引用的 evidence trace observation 中取证并逐项比较。因此，异边界、异口径或异期间的 source 仍可被贴上匹配标签后进入 DIRECT normal-earnings/owner-cash reader/valuation-route request；该缺口可实质改变条件性正常盈利、普通股现金与价值路线的可信度。

## 范围与方法

本复审仅读取原工程 RETURN、指定 cash/fact-register/value-bridge/episode/training/anonymous-packet 实现、schema 和定向测试；未读取 campaign outcome、observation、final review 或 FY2018+ 源材料。

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

结果：**205 passed in 4.50s**。通过项证明已有的负例/回归未回退；它们不覆盖下面的 evidence-trace metadata 与 v2 magnitude binding 的错配。

## 已复核通过的原阻断项

1. **adopted cash/equity bridge operand binding 与消费：通过。**
   - 现金输入只能使用 v2 canonical official register；每个被枚举的数值、布尔及资金身份 operand 都必须有唯一 binding，并逐项核对 observation 的 fact id、值、单位、责任边界及来源就近声明；任何漏绑都会失败（`scripts/cash_accessibility_model.py:373-482`）。
   - valuation bridge 再要求每个数值 cash operand 在全局 bridge ledger 指向同一 fact，并把 shares（及跨币种时 FX）也绑定至同一 official observation；然后确定性重算 cash projection（`scripts/valuation_value_bridges.py:115-226`、`1296-1312`）。定向测试覆盖自填 VERIFIED id、缺 observation、cutoff 不安全 source、值/单位/责任边界错配及 cash claim 未真正进入 equity bridge。

2. **冻结 derivation-v1：通过。**
   - 仅登记的 frozen contract 与仓库 canonical JSON 完全相等时才可以 replay（`scripts/enterprise_underwriting_training.py:291-307`）。
   - v1 contract 或 v1 derivation interface 均会在新 `run` 和 `render-subagent-task` 前被拒绝，保留 validate/compile replay（`scripts/enterprise_underwriting_training.py:310-323`、`935-1021`）。定向冻结回归通过。

3. **匿名 label 与 source 内容：通过。**
   - 输入 label 直接拒绝含任一完整/短 arm identifier 的值；构成 packet 后，对完整序列化 payload（包括 shared `source_ref` 和 `content`）做 identifier 扫描（`scripts/anonymous_preoutcome_review_packet.py:51-102`）。`ANON_A00` 和 shared source content 含 `A00` 的负例均已覆盖。

## 阻断项

### v2 BOUNDED delta 的幅度来源没有被证明与声明的责任边界同口径

**根因分类：MODEL、DATA_COVERAGE。**

`_economic_derivation_findings` 把 `evidence_trace` 缩减为一个仅含 `evidence_id` 的集合（`scripts/enterprise_underwriting_episode.py:1109-1113`）。随后 `_validate_sensitivity_delta_magnitude_evidence` 只检查 magnitude evidence id 属于该集合、没有复用 driver-case id，并把 `component_ids`、`responsibility_boundary`、metric/unit/horizon、axis 和 delta unit 与 sensitivity 中**同一份 agent 填写的字符串**比较（`scripts/enterprise_underwriting_episode.py:1036-1082`）。它从未按 id 查回 evidence trace 的 `scope`、`source_ref` 或 `locator`，更没有任何结构化 observation metadata 可供比较。

所以一个异责任边界、异单位经济、异 horizon 的 evidence trace 项，只要在 `magnitude_evidence` 再声明为目标边界/单位/horizon，就会通过当前 v2 校验并允许非 PRESERVED BOUNDED delta。现有回归只验证“缺少 magnitude_evidence 必须失败”，没有覆盖这一错配路径。

**经济影响。** 该 delta 可作为 DIRECT normal-earnings 或 owner-cash transmission 进入 compiler-owned summary、reader brief 和 valuation-route request。将不属于目标成熟业务、责任边界或时间窗的幅度搬入，会虚增或扭曲条件性盈利/现金与相关价值路线，进而改变永久损失和估值使用的可信度。

**缺失事实。** 每个被用于幅度的 evidence id 缺少可机器比对的、来自该 evidence observation 的 component scope、responsibility boundary、driver metric/unit、horizon、affected axis、delta unit 及 calculation inputs metadata。

**禁止假设。** 不得把 `magnitude_evidence` 自身复述的 boundary/metric/unit/horizon、自由文本 `scope`、calculation expression 或已有 component authority 当作幅度来源已与目标 sensitivity 同边界的证明。

**可执行修复。** 为 evidence trace 中可量化幅度 source 增加可选但对 economic-derivation-interface.v2 的非 PRESERVED BOUNDED delta 必填的结构化 measurement/calculation metadata。validator 必须按 `magnitude_evidence.evidence_ids` 查回这些 canonical evidence entries，逐项比较 component ids、责任边界、driver metric/unit、horizon、affected axis、delta unit 与 calculation inputs；禁止只比较 delta 内重复字段。将此要求限定在 v2 interface，保持 v1 raw response 的精确 replay 兼容。

**验收标准。**

- 对 v2 contract：magnitude evidence 的 trace metadata 若为不同 component、责任边界、metric/unit、horizon、axis、delta unit 或 calculation input，必须 INVALID，即使 `magnitude_evidence` 内的复制字段与 sensitivity 相同。
- 同一 source observation 的完整 metadata 与计算输入逐项匹配时，合法 DIRECT BOUNDED delta 通过；driver-case id 复用继续失败；PRESERVED `[0,0]` 与 UNKNOWN 均保持现有处理。
- 已登记的 derivation-v1 contract/raw response 仍逐字 replay，且 `render-subagent-task`/`run` 对其仍拒绝。
- 重新运行本复审所列定向测试集及上述正反例。
