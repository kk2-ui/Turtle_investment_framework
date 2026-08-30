# Course 2B 两臂冻结执行记录

> 状态：`TWO_FRESH_CODEX_ARMS_FROZEN / OUTCOME_MAY_OPEN`

## 运行身份

- Baseline：`/root/course2b_baseline`，`fork_turns=none`，一次正式 `run --agent-response` 成功；Episode ID=`UWEP:CN000672:20180430:COURSE2B:BASELINE:V1`。
- Enhanced：`/root/course2b_enhanced`，`fork_turns=none`，一次正式 `run --agent-response` 成功；Episode ID=`UWE:CN000672:20180430:COURSE2B:ENHANCED:V1`。
- 两臂继承同一 Codex 模型与 reasoning 配置；未使用模型覆盖、API key、外部 provider、`codex exec`、网页搜索或 provider replay。
- 两个 Agent 均只收到各自 task packet、共同 Episode schema/validator 和具名响应/输出路径；不得读取父会话、另一臂、Pack 原文、Course 1/AB3 公司结论或结果期资料。

## 冻结产物

- Baseline：`arms/baseline/enterprise_underwriting_episode.json`、`enterprise_underwriting_downstream_bundle.json`、`investor_readout.md`。
- Enhanced：`arms/enhanced/enterprise_underwriting_episode.json`、`enterprise_underwriting_downstream_bundle.json`、`investor_readout.md`。
- 两份 Episode 在正式持久化后又分别通过 `validate-episode`，结果均为 `REVIEWABLE`、findings 为空。
- 两份投资者读本只由冻结 Episode 经 `render_underwriting_readout` 确定性生成，没有第二个 writer 或新增判断。

从本记录形成起，两臂产物不得再修改。Custodian 现在可以按 `03_OUTCOME_CUSTODY_AND_SEAL.md` 开封 FY2018--FY2020 行业与公司结果；两层结果必须分开结算，且不得把上峰单家公司结果用作行业主张的结算依据。
