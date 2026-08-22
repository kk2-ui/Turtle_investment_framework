# R-03 外部档案候选复筛（2026-08-21）

状态：`PRE_OUTCOME_ONLY / NO_ADMISSION / NO_OUTCOME_OPENED`

目的：复验 R-03 的 fail-fast 规则：外部档案不是因为知名、争论激烈或有许多幻灯片就可作为公司经验；它在**打开任何后续经营结果前**，必须已写出可由同一公司官方披露重建的经营谓词、指标、窗口和允许替代项。本筛查不形成任何公司、价格、回报或 Turtle 判断能力结论。

## 已读范围与防火墙

只读下列当时的 SEC 原件；没有打开其后的 10-Q、10-K、业绩公告、价格或回报材料，也没有下载 outcome package。

| 候选 | cutoff 前原件 | 读到的机制材料 | 准入裁决 |
|---|---|---|---|
| P&G / Trian，2017-07-17 | [Trian 的 DFAN14A](https://www.sec.gov/Archives/edgar/data/80424/000090266417002944/p17-1517dfan14a.htm) | Trian 将市占流失、组织官僚和成本项目无效连接到销售、利润与董事会改革。 | `NO_ADMISSION`：材料给出的是方向性目标（提高销售/利润、夺回份额），没有指标定义、数值/范围、观察窗与官方结果映射；不能从“未来是否改善”倒推一个谓词。 |
| Darden / Starboard，2014-08 至 2014-09 | [Starboard 2014-08-05 DFAN14A](https://www.sec.gov/Archives/edgar/data/940944/000092189514001678/dfan14a06297125_08052014.htm)；[Darden 2014-09-09 DEFA14A/8-K](https://www.sec.gov/Archives/edgar/data/940944/000119312514343132/d786527ddefa14a.htm) | 双方对 Olive Garden turnaround、运营改进、现金流与公司治理提出竞争性叙述。 | `NO_ADMISSION`：双方均有行动与归因语言，但没有同一、预先承诺的经营指标和时间窗口；“品牌复兴/更快增长/更好现金流”不能由后来同店销售、EBITDA 或现金流任择替代。 |
| ADP / Pershing Square，2017-09 至 2017-10 | [ADP 2017-10-23 DEFA14A](https://www.sec.gov/Archives/edgar/data/8670/000095014217001881/eh1701067_defa14a.htm)；[Pershing Square 2017-09-25 DFAN14A](https://www.sec.gov/Archives/edgar/data/8670/000119312517293160/d461073ddfan14a.htm)；[ADP FY2017 10-K](https://www.sec.gov/Archives/edgar/data/8670/000000867017000010/q4fy1710k.htm) | ADP 说其管理计划到 FY2020 增加 `500bp` net operational margin；Pershing 的相反解释是计划的实际含义仅约 `300bp`，因为大部分“改善”不是公司可控经营效率。 | `NO_ADMISSION`：这次虽有同一指标、基准与 FY2020 窗口，但 `net operational margin` / `adjusted EBIT` 不在 cutoff 前的 FY2017 10-K 中作为连续官方结果指标出现；管理层材料中的 reconciliation 不能证明 FY2020 会有可重建的同口径官方 endpoint。未读任何 FY2020 结果。 |

## 为什么拒绝

三例都具有丰富的争论和一手来源，但缺少 R-03 所需的 `author predicate → recurring official metric channel → window → prohibited substitutes`。P&G 与 Darden 缺明确谓词；ADP/Pershing 已有一个貌似完整的 500bp/300bp 分歧，却不能证明该非 GAAP campaign metric 会在未来同类官方结果中连续出现。将这些主张事后映射为任一以后披露的销售、利润、现金、GAAP operating margin、adjusted EBIT 或股东回报，都会改变原主张的可证伪含义。

- 根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。缺失的不是报告数量，而是当时可重建的指标—窗口承诺和其**重复官方结果通道**。
- 经济影响：若放行，会把成功或失败的行动、董事会变化、单期利润或证券结果错误归为组织、渠道或运营机制成立；尤其会把管理层 campaign metric 与后来不同定义的 GAAP/adjusted 指标拼接，污染正常盈利、现金转换和资本配置的外部结构经验。
- 禁止假设：不得把名气、proxy contest 胜负、管理层/激进股东的广义愿景、一次性 investor deck 的 reconciliation、后续公司 KPI、股价或回报补成预测；不得因后来材料较容易找到而反向选择案例。
- 可执行补救：仅在 cutoff 前另有同一主体的常规官方披露，明确证明该指标（或完整 GAAP 重建）会按同一文件类型/节奏连续出现，并给出比较对象、窗口、调整项及禁止替代时，才可重开。否则保持 `TEACHING_ONLY / NO_ADMISSION`。
- 接纳条件：在读取 outcome 前，独立审阅者能仅凭既有重复披露和预期 outcome source 复写原谓词，不需要解释者选择相近 KPI；做不到即停止。

## 方法裁决

`RETAIN_FAIL_FAST_METRIC_GATE`。R-03 的杜邦试转曾因核心经营利润桥无法连续重建而在结果期关闭；这次筛查将同一规则前移到 P&G 与 Darden 的两组不同公司、不同年份的同期原件，避免了不必要的结果读取。它只证明流程能再次拒绝没有可结算谓词的材料；不证明这些公司、任何一方机制或外部档案方法本身正确。

这一处理与过程追踪需要诊断性、时间定位证据而非事后故事的要求一致（[Collier, 2011](https://doi.org/10.1017/S1049096511001429)），也与 outcome bias 防护一致（[Baron & Hershey, 1988](https://doi.org/10.1037/0022-3514.54.4.569)）。两篇研究提供方法边界，不对上述公司给出经营结论。
