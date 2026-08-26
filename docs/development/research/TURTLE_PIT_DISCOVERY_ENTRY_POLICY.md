# Turtle 历史 PIT 发现入口政策

状态：`CURRENT / V4_SELECTION_DISCOVERY_ONLY`
更新：2026-08-25
适用：[V4 候选采集工作包](templates/TURTLE_V4_CANDIDATE_ACQUISITION_WORK_PACKAGE_TEMPLATE.md) 的 Stage-0/A；不适用当前公司研究、前瞻研究或已冻结 outcome acquisition。

本文只约束 `RELATIVE_CAUSAL / Comparative Episode` 的 PIT discovery。Industry History 与 Teaching/Lifecycle 仍须标记资料时间角色，但不以本文的五成员 V5 feasibility 门作为总入口。分层迁移前 H1/H2 仍按当前 closed-roster validator 执行；迁移后也只允许 outcome 前、按冻结 eligibility predicate 追加 static official PDF batch，动态 CNINFO 禁令不变。

## 要防止的真实失效

CNINFO 的 `new/fulltextSearch` 与证券个股页不是 PIT-safe 的历史发现入口。即使操作者先填好历史日期，页面仍可能先自动渲染当前价格、最新公告或证券卡；日期过滤只约束结果列表，不能约束页面附属组件。塔牌集团 002233 因代码检索、而行业关键词检索也因自动展示 2026 当前公告而失败。二者都不是资料不足或候选的经济裁决；它们是 `ACQUISITION_MODULE` 的页面路由错误。

经济影响是当前行情或结果期标题会污染历史选择者的信息集，令随后形成的 H-A/H-B、样本选择或弃权不再是严格 PIT。故一旦发生，当前公司不能改用同一历史年报或换一条行动继续入选。

## 当前唯一允许的入口

| entry kind | 可做 | 不可做 |
|---|---|---|
| `KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF` | 打开一组已由 cutoff-before identity、发布日期和 official source ID 预先指明的 `https://static.cninfo.com.cn/...PDF`。 | 从该 PDF 包返回 CNINFO 发行人页、公告 detail 页或任何全文搜索页补查。 |

CNINFO 的行业/机制关键词全文检索当前同样禁止；实测其前端忽略历史日期并展示 2026 当前公告。未来只有某一接口经单独、日期边界测试证明不会加载当前价格、标题或元数据，并以新的 policy/admission version 记录后，才可加入白名单。当前 V5 Stage-0 仍必须 cohort-first，并以已知 cutoff-before 年报的 D2/D3/D4 可得性建立五家 feasibility carriers；该数量只属于当前 comparative topology，不因为入口收紧而降低行动、D2、材料性、同行或 firewall 门。

## 操作顺序

1. 先冻结 cohort cutoff、预声明 static PDF package 与 outcome firewall；在任何页面载入前记录它们。
2. 若已有原件 identity，直接打开预先列明的 static CNINFO PDF package，并确认**每一份** source ID、发布日期、发行人边界和字段位置都在 cutoff 前。
3. curator 先只读 H1 PDF package；将每一份 URL、source ID 和发布日期加入 allowlist，再建立 H1 receipt。H1 不得含行动决定、实际实施或 H-A/H-B。H1 成功后，curator 可一次性提交绑定 receipt 的 H2 action-screen static-PDF extension；行动决定、实际实施、成本/客户观察可以分属其不同原件，但 extension 开始 screen 后不得再增加或替换。任何额外公司页、detail 页、搜索页、价格、推荐卡或 cutoff 后标题都不是“补充查证”。
4. 若页面自动出现 post-cutoff 标题、元数据、价格或结果正文，立即停止该对象：`EXPOSURE_EXCLUDED`。记录触发页面与暴露类别；不得读取其余内容，也不得由同一 curator 用相同对象继续筛选。

## 可审阅记录

每份 V4 discovery manifest 的 `source_firewall.discovery_entry` 必须声明：

```json
{
  "kind": "KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF",
  "issuer_code_or_name_submitted_to_cninfo_fulltext": false,
  "cninfo_issuer_stock_or_detail_page_opened": false,
  "post_identification_access": "PREDECLARED_CUTOFF_BEFORE_STATIC_CNINFO_PDF_PACKAGE_ONLY",
  "static_pdf_sources": [
    {
      "url": "https://static.cninfo.com.cn/finalpage/<date>/<id>.PDF",
      "source_id": "<a supplied cutoff-before source_id>"
    }
  ]
}
```

每个 `static_pdf_sources[].source_id` 必须确实出现在同一 manifest 的 supplied evidence 和 phase-10 allowlist 中。该记录提供可复核的流程证据，不伪称能隔离操作者的浏览器；正常协作环境的浏览器隔离仍由 task space 与 PIT allowlist 承担。

## 为什么范围到此为止

本政策不添加哈希、抓取镜像、代理、账户隔离或第二套浏览器。它只封堵已发生且会改变 PIT 结论的入口：CNINFO 前端的发行人可解析搜索**和行业关键词搜索**都会自动展示当前信息；两者均不得用于 PIT discovery。当前 cohort-first 只能由 curator 交付预声明的官方 static-PDF package 启动；若未来发现一个可证明不会展示当前信息的独立官方接口，必须以新 policy/admission version 单独验证，不能凭日期参数假定安全。结果包和最终来源阅读继续沿用既有 source allowlist 与独立 custodian 流程。
