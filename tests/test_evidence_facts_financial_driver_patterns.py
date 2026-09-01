from __future__ import annotations

from pathlib import Path

from scripts.evidence_facts import _verified_observations


def test_cash_normalization_and_allocation_patterns_extract_distinct_facts(tmp_path: Path) -> None:
    (tmp_path / "2025_年报.md").write_text("\n".join([
        "## 第 1 页",
        "合并资产负债表",
        "经营活动产生的现金流量净额 46,383,114,754.02 29,369,250,570.66",
        "购建固定资产、无形资产和其他长期资产支付的现金 1,717,311,068.10 3,299,787,341.22",
        "销售商品、提供劳务收到的现金 180,152,594,833.80 171,937,113,993.38",
        "交易性金融资产 五、2 31,336,448,103.06 16,548,258,632.49",
        "应收账款 15,987,180,598.76 16,831,887,388.06",
        "存货 28,183,464,259.53 27,910,910,515.55",
        "应付账款 42,103,940,920.24 47,091,320,744.05",
        "短期借款 67,956,629,538.51 39,009,527,273.22",
        "合同负债 15,206,576,385.44 12,491,059,928.53",
        "其中：利息费用 1,964,864,912.15 2,378,372,721.06",
        "利息收入 5,885,051,089.40 5,999,412,762.36",
        "消费电器 133,055,208,627.13 86,112,528,829.42 35.28% -10.44% -10.94% 0.37",
        "内销-主营业务 126,407,077,425.42 82,766,067,955.42 34.52% -10.67% -11.05% 0.27",
        "空调 131,712,664,218.81 90,576,252,210.44 31.23% 13.96% 20.14% -3.54%",
        "奥维云网统计数据显示，2025年格力家用空调线上市场零售额占比为24.31%，位居行业第一。",
        "公司利润表",
        "销售费用 5,586,181,281.04 8,139,831,424.59",
        "## 第 177 页",
        "34、合同负债",
        "【注】合同负债主要是预收经销商的货款。",
        "## 第 178 页",
        "40、其他流动负债",
        "销售返利 48,571,252,011.64 49,056,364,849.24",
        "## 第 179 页",
        "57、销售费用",
        "销售费用 五、57 8,410,739,569.54 9,753,022,469.17",
        "## 第 180 页",
        "票据、保函保证金等经营活动有关",
        "受限资金净减少额",
        "15,667,164,024.70",
        "## 第 178 页",
        "货币性投资产品、大额存单、债务",
        "28,454,978,293.91 27,116,400,779.20",
        "工具投资等产品赎回",
        "货币性投资产品、大额存单、债务",
        "61,660,810,246.69 42,427,405,328.01",
        "工具投资等产品支付",
        "定期存款净增加额 24,911,877,903.12 715,596,870.46",
        "## 第 179 页",
        "（4）现金和现金等价物的构成",
        "不属于现金及现金等价物范畴的定期存款及应计利息 72,408,953,590.30 56,614,301,656.50",
        "使用受到限制的存款 10,577,592,111.08 36,145,202,061.32",
        "四、期末现金及现金等价物余额 27,566,460,949.51 21,140,958,080.12",
        "## 第 155 页",
        "在建工程的减值测试情况",
        "格力钛工程 1,425,543,675.40 283,378,372.21 1,142,165,303.19",
    ]), encoding="utf-8")
    document = {"authority": "issuer", "derived_text_path": "2025_年报.md", "period_end": "2025-12-31", "doc_id": "DOC:000651"}

    rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, document)}

    assert round(rows["operating_cash_flow_rmb_m"]["normalized_value"], 6) == 46383.114754
    assert round(rows["cash_capex_rmb_m"]["normalized_value"], 6) == 1717.311068
    assert round(rows["operating_restricted_funds_release_rmb_m"]["normalized_value"], 6) == 15667.164025
    assert round(rows["financial_product_purchases_rmb_m"]["normalized_value"], 6) == 61660.810247
    assert round(rows["financial_product_redemptions_rmb_m"]["normalized_value"], 6) == 28454.978294
    assert round(rows["trading_financial_assets_rmb_m"]["normalized_value"], 6) == 31336.448103
    assert round(rows["gree_titanium_cip_impairment_rmb_m"]["normalized_value"], 6) == 1142.165303
    assert round(rows["cash_and_cash_equivalents_rmb_m"]["normalized_value"], 6) == 27566.460950
    assert round(rows["term_deposits_excluded_from_cash_equivalents_rmb_m"]["normalized_value"], 6) == 72408.953590
    assert round(rows["restricted_monetary_funds_rmb_m"]["normalized_value"], 6) == 10577.592111
    assert round(rows["contract_liabilities_rmb_m"]["normalized_value"], 6) == 15206.576385
    assert rows["contract_liabilities_primary_counterparty"]["normalized_value"] == "dealer_prepayments"
    assert round(rows["sales_rebates_payable_rmb_m"]["normalized_value"], 6) == 48571.252012
    assert round(rows["sales_expense_rmb_m"]["normalized_value"], 6) == 8410.739570
    assert rows["interest_income_rmb_m"]["normalized_value"] > rows["interest_expense_rmb_m"]["normalized_value"]
    assert rows["consumer_electrics_gross_margin_pct"]["normalized_value"] == 35.28
    assert rows["consumer_electrics_revenue_yoy_pct"]["normalized_value"] == -10.44
    assert rows["domestic_main_business_revenue_yoy_pct"]["normalized_value"] == -10.67
    assert rows["air_conditioner_product_gross_margin_pct"]["normalized_value"] == 31.23
    assert rows["air_conditioner_product_revenue_yoy_pct"]["normalized_value"] == 13.96
    assert rows["residential_ac_online_retail_share_pct"]["normalized_value"] == 24.31


def test_cash_equivalents_rules_accept_split_cninfo_table_row_but_not_an_unscoped_mention(tmp_path: Path) -> None:
    (tmp_path / "2024_年报.md").write_text("\n".join([
        "## 第 30 页",
        "四、期末现金及现金等价物余额 999,999,999.99 0.00",
        "使用受到限制的存款 888,888,888.88 0.00",
        "## 第 178 页",
        "（4）现金和现金等价物的构成",
        "不属于现金及现金等价物范",
        "56,614,301,656.50 56,746,121,561.64",
        "畴的定期存款及应计利息",
        "## 第 179 页",
        "使用受到限制的存款 36,145,202,061.32 36,444,669,541.57",
        "四、期末现金及现金等价物余额 21,140,958,080.12 30,914,196,186.41",
    ]), encoding="utf-8")
    document = {"authority": "issuer", "derived_text_path": "2024_年报.md", "period_end": "2024-12-31", "doc_id": "DOC:000651:2024"}

    rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, document)}

    assert round(rows["cash_and_cash_equivalents_rmb_m"]["normalized_value"], 6) == 21140.958080
    assert round(rows["term_deposits_excluded_from_cash_equivalents_rmb_m"]["normalized_value"], 6) == 56614.301656
    assert round(rows["restricted_monetary_funds_rmb_m"]["normalized_value"], 6) == 36145.202061
    assert rows["cash_and_cash_equivalents_rmb_m"]["locator"]["page"] == 179
    assert rows["term_deposits_excluded_from_cash_equivalents_rmb_m"]["locator"]["page"] == 178
    assert rows["restricted_monetary_funds_rmb_m"]["locator"]["page"] == 179


def test_sales_expense_policy_reclassification_stays_separate_from_period_expense(tmp_path: Path) -> None:
    (tmp_path / "2024_年报.md").write_text("\n".join([
        "## 第 77 页",
        "根据解释18号，将保证类质量保证原计入销售费用，现列报于营业成本项目中，并进行追溯调整。",
        "项目 2023年",
        "销售费用 -2,327,937,473.10",
        "营业成本 2,327,937,473.10",
        "## 第 113 页",
        "合并利润表",
        "销售费用 五、57 9,753,022,469.17 14,801,702,209.41",
    ]), encoding="utf-8")
    document = {"authority": "issuer", "derived_text_path": "2024_年报.md", "period_end": "2024-12-31", "doc_id": "DOC:000651:2024"}

    rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, document)}

    assert round(rows["sales_expense_rmb_m"]["normalized_value"], 6) == 9753.022469
    assert round(rows["sales_expense_policy_reclassification_rmb_m"]["normalized_value"], 6) == -2327.937473
    assert rows["sales_expense_policy_reclassification_rmb_m"]["basis"] == "sales_expense_to_operating_cost_policy_reclassification"


def test_operating_restricted_funds_keeps_release_and_addition_directions_separate(tmp_path: Path) -> None:
    (tmp_path / "2023_年报.md").write_text("\n".join([
        "## 第 208 页",
        "收到的其他与经营活动有关的现金",
        "票据质押保证金、保函保证金等净减少额 630,231,744.37",
    ]), encoding="utf-8")
    (tmp_path / "2024_年报.md").write_text("\n".join([
        "## 第 203 页",
        "支付的其他与经营活动有关的现金",
        "票据、保函保证金等经营活动有关",
        "950,809,072.53 5,911,533,582.83",
        "受限资金净增加额",
    ]), encoding="utf-8")
    release_doc = {"authority": "issuer", "derived_text_path": "2023_年报.md", "period_end": "2023-12-31", "doc_id": "DOC:000651:2023"}
    addition_doc = {"authority": "issuer", "derived_text_path": "2024_年报.md", "period_end": "2024-12-31", "doc_id": "DOC:000651:2024"}

    release_rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, release_doc)}
    addition_rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, addition_doc)}

    assert round(release_rows["operating_restricted_funds_release_rmb_m"]["normalized_value"], 6) == 630.231744
    assert "operating_restricted_funds_addition_rmb_m" not in release_rows
    assert round(addition_rows["operating_restricted_funds_addition_rmb_m"]["normalized_value"], 6) == 950.809073
    assert "operating_restricted_funds_release_rmb_m" not in addition_rows


def test_balance_sheet_rules_reject_an_acquisition_table_before_consolidated_statement(tmp_path: Path) -> None:
    (tmp_path / "2024_年报.md").write_text("\n".join([
        "## 第 27 页",
        "收购子公司资产负债表",
        "应收账款 306,347,000.00 0.00",
        "存货 20,200,000.00 0.00",
        "应付账款 37,510,000.00 0.00",
        "短期借款 39,000,000.00 0.00",
        "合同负债 14,000,000.00 0.00",
        "## 第 83 页",
        "合并资产负债表",
        "应收账款 五、4 8,513,334,545.08 7,642,434,078.24 7,699,658,990.16",
        "存货 （七）8 24,084,854,064.29 20,011,518,230.53 20,011,518,230.53",
        "## 第 84 页",
        "合并资产负债表(负债及所有者权益)",
        "应付账款 五、30 41,656,815,752.46 38,987,371,471.02 38,987,371,471.02",
        "短期借款 （七）24 15,944,176,463.01 22,197,899,406.88 22,067,750,002.70",
        "合同负债 五、34 15,206,576,385.44 12,491,059,928.53 11,000,000,000.00",
    ]), encoding="utf-8")
    document = {"authority": "issuer", "derived_text_path": "2024_年报.md", "period_end": "2024-12-31", "doc_id": "DOC:000651:2024"}

    rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, document)}

    assert abs(rows["accounts_receivable_rmb_m"]["normalized_value"] - 8513.33454508) < 1e-6
    assert abs(rows["inventory_rmb_m"]["normalized_value"] - 24084.85406429) < 1e-6
    assert abs(rows["accounts_payable_rmb_m"]["normalized_value"] - 41656.81575246) < 1e-6
    assert abs(rows["short_term_borrowings_rmb_m"]["normalized_value"] - 15944.17646301) < 1e-6
    assert abs(rows["contract_liabilities_rmb_m"]["normalized_value"] - 15206.57638544) < 1e-6
    assert {rows[name]["locator"]["page"] for name in rows if name.endswith("_rmb_m")} >= {83, 84}


def test_residential_ac_channel_and_volume_rules_keep_industry_and_company_scopes_separate(tmp_path: Path) -> None:
    (tmp_path / "2023_年报.md").write_text("\n".join([
        "## 第 10 页",
        "根据产业在线数据，2023年，家用空调生产16,869.2万台，同比增长11.1%，销售17,044.0万台，同比增长11.2%，其中内销出货9,959.7万\n台，同比增长13.8%。",
        "## 第 11 页",
        "根据奥维云网数据，2023年格力品牌家用空调线上零售额份额为28.15%，位居第一。",
        "## 第 14 页",
        "2023年，根据产业在线报告，公司家用空调内销为2,979万台，同比增长4.05%。",
    ]), encoding="utf-8")
    document = {"authority": "issuer", "derived_text_path": "2023_年报.md", "period_end": "2023-12-31", "doc_id": "DOC:000651:2023"}

    rows = {item["fact_name"]: item for item in _verified_observations(tmp_path, document)}

    assert rows["residential_ac_industry_domestic_units_m"]["normalized_value"] == 9959.7
    assert rows["residential_ac_industry_domestic_units_yoy_pct"]["normalized_value"] == 13.8
    assert rows["company_residential_ac_domestic_units_m"]["normalized_value"] == 2979
    assert rows["company_residential_ac_domestic_units_yoy_pct"]["normalized_value"] == 4.05
    assert rows["residential_ac_online_retail_share_pct"]["normalized_value"] == 28.15
    assert rows["residential_ac_industry_domestic_units_m"]["basis"] != rows["company_residential_ac_domestic_units_m"]["basis"]
