# R-05 候选来源观察卡：Starbucks FY2026 Q3 与 Investor Day

## 来源身份

- 标题、作者/机构：Starbucks Corporation，*Starbucks Reports Q3 Fiscal Year 2026 Results*（2026-07-29）；*Starbucks Is Back: Turning Momentum Into Long-Term Sustainable Growth*（2026-01-29）。
- 发布/可得时点、版本：两篇均为 Starbucks Investor Relations 页面；筛选读取于 `2026-08-21`。链接：
  - <https://investor.starbucks.com/news/financial-releases/news-details/2026/Starbucks-Reports-Q3-Fiscal-Year-2026-Results/default.aspx>
  - <https://investor.starbucks.com/news/financial-releases/news-details/2026/Starbucks-Is-Back-Turning-Momentum-Into-Long-Term-Sustainable-Growth/default.aspx>
- 原始来源还是转述：公司一手披露。
- `lineage_id`：`SBUX:IR:FY2026_Q3_RELEASE` 与 `SBUX:IR:INVESTOR_DAY_20260129`；二者均来自公司，不能视作独立因果证据。
- 最原始可追溯来源、release/query/访谈样本或事件链：公司 Investor Relations 业绩公告与 Investor Day 公告。
- 与既有观察是否独立；若是，独立性依据：业绩公告的数值披露与 Investor Day 的管理层归因分开记录；后者不独立验证前者。
- 覆盖对象、交易点、单位、期间、渠道/样本边界：北美分部，FY2026 Q3（截至 2026-06-28）；同店指标只覆盖开业至少 13 个月的公司经营 Starbucks 门店，排除汇率及 Siren Retail，按公告脚注定义。
- 证据上限：当前为 `SETTLEMENT_ELIGIBLE`。截止日前源包已冻结在 `output/research/experiments/r05_starbucks_prospective_20260821/source_manifest.package.json`：两篇原始 HTML 与各自页标记阅读本均已物化。冻结前 PIT runner 已显式读取 `IR:SBUX.US:INVESTOR_DAY_20260129` 与 `IR:SBUX.US:FY2026Q3_RESULTS`；`pit_source_package_attestation.json` 记录 `read_count=2`、两个 `ALLOW`、零越界读取和零拒绝。通用边界见[官方 IR 网页来源契约](../../../OFFICIAL_WEB_RELEASE_SOURCE_CONTRACT.md)。
- 证据上限的原因及升级条件：当前事实可进入正式 FJ 冻结；未来结果仍须以同一 `OFFICIAL_WEB_RELEASE` 来源契约在观察窗口内另行获取。不得把新闻转述、网页当前重写版或其他域名页面替代结果源。

## 原文观察

- 可复读事实（FY2026 Q3）：北美同店销售同比 `+8.1%`，由同店交易量 `+4.5%` 与平均客单 `+3.5%` 构成；北美门店数 `18,371`，同比 `-2%`；北美收入 `+7%` 至约 `$7.4bn`；北美经营利润率 `13.6%`，同比 `+30bp`。
- 可复读事实（定义边界）：同店指标只计开业至少 13 个月的公司经营门店；汇率和 Siren Retail 排除；临时关闭不足三周或缩短营业时间的门店仍保留，永久关闭门店在关闭次月移除。
- 可复读事实（FY2026 Q3 成本边界）：北美利润率的公司归因包含销售杠杆、Leadership Experience 2025 的同比基数、较低通胀和关税退款；同时受到重组成本、支持 Back to Starbucks 的劳动力投入及产品组合变化的抵消。
- 在机制中的角色：业绩数值和定义为 `STATE / OUTCOME`；利润率归因及 Investor Day 所述服务、吞吐、满意度、奖励计划为 `CAUSAL_ATTRIBUTION / ACTION`。
- 作者或管理层的解释：Investor Day 称 Green Apron Service 已在北美公司经营店全面铺开，并“driving improved service times, higher throughput and stronger customer satisfaction”；奖励计划于 2026-03-10 重设。它们提出可检验路径，不能证明这些路径导致 Q3 交易增长。
- 缺失字段、口径或版本：顾客层级留存、促销强度、竞争者价格、地区经济环境、同店交易的分渠道组成、服务动作的因果归属，以及可由 Turtle 正式冻结的网页/附件包。
- 来源身份：Q3 数值/定义为 `FACT`；服务/奖励与交易的因果关系为 `HYPOTHESIS`；客户留存和外部需求的相对贡献为 `UNKNOWN`。
- 未知原因：`MECHANISM_NONDIAGNOSTIC`；当前一季状态允许多条机制。正式来源包已就绪，但不改变当前事实本身的非诊断性。
- 对竞争机制的诊断性：Q3 数值为 `COMMON`；Investor Day 归因为 `NONDIAGNOSTIC`。

## 研究用途

- 它涉及哪条机制箭头：Q3 的交易量/客单/门店数是双方须解释的共同状态；服务与忠诚计划动作只生成 H-A 的候选传导；利润率成本归因是对单一“经营杠杆已证明”叙事的边界提醒。
- 最强替代解释：交易增长可能来自广泛需求、同比基数、组合或短期商业动作，而非服务模型带来的可持续频次改善；现有材料无法区分。
- 它不能支持的结论：不能证明 Green Apron、奖励计划或任一管理动作导致交易增长；不能证明长期正常盈利、现金、价值、证券价格或投资回报。
- 下一项能提高诊断力的观察或资料请求：在截止日正式冻结同口径 FY2027 Q1/Q3 北美同店交易量的 A-only/B-only 结果区域；结果期以同一通用官方 IR 静态披露取得路径读取。
- 与已读材料的共同来源谱系或冲突：两份材料同属公司来源；不可相互独立加权。Q3 的多重成本因素直接反对把利润率单独当作服务机制的证明。
