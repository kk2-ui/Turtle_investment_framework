# U1 独立产品审阅：海螺水泥完整承保切片

审阅结论：`ACCEPT`

## 审阅范围

- `MAGNA_200903_WORKED_CASE_V1.json`
- `CN600585_20240501_WORKED_CASE_V1.json`
- 海螺投资者读本及三份同源 projection
- `scripts/enterprise_underwriting_episode.py`
- `tests/test_enterprise_underwriting_episode.py`

## 裁决

海螺形成了连续、可用的承保路线：周期处境 → 生存缓冲 → 保守中周期正常盈利 → owner-cash 的局部边界 → 永久损失传导 → 资产价值/EPV/资本回报交叉路线。

`CANNOT_BOUND` 只限制普通股 owner cash 的单点估计；生存、国内核心、增量资产、海外情景和价值路线仍分别处理，没有退化为整家公司 `UNKNOWN`。

麦格纳仅保留“先判生存、再选资产/EPV 路线”的结构性 near miss。海螺结论来自其自身水泥需求、量价、成本、资本与项目现金证据，未导入麦格纳的恢复结论。

三份 projection 都由 `UWT:CN600585:20240501:V1` 精确确定性投影，保持教学、路线请求与报告 handoff 的权限边界；没有生成 CJO、价值、价格、BuyBand、报告发布或投资动作。

验证：`tests/test_enterprise_underwriting_episode.py`，`6 passed`。
