# Turtle 训练系统统一基线 2026-08-29

> 状态：`CONSOLIDATED_MAIN_BASELINE / VERIFIED`
>
> 集成分支：`feat/consolidated-training-baseline-v1`
>
> 能力底座：`feat/judgment-first-training-iteration-12h@08c8620`

## 1. 唯一基线裁决

本文件所在的验收提交快进 `main` 后，`main` 是训练、企业判断、结果结算、学习读模型和经验调用
设计的唯一新工作基线。后续 Agent 不再从本表中的旧功能分支继续扩展；需要追溯时可以读取其
提交，但新实现必须从统一 `main` 建立 linked worktree。

统一基线保留以下能力链：

```text
Judgment-First company judgment
-> Teaching / Blind / Holdout / Prospective curriculum
-> independent outcome and judgment feedback
-> investor judgment learning read model / research agenda
-> appliance Minimal and four-stage real training artifacts
-> Judgment Experience Invocation Loop design
```

这次集成只整合已经提交且可验收的能力，不把旧状态文档、重复实现或外部工作树中的未提交
代码伪装成已完成系统。

## 2. 已合入的独立成果

| 来源 | 集成状态 | 保留的能力 |
|---|---|---|
| `08c8620` | `FOUNDATION` | Judgment-First、训练课程、反馈关联 Blind、招商银行与隆基真实反馈，以及其全部祖先实现 |
| `main@56b70fe` | `ANCESTRY_RETAINED / CONTENT_SUPERSEDED` | 保留主线历史；其 V2 激活状态已被 `08c8620` 后续真实训练事实取代，不覆盖新文档 |
| `2af945b` | `MERGED` | 投资者判断学习 read model 与 research agenda 投影 |
| `14290a9` | `MERGED` | 家电 Minimal 年报版本路由、CN000921 真实结算及局部 mismatch 工件 |
| `2db94a0` | `MERGED` | 家电连续训练与 E0/E1/E2/E3 四阶段控制、采集恢复、机械结算和独立审阅 |
| `09b4b12` | `MERGED` | 企业判断经验登记、检索、调用和反馈更新的 V1 实施设计 |

## 3. 已被统一基线继承，不再单独合并

| 旧来源 | 当前裁决 | 替代来源 |
|---|---|---|
| `575a7f1` / `4c9ce30` | `PATCH_EQUIVALENT_IN_BASELINE` | `08c8620` 中的 outcome acquisition/settlement adapter |
| `8a33e67` / `9eeca86` | `EVOLVED_IN_BASELINE` | `df9ac72`、`d374db7`、`a0a2526` 后的 CJO Core/Overlay 实现 |
| `75f5302` / `bcd3a18` | `PATCH_EQUIVALENT_IN_BASELINE` | `08c8620` 中的家电行业块和 J2/J3/J4 资产 |
| `dd68882` | `ANCESTOR_OF_BASELINE` | Round 10 及其独立审阅已在 `08c8620` 历史中 |
| `5c71d53` | `SUPERSEDED_IMPLEMENTATION` | 更新后的 `enterprise_judgment_episode.py`、J1/J2/J3/J4 和真实训练工件 |
| `40f21ce` | `PATCH_EQUIVALENT` | 与已合入的 `09b4b12` 文件树相同 |
| `5eb0f1b` | `SUPERSEDED_DESIGN` | `TURTLE_JUDGMENT_EXPERIENCE_MEMORY_V1.md` 只补实际缺失的经验调用闭环 |

这些分支的工作没有丢失：能力相同或更强的版本已进入统一基线。旧分支不再决定当前状态。

## 4. 尚未合入的唯一已知代码增量

`feat/appliance-continuous-training-v1` 的已提交 HEAD `79859c7` 已被 `2db94a0` 继承，但其工作树
仍有一份未提交的 `scripts/enterprise_judgment_appliance_continuous_training.py` 修改。该修改
尝试把 acquired outcome field 接入 Minimal settlement，属于外部 Agent 的在途工作：

- 未删除、未重置、未暂存；
- 不计入本次统一基线；
- 外部 Agent 提交并通过验收后，只需从统一 `main` 做一次增量移植或合并。

这不是当前统一基线的阻断，也不能在提交前被称为已实现能力。

## 5. 后续工作规则

1. 新任务只从统一 `main` 创建 worktree；
2. 旧分支只作历史来源，不作执行入口；
3. 任何 Agent 返回成果时必须给出其 `main` 基线和独立提交；
4. 若成果基于旧分支，先做 patch-equivalence/能力映射，再移植材料增量；
5. 不再用旧 branch 名称描述系统当前进度；
6. 经验调用设计仍是 `NOT_IMPLEMENTED`，后续实现应从统一 `main` 开始；
7. 家电四阶段真实结算只证明局部机制反馈，不自动授予方法、CJO、估值、报告或投资权限。

## 6. 投资者看到的统一结果

统一以后，训练系统不再是几条互相不知道的实验线：

- 真实反馈可以进入统一的投资者学习状态与研究议程；
- 家电单字段结算和四阶段机制训练共用同一 acquisition/settlement 基础；
- Judgment-First 负责当前公司必须形成有用判断；
- 经验调用设计负责把已学到的经营机制带入下一家公司；
- 当前公司 CJO、估值和买点仍只由当前公司证据决定。

本次收口解决的是代码和训练资产继承，不宣称企业判断能力已经完成验证。
