# Report Autonomy Five Phase — Appliance Pack Seed Source Audit

> 审计性质：`PACK_SIDE / SOURCE_ONLY / CUTOFF_ONLY / RESULT_ISOLATED`  
> 覆盖财年：`FY2015`—`FY2017`；不读取或引用 FY2018+ 的正文、价格、回报、估值或任何结果材料。  
> 结论权限：只确认现有来源线索、发行人暴露角色和字段缺口；不判断 Pack 是否有效、训练是否有效，亦不新建 Pack、比较面板或公司结论。

## 1. 审计对象与时间边界

本审计只交叉读取下列既有对象的**来源元数据、J2 线程、已登记的经营边界和来源定位**：

- [`CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json`](CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json)：五家发行人的截止日内法定静态 PDF register；其中 C1 为 `2017-04-30`，C2 为 `2018-09-30`。
- [`CN_APPLIANCE_INDUSTRY_J234_V1.json`](CN_APPLIANCE_INDUSTRY_J234_V1.json)：五个 J2 机制候选线程、listed-consolidated 责任边界及 J4 的最小字段缺口。
- [`CN_APPLIANCE_TEACHING_PACK_V1_IMPLEMENTATION.md`](CN_APPLIANCE_TEACHING_PACK_V1_IMPLEMENTATION.md) 与 [`CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1.md`](CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1.md)：现有五个 teaching drill 和其经营系统标签。
- 仅为检查 FY2015 线索而读取 [`CNINFO_000333_FY2015.md`](experiments/R-02_action_vs_judgment_kuka/01_source_notes/CNINFO_000333_FY2015.md) 的来源身份段；该卡是美的的要约前语境卡，不被升级为 appliance Pack 来源。

“FY2017”表示报告期截至 2017-12-31；其在 2018 年发布的年报仍属本审计的财年窗口。反之，register 中格力的 FY2018 H1 条目只作为**排除元数据**识别，未读取其正文，也不计入下表。

现有 register 并没有声明一个新的、完整 FY2015—FY2017 Pack 截止日。因此本审计不虚构第三个 cutoff；它只报告：现有 C1/C2 来源中哪些财年线索已经存在、哪些仍需取得。

## 2. 可放入同一 Pack 的训练侧 issuer roster（来源种子层）

五家公司都已在 `ILB:CN:APPLIANCE:NATIONAL:V1` 的行业宇宙和 teaching drill 中出现；在 J234 的 universe 中其共同登记角色都是 `CORE_SYSTEM_RECONSTRUCTION`。下表的“经营暴露角色”是已有 J2 arena/线程的简写，**不是**为未来 Pack 新赋予的 `CENTRAL`、`HETEROGENEOUS` 或其他角色。

| 训练侧发行人 | 既有经营暴露角色（J2） | 已登记的 J2 线程与观察钟 | FY2015 线索 | FY2016 CNINFO 法定静态 PDF | FY2017 CNINFO 法定静态 PDF | 审计性来源状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 珠海格力电器（`CN:000651`） | 房间空调；渠道、核心部件与制造系统 | `T:GREE:CHANNEL_COMPONENT`，`C1_ONLY` | appliance register / 已检查 source docs 中未登记 | `CNINFO:000651:ANN:20170427:1203403930`；报告期 FY2016，公告 2017-04-27，PDF pp. 8–12、20–23 | appliance register 中未登记 FY2017 年报；仅有 FY2018 H1 元数据，已排除 | FY2016 线索明确；FY2015 与 FY2017 均待补 |
| 美的集团（`CN:000333`） | 房间空调、冰洗与多品类渠道/供应链系统 | `T:MIDEA:CHANNEL_SUPPLY_CHAIN`，`C2_ONLY` | `CNINFO:000333:ANN:20160326:1202084987`；FY2015 年报，公告 2016-03-26。现存卡只将其定位为要约前语境，尚非 appliance register 条目 | `CNINFO:000333:ANN:20170330:1203240657`；报告期 FY2016，公告 2017-03-30，PDF pp. 11–14、18–25 | `CNINFO:000333:ANN:20180330:1204557296`；报告期 FY2017，公告 2018-03-30，PDF pp. 12、14、18–23 | 三个财年都有线索，但 FY2015 仍须转为 Pack 内静态来源并确认家电责任边界 |
| 青岛海尔（`CN:600690`） | 冰洗；服务、物流与交付系统 | `T:HAIER:SERVICE_LOGISTICS`，`C2_ONLY` | appliance register / 已检查 source docs 中未登记 | `CNINFO:600690:ANN:20170429:1203428901`；报告期 FY2016，公告 2017-04-29，PDF pp. 10–13、16、18、25–28、33–34 | `CNINFO:600690:ANN:20180426:1204797433`；报告期 FY2017，公告 2018-04-26，PDF pp. 10–11、13、16、20–21、24–25、29–30 | FY2016—FY2017 线索明确；FY2015 待补 |
| 海信科龙（`CN:000921`） | 房间空调与冰洗双产品；产品、成本和库存传导 | `T:HISENSE:PRODUCT_COST_INVENTORY`，`C1_ONLY` | appliance register / 已检查 source docs 中未登记 | `CNINFO:000921:ANN:20170330:1203223381`；报告期 FY2016，公告 2017-03-30，PDF pp. 9、11–12、15、18 | `CNINFO:000921:ANN:20180330:1204544098`；报告期 FY2017，公告 2018-03-30，PDF pp. 9、11–13、18 | FY2016—FY2017 线索明确；FY2015 待补 |
| 四川长虹（`CN:600839`） | 空调、冰箱与多产品发行人边界；白电组合 | `T:CHANGHONG:WHITEGOODS_PORTFOLIO`，`C2_ONLY` | appliance register / 已检查 source docs 中未登记 | `CNINFO:600839:ANN:20170428:1203418558`；报告期 FY2016，公告 2017-04-28，PDF pp. 9–12、16 | `CNINFO:600839:ANN:20180418:1204647552`；报告期 FY2017，公告 2018-04-18，PDF pp. 10、12–14、18 | FY2016—FY2017 线索明确；FY2015 待补 |

这给出了多于四家的 issuer 种子 roster，但不把不同 `C1_ONLY` / `C2_ONLY` 观察钟伪装为同一期横截面，也不把这些发行人升级成产品级可比对象。

## 3. 现有来源能确认什么，不能确认什么

### 已确认的来源线索

- 五个 FY2016 source ID 都在 appliance source register 内，均标为 `OFFICIAL_STATUTORY_STATIC_PDF`，并有公告日、静态 PDF URL 和页码集合。
- FY2017 的美的、海尔、海信科龙和四川长虹年报也在该 register 内，均以相同来源身份和精确页码登记。
- 美的 FY2015 年报存在一个精确 `lineage_id` 线索，但该来源卡的既有用途是收购要约前的背景，不能由此省略家电产品与责任边界的 Pack-side 复核。
- 五个 J2 线程均至少把 `CUSTOMER`、`OPERATING`、`COMPETITION` 作为机制问题的必需 cell；它们为以后逐 issuer 收集同结构字段提供了既有路线，而不是公司间结论。

### `DATA_COVERAGE` 缺口

1. **FY2015 的 roster coverage 不完整。** 现有 appliance register 对五家公司均没有 FY2015 年报条目；被检查的现有 source docs 只给出美的一条 FY2015 年报线索。因此，目前不能从既有 Pack-side register 填出四家或更多发行人的连续 FY2015—FY2017 CNINFO 来源链。
2. **格力的 FY2017 年报未进入 appliance register。** 该 register 的格力 C2 来源是 FY2018 H1，按本审计范围排除；它不能替代 FY2017 年报。
3. **同 arena 的字段尚未覆盖。** J4 已明确缺少同产品客户/SKU cohort、同责任边界的销量、成本、库存和现金字段，以及把白电与更宽合并范围分开的产品/资本边界。现有 J2 cell 是研究问题来源，不是这组字段已经齐备的声明。
4. **共同冲击的来源尚未绑定。** 年报中的各公司叙述可提示需求、材料、渠道迁移或天气等候选冲击，但现有对象没有把一个同 product-arena、同期间的外部冲击观察及其逐 issuer 暴露逐行绑定。因此不能由五份公司年报直接生成共同冲击事实。

这些都是 `DATA_COVERAGE`，不是结果缺失、也不是对任何公司或训练效用的负面判断。

## 4. 同一 Industry Experience Pack 所需的最小字段面

为避免把“同属家电”误写为共同冲击，后续 source package 至少要逐字段保留下列两层。字段是采集请求，不是本审计对其值或传导的判断。

| 层级 | 最小字段 | 每个字段应有的来源属性 | 用途边界 |
| --- | --- | --- | --- |
| 共同冲击 | `shock_id`、发生/观察期间、产品 arena、客户/地域范围、一个可定义的行业需求/供给/材料/渠道条件 | 同期独立静态来源 ID、发布日期、报告期、页码或表格 locator | 只定义共同环境；不替代任何公司的暴露或经营事实 |
| 逐 issuer 暴露 | `issuer_id`、listed-consolidated 与产品责任边界、产品/客户 cohort、对该 `shock_id` 的暴露方向、渠道/交付接口 | 截止日前 CNINFO 来源 ID、发行人、期间、物理页、边界说明 | 证明“谁实际暴露于什么”，不把集团概述当产品层事实 |
| 公司分化：经营传导 | 产品销量、单位成本、库存、应收与回款的同期间序列 | 同一产品、同一责任边界、相同单位和期间定义；逐个 source locator | 用于区分公司传导路径；不能混用集团总额、不同产品或不同期间 |
| 公司分化：范围连续性 | 并购/重组/控制/合并范围桥、白电与非白电拆分、维护与增长性资本投入的责任归属 | 法定披露的事件/年报 source ID、日期、责任单元和 scope bridge | 防止把并表或非白电业务变化重述为白电经营传导 |

J4 的现有边界仍适用：产品 identity、客户群、责任边界和观察钟要先匹配；不同 arena 只能作为机制参考类，不能因名称相近形成同质面板。

## 5. 可执行的下一步（不执行）

1. **补齐 FY2015。** 对五家 issuer 分别取得 FY2015 年报的 CNINFO 公告 ID、公告日、静态 PDF URL 和最小页码 locator；将美的现有 FY2015 lineage 以原 ID 复核，而非重命名或复制其收购语境卡。
2. **补齐格力 FY2017。** 只定位 FY2017 年报的公告 metadata 与静态 PDF，再登记其报告期、公告日、页码和 C2 截止日资格；不以 FY2018 H1 代替，也不读取 FY2018 年报或之后材料。
3. **建立字段级 source receipt。** 按上表的共同冲击、issuer 暴露、经营传导和范围连续性字段，为每个来源写明 `source_id`、发布日期、报告期、责任边界、物理页与缺失处理；相同来源可服务多个字段，但各字段仍保留自己的 locator。
4. **先做产品 arena roster。** 将房间空调与冰洗分别列出；每个成员须有同产品/客户 cohort 与责任边界的来源证明。没有共同字段的发行人保留为 `REFERENCE_CLASS_ONLY`，不以 silence 补成 comparator。

完成这些采集和 receipts 后，才可由 Pack-side compiler 处理来源角色与 maturity；该决定不在本审计权限内。

## 6. 审计结语

现有材料已经精确定位了五家训练侧发行人、五条 J2 经营暴露路线，以及所有五家的 FY2016 与其中四家的 FY2017 CNINFO 静态来源。它同时明确暴露了 FY2015 roster coverage、格力 FY2017 来源和同 arena 字段绑定的 `DATA_COVERAGE` 缺口。审计在此停止：未读取任何 FY2018+ 正文，也未接触价格、回报、估值或结果材料。
