"""Focused regression tests for Codex workflow assembly helpers."""

from pathlib import Path

from codex_workflow import (
    business_handoff_content,
    build_composite_benchmark_table,
    build_cash_quality_audit_sections,
    build_fallback_absolute_valuation,
    build_historical_quantile_table,
    build_dip_buy_strategy_section,
    build_wacc_assumption,
    annual_core_dividend_report_snippet,
    calc_dps_growth_tiers,
    choose_ddm_growth_assumption,
    choose_g_coefficient,
    compute_threshold_price_crosscheck,
    executive_summary_assumption_sentence,
    ensure_interim_report_requirement,
    ensure_recent_annual_report_coverage,
    latest_h1_year_from_market_pack,
    tax_scenarios_for_listing_structure,
    compute_aa_cash_audit,
    extract_annual_capex_da_series,
    extract_annual_dividend_dps_points_from_output,
    extract_markdown_tables,
    infer_listing_structure_from_output,
    infer_turtle_recommendation,
    resolve_current_market_snapshot,
    resolve_rf_pct_for_report,
    _extract_dps_series_with_source,
    _extract_latest_dps,
    _extract_latest_payout_ratio,
    _extract_share_count_from_text,
    split_table_rows,
    turtle_report_scaffold,
    workflow_tax_context,
    nci_dividend_alert,
    _dps_cagr_basis,
)
from turtle_thresholds import ThresholdProfile
from turtle_thresholds import classify_threshold_profile


def test_extract_markdown_tables_keeps_last_row_and_splits_adjacent_tables():
    text = """
| 年份 | 值 |
| --- | ---: |
| 2025 | 1 |
| 2024 | 2 |

| 变量 | 值 | 说明 |
| --- | ---: | --- |
| M | 36.10% | 基于3年 |
""".strip()

    tables = extract_markdown_tables(text)

    assert len(tables) == 2
    assert "| 2024 | 2 |" in tables[0]
    assert "| M | 36.10% | 基于3年 |" in tables[1]


def test_extract_latest_dps_handles_blank_line_after_table_header():
    text = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) | |

| 2025 | 0.1660 | 49.25 | |
| 2024 | 0.1660 | 49.97 | |

## 7. 股东与治理
""".strip()

    assert _extract_latest_dps(text) == 0.1660


def test_extract_latest_payout_ratio_reads_first_dividend_row():
    text = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.60 |
| 2024 | 0.1600 | 49.00 |
""".strip()

    assert _extract_latest_payout_ratio(text) == 0.496


def test_calc_dps_growth_tiers_uses_rule_node_not_ad_hoc_caps():
    tiers = calc_dps_growth_tiers(
        dps_cagr=0.033,
        minority_ratio=0.396,
        decay_factor=0.7,
        industry_ceiling=0.023,
        current_payout=0.496,
        hold_years=3,
        source_label="DPS CAGR 3.3%",
    )

    assert abs(float(tiers["pess"]) - 0.00697) < 0.0001
    assert abs(float(tiers["base"]) - 0.01395) < 0.0001
    assert abs(float(tiers["opt"]) - 0.02092) < 0.0001
    expected_release = ((0.596 / 0.496) ** (1.0 / 3) - 1.0) * 0.30
    assert abs(float(tiers["payout_release"]) - expected_release) < 0.0001
    assert "派息率释放" in str(tiers["basis"])


def test_calc_dps_growth_tiers_falls_back_without_payout_release():
    tiers = calc_dps_growth_tiers(
        dps_cagr=0.03,
        minority_ratio=None,
        decay_factor=0.7,
        industry_ceiling=0.023,
        current_payout=None,
    )

    assert abs(float(tiers["base"]) - 0.021) < 0.0001
    assert abs(float(tiers["opt"]) - 0.0276) < 0.0001
    assert tiers["payout_release"] is None


def test_calc_dps_growth_tiers_caps_target_payout_at_70pct():
    tiers = calc_dps_growth_tiers(
        dps_cagr=0.02,
        minority_ratio=None,
        decay_factor=1.0,
        industry_ceiling=0.05,
        current_payout=0.68,
        target_payout=None,
        hold_years=3,
    )

    expected_release = ((0.70 / 0.68) ** (1.0 / 3) - 1.0) * 0.30
    assert abs(float(tiers["payout_release"]) - expected_release) < 0.0001
    assert "70.0%/68.0%" in str(tiers["basis"])


def test_g_coefficient_missing_f_defaults_to_neutral_one():
    assert choose_g_coefficient(None) == 1.00
    assert choose_g_coefficient(1.05) == 1.00
    assert choose_g_coefficient(1.20) == 1.20
    assert choose_g_coefficient(1.60) == 1.40


def test_recommendation_uses_gg_vs_ii_as_primary_rule():
    assert infer_turtle_recommendation(6.48, 6.00, 0.48, "中") == "买入"
    assert infer_turtle_recommendation(5.76, 6.00, -0.24, "中") == "观察"
    assert infer_turtle_recommendation(5.00, 6.00, -1.00, "高") == "排除"


def test_rf_resolver_never_returns_zero_when_missing():
    rf, source = resolve_rf_pct_for_report(ts_code="00506.HK", data_pack_text="", candidate=0.0)
    assert rf == 3.60
    assert "香港" in source


def test_extract_annual_capex_da_series_reads_latest_annual_sections(tmp_path):
    snippets = {
        2023: """
Depreciation of property, plant and equipment 756,615
Depreciation of right-of-use assets 78,873
Amortisation of intangible assets 14,276
Payments for property, plant and equipment (627,469)
Payments for intangible assets (20,240)
""",
        2024: """
Depreciation of property, plant and equipment 769,131
Depreciation of right-of-use assets 69,962
Amortisation of intangible assets 17,442
Payments for property, plant and equipment (712,424)
Payments for right-of-use assets (50,143)
Payments for intangible assets (12,067)
""",
        2025: """
Depreciation of property, plant and equipment 807,383
Depreciation of right-of-use assets 64,948
Amortisation of intangible assets 21,234
Payments for property, plant and equipment (1,048,816)
Payments for intangible assets (11,699)
""",
    }
    for year, text in snippets.items():
        (tmp_path / f"pdf_sections_{year}.json").write_text(text, encoding="utf-8")

    series, source = extract_annual_capex_da_series(tmp_path)
    ratios = {int(item["year"]): float(item["ratio"]) for item in series}

    assert "2023-2025" in source
    assert sorted(ratios, reverse=True) == [2025, 2024, 2023]
    assert abs(ratios[2025] - (1060515 / 893565)) < 0.001
    assert abs(ratios[2024] - (774634 / 856535)) < 0.001
    assert abs(ratios[2023] - (647709 / 849764)) < 0.001


def test_annual_report_coverage_targets_five_years_and_flags_missing(tmp_path):
    for year in [2021, 2023, 2025]:
        (tmp_path / f"00506_{year}_年报.pdf").write_bytes(b"%PDF-1.4\n")

    coverage = ensure_recent_annual_report_coverage(
        tmp_path,
        "00506.HK",
        2025,
        lookback_years=5,
        minimum_years=3,
    )

    assert coverage.target_years == [2021, 2022, 2023, 2024, 2025]
    assert coverage.found_years == [2021, 2023, 2025]
    assert coverage.missing_years == [2022, 2024]
    assert coverage.has_minimum_coverage
    assert not coverage.is_target_complete
    assert "未满 5 年但达到最低 3 年" in coverage.markdown_summary()


def test_business_handoff_requires_five_year_annual_reports_and_downgrades_under_three(tmp_path):
    (tmp_path / "00506_2025_年报.pdf").write_bytes(b"%PDF-1.4\n")
    coverage = ensure_recent_annual_report_coverage(
        tmp_path,
        "00506.HK",
        2025,
        lookback_years=5,
        minimum_years=3,
    )

    content = business_handoff_content(
        "00506.HK",
        tmp_path,
        tmp_path / "00506_2025_年报.pdf",
        coverage.found,
        annual_coverage=coverage,
    )

    assert "默认先补齐最近 5 个完整年度年报" in content
    assert "覆盖不足 3 年" in content
    assert "待补年报：2021、2022、2023、2024 年年报" in content
    assert "DPS CAGR、Capex/D&A 五年中位数、现金审计与治理轨迹必须降级标注" in content


def test_interim_requirement_triggers_from_h1_market_pack_and_flags_missing(tmp_path):
    data_pack = tmp_path / "data_pack_market.md"
    data_pack.write_text(
        """
| 指标 | 2025H1 | 2024 |
| --- | ---: | ---: |
| 收入 | 100 | 180 |
""",
        encoding="utf-8",
    )

    assert latest_h1_year_from_market_pack(data_pack) == 2025

    requirement = ensure_interim_report_requirement("00506.HK", tmp_path, data_pack)

    assert requirement.required
    assert requirement.year == 2025
    assert requirement.pdf is None
    assert not requirement.is_satisfied
    assert "最新经营、应收、现金、分红与MD&A时效性降级" in requirement.markdown_summary()


def test_interim_requirement_uses_local_interim_pdf(tmp_path):
    data_pack = tmp_path / "data_pack_market.md"
    data_pack.write_text("| 指标 | 2025H1 | 2024 |\n| --- | ---: | ---: |\n", encoding="utf-8")
    interim_pdf = tmp_path / "00506_2025_中报.pdf"
    interim_pdf.write_bytes(b"%PDF-1.4\n")

    requirement = ensure_interim_report_requirement("00506.HK", tmp_path, data_pack)

    assert requirement.required
    assert requirement.is_satisfied
    assert requirement.pdf == interim_pdf.resolve()
    assert "最新中报已就位" in requirement.markdown_summary()


def test_business_handoff_requires_interim_when_h1_exists(tmp_path):
    coverage = ensure_recent_annual_report_coverage(
        tmp_path,
        "00506.HK",
        2025,
        lookback_years=5,
        minimum_years=3,
    )
    data_pack = tmp_path / "data_pack_market.md"
    data_pack.write_text("| 指标 | 2025H1 | 2024 |\n| --- | ---: | ---: |\n", encoding="utf-8")
    interim_requirement = ensure_interim_report_requirement("00506.HK", tmp_path, data_pack)

    content = business_handoff_content(
        "00506.HK",
        tmp_path,
        None,
        coverage.found,
        annual_coverage=coverage,
        interim_requirement=interim_requirement,
    )

    assert "待补中报：最新中报 PDF" in content
    assert "若 `data_pack_market.md` 含 H1 列，必须下载并处理对应中报" in content
    assert "最新经营、应收、现金、分红与MD&A时效性必须降级标注" in content


def test_extract_annual_dividend_dps_points_uses_all_available_pdf_sections(tmp_path):
    share_text = """
Issued and fully paid 2,797,223,396 ordinary shares
"""
    snippets = {
        2025: "Dividends paid 已付股息 (427,608) (413,989)\nDividends paid to non-controlling interests (1,149,440) (90,201)",
        2023: "Dividends paid 已付股息 (391,000) (377,000)\nDividends paid to non-controlling interests (80,000) (70,000)",
        2021: "Dividends paid 已付股息 (350,000) (330,000)\nDividends paid to non-controlling interests (60,000) (50,000)",
    }
    for year, text in snippets.items():
        (tmp_path / f"pdf_sections_{year}.json").write_text(share_text + text, encoding="utf-8")

    points, source = extract_annual_dividend_dps_points_from_output(
        tmp_path,
        latest_market_dps=0.1660,
        max_years=5,
    )

    assert sorted(points) == [2021, 2022, 2023, 2024, 2025]
    assert "5年" in source
    assert abs(points[2025] - 0.1660) < 0.0001


def test_extract_annual_dividend_dps_points_prefers_declared_dps_notes(tmp_path):
    share_text = "Issued and fully paid 2,797,223,396 ordinary shares\n"
    snippets = {
        2021: "Subsequent to the end of the reporting period, a final dividend in respect of the year ended 31 December 2021 of HKD12.5 cents (2020: HKD10.6 cents) per ordinary share has been proposed.",
        2022: "Subsequent to the end of the reporting period, a final dividend in respect of the year ended 31 December 2022 of HK13.3 cents (2021: HK12.5 cents) per ordinary share has been proposed.",
        2023: "Subsequent to the end of the reporting period, a final dividend in respect of the year ended 31 December 2023 of RMB0.148 per ordinary share has been proposed.",
        2024: "Subsequent to the end of the reporting period, a final dividend in respect of the year ended 31 December 2024 of RMB0.153 per ordinary share has been proposed.",
        2025: "Subsequent to the end of the reporting period, a final dividend in respect of the year ended 31 December 2025 of RMB0.154 (2024: RMB0.153) per ordinary share has been proposed.",
    }
    for year, text in snippets.items():
        (tmp_path / f"pdf_sections_{year}.json").write_text(share_text + text, encoding="utf-8")

    points, source = extract_annual_dividend_dps_points_from_output(
        tmp_path,
        latest_market_dps=0.1660,
        max_years=5,
    )

    assert sorted(points) == [2021, 2022, 2023, 2024, 2025]
    assert "年报末期/普通股股息拆分" in source
    assert "5年" in source
    assert abs(points[2021] - 0.1250) < 0.0001
    assert abs(points[2022] - 0.1330) < 0.0001
    assert abs(points[2025] - 0.1660) < 0.0001


def test_dps_cagr_basis_uses_annual_report_3y_or_more_and_warns_for_short_samples():
    report_pack = """
| 项目 | 2025 | 2024 | 2023 | 2022 |
| --- | ---: | ---: | ---: | ---: |
| 已付普通股东股息 | -166.0 | -160.0 | -153.0 | -149.0 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
"""
    cagr, source, basis = _dps_cagr_basis("", report_pack)

    assert cagr is not None
    assert "2022 DPS 0.1490 → 报告期2025 DPS 0.1660，3 年 CAGR" in basis
    assert "仅2年数据" not in basis
    assert "仅" not in basis
    assert "年报普通股股息/股本反推" in source

    one_year_pack = """
| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 已付普通股东股息 | -166.0 | -160.0 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
"""
    _cagr, _source, one_year_basis = _dps_cagr_basis("", one_year_pack)
    assert "DPS 单年增长率" in one_year_basis
    assert "1 年单年增长率" in one_year_basis
    assert "1 年 CAGR" not in one_year_basis


def test_threshold_price_crosscheck_uses_aa_and_dps_paths():
    result = compute_threshold_price_crosscheck(
        aa_base=1356.8,
        payout_anchor_pct=49.61,
        q_pct=10.0,
        ii_pct=6.0,
        total_shares=2797.223,
        latest_dps=0.166,
    )

    assert abs(float(result["aa_price"]) - 3.61) < 0.02
    assert abs(float(result["dps_price"]) - 2.49) < 0.02
    assert result["selected_price"] == result["aa_price"]
    assert float(result["gap_pct"]) > 30.0
    assert "AA 与 DPS 背离" in str(result["warning"])
    assert "取较高者" in str(result["note"])


def test_dps_growth_soe_consumer_policy_uses_explicit_payout_release():
    data_pack = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.6 |
| 2024 | 0.1606 | 49.6 |
| 2023 | 0.1556 | 49.6 |
""".strip()

    result = choose_ddm_growth_assumption(
        ts_code="00506.HK",
        company_name="中国食品",
        data_pack_text=data_pack,
        report_pack_text="""
中粮集团 央企 可口可乐 饮料

| 项目 | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 已付普通股东股息 | -166.0 | -160.6 | -155.6 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
""",
        threshold_category="港股防御型高派蓝筹/净现金央企",
        terminal_g_pct=2.5,
        minority_share=0.396,
        trap_risk="中",
        current_payout=0.496,
        hold_years=3,
    )

    assert 1.3 < float(result["base_growth_pct"]) < 1.5
    assert 2.0 < float(result["opt_growth_pct"]) < 2.2
    assert 1.9 < float(result["payout_release_growth_pct"]) < 2.1
    assert "目标派息率60%" in str(result["growth_tiers_basis"])
    assert "DPS CAGR =" in str(result["dps_cagr_basis"])


def test_workflow_tax_context_formats_hk_local_direct_channel(tmp_path):
    output_dir = tmp_path / "02669_中海物业"
    output_dir.mkdir()
    (output_dir / "pdf_sections_2025.json").write_text(
        "registered in the Cayman Islands", encoding="utf-8"
    )

    structure_label, channel_label, tax_note = workflow_tax_context(
        "02669.HK", output_dir, "hk_local_direct"
    )

    assert structure_label == "红筹/开曼"
    assert channel_label == "香港居民通过香港券商直投"
    assert "待确认" in tax_note
    assert "不可默认 0%" in tax_note


def test_workflow_tax_context_supports_explicit_hk_direct_tax_scenarios(tmp_path):
    output_dir = tmp_path / "00506_中国食品"
    output_dir.mkdir()
    (output_dir / "pdf_sections_2025.json").write_text(
        "registered in the Cayman Islands", encoding="utf-8"
    )

    _structure, channel_0, tax_0 = workflow_tax_context(
        "00506.HK", output_dir, "hk_local_direct_tax0"
    )
    _structure, channel_10, tax_10 = workflow_tax_context(
        "00506.HK", output_dir, "hk_local_direct_tax10"
    )

    assert "0%" in channel_0
    assert "0.00%" in tax_0
    assert "10%" in channel_10
    assert "10.00%" in tax_10


def test_tax_scenarios_by_listing_structure_distinguish_red_chip_and_h_share():
    red_chip = tax_scenarios_for_listing_structure("red_chip_cayman")
    h_share = tax_scenarios_for_listing_structure("h_share")

    assert [row["tax_pct"] for row in red_chip] == [5.0, 10.0, 20.0]
    assert "红筹不适用" in str(red_chip[0]["note"])
    assert [row["tax_pct"] for row in h_share] == [0.0, 10.0, 20.0]
    assert "居民企业豁免" in str(h_share[0]["note"])


def test_current_market_snapshot_prefers_refresh_price_over_stale_quantitative():
    base_pack = """
| 项目 | 内容 |
| --- | ---: |
| 当前价格 (HKD) | 4.01 |
| 总市值 (百万港元) | 11,216.87 |
"""
    refresh_pack = """
### 17.6 因子4·股价分位

| 指标 | 值 |
| --- | ---: |
| 当前股价 | 3.09 |
| 当前股价历史分位 | 56.7% |
"""
    quantitative = """
| 参数 | 值 | 来源 |
| --- | ---: | --- |
| market_cap_mm | 11,216.87 | stale |
| total_shares_mm | 2,797.22 | stale |
| current_price | 4.01 | stale |
"""

    snapshot = resolve_current_market_snapshot(base_pack, refresh_pack, quantitative)

    assert snapshot["current_price"] == 3.09
    assert abs(float(snapshot["total_shares"]) - 2797.22) < 0.01
    assert abs(float(snapshot["market_cap"]) - 3.09 * 2797.22) < 0.01
    assert snapshot["source"] == "刷新包股价×历史股本"


def test_listing_structure_infers_bermuda_red_chip_before_h_share_noise(tmp_path):
    output_dir = tmp_path / "00506_中国食品"
    output_dir.mkdir()
    (output_dir / "pdf_sections_interim_2025.json").write_text(
        """
        China Foods Limited 中國食品有限公司
        (Incorporated in Bermuda with limited liability)
        REGISTERED OFFICE Clarendon House, Bermuda.
        本报告同时提及港股通、H股市场估值作为可比参照。
        """,
        encoding="utf-8",
    )

    structure = infer_listing_structure_from_output("00506.HK", output_dir)
    scenarios = tax_scenarios_for_listing_structure(structure)

    assert structure == "red_chip_bermuda"
    assert [row["tax_pct"] for row in scenarios] == [5.0, 10.0, 20.0]
    assert "红筹不适用" in str(scenarios[0]["note"])


def test_split_table_rows_handles_embedded_summary_block():
    block = """
| 变量 | 2025 | 2024 |
| --- | ---: | ---: |
| C 归母净利润 | 1,488.94 | 1,654.89 |
| D 折旧与摊销 | 123.61 | 113.80 |
| 汇总变量 | 值 | 说明 |
| F（Capex/D&A 5年中位数） | 1.40 | — |
| M（支付率3年均值） | 36.10% | 基于 3 年 |
""".strip()

    rows, summary_rows = split_table_rows(block, "汇总变量")

    assert rows["C 归母净利润"][0] == "1,488.94"
    assert summary_rows["F（Capex/D&A 5年中位数）"][0] == "1.40"
    assert summary_rows["M（支付率3年均值）"][0] == "36.10%"


def test_china_foods_threshold_profile_is_defensive_consumer_not_fallback():
    profile = classify_threshold_profile(
        "00506.HK",
        company_name="中国食品",
        fullname="China Foods Limited",
        industry="饮料行业",
        net_cash=4549.5,
        payout_pct=49.6,
        rf_pct=4.0,
    )

    assert profile.category == "港股防御型高派蓝筹/净现金央企"
    assert profile.ii_pct == 6.5
    assert len(profile.evidence) >= 3


def test_minorities_above_30pct_lower_defensive_threshold():
    profile = classify_threshold_profile(
        "00506.HK",
        company_name="中国食品",
        fullname="China Foods Limited",
        industry="饮料行业",
        net_cash=4549.5,
        payout_pct=49.6,
        rf_pct=4.0,
        minority_share_pct=39.6,
    )

    assert profile.category == "港股防御型高派蓝筹/净现金央企"
    assert profile.ii_pct == 6.0
    assert profile.star_5_pct == 6.0
    assert any("少数股东" in item for item in profile.adjustments)


def test_compute_aa_cash_audit_uses_ocf_minus_min_capex_da():
    data_pack = """
## 5. 现金流量表

| 项目 (百万元) | 2025 | 2024 |
| --- | ---: | ---: |
| 折旧摊销 | 500.0 | 400.0 |
""".strip()
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 本公司拥有人应占溢利 | 600.0 | 500.0 |
| 年内溢利 | 1,000.0 | 800.0 |
| 非控股权益应占溢利 | 400.0 | 300.0 |
| 经营活动现金净额 | 2,000.0 | 1,600.0 |
| 购买物业、厂房及设备 | -900.0 | -300.0 |
| 支付无形资产 | -100.0 | -50.0 |
""".strip()

    result = compute_aa_cash_audit(data_pack_text=data_pack, report_pack_text=report_pack)

    assert result["maintenance_capex_latest"] == 500.0
    assert result["aa_2y"] == 825.0
    assert result["aa_type"] == "AA_2y_cash"
    assert "min" in str(result["maintenance_capex_policy"])


def test_extract_share_count_from_annual_report_text():
    text = """
    The percentages were calculated based on the total number of shares
    of the Company in issue as at 31 December 2025, i.e. 2,797,223,396
    shares.
    Issued and fully paid 2,797,223,396 279,722
    """

    assert _extract_share_count_from_text(text) == 2797.223396


def test_cash_audit_prefers_annual_core_rows_over_stale_market_pack():
    report_pack = ""
    data_pack = """
## 5. 现金流量表

| 项目 (百万元) | 2025 | 2024 |
| --- | ---: | ---: |
| 经营业务现金净额 (OCF) | 1,881.45 | 2,847.15 |
| 购建无形资产及其他资产 | 10.87 | 11.51 |
| 折旧摊销 | 856.53 | 849.76 |
""".strip()
    annual_core_rows = {
        "年内溢利": [1428.047, 1422.577],
        "本公司拥有人应占溢利": [861.968, 860.535],
        "非控股权益应占溢利": [566.079, 562.042],
        "经营活动现金净额": [3229.308, 2847.149],
        "现金资本开支": [1060.515, 774.634],
        "折旧摊销": [893.565, 856.535],
    }

    result = compute_aa_cash_audit(
        data_pack_text=data_pack,
        report_pack_text=report_pack,
        g_coefficient=1.2,
        annual_core_rows=annual_core_rows,
    )

    assert result["aa_type"] == "AA_2y_cash"
    assert 1300 < float(result["aa_selected"]) < 1360
    assert result["maintenance_capex_latest"] == 893.565
    assert result["minority_share"] > 0.30
    assert "强制Total Entity现金审计" in str(result["minority_note"])


def test_dip_buy_strategy_section_generates_ladder():
    data_pack = """
## 3. 合并利润表

| 项目 (百万港元) | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 股东应占溢利 | 1,488.94 | 1,654.89 | 1,501.60 |
| 少数股东损益 | 11.69 | 13.16 | 10.07 |

## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1900 | 41.90 |
| 2024 | 0.1800 | 35.80 |
| 2023 | 0.1400 | 30.60 |
""".strip()
    profile = ThresholdProfile(
        category="港股净现金轻资产央企物管/服务",
        ii_pct=5.5,
        star_5_pct=5.5,
        star_4_pct=5.0,
        star_3_pct=4.5,
        method="test",
        rationale="test",
    )

    section = build_dip_buy_strategy_section(
        data_pack_text=data_pack,
        current_price=3.25,
        threshold_profile=profile,
        q_pct=None,
    )

    assert "越跌越买策略" in section
    assert "| 买入价 | 跌幅 | 税前股息率" in section
    assert "税后股息率(默认10%)" in section
    assert "默认10%" in section
    assert "3.25" in section
    assert "合格买入区间" in section


def test_dip_buy_strategy_uses_passed_red_chip_tax_scenarios():
    data_pack = """
## 3. 合并利润表

| 项目 (百万港元) | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 股东应占溢利 | 60.0 | 55.0 | 50.0 |
| 少数股东损益 | 40.0 | 36.0 | 32.0 |

## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.0 |
| 2024 | 0.1600 | 49.0 |
| 2023 | 0.1530 | 49.0 |
""".strip()
    profile = ThresholdProfile(
        category="港股防御型高派蓝筹/净现金央企",
        ii_pct=6.0,
        star_5_pct=6.0,
        star_4_pct=5.3,
        star_3_pct=4.7,
        method="test",
        rationale="test",
    )

    section = build_dip_buy_strategy_section(
        data_pack_text=data_pack,
        current_price=3.19,
        threshold_profile=profile,
        q_pct=None,
        tax_scenarios=tax_scenarios_for_listing_structure("red_chip_bermuda"),
    )

    assert "| 买入价 | Q=5% | Q=10% | Q=20% |" in section
    assert "0%仅H股居民企业豁免，红筹不适用" in section
    assert "Q=0%" not in section


def test_dip_buy_growth_links_to_dps_cagr_and_minority_discount():
    data_pack = """
## 3. 合并利润表

| 项目 (百万港元) | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 股东应占溢利 | 60.0 | 55.0 | 50.0 |
| 少数股东损益 | 40.0 | 36.0 | 32.0 |

## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.0 |
| 2024 | 0.1600 | 49.0 |
| 2023 | 0.1530 | 49.0 |
""".strip()
    profile = ThresholdProfile(
        category="港股防御型高派蓝筹/净现金央企",
        ii_pct=6.0,
        star_5_pct=6.0,
        star_4_pct=5.3,
        star_3_pct=4.7,
        method="test",
        rationale="test",
    )

    section = build_dip_buy_strategy_section(
        data_pack_text=data_pack,
        report_pack_text="""
| 项目 | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 已付普通股东股息 | -166.0 | -160.0 | -153.0 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
""",
        current_price=3.19,
        threshold_profile=profile,
        q_pct=10.0,
        minority_ratio=0.3964,
        minority_ratio_source="因子3单源",
    )

    assert "DPS CAGR = 4.2%" in section
    assert "基期2023 DPS 0.1530 → 报告期2025 DPS 0.1660" in section
    assert "少数股东利润占比 | 39.6%" in section
    assert "少数股东占比与因子3一致：39.6%（校验通过；因子3单源）" in section
    assert "基准 DPS 增速：1.5%" in section
    assert "DPS增速三档来源：DDM g推导链" in section
    assert "DPS 增速联动 DDM g" in section
    assert "乐观终点GG已纳入行业牛市/利率下行情景" in section
    assert "判定规则说明" in section
    assert "| 保守 | 基准年化≥10%" in section
    assert "| 平衡 | 乐观年化≥10%" in section
    assert "| 进取 | 悲观年化≥10%" in section


def test_wacc_conservatism_is_rule_based_for_defensive_soes():
    result = build_wacc_assumption(
        rf_pct=1.81,
        supplied_ke_pct=10.6,
        supplied_wacc_pct=10.6,
        debt_ratio_pct=0.0,
        trap_risk="中",
        threshold_category="港股防御型高派蓝筹/净现金央企",
        company_name="中国食品",
        report_pack_text="中粮集团 央企",
    )

    assert abs(float(result["ke_fair_pct"]) - 7.41) < 0.001
    assert result["conservatism_pct"] == 1.5
    assert abs(float(result["wacc_pct"]) - 8.91) < 0.001
    assert "防御高派" in str(result["conservatism_basis"])
    assert "央企" in str(result["conservatism_basis"])


def test_ddm_growth_chain_uses_dps_then_minority_decay_and_cap():
    data_pack = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.0 |
| 2024 | 0.1606 | 49.0 |
| 2023 | 0.1556 | 49.0 |
""".strip()

    result = choose_ddm_growth_assumption(
        ts_code="00506.HK",
        company_name="中国食品",
        data_pack_text=data_pack,
        report_pack_text="""
中国食品 饮料 可口可乐 中粮集团

| 项目 | 2025 | 2024 | 2023 |
| --- | ---: | ---: | ---: |
| 已付普通股东股息 | -166.0 | -160.6 | -155.6 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
""",
        threshold_category="港股防御型高派蓝筹/净现金央企",
        terminal_g_pct=2.5,
        minority_share=0.396,
        trap_risk="中",
    )

    assert 1.3 < float(result["ddm_g_pct"]) < 1.5
    assert "基础g=DPS CAGR" in str(result["ddm_g_basis"])
    assert "成熟衰减" in str(result["ddm_g_basis"])
    assert "普通股东口径" in str(result["ddm_g_warning"])


def test_dip_buy_strategy_prefers_report_dividend_dps_over_duplicate_market_rows():
    data_pack = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.25 |
| 2024 | 0.1660 | 49.97 |
| 2024 | 0.1660 | 53.94 |
| 2023 | 0.1660 | 51.65 |
""".strip()
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 已付普通股东股息 | -427.6 | -414.0 |

## 分红与股本

- 年内总股本：2,797,223,396 股。
""".strip()

    series, source = _extract_dps_series_with_source(data_pack, report_pack)

    assert source == "年报普通股股息/股本反推"
    assert len(series) == 2
    assert series[0] == 0.1660
    assert series[1] < series[0]


def test_dps_cagr_rejects_deduped_market_dividend_table_as_primary_source():
    data_pack = """
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.25 |
| 2024 | 0.1660 | 49.97 |
| 2024 | 0.1660 | 53.94 |
| 2023 | 0.1660 | 51.65 |
""".strip()

    cagr, source, basis = _dps_cagr_basis(data_pack, "")

    assert cagr is None
    assert "市场分红表（同一年去重）不作为DPS CAGR主输入" in source
    assert "DPS CAGR缺失" in basis


def test_ddm_growth_warns_when_zero_dps_cagr_conflicts_with_profit_growth():
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 本公司拥有人应占溢利 | 110.0 | 100.0 |
| 已付普通股东股息 | -166.0 | -166.0 |

## 分红与股本

- 年内总股本：1,000,000,000 股。
- 历史数据包记录年度 DPS 为 0.166 港元/股，需以 HKEX 末期股息公告复核最终 DPS。
""".strip()

    result = choose_ddm_growth_assumption(
        ts_code="00000.HK",
        company_name="测试公司",
        data_pack_text="",
        report_pack_text=report_pack,
        threshold_category="港股防御型高派蓝筹/净现金央企",
        terminal_g_pct=2.5,
        minority_share=None,
        trap_risk="中",
    )

    assert "DPS CAGR 可能被数据源去重卡死，请人工复核" in str(result["ddm_g_warning"])


def test_annual_core_dividend_snippet_provides_report_dps_cagr_source():
    snippet = annual_core_dividend_report_snippet(
        {
            "已付普通股东股息": [427.6, 414.0],
            "总股本": [2797.223396],
        },
        latest_market_dps=0.166,
    )

    cagr, source, basis = _dps_cagr_basis("", snippet)

    assert cagr is not None
    assert source == "年报普通股股息/股本反推"
    assert "DPS 单年增长率 =" in basis
    assert "1 年 CAGR" not in basis


def test_executive_summary_assumption_sentence_is_explicit():
    sentence = executive_summary_assumption_sentence(
        q_display="默认10%税后；并列5%/10%/20%敏感性",
        threshold_adjustments=["少数股东占比>30%，II下调0.5pct"],
        dps_cagr_basis="DPS 单年增长率 = 3.3%（基期2024 DPS 0.1600 → 报告期2025 DPS 0.1660，1 年单年增长率；年报普通股股息/股本反推）",
    )

    assert "本结论基于 [税率 Q=默认10%税后" in sentence
    assert "[少数股东占比>30%，II下调0.5pct]" in sentence
    assert "[DPS 单年增长率 = 3.3%" in sentence
    assert "若假设变化，结论可能翻转" in sentence


def test_dip_buy_strategy_falls_back_to_report_dividend_dps_when_market_missing():
    data_pack = """
## 6. 分红历史

暂无分红数据
""".strip()
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 本公司拥有人应占溢利 | 862.0 | 860.5 |
| 非控股权益应占溢利 | 566.1 | 562.0 |
| 已付普通股东股息 | -427.6 | -414.0 |

## 分红与股本

- 年内总股本：2,797,223,396 股。
- 历史数据包记录年度 DPS 为 0.166 港元/股，需以 HKEX 末期股息公告复核最终 DPS。
""".strip()
    profile = ThresholdProfile(
        category="港股防御型高派蓝筹/净现金央企",
        ii_pct=6.0,
        star_5_pct=6.0,
        star_4_pct=5.3,
        star_3_pct=4.7,
        method="test",
        rationale="test",
    )

    section = build_dip_buy_strategy_section(
        data_pack_text=data_pack,
        report_pack_text=report_pack,
        current_price=3.19,
        threshold_profile=profile,
        q_pct=10.0,
    )

    assert "DPS 数据缺失" not in section
    assert "DPS 三档推导" in section
    assert "年报普通股股息/股本反推" in section
    assert "当前派息率 | 49.6%" in section


def test_turtle_report_scaffold_uses_factor_based_structure():
    scaffold = turtle_report_scaffold("00506.HK", "中国食品")

    assert "## 四、因子2：穿透回报率粗算（Top-Down）" in scaffold
    assert "## 五、因子3：穿透回报率精算（Bottom-Up）+ 现金质量审计" in scaffold
    assert "## 六、因子4：估值与安全边际" in scaffold
    assert "## 七、越跌越买策略 · 年化10%目标" in scaffold
    assert "## 穿透回报率分析" not in scaffold


def test_fallback_absolute_valuation_uses_local_hk_packs():
    data_pack = """
## 3. 合并利润表

| 项目 (百万港元) | 2024 | 2023 | 2022 |
| --- | ---: | ---: | ---: |
| 每股基本盈利 (HKD) | 0.31 | 0.30 | 0.24 |

## 5. 现金流量表

| 项目 (百万港元) | 2024 | 2023 | 2022 |
| --- | ---: | ---: | ---: |
| 自由现金流 (FCF) | 2,784.94 | 2,409.45 | 1,134.25 |

## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1660 | 49.25 |
| 2024 | 0.1660 | 49.97 |
| 2023 | 0.1660 | 51.65 |

## 12. 关键财务指标

| 指标 | 2024 | 2023 | 2022 |
| --- | ---: | ---: | ---: |
| PE (TTM) | 13.40 | 12.55 | 14.38 |
""".strip()
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 收入 | 22,070.2 | 21,491.8 |
| 现金及现金等价物 | 4,549.5 | 4,014.4 |
| 经营活动现金净额 | 3,229.3 | 2,847.1 |
| 购买物业、厂房及设备 | -1,048.8 | -712.4 |
| 支付无形资产 | -11.7 | -12.1 |
""".strip()

    result = build_fallback_absolute_valuation(
        data_pack_text=data_pack,
        report_pack_text=report_pack,
        current_price=3.19,
        total_shares_mm=2797.2,
        market_cap=8923.0,
        ke_pct=10.6,
        wacc_pct=10.6,
        rf_pct=4.0,
        ts_code="00506.HK",
        company_name="中国食品",
        threshold_category="港股防御型高派蓝筹/净现金央企",
        minority_share=0.396,
        debt_ratio_pct=0.0,
        trap_risk="中",
    )

    assert result["source"] == "本地数据包回退"
    assert result["ddm"] is not None
    assert result["ddm_fair"] is not None
    assert result["ddm_conservative"] is not None
    assert result["ddm_fair"] > result["ddm_conservative"]
    assert result["pe_band"] is not None
    assert result["dcf"] is not None
    assert "Rf 4.00%" in str(result["wacc_breakdown"])
    assert "β 0.80" in str(result["wacc_breakdown"])
    assert "ERP 5.50%" in str(result["wacc_breakdown"])
    assert result["specific_risk_pct"] is not None
    assert result["ddm_g_pct"] is not None
    assert float(result["ddm_g_pct"]) < float(result["terminal_g_pct"])
    assert "弱周期防御消费" in str(result["ddm_g_basis"])
    assert result["wacc_pct"] is not None
    assert result["ke_fair_pct"] is not None
    assert result["ddm_d1"] is not None
    assert "D1 = DPS" in str(result["ddm_formula"])
    assert result["pressure_center"] is not None
    assert result["terminal_g_pct"] is not None
    assert result["forecast_years"] == 5.0
    assert abs(float(result["stage_g_pct"]) - float(result["ddm_g_pct"])) < 0.01
    if float(result["terminal_value_share_pct"]) > 70.0:
        assert "终值占比偏高" in str(result["parameter_warning"])


def test_fallback_absolute_valuation_flags_wacc_below_rf_plus_3():
    result = build_fallback_absolute_valuation(
        data_pack_text="",
        report_pack_text="",
        current_price=3.19,
        total_shares_mm=2797.2,
        market_cap=8923.0,
        ke_pct=5.0,
        wacc_pct=5.0,
        rf_pct=3.0,
    )

    assert "外部WACC 5.00% 与v2.1规则化WACC" in str(result["parameter_warning"])
    assert float(result["wacc_pct"]) > 5.0


def test_composite_benchmark_table_uses_available_anchors():
    data_pack = """
| 指标 | 值 |
| --- | ---: |
| 每股净资产 (HKD) | 2.40 |

## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1800 | 40.0 |
""".strip()
    quantitative = """
| transfer_key | value |
| --- | ---: |
| net_cash_mm | — |
""".strip()
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 现金及现金等价物 | 600.0 | 550.0 |
| 借贷 | 0.0 | 0.0 |
""".strip()

    composite, table = build_composite_benchmark_table(
        data_pack_text=data_pack,
        refresh_pack_text="| 项目 | 数值 |\n| --- | ---: |\n| 10%分位价格 | 2.60 |",
        report_pack_text=report_pack,
        quantitative_text=quantitative,
        current_price=3.2,
        total_shares=300.0,
    )

    assert composite is not None
    assert "综合基准价" in table
    assert "6%股息价" in table
    assert "2.00" in table
    assert "2.60" in table


def test_composite_benchmark_table_calculates_bvps_from_report_equity():
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 现金及现金等价物 | 600.0 | 550.0 |
| 借贷 | 0.0 | 0.0 |
| 本公司拥有人应占权益 | 900.0 | 850.0 |
""".strip()

    _composite, table = build_composite_benchmark_table(
        data_pack_text="""
## 6. 分红历史

| 年度 | 每股股息 (HKD) | 派息率 (%) |
| --- | ---: | ---: |
| 2025 | 0.1800 | 40.0 |
""".strip(),
        refresh_pack_text="| 项目 | 数值 |\n| --- | ---: |\n| 10%分位价格 | 2.60 |",
        report_pack_text=report_pack,
        quantitative_text="",
        current_price=3.2,
        total_shares=300.0,
    )

    assert "| BVPS | 3.00 |" in table
    assert "归母权益/总股本" in table


def test_historical_quantile_table_includes_high_low_quartiles_and_source():
    table = build_historical_quantile_table("""
## 11. 十年周线行情

| 指标 | 数值 |
| --- | ---: |
| 10年最高 (HKD) | 5.42 (20171112) |
| 10年最低 (HKD) | 1.97 (20221030) |

### 17.6 因子4·股价分位

| 指标 | 值 |
| --- | ---: |
| 10年数据点数 | 524 |
| 当前股价历史分位 | 56.5% |
| 10%分位价格 | 2.60 |
| 25%分位价格 | 2.77 |
| 50%分位价格（中位数） | 3.03 |

*数据来源: Tushare Pro*
""".strip())

    assert "10年最高" in table
    assert "10年最低" in table
    assert "10%分位" in table
    assert "25%分位" in table
    assert "50%分位" in table
    assert "当前分位" in table
    assert "周频" in table


def test_historical_quantile_table_lists_daily_weekly_and_composite_uses_lower():
    daily_pack = """
### 17.6 因子4·股价分位

| 指标 | 值 |
| --- | ---: |
| 10年数据点数 | 2400 |
| 当前股价历史分位 | 40.0% |
| 10%分位价格 | 2.02 |
| 25%分位价格 | 2.20 |
| 50%分位价格（中位数） | 2.40 |

*数据来源: Tushare Pro*
""".strip()
    weekly_pack = """
## 11. 十年周线行情

| 指标 | 数值 |
| --- | ---: |
| 10年最高 (HKD) | 5.42 |
| 10年最低 (HKD) | 1.97 |

### 17.6 因子4·股价分位

| 指标 | 值 |
| --- | ---: |
| 10年数据点数 | 524 |
| 当前股价历史分位 | 56.5% |
| 10%分位价格 | 2.60 |
| 25%分位价格 | 2.77 |
| 50%分位价格（中位数） | 3.03 |
""".strip()

    table = build_historical_quantile_table(daily_pack, weekly_pack)
    assert "历史10%分位价（日频）2.02；（周频）2.60；差异>15%，取保守值 2.02" in table

    _composite, benchmark_table = build_composite_benchmark_table(
        data_pack_text=daily_pack,
        refresh_pack_text=weekly_pack,
        report_pack_text="",
        quantitative_text="",
        current_price=3.2,
        total_shares=300.0,
    )
    assert "| 历史10%分位价 | 2.02 |" in benchmark_table
    assert "取保守值 2.02" in benchmark_table


def test_cash_quality_audit_sections_restore_52_to_59():
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 收入 | 22,070.2 | 21,491.8 |
| 应收贸易款项 | 329.7 | 339.4 |
| 合约负债 | 1,308.0 | 866.0 |
| 受限制银行存款 | 0.2 | 4.1 |
| 经营活动现金净额 | 3,229.3 | 2,847.1 |
| 购买物业、厂房及设备 | -1,048.8 | -712.4 |
| 支付无形资产 | -11.7 | -12.1 |
| 分销及销售支出 | -5,949.1 | -5,871.2 |
| 行政支出 | -472.2 | -537.6 |
| 已付普通股东股息 | -427.6 | -414.0 |
| 已付非控股权益股息 | -1,149.4 | -90.2 |
""".strip()

    section = build_cash_quality_audit_sections(
        data_pack_text="",
        report_pack_text=report_pack,
        aa_2y=1295.2,
        aa_all=1350.0,
        aa_excl=1350.0,
        maintenance_capex_latest=893.6,
        capex_da_median=1.19,
        cash_2025=4549.5,
        net_cash_2025=4549.5,
        fcf_sequence=[1134.2, 2409.5, 2784.9],
        payout_anchor=49.6,
    )

    for heading in [
        "### 5.2 应收 Footnote 核查",
        "### 5.3 非经常现金分类",
        "### 5.4 经营现金支出还原",
        "### 5.5 Capex 极端保守处理",
        "### 5.6 HKFRS 差异核查",
        "### 5.7 AA 三口径",
        "### 5.8 现金储备质量",
        "### 5.9 派息后净变动",
    ]:
        assert heading in section
    assert "c_pay_to_staff缺失时用SGA+行政支出代理" in section


def test_composite_benchmark_table_labels_frequency_window_and_source():
    composite, table = build_composite_benchmark_table(
        data_pack_text="",
        refresh_pack_text="""
| 项目 | 数值 |
| --- | ---: |
| 10%分位价格 | 2.02 |
| 10年数据点数 | 2400 |

### 年度行情汇总

| 年份 | 收盘价 |
| --- | ---: |
| 2016 | 2.10 |
| 2026 | 3.19 |

数据源：Tushare Pro
""".strip(),
        report_pack_text="",
        quantitative_text="",
        current_price=3.2,
        total_shares=300.0,
    )

    assert composite is not None
    assert "10年全区间 2016-01-01" in table
    assert "日频" in table
    assert "Tushare" in table


def test_cash_audit_uses_ocf_capex_not_parent_profit_when_available():
    report_pack = """
## 三表核心数据（2025 vs 2024）

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 年内溢利 | 1,428.0 | 1,422.6 |
| 本公司拥有人应占溢利 | 862.0 | 860.5 |
| 非控股权益应占溢利 | 566.1 | 562.1 |
| 经营活动现金净额 | 3,229.3 | 2,847.1 |
| 购买物业、厂房及设备 | -1,048.8 | -712.4 |
| 支付无形资产 | -11.7 | -12.1 |
| 已付普通股东股息 | -427.6 | -414.0 |
""".strip()

    data_pack = """
## 5. 现金流量表

| 项目 (百万元) | 2025 | 2024 |
| --- | ---: | ---: |
| 折旧摊销 | 950.0 | 650.0 |
""".strip()

    result = compute_aa_cash_audit(data_pack_text=data_pack, report_pack_text=report_pack)

    assert result["aa_type"] == "AA_2y_cash"
    assert result["aa_selected"] != 862.0
    assert 1200 < result["aa_selected"] < 1400
    assert result["minority_share"] > 0.30
    assert "强制Total Entity现金审计" in result["minority_note"]
    assert result["aa_manual_check"] is not None
    assert 1200 < float(result["aa_manual_check"]) < 1320
    assert float(result["aa_manual_diff_pct"]) > 0.0
    assert "现金审计可接受" in str(result["aa_manual_note"])
    assert "差异 0.0%" not in str(result["aa_manual_note"])


def test_nci_dividend_alert_triggers_for_large_brand_jv_jump():
    report_pack = """
中国食品与 Coca-Cola 可口可乐装瓶业务合资运营。

| 项目 | 2025 | 2024 |
| --- | ---: | ---: |
| 已付非控股权益股息 | -1,149.4 | -90.2 |
""".strip()

    alert = nci_dividend_alert(report_pack, 0.396)

    assert "非控股股息同比" in alert
    assert "普通股东 DPS 提速受合资协议约束" in alert
