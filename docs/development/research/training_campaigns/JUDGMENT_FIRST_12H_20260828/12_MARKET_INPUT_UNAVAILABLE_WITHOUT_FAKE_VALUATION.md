# 行情输入不可得，不得制造估值

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`ACTIVE_FAKE_MARKET_INPUT_REMOVED`
>
> 方法状态：`NOT_VALIDATED / NOT_FROZEN`

## 发现的材料性错误

活跃 `compute_bundle --from-db` 路径在行情 provider 不可用时，把当前价固定成 `1.0`。这个数字不是
保守假设，而是伪事实：它同时制造市值、GG、DDM 上行空间和交易动作，可能把一家普通公司写成极度
便宜。JSON 路径则因当前价或股本缺失直接终止，丢弃已经可用的企业经营与现金计算。

同一轮还发现两种相反方向的零值错误：

- 已观察到的 `AA₃y=0` 被 Python truthiness 当成缺失，真实负面 `GG=0` 被撤回成 unresolved；
- 保守现金 GG 已经存在时，只因正常化维护资本系数缺失，代码会覆盖保守 GG 并谎称“三年 AA 不足”。

前者掩盖真实负面，后者抹去已有判断。两者都不是证据纪律，而是计算层的防御性拒绝判断。

## 当前规则

- 当前价缺失：保留 NP、OE、AA 和企业经营判断；撤回市值、GG、DDM、价格动作和仓位。
- 股本或 DPS 缺失：保留绝对经营与现金事实；撤回每股估值和依赖它的动作。
- 当前价恢复：按真实价重新承保市值、GG、DDM 和动作，不继承 unresolved。
- `AA₃y=0` 且三期数据真实存在：结算为 observed `GG=0`，不是 UNKNOWN。
- 正常化资本系数缺失：只不生成 normalized GG；已经结算的保守 GG 保留。
- 利润字段真实为零与字段缺失严格区分；前者结算 0，后者保持局部 unavailable。

## 结果

机械复验得到：

- missing quote：经营计算继续，价格和市值为 `None/UNAVAILABLE`，估值为
  `UNRESOLVED_VALUATION`，不再出现 `price=1.0`；
- provider/人工真实报价：市值和估值正常恢复；
- observed `AA₃y=0`：完整 Factor2→Factor3→Factor4 链为 `RESOLVED / AVOID`，不是资料缺失；
- missing shares/DPS：企业经营和现金继续，局部估值撤回且不崩溃；
- calculation trace 对不可得回报写 `null` 和空步骤，不用数值 0 冒充计算结果。

独立审阅给出 `ACCEPT`，确认缺行情不会制造便宜程度或全局 AVOID，真实零值仍保持负面结算。本地相关
定向回归为 `46 passed`。这只是活跃计算路径纠错，不构成跨公司方法验证，也不授予正式估值、
BuyBand、报告或投资权限。
