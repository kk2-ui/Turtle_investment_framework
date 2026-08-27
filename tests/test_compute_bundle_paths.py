import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import compute_bundle as cb  # noqa: E402


def test_lambda_statistic_uses_true_median_not_arithmetic_mean():
    values = [1.809, -0.162, 0.102]

    assert cb._median_or_none(values) == 0.102
    assert cb._median_or_none([]) is None


def _stub_factor2():
    return {
        "rejection": {},
        "M": 0.55,
        "oe_maintenance_G": {"coefficient": 0.85},
    }


def _stub_factor3():
    return {
        "rejection": {},
        "M": 0.62,
        "gg": {"base": 8.6},
        "gg_labor_source": "pdf_override",
        "gg_labor_confidence": "medium",
        "gg_labor_method": "pdf_override > hybrid_override > industry_heuristic > db_proxy",
        "gg_labor_explanation": "W1 direct labor dedup uses annual-report note facts from gg_override.json.",
        "gg_labor_capability": "function_split_available",
        "gg_override_applied": True,
        "gg_override_years": ["2025"],
        "gg_override_modes": ["pdf_override", "pdf_total_labor_override"],
        "w_breakdown": {
            "w1_dedup_years": {"2025": {"source": "pdf_override", "direct_labor_cost": 3941.9}},
            "w2_override_years": {"2025": {"source": "pdf_total_labor_override", "total_labor_cost": 4220.4}},
        },
    }


def _stub_factor4():
    return {
        "rejection": {},
        "ddm_v_hkd": 1.23,
    }


def _stub_override(tmp_path: Path):
    return {
        "source_file": str(tmp_path / "gg_override.json"),
        "years": {"2025": {"direct_labor_cost": 3941.9}},
    }


def _stub_labor_summary():
    return {
        "years_with_total_only": [],
        "years_with_function_split": ["2025"],
        "years_with_no_labor_disclosure": ["2024"],
    }


def test_compute_json_mode_emits_gg_metadata(tmp_path, monkeypatch):
    output_dir = tmp_path / "02669_sample"
    output_dir.mkdir()

    monkeypatch.setattr(cb, "load_threshold", lambda _: {"II": 5.5, "shares_m": 100.0})
    monkeypatch.setattr(cb, "load_input_data", lambda _: {"ts_code": "02669.HK", "currency": "HKD", "years": ["2025"]})
    monkeypatch.setattr(cb, "normalize_input_data", lambda raw: {"ts_code": raw["ts_code"], "currency": raw["currency"]})
    monkeypatch.setattr(cb, "load_hk_fallback", lambda _: None)
    monkeypatch.setattr(cb, "load_data_pack", lambda _: None)
    monkeypatch.setattr(cb, "load_gg_override", lambda _: _stub_override(tmp_path))
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: _stub_labor_summary())
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: _stub_factor2())
    monkeypatch.setattr(cb, "compute_factor3", lambda *args, **kwargs: _stub_factor3())
    monkeypatch.setattr(cb, "compute_factor4", lambda *args, **kwargs: _stub_factor4())
    monkeypatch.setattr(cb, "_build_calculation_trace", lambda *args, **kwargs: {})
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: {"status": "pass", "gg_base": 8.6})

    bundle = cb.compute(str(output_dir), price_hkd=1.0, shares_m=100.0)

    assert bundle["meta"]["code"] == "02669.HK"
    assert bundle["factor2"]["M"] == 0.62
    assert bundle["gg_labor"]["source"] == "pdf_override"
    assert bundle["gg_labor"]["annual_report_function_split_years"] == ["2025"]
    assert bundle["gg_override"]["years"] == ["2025"]
    assert "trading_info" not in bundle


def test_compute_json_mode_missing_market_inputs_keeps_enterprise_computation(
    tmp_path, monkeypatch,
):
    output_dir = tmp_path / "anonymous_missing_market"
    output_dir.mkdir()
    captured_market = {}
    monkeypatch.setattr(cb, "DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(cb, "load_threshold", lambda _: {"II": 5.5})
    monkeypatch.setattr(cb, "load_input_data", lambda _: {"ts_code": "", "currency": "HKD", "years": ["2025"]})
    monkeypatch.setattr(cb, "normalize_input_data", lambda raw: {"ts_code": "", "currency": "HKD"})
    monkeypatch.setattr(cb, "load_hk_fallback", lambda _: None)
    monkeypatch.setattr(cb, "load_data_pack", lambda _: None)
    monkeypatch.setattr(cb, "load_gg_override", lambda _: {})
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: {})
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: _stub_factor2())

    def factor3_stub(fin, market, *args, **kwargs):
        captured_market.update(market)
        return {
            "rejection": {"market_cap": "unresolved"}, "M": 0.62,
            "gg": {"base": None, "pessimistic": None, "optimistic": None},
            "gg_unavailable": True,
        }

    monkeypatch.setattr(cb, "compute_factor3", factor3_stub)
    monkeypatch.setattr(cb, "compute_factor4", lambda *args, **kwargs: {
        "valuation_status": "UNRESOLVED_VALUATION",
        "rejection": {"valuation_input": "unresolved"},
    })
    monkeypatch.setattr(cb, "_build_calculation_trace", lambda *args, **kwargs: {})
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: None)

    bundle = cb.compute(str(output_dir))

    assert captured_market["price_rmb"] is None
    assert captured_market["shares_m"] is None
    assert captured_market["mc_rmb"] == 0
    assert bundle["market"]["market_cap_status"] == "UNAVAILABLE"
    assert bundle["rejection_summary"]["overall"] == "unresolved"


def test_calculation_trace_with_missing_market_cap_contains_nulls_not_fake_zero_returns():
    factor2 = {
        "r_np": None, "r_oe": None, "np_avg_3y": 100.0, "oe_avg_3y": 90.0,
    }
    factor3 = {
        "M": 0.62, "g_adj": 1.5, "g_base": 2.0,
        "gg": {"base": None, "pessimistic": None, "optimistic": None},
        "gg_raw": {}, "aa_avg": {"3y": 80.0}, "lambda": {},
    }
    factor4 = {
        "valuation_status": "UNRESOLVED_VALUATION",
        "valuation_unresolved_reason": "current price missing",
    }
    market = {"price_rmb": None, "shares_m": None, "mc_rmb": 0, "fx": 1.0}

    trace = cb._build_calculation_trace(
        factor2, factor3, factor4, market,
        {"II": 5.5, "Q": 0.1, "dps_latest": None},
    )

    assert trace["factor2_r_np"]["result"] is None
    assert trace["factor2_r_oe"]["result"] is None
    assert trace["factor2_r_np_after_tax"]["result"] is None
    assert trace["factor2_r_np_after_tax"]["steps"] == []
    assert trace["factor4_ddm"]["status"] == "UNRESOLVED_VALUATION"


def test_compute_paths_share_same_gg_metadata(tmp_path, monkeypatch):
    output_dir = tmp_path / "02669_sample"
    output_dir.mkdir()

    fin_data = {
        "ts_code": "02669.HK",
        "currency": "HKD",
        "financial_source_code": "02669.HK",
        "income": [{"depr_fa_coga_dpba": 1.0, "amort_intang_assets": 0.0}],
        "balance_sheet": [],
        "cashflow": [],
        "dividends": [{"dps": 0.1, "dividends_paid": 10.0}],
    }
    stock_info = {"shares_m": 100.0, "currency": "HKD"}

    monkeypatch.setattr(cb, "DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(cb, "load_threshold", lambda _: {"II": 5.5, "shares_m": 100.0})
    monkeypatch.setattr(cb, "load_input_data", lambda _: {"ts_code": "02669.HK", "currency": "HKD", "years": ["2025"]})
    monkeypatch.setattr(cb, "normalize_input_data", lambda raw: {"ts_code": raw["ts_code"], "currency": raw["currency"]})
    monkeypatch.setattr(cb, "load_hk_fallback", lambda _: None)
    monkeypatch.setattr(cb, "load_data_pack", lambda _: None)
    monkeypatch.setattr(cb, "load_from_db", lambda ts_code, contract=None: {**fin_data, "_threshold": {"II": 5.5}, "_stock": stock_info})
    monkeypatch.setattr(cb, "find_stock_output_dir", lambda _: str(output_dir))
    monkeypatch.setattr(cb, "fetch_market_from_tushare", lambda _: None)
    monkeypatch.setattr(cb, "_extract_annual_report_dividend_plan", lambda _: {})
    monkeypatch.setattr(cb, "_load_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "_resolve_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "load_gg_override", lambda _: _stub_override(tmp_path))
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: _stub_labor_summary())
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: _stub_factor2())
    monkeypatch.setattr(cb, "compute_factor3", lambda *args, **kwargs: _stub_factor3())
    monkeypatch.setattr(cb, "compute_factor4", lambda *args, **kwargs: _stub_factor4())
    monkeypatch.setattr(cb, "_build_calculation_trace", lambda *args, **kwargs: {})
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: {"status": "pass", "gg_base": 8.6})

    json_bundle = cb.compute(str(output_dir), price_hkd=1.0, shares_m=100.0)
    db_bundle = cb.compute_from_db("02669.HK", price_hkd=1.0)

    assert json_bundle["gg_labor"] == db_bundle["gg_labor"]
    assert json_bundle["gg_override"] == db_bundle["gg_override"]


def test_compute_from_db_missing_quote_never_invents_one_currency_unit_price(
    tmp_path, monkeypatch,
):
    output_dir = tmp_path / "02669_missing_quote"
    output_dir.mkdir()
    fin_data = {
        "ts_code": "02669.HK", "currency": "HKD", "financial_source_code": "02669.HK",
        "income": [{"depr_fa_coga_dpba": 1.0}], "balance_sheet": [], "cashflow": [],
        "dividends": [{"dps": 0.1, "dividends_paid": 10.0}],
    }
    stock_info = {"shares_m": 100.0, "currency": "HKD"}
    captured_market = {}

    monkeypatch.setattr(cb, "DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(cb, "load_from_db", lambda *args, **kwargs: {
        **fin_data, "_threshold": {"II": 5.5}, "_stock": stock_info,
    })
    monkeypatch.setattr(cb, "find_stock_output_dir", lambda _: str(output_dir))
    monkeypatch.setattr(cb, "fetch_market_from_tushare", lambda _: None)
    monkeypatch.setattr(cb, "_extract_annual_report_dividend_plan", lambda _: {})
    monkeypatch.setattr(cb, "_load_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "_resolve_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "load_gg_override", lambda _: {})
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: {})
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: _stub_factor2())

    def factor3_stub(fin, market, *args, **kwargs):
        captured_market.update(market)
        return {
            "rejection": {"market_cap": "unresolved"}, "M": 0.62,
            "gg": {"base": None, "pessimistic": None, "optimistic": None},
            "gg_unavailable": True, "gg_unavailable_reason": "market cap unavailable",
        }

    monkeypatch.setattr(cb, "compute_factor3", factor3_stub)
    monkeypatch.setattr(cb, "compute_factor4", lambda *args, **kwargs: {
        "valuation_status": "UNRESOLVED_VALUATION",
        "rejection": {"valuation_input": "unresolved"},
    })
    monkeypatch.setattr(cb, "_build_calculation_trace", lambda *args, **kwargs: {})
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: None)

    bundle = cb.compute_from_db("02669.HK")

    assert captured_market["price_native"] is None
    assert captured_market["price_rmb"] is None
    assert captured_market["mc_rmb"] == 0
    assert bundle["market"]["price_status"] == "UNAVAILABLE"
    assert bundle["market"]["price_source"] == "unavailable"
    assert bundle["rejection_summary"]["overall"] == "unresolved"


def test_compute_from_db_missing_shares_and_dps_keeps_enterprise_computation(
    tmp_path, monkeypatch,
):
    output_dir = tmp_path / "02669_missing_per_share_inputs"
    output_dir.mkdir()
    fin_data = {
        "ts_code": "02669.HK", "currency": "HKD", "financial_source_code": "02669.HK",
        "income": [{"depr_fa_coga_dpba": 1.0}], "balance_sheet": [], "cashflow": [],
        "dividends": [{}],
    }
    stock_info = {"shares_m": None, "currency": "HKD"}
    captured = {}
    monkeypatch.setattr(cb, "DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(cb, "load_from_db", lambda *args, **kwargs: {
        **fin_data, "_threshold": {"II": 5.5}, "_stock": stock_info,
    })
    monkeypatch.setattr(cb, "find_stock_output_dir", lambda _: str(output_dir))
    monkeypatch.setattr(cb, "fetch_market_from_tushare", lambda _: {"price": 8.0, "source": "test"})
    monkeypatch.setattr(cb, "_extract_annual_report_dividend_plan", lambda _: {})
    monkeypatch.setattr(cb, "_load_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "_resolve_dividend_evidence", lambda _: {})
    monkeypatch.setattr(cb, "load_gg_override", lambda _: {})
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: {})
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: _stub_factor2())

    def factor3_stub(fin, market, params, *args, **kwargs):
        captured.update({"market": market, "params": params})
        return {
            "rejection": {"market_cap": "unresolved"}, "M": 0.62,
            "gg": {"base": None, "pessimistic": None, "optimistic": None},
            "gg_unavailable": True,
        }

    monkeypatch.setattr(cb, "compute_factor3", factor3_stub)
    monkeypatch.setattr(cb, "compute_factor4", lambda *args, **kwargs: {
        "valuation_status": "UNRESOLVED_VALUATION",
        "rejection": {"valuation_input": "unresolved"},
    })
    monkeypatch.setattr(cb, "_build_calculation_trace", lambda *args, **kwargs: {})
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: None)

    bundle = cb.compute_from_db("02669.HK")

    assert captured["market"]["price_rmb"] is not None
    assert captured["market"]["shares_m"] is None
    assert captured["market"]["mc_rmb"] == 0
    assert captured["params"]["dps_latest"] is None
    assert bundle["market"]["shares_status"] == "UNAVAILABLE"
    assert bundle["rejection_summary"]["overall"] == "unresolved"


def test_compute_with_missing_dps_writes_unresolved_trace_instead_of_crashing(tmp_path, monkeypatch):
    output_dir = tmp_path / "02669_missing_dps"
    output_dir.mkdir()

    monkeypatch.setattr(cb, "load_threshold", lambda _: {"II": 5.5, "shares_m": 100.0})
    monkeypatch.setattr(cb, "load_input_data", lambda _: {"ts_code": "02669.HK", "currency": "HKD", "years": ["2025"]})
    monkeypatch.setattr(cb, "normalize_input_data", lambda raw: {"ts_code": raw["ts_code"], "currency": raw["currency"]})
    monkeypatch.setattr(cb, "load_hk_fallback", lambda _: None)
    monkeypatch.setattr(cb, "load_data_pack", lambda _: None)
    monkeypatch.setattr(cb, "load_gg_override", lambda _: {})
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: {})
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: {
        "rejection": {}, "M": 0.62, "r_np": 8.0, "r_oe": 7.0,
        "np_avg_3y": 100.0, "oe_avg_3y": 90.0,
    })
    monkeypatch.setattr(cb, "compute_factor3", lambda *args, **kwargs: {
        "rejection": {}, "M": 0.62, "g_adj": 1.5, "g_base": 2.0,
        "gg": {"base": 8.0, "pessimistic": 7.0, "optimistic": 9.0},
        "gg_raw": {}, "aa_avg": {"3y": 80.0}, "lambda": {},
    })
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: {"status": "pass"})

    bundle = cb.compute(str(output_dir), price_hkd=1.0, shares_m=100.0)

    assert bundle["factor4"]["valuation_status"] == "UNRESOLVED_VALUATION"
    assert bundle["calculation_trace"]["factor4_ddm"]["status"] == "UNRESOLVED_VALUATION"
    assert bundle["calculation_trace"]["factor4_ddm"]["result"] is None
    assert bundle["calculation_trace"]["factor4_ddm"]["steps"] == []
    assert bundle["rejection_summary"]["overall"] == "unresolved"


def test_unverified_high_gg_identity_withdraws_valuation_without_stopping_bundle(tmp_path, monkeypatch):
    output_dir = tmp_path / "02669_unverified_high_gg"
    output_dir.mkdir()
    monkeypatch.setattr(cb, "load_threshold", lambda _: {"II": 5.5, "shares_m": 100.0})
    monkeypatch.setattr(cb, "load_input_data", lambda _: {"ts_code": "02669.HK", "currency": "HKD", "years": ["2025"]})
    monkeypatch.setattr(cb, "normalize_input_data", lambda raw: {"ts_code": raw["ts_code"], "currency": raw["currency"]})
    monkeypatch.setattr(cb, "load_hk_fallback", lambda _: None)
    monkeypatch.setattr(cb, "load_data_pack", lambda _: None)
    monkeypatch.setattr(cb, "load_gg_override", lambda _: {})
    monkeypatch.setattr(cb, "load_labor_disclosure_summary", lambda _: {})
    monkeypatch.setattr(cb, "compute_factor2", lambda *args, **kwargs: {
        "rejection": {}, "M": 0.62, "r_np": 12.0, "r_oe": 11.0,
        "np_avg_3y": 100.0, "oe_avg_3y": 90.0,
    })
    monkeypatch.setattr(cb, "compute_factor3", lambda *args, **kwargs: {
        "rejection": {}, "M": 0.62, "g_adj": 1.5, "g_base": 2.0,
        "gg": {"base": 12.0, "pessimistic": 11.0, "optimistic": 13.0},
        "gg_raw": {}, "aa_avg": {"3y": 100.0}, "lambda": {},
    })
    monkeypatch.setattr(cb, "_check_gg_guard", lambda *args, **kwargs: {
        "error": "gg_base_requires_annual_report_recheck",
        "message": "shares identity not verified",
    })

    bundle = cb.compute(
        str(output_dir),
        params_override={"dps_latest": 0.1},
        price_hkd=1.0,
        shares_m=100.0,
    )

    assert "error" not in bundle
    assert bundle["factor3"]["gg_diagnostic_unverified"]["base"] == 12.0
    assert bundle["factor3"]["gg"]["base"] is None
    assert bundle["factor4"]["valuation_status"] == "UNRESOLVED_VALUATION"
    assert bundle["rejection_summary"]["overall"] == "unresolved"
