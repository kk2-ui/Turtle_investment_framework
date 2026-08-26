# Turtle V5 审阅回执快照补充约定

> 状态：`CURRENT_FOR_SLICE0_1_REVIEW_BINDING`
>
> 日期：2026-08-24
>
> 上位约束：[V5 最小实现工作包](TURTLE_V5_MINIMAL_IMPLEMENTATION_WORK_PACKAGE.md) §3.4–3.4.1。

## 决定

`selection_bundle` 仍是 V5 唯一的经济真源，并且同一 root 必须原样经由
admission validator、seal 与 outcome resolver。不得新增第二个 candidate bundle、
adapter、metric map、数据库对象或下游读取入口。

为使独立 pre-outcome reviewer 的已接受意见能约束其后的 seal，
`independent_pre_outcome_review.reviewed_selection_contract` 可保存 root 中全部
**非 review** material fields 的逐字段回执快照。它不是第二个经济对象：

- 它只由 admission validator 作与 root 当前字段的精确相等比较；
- outcome resolver、control-plane calculation、报告和任何下游消费者只能读取 root
  的 canonical fields，绝不得读取该回执作为公式、面板、来源或结论输入；
- 任一差异（包括 metric formula、threshold、raw matrix、panel、scope、time、
  collision key 或 firewall receipt）使 selection `NOT_ADMITTED`，必须获得新的
  reviewer acceptance 后才可 seal；
- 这是单一 root 内、为独立审阅可验证性设置的受限例外，不能泛化为第二套
  projection、compatibility shape 或 artifact lifecycle。

该约定不引入真实公司资料、生产数据库、R-103/R-104、post-outcome review、
method release 或新的 memory 基础设施。
