# R-13 中国边界复验候选：准入登记

状态：`SCREENING_ONLY / NO_COMPANY_CONCLUSION / NO_OUTCOME_READ`

用途：为 [R-09 至 R-12 批次复盘](R-09_R-12_china_micro_drill_batch_review.md) 的下一批 `boundary` 角色登记实际处置，避免因资料可得性、公司知名度或已读材料而反复重入。它不是候选公司的研究报告，也不基于价格、回报或后续经营结果选案。

| 对象 | 已核对的最小前提 | 处置 | 原因与下一动作 |
|---|---|---|---|
| PDD | 2023 Q1 结果可见；本次受限 SEC metadata 检索未找到 cutoff 前可定位的 Q2 结果事件。 | `DEFER / RESULT_EVENT_UNVERIFIED` | 这不声称公司未发布预告，只说明当前没有预先锚定的 publisher/event/window/label 五元组；不读 Q2 结果。若以后先找到 cutoff 前官方预告，再从未暴露的事实包重启。 |
| Full Truck Alliance | 业务概念上接近外部货运平台；本次 SEC metadata 未提供 cutoff 前可定位的 Q2 结果事件。 | `DEFER / RESULT_EVENT_UNVERIFIED` | 不以平台常识替代结果合同；同上。 |
| Bilibili | Q2 结果公告时间在 cutoff 前由公司预告；Q1 有广告、VAS、游戏等收入类别。 | `DEFER / EXTERNAL_BOUNDARY_UNVERIFIED` | 当前已读材料不足以把报告类别逐项绑定为本题要求的外部客户/无内部抵消边界；不能从平台常识推断。只有一手收入确认或客户/内部结算边界进入事实包，才可继续。 |
| Kuaishou | Q1/Q2 结果事件在官方 IR 链可定位。 | `CLOSED / CONTEXT_EXPOSURE` | 候选检索页直接暴露了 Q1 管理层叙事，不能再声称“先事实后解释”。它可用于结果已知教学，不可用于检验两遍训练。 |
| Tencent Music | Q2 results event 的公司/HKEX 公告可在 cutoff 前定位。 | `CLOSED / FACT_PACKET_LEAK` | 旧关键词过滤器在 Q1 表格节点输出管理层项目叙事，触发 P-60.4；不在本候选上补做白名单抽取。下一未暴露对象才检验新规则。 |

## 准入结论

本轮没有合格 `boundary` card 可以冻结。根因是 `ACQUISITION_MODULE + DATA_COVERAGE + REASONING`：有的缺结果事件，有的外部收入边界未被一手定义，有的已发生解释暴露。经济影响是若为填满 `1 + 1 + 1` 强行入场，会把内部收入、叙事锚定或事后结果源混入“外部需求”判断，错误迁移到正常收入、现金转换和永久损失分析。

缺失的是符合下列所有条件的一个未暴露中国对象：

1. cutoff 前已定位 `publisher + event + window + calendar/URL metadata + label`；
2. 一手材料能把主收入/单位指标界定为外部客户、内部结算或两者的明确边界；
3. `FROZEN_METRIC_SLICE` 只返回预列标签、数值、单位、期间与 locator；
4. 同一对象有可冻结的 H-A/H-B 和与简单基线不同的结果合同。

禁止假设：更多报告、双重上市、平台商业模式、分部名称、股价或已知后果能补足上述任一项。接纳标准是下一对象先通过四项，再读取深层公司材料；否则本登记维持 `SCREENING_ONLY`。
