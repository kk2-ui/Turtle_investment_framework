# CN600309 outcome custody isolation incident

状态：`CUSTODIAN_DISCARDED_BEFORE_OUTCOME_READ`。

原 custodian 为定位 FY2024 年报误打开上交所公告列表接口。该接口忽略其本意中的年度报告过滤，返回了 CN600309 其他 2025 公告的标题、日期与 URL 元数据。custodian 未打开这些文件、未读取 FY2024 年报正文或任何结果数值、未写入 settlement，也未改动仓库；已关闭其浏览器任务空间。

这不改变 72–76 号结果前冻结工件，也不构成任何企业、方法或投资结论。由于原合同禁止接触其他结果期资料，原 custodian 角色作废。后续只可由新的 fresh custodian 经 78 号恢复授权，直接打开唯一指定的官方 FY2024 年报 URL；不得再次使用公告列表或搜索页。
