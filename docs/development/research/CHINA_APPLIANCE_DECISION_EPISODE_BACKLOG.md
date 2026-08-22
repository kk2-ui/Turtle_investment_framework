# 中国早期家电：经营决策 episode 队列

状态：`ACTIVE_DISCOVERY / COMPANY_FIRST / NO_PRICE_OR_RETURN_CONCLUSION`

关联：[中国家电竞争史训练地图](CHINA_APPLIANCE_COMPETITION_TRAINING_MAP.md)、[企业经营判断训练方案](TURTLE_ENTERPRISE_JUDGMENT_TRAINING_BLUEPRINT.md)、[企业经营判断取证路线](TURTLE_ENTERPRISE_JUDGMENT_SOURCE_ROUTING.md)。

本表是研究目标的执行队列，不是公司排名、幸存者名单或案例库。一个对象只有在满足其当前层级的准入条件时才可前进；资料增多本身不改变层级。

## 1. 统一入场与退出规则

```text
STATE_REPERTOIRE
  → 可训练状态、行动和替代方案；不评价经济效果。

RESULT_KNOWN_TEACHING
  → 可用已知后果训练错误归因与条件边界；不计作 agent 判断。

OUTCOME_CONTRACTED_EPISODE
  → 只有决策时点、反方、同口径结果包均在冻结前定位后，才可进入判断反馈。
```

若一个 candidate 的新材料不能改变 `历史状态 / 实际决策 / 可行替代 / H-A-H-B 分叉 / 同口径结果合同` 之一，停止阅读，不为它增加公司史细节。

## 2. 当前队列

| ID | 历史状态与实际决策 | 训练的经营判断 | 当前材料身份 | 当前缺口与下一动作 | 明确不做什么 |
|---|---|---|---|---|---|
| `MW-01` | 1996 微波炉：国内进入者众多、外资进入；格兰仕对两款主销机型降价 40%。[同期原文](https://rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1996/10/1996-10-22.htm) | 制造商降价何时是利用率/成本位置投入，何时只是让行业租金下降？ | `RESULT_KNOWN_TEACHING / MIXED` | 1998 同期后续报道形成份额/产能与进入反应的有限观察；完整量价—现金合同仍缺。见 [R-14](experiments/R-14_china_appliance_price_teaching/00_galanz_1996_price_learning_review.md)。 | 不以份额、产能、管理层行业整合主张或后来的品牌位置裁决。 |
| `AC-02` | 1996 空调：经销商降价，引发春兰、华宝的区域价格和待遇/制裁冲突。[同期原文](https://rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1996/08/1996-08-03.htm) | 制造商控价是在保护服务/回款/渠道网络，还是维持低效价格与压货？ | `RESULT_KNOWN_TEACHING / MEASUREMENT_MISMATCH` | R-14 的进入反应要求已应用；取得的后续材料只确认渠道架构，不能同口径结算。见 [R-15](experiments/R-15_air_conditioner_channel_price_teaching/00_chunlan_huabao_1996_channel_price_review.md)。转入 `JV-01`，不继续补公司史。 | 不与 MW-01 拼成同品类 near miss，也不把消费者支持低价等同于经济结果。 |
| `JV-01` | 1996 冰箱：扬子向合资企业授予冰箱/冰柜商标使用权，并以技术和资金为交易理由。[同期原文](https://rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1996/12/1996-12-06.htm) | 合资引进技术何时转化为成本/产品能力，何时以品牌、控制或未来现金为代价？ | `RESULT_KNOWN_TEACHING / ATTRIBUTION_INSUFFICIENT` | R-15 的权利—控制—组织—现金拆解已应用；后续仅有叙事性逆风信号，不能归因裁决。见 [R-16](experiments/R-16_yangzi_bosch_siemens_joint_venture_teaching/00_yangzi_1996_brand_and_control_review.md)。下一案换公司与组织动作。 | 不把一次性对价、资产评估、技术宣传或交割直接写为资本配置成功。 |
| `HI-02` | 1995 洗衣机：海尔整体接收经营困难的红星电器，候选机制是以管理/质量/资金调度重建组织。 | 经营系统能否跨工厂、员工与品类迁移，且产生可持续现金改善？ | `RESULT_KNOWN_TEACHING / ATTRIBUTION_INSUFFICIENT` | 早期扭亏说法和并购当年产量可用于教学，仍缺同期交接与同主体经营披露。见 [R-17](experiments/R-17_haier_redstar_integration_screen/00_1995_redstar_integration_screen.md)。 | 不把后来的规模、三/五个月扭亏口径或管理传记当作整合能力证据。 |
| `HQ-01` | 1994–1995 冰箱/耐用品：海尔在已纳入集团的冷柜、空调厂使用品牌，并把售后服务和品牌延伸放在一起。[同期原文](https://www.rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1995/03/1995-03-02.htm) | 品牌延伸和服务制度何时能降低新业务获客/质量成本，何时会稀释组织与品牌承诺？ | `QUESTION_ONLY` | 需要先找被并入厂的独立产品、组织投入、质量/服务成本和现金边界，才能写实际/替代/不作为。 | 不把品牌声誉、集团规模或后来海外成绩作为当时能力证据。 |
| `ML-01` | 1996 冰箱企业提出以冰箱为支柱、向洗衣机/空调/热水器扩展的“森林战略”。[同期原文](https://www.rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1996/04/1996-04-03.htm) | 多元化是共享品牌/渠道/组织能力，还是资本与注意力分散？ | `QUESTION_ONLY / ACTION_NOT_YET_CONFIRMED` | 已验证到早年审计报表和项目线索的可得性，但洗衣机子公司和上市主体边界不连续；不升级。见 R-18 的边界教训。 | 不用后来业务规模或行业变化把愿景倒写成决策质量。 |
| `MD-03` | 1997 多品类家电集团：美的实行事业部制以回应集中管理与市场响应问题。 | 分权能否把决策权、经营责任和激励转换为更好的客户响应与现金效率？ | `RESULT_KNOWN_TEACHING / MEASUREMENT_MISMATCH` | 行动存在、1996–1997 审计报表存在；但 1998 集团与上市公司收入边界不一致，且缺责任单元结果。见 [R-18](experiments/R-18_midea_divisionalization_source_screen/00_1997_divisionalization_source_screen.md)。 | 不把集团销售额、后来的管理叙事或品牌地位当作组织能力结果。 |
| `TC-16` | 2000 TCL：对主要事业部和子公司实行 KPI、责任书、月度排名、审计和奖惩。 | 目标责任制何时真的把决策权、责任边界与单位经济/现金连在一起，何时只是可观察的考核程序？ | `RESULT_KNOWN_TEACHING / SOURCE_TIER_MISMATCH` | 2004 招股书同时披露制度和若干子公司历史财务资料，但行动文件晚于结果期、无负责人—责任书—法人财务表映射，且制造/销售单位分离。见 [R-31](experiments/R-31_tcl_2000_responsibility_unit_screen/00_2000_kpi_responsibility_unit_screen.md)。 | 不把 KPI、内部审计、法人利润或后来的规模自动当作组织能力证据。 |
| `HK-04` | 2005 冰洗/空调：海信拟取得科龙 26.43% 控制权，并以有代价的预付款代理安排维持危机中的渠道与生产循环。 | 危机收购如何区分商业信用恢复、会计性扭亏与真正的 owner-cash 恢复？ | `RESULT_KNOWN_TEACHING / CLOSED` | 2006 有收入恢复和正 OCF，但营业/扣非利润为负且有补贴；2007 营业、扣非与 OCF仍为负，归母净利受资产处置抬升。结论只针对“自立恢复”支持反方，不裁决交易总价值。见 [R-19 结果复盘](experiments/R-19_hisense_kelon_crisis_acquisition/02_2006_2007_outcome_resolution.md)。 | 不把补贴后的单年净利、后续资产注入、品牌存续或证券回报判作整合成功。 |
| `TCL-05` | 2004 彩电：TCL 与汤姆逊将电视/DVD 业务及资产放入 TTE；欧美原业务已经亏损，目标是通过全球运营协同在 18 个月内改善盈利。 | 资产与品牌合并何时真能变成端到端经营控制、正常盈利与可持续现金，何时只是规模叠加并暴露于技术范式转换？ | `RESULT_KNOWN_TEACHING / CLOSED / CHINA_BOUNDARY` | 2005 欧美经营亏损，销售/营销控制仍在转移；2006 持续经营巨亏与欧洲重组并存，正 OCF 主要需由营运资本释放解释。结论只支持“初始整合路径未显示自立恢复”，不裁决 TCL 或跨境并购总价值。见 [R-20 结果复盘](experiments/R-20_tcl_thomson_tv_integration/02_2005_2006_outcome_resolution.md)。 | 不以彩电销量、全球排名、年末现金、后来的公司转型、价格或回报说明 2004 决策正确/错误。 |
| `CH-06` | 2003 彩电/DVD 出口：长虹在 APEX 应收已达 4.627 亿美元、OCF 为负、短借大增后，仍将深耕北美等海外市场列入年度经营计划。 | 重点客户和出口规模何时是制造/渠道能力，何时是以公司资产负债表替客户融资？ | `RESULT_KNOWN_TEACHING / CLOSED / NO_SELECTION_VERDICT` | 2003 APEX 应收增至 5.372 亿美元且 OCF 仍为负；2004 对 APEX 计提大额坏账并停止业务。结论只支持“信用—现金路径未成立”，不评价某次具体审批或国际化总战略。见 [R-21 结果复盘](experiments/R-21_changhong_apex_credit_growth/02_2003_2004_outcome_resolution.md)。 | 不把坏账后的损失倒灌为 2002 年每笔出货已显然不可收回；不用总收入、后续诉讼、价格或回报裁决。 |
| `KK-07` | 2004 彩电：康佳海外销售增长 80%，新增海外应收中“大部分”投保出口信用保险，公司整体前五销售商占比仅 6.92%，但 OCF 已为负。 | 保险与客户分散何时真正改善可收现金，何时只改变潜在损失分担或融资时间？ | `RESULT_KNOWN_TEACHING / CLOSED / BOUNDARY_ONLY` | 2005 OCF仍为负；2006 OCF转正但应收、存货继续占用现金，应付增加提供主要经营现金流入。它收紧信用工具与现金桥的拆分，不裁决康佳、保险或国际化总成败。见 [R-22 结果复盘](experiments/R-22_konka_export_credit_boundary/02_2005_2006_outcome_resolution.md)。 | 不把“已投保”、全公司低集中度、未见巨额坏账或单年正 OCF当作逐客户回款/信用治理成功。 |
| `HS-08` | 2006 消费电子出口：宏盛科技以保险、保理、共管账户、L/C 和订单驱动采购组织终端零售链，前五客户/供应商均接近全部交易。 | 详尽的信用流程何时真把终端信用转为公司可收现金，何时只是不能穿透的复杂链条？ | `RESULT_KNOWN_TEACHING / CLOSED / CHINA_CONSUMER_ELECTRONICS_BOUNDARY` | 2006 OCF为负；13.59 亿元境外应收超过合同期未收回且审计师无法取得充分可收回性证据，出具保留意见。结论仅反驳“流程已锁定回款”，不判保险失效、个人品格或公司整体成败。见 [R-23 结果复盘](experiments/R-23_hongsheng_trade_credit_chain/02_2006_outcome_resolution.md)。 | 不将流程图、保险费、知名终端、保留意见或后续故事直接替代逐订单、保单、回款与因果事实。 |
| `HX-09` | 2005 彩电/冰箱：海信电器的海外收入增长、票据结算比重上升与库存增加使 OCF转负；前五客户占 36.64%。 | 在客户信用未获充分穿透时，库存周转能否使继续增长的经营恢复现金，而不靠供应商融资？ | `RESULT_KNOWN_TEACHING / CLOSED / POSITIVE_OPERATING_BOUNDARY` | 2006 海外收入继续增长、OCF转正，存货下降带来现金而经营性应付减少；应收仍增，故只支持库存现金修复，不支持客户信用已改善。见 [R-24 结果复盘](experiments/R-24_hisense_turnover_cash_recovery/02_2006_outcome_resolution.md)。 | 不把单年正 OCF、公司对“加快周转”的归因或海外增长写成信用治理/个人决策已验证。 |
| `MD-10` | 2004 空调/压缩机：美的在成本竞争趋紧时完成多基地空调扩能，并推进美芝压缩机能力和东芝开利合资。 | 重资产扩能与关键部件纵向一体化何时形成可被经营吸收的成本/交付优势，何时只是成熟期的供给复制？ | `RESULT_KNOWN_TEACHING / CLOSED / MIXED_OPERATING_OUTCOME` | 2005–2006 空调销量/收入继续增长，但压缩机销量增长未阻止外部收入下降、毛利率降 9 个百分点；两年 OCF均不能归给扩产。见 [R-25 结果复盘](experiments/R-25_midea_2004_capacity_chain_teaching/02_2005_2006_outcome_resolution.md)。 | 不把产能、销量、合资、总 OCF、后来的行业集中度或管理层产业链表述写成项目现金回报或最优资本配置。 |
| `JY-11` | 2005 厨房小家电：九阳后来披露推出商用豆浆机、2006 起加大营销，且有连续三年产销量。 | 新品何时由用户采用转成可持续的单位经济与现金，而不只是一个被事后选中的品类故事？ | `SOURCE_SCREEN / NO_PRIMARY / CONTEXT_SEPARATION_NOT_ASSURED` | 现有来源是 2008 招股书，已混合披露 2005 行动与 2006–2007 结果，缺同期行动、客户采用、单品经济和结果合同。见 [R-26 拒绝记录](experiments/R-26_joyoung_commercial_soymilk_product_screen/00_2005_product_innovation_source_screen.md)。 | 不以销量、专利、后来的品类地位、总收入或“健康需求”替代新品决策和单位经济。 |
| `GR-12` | 2005 空调服务：格力把新购家用空调整机免费包修延至六年。 | 质量/服务承诺何时能穿过故障率、服务成本和客户选择，变成单位经济，何时只是行业共同成本？ | `SOURCE_SCREEN / GREE_PRESSURE_TEST / NO_MANAGER_VERDICT` | 当期动作与 2005–2006 空调收入/毛利可读，但返修率、每台保修成本、客户转换和同口径服务准备缺失；不同会计维修项目不可硬拼。见 [R-27 筛查](experiments/R-27_gree_warranty_quality_screen/00_2005_six_year_warranty_quality_screen.md)。 | 不用奖项、承诺、总收入、毛利、后来集中度、价格或回报，替代质量和服务经济性。 |
| `VD-13` | 2005 厨卫电器：华帝在低端价格战、原料涨价下，实施中高端产品结构调整，并继续建设环保烟机、节能热能项目。 | 产品结构与配套制造是否先改善核心产品的量价/成本，继而能否覆盖渠道、营运资本与资本支出？ | `RESULT_KNOWN_TEACHING / CLOSED / MIXED_OPERATING_OUTCOME` | 2006 三项主要产品毛利率均改善，支持产品经济 package 的早期箭头；但渠道、采购、自制同样变化，净利下降、OCF部分由应付增加支撑且募投现金流出，故不裁决产品归因或最优资本配置。见 [R-28 结果复盘](experiments/R-28_vatti_2005_product_mix_teaching/02_2006_outcome_resolution.md)。 | 不把高端份额的不同分母、总收入、公司归因、项目投产、OCF单值或后来品牌写成产品决策已经验证。 |
| `SP-14` | 2005 炊具/厨房小家电：苏泊尔在产品毛利承压时，推行产品差异化、扩品类和多基地制造；新品与厨卫产品已在年内推出。 | 产品差异化何时要连同价格、制造规模和渠道成本来判断，何时才能穿过现金与资本回收？ | `RESULT_KNOWN_TEACHING / CLOSED / BOUNDARY_REPLICATION` | 2006 炊具、电器及四个核心产品毛利率均提高，但同时有部分提价、高端结构、产能释放与成本下降；OCF含应付增加且持续资本开支材料性。见 [R-29 结果复盘](experiments/R-29_supor_2005_product_economics_boundary/02_2006_outcome_resolution.md)。 | 不把多项并发的产品、价格、规模和营运资本作用压缩为“创新成功”，也不把公司总 OCF/项目进度当作产品的 owner cash 或项目回报。 |
| `HE-15` | 2011 家电渠道服务：海尔电器收购日日顺售后服务网络，并把它列为渠道综合服务核心网络。 | 售后网络何时既降低产品保修/服务责任，又使客户或第三方选择服务，进而形成独立服务经济？ | `SOURCE_SCREEN / MEASUREMENT_MISMATCH / CLOSED` | 2012 有服务商、外部厂商、保修准备、费用方向与服务收入，但共同控制下重述使 before/after 失真，服务/电商/产品保修边界又不一致。见 [R-30 筛查](experiments/R-30_haier_2011_service_platform_screen/00_2011_service_platform_quality_screen.md)。 | 不把服务网点、奖项、线上评分、总服务收入、准备金或集团费用率写成质量、客户选择、owner cash或收购资本回报。 |
| `RQ-16` | 1984–1992 冰箱：青岛的技术吸收、雪花的停线技改/维修投入与万宝的质量整顿，均发生在产能扩张、卖方市场逐步转向买方市场的阶段。 | 质量、服务与技术吸收何时是可持续经营能力的一部分，何时仍不足以替代产品状态、客户选择与现金转换的判断？ | `RESULT_KNOWN_TEACHING / STATE_REPERTOIRE / NO_TURTLE_BACKTEST` | 三组一手报道只构成不同管理选择切片；雪花后续产品重置只显示质量/服务并非充分条件，不能归因裁决。见 [R-37](experiments/R-37_early_refrigerator_quality_state/00_1984_1992_refrigerator_quality_state_screen.md)。 | 不用“只剩少数龙头”、后来品牌、媒体赞誉、总产值、短期销售、股价或企业存续解释 1980 年代的管理选择。 |
| `QT-20` | 1984–1991 冰箱：青岛、上菱、扬子均引进先进线并报告质量/效益改善，万宝亦在质量危机后整顿。 | 技术引进与质量纪律是某家企业的可选择优势，还是 S2 广泛可得的共同条件？ | `RESULT_KNOWN_TEACHING / S2_COMMON_CONDITION / NO_COMPANY_VERDICT` | 同期来源足以拒绝幸存者倒推，却没有同定义客户选择、服务成本、渠道回款或 S3 现金链。见 [R-47](experiments/R-47_early_refrigerator_quality_common_condition/00_1984_1991_quality_import_common_condition_screen.md)。下一案只筛 S3 的非共同分叉。 | 不把技术来源、质量口号、不可比返修/利润、后来存续、股价或回报当成早期企业家判断的证据。 |
| `SV-21` | 1990–1993 耐用品：消费者投诉显示维修/备件/责任缺口；14 城调查显示服务会改变购买选择。 | 服务如何从客户选择变成可吸收的履约、价格和现金经济，何时只是共同需求？ | `RESULT_KNOWN_TEACHING / S3_CUSTOMER_CHOICE_STATE / NO_COMPANY_VERDICT` | 市场状态已确认；缺单一企业的履约、服务成本/保修、渠道责任与现金。见 [R-48](experiments/R-48_appliance_service_customer_choice_state/00_1990_1993_service_customer_choice_state.md)。只筛成对结果合同。 | 不以满意度、热线、网点、奖项、品牌、后来存续、股价或回报替代服务经济。 |
| `AS-17` | 1987–1993 冰箱：九家企业引进相近阿里斯顿平台后，穿越同一轮供给过剩，1993 年的资本效率和周转出现巨大分化。 | 同一技术平台何时被转译为本地客户选择、周转与核心再投资，何时只是一项共同投入？ | `RESULT_KNOWN_TEACHING / COHORT_LEVEL_MECHANISM / NO_INDIVIDUAL_VERDICT` | 1994 综合报道能确认共同平台不足与高度分化，却未给全体命名单位的行动、同口径经营和现金链；只保留为选案状态，不升级为 company pair。见 [R-40](experiments/R-40_ariston_refrigerator_cohort/00_1987_1993_common_platform_divergence_teaching.md)。 | 不把报纸的事后归因、未点名的失败对象、后来的集中度或企业存续改写为某家公司或某种技术策略的因果结论。 |
| `ML-18` | 1989 冰箱需求转冷、库存出现：合肥冰箱厂将家庭储存需求转译为更大冷冻室的 181 型产品。 | 行业“冷”何时其实是主力产品未匹配客户使用约束，何时只是需求/渠道波动？ | `RESULT_KNOWN_TEACHING / PARTIAL_MECHANISM_SUPPORT / NO_CASH_VERDICT` | 同期报道存在具体规格、工程师检测和多地早期接受，但无同规格竞争对照、量价、服务成本与现金链。见 [R-41](experiments/R-41_meiling_1989_large_freezer/00_1989_customer_problem_product_response_teaching.md)。 | 不把早期热销、集团产量/利税、后来的品牌位置或“用户需求”口号升级为长期产品能力、资本回报或企业家总评价。 |
| `XF-19` | 1998 冰箱：新飞为农村客户推出功能简化、价格更低且适应宽温度/电压/湿度的经济型冰箱。 | 细分产品适配何时在放弃功能和降低价格后仍可形成可吸收的经济性，何时只是与采购/总体成本改善并发？ | `RESULT_KNOWN_TEACHING / MIXED_OPERATING_OUTCOME / NO_PRODUCT_RETURN` | 产品销量占比与集团利税可读，但同源也披露原料成本下降，缺产品级量价、成本、渠道与现金。见 [R-42](experiments/R-42_xinfei_1998_rural_economy_refrigerator/00_1998_rural_product_cost_teaching.md)。 | 不把细分采用、总利税、供应链口号、后来品牌地位、股价或回报写成该产品创造的单位经济或资本回报。 |

## 3. 第一轮研究顺序

1. `MW-01`：作为价格—成本—现金机制的 focal discovery；
2. `AC-02`：只作改变渠道权利结构的 boundary，对照“谁在降价、谁承担成本”；
3. `JV-01`：承接 R-15 的“权利不等于经济控制”教训，完成资本权利/技术吸收域的受限复盘；
4. `HI-02` 与 `MD-03`：组织整合与分权分别只保留可审计的缺口；不以海尔或美的公司史延长研究；
5. `HK-04`：危机收购教学复盘已结束，并把收入/净利分解、营运资本与两期持续性带入下一家；不再增加科龙材料；
6. `TCL-05`：在不同公司、不同技术范式中实际应用 R-19 的四项字段，并新增“经营控制完成度”；不把中国白电的结论外推到彩电全球化；
7. `CH-06`：在渠道信用状态应用上述字段，新增 `credit_governance_visibility`；
8. `KK-07`：作为不同集中度与已投保状态的边界复验，新增 `risk_transfer_vs_liquidity`，避免把保险/低集中度误训练为现金成功；
9. `HS-08`：在相邻中国消费电子 arena 验证“流程完备”仍不足以证明回款，新增 `counterparty_chain_identity → contractual_control → realized_collection → independent_verification → cash_conversion`；
10. `HX-09`：提供收入仍增、库存周转而非应付融资使 OCF恢复的正向经营边界；新增现金来源分解，避免把客户信用与库存释放混为一谈；
11. `MD-10`：进入产能/纵向一体化域，把产能吸收、部件单位经济、营运资本现金与资本回报分开；它的混合结果禁止被压成“规模成功”；
12. `JY-11`：保留为产品采用候选，但仅有后验招股书，严格停在 `NO_PRIMARY`；不把数据丰富误当作可训练；
13. `GR-12`：只用作质量/服务的压力测试，建立故障—服务成本—客户选择的结果合同；不再扩读格力叙事；
14. `VD-13`：用不同公司把产品结构、单位毛利、渠道费用、营运资本与资本支出分开；新增 `gross_margin_bridge`，不把产品收入或高端叙事当 owner cash；
15. `ML-01`：用主体边界作为硬门重新筛选多元化，不把上市公司与子公司拼成结果；
16. 只有其中任一项取得冻结前可定位的结果合同，才创建完整企业经营判断卡；否则保持上述层级并继续换 arena。
17. `RQ-16` 只把早期冰箱材料沉淀为“质量/服务/技术吸收必须连接产品状态与现金”的状态语言；下一张案例必须有同产品的可靠性、客户选择、服务成本和现金中的至少一条可结算链，不能为补全幸存者故事而扩读。

这条顺序故意不从海尔、美的、格力的完整公司史开始：目标是连续训练不同类型的决策，而非把研究时间投入最著名或材料最多的名字。
