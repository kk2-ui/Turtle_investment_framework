# R-62 Judgment-First Paired Runtime Contract

## Purpose

This is one prospective paired runtime test of the active Judgment-First prompt
change. It asks whether that prompt produces a more useful best-current
enterprise judgment on the previously blocked Pengding automotive/server PCB
case without weakening evidence, PIT, or authority boundaries.

This run is an evaluation of a prompt change. It is not a new historical
training episode, a feedback turn, transfer validation, method freeze, CJO,
valuation, BuyBand, or investment authorization.

## Frozen case and evidence budget

- Company: `CN:002938` / Pengding Holdings (Shenzhen) Co., Ltd.
- Cutoff: `2023-03-30T00:00:00+08:00`.
- Evidence packet, and only this packet:
  - `../00_source_selection.json`;
  - `../01_pre_outcome_admission_screen.md`.
- Permitted official source references are the two cutoff-visible CNINFO
  documents already identified in `00_source_selection.json`.
- The paired model receives the local packet text. It receives no web, file,
  search, retrieval, price, outcome, or other tools.
- `02_training_readiness_return.md`, all post-cutoff material, prices, and
  outcome evidence are excluded.

## Fixed task

Both arms receive this same user task:

> 截至 2023-03-30，只根据所附证据，投资者目前应如何判断鹏鼎的汽车/服务器 PCB 扩产？它应如何进入企业判断和投资研究的基准情景？请形成一份简洁、可反驳、对投资研究有用的当前结论，不得获取或假设任何其他材料。

Both arms receive this same shared system instruction:

> 你是 Turtle 的企业研究综合员。只能使用用户提供的 cutoff 前证据，不得搜索或调用工具，不得读取结果、价格或 cutoff 后材料。必须区分事实、推论和尚未获得的权限；不得把项目审批、客户认证、公司层收入或集团现金直接等同于项目客户吸收、单位经济或 owner cash。用自然的投资者语言回答，避免复述流程，正文控制在约 700 至 1200 个汉字。

The evidence packet is appended verbatim after the fixed task.

## Arms

- Baseline arm: shared system instruction only.
- Enhanced arm: the identical shared system instruction followed by the exact
  output of `_judgment_first_prompt_block("report")` from
  `scripts/turtle_agent/agent_loop.py` at base commit `a32733e`.

No other prompt, evidence, model, or budget difference is allowed. The arms do
not see one another's output. There is no semantic retry or repair loop.

## Runtime budget and stop conditions

- Provider: Anthropic direct Messages API, with tools omitted.
- Model: `claude-sonnet-4-20250514`.
- Temperature: `0`.
- Maximum output tokens: `2500` per arm.
- Maximum primary model calls: `2`, one per arm.
- Maximum independent review calls: `1`.
- Provider retries: `0`.
- Wall-clock upper bound: `30 minutes` for the paired run and review.

Stop without accepting the experiment if:

- either arm cannot run under the same fixed conditions;
- either arm accesses or cites excluded outcome, price, post-cutoff, or outside
  evidence;
- the evidence or token budget differs across arms;
- an arm is regenerated or repaired for semantic quality;
- the enhanced arm turns uncertainty into unsupported confidence or crosses an
  authority boundary.

## Blind review

A fresh model context receives the two raw outputs under neutral labels, the
case cutoff, and the frozen evidence packet. It does not receive the arm
mapping or the treatment description.

The reviewer compares:

1. whether there is a clear best-current enterprise judgment;
2. whether the economic mechanism is explicit and evidence-linked;
3. whether the strongest rival explanation is engaged;
4. whether unknowns are localized instead of ending the whole judgment;
5. whether the investment consequence and reversal conditions are actionable;
6. whether evidence, PIT, and authorization boundaries remain intact.

The reviewer must identify concrete field-level differences and return one of:

- `OUTPUT_1_MATERIALLY_BETTER`;
- `OUTPUT_2_MATERIALLY_BETTER`;
- `NO_MATERIAL_DIFFERENCE`;
- `INVALID_COMPARISON`.

After the blind verdict is frozen, the coordinator reveals the arm mapping.
The experiment is accepted as `JUDGMENT_FIRST_RUNTIME_PAIRED_ACCEPTED` only if
the enhanced arm is judged materially better and has no material boundary
violation. Fluent prose, greater confidence, or greater length alone is not a
pass.
