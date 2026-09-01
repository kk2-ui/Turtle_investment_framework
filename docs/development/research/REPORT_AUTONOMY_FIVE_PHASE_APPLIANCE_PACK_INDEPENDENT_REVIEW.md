# 家电行业经验包独立复审

> 结论：`PASS`  
> 复审范围：修复后的 `scripts/industry_context_acquisition.py`、其测试，以及 `CN_APPLIANCE_2017_2018/03`、`03a`、`06`、`08`、`09`。  
> 信息边界：只读取截至 `2018-12-31` 的 Pack 内来源、身份和上下文材料；未读取任何 2019 年后、价格、估值、回报或结果资料，也未调用外部模型 API。

## 对原 RETURN 的修复复核

- `03_official_industry_context_observations_v1.json` 现将国家统计局 2018 年 1--11 月“家用电器和音像器材类”累计零售额正确记录为 `RMB 796.5bn`，并将实物商品网上零售额正确记录为 `RMB 6,271.0bn`。它们分别对应原文的 `7,965 亿元` 和 `62,710 亿元`。
- 两个数值均有可复核的 `quantity_provenance`：原生值、`RMB_100M` 原生单位、`RMB_BN` 标准化单位、标准化数值，以及指向本地官方 raw 的原文/table locator。换算关系为 `亿元 × 0.1 = RMB bn`，与原文一致。
- 采集模块对已声明的 `quantity_provenance` 执行可复用校验；错误的 `7,965 亿元 -> RMB 79.65bn` 映射会返回 `quantity_provenance[0]_conversion_mismatch`。新增负例测试通过，完整 `tests/test_industry_context_acquisition.py` 为 `8 passed`。对实际家电 ledger 重跑 `validate-observations` 得到 `REVIEWABLE_CONTEXT_ONLY`，与更新后的 `03a` 一致。

## 未改变的 Pack 边界

- 官方共同环境仍是 `CONTEXT_ONLY`：全国生产、零售、产销率、行业利润或标签目录不能被写成公司销量、份额、价格、库存、现金、估值或竞争优势。
- `06` 仍将行业路径及四家公司差异限定为候选机制、责任边界和目标公司必须独立完成的取证问题；没有把共同环境变成任何公司的业绩、现金或投资结论。
- `08` 的 `TRAINING_READY` 仍仅代表机械的来源/结构就绪：`transfer_reviews` 为空，边界明确否认目标公司事实、估值/投资权限和能力证明。`09` 仍只保留行业主路径、最强反方、参考类别、独立取证问题与反转观察，未声称 utility 或 transfer。

## 来源与身份复核结论

四项官方行业来源均保留官方 host、本地 raw 文件和不晚于 `2018-12-31` 的发布时间与数据截止日。四家发行人身份仍由代码、法定名称、精确名称引文、CNINFO source ID、发布日期和 PDF 页码追溯，身份再策展审计的直接 CNINFO 年报核对均在 cutoff 前。

本次 PASS 只接纳该 Pack 的机械训练输入与边界完整性；不构成公司判断、估值/投资结论，亦不构成 transfer 或 utility 证明。
