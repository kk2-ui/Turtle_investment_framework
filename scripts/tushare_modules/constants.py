"""Turtle Investment Framework - Tushare field mapping constants.

All *_MAP dicts used by TushareClient mixins live here.
"""

_VIP_MAP = {
    "income": "income_vip",
    "balancesheet": "balancesheet_vip",
    "cashflow": "cashflow_vip",
    "fina_indicator": "fina_indicator_vip",
    "fina_mainbz": "fina_mainbz_vip",
    "forecast": "forecast_vip",
    "express": "express_vip",
}

# HK line-item field mappings: Tushare column name → HK ind_name (Chinese)
HK_INCOME_MAP = {
    "revenue": "营业额",
    "oper_cost": "营运支出",
    "sell_exp": "销售及分销费用",
    "admin_exp": "行政开支",
    "operate_profit": "经营溢利",
    "invest_income": "应占联营公司溢利",
    "int_income": "利息收入",
    "finance_exp": "融资成本",
    "total_profit": "除税前溢利",
    "income_tax": "税项",
    "n_income": "除税后溢利",
    "n_income_attr_p": "股东应占溢利",
    "minority_gain": "少数股东损益",
    "basic_eps": "每股基本盈利",
    "diluted_eps": "每股摊薄盈利",
}

HK_BALANCE_MAP = {
    "money_cap": "现金及等价物",
    "accounts_receiv": "应收帐款",
    "inventories": "存货",
    "total_cur_assets": "流动资产合计",
    "lt_eqt_invest": "联营公司权益",
    "fix_assets": "物业厂房及设备",
    "cip": "在建工程",
    "intang_assets": "无形资产",
    "total_assets": "总资产",
    "acct_payable": "应付帐款",
    "notes_payable": "应付票据",
    "contract_liab": "递延收入(流动)",
    "st_borr": "短期贷款",
    "total_cur_liab": "流动负债合计",
    "lt_borr": "长期贷款",
    "bond_payable": "应付票据(非流动)",
    "total_liab": "总负债",
    "defer_tax_assets": "递延税项资产",
    "defer_tax_liab": "递延税项负债",
    "total_hldr_eqy_exc_min_int": "股东权益",
    "minority_int": "少数股东权益",
}

HK_CASHFLOW_MAP = {
    "n_cashflow_act": "经营业务现金净额",
    "n_cashflow_inv_act": "投资业务现金净额",
    "n_cash_flows_fnc_act": "融资业务现金净额",
    "c_pay_acq_const_fiolta": "购建无形资产及其他资产",
    "depr_fa_coga_dpba": "折旧及摊销",
    "c_pay_dist_dpcp_int_exp": "已付股息(融资)",
    "c_paid_for_taxes": "已付税项",
    "c_recp_return_invest": "收回投资所得现金",
}

# ── Reverse mappings: HK Chinese ind_name → DB field name ──
# Used by rebuild_hk_data.py and tushare_modules to pivot LONG-format CSV data.
# Each DB field can have multiple Chinese aliases (different companies use different terms).

HK_INCOME_NAME_TO_FIELD = {
    # 营业收入
    "营业额": "revenue",
    "营运收入": "revenue",
    "营业收入": "revenue",
    # 营业成本
    "销售成本": "oper_cost",
    "营运支出": "oper_cost",
    "营业成本": "oper_cost",
    # 毛利
    "毛利": "gross_profit",
    # 归母净利润
    "股东应占溢利": "n_income_attr_p",
    "除税后溢利": "n_income_attr_p",
    "本公司拥有人应占全面收益总额": "n_income_attr_p",
    "持续经营业务税后利润": "n_income_attr_p",
    # 少数股东损益
    "少数股东损益": "minority_profit",
    "非控股权益应占全面收益总额": "minority_profit",
    # 税前利润
    "除税前溢利": "pretax_profit",
    # 所得税
    "税项": "income_tax",
    # 员工成本 (HK: 薪金福利支出是最常见的术语, 8,574行)
    "员工成本": "employee_cost",
    "员工薪酬": "employee_cost",
    "薪金福利支出": "employee_cost",
    "雇员福利支出": "employee_cost",
    "员工福利支出": "employee_cost",
    "僱員福利支出": "employee_cost",
    "僱員成本": "employee_cost",
    "职工薪酬": "employee_cost",
    "薪酬总额": "employee_cost",
    "员工费用": "employee_cost",
    "僱員費用": "employee_cost",
    "人工成本": "employee_cost",
    "劳工成本": "employee_cost",
    "staff cost": "employee_cost",
    "staff costs": "employee_cost",
    "employee benefit expense": "employee_cost",
    "employee benefits expense": "employee_cost",
    "personnel expenses": "employee_cost",
    "salaries and wages": "employee_cost",
    "salaries, wages and benefits": "employee_cost",
    # 折旧摊销
    "折旧与摊销": "d_a",
    "折旧及摊销": "d_a",
    # 每股收益
    "每股基本盈利": "eps",
    "每股摊薄盈利": "eps_diluted",
    # 经营利润
    "经营溢利": "operate_profit",
    # 费用
    "销售及分销费用": "sell_exp",
    "行政开支": "admin_exp",
    "研发费用": "rd_exp",
    "融资成本": "finance_exp",
    # 其他
    "利息收入": "int_income",
    "应占联营公司溢利": "invest_income",
    "应占合营公司溢利": "jv_income",
    "其他收入": "other_income",
    "其他收益": "other_income",
    "其他收入": "other_income",
    "其他支出": "other_expense",
    # 政府补助
    "政府补助": "gov_subsidy",
    "政府补贴": "gov_subsidy",
    "政府资助": "gov_subsidy",
    "政府拨款": "gov_subsidy",
    "减值及拨备": "impairment",
    "重估盈余": "revaluation_surplus",
    "全面收益总额": "total_comprehensive_income",
    "非运算项目": "non_operating_items",
    # OCI decomposition (important for quality check — can be large)
    "其他全面收益": "other_comprehensive_income",
    "其他全面收益其他项目": "oci_other_items",
    "本公司拥有人应占全面收益总额": "tci_attr_parent",
    "非控股权益应占全面收益总额": "tci_attr_minority",
    "优先股股东应占全面收益总额": "tci_attr_preferred",
    "永久资本证券持有人应占全面收益总额": "tci_attr_perpetual",
    "全面收益其他项目": "tci_other_items",
}

HK_BS_NAME_TO_FIELD = {
    # 现金
    "现金及等价物": "money_cap",
    "现金及现金等价物": "money_cap",
    "受限制存款及现金": "cash_broad",
    "短期存款": "short_term_deposits",
    "定期存款": "time_deposits",
    "中长期存款": "time_deposits",
    # 短期投资
    "短期投资": "short_term_investments",
    "交易用途资产": "short_term_investments",
    "交易性金融资产": "trading_fin_assets",
    # 应收应付
    "应收帐款": "accounts_receiv",
    "应收账款及票据": "accounts_receiv",
    "应付帐款": "acct_payable",
    "应付账款及票据": "acct_payable",
    "应付票据": "notes_payable",
    "应付税项": "tax_payable",
    # 合同负债
    "合同负债": "contract_liab",
    "递延收入(流动)": "contract_liab",
    "递延收入(非流动)": "defer_income_non_current",
    # 存货
    "存货": "inventories",
    # 资产总计
    "总资产": "total_assets",
    "资产总计": "total_assets",
    # 负债总计
    "总负债": "total_liab",
    "负债总计": "total_liab",
    # 权益
    "股东权益": "total_hldr_eqy_exc_min_int",
    "总权益": "total_hldr_eqy_exc_min_int",
    "净资产": "total_hldr_eqy_exc_min_int",
    "本公司拥有人应占权益": "total_hldr_eqy_exc_min_int",
    "少数股东权益": "minority_int",
    "非控股权益": "minority_int",
    # 商誉
    "商誉": "goodwill",
    # 借款
    "短期贷款": "st_borr",
    "短期借款": "st_borr",
    "长期贷款": "lt_borr",
    "长期借款": "lt_borr",
    # 固定资产
    "物业厂房及设备": "fix_assets",
    "固定资产": "fix_assets",
    "无形资产": "intang_assets",
    "在建工程": "cip",
    "长期待摊费用": "deferred_assets",
    "递延资产": "deferred_assets",
    "专项储备": "special_reserve",
    "法定储备": "special_reserve",
    "法定公积金": "special_reserve",
    "公积金": "special_reserve",
    "法定盈余公积": "special_reserve",
    "任意盈余公积": "special_reserve",
    "一般风险准备": "special_reserve",
    "statutory reserve": "special_reserve",
    "statutory reserves": "special_reserve",
    "legal reserve": "special_reserve",
    # 投资
    "联营公司权益": "lt_eqt_invest",
    "合营公司权益": "jv_invest",
    "投资物业": "investment_properties",
    # 递延税项
    "递延税项资产": "defer_tax_assets",
    "递延税项负债": "defer_tax_liab",
    # 汇总项
    "流动资产合计": "total_cur_assets",
    "流动负债合计": "total_cur_liab",
    "非流动资产合计": "total_non_cur_assets",
    "非流动负债合计": "total_non_cur_liab",
    # 其他
    "股本": "share_capital",
    "储备": "reserves",
    "保留溢利(累计亏损)": "retained_earnings",
    "预付款按金及其他应收款": "prepayments_and_other_receivables",
    "预付款项": "prepayments",
    "合同资产": "contract_assets",
    "融资租赁负债(流动)": "lease_liab_current",
    "融资租赁负债(非流动)": "lease_liab_non_current",
    "长期应付款": "long_term_payables",
    "长期应收款": "long_term_receivables",
    "指定以公允价值记账之金融资产": "fv_financial_assets",
    "指定以公允价值记账之金融资产(流动)": "fv_financial_assets_current",
    "衍生金融工具-负债": "derivative_financial_liab",
}

HK_CF_NAME_TO_FIELD = {
    # 经营活动
    "经营业务现金净额": "n_cashflow_act",
    "经营活动现金净额": "n_cashflow_act",
    "经营产生现金": "cash_from_operations",
    # 投资活动
    "投资业务现金净额": "n_cashflow_inv_act",
    "投资活动现金净额": "n_cashflow_inv_act",
    # 融资活动
    "融资业务现金净额": "n_cash_flows_fnc_act",
    "融资活动现金净额": "n_cash_flows_fnc_act",
    # 资本支出
    "购建固定资产": "c_pay_acq_const_fiolta",
    "购建无形资产及其他资产": "c_pay_acq_const_fiolta",
    "资本支出": "c_pay_acq_const_fiolta",
    # 折旧摊销(CF口径)
    "折旧及摊销": "d_a_cf",
    "加:折旧及摊销": "d_a_cf",
    # 股息
    "已付股息(融资)": "dividends_paid",
    "已付股息": "dividends_paid",
    # 税项
    "已付税项": "tax_paid",
    "已付利息(融资)": "interest_paid",
    "已收利息(投资)": "interest_received_inv",
    "已收利息(经营)": "interest_received_oper",
    "已收股息(投资)": "dividends_received_inv",
    # 借款
    "新增借款": "new_borrowings",
    "偿还借款": "loan_repayments",
    "偿还融资租赁": "lease_repayments",
    # 投资
    "收回投资所得现金": "c_recp_return_invest",
    "投资支付现金": "invest_payments",
    "处置固定资产": "disposal_fixed_assets",
    "收购附属公司": "acquisition_subsidiaries",
    "出售附属公司": "disposal_subsidiaries",
    # 其他
    "融资前现金净额": "net_cash_before_financing",
    "现金净额": "net_cash_change",
    "期末现金": "cash_end",
    "期初现金": "cash_beginning",
    "营运资金变动前经营溢利": "operating_profit_before_wc_changes",
    "除税前溢利(业务利润)": "pretax_profit_operating",
    # Working capital changes (for cash flow quality analysis)
    "应收帐款减少": "ar_decrease",
    "应收票据(增加)减少": "notes_receivable_change",
    "存货(增加)减少": "inventory_change",
    "应付帐款及应计费用增加(减少)": "ap_increase",
    "预付款项、按金及其他应收款项减少(增加)": "prepayments_change",
    "预收账款、按金及其他应付款增加(减少)": "advance_from_customers_change",
    "应付关联方款项增加(减少)": "related_party_payables_change",
    "应收关联方款项(增加)减少": "related_party_receivables_change",
    "营运资本变动其他项目": "wc_other_changes",
    # Non-cash adjustments (for OCF quality)
    "加:减值及拨备": "add_impairment",
    "加:利息支出": "add_interest_expense",
    "减:利息收入": "less_interest_income",
    "减:出售资产之溢利": "less_gain_on_asset_sale",
    "减:重估盈余": "less_revaluation_surplus",
    "减:应占附属公司溢利": "less_share_of_subsidiary_profit",
    "减:汇兑收益": "less_exchange_gain",
    "减:投资收益": "less_investment_income",
    "加:经营调整其他项目": "add_other_operating_adjustments",
    "非运算项目": "cf_non_operating_items",
    "期间变动其他项目": "cf_period_change_other",
    # Borrowing detail
    "发行股份": "share_issuance",
    "吸收投资所得": "investment_received",
}

# ── fina_indicator column → DB field mapping ──
# Maps Tushare hk_fina_indicator CSV columns to annual_financials fields.

FI_COLUMN_TO_FIELD = {
    "operate_income": "revenue",
    "gross_profit": "gross_profit",
    "holder_profit": "n_income_attr_p",
    "operate_profit": "pretax_profit",
    "pretax_profit": "pretax_profit",
    "total_assets": "total_assets",
    "total_liabilities": "total_liab",
    "total_parent_equity": "total_hldr_eqy_exc_min_int",
    "basic_eps": "eps",
    "diluted_eps": "eps_diluted",
    "dps_hkd": "dps",
    # "dps_hkd_ly": removed — prior-year DPS must not overwrite current-year DPS
    # (interim DPS is accumulated in build_records)
    "netcash_operate": "n_cashflow_act",
    "netcash_invest": "n_cashflow_inv_act",
    "netcash_finance": "n_cash_flows_fnc_act",
    "gross_profit_ratio": "gross_margin",
    "roe_avg": "roe",
    "roa": "roa",
    "debt_asset_ratio": "debt_ratio",
    "total_market_cap": "market_cap",
    "hksk_market_cap": "market_cap_hk",
    "pe_ttm": "pe",
    "pb_ttm": "pb",
    "current_ratio": "current_ratio",
    "ocf_sales": "ocf_to_sales",
    "tax_ebt": "tax_rate",
    "per_netcash_operate": "ocf_per_share",
    "per_oi": "operate_income_per_share",
    "bps": "book_value_per_share",
    "operate_income_yoy": "revenue_yoy",
    "holder_profit_yoy": "np_yoy",
    "gross_profit_yoy": "gp_yoy",
    # ── Additional critical indicators ──
    "roe_yearly": "roe",
    "roic_yearly": "roic",
    "net_profit_ratio": "net_margin",
    "eps_ttm": "eps_ttm",
    "divi_ratio": "dividend_payout_ratio",
    "dividend_rate": "dividend_yield",
    "equity_ratio": "equity_ratio",
    "equity_multiplier": "equity_multiplier",
    "currentdebt_debt": "short_term_debt_ratio",
    # ── Share structure (for stocks table population) ──
    "issued_common_shares": "issued_common_shares",
    "hk_common_shares": "hk_common_shares",
    "per_shares": "lot_size",
    # ── Bank/Insurance specific (essential for financial stock analysis) ──
    "premium_income": "premium_income",
    "premium_income_yoy": "premium_income_yoy",
    "premium_expense": "premium_expense",
    "net_interest_income": "net_interest_income",
    "net_interest_income_yoy": "net_interest_income_yoy",
    "fee_commission_income": "fee_commission_income",
    "fee_commission_income_yoy": "fee_commission_income_yoy",
    "loan_deposit": "loan_deposit_ratio",
    "loan_equity": "loan_equity_ratio",
    "loan_assets": "loan_assets_ratio",
    "deposit_equity": "deposit_equity_ratio",
    "deposit_assets": "deposit_assets_ratio",
    # ── Turnover days (operational efficiency) ──
    "accounts_rece_tdays": "ar_turnover_days",
    "inventory_tdays": "inventory_turnover_days",
    "current_assets_tdays": "ca_turnover_days",
    "total_assets_tdays": "asset_turnover_days",
    # ── Single-quarter metrics (different from cumulative YTD) ──
    "operate_income_sq": "revenue_single_q",
    "operate_income_qoq": "revenue_qoq",
    "operate_income_qoq_sq": "revenue_qoq_single_q",
    "holder_profit_sq": "np_single_q",
    "holder_profit_qoq": "np_qoq",
    "holder_profit_qoq_sq": "np_qoq_single_q",
    "gross_profit_qoq": "gp_qoq",
    "net_profit_ratio_sq": "net_margin_single_q",
    "roe_avg_sq": "roe_single_q",
    "roa_sq": "roa_single_q",
    "pe_ttm_sq": "pe_ttm_single_q",
    "pb_ttm_sq": "pb_single_q",
}

# US line-item field mappings: Tushare column name → US ind_name (Chinese)
US_INCOME_MAP = {
    "revenue": "营业收入",
    "oper_cost": "营业成本",
    "gross_profit": "毛利",
    "sell_exp": "营销费用",
    "rd_exp": "研发费用",
    "operate_profit": "经营利润",
    "n_income": "净利润",
    "n_income_attr_p": "归属于母公司净利润",
    "basic_eps": "基本每股收益",
    "diluted_eps": "稀释每股收益",
}

US_BALANCE_MAP = {
    "money_cap": "现金及等价物",
    "accounts_receiv": "应收帐款",
    "inventories": "存货",
    "total_cur_assets": "流动资产合计",
    "fix_assets": "固定资产",
    "intang_assets": "无形资产",
    "total_assets": "总资产",
    "acct_payable": "应付帐款",
    "st_borr": "短期贷款",
    "total_cur_liab": "流动负债合计",
    "lt_borr": "长期贷款",
    "total_liab": "总负债",
    "defer_tax_assets": "递延税项资产",
    "defer_tax_liab": "递延税项负债",
    "total_hldr_eqy_exc_min_int": "股东权益",
    "minority_int": "少数股东权益",
    "goodwill": "商誉",
    "trad_asset": "交易性金融资产",
}

US_CASHFLOW_MAP = {
    "n_cashflow_act": "经营活动现金净额",
    "n_cashflow_inv_act": "投资活动现金净额",
    "n_cash_flows_fnc_act": "筹资活动现金净额",
    "c_pay_acq_const_fiolta": "资本支出",
    "depr_fa_coga_dpba": "折旧及摊销",
    "c_pay_dist_dpcp_int_exp": "已付股息",
}

# yfinance field mappings: yfinance index name → Tushare column name
# Both CamelCase and space-separated variants included (format varies by yfinance version)
_YF_INCOME_MAP = {
    "Total Revenue": "revenue", "TotalRevenue": "revenue",
    "Cost Of Revenue": "oper_cost", "CostOfRevenue": "oper_cost",
    "Selling General And Administration": "admin_exp",
    "SellingGeneralAndAdministration": "admin_exp",
    "Operating Income": "operate_profit", "OperatingIncome": "operate_profit",
    "Interest Expense": "finance_exp", "InterestExpense": "finance_exp",
    "Pretax Income": "total_profit", "PretaxIncome": "total_profit",
    "Tax Provision": "income_tax", "TaxProvision": "income_tax",
    "Net Income": "n_income", "NetIncome": "n_income",
    "Net Income Common Stockholders": "n_income_attr_p",
    "NetIncomeCommonStockholders": "n_income_attr_p",
    "Basic EPS": "basic_eps", "BasicEPS": "basic_eps",
    "Diluted EPS": "diluted_eps", "DilutedEPS": "diluted_eps",
    "Gross Profit": "gross_profit", "GrossProfit": "gross_profit",
    "Research And Development": "rd_exp", "ResearchAndDevelopment": "rd_exp",
}

_YF_BALANCE_MAP = {
    "Cash And Cash Equivalents": "money_cap",
    "CashAndCashEquivalents": "money_cap",
    "Accounts Receivable": "accounts_receiv", "AccountsReceivable": "accounts_receiv",
    "Inventory": "inventories",
    "Current Assets": "total_cur_assets", "CurrentAssets": "total_cur_assets",
    "Investments And Advances": "lt_eqt_invest",
    "Net PPE": "fix_assets", "NetPPE": "fix_assets",
    "Goodwill And Other Intangible Assets": "intang_assets",
    "Total Assets": "total_assets", "TotalAssets": "total_assets",
    "Accounts Payable": "acct_payable", "AccountsPayable": "acct_payable",
    "Current Debt": "st_borr", "CurrentDebt": "st_borr",
    "Current Liabilities": "total_cur_liab", "CurrentLiabilities": "total_cur_liab",
    "Long Term Debt": "lt_borr", "LongTermDebt": "lt_borr",
    "Total Liabilities Net Minority Interest": "total_liab",
    "Stockholders Equity": "total_hldr_eqy_exc_min_int",
    "StockholdersEquity": "total_hldr_eqy_exc_min_int",
    "Minority Interest": "minority_int", "MinorityInterest": "minority_int",
    "Goodwill": "goodwill",
    "Other Short Term Investments": "trad_asset", "OtherShortTermInvestments": "trad_asset",
}

_YF_CASHFLOW_MAP = {
    "Operating Cash Flow": "n_cashflow_act", "OperatingCashFlow": "n_cashflow_act",
    "Investing Cash Flow": "n_cashflow_inv_act", "InvestingCashFlow": "n_cashflow_inv_act",
    "Financing Cash Flow": "n_cash_flows_fnc_act", "FinancingCashFlow": "n_cash_flows_fnc_act",
    "Capital Expenditure": "c_pay_acq_const_fiolta", "CapitalExpenditure": "c_pay_acq_const_fiolta",
    "Depreciation And Amortization": "depr_fa_coga_dpba",
    "DepreciationAndAmortization": "depr_fa_coga_dpba",
    "Common Stock Dividend Paid": "c_pay_dist_dpcp_int_exp",
    "Income Tax Paid Supplemental Data": "c_paid_for_taxes",
    "Sale Of Investment": "c_recp_return_invest",
}
