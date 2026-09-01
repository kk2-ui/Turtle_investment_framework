# 孚日股份 `CN:002083 × 2019-05-01`：首个 Enterprise Judgment Episode

> 状态：`REAL_J1_SAMPLE / E0_E1_ONLY / OUTCOME_SEALED / NOT_AUTHORIZED`
>
> cutoff：`2019-05-01T00:00:00+08:00`

这是重构后首个真实企业判断训练样本，不是 Comparative、Forecast、估值或选股样本。它采用 FY2014--FY2018 的五份 cutoff 前 CNINFO 官方年报；只重建上市公司合并口径的业务/渠道、出口敞口、盈利与经营现金事实，以及这些事实之间的有限推断。

输入与派生顺序：

```text
01_source_packet_receipt.json
  -> 02_decision_contract.json
  -> 03_enterprise_system_model.json + 04_management_decision_ledger.json
  -> 05_j1_reconstruction_spec.json
  -> 06_episode_manifest.json
  -> runtime J1 / J0 read models
```

`01` 是唯一 source packet。每个 PDF URL 是 H1 static catalog 已登记的官方 CNINFO static-finalpage locator；本仓未声称已 materialize PDF。公告可得时间只到日期精度，adapter 将其处理为当地日结束的保守上界，故 `2019-05-01` 不借用同年 5--12 月材料。

`04` 有意为空。年报叙述存在经营举措，但不足以重建一个具有明确问题、替代方案、承诺、执行时点与责任范围的材料性决策序列。因此 `05` 的 `decision_observation=INSUFFICIENT_EVIDENCE`，不是“公司没有行动”的断言。管理行动、资本配置细节、客户反应、竞争份额、永久损失测量及任何同行因果比较保持 `UNKNOWN` 或未启动。

运行验证位于 `tests/test_cn002083_20190501_j1_episode.py`。它只使用本目录 inputs 和 J1/J0 compiler；不会读取价格、后续结果或 outcome custody。
