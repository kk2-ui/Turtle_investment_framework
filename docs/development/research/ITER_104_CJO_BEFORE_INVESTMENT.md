# ITER-104 — 公司判断必须先可冻结，投资轨不得反向污染它

日期：2026-08-21

对格力恢复说明的交叉核对发现，生产 CJO 契约已经允许四层公司事实、H-A/H-B、经营 FJ 与无价格 settlement 独立完成，但旧文档仍把“模型输入和决策账目”写成所有 driver bridge 的接纳条件。这会让研究者误以为公司判断要么伪造估值/仓位，要么不能冻结。

路线改为两阶段：CJO 只要求 observation、cash-normalization contract、FJ monitoring/realization、对立机制和独立审阅；其可发布物不含价格、估值、回报或行动。只有 CJO 已形成可审阅中心路径后，投资版本才在同一 bridge 上另接市场隐含轨、估值模型和决策账目。

根因是 `MODEL + WRITING`。若沿用旧措辞，经济影响是将表观 OCF、线上排名或未判别的 H-A/H-B 直接塞入价值/行动，材料性污染 owner-cash、永久损失和仓位；或者错误地停掉本可进行的公司学习。禁止在 CJO 里补模型 ID、decision ID、股价或目标回报，也禁止将缺市场价格作为拒绝公司盲轨的理由。接纳条件是 CJO 和投资版本各自使用相应门并严格拒绝跨用途字段；格力仍因 P0 行业 release 和 cash bridge 未闭合而处在 `PRE_FREEZE / UNDISCRIMATED / NO_PROBABILITY`。
