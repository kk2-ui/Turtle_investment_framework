# 研究流程干跑 04：稀疏经验会不会被伪装成精确概率？

状态：`METHOD_PREPARATION_TEST / SYNTHETIC / NO_COMPANY_RESEARCH`  
目的：测试流程能否阻止研究者在没有独立、同定义历史 episode 时，为竞争机制填入 60%/40% 之类看似严谨的概率。

## 1. 虚拟输入

研究者面对一个新公司问题，有两条可运行的机制 H-A/H-B，只有一个书籍案例、两份结果已知教学案例和若干行业转述。研究者倾向于写“我认为 H-A 60%、H-B 40%”，并计划在一年后用单一结果的 Brier score 评价自己。

## 2. 旧流程干跑：暴露的问题

验证协议已说明小样本不应报告校准数字，但迭代卡没有要求说明概率从何而来。研究者仍可将主观信心写成概率，再用一次结果制造“定量反馈”的印象。

根因：`REASONING + MODEL`。经济影响是伪概率可能错误收窄竞争、持续期和现金判断，并掩盖真正需要补的机制或数据边界。

## 3. 流程修改

每项前瞻判断必须先选不确定性表达：

- `DIRECTION_ONLY`：仅声明相对方向；
- `RANGE`：有可解释、可结算的上下界；
- `PROBABILITY`：只有在同定义、彼此独立的历史 episode 或外部可验证频率足以支撑时允许。

选择 `PROBABILITY` 时，迭代卡必须写出样本/频率来源、独立性、事件定义和校准计划；缺任一项则自动降为 `DIRECTION_ONLY` 或 `RANGE`。概率的 Brier/log score 只能在多期、独立 outcome 后报告；单一案例只结算机制，不评价概率校准。

## 4. 修改后复跑

虚拟输入没有同定义独立 episode，故 H-A/H-B 均为 `NO_PROBABILITY`。研究者可保留竞争机制和可观察的 `A_ONLY / B_ONLY` 信号，但不能写 60%/40%，也不能用一次结果产生 Brier score。

正确输出：`UNDIFFERENTIATED / NO_PROBABILITY / SIGNAL_DESIGN_REQUIRED`。

## 5. 迭代裁决

`MODIFY → RETEST_PASSED`：流程将“有不确定性”与“可校准概率”分开。真实研究中还需检验足够 episode 后的概率表达是否确实改善校准，而非只增加复杂度。
