# 结果出现不等于预测方法需要改变

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`REAL_LOCAL_FORECAST_ERROR_REQUIRED / REVIEWER_PROSE_HAS_NO_AUTHORITY`

## 被纠正的奖励错位

旧 Forecast attribution 只要引用一个 `OBSERVED` cell，reviewer 就可能把它标成
`CALIBRATION`、`STATE_DEFINITION`、`UNCERTAINTY_POLICY` 或 `BASELINE_PERFORMANCE`，并生成
活跃 policy。预测即使完全正确、Brier/RPS 为零、且与公平 baseline 完全相同，也可能因为一段
解释性文字被记成“学到了方法”。

这会奖励结果后造规则，而不是结果前判断接受现实检验。

## 当前机械语义

Forecast policy 只从冻结概率、同 cell 的真实 settlement 和必要时的冻结 baseline 派生：

- `CALIBRATION`：唯一 modal 类别与实际类别发生方向性错判；
- `UNCERTAINTY_POLICY`：实际发生的类别在冻结预测中被赋予零概率，或二元确定性被推翻；
- `BASELINE_PERFORMANCE`：公平 baseline 的 modal 类别正确、enhanced forecast 错误，且 baseline
  的 Brier 严格更优；
- `STATE_DEFINITION`：当前载荷不能机械识别该根因，因此只能 `NOT_DIAGNOSTIC / NONE`；
- `COVERAGE`：继续只接受已登记的 `MEASUREMENT_MISMATCH`，不与预测误差混合。

modal 并列和 binary `0.5` 没有唯一方向，不产生学习。引用的每个 cell 都必须各自满足对应错误
条件；夹带正确、无关或不可结算 cell 会使整项 attribution 失效。

```text
预测正确，或 baseline 与 enhanced 相同
    -> NONE

结果出现，但无法识别具体错误类型
    -> NOT_DIAGNOSTIC / NONE

冻结 modal 方向被同维度、同期限真实结果推翻
    -> 局部 error signature
    -> 对应 Forecast policy 才可 DIRECT
```

## 防止局部错误被全局化

Control plane 在注册和读取 active policy 时都从已冻结 forecast、registered settlement，以及
需要时的 registered pairing 重新推导，不采用 reviewer 自报分数或结论。活跃 policy 保留：

- `dimension_id` 与 `window_id`；
- `expected_label -> realized_label`；
- `error_kind`；
- baseline 路径的 `baseline_expected_label`。

因此一家公司一个期限上的预测错误，只能修正对应局部预测行为，不能自动传播为所有公司、所有
期限的状态定义或不确定性政策。

## 对训练的意义

结果本身不是学习成果，正确预测也不需要为了“有反馈”而强行改方法。训练信用来自一个可定位、
可反驳、会改变下一次预测处理的真实错误。该信用仍不等于 transfer validated、method frozen，
也不授予 Comparative、CJO、正式估值、BuyBand、报告发布或投资权限。
