# 中国水泥行业经验 Pack V3 发行人身份独立审阅

> 裁决：`PASS / IDENTITY_CORRECTION_ACCEPTED / PACK_TRAINING_READY`
>
> 审阅对象：`IEP:CN:CEMENT_LISTED:2014_2018:TRAINING:V3`
>
> 前次 RETURN 根因：`ACQUISITION_MODULE + DATA_COVERAGE`
>
> 知识截止：`2018-04-30T23:59:59+08:00`

## 投资者结论

发行人纠正实质正确，前次 validator 的材料性逃逸已经关闭，可以接受 Pack V3。官方 CNINFO 年报证明 `CN:600425` 是新疆青松建材化工(集团)股份有限公司，而不是天山股份；687.46 万吨、7.61%、16.78% 和提高 3.96 个百分点也都属于青松建化。V3 已把活跃训练叙述和共同冲击投影绑定到青松建化，V2 历史文件保持不变，Course 2B 继续为 `NO_MATERIAL_UTILITY`，Pack 仍只能为 `TRAINING_READY`。

修复没有改变行业中心判断：2017 年水泥利润池恢复仍最可能由价格与有效供给纪律驱动，但未解决过剩、区域差异、成本传导和资本吸收限制其耐久性。同一冲击下公司的利润与现金分化仍成立；纠正改变的是公司归属，避免把青松建化的新疆区域经济错误归给 `CN:000877` 天山股份。

最强竞争解释是：catalog 与 projection 都是本地工件，若两者被协同改错，机械比较仍无法代替官方原件。该风险不阻断本次接受：catalog 已与六份官方封面独立复核，且它与待验证 projection 是分离的 source object；本项目是本机协作研究流程，不需要为假想对手增加运行时联网、哈希或另一层重复守卫。真正发生过且材料的两种失败——projection 自洽错名和活跃叙述错绑——现在都被确定性拒绝。

## 官方原始资料复核

`CN:600425` 官方文件：`https://static.cninfo.com.cn/finalpage/2018-04-21/1204677754.PDF`。

- 封面（PDF p1）写明公司代码 `600425`、公司简称 `*ST 青松`、法定全称“新疆青松建材化工(集团)股份有限公司”。
- PDF p10 写明新疆水泥产能过剩仍持续、水泥销量同比增加 `7.61%`，并描述公司超过 1,800 万吨的区域产能及停产化工子公司；这些均是青松建化的发行人边界。
- PDF p11 的水泥产品表写明水泥收入 191,174.59 万元、毛利率 `16.78%`、收入同比增加 17.61%、成本同比增加 12.28%、毛利率同比增加 `3.96 个百分点`。
- PDF p12 的产销量表写明水泥生产量 683.34 万吨、销售量 `687.46 万吨`、库存量 17.14 万吨，销售量同比增加 `7.61%`。

identity catalog 的其余官方 CNINFO 封面也一致：

- `CN:600585 / 1204507132`：安徽海螺水泥股份有限公司；
- `CN:600802 / 1204639756`：福建水泥股份有限公司；
- `CN:600801 / 1203190337`：华新水泥股份有限公司；
- `CN:000401 / 1204506085`：唐山冀东水泥股份有限公司；
- 冲突身份 `CN:000877 / 1204507441`：新疆天山水泥股份有限公司，封面品牌短名“天山股份”。

因此 `65a_cement_issuer_identity_catalog_v1.json` 对 Pack 五家公司及已知冲突公司的代码、法定名称、官方短名、source id、发布日期和封面页绑定正确；`66_cement_shared_shock_company_projection_v2.json` 的五家公司身份逐字段与 catalog 一致。

## 前次 RETURN 的关闭证据

### 独立机器可读身份真源

V3 将 `65a_cement_issuer_identity_catalog_v1.json` 作为 `ISSUER_IDENTITY_CATALOG / CUTOFF_SAFE_EVIDENCE / INCLUDED` source object。validator 要求 V3 worked case 的每家公司 identity 在以下字段逐项等于 catalog：

- `company_id`；
- `security_code`；
- `issuer_legal_name`；
- `exact_name_quote`；
- `source_id`；
- `publication_date`；
- `pdf_page_ref`。

这修复了旧逻辑只判断 `issuer_legal_name == exact_name_quote`、两个字段可一起写错的问题。catalog 还纳入 `CN:000877` 及“天山股份 / 天山水泥 / 新疆天山水泥”别名，使错误名称被识别为另一个正式发行人，而不是未知普通文字。

### 活跃训练叙述绑定

V3 的 `current_synthesis`、共同冲击 discriminator 和 `settlement_plan` 使用 `[[company_id|catalog alias]]` token。validator 同时检查：

1. token 的 company id 存在于 catalog；
2. 显示名称属于该 company id 的法定名称或官方短名；
3. 共同冲击 discriminator 的 token company ids 与结构化 `company_ids` 完全一致；
4. catalog 中已知发行人名称不能脱离 token 出现在活跃训练文字。

这不是格式性增强。它直接阻止错误公司原型、销量、利润率和现金路径进入正常盈利、owner cash、永久损失或价值路线参照。

## 两个原始反例复测

### 反例一：法定名称与 quote 同时错误但自洽

在 `66` 临时副本中，将 `CN:600425` 的 `issuer_legal_name` 与 `exact_name_quote` 同时改为“新疆天山水泥股份有限公司”，保留公司代码、source id 和证据 source id。复测结果：

- `state = INVALID`；
- `derived_state = DRAFT`；
- findings 同时包含 `catalog_mismatch:issuer_legal_name` 与 `catalog_mismatch:exact_name_quote`；
- 共同冲击证据不再获准，出现 `shared_shock_evidence_bundle_incomplete`。

新增参数化回归还对 Pack 五家公司逐一实施相同的自洽错名替换，均由同一 catalog 机制拒绝，没有为 600425 写单案补丁。

### 反例二：结构化身份正确、活跃叙述错绑

保持 `66` 正确，把活跃 V3 的 `[[CN:600425|青松建化]]` 改为 `[[CN:600425|天山股份]]`。复测结果：

- `state = INVALID`；
- `current_synthesis`、共同冲击 discriminator 和 `settlement_plan` 均报告 `issuer_identity_token_mismatch:CN:600425`；
- 即使其余成熟度证据仍完整，错误活跃叙述也不能成为 `REVIEWABLE` Pack。

正确的 `65a + 66 + 67` 则返回：`state = REVIEWABLE`、声明与派生状态均为 `TRAINING_READY`、`findings=[]`、`training_readiness_gaps=[]`。

## V2、Course 2B 与成熟度

`63_industry_experience_pack_training_v2.json` 与 `64_industry_experience_training_ready_review.md` 没有工作树差分，历史 V2 保持原样；其中“天山”文字作为当时错误记录保留，没有回写历史工件。

Course 2B Enhanced contract 只允许读取目标公司 `CN:000672` 的 pre-cutoff sources、冻结 IndustryUnderwritingContext 和训练记忆。该 context 对五家代表公司均使用 `company_name = UNSPECIFIED`，`CN:600425` 只通过代码、archetype 和 `CNINFO:600425:ANN:20180421:1204677754` 指针出现，没有读取 Pack V2 中错误的“天山股份”名称或该公司的数值 discriminator。因此发行人纠正不能反向改变冻结 A/B 比较。

最终映射裁决继续是：行业路径 `NO_MATERIAL_DIFFERENCE`、公司传导 `NO_MATERIAL_DIFFERENCE`、整体 `NO_MATERIAL_UTILITY`。V3 的 `transfer_reviews` 只记录该负结果，没有任何独立 `MATERIAL_UTILITY` 公司轴或时间轴；按派生成熟度规则仍只能 `TRAINING_READY`，不得升为 `TRANSFER_CANDIDATE` 或 `RELEASED`。

## 接受标准结算

- `CN:600425` legal name 与 quote 同时改成错误但自洽的天山名称：`PASS`，validator 返回 `INVALID`；
- projection 正确、活跃 V3 token 把青松绑定成天山：`PASS`，validator 返回 `INVALID`；
- Pack 五家公司任一 legal name 被同样自洽替换：`PASS`，同一通用机制拒绝；
- 正确 `66 + 67`：`PASS`，仍为 `REVIEWABLE / TRAINING_READY` 且无 gaps；
- V2 零差分：`PASS`；
- Course 2B 保持 `NO_MATERIAL_UTILITY`，没有新增方法、迁移、估值或投资权限：`PASS`。

## 定向测试

- `.venv/bin/python -m pytest tests/test_industry_experience_pack.py -q`
- 结果：`15 passed in 0.53s`
- 额外独立负向探针：两个原始逃逸均返回 `INVALID`；正确 V3 返回无 findings 的 `REVIEWABLE / TRAINING_READY`。

本次复审未读取新的 outcome 封存结果，未调用任何外部模型 API。
