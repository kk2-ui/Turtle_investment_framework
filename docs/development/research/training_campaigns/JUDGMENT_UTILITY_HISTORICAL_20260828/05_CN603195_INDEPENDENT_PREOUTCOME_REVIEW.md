# CN603195 前置结果最终复验

## 最终裁决

**ACCEPT**

本裁决取代上一轮 `RETURN`。本次仅复验修订后的 `PREOUTCOME_JUDGMENT.json`，未读取 FY2024、价格、回报、父工作区或其他材料。

## 材料性结论

上一轮 `REASONING` 阻断项已完成最小且有效的修复：

- 三个 cell 都在数值分类之前设置 `LOCAL_UNKNOWN / COMPARABILITY_MISMATCH` 等输入门；数值 `ELSE` 被明确限制为完整、有效、同口径输入的补集，未披露或不匹配不再被当成恶化。
- 核心 cell 不再用集团扣非归母利润决定核心分类；该指标只作交叉验证，冲突时进入利润桥研究，不反判核心侵蚀。
- 核心、现金与新能源 cell 均明确了传播上限。JSON 中出现的前置 `RAISE / UP / COUNT_IN_PARENT_OWNER_CASH` 是沿用既有基线，不表示该 cell 新增跨轴信用。
- `OCF－全部长期资产购置` 已正确更名为合并口径的保守现金下限；总 capex 不再被假定为维持性 capex，已识别扩产导致的负下限可进入 `EXPANSION_FUNDED_CASH`，不会自动判弱。
- parent owner cash 只在 NCI 不重大时近似计入；NCI 重大而现金归属桥缺失时进入 `PARENT_ATTRIBUTION_UNKNOWN` 并仅 `COUNT_CONDITIONALLY`。
- 即时流动性只计不受限现金及已核实能在短债到期前回款的资产；封闭式信托、资管和其他不可立即动用的交易性金融资产不再自动计入。
- 新能源的收入、毛利及产销规模只更新项目级执行和增长期权；复购、营业利润、现金投入及售后未闭合前，仍 `EXCLUDE_COMPONENT / DO_NOT_COUNT`，不进入企业正常盈利或 parent owner cash。

## 十项反例机械重放

| # | 重放结果 | 裁定 |
|---|---|---|
| 1 | FY2023 核心比较数无法同口径重述时，先命中 `COMPARABILITY_MISMATCH`，不进入 `CORE_EROSION`。 | PASS |
| 2 | 新能源收入、毛利可比而产销量缺失或单位变化时，命中 `INCOMPLETE_SCALE_PROOF`，不判价值破坏。 | PASS |
| 3 | 必需分母为零、无效或未披露时，仅受影响 cell 进入局部门；新能源附加产销分母无效进入 `INCOMPLETE_SCALE_PROOF`，经济处理同样局部且非负面。 | PASS |
| 4 | 核心达到强档而集团扣非因已归因的新业务投入偏弱时，保持 `CORE_COMPOUNDING` 并标记企业交叉验证 mismatch，不反判核心。 | PASS |
| 5 | 现金强档不新增正常盈利判断，核心强档不新增 owner cash 判断；相同状态码明确是沿用前置处理。 | PASS |
| 6 | 新能源收入 +60%、毛利 31%、产销差 5 个百分点且复购/利润/现金未知时，进入 `QUALITY_SCALE_OPTION_RETAINED`，仅加强项目期权。 | PASS |
| 7 | OCF 转换健康、即时流动性覆盖短债、负现金下限由已识别扩产 capex 解释时，进入 `EXPANSION_FUNDED_CASH`，owner cash 仅条件计入且不下修正常盈利。 | PASS |
| 8 | NCI 重大且缺少归属现金桥时，进入 `PARENT_ATTRIBUTION_UNKNOWN`，不得全额计入 parent owner cash。 | PASS |
| 9 | 只有封闭式理财使广义金融资产为正而即时资金不能覆盖短债时，不能进入 durable/流动性放松类；封闭式资产不进入即时流动性公式。 | PASS |
| 10 | 对完整、有效、同口径输入，三组数值规则按 `>= / >` 和 first-match 顺序得到唯一结果，受限 `ELSE` 穷尽数值补集；UNKNOWN/mismatch 永不进入该补集。 | PASS |

## 责任边界复验

- **Management execution：** 核心 cell 可更新核心执行；新能源信用明确为项目级；现金 cell 不借现金结果新增管理信用。
- **Normal earnings：** 核心收入与毛利负责核心正常盈利方向；现金转换不改变盈利金额；新能源在利润和现金闭合前排除组件。
- **Owner cash：** 由保守现金下限、NCI 归属和 capex 解释负责；核心与新能源规模结果不自动更新 parent owner cash。
- **Permanent loss：** 核心侵蚀可收紧经营性约束；现金 cell 只按经核实的即时流动性和现金事实更新；项目级新能源结果需另过 parent materiality 门才可传播。
- **Valuation direction：** 核心盈利可影响方向；现金和新能源 cell 中的 `UP/UNCHANGED` 已明确为沿用前置基线，不构成无依据的新上调。

修订后的决策器已达到材料性验收标准。没有剩余问题足以改变当前投资结论、永久损失判断、正常盈利或 owner cash 归属，故予以 **ACCEPT**。
