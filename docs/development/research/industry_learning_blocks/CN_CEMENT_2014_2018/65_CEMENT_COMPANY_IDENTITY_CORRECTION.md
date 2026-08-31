# 水泥公司身份纠正：`CN:600425`

> 状态：`MATERIAL_IDENTITY_ERROR_CONFIRMED / PACK_V2_SUPERSEDED_FOR_NEW_USE`
>
> 纠正日期：2026-08-31
>
> 影响类别：`ACQUISITION_MODULE + WRITING`

## 结论

现有水泥 Pack V2 及其 worked-case 来源把证券代码、公告编号和控制人正确绑定到了 `CN:600425`，但多处自由文本错误地写成“天山股份 / Xinjiang Tianshan Cement”。官方年报 `CNINFO:600425:ANN:20180421:1204677754` 的封面明确写明：

- 公司代码：`600425`
- 公司简称：`*ST 青松`
- 法定全称：`新疆青松建材化工(集团)股份有限公司`

因此，Pack 中 2017 年水泥销量 687.46 万吨、同比增长 7.61%、水泥毛利率 16.78%及提高 3.96 个百分点，均属于青松建化，不属于天山股份。真正的天山股份证券代码是 `000877`，不能与 `600425` 合并为一个发行人经验。

## 投资影响

这不是排版错误。若继续把青松建化的新疆区域规模、成本结构、控制人和盈利恢复归给天山股份，会污染区域成本原型、重复计算已参加 Course 1 的 `CN:000877`，并可能让后续 Agent 对正常盈利、owner cash、永久损失及价值路线使用错误的公司参照。

多公司共同冲击的方向性结论暂不翻转：海螺、青松建化和福建水泥在同一行业恢复下仍出现不同利润和现金结果；华新、冀东仍属于责任边界案例。需要纠正的是发行人归属，不是把现有数字改写成另一组结果。

## 对 Course 2B 的处理

Course 2B 的 Enhanced arm 读取的是目标公司 `CN:000672` 的 cutoff-safe `IndustryUnderwritingContext`。其中代表公司名称均为 `UNSPECIFIED`，`CN:600425` 只以代码、原型和官方 source id 出现；该 arm 没有读取 Pack V2 中错误的“天山”名称或公司数值 discriminator。因此既有 `NO_MATERIAL_UTILITY / MODEL + DATA_COVERAGE` 裁决保留，不因本次身份纠正改写。

本结论不表示 Pack V3 已经证明方法效用。V3 只恢复可安全训练的身份边界，仍需新的公司轴 A/B 验证。

## 修复

1. V1/V2 与 Course 2B 历史工件保持不变，作为当时实验记录。
2. 新的公司共同冲击投影逐家公司绑定 `company_id + security_code + issuer_legal_name + exact_name_quote + source_id + publication_date + PDF page`。
3. Pack V3 只能引用纠正后的投影；所有 `600425` 叙述统一为青松建化。
4. Pack validator 对 V3 及以后强制检查上述身份绑定，且 CNINFO source code 必须与公司代码一致。

## 接受标准

- `CN:600425` 的 identity binding 精确指向青松建化和公告 `1204677754`；
- V3 的共同冲击叙述、结算源和范围条件不再出现天山名称；
- V2 文件保持不变，Course 2B 历史裁决保持不变；
- Pack V3 机械状态仍为 `TRAINING_READY`，不升格为 transfer candidate；
- 独立审阅者回读官方封面与第 10--12 页并确认公司归属和数值归属。
