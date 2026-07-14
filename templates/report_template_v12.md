# [公司名称] 全貌分析与投资框架报告

**风险警示与免责声明**：*本文由AI/大模型基于 [公司名称] (TICKER) 已公开披露且可核查的财报/公告文件辅助生成，仅用于学术研究与信息交流之目的。因AI/大模型存在幻觉，本文不可避免地会产生不完全符合财报原文的情况，阅读本文后产生的任何观点需核对原文。*

<!--
REPORT_GOAL
生成一份面向买方的全貌分析报告——先通过定性深度分析（Dayu 方法论）重建公司经营全貌，
再通过定量估值框架（Turtle 四因子模型）判断该不该买、买多少。
所有数据断言必须附带证据来源锚点 [source: X]。
END_REPORT_GOAL
-->

<!--
AUDIENCE_PROFILE
买方分析师/基金经理，具备财务会计基础知识，关注商业模式可持续性、回报率质量和安全边际。
报告应保持客观、审慎，不回避负面信号，不做推销式写作。
定性部分不做估值和目标价；定量部分不做无证据的商业判断。
END_AUDIENCE_PROFILE
-->

<!--
COMPANY_FACET_CATALOG
business_model_candidates:
  - 平台互联网
  - 电商/交易平台
  - 广告媒体
  - 内容/娱乐平台
  - 游戏/互动娱乐
  - 企业软件
  - 垂直软件/创意软件
  - 数据基础设施/数据中心
  - 支付/金融基础设施
  - 交易所/市场基础设施
  - 资产管理/财富管理
  - 银行
  - 消费金融/信贷
  - 保险
  - 硬件/消费电子
  - 半导体设计
  - 半导体设备/制造
  - 整车制造
  - 汽车零部件
  - 动力电池/关键部件
  - 工业制造/关键部件
  - 特种材料/配方材料
  - 大宗材料/基础化工
  - 物流网络/快递
  - 航空/航运/出行服务
  - REIT/基础设施
  - 公用事业
  - 通信/连接服务
  - 医疗器械
  - 生命科学工具
  - 生物制药
  - 医疗服务
  - 上游资源/勘探开发
  - 能源设备/服务
  - 酒店/旅游服务
  - 消费品牌
  - 零售渠道/连锁
constraint_candidates:
  - 监管敏感
  - 出口限制敏感
  - 数据/隐私敏感
  - 许可/牌照依赖
  - 高资本开支
  - 高研发驱动
  - 高营销费用驱动
  - 高SBC
  - 高负债/融资依赖
  - 利率敏感
  - 周期性强
  - 商品价格敏感
  - 专利/管线依赖
  - 支付方/报销方依赖
  - 单一关键供应商依赖
  - 客户集中
  - 单一产品/资产集中
  - 渠道/分发依赖
  - 网络效应显著
  - 规模效应显著
  - 品牌效应明显
  - 有明显定价权
  - 关联交易风险
  - 多归属/低切换成本风险
  - 预收款/合同负债敏感
  - 利用率敏感
  - 项目制/长交付周期
END_COMPANY_FACET_CATALOG
-->

---

## 投资要点概览

<!--
CHAPTER_GOAL
基于全部分析结果，把整份报告压缩成一页买方封面：先让读者一眼知道"这是什么生意、这是一家怎样的公司"，
再快速交代定性结论（继续研究/暂缓/放弃）和定量结论（买/观望/回避），以及两者是否一致。
核心不是摘要回填，而是把所有分析收成一个可快速判断的前台入口。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "封面→定性→定量→合成"
must_answer:
  - "用一句话定义这到底是什么生意"
  - "给出定性研究决定（继续研究/暂缓/放弃）及最主要理由"
  - "给出定量投资决定（买/观望/回避）及最主要理由"
  - "定性量化是否一致？若不一致，根本分歧是什么"
  - "当前最值得先看的变量和最大难点"
  - "下一步最小验证问题"
must_not_cover:
  - "不把本章写成各章节的摘要复述"
  - "不把本章拆成结论要点/详细情况/证据与出处三段结构"
required_output_items:
  - "一句话这是什么生意 + 公司简介"
  - "定性决定 + 定量决定 + 是否一致"
  - "最主要理由（最多2条）"
  - "最该先盯的变量"
  - "最大难点"
  - "下一步最小验证问题"
preferred_lens:
  - lens: "把本章当成买方决策封面页，读者应在最短时间内知道'这是什么生意→该不该买→关键变量是什么'"
    priority: core
  - lens: "若定性=继续但定量=回避（好公司太贵），显式标注根本分歧，不隐藏矛盾"
    priority: core
END_CHAPTER_CONTRACT
-->

### 一眼看懂

- **公司简介**

- **这是什么生意**

- **定性决定**：继续研究 / 暂缓 / 放弃

- **定量决定**：买入 / 观望 / 回避

- **一致吗？**

### 为什么现在是这个动作

- **最主要的理由**

- **公司现在大致处在什么状态**

- **最该先盯哪个变量**

- **现在最大的难点是什么**

### 下一步怎么验证

- **下一步最该先验证什么**

- **什么变化会改变当前动作**

---

## Part A: 定性深度分析

## 公司做的是什么生意

<!--
CHAPTER_GOAL
从第一性原理出发，清晰界定公司的生意本质：核心产品/服务、赚钱逻辑、用户与支付方、
业务结构与收入来源、在产业链中的角色与相对位置。
目标是让读者读完本章后，能用一句话向别人解释这家公司到底是做什么生意的。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "公司的核心产品/服务是什么，解决什么问题"
  - "公司的赚钱逻辑（谁付钱、为什么付钱、毛利率特征）"
  - "业务结构与收入来源（按业务线/产品/地区拆分）"
  - "公司在产业链中的位置与角色"
must_not_cover:
  - "不要在此章展开行业规模测算或竞争格局详细分析"
  - "不要在此章做估值判断"
required_output_items:
  - "核心产品/服务描述"
  - "赚钱逻辑分析"
  - "收入结构拆解"
  - "产业链位置"
  - "证据与出处"
preferred_lens:
  - lens: "关注收入质量而非收入规模：收入是交易型、订阅型、项目型还是混合型"
    priority: core
  - lens: "区分用户与支付方：谁使用产品 vs 谁为产品付费，是否一致"
    priority: core
  - lens: "若公司有多条业务线，评估各业务线的收入占比、毛利率差异和增长驱动力是否独立"
    priority: supporting
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关键资产、流量入口或分发入口
when: 只要有稳定披露且有判断价值就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 数据基础设施/数据中心, REIT/基础设施, 通信/连接服务, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的双边参与方结构或网络效应
when: 只要有稳定披露且有判断价值就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 网络效应显著]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 消费品牌公司的核心品类、价格带或目标人群
when: 只要有稳定披露且有判断价值就写
facets_any: [消费品牌, 零售渠道/连锁, 高营销费用驱动]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权正在共同定义这门生意
when: 只要有稳定披露且它比产品名称更能解释“这是什么生意”就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 预收款结构、长交付周期或验收节点正在共同定义这门生意
when: 只要有稳定披露且它比产品名称更能解释钱怎么收进来、什么时候确认就写
facets_any: [预收款/合同负债敏感, 项目制/长交付周期]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 核心变现触点或收费单位
when: 只要有稳定披露且有判断价值就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心, 通信/连接服务]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 医药/生物公司的适应症、支付方或授权结构
when: 只要有稳定披露且有判断价值就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 支付方/报销方依赖, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 部署方式、安装基础、售后或耗材关系
when: 只要有稳定披露且有判断价值就写
facets_any: [企业软件, 垂直软件/创意软件, 数据基础设施/数据中心, 工业制造/关键部件, 半导体设备/制造, 医疗器械]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 产业链环节与收费对象
when: 只要有稳定披露且有判断价值就写
facets_any: [半导体设计, 半导体设备/制造, 汽车零部件, 动力电池/关键部件, 工业制造/关键部件, 特种材料/配方材料, 大宗材料/基础化工]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 使用场景或关键交付对象
when: 只要有稳定披露且有判断价值就写
facets_any: [工业制造/关键部件, 半导体设备/制造, 医疗器械, 医疗服务, 上游资源/勘探开发, 能源设备/服务]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 使用者、客户与付款方并不一致
when: 只要有稳定披露且这种分离会直接改变商业理解就写
facets_any: [平台互联网, 广告媒体, 医疗服务, 生物制药, 支付/金融基础设施, 保险, 银行, 消费金融/信贷, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 更细的收入分部、业务 segments 或产品线拆分
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 重要收入地理分布或更细区域拆分
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了这类生意里常见的情况之外、最能定义这门生意的特殊情况
when: 只要有稳定披露且它比这类生意里常见的情况更能说明“这家公司到底靠什么赚钱”就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 关键牌照、协议、渠道或生态入口依赖
when: 只要有稳定披露且有判断价值就写
facets_any: [监管敏感, 许可/牌照依赖, 渠道/分发依赖, 支付方/报销方依赖, 单一关键供应商依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 单一产品、单一区域、单一客户或单一支付方主导收入结构
when: 只要有稳定披露且有判断价值就写
facets_any: [单一产品/资产集中, 客户集中, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 核心收费、分成或合作结构依赖特殊制度安排
when: 只要有稳定披露且有判断价值就写
facets_any: [支付/金融基础设施, 交易所/市场基础设施, 银行, 消费金融/信贷, 保险, 平台互联网, 电商/交易平台, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 关联交易、关联渠道或内部结算安排直接影响生意定义
when: 只要有稳定披露且它会明显改变你对用户、付费方或赚钱方式的理解就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 客户集中度
when: 只要有稳定披露且有判断价值就写
facets_any: [客户集中]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 品牌心智、标准地位或默认入口
when: 只要有稳定披露且有判断价值就写
facets_any: [消费品牌, 零售渠道/连锁, 平台互联网, 企业软件, 垂直软件/创意软件, 网络效应显著]
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 核心产品与服务

#### 赚钱逻辑

#### 业务结构与收入来源

#### 产业链位置与角色

### 证据与出处

---

## 行业吸引力与公司位置

<!--
CHAPTER_GOAL
评估行业是否值得看、公司在行业中的相对位置、是否有结构性硬伤。
核心问题是：这个行业整体在变好还是变差？公司在这个行业里是领先者、追赶者还是边缘角色？
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "行业基本结构（规模、增速、集中度、进入壁垒）"
  - "行业关键趋势与变化方向"
  - "公司在行业中的竞争位置（市场份额、差异化来源）"
  - "行业层面是否存在结构性问题使公司难以获得超额回报"
must_not_cover:
  - "不要在此章展开详细的财务分析"
  - "不要泛泛而谈'行业前景广阔'"
required_output_items:
  - "行业结构概述"
  - "关键趋势与变化方向"
  - "公司竞争位置"
  - "行业结构性风险"
  - "证据与出处"
preferred_lens:
  - lens: "先判断行业的经济性、结构性约束和进入壁垒是否值得继续看，再判断公司位置是否存在先天硬伤。先用看这类生意时通常最先要看的东西解释行业吸引力，再用一个最关键的公司位置变量解释这家公司为什么能站在现在的位置。最后给一条最关键的有利点和一条最关键的硬伤——不要把优点缺点铺成并列清单。"
    priority: core
  - lens: "能先用客观事实和直接依据说清的，不要先写强判断；若影响只是合理推断而缺少直接支撑，应降级为待跟踪变量。"
    priority: core
  - lens: "平台、交易平台与广告生意优先看默认入口、流量分发权、广告预算位置、数据回传能力和同时用多家的风险，再判断公司位置是被网络效应保护，还是被平台规则与流量迁移削弱。"
    facets_any: ["平台互联网", "电商/交易平台", "广告媒体", "数据/隐私敏感", "网络效应显著", "多归属/低切换成本风险"]
    priority: core
  - lens: "内容、游戏与互动娱乐优先看内容供给权、爆款依赖、分发渠道、用户留存和生命周期管理，再判断公司位置来自稳定内容工厂，还是单款产品与单一渠道驱动。"
    facets_any: ["内容/娱乐平台", "游戏/互动娱乐", "渠道/分发依赖"]
    priority: core
  - lens: "软件与数据基础设施优先看工作流默认位置、切换成本、预算关键性、部署/迁移难度和收费机制，再判断公司位置来自深度嵌入与数据资产，还是来自阶段性销售优势。"
    facets_any: ["企业软件", "垂直软件/创意软件", "数据基础设施/数据中心"]
    priority: core
  - lens: "半导体、设备、关键零部件与动力电池优先看技术代际、客户验证周期、良率/性能、资本开支强度和供应链位置，再判断公司位置来自真实技术与生态优势，还是来自景气与客户周期。"
    facets_any: ["半导体设计", "半导体设备/制造", "汽车零部件", "动力电池/关键部件", "高资本开支"]
    priority: core
  - lens: "工业制造、特种材料和硬件优先看认证周期、单机价值量、产品规格、交付能力、售后服务和全球配套能力，再判断公司位置是否建立在长期验证与执行壁垒上。"
    facets_any: ["工业制造/关键部件", "特种材料/配方材料", "硬件/消费电子"]
    priority: core
  - lens: "整车、消费品牌、零售渠道和硬件/消费电子优先看品牌心智、渠道控制、价格权、产品周期、库存节奏和营销投入效率，再判断公司位置来自稳固品牌、规模和定价权，还是来自促销、补库或短期投放。"
    facets_any: ["整车制造", "消费品牌", "零售渠道/连锁", "硬件/消费电子", "高营销费用驱动", "品牌效应明显", "规模效应显著", "有明显定价权"]
    priority: core
  - lens: "医药、器械、生命科学工具与医疗服务优先看临床/产品差异化、支付覆盖、监管审批、医生/医院采用和服务网络密度，再判断公司位置到底是靠疗效和规则带来的保护站稳，还是会被专利、支付和执行上的限制削弱。"
    facets_any: ["生物制药", "医疗器械", "生命科学工具", "医疗服务", "监管敏感", "支付方/报销方依赖", "专利/管线依赖"]
    priority: core
  - lens: "支付、交易所、资管、银行、消费金融与保险优先看牌照和规则优势、信任、费率权、负债成本、风控能力与监管位置，再判断公司位置到底来自真正的制度壁垒，还是主要吃到了周期和利率环境的好处。"
    facets_any: ["支付/金融基础设施", "交易所/市场基础设施", "资产管理/财富管理", "银行", "消费金融/信贷", "保险", "监管敏感", "利率敏感"]
    priority: core
  - lens: "REIT、通信、公用事业、物流网络和酒店/旅游服务优先看资产区位、网络密度、利用率、合同/费率机制、容量扩张与再投资回收，再判断公司位置是否来自稀缺资产与网络效应，还是来自周期性供需错配。"
    facets_any: ["REIT/基础设施", "通信/连接服务", "公用事业", "物流网络/快递", "航空/航运/出行服务", "酒店/旅游服务", "高资本开支", "利用率敏感"]
    priority: core
  - lens: "上游资源、能源设备与基础化工优先看资源禀赋、成本曲线、项目回收期、商品价格敏感度和资本纪律，再判断公司位置来自低成本资产与执行能力，还是来自价格上行带来的好处。"
    facets_any: ["上游资源/勘探开发", "能源设备/服务", "大宗材料/基础化工", "商品价格敏感", "周期性强"]
    priority: core
  - lens: "如果网络效应、同时用多家的风险、品牌效应、定价权、利率环境、预收款结构或长交付周期，本身就会改变行业吸引力或公司位置判断，就优先按这些约束来写，不要等业务类型去兜底。"
    facets_any: ["网络效应显著", "多归属/低切换成本风险", "品牌效应明显", "规模效应显著", "有明显定价权", "高营销费用驱动", "利率敏感", "预收款/合同负债敏感", "项目制/长交付周期"]
    priority: core
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 利润池/价值主要落点
when: 只要有稳定披露且它直接决定行业吸引力或公司位置就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 更细的市场份额或竞争位置数字
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 更细的利润率、增速或行业经济性数字
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了这类生意里常见的情况之外、最能改变公司位置判断的特殊情况
when: 只要有稳定披露且它比这类生意里常见的情况更能解释公司为什么站在这个位置就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的用户同时用多家、流量迁移或分发依赖
when: 只要有稳定披露且有判断价值就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 网络效应显著, 多归属/低切换成本风险, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的平台规则依赖或广告预算位置
when: 只要有稳定披露且它直接改变行业位置判断就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 网络效应显著, 多归属/低切换成本风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的专利悬崖、支付方压价或审批风险
when: 只要有稳定披露且它直接改变行业位置判断就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 监管敏感, 支付方/报销方依赖, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 软件/数据公司的工作流默认位置、AI 商业化或收费/取消机制风险
when: 只要有稳定披露且它直接改变行业位置判断就写
facets_any: [企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 游戏/内容公司的爆款依赖、渠道分发或生命周期衰减
when: 只要有稳定披露且它直接改变公司位置质量就写
facets_any: [内容/娱乐平台, 游戏/互动娱乐, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 工业/制造公司的认证周期、客户资本开支依赖、安装基础或关键供应约束
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [工业制造/关键部件, 特种材料/配方材料, 硬件/消费电子, 高资本开支, 单一关键供应商依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 半导体公司的技术代际、出口限制、客户验证、资本开支或生态位置
when: 只要有稳定披露且它直接改变行业位置判断就写
facets_any: [半导体设计, 半导体设备/制造, 出口限制敏感, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 汽车链公司的车型周期、单车价值量、客户绑定或电池技术路径
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [整车制造, 汽车零部件, 动力电池/关键部件]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 保险/经纪公司的地域集中、渠道位置、赔付波动或投资收益敏感性
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [保险, 利率敏感, 客户集中]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/消费金融/资管公司的负债成本、风控纪律或牌照/牌照和规则优势
when: 只要有稳定披露且它直接改变行业位置判断就写
facets_any: [银行, 消费金融/信贷, 资产管理/财富管理, 利率敏感, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医疗服务公司的支付方关系、医生资源或服务网络密度
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [医疗服务, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 消费品牌/零售公司的品牌力、渠道位置或营销投入效率
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [消费品牌, 零售渠道/连锁, 高营销费用驱动]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权是否让公司站到更有利的位置
when: 只要有稳定披露且它直接改变行业吸引力或公司位置判断就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 利率变化是不是在放大利润池或公司位置判断
when: 只要有稳定披露且它直接决定当前位置更像真实优势还是资金环境顺风就写
facets_any: [利率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 预收款、合同负债或长交付周期会不会让位置看起来比实际更稳
when: 只要有稳定披露且它直接决定公司位置判断是否被收款节奏或项目周期放大就写
facets_any: [预收款/合同负债敏感, 项目制/长交付周期]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 电信/连接公司的频谱、网络覆盖或价格竞争
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [通信/连接服务, 高资本开支, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 媒体/内容公司的版权库、分发依赖或订阅黏性
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [广告媒体, 内容/娱乐平台, 游戏/互动娱乐]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 物流/出行/酒店公司的网络密度、利用率或供给投放约束
when: 只要有稳定披露且它直接改变公司位置判断就写
facets_any: [物流网络/快递, 航空/航运/出行服务, 酒店/旅游服务, 利用率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一关键渠道、平台、支付方或合作方依赖
when: 只要有稳定披露且它显著放大公司位置脆弱性就写
facets_any: [渠道/分发依赖, 支付方/报销方依赖, 客户集中]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一地区、单一客户、单一产品或单一适应症集中
when: 只要有稳定披露且它显著放大公司位置脆弱性就写
facets_any: [单一产品/资产集中, 客户集中, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 关联交易、控股安排或关联渠道是否扭曲真实位置判断
when: 只要有稳定披露且它会明显影响你对公司真实位置的理解就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌认知、标准地位或用户心智
when: 只要有稳定披露且对公司位置形成结构性保护就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 消费品牌公司的货架优先级、渠道控制力或心智份额
when: 只要有稳定披露且对公司位置形成结构性保护就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 替代威胁或供给约束
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 制造、软件或金融基础设施公司的认证、切换成本，或牌照和规则带来的保护
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 银行/综合金融公司的低成本负债、信用成本或牌照位置
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 能源/资源公司的成本曲线、资源禀赋、价格敏感度或资本纪律
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: REIT/基础设施公司的租户质量、合同期限、电力/容量获取或资本结构约束
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 渠道位置或客户议价
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 核心收费机制、取消机制或分发机制正受监管/诉讼冲击
when: 只要有稳定披露且它直接改变行业吸引力或公司位置就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关键市场准入、出口限制或地缘政治约束
when: 只要有稳定披露且它直接改变行业吸引力或公司位置就写
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 行业基本结构

#### 关键趋势与变化方向

#### 公司在行业中的竞争位置

#### 行业结构性风险

### 证据与出处

---

## 商业模式机制、护城河与关键约束

<!--
CHAPTER_GOAL
深入分析公司为什么能持续赚钱（或不能）、护城河的来源与强度、商业模式中的脆弱点和关键约束。
本章是定性分析的核心章节，输出将直接影响 Turtle Zone J 的护城河评级和 b_penalty 参数。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "公司的护城河来源（品牌/网络效应/规模效应/转换成本/技术壁垒/监管壁垒/成本优势）及其强度"
  - "公司是否存在B类/劣质业务板块及其对整体回报率的拖累（用于估算 b_penalty）"
  - "公司的增长机制是什么（量价驱动、提价能力、品类扩张、地域扩张、并购）"
  - "商业模式中的关键脆弱点与约束（客户集中、供应商依赖、技术迭代风险等）"
  - "公司是否具备长期提价能力"
must_not_cover:
  - "不要在此章计算具体估值数字"
  - "不要将护城河分析写成公司竞争优势的广告式罗列"
required_output_items:
  - "护城河来源与强度评估"
  - "B类业务识别与 b_penalty 评估"
  - "增长机制分析（g_base 上下文）"
  - "关键约束与脆弱点"
  - "证据与出处"
preferred_lens:
  - lens: "护城河评估应基于可观察的证据（定价能力、市场份额稳定性、回报率持续性），而非管理层陈述"
    priority: core
  - lens: "区分'有护城河'和'暂时领先'——后者可能因为技术周期、监管变化或竞争加剧而消失"
    priority: core
  - lens: "对于平台/互联网公司，重点评估网络效应的强度、多归属程度和赢家通吃的可能性"
    priority: supporting
    facets_any: ["平台互联网", "电商/交易平台", "内容/娱乐平台", "游戏/互动娱乐"]
  - lens: "对于品牌消费品，重点评估品牌溢价的可验证性（是否体现在毛利率、复购率、价格带上）"
    priority: supporting
    facets_any: ["消费品牌", "零售渠道/连锁"]
  - lens: "对于制造业/工业公司，重点评估规模效应、技术壁垒和客户转换成本"
    priority: supporting
    facets_any: ["工业制造/关键部件", "整车制造", "汽车零部件", "动力电池/关键部件"]
  - lens: "对于资源类公司，重点评估资源禀赋的稀缺性、开采成本和价格周期中的生存能力"
    priority: supporting
    facets_any: ["上游资源/勘探开发", "大宗材料/基础化工", "能源设备/服务"]
  - lens: "对于医药/生物科技公司，重点评估管线价值、专利悬崖和研发成功率"
    priority: supporting
    facets_any: ["生物制药", "医疗器械", "生命科学工具"]
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 品牌认知、标准地位或用户心智
when: 只要有稳定披露且它是客观机制，不是营销拔高，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了这类生意里常见的情况外，最容易改变判断的特殊情况
when: 只要有稳定披露且它比这类生意里常见的情况更能解释为什么能持续赚钱，或为什么会变脆弱，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 网络效应、切换成本，或产品到底用得有多深
when: 只要有稳定披露且它直接决定客户是否持续留下或持续付钱就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的双边自强化或用户同时用多家带来的削弱
when: 只要有稳定披露且它直接决定这套赚钱方式是在自我强化，还是正在被平台规则削弱，就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 网络效应显著, 多归属/低切换成本风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的默认入口、分发依赖或广告拍卖机制
when: 只要有稳定披露且它直接决定流量如何转成收入、利润或现金流就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 游戏/内容公司的内容供给、留存曲线或爆款依赖
when: 只要有稳定披露且它直接决定用户是否留存、内容是否续供或收入是否可持续就写
facets_any: [内容/娱乐平台, 游戏/互动娱乐, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 规模效应、密度效应或成本曲线
when: 只要有稳定披露且它能明显增强对这套赚钱方式质量的解释力就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权是否真能把价值留在公司里
when: 只要有稳定披露且它直接决定客户是否持续接受当前价格与利润结构就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 网络效应或同时用多家的风险能不能真正把用户和价值留住
when: 只要有稳定披露且它直接决定需求能不能留下、价值能不能留在公司里就写
facets_any: [网络效应显著, 多归属/低切换成本风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 利率环境、预收款结构或长交付周期是不是让这套模式看起来比实际更稳
when: 只要有稳定披露且它直接决定收入、现金流或价值沉淀是不是被外部环境和确认节奏放大就写
facets_any: [利率敏感, 预收款/合同负债敏感, 项目制/长交付周期]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 工业、设备或基础设施公司的安装基数、耗材/服务收入或维护合同
when: 只要有稳定披露且它直接决定一次性卖出能否转成持续收入和利润就写
facets_any: [工业制造/关键部件, 半导体设备/制造, 医疗器械, REIT/基础设施, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 半导体公司的设计胜出、技术代际、安装基数、关键供应或出口限制
when: 只要有稳定披露且它直接决定技术优势能否沉淀成持续收入和现金流就写
facets_any: [半导体设计, 半导体设备/制造, 出口限制敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 监管、牌照、认证门槛，或规则带来的保护
when: 只要有稳定披露且它直接决定客户能否使用、公司能否收费或竞争者能否进入就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的专利/独占期、支付覆盖或合作分成
when: 只要有稳定披露且它直接决定产品价值如何留在公司里而不是被支付方、渠道或合作方拿走就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 医疗服务, 支付方/报销方依赖, 监管敏感, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 汽车链公司的平台化、单车价值量、客户绑定或电池技术路径
when: 只要有稳定披露且它直接决定公司是赚车型周期的钱，还是赚长期技术或绑定的钱就写
facets_any: [整车制造, 汽车零部件, 动力电池/关键部件, 客户集中]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 软件/数据公司的工作流默认位置、AI 商业化或收费/取消机制
when: 只要有稳定披露且它直接决定客户为什么持续付钱或为什么可能不再付钱就写
facets_any: [企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医疗服务公司的支付方关系、医生供给或服务网络
when: 只要有稳定披露且它直接决定患者流量、服务利用率和单位经济性就写
facets_any: [医疗服务, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 保险/经纪公司的承保纪律、地域集中、渠道依赖或浮存金
when: 只要有稳定披露且它直接决定保费增长、赔付波动和投资收益如何共同构成这门生意的赚钱方式就写
facets_any: [保险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/消费金融/资管公司的低成本负债、风控或牌照与规则优势
when: 只要有稳定披露且它直接决定收益率、成本和风险是否能长期共存就写
facets_any: [银行, 消费金融/信贷, 资产管理/财富管理, 利率敏感, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 电信/连接公司的网络覆盖、每用户收入或流失率控制
when: 只要有稳定披露且它能更快说明付费持续性就写
facets_any: [通信/连接服务, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 媒体/内容公司的内容库、分发渠道或订阅留存
when: 只要有稳定披露且它能显著增强对留存和变现节奏的解释力就写
facets_any: [广告媒体, 内容/娱乐平台]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: REIT/基础设施公司的互联密度、电力容量或再融资约束
when: 只要有稳定披露且它直接决定资产利用、定价权和资本回收能否持续就写
facets_any: [REIT/基础设施, 数据基础设施/数据中心, 高资本开支, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 能源/资源公司的资源寿命、成本曲线或资本纪律
when: 只要有稳定披露且它直接决定顺周期收入能否沉淀成长期可持续现金流就写
facets_any: [上游资源/勘探开发, 能源设备/服务, 大宗材料/基础化工, 商品价格敏感, 周期性强]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一关键供应商、关键技术来源或关键许可依赖
when: 只要有稳定披露且它直接决定这条赚钱链里哪一环最可能被卡住就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、内部结算或关联渠道安排
when: 只要有稳定披露且它直接改变价值如何留在公司里或被谁拿走就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一产品、单一渠道、单一客户或单一适应症依赖
when: 只要有稳定披露且它直接决定收入或需求能否持续就写
facets_any: [单一产品/资产集中, 客户集中, 渠道/分发依赖, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 客户习惯、默认选择或生态嵌入
when: 只要有稳定披露且它能解释为什么客户不轻易离开就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 客户集中、验证周期、资本开支或内容成本这些难绕开的地方
when: 只要有稳定披露且它直接决定这套赚钱方式现在看是比较稳，还是偏脆弱，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 核心收费机制、分发机制或合作结构正被监管、诉讼或制度变化重塑
when: 只要有稳定披露且它直接决定原来的赚钱方式是不是正在失效，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 大额转型投入正在改变原来的赚钱方式
when: 只要有稳定披露且转型投入会直接改变原来的收费、分发或成本结构就写
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 护城河来源与强度评估

#### B类/劣质业务板块识别（b_penalty 相关）

#### 增长机制（g_base 上下文）

#### 关键约束与脆弱点

### 证据与出处

---

## 最近一年关键变化与当前阶段

<!--
CHAPTER_GOAL
识别公司在最近一年的关键变化（战略、经营、财务、行业层面），并判断公司当前所处的
生命周期阶段（成长期/成熟期/转型期/衰退期）。帮助读者理解"现在发生了什么"和"公司在哪个阶段"。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "最近一年最重要的变化是什么（最多3-5项）"
  - "这些变化是阶段性的还是结构性的"
  - "公司当前处于生命周期的哪个阶段"
  - "当前阶段对投资判断的核心含义是什么"
must_not_cover:
  - "不要逐一罗列年报中提到的所有变化"
  - "不要在此章做估值判断"
required_output_items:
  - "关键变化清单（每项标注阶段性/结构性）"
  - "生命周期阶段判断"
  - "阶段含义与投资启示"
  - "证据与出处"
preferred_lens:
  - lens: "区分'公司变了'和'环境变了'——前者改变公司的内在价值，后者可能只是周期波动"
    priority: core
  - lens: "关注变化是否改变了公司赚钱的逻辑，而非仅改变短期增速"
    priority: core
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了行业里的共同点之外、最能解释“为什么是现在”的特殊情况
when: 只要有稳定披露且它比行业里常见的节奏更能解释当前阶段判断就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的流量入口、广告测量或平台规则变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 数据/隐私敏感, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 消费品牌/零售公司的渠道去库存、提价节奏或新品周期
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [消费品牌, 零售渠道/连锁, 高营销费用驱动]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌力、规模效应或定价权在过去一年是增强了还是减弱了
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的临床、审批或商业化节点
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 支付方/报销方依赖, 专利/管线依赖, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医疗服务公司的支付方、利用率或医护供给变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [医疗服务, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 工业/制造公司的订单、积压、验证、交付或产能投放变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [工业制造/关键部件, 半导体设备/制造, 整车制造, 汽车零部件, 动力电池/关键部件, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 软件/数据公司的续费、用量、AI 商业化或销售效率变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 半导体公司的技术代际、库存周期、客户验证或出口管制变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [半导体设计, 半导体设备/制造, 出口限制敏感, 周期性强]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/保险公司的资金成本、赔付率、准备金或信用质量变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [银行, 消费金融/信贷, 保险, 利率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 能源/运输/公用事业公司的项目进度、运价、费率或利用率变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [上游资源/勘探开发, 能源设备/服务, 公用事业, 物流网络/快递, 航空/航运/出行服务, 酒店/旅游服务, 商品价格敏感, 利用率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 电信/媒体公司的 每用户收入、内容供给、订阅结构或 流失率 变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [通信/连接服务, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 大额资产出售、业务剥离、并购整合或资本结构突变
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [REIT/基础设施, 资产管理/财富管理, 公用事业, 上游资源/勘探开发, 高负债/融资依赖, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 核心收费机制、取消机制、支付规则或监管框架的突发变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [平台互联网, 电商/交易平台, 支付/金融基础设施, 交易所/市场基础设施, 银行, 消费金融/信贷, 保险, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一产品、单一适应症、单一渠道、单一客户或单一区域的关键节点变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [单一产品/资产集中, 客户集中, 专利/管线依赖, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、资产注入/剥离或关联渠道安排变化
when: 只要有稳定披露且它直接改变当前阶段或研究优先级就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 变化还没完全兑现、仍在验证中的关键前提
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 当前阶段最受哪一个特殊情况影响
when: 只要有稳定披露且它比一般行业节奏更能解释当前阶段就写
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 最近一年关键变化

#### 变化性质判断（阶段性 vs 结构性）

#### 生命周期阶段判断

#### 当前阶段的投资含义

### 证据与出处

---

## 经营表现与核心驱动

<!--
CHAPTER_GOAL
分析公司近几年的经营表现，识别核心驱动因素，区分结构性改善与周期性波动，
评估经营数据的可信度。本章输出将用于 Turtle Zone J 的增长分类和增量 ROIC 判断。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "近几年营收、毛利率、费用率的变化趋势及核心驱动"
  - "增长是由量驱动还是价驱动"
  - "经营改善是结构性的还是周期性的"
  - "经营数据是否存在需要警惕的信号（如应收账款增速远超营收增速）"
must_not_cover:
  - "不要在此章做详细的财务三表分析（留给Ch6）"
  - "不要在此章计算GG或DDM"
required_output_items:
  - "营收与毛利驱动分析"
  - "量与价拆解"
  - "结构性 vs 周期性判断"
  - "经营数据可信度评估"
  - "证据与出处"
preferred_lens:
  - lens: "经营分析的核心不是增速高低，而是增速的质量和可持续性"
    priority: core
  - lens: "关注经营杠杆的方向：收入增长是带来利润率扩张（正向经营杠杆）还是利润率压缩（负向经营杠杆）"
    priority: core
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了行业里的共同点之外、最能解释当前经营表现的特殊情况
when: 只要有稳定披露且它比行业里常见的情况更能解释当前经营表现就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网公司的用户活跃、参与深度或广告加载变化
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 网络效应显著]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 消费品牌/零售公司的销量、价格、产品组合或渠道去库存
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [整车制造, 消费品牌, 零售渠道/连锁, 高营销费用驱动]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权变化
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 预收款、合同负债、项目交付或验收节奏是不是在扭曲当前经营表现
when: 只要有稳定披露且它直接改变你对收入、利润率或现金转换的理解就写
facets_any: [预收款/合同负债敏感, 项目制/长交付周期]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的处方量、渗透率或支付覆盖
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 医疗服务, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医疗服务公司的同店增长、利用率或支付方 mix
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [医疗服务, 支付方/报销方依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 工业/制造公司的出货、订单转化、产能利用率或验证进度
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [工业制造/关键部件, 整车制造, 汽车零部件, 动力电池/关键部件, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 软件/数据公司的 经常性收入、净收入留存和席位数 或 用量 变化
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 半导体公司的 ASP、良率、库存、利用率或客户验证变化
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [半导体设计, 半导体设备/制造, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/保险公司的净息差、赔付率、续保率或信用成本变化
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [银行, 消费金融/信贷, 保险, 利率敏感, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 能源/运输/公用事业公司的产量、运价、入住率、利用率或费率回收
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [上游资源/勘探开发, 能源设备/服务, 公用事业, REIT/基础设施, 物流网络/快递, 航空/航运/出行服务, 酒店/旅游服务, 周期性强, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 电信/媒体公司的 每用户收入、订阅净增、流失率 或内容成本回收
when: 只要有稳定披露且它直接改变经营判断就写
facets_any: [通信/连接服务, 广告媒体, 内容/娱乐平台, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 当前经营表现最受哪一个特殊情况影响
when: 只要有稳定披露且它比一般行业节奏更能解释当前表现就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 价格、销量、产品组合或客户结构的拆分
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 销售效率、获客成本、客户留存或复购的拆分
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 产能、良率、利用率、服务网络密度或门店成熟度的拆分
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 一次性因素、口径变化、并购并表或外部环境帮忙的剥离
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一产品、单一适应症、单一渠道、单一客户或单一区域集中驱动
when: 只要有稳定披露且它直接改变经营判断就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 核心收费、支付、分发或结算机制变化对经营数据的扭曲
when: 只要有稳定披露且它直接改变你对经营结果的理解就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、内部供销或关联渠道安排对经营数据的扭曲
when: 只要有稳定披露且它直接改变你对经营结果真实性的理解就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 营收增长驱动分析

#### 毛利率与费用率趋势

#### 结构性 vs 周期性判断

#### 经营数据可信度评估

### 证据与出处

---

## 财务表现与资本配置

<!--
CHAPTER_GOAL
分析公司的财务健康状况：利润质量、现金流生成能力、资产负债表安全性、
以及管理层的资本配置决策（再投资/并购/分红/回购）。
本章与 Turtle 的 financial_trends 互补而非重复——Turtle 负责标准化数据提取，本章负责定性判断。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "利润质量如何（经营利润 vs 非经常性损益、应计项目比例）"
  - "现金流生成能力（OCF/NP 比例、FCF 稳定性、营运资金效率）"
  - "资产负债表安全性（杠杆水平、短期偿债压力、表外风险）"
  - "管理层资本配置的过往记录与质量判断"
must_not_cover:
  - "不要在此章重复 Turtle compute_bundle 的计算结果"
  - "不要在此章做估值或目标价判断"
required_output_items:
  - "利润质量评估（非经常项、应计比例）"
  - "现金流质量评估"
  - "资产负债表安全性"
  - "资本配置记录与判断"
  - "证据与出处"
preferred_lens:
  - lens: "利润质量的核心是'利润是否转化为现金'——OCF/NP 持续偏低是危险信号"
    priority: core
  - lens: "资本配置判断不是看公司做了什么，而是看这些决策是否在长期提升了每股价值"
    priority: core
  - lens: "对于高杠杆/高负债公司，重点评估再融资风险和利率敏感性"
    priority: supporting
    facets_any: ["高负债/融资依赖", "利率敏感"]
  - lens: "对于高资本开支公司，重点评估增量ROIC是否高于加权平均资金成本"
    priority: supporting
    facets_any: ["高资本开支"]
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 行业里不常见、但更能说明当前财务判断的情况
when: 只要有稳定披露，且它比行业里常见的情况更能说明当前财务判断，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 毛利率、运营利润率和现金流转换这几年的变化
when: 只要有稳定披露，且它会明显影响你对财务质量的看法，就写
facets_any: [工业制造/关键部件, 企业软件, 垂直软件/创意软件, 消费品牌, 零售渠道/连锁, 半导体设计, 半导体设备/制造, 整车制造, 汽车零部件, 动力电池/关键部件]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权有没有真正撑住毛利和现金流
when: 只要有稳定披露，且它会明显影响你对财务质量的看法，就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 利率变化是不是让利润、资本回报或资金压力看上去比实际更好或更差
when: 只要有稳定披露，且它会明显改变你对财务结果真实性或安全性的看法，就写
facets_any: [利率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 预收款、合同负债或长交付周期会不会让收入和现金流前后错位
when: 只要有稳定披露，且它会明显改变你对利润质量、现金创造能力或资金压力的看法，就写
facets_any: [预收款/合同负债敏感, 项目制/长交付周期]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 债务比例、付息能力或再融资压力这几年的变化
when: 只要有稳定披露，且它会明显影响你对财务安全性的看法，就写
facets_any: [高负债/融资依赖, REIT/基础设施, 数据基础设施/数据中心, 通信/连接服务, 公用事业, 上游资源/勘探开发, 航空/航运/出行服务, 酒店/旅游服务]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: SBC 占收入比例、回购占总股本比例或分配覆盖这几年的变化
when: 只要有稳定披露，且它会明显影响你对每股价值的看法，就写
facets_any: [高SBC, 平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: non-GAAP、一次性项目或会计口径的剥离
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/软件公司的 SBC、递延收入或自由现金流质量
when: 只要有稳定披露，且它会明显影响你对利润质量的看法，就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心, 高SBC]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 制造、半导体或能源公司的库存、折旧、应收或维持性资本开支
when: 只要有稳定披露，且它会明显影响你对利润质量的看法，就写
facets_any: [工业制造/关键部件, 半导体设计, 半导体设备/制造, 整车制造, 汽车零部件, 动力电池/关键部件, 硬件/消费电子, 上游资源/勘探开发, 能源设备/服务, 大宗材料/基础化工, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 金融或保险公司的拨备、准备金、资金成本或监管口径利润
when: 只要有稳定披露，且它会明显影响你对利润质量的看法，就写
facets_any: [银行, 消费金融/信贷, 保险, 支付/金融基础设施, 交易所/市场基础设施, 资产管理/财富管理, 监管敏感, 利率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/保险公司的资本充足、流动性或准备金约束
when: 只要有稳定披露且它直接决定安全性判断就写
facets_any: [银行, 消费金融/信贷, 保险, 支付/金融基础设施, 交易所/市场基础设施, 资产管理/财富管理, 高负债/融资依赖, 监管敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 电信/基础设施/REIT 的高杠杆与再融资约束
when: 只要有稳定披露且它直接决定安全性判断就写
facets_any: [REIT/基础设施, 数据基础设施/数据中心, 通信/连接服务, 公用事业, 物流网络/快递, 航空/航运/出行服务, 酒店/旅游服务, 高负债/融资依赖, 高资本开支]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的现金还能撑多久，以及对融资的依赖
when: 只要有稳定披露且它直接决定安全性判断就写
facets_any: [生物制药, 高研发驱动, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 资本结构突变、再融资窗口、项目融资或外部融资依赖
when: 只要有稳定披露且它直接决定安全性判断就写
facets_any: [高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一资产、单一项目或单一区域的负债与承诺集中
when: 只要有稳定披露且它直接决定安全性判断就写
facets_any: [单一产品/资产集中, 客户集中, REIT/基础设施]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 受限现金、客户资金、项目融资或表外承诺
when: 只要有稳定披露且它直接决定安全性或资本分配判断就写
facets_any: [REIT/基础设施, 支付/金融基础设施, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、内部资金占用或非常规往来
when: 只要有稳定披露且它直接改变你对财务安全性或资本分配的理解就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 回购、分红、并购或 资本开支 的优先级判断
when: 只要有稳定披露且它直接决定资本分配判断就写
facets_any: [高资本开支, 高SBC, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 高投入行业的资本纪律
when: 只要有稳定披露且它直接决定资本分配判断就写
facets_any: [高资本开支, 高研发驱动, 上游资源/勘探开发, 能源设备/服务, 半导体设计, 半导体设备/制造, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 现金回流与股东稀释的平衡
when: 只要有稳定披露且它直接决定资本分配判断就写
facets_any: [高SBC, 平台互联网, 广告媒体, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 后面最该继续盯的一两个财务变量
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 利润质量评估

#### 现金流质量评估

#### 资产负债表安全性

#### 资本配置记录与判断

### 证据与出处

---

## 股东回报路径

<!--
CHAPTER_GOAL
分析股东回报的实现路径：分红政策、回购行为、股权稀释情况、以及资本分配是否偏向股东。
核心问题是：如果公司赚了钱，股东能拿到多少、通过什么方式拿到。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "公司是否有持续稳定的分红记录和政策"
  - "回购是价值创造还是抵消股权激励稀释"
  - "是否存在大规模股权激励稀释股东权益的情况"
  - "资本分配整体偏向股东还是偏向管理层/再投资"
must_not_cover:
  - "不要在此章做DDM估值（留给Ch12）"
required_output_items:
  - "分红政策与记录"
  - "回购行为分析（含稀释抵消评估）"
  - "股权激励稀释评估"
  - "资本分配偏向判断"
  - "证据与出处"
preferred_lens:
  - lens: "重点关注每股价值的增长，而非总派息金额——总派息可能被股本扩张稀释"
    priority: core
  - lens: "对于高SBC公司，回购的真实目的往往是掩盖股权激励的稀释效应而非回馈股东"
    priority: supporting
    facets_any: ["高SBC"]
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 除了行业里的共同点之外、最能解释股东回报判断的特殊情况
when: 只要有稳定披露且它比行业里常见的情况更能解释股东回报真假和可持续性就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 分红、回购、再投资或去杠杆的主次关系
when: 只要有稳定披露且它直接决定股东最后拿到什么就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/软件公司的回购与 SBC 稀释平衡
when: 只要有稳定披露且它直接决定每股回报是否真实就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心, 高SBC]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 银行/保险/公用事业公司的分派与资金压力平衡
when: 只要有稳定披露且它直接决定回报能不能持续就写
facets_any: [银行, 消费金融/信贷, 保险, 公用事业, REIT/基础设施, 通信/连接服务, 利率敏感, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权有没有真正变成每股回报
when: 只要有稳定披露且它直接决定股东最后拿到的是现金回流，还是被品牌维护、扩张和产品投入吞掉就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 稀释来源与每股回报侵蚀
when: 只要有稳定披露且它直接决定股东有没有被悄悄稀释就写
facets_any: [高SBC, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 高投入行业的资本开支或项目投资对股东回报的侵蚀
when: 只要有稳定披露且它直接决定现金有没有真正回到股东手里就写
facets_any: [高资本开支, 半导体设备/制造, 数据基础设施/数据中心, REIT/基础设施, 公用事业, 通信/连接服务, 上游资源/勘探开发, 能源设备/服务, 航空/航运/出行服务, 酒店/旅游服务]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 医药/生物公司的融资依赖与远期回报
when: 只要有稳定披露且它直接决定回报是不是还只是远期命题就写
facets_any: [生物制药, 医疗器械, 生命科学工具, 高研发驱动, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、关联分红、内部资金占用或关联渠道安排
when: 只要有稳定披露且它直接改变你对股东回报真实性、公平性或可持续性的判断就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 股东回报框架或资本分配纪律的稳定性
when: 只要有稳定披露且它直接决定这条回报路径能不能持续就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 外部管理、控股股东或特殊分派安排
when: 只要有稳定披露且它直接改变股东回报的真实性或公平性就写
facets_any: [REIT/基础设施, 资产管理/财富管理, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 资产出售、杠杆变化或财务工程驱动的表面回报
when: 只要有稳定披露且它直接决定回报是不是表面上好看就写
facets_any: [高负债/融资依赖, REIT/基础设施, 资产管理/财富管理, 上游资源/勘探开发]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易风险是否让股东回报看上去更好、但实际质量更差
when: 只要有稳定披露且它直接决定回报是不是表面上好看就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 后面最该继续盯的一两个股东回报变量
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 分红政策与记录

#### 回购行为与效果分析

#### 股权激励与稀释评估

#### 资本分配偏向判断

### 证据与出处

---

## 管理层、治理与激励

<!--
CHAPTER_GOAL
评估公司的治理质量：核心决策者是谁、治理结构是否存在制衡、管理层的激励是否与股东利益一致。
本章输出将影响 Turtle Zone J 的数据质量折扣评估。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "核心决策者是谁（实控人/管理层/董事会构成）"
  - "治理结构是否存在有效的制衡机制"
  - "管理层激励是否与长期股东利益一致（薪酬结构、KPI选择、锁定期）"
  - "是否存在关联交易、资金占用或其他治理风险信号"
must_not_cover:
  - "不要在此章对管理层进行人身评价"
required_output_items:
  - "核心决策者画像"
  - "治理制衡评估"
  - "激励一致性分析"
  - "治理风险信号"
  - "证据与出处"
preferred_lens:
  - lens: "关注管理层'做了什么'而非'说了什么'——资本配置决策是最好的品格检验"
    priority: core
  - lens: "对于国企/央企，关注治理约束是否来自制度而非个人；对于民企，关注实控人风险"
    priority: core
  - lens: "对于高SBC公司，关注激励是否过度偏向短期股价而非长期价值创造"
    priority: supporting
    facets_any: ["高SBC"]
  - lens: "对于有控股结构/VIE等复杂架构的公司，关注少数股东保护和利益输送风险"
    priority: supporting
    facets_any: ["关联交易风险"]
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 创始人控制力或关键人物依赖
when: 只要有稳定披露且它直接决定谁在真正做决定以及治理会不会过度依赖单个人就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 内容/娱乐平台, 游戏/互动娱乐, 企业软件, 垂直软件/创意软件, 生物制药]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 管理层的经营与资本分配框架
when: 只要有稳定披露且它直接决定管理层是偏长期每股价值，还是偏规模和表面增长就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 金融、保险或基础设施公司的风险与资本决策责任边界
when: 只要有稳定披露且它直接决定关键风险、资本和分派到底由谁拍板就写
facets_any: [支付/金融基础设施, 交易所/市场基础设施, 资产管理/财富管理, 银行, 消费金融/信贷, 保险, REIT/基础设施, 公用事业, 通信/连接服务]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权对应的管理取舍
when: 只要有稳定披露且它直接决定管理层是在保护长期优势，还是在透支这些优势换短期结果就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 平台/互联网或软件公司的强控制弱约束问题
when: 只要有稳定披露且它直接决定治理是不是容易失去约束就写
facets_any: [平台互联网, 电商/交易平台, 广告媒体, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 周期和高投入行业的扩张纪律约束
when: 只要有稳定披露且它直接决定治理能不能约束在景气高点盲目扩产、顺周期投资或项目冲动就写
facets_any: [半导体设备/制造, 整车制造, 汽车零部件, 动力电池/关键部件, 工业制造/关键部件, 上游资源/勘探开发, 能源设备/服务, 公用事业, 高资本开支, 周期性强]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、内部结算或控股安排是否削弱约束
when: 只要有稳定披露且它直接决定董事会、委员会或少数股东保护是否失灵就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易定量分析——关联方收入具体金额及占总收入比例、定价对比、财务公司存款金额及利率。禁止只做定性描述
when: 关联交易占比>10%时触发
facets_any: [关联交易风险, 客户集中]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 股权激励、SBC 或绩效指标的偏差
when: 只要有稳定披露且它直接决定激励是不是偏离长期每股价值就写
facets_any: [高SBC, 平台互联网, 企业软件, 垂直软件/创意软件, 数据基础设施/数据中心]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 控制权安排或关键股东约束
when: 只要有稳定披露且它直接决定少数股东是否要承担额外治理风险就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 外部管理人、关联方交易或关键合作方约束
when: 只要有稳定披露且它直接决定治理真实性、公平性或信息透明度就写
facets_any: [REIT/基础设施, 资产管理/财富管理, 支付/金融基础设施, 渠道/分发依赖, 单一关键供应商依赖, 关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌、规模或定价权被用来服务长期价值，还是服务短期拉货和表面增长
when: 只要有稳定披露且它直接决定激励和控制权会把公司带向哪里就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易或控股安排会不会让少数股东承担额外风险
when: 只要有稳定披露且它直接决定激励和控制权是否真正公平就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 核心决策者

#### 治理结构制衡机制

#### 管理层激励与股东利益一致性

#### 治理风险信号

### 证据与出处

---

## 核心风险与否决项

<!--
CHAPTER_GOAL
识别公司面临的否决级风险（一票否决）、重大限制性风险和可跟踪风险。
本章融合 Dayu 的风险识别方法论和 Turtle 的风险矩阵。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化枚举"
must_answer:
  - "是否存在否决级风险（一旦发生将彻底改变投资逻辑）"
  - "重大限制性风险有哪些（虽不否决但显著影响回报预期）"
  - "需要持续跟踪的风险指标有哪些"
must_not_cover:
  - "不要写'股市有风险投资需谨慎'之类的通用风险声明"
required_output_items:
  - "否决级风险清单（如有，触发条件 + 潜在影响）"
  - "重大限制性风险清单"
  - "持续跟踪指标"
  - "证据与出处"
preferred_lens:
  - lens: "否决级风险的判断标准：一旦发生，无论当前估值多低，投资逻辑都将失效"
    priority: core
  - lens: "区分'可能发生的坏事情'和'一旦发生就game over的事情'——只有后者才是否决级"
    priority: core
END_CHAPTER_CONTRACT
-->

<!--
ITEM_RULE
mode: optional
item: 专业名词释义
when: 只要有稳定披露且有判断价值就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: optional
item: 单一产品、单一客户、单一平台或单一市场依赖
when: 只要有稳定披露且有判断价值就写
facets_any: [单一产品/资产集中, 客户集中, 渠道/分发依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 监管、合规、诉讼或规则变化带来的风险
when: 只要有稳定披露，且它会明显影响风险会不会从可跟踪问题升级为否决项，就写
facets_any: [监管敏感, 数据/隐私敏感, 许可/牌照依赖, 支付方/报销方依赖, 出口限制敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 行业里不常见、但最可能把问题推到否决边缘的情况
when: 只要有稳定披露，且它比行业里常见的风险更能解释为什么问题会升级，就写
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权正在变弱
when: 只要有稳定披露，且它会明显影响研究前提会不会被推翻，就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易、内部结算、关联渠道或控股安排带来的风险
when: 只要有稳定披露，且它会明显影响风险是不是被低估，或是否可能伤害少数股东，就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 融资、杠杆或现金还能撑多久带来的风险
when: 只要有稳定披露，且它会明显影响风险更像否决项、必须先处理的大问题，还是还能继续跟踪，就写
facets_any: [高负债/融资依赖, 高资本开支, 高研发驱动]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 周期、库存、利用率或价格波动带来的风险
when: 只要有稳定披露，且它会明显影响风险什么时候会快速放大，就写
facets_any: [周期性强, 商品价格敏感, 高资本开支, 利用率敏感]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 技术路线、临床节点或项目进度这类关键验证点
when: 只要有稳定披露，且它是下一轮最可能直接推翻研究前提的验证点，就写
facets_any: [半导体设计, 半导体设备/制造, 动力电池/关键部件, 生物制药, 专利/管线依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 单一关键供应商、关键技术来源或关键牌照带来的风险
when: 只要有稳定披露，且它是下一轮最可能直接推翻研究前提的验证点，就写
facets_any: [单一关键供应商依赖, 出口限制敏感, 许可/牌照依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 大额转型投入、并购整合或资本结构重整带来的风险
when: 只要有稳定披露，且它是下一轮最可能直接推翻研究前提的验证点，就写
facets_any: [高资本开支, 高研发驱动, 高负债/融资依赖]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 品牌效应、规模效应或定价权还能不能守住
when: 只要有稳定披露，且它是下一轮最值得优先验证的风险变量，就写
facets_any: [品牌效应明显, 规模效应显著, 有明显定价权]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 关联交易或控股安排会不会继续放大风险
when: 只要有稳定披露，且它是下一轮最值得优先验证的风险变量，就写
facets_any: [关联交易风险]
END_ITEM_RULE
-->
<!--
ITEM_RULE
mode: conditional
item: 资产陷阱三段论——(1)现金在谁手里(控股股东/公司账上/中小股东可及？)(2)催化剂在哪里(有无特别分红/大额回购/资产剥离计划？)(3)历史验证(过去5年有无释放股东价值的先例？)
when: 净现金/市值>100%或PB<0.6x时触发。三段论的核心不是判断"是否便宜"，而是判断"便宜能否被实现"
facets_any: [高资本开支, 周期性强, 商品价格敏感, 上游资源/勘探开发, REIT/基础设施, 银行, 保险]
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 否决级风险

#### 重大限制性风险

#### 持续跟踪指标

### 证据与出处

---

## Part B: 量化投资判断

## 增长质量与参数校准

<!--
CHAPTER_GOAL
在定性分析的基础上，对公司的增长质量进行定量校准：增长轨迹、利润vs营收增速差、
增量ROIC、增长类型分类（维护性/成长性/混合型）。本章输出将作为 Turtle Factor 2/3 GG 计算的参数基础。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化分析"
must_answer:
  - "近五年营收和归母净利润的增速轨迹及趋势"
  - "增量ROIC是否显著高于加权平均资金成本"
  - "增长类型分类（维护性/成长性/混合型）及其依据"
  - "基于定性上下文（Ch3/Ch5）的增长可持续性判断"
must_not_cover:
  - "不要在此章做最终估值判断"
required_output_items:
  - "营收与利润增长轨迹"
  - "增量ROIC计算与判断"
  - "增长类型分类"
  - "增长可持续性评估（利用定性上下文）"
  - "证据与出处"
END_CHAPTER_CONTRACT
-->

### 结论要点

### 详细情况

#### 增长轨迹（2021-2025）

#### 增量ROIC分析

#### 增长类型分类

#### 定性上下文交叉验证

### 证据与出处

---

## 穿透回报率 GG

<!--
CHAPTER_GOAL
计算 Turtle 因子2（粗算GG）和因子3（精算GG），利用定性分析的护城河判断和增长分类改善参数估计。
核心问题：在当前参数下，这只股票的预期穿透回报率是否超过门槛回报率 II。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "计算展示 + 判断"
must_answer:
  - "因子2粗算结果（R(NP)、R(OE)、M系数、OCF/NP质量）"
  - "因子3精算结果（AA序列、GG基准/悲观/乐观三档、λ值）"
  - "GG vs II 判断（超额/不足/边界）"
  - "定性护城河判断对GG参数的影响说明"
must_not_cover:
  - "不要在此章重新分析商业模式或护城河（引用Ch3即可）"
required_output_items:
  - "因子2粗算展示"
  - "因子3精算展示"
  - "GG vs II 判断"
  - "参数来源与定性交叉引用"
  - "证据与出处"
END_CHAPTER_CONTRACT
-->
<!--
ITEM_RULE
mode: conditional
item: GG 精算 12 步完整推导（对标海螺水泥报告）。具体格式：(1)参数表—列出 NP_avg/OE_avg/AA_avg/M/Q/MC/g_adj/II 全部8个参数，标注来源 (2)方法论检查—OCF/NP 背离 >2x？折旧/NP>50%触发重资产豁免？ (3)AA 逐年表—调 compute_aa 展示 9 年 FCF+收款比率+趋势判断 (4)GG 公式完全展开—逐行写 GG_np=[NP]×[M]×(1-[Q])/[MC]×100=[结果]%，GG_oe 同理 (5)三档情景—悲观(NP-15%)/基准/乐观(NP+15%)，标注每档假设差异 (6)M 值溯源—标注 M 来源(computed/fallback)+样本数，若 fallback 必须警示 (7)HH 偏离—|R(NP)-GG|，>3pct→因子2不适用 (8)敏感性—"若股价翻倍，GG降至X%""若M降至0.4，GG降至X%"
when: 写 GG 章时强制执行。禁止只输出一个最终数字。对标的报告是海螺水泥 2864 行报告中 GG 章的精算深度。
END_ITEM_RULE
-->

### 结论要点

### 详细情况

#### 因子2：粗算穿透回报率

#### 因子3：精算穿透回报率

#### GG vs II 综合判断

#### 定性上下文对GG参数的影响

### 证据与出处

---

## DDM 估值与仓位建议

<!--
CHAPTER_GOAL
基于 Turtle 因子4 DDM模型，计算多层公允价（保守/基准/乐观），
给出阶梯买入价和仓位建议。核心问题：当前价格下，是否有足够的安全边际。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "计算展示 + 结论"
must_answer:
  - "DDM合理PE基准及依据"
  - "DDM三轨估值（保守/基准/乐观）及对应公允价"
  - "GG-DDM分歧度分析"
  - "阶梯买入价与仓位建议"
must_not_cover:
  - "不要在此章重新讨论是否值得研究（那是Ch13的职责）"
required_output_items:
  - "合理PE基准与参数锚定"
  - "DDM三轨估值结果"
  - "当前价 vs 公允价对比"
  - "阶梯买入价"
  - "仓位建议"
  - "证据与出处"
END_CHAPTER_CONTRACT
-->

### 结论要点

### 详细情况

#### DDM合理PE基准

#### DDM三轨估值

#### GG-DDM分歧度分析

#### 阶梯买入价与仓位建议

### 证据与出处

---

## Part C: 综合决策

## 综合决策

<!--
CHAPTER_GOAL
将定性研究决定（Dayu: Continue/Pause/Abandon）与定量投资决定（Turtle: Buy/Hold/Avoid）
合成为一个统一的5状态决策，显式标注定性定量一致性或根本分歧。
END_CHAPTER_GOAL
-->

<!--
CHAPTER_CONTRACT
narrative_mode: "结构化判断"
must_answer:
  - "定性研究决定及核心理由（Continue/Pause/Abandon）"
  - "定量投资决定及核心理由（Buy/Hold/Avoid）"
  - "定性定量合成结果（Strong Buy/Buy/Hold/Avoid/Strong Reject）"
  - "若定性定量不一致，根本分歧是什么"
  - "关键假设与脆弱点"
  - "监控触发器与退出条件"
must_not_cover:
  - "不要在定性定量一致时不必要地制造分歧叙事"
  - "不要将合成决策写成各打五十大板的平衡表述"
required_output_items:
  - "定性研究决定 + 核心理由"
  - "定量投资决定 + 核心理由"
  - "合成决策矩阵结果"
  - "定性定量一致性/分歧分析"
  - "关键假设与脆弱点"
  - "监控触发器与退出条件"
END_CHAPTER_CONTRACT
-->
<!--
ITEM_RULE
mode: optional
item: GG/DDM 估值逻辑前提差异分析——GG 隐含 PE=1/GG≈X倍(看利润可持续性)，DDM 隐含 PE=公允价/DPS≈Y倍(看分红意愿)。两者前提不同：GG 假设利润维持当前水平，DDM 假设分红维持当前水平。如果利润下滑但分红不变，GG降而DDM不降——这种结构性矛盾需要在"定性定量一致性"部分充分讨论，不能只说"方向一致"
when: 写综合决策章时自动触发
END_ITEM_RULE
-->

### 定性研究决定

### 定量投资决定

### 合成决策矩阵

| | Turtle: Buy | Turtle: Hold | Turtle: Avoid |
|---|---|---|---|
| **Dayu: Continue** | Strong Buy | Cautious Watch | 好公司太贵 — 等待更好价格 |
| **Dayu: Pause** | 价格错配 — 验证定性 | Hold Review | Likely Avoid |
| **Dayu: Abandon** | 数据冲突 — 重新核验 | Slow Fade | Strong Reject |

### 定性定量一致性分析

### 关键假设与脆弱点

### 监控触发器与退出条件

---

## 来源清单

<!--
CHAPTER_GOAL
自动聚合全部分析章节中使用的 [source: X] 证据锚点，按来源类型分类展示。
END_CHAPTER_GOAL
-->

{source_list}
