# HK02669 专家纠偏教师包

> 状态：`TRAINING_READY / RESULT_KNOWN_TEACHING_ONLY / METHOD_NOT_VALIDATED`
>
> 权限：`TRAINING_MEMORY_ONLY_NOT_CURRENT_INVESTMENT_EVIDENCE`

## 包内容

- `01_TEACHER_PACKAGE.json`：九项被接受的材料纠偏、七张条件化原则、cutoff 反馈设计和迁移验收合同；
- `02_COMPILED_TRAINING_MEMORY.md`：唯一可以交给后续 Enhanced arm 的派生记忆；
- `source_snapshots/`：目标报告 Markdown 与七份审阅/纠偏出处，只供教师包出处复核；其中 `08` 是用户接受的旧 Q1—黄金候选成对比较，不把任一版本整体视为完美答案；
- `docs/value_investing_from_graham_to_buffett_notes.md`：条件化原则来源，下一家公司不能把它当目标公司证据。

## 来源与身份

目标报告来自旧工作树：

`/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-q1-02669-revision-20260811/output/02669_中海物业/reports/02669_投资研究报告_Q1_读者版.revision-20260811.candidate.md`

前六份审阅和 handoff 来自旧 Q1 工作树；第七份是用户对旧 Q1 与现黄金候选的接受比较。两个旧工作树均未被修改、重置或删除；教师包只持久化与规则修订直接相关的内容，完整报告不进入后续 Enhanced arm。

目标报告的独立实质裁决是 `ACCEPT_WITH_DATA_LIMITED`，不是正式黄金发布。材料限制主要是项目/cohort 经济与法律实体现金上游未完全闭合；这正是教师包保留条件化处理，而不把终稿当标准答案全文背诵的原因。

后续成对纠偏进一步收窄了旧规则：黄金候选的显式价值—终值—XIRR—行动价格层级优于旧版的全局 `UNKNOWN`，但旧版的经营利润桥、现金经济解释和敏感性归因更容易让投资者追问。现金零认可只是当前事实基准下限，不是最终经济估计。教师记忆因此同时要求可执行行动层级、读者可重建推导，以及由法律实体上游、特别返还资金来源、支付后余额和项目批次回款收窄的现金区间。

## 使用边界

后续未见公司 arm：

- Baseline 不读取本目录任何文件；
- Enhanced 只读取 `02_COMPILED_TRAINING_MEMORY.md`，其合同角色必须是 `TRAINING_MEMORY`；
- 两个 arm 都不得读取 `source_snapshots/`、教师公司事实、价格、结果和 parent conversation；
- 训练记忆只能改变问题顺序、反方检查和条件处理，不能进入目标 Episode 的证据引用；
- 第三个 fresh reviewer 先匿名审阅，再按预注册规则读取隔离结果。

## 验证

```bash
.venv/bin/python scripts/expert_correction_training.py validate \
  docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/01_TEACHER_PACKAGE.json
```

期望状态：`TRAINING_READY`。
