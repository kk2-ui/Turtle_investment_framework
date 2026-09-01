# 官方 Investor Relations 网页来源契约

状态：`ACTIVE / RESEARCH_SOURCE_ACQUISITION`

## 要解决的问题

很多公司把季度经营 KPI 首先发布在 Investor Relations 网页，而不是可由 CNINFO/SSE 取得的 PDF。若 Turtle 因为没有 PDF 就放弃这些一手、可重复披露的经营序列，真实前瞻学习会被不必要地限制；若直接把浏览器页面或新闻转述当证据，又会失去 PIT 边界。

根因是 `ACQUISITION_MODULE`，不是数据量、写作或模型评分。经济影响是研究者可能无法冻结客户频次、销量、留存等可在 6–12 个月结算的经营信号，反而退回报告数量或事后故事。

## 窄契约

`OFFICIAL_WEB_RELEASE`（HTML）或 `OFFICIAL_IR_PDF_RELEASE`（PDF）只接纳一份明确声明的、发行方自己 Investor Relations 域名上的 HTTPS release。源记录必须有：

- `release_id`、标题、发布时间、数据截止日、发行方名和声明域名；
- `source_type=OTHER_OFFICIAL` 与 `official=true`；
- 原始 HTML + 单页 Markdown，或原始 PDF + 页级 Markdown；来源版本和 reader metadata；
- 截止日前的 source package。`enumeration_complete` 仅指冻结的**研究 release 集合**完整，不指整个网站或历史档案完整。

HTML/PDF 原件是来源，Markdown 只是带页码 locator 的读取表示。网页中管理层的因果叙事仍是 `CAUSAL_ATTRIBUTION`，不会因为页面属于官网而升级为因果事实。

## 使用边界

- 可用于：公司一手的当前事实、预注册的经营 FJ、后续同口径经营结算；HBT 只接受 `official=true` 且 `BODY_READ` 的 `OTHER_OFFICIAL` 结果 source。
- 不可用于：新闻转载、第三方研究、社媒、没有明确发行方域名的页面、当前页面重建历史 PIT、行业 vendor 数据、现金/资本配置的非一手替代、价格/回报来源。
- 页面定义变化、源在观察窗口外、或页面不再能支持原文时：结算为 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，而不是换口径或补写阈值。

## 操作

```bash
python scripts/phase10_acquisition.py enumerate-web \
  --input source_release_set.input.json \
  --output source_manifest.inventory.json \
  --company-code SBUX.US \
  --cutoff-at 2026-08-21T11:55:36+08:00

python scripts/phase10_acquisition.py download-package \
  --input source_manifest.inventory.json \
  --output source_package \
  --manifest-output source_manifest.package.json
```

R-05 是首个真实 source-package 验证：两个 Starbucks 官方 IR 页面均物化为 HTML + reader，package `COMPLETE`，PIT runner `REVIEWABLE`。这只证明来源路径可用；并不证明 H-A、H-B 或公司的任何经营结论。
