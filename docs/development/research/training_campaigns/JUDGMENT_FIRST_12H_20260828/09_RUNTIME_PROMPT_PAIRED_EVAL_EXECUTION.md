# Runtime Prompt Paired Eval：执行记录

> contract：`08_RUNTIME_PROMPT_PAIRED_EVAL_CONTRACT.json`
>
> 状态：`NOT_EXECUTED / AUTHENTICATION_BLOCKED`

第一次 Baseline 调用在生成任何模型输出前返回 Anthropic `401 authentication_error`。合同规定任何
API 错误即停止且不重跑，因此：

```text
successful_baseline_calls  0
successful_enhanced_calls  0
model_outputs               0
paired_utility_verdict      NOT_AVAILABLE
```

没有更换模型、API、证据投影或 prompt commit，也没有用主 Agent 或已有结果后文本代替缺失的模型
输出。该实验不能支持或反驳 runtime prompt 的行为效用，不能计为反馈、transfer 或方法验证。

仍然成立的独立证据只有：

- active research、synthesis、full report 与完整 PIT production 路径已经注入修订后的 compact block；
- 本地 targeted tests 能检测旧的默认偏空、固定 15% 缺失折价、状态码固定仓位、无条件百分比、
  比较时钟漂移和建成即吸收等指令是否重新出现；
- 独立代码审阅为 `ACCEPT`。

这些只证明运行时接线和已知冲突被修复，不证明生成的真实企业判断已经改善。不要为本次凭据失效
增加新 gate；在正常生产凭据恢复后，另行冻结新的有界运行合同即可。
