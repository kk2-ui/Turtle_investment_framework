# 估值实施蓝图

这里保存的是可复用的**估值实施知识**：一类企业要重建哪些经营能力、应取哪些证据、哪些计算方法可用、双计归谁处理，以及何时必须保留不完整范围。

它不是行业机制知识库、公司研究缓存、参数表或模型路由表。

## 权限边界

```text
valuation archetype card
  -> 要求本公司补取字段、给出官方来源/模块/查询提示和有界停止规则
  -> ValuationEvidencePlan 按当前 VERIFIED observation 编译逐角色 AVAILABLE/MISSING/INELIGIBLE
  -> 公司当期 VERIFIED OBS/CALC 输入确定性模型
  -> 公司估值与报告
```

卡片不得携带公司事实、金额、比例、倍数、默认折价、默认完成率或自动估值路线。它不能直接给目标公司填入任何数值，也不能把历史案例参数传给新公司。被卡片要求的能力证据必须由当前、已核验的官方原始 observation 显式声明对应的 `valuation_evidence_roles`；一个成本或余额事实不能在模型内被重新贴标为客户留存、合同簿或重建时间。组件排除同样只能引用明确声明 `valuation_exclusion_destinations` 的原始 observation。

`config/archetype_valuation_registry.v1.json` 只把已经选择的估值路线连接到一张特定版本的卡；卡片本身不选择路线。重置价值内核只接受与路线一致、且已解析的卡片版本。

生产读取入口 `read_valuation_route` 会同时返回 `valuation_evidence_plan`。缺失角色会
给出官方来源、`search_report / read_section / verify_official_fact` 等采集模块提示、
查询词、停止规则和受影响估值主张。可选的
`valuation_evidence_attempt_receipts.json` 只记录已经执行的有界检索；它不具事实
资格，也不能解除 `UNKNOWN`。需要单独生成持久工件时可运行：

```bash
.venv/bin/python scripts/valuation_evidence_plan.py output/<company-dir>
```

## 首张卡与扩展

`property_service.v1.json` 保留首张模型边界蓝图；`property_service.v2.json` 新增逐角色采集与停止知识，并由当前路线显式引用。两版都要求客户关系、区域组织、获客渠道、履约记录、项目启动营运资本和其他功能资产被显式处理；未定界或仅情景化的必需组件不得形成公司级重置范围或共同保护价。历史模型仍按原卡版本复现，不能原地改写旧卡。

`v2` 是非数值生产取证蓝图的版本发布，不是训练晋升、跨公司验证或估值结论。

新行业应新增一张独立卡，而不是修改物业卡或复用其组件名称。例如制造业可以定义客户认证、工艺资格、模具/产线爬坡等自身组件。新增卡至少需要：独立公司重跑、明确反例或不适用边界，以及独立审阅。

## 训练接缝

审计或已结算的训练案例只能提出“缺哪个证据角色、哪条双计规则失败、哪个 UNKNOWN 边界应收窄”的**研发候选**。它们不能自动改写生产卡，更不能产生金额、百分比或估值结论。

任何卡片修改应先在另一家公司、同一 cutoff 的冻结前研究中检验，再由独立审阅确认；通过不同公司和时间留出后，才允许升级为默认可用的生产卡。
