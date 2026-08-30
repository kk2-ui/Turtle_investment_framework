# 中国中免独立 A/B：候选与材料机制合同

> 状态：`PREOUTCOME_CONTRACT_DRAFT / OUTCOME_SEALED`
>
> 公司 / cutoff：`CN:601888 / 2019-05-01T00:00:00+08:00`
>
> 权限：`RESEARCH_TRAINING_ONLY / NO_CJO_VALUATION_BUYBAND_REPORT_OR_INVESTMENT_AUTHORITY`

## 选择理由

中国中免被选择为下一条独立机制测试，因为它与水泥、设备制造、汽车、封测和生猪养殖的
资本责任不同：利润主要来自受许可和期限约束的机场／离岛免税渠道，同时承受商品库存、
机场租金、供应商议价、收购并表和少数股东索取权。该候选用于检验 Agent 是否会把高毛利、
渠道经营权和收购协同直接资本化，还是会沿“合同／期限 → 客流和消费者吸收 → 存货与租金
责任 → 普通股现金和永久损失”的链条承保。

候选选择只依据 cutoff 前资料可得性、责任边界和与既有课程的异质性；没有读取 2019-05-01
之后的年报、结果、价格、回报、分析师观点或本次 A/B 结果。目标公司的所有事实只来自同一份
中性事实包。该文档本身不是目标公司证据，不能进入两臂 `evidence_trace`。

## 预注册材料性分叉

Baseline 最可能的风险是把 FY2018 免税商品 53.09% 毛利率、机场经营权、日上上海并表和三亚
客流增长合并成可持续的高正常盈利；另一个方向性错误是看到机场租金、存货和投资现金流出后，
把整个免税底盘降格为不可承保。Enhanced 唯一允许使用的条件化方法是：

1. 先分开有期限／可续约的渠道经营权、既有离岛店和收购新增渠道，不把经营权本身当作永久
   特许权；
2. 把消费者吸收（客流、购物人数、同店／渠道销售）与商品采购毛利分开；
3. 把机场租金、季节性备货、在建项目和收购现金按同一责任边界写入普通股现金与永久损失；
4. 在证据不足时给出“成熟渠道底盘 + 条件性扩张”的正常化方向，而不是直接永久化峰值或
   因项目责任未知而否定成熟底盘。

只有当 Enhanced 以中国中免 cutoff 前事实为依据，在相同盈利指标下材料性改变以下至少一项，
才可成为结果后检验候选：成熟渠道／收购渠道是否进入基准正常盈利、owner-cash 责任范围、
永久损失路径或价值路线。新增字段、更多 caveat、更长文字、更高／更低信心或不同指标口径
均为 `NO_MATERIAL_UTILITY`；把经营权当永久特许权、把 FY2018 峰值直接年金化、或用 OCF
减资本开支冒充 owner cash 则为 `ENHANCED_WORSE`。

## 隔离合同

- 两臂使用同一 `2018 年年度报告` 中性事实包、同一 cutoff、同一模型、同一完整
  `EnterpriseUnderwritingEpisode` 产品和相近 token 预算。
- Baseline 不接收本合同、Enhanced treatment、任何历史经验、对方草稿或 cutoff 后资料；
  它只接收自己的 JSON 合同和中性事实包。
- Enhanced 的唯一增量输入是 `01_CHANNEL_CONTRACT_AND_CASH_RESPONSIBILITY_TREATMENT.md`，
  其角色为 `TRAINING_MEMORY`。它不含中国中免事实、结果或数值结论，也不得进入目标公司的
  `evidence_trace` 或 `existing_object_refs`。
- 结果前审阅先冻结配对是否有效和材料性差异，再由独立 custodian 读取预先指定的官方结果
  报告；结果不得回流修复 Episode 或事后给 Enhanced 加分。

## 预注册结算

| 结果前状态 | 结算 |
| --- | --- |
| 共享输入或两臂证据／预算不可比 | `PAIRED_TEST_INVALID`，根因 `MODEL` 或 `ACQUISITION_MODULE` |
| 两臂均把成熟渠道与条件扩张分开，投资处理相同 | `NO_MATERIAL_UTILITY`，不是失败也不是成功 |
| Enhanced 预支期限经营权、峰值毛利或忽略租金／存货／资本责任 | `ENHANCED_WORSE`，根因 `REASONING` |
| Enhanced 独有地纠正 Baseline 的永久化或过度否定，并改变同口径正常化／现金／价值路线 | `MATERIAL_PREOUTCOME_IMPROVEMENT_CANDIDATE`，仅允许进入结果后局部结算 |

本轮不授予 `METHOD_VALIDATED`、`TRANSFER_VALIDATED`、CJO、正式估值、BuyBand、黄金报告或
投资权限。再次 `NO_MATERIAL_UTILITY` 时停止扩展这一类 memory，不增加 gate、schema、receipt
或比较面板。

## 结果前勘误

本合同草案初版头部曾把 FY2018 年报公告日 `2019-04-27` 误写为 cutoff。正式 JSON 合同、两臂
Episode 与运行绑定均使用 `2019-05-01T00:00:00+08:00`，源包 `available_at` 为
`2019-04-27T23:59:59+08:00`。本勘误只统一已有来源可用时点，不改变候选、事实包、材料性分叉
或任何 Episode 经济结论。
