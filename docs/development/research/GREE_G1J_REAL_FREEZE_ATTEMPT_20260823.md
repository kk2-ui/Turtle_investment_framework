# 格力 G1-J 真实冻结尝试：2026-08-23

状态：`PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`

本记录是一次实际运行结果，不是新的案例卡、行业报告或能力结论。它只回答：截至 `2026-08-03T18:00:00+08:00` 的格力公司盲轨是否已具备 G1-J 的真实冻结条件。

## 已完成的运行边界

1. 以 `000651 / gssz0000651` 从 `2018-01-01` 到 cutoff 重放巨潮官方 enumeration：`889` 条 inventory；
2. 以冻结的 `config/gree_v1_source_selection.v2.json` 选择 `41` 条官方来源；
3. 下载与页级物化结果为 `41/41 COMPLETE`，source manifest 为 `REVIEWABLE`；
4. PIT runner 对这 41 个 source ID 留下 `41` 个 `ALLOW` read，并只为它们建立 document manifest；该 manifest 为 `REVIEWABLE`；
5. 当前 document manifest 自动派生 `187` 条页级定位的 `VERIFIED` fact observation。

这些结果确认公司证据边界可重放，不能被计作 41 个公司经验样本、41 份独立报告、行业证据、选择正确性或飞轮有效性。

## 未通过的冻结门

格力当前唯一合适的公司判断问题仍是 H-A/H-B：线上相对位置下降究竟是渠道/价格带重配，还是会扩散为全渠道竞争与价格实现恶化。当前官方包没有同一 provider、同一产品/地域/渠道/品牌分母/交易点下的全渠道或线下相对位置、品牌量价、返利/佣金或可对账库存；调整后现金转换也尚无完成的逐期 bridge。

因此：

- 不能选择 H-A 或 H-B 为 3/5 年中心路径；
- 不能构造具方向性、同口径、可复算简单基线的 3--5 项 FJ；
- 不能获得 `SELECTION_ADMITTED`，只能登记为 `NO_PRIMARY`；
- 没有冻结对象，就不能进入独立盲评、未来经营结算、learning note 或跨公司字段改变。

这不是“等待中的正确”。它是当前证据下的明确拒绝，避免把线上份额、单期毛利、表观 OCF、回购动作或报告数量偷换为全渠道竞争和 normal owner cash 的判断。

## 旧账本重放失败

另一工作树的历史事实账本包含 286 条 observation，其中声称有 257 条可定位事实。将其直接交给本次新 package 的验证器后，257 条报 `quote_not_at_locator`。故旧账本不是本次冻结可接受的证据输入；它只能作为提取器回归诊断。当前可用账本是本次 runner/document manifest 下的 187 条 `VERIFIED` observation。

根因是 `ACQUISITION_MODULE + REASONING`：将忽略的旧运行输出视为可跨工作树迁移的当前事实账本。经济影响是营运资本、短借、现金转换、格力钛和资本配置的数字可能被错误带入 owner cash、永久损失或中心路径。禁止假设是“同一来源 ID 自动保证旧页码、原文定位和观察身份仍有效”。

修复是从本次 package 重新提取或逐条重验材料 observation，并只让通过当前 `document_manifest` 的记录进入 financial driver bridge。验收是每项被用于 bridge 的 observation 在当前 package 上为 `VERIFIED`，且其 locator 可重读。

## 下一条允许路径

奥维云网公开站点只确认其提供线上线下全渠道数据服务；它没有提供可冻结的历史品牌×渠道×量价 release。因此它是 acquisition route，不是格力公司事实。下一次可进入 G1-J 的输入必须是授权或可审计取得的 AVC/产业在线原始历史 release，并同时冻结 provider、dataset/release/version、查询、修订政策、产品、地域、渠道、品牌/分母、交易点、期间和定义 locator。

取得该 release 后，按既有 `enumerate-industry -> compose-industry -> download-package` 路径将它与本次 41 源公司包组合；先完成四层 bridge、H-A/H-B 的相反预测与简单基线，再申请 `SELECTION_ADMITTED` 冻结和独立盲评。没有该输入，不得以更多格力材料、宏观叙事、回购公告或后续股价代替。
