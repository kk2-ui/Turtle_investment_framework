# Golden Set v1 注册表（G2 后）

> 集合状态：`G3_NOT_READY`  
> 当前阶段：`G2_CROSS_REPORT_ADJUDICATION_COMPLETE`  
> 正式 Golden 成员：`0`

| 代码 | 公司 | 案例责任 | 当前候选状态 | 主路线 | 主价格身份 | G3资格 |
|---|---|---|---|---|---|---|
| 87001.HK | 汇贤产业信托 | 有限期限 REIT、债务/分派/终局顺位 | `ACCEPT_WITH_DATA_LIMITED`（读者和矩阵局部通过） | `FINITE_LIFE_XIRR` | `P_LEGAL` | `NOT_READY` |
| 900936.SH | 鄂尔多斯B | 多实体周期制造、NCI和汇率 | `ACCEPT_WITH_DATA_LIMITED`（读者语义通过） | `DUAL_ROUTE`（长期主） | `P_LONG` | `NOT_READY` |
| 000651.SZ | 格力电器 | 成熟消费制造、金融资产和资本配置 | `ACCEPT_WITH_DATA_LIMITED`（读者深度通过） | `LONG_TERM_OWNER` | `P_LONG` | `NOT_READY` |
| 01522.HK | 京投交通科技 | 项目资本、关联订单和现金回收 | `OBSERVE / READY_FOR_INDEPENDENT_REVIEW_NOT_GOLDEN` | `FINITE_XIRR` | 无新确认 `P_XIRR_FIXED_TERMINAL_5` | `NOT_READY` |
| 02669.HK | 中海物业 | 轻资产物业、关联生态和现金转换 | `REVISION_CANDIDATE / NOT_GOLDEN` | `LONG_TERM_OWNER` | 长期回报价格 | `NOT_READY` |
| 00506.HK | 中国食品 | 装瓶商产品结构、毛利/费用杠杆 | `ACCEPT_WITH_DATA_LIMITED` | `LONG_TERM_OWNER` | `P_LONG` 区间 | `NOT_READY` |
| 00882.HK | 天津发展 | 综合控股、内部债权、NCI和现金上游 | `ACCEPT_WITH_DATA_LIMITED` | `DUAL_ROUTE / PRIMARY_ROUTE_UNKNOWN` | `null`（条件诊断） | `NOT_READY` |
| 600585.SH | 海螺水泥 | 重资产水泥周期、维护资本和净现金 | `ACCEPT_WITH_DATA_LIMITED` | `LONG_TERM_OWNER` | 零确认折价路径诊断 | `NOT_READY` |
| 601899.SH | 紫金矿业 | 逐矿寿命、项目、联营现金与再投资 | `ACCEPT_WITH_DATA_LIMITED` | `DUAL_ROUTE / PRIMARY_ROUTE_UNKNOWN` | 无正式主价格 | `NOT_READY` |

## 进入 G3 前的集合级阻断

1. 中海物业尚未完成当前 revision 的集合级内容接纳；
2. 汇贤25%现金税/泄漏、BOP台账和实体可达性仍是材料性未知；
3. 天津发展、紫金的主路线仍未知，不能冻结主价格；
4. 京投的条件确认回报不能作为无条件动作价格；
5. 格力、中国食品、海螺和鄂尔多斯虽有局部/候选通过，仍未完成跨案例传播和集合级用户审阅。

因此 G3 保持 `NOT_READY`，G4/G5 不启动。
