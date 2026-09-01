# 顺丰控股结果前配对测试

> 状态：`FROZEN_BEFORE_OUTCOME`

## 问题

十二个 Worked Case 形成的参照系，能否在一家具备不同网络责任边界的未见公司上，
材料性改善完整企业判断，而不只是增加问题、文字或谨慎程度。

## 公平条件

两个 arm 均使用：

- 公司：`CN:002352` 顺丰控股；
- cutoff：`2019-05-01T00:00:00+08:00`；
- 唯一公司材料：`sources/CN002352_20190501_PRE_CUTOFF_SOURCE_PACKAGE.md`；
- 相同的 `CN002352_BLIND_CONTRACT.json`、Episode schema 和一轮完整企业判断预算；
- 结果封存，禁止市场价格、回报及 FY2019 以后事实。

唯一处理差异：

- `Baseline` 只使用 AGENTS 判断优先宪法、合同、schema 与顺丰源包，不读取本课程的
  Worked Case、课程读出、经验记忆或其他公司材料；
- `Training-Enhanced` 额外读取 `03_WORKED_CASE_COURSE_READOUT.md`，只能把其中经验用于
  问题、证据顺序、参考类别、反方与处理边界，不能复制旧公司的企业结论。

两个 arm 由相互隔离的 fresh Agent 独立生成。Baseline 不得事后补看 Enhanced，Enhanced
也不得读取 Baseline。配对结果在两份 Episode 都验证并提交冻结后才可比较，结果窗口在
配对比较冻结后才可打开。

## 材料性标准

只有以下至少一项因训练参照系发生有理由的改变，才是结果前 `TRANSFER_CANDIDATE`：

- 行业利润池或顺丰在其中的责任位置；
- 核心时效网与新业务的正常盈利处理；
- 直营网维护/增长资本、债务和 owner cash 的经济范围；
- 服务优势失效或低回报扩张造成的永久损失路径；
- EPV、分部、资产或压力路线的主次；
- 最早、最能区分竞争解释的结果观察。

文字更多、列项更多、UNKNOWN 更多、简单复制“客户到现金”口号，或只把所有结论写得
更保守，均不算增量。结果前比较只能建立迁移候选；结果揭示后的事实才决定该变化是帮助、
无效还是误导，不得标记 `TRANSFER_VALIDATED` 或 `METHOD_VALIDATED`。
