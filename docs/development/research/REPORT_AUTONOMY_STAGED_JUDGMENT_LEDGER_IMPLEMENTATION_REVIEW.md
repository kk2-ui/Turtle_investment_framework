# Staged Judgment Ledger v1 — implementation review

结论：PASS（最小 v1，price-free）。

本实现新增 `scripts/staged_judgment_ledger.py` 与离线
`tests/test_staged_judgment_ledger.py`。Validator 固定检查 v1 顶层/claim/component
字段、J0/J1/J2 八个经济面、UNKNOWN 局部诊断、翻转观察、组件权限、来源索引及
TRAINING_MEMORY 边界；价格、收益、估值结果和动作键在任意嵌套位置均拒绝。

Compiler 是纯复制/排序/绑定流程：从 ledger 生成 EnterpriseUnderwritingEpisode v2
所需 situation model、claims、component treatments/decisions、value-route buckets、
evidence trace 与 underwriting thesis；不补写经济事实，不生成价格或数值，不把
UNKNOWN 转成零或负面。阻断诊断以 `staged-ledger-diagnostics.v1` sidecar 保留，
不会输出可消费 Episode。

验证范围：synthetic 最小账本、确定性双编译、UNKNOWN 合法局部处理及 price firewall。
当前容器未安装 pytest（`python3 -m pytest` 报 No module named pytest），因此未执行
pytest runner；模块可直接导入并完成 validator/compile smoke check。建议在项目测试
环境安装既有依赖后运行 `pytest -q tests/test_staged_judgment_ledger.py`，并接入两个
worked fixture 做完整 Episode/projection parity 验收。

审阅分类：无需 RETURN。若后续接入真实 fixture，新增事实采集或 route contract 变化
应分别在 source index/contract 层修复，不在 compiler 中增加推理或默认值。
