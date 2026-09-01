# CN600161 strict paired holdout V2 — pre-outcome pairing review

**Verdict: RETURN — pair not evaluable.**

独立审阅只读取配对包、两臂结果前判断与执行回执、Enhanced 的冻结方法包及共同的 FY2021–FY2023 官方年报；未读取 FY2024、价格、回报或 settlement。两臂使用同一公司、cutoff、资料预算和 sealed outcome；仅 Enhanced 收到 Method Pack，且均为 one-shot、无跨臂复核。Baseline 不是空壳或稻草人，但当前不能进行公平的 method-only 评价。

## 材料性阻塞

### 1. Baseline 将无关的母公司现金条件带入经营结算

`FY2024_RECURRING_OPERATING_CONVERSION` 与 `FY2024_CAPACITY_PRODUCT_AND_QUALITY_SETTLEMENT` 要求 NCI scope CLOSED、parent access EVIDENCED，尽管其 direct axes 是经营/管理/正常盈利；集团现金 cell 也重复要求该条件，另有独立 upstream-access cell。这样，经营利润、产品吸收或质量已被观察时，只因母公司上划未披露就可能整项 UNKNOWN。

根因：`REASONING + DATA_COVERAGE`。经济影响是把局部现金边界缺口误写成经营未知，延迟或吞掉正常盈利、管理执行和质量判断。缺失事实不是更多年报，而是每个 cell 对自身责任边界的明确 required inputs。禁止假设：parent distributions 是产品吸收的前置；open NCI/access 等于经营恶化；group cash 等于 parent cash。

最小修复（仅供未来新 pair，不回写本 arm）：经营与产能/质量 cell 删除 NCI/parent-access 前置；集团 cash cell 只消费集团现金输入；NCI/parent access 由独立 cell 结算。验收：经营或质量完整观察在 parent access UNKNOWN 时仍能结算，owner cash 仍必须等待专属 upstream-access 证据。

### 2. Baseline 把商业化与质量监管绑在一个 cell

`FY2024_CAPACITY_PRODUCT_AND_QUALITY_SETTLEMENT` 将新增产能/产品商业化与 GMP、批签发、召回、许可等质量轴合并。商业化成功但出现孤立质量缺陷，或质量正常但利用率延迟时，first-match 无法保留两个轴的不同处理，可能同时下调管理层并收紧永久损失。

根因：`REASONING`。经济影响是把一个责任单元的正面吸收擦除，或把局部质量事件错误传播到全公司资本回报。缺失事实：项目利用率/商业批次与质量事件必须分开定位并带责任边界及经济损失。禁止假设：孤立质量问题否定产品执行；项目完成证明利用率或回报；正常批签发证明无永久损失。

最小修复：拆为 capacity/product absorption 与 quality/regulatory integrity 两个 cell；如保留交互，使用保留各轴局部处理的二维矩阵。验收：混合组合可分别更新管理层、正常盈利和永久损失；只有材料、责任匹配的质量损失才收紧永久损失。

### 3. 两臂正常盈利口径不具母公司可比性

Baseline 以未做税和 NCI 桥的合并税前“经常经营利润”约 17.01 亿元作 normal-earnings/valuation 锚，Enhanced 使用扣非归母净利润约 11.04 亿元。核心子公司存在约 25.995% NCI，二者不是同一上市股东经济口径；即使 treatment code 都是 `RAISE`，其可结算对象不同。

根因：`REASONING + DATA_COVERAGE`。经济影响是把合并利润误资本化为母公司股东盈利，可能高估正常盈利与估值方向。缺失事实：同一责任边界的合并经营利润→税→NCI→归母经常盈利桥，或明确把企业税前价值与母公司价值分开。禁止假设：NCI 不重大；合并税前利润等于归母 owner earnings；parent cash access 可替代 earnings perimeter。

最小修复：未来 pair 先冻结共同 normal-earnings perimeter，保留 enterprise operating profit、attributable normal earnings、owner cash 三个轴；valuation 只能消费声明过的口径。验收：两臂 outcome cells 结算同一经济量，未经税/NCI/边界桥不得触发母公司估值更新。

## 处置

本 pair 保持 sealed、不可返修、不可进入 FY2024 outcome access；不修改任一 forecaster。CN600161 的单臂结果后材料（如有）只能作为历史企业反馈，不得把本 pair 标作公平 Holdout 或方法效用证据。后续应先完成新的结果隔离 Blind，再按上述边界设计下一 pair。

