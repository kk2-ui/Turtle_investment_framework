# CASE:01 runtime remediation

日期：2026-09-01  
范围：下一 cohort 的执行控制面，不改变已冻结 CASE:01 结果

## 问题与经济影响

CASE:01 的三臂失败不能用于效用比较。复盘显示，失败来自执行协议而非行业判断：旧 raw 被复用、A11 的 route-role 绑定不兼容，以及冻结后仍可直接覆盖 raw 文件。后者会破坏“一次尝试、不可重试”的证据身份，使后续结果无法证明是原始 fresh 判断。

根因分类：`REASONING`、`MODEL`、`ACQUISITION_MODULE / RUNTIME`。

## 可执行修复

1. 新增 `persist_fresh_agent_response` 作为受控 raw 写入入口。它要求固定的 fresh-context 声明（未读取旧 cohort、父上下文、兄弟输出、结果和外部 provider），并拒绝已有响应或终态 cell。
2. `finalize_fresh_cell` 在 Episode 无效、配对读者失败或成功冻结后都将 raw response 设为只读，并在 receipt 中记录 `raw_response_sealed=true`。后续应新建 cohort，不得改写该文件。
3. fresh task 的语义要求前置列出 route id 与角色：primary、corroborative、stress、excluded；组件 binding 的 use 必须与角色相容，避免把 schema 可接受的绑定误当成经济有效的绑定。

## 验收标准

- 受控入口缺失或错误声明时不写 raw；同一 cell 已有响应或已终态时拒绝写入。
- 任一终态 receipt 均标记 raw 已封存，且文件不可写。
- 现有 cohort 的失败 receipt、quarantine 与 `UNKNOWN` 效用结论保持不变；不读取 outcome、不重跑 CASE:01。
- 针对性测试覆盖上述行为，并通过后才允许建立新的未见公司四臂 cohort。

