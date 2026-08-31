# Course 2C 执行与方法收口

> 状态：`FRESH_CODEX_PAIR_COMPLETED / INDEPENDENT_OUTCOME_REVIEW_COMPLETED`
>
> 最终效用：`ENHANCED_MATERIALLY_BETTER`
>
> 方法处置：`TRANSFER_CANDIDATE`

## 对投资判断真正证明了什么

本轮没有证明 Enhanced 更会预测全国水泥行业主路径。两臂都在截止时形成了同一条有边界的行业判断：有效供给纪律可以阶段性修复利润池，但名义过剩、成本、需求和区域竞争仍会重新传导。结果期对此给出 `MIXED` 结算，独立 Reviewer 因而将行业轴裁为 `NO_MATERIAL_DIFFERENCE`。

本轮证明的是更窄、但会改变投资处理的能力：行业经验派生的方法可以帮助未见公司把持续经营经济、会计并表边界、普通股现金归属、已投产/未投产/终止项目和新增资本责任分开，并将它们分别接入正常盈利、owner cash、融资压力、永久损失和价值路线。祁连山结果期实际出现了这些组件的异向状态，Enhanced 的局部更新能力因此被目标公司证据区分，而不是因篇幅或字段更多胜出。

## 正式执行链

1. Outcome Custodian 先只确认 FY2018—FY2022 为 `PARTIAL_BUT_SETTLEABLE`，没有向两臂或 Reviewer 泄露结果。
2. Baseline 与 Enhanced 均由独立 `fork_turns=none` fresh Codex 在相同模型、reasoning、任务预算和共同源包下各生成一次完整 Episode。
3. 两臂均使用 `run --agent-response` 完成 v2 合同绑定，状态均为 `TRAINING_EPISODE_COMPLETED`；没有使用 `--provider`、API key 或外部模型 API。
4. 执行时发现共享 schema 文件许可写成了旧的 `scripts/enterprise_judgment_episode.py`。协调者在任一 arm 完成前，向两臂同时、等量更正为 `scripts/enterprise_underwriting_episode.py`；这只恢复预注册已允许的共享 schema/validator，不增加事实、训练记忆或结果信息。
5. Custodian 私下封存真实映射并清理匿名 JSON 中的 arm 身份标识。Fresh Reviewer 第一阶段只看共同 cutoff 资料和匿名 Episode/bundle，冻结为 `ARM_A_STRONGER_PRE_OUTCOME`。
6. 第一阶段冻结后，两名隔离 Custodian 分别形成行业路径与公司传导 outcome feedback，均未读取 arm、映射或第一阶段裁决内容。
7. 同一 fresh Reviewer 第二阶段读取 Pack V3、Context、训练记忆、两层 outcome 和 sealed mapping，揭示 `Arm A = Enhanced`、`Arm B = Baseline`，并裁决：
   - `INDUSTRY_PATH_VERDICT: NO_MATERIAL_DIFFERENCE`
   - `COMPANY_TRANSMISSION_VERDICT: ENHANCED_MATERIALLY_BETTER`
   - `OVERALL_UTILITY_VERDICT: ENHANCED_MATERIALLY_BETTER`
   - `METHOD_DISPOSITION: TRANSFER_CANDIDATE`

## 可迁移范围

当前只允许迁移以下方法：

- 重资产区域行业先区分成熟核心、已投产、未投产和终止项目；
- 将会计控制/并表事件与底层持续经营经济、现金归属和新增资本责任分开；
- 每个组件分别绑定正常盈利、owner cash、融资、永久损失和价值用途，并允许局部晋级或撤销；
- 维护资本或项目回报不可测时保留局部 conditional，不把公司整体拒判，也不把责任单元利润升级为项目 ROIC。

不得把单一样本正结果解释为 Pack 已 `RELEASED`、行业预测能力普遍有效、项目 ROIC 已知，或产生估值、价格、BuyBand、报告发布与投资权限。下一次材料升级需要另一个未见公司或时间 holdout 复现相同效用。

## 工程验证

独立工程审阅先发现并返回两个 reusable multi-source acquisition 缺陷：一个 raw `field_id` 可跨 cell 改绑成不同经济角色，及负单位倍率可与内建减法双重计符号。修复后，multi-source 合同在 outcome access 前冻结物理事实身份；单位倍率只表示正的量纲转换，经济正负号单独绑定到允许的公式输入。原负向探针与 legacy V3 兼容性均由新的 fresh Reviewer 复审通过。

最终统一定向回归覆盖训练合同/Episode、Pack V3、multi-source acquisition、outcome settlement、working-capital 和 financial-driver consumers：

```text
239 passed, 2 skipped
```

跳过项沿用既有可选 fixture 条件，不影响本轮两臂绑定、acquisition 修复或最终效用裁决。旧 generic settlement executor 尚未支持新的 multi-source 系数接口，但该路径对新合同失败关闭、不会持久化相反经济结果；如未来接入，必须连同 executor 和 source-set registry 一并升级并新增端到端结算测试。
