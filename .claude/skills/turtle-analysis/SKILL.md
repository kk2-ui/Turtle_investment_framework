# Turtle Investment Framework — Skill Definition (V9.3)

## Skill Info
- **Name**: turtle-analysis
- **Description**: 一条 `/turtle-analysis <stock_code>` 跑完全部分析。协调器调度 sub-agent，不亲自干活。
- **Entry Point**: `strategies/turtle/coordinator_v8.md`

## 协调器角色

你是总调度者，不是苦力。你只做三件事：**调度、检查、拼装**。

- 重活（读 PDF、处理 prompt）→ 扔给 sub-agent
- 质量检查（每个 sub-agent 产出是否达标）→ 你亲自审
- 拼装（Zone B → Zone J → Zone C 串起来）→ 你亲自做

## 完整流程

### Phase 0: 前置诊断
```bash
python3 scripts/pre_analysis_phase.py --code {CODE} --output output/{DIR} -v
```

### Phase 1: Zone A 定量
```bash
python3 scripts/compute_bundle.py --from-db --code {CODE} --output output/{DIR} --price {PRICE}
python3 scripts/build_financial_trends.py --code {CODE}
python3 scripts/zone_d_industry_context.py --code {CODE} --output output/{DIR}
python3 scripts/build_data_pack.py --code {CODE}
```

### Phase 2.2: 调度 4 个 sub-agent 并行读 PDF

```bash
# 先生成 page_map（每年一次）
for YEAR in 2022 2023 2024 2025; do
  python3 scripts/pdf_page_locator.py --pdf ... --output output/{DIR}/page_map_{YEAR}.json
done
```

然后**并行调度 4 个 sub-agent**（每个读一年 PDF）：

```
sub-agent-1: 读 FY2022 PDF → 输出 zone_b_2022_partial.json
sub-agent-2: 读 FY2023 PDF → 输出 zone_b_2023_partial.json
sub-agent-3: 读 FY2024 PDF → 输出 zone_b_2024_partial.json
sub-agent-4: 读 FY2025 PDF → 输出 zone_b_2025_partial.json
```

每个 sub-agent 的 prompt：按 page_map 页码范围，用 pdfplumber 读对应章节，提取定性数据。提取内容见 coordinator_v8.md Phase 2.2。

**协调器检查**：4 个 partial 是否都有内容（>500 chars），缺失字段是否标注 ⚠️。

### Phase 2.3: 协调器汇总

4 个 partial 到位后，协调器自己做跨年对比，写最终 Zone B JSON（mda/segments/risks/governance/audit.json），标注跨年趋势。

### Phase 3: 调度 4 个 sub-agent 并行处理 Zone J

```bash
# 先生成 prompt
for AGENT in moat capex earnings_quality data_quality; do
  python3 scripts/zone_j_agent.py --code {CODE} --agent $AGENT --save-prompt output/{DIR}/zone_j_prompt_${AGENT}.txt
done
```

然后**并行调度 4 个 sub-agent**：

```
sub-agent-ZJ-1: 读 zone_j_prompt_moat.txt → 输出 moat_assessment.json
sub-agent-ZJ-2: 读 zone_j_prompt_capex.txt → 输出 capex_classification.json  
sub-agent-ZJ-3: 读 zone_j_prompt_earnings_quality.txt → 输出 earnings_quality.json
sub-agent-ZJ-4: 读 zone_j_prompt_data_quality.txt → 输出 data_discount.json
```

**协调器检查**：`python3 scripts/zone_j_agent.py --code {CODE} --agent moat --validate output/{DIR}/moat_assessment.json` 确保每个参数有 evidence_ref。

4 个全部通过后：
```bash
python3 scripts/compute_bundle.py --from-db --code {CODE} --zone-j output/{DIR}/ --output output/{DIR} --price {PRICE}
```

### Phase 4: 调度 1 个 sub-agent 处理 Zone C（V9.3 单 Agent）

```bash
python3 scripts/zone_c_chain.py --code {CODE} --agent C_FULL --save-prompts --output output/{DIR}
```

协调器**调度 1 个 sub-agent**：

```
sub-agent-ZC: 读 zone_c_C_FULL_prompt.txt → 一次性写完整报告（3000-4000行）
  → output/{DIR}/zone_c_C_FULL_output.md → 即最终报告
```

**为什么是 1 个 Agent**：C1-C4 总上下文约 280K chars，1M 窗口完全容纳。单 Agent 确保因子间计算一致性，无需 chain_context 传递，无拼接组装。

回退：`--assemble` 自动检测 `C_FULL_output.md`，存在则直接使用；不存在则回退到旧 6-agent 拼接。

### Phase 5: 验证 + 发送
```bash
python3 scripts/boundary_validator.py --code {CODE} --boundary zone_b
python3 scripts/quality_gate.py --code {CODE}
```

## 硬约束

1. 协调器只调度、检查、拼装——不亲自读 PDF、不亲自处理 prompt
2. 每个 sub-agent 产出后协调器必须检查质量
3. Phase 3 每个参数必须带 evidence_ref
4. Phase 4 禁止压缩表格
5. 异常时标注 ⚠️ 继续，不阻塞管道
6. 完成后自动发报告
