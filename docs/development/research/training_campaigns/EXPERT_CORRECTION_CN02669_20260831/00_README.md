# HK02669 专家纠偏教师包

> 状态：`TRAINING_READY / RESULT_KNOWN_TEACHING_ONLY / METHOD_NOT_VALIDATED`
>
> 权限：`TRAINING_MEMORY_ONLY_NOT_CURRENT_INVESTMENT_EVIDENCE`

## 包内容

- `01_TEACHER_PACKAGE.json`：八项被接受的材料纠偏、七张条件化原则、cutoff 反馈设计和迁移验收合同；
- `02_COMPILED_TRAINING_MEMORY.md`：唯一可以交给后续 Enhanced arm 的派生记忆；
- `source_snapshots/`：目标报告 Markdown 与六份审阅/纠偏出处的内容快照（只规范化行尾空白），只供教师包出处复核；
- `docs/value_investing_from_graham_to_buffett_notes.md`：条件化原则来源，下一家公司不能把它当目标公司证据。

## 来源与身份

目标报告来自旧工作树：

`/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-q1-02669-revision-20260811/output/02669_中海物业/reports/02669_投资研究报告_Q1_读者版.revision-20260811.candidate.md`

六份审阅和 handoff 来自同一旧工作树。旧工作树仍有用户未提交改动，本次没有修改、重置或删除它；这里只复制与教师纠偏直接相关的七份快照，使训练出处不再依赖旧工作树持续存在。

目标报告的独立实质裁决是 `ACCEPT_WITH_DATA_LIMITED`，不是正式黄金发布。材料限制主要是项目/cohort 经济与法律实体现金上游未完全闭合；这正是教师包保留条件化处理，而不把终稿当标准答案全文背诵的原因。

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
