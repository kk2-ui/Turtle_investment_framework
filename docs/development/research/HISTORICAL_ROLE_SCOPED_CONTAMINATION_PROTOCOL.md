# 历史训练的角色级污染与盲包协议

> 裁决：`WORKSPACE_PRESENCE_IS_NOT_EXPOSURE / ROLE_ACTUAL_INPUT_GOVERNS`

## 问题

旧筛选把“仓库或本机存在下一期年报、旧报告或 settlement”直接等同于“候选已经污染”。随着训练
积累，本地候选池必然单向缩小，最终只能不断寻找新公司，或者错误地把数据管理问题变成全局准入门。

文件存在与研究者已经读取不是同一事实。真正会破坏结果前判断的是：负责选样或形成判断的具体角色，
在 freeze 前收到同公司、同结果窗口的正文、派生结论、价格或回报。

## 当前裁决

污染按 `role × company × cutoff/outcome window × actual input` 记录：

- 仓库中存在 outcome 文件：不构成污染；
- 只知道下一期官方文件存在：不构成污染；
- 当前主 Agent 已经看过 cutoff 后的 outcome、派生结论、价格或回报：该 Agent 不得再担任该
  episode 的 selector 或 forecaster；
- 新的无会话上下文 Agent 只收到白名单 cutoff 前材料包：可以担任 forecaster；
- outcome custodian 在 freeze 后读取结果：不污染已经冻结的判断；
- selector 或 forecaster 实际收到 post-cutoff/outcome 正文或其派生结论：该角色与该 episode 污染，
  不能靠删除文件或重写较早时间戳恢复。

污染不是“公司永久拉黑”，也不是“整个仓库永久污染”。已经读过结果的角色必须退出结果前职责，
由新的 selector/forecaster 接替。

## 可执行隔离

`scripts/historical_role_isolation.py` 是 selector/forecaster 的最小盲包构建器和输入契约校验器：

1. 只复制 manifest 明列的 cutoff 前官方材料；
2. packet 中不写 outcome URL、路径、数值、派生结论、exposure ledger 或其他角色身份；
3. cutoff 后材料不能混入 source budget；
4. selector、forecaster、custodian、reviewer 必须不同；
5. selector/forecaster 已有 cutoff 后正文、派生内容、价格或回报 exposure 时拒绝生成 packet；
6. 目标目录必须为空，避免旧文件混入。

同公司更早且在当前 cutoff 前已经公开的正文是合法训练输入，不会令公司永久污染。metadata-only 的
下一期文件存在性也不污染。exposure 缺少 role、company、access 或 source availability 时，该 episode
manifest 无效，但不会扩展成全局公司黑名单。

构建器本身不宣称完成角色隔离。实际运行必须由协调器使用无父会话继承的新 Agent，只给 packet
目录和列明文件，并记录真实 Agent 身份、`fork_turns=none`、实际输入目录与输出工件。完成一次真实
one-shot selector/forecaster 之前，只能称 `BLIND_PACKET_READY`，不能称 `ROLE_ISOLATION_PROVED`。
该协议不声称在合作者本机建立敌手级沙箱；它针对的是本项目真实发生的意外上下文继承和宽泛本地搜索。

## 与判断优先的关系

本协议只解决结果隔离，不新增企业判断 gate。盲包通过后，forecaster 仍必须形成当前最合理、可反驳、
对投资有用的判断；局部 `UNKNOWN` 不得终止公司。packet、receipt 或污染状态本身不计训练效用。

训练效用仍只来自结果前材料处理的真实变化，以及相关结果对该变化的支持。更多白名单文件、更干净的
目录或更完整的 exposure ledger 都不产生学习信用。

## 后续历史训练角色顺序

```text
fresh selector（无父会话，只看候选身份、业务原型、cutoff 与前置来源数量）
  -> 冻结 roster 与 source budget
  -> fresh forecaster（无父会话，只收 cutoff 前盲包）
  -> independent pre-outcome reviewer
  -> freeze
  -> outcome-only custodian（只收 measurement contract 与 outcome locator）
  -> post-outcome synthesizer / utility reviewer
```

主协调 Agent 可以知道仓库里有结果文件，也可以在 freeze 后汇总结果；只要它不担任该 episode 的
selector/forecaster，就不影响 fresh forecaster 的结果前判断。
