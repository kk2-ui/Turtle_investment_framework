import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from compute_bundle import compute_factor3, load_gg_override, _normalized_aa_value  # noqa: E402


def _sample_fin_data():
    years = ["2023", "2024", "2025"]
    income = []
    balance_sheet = []
    cashflow = []
    dividends = []
    for year in years:
        income.append({
            "end_date": f"{year}1231",
            "revenue": 1000.0,
            "n_income_attr_p": 100.0,
            "minority_profit": 0.0,
            "depr_fa_coga_dpba": 20.0,
            "amort_intang_assets": 0.0,
            "oper_cost": 850.0,
            "sell_dist_exp": 50.0,
            "admin_exp": 100.0,
            "rd_exp": 20.0,
            "other_income": 0.0,
            "gov_subsidy": 0.0,
            "invest_income": 0.0,
            "total_profit": 120.0,
            "income_tax": 20.0,
        })
        balance_sheet.append({
            "end_date": f"{year}1231",
            "money_cap": 200.0,
            "accounts_receiv": 100.0,
            "acct_payable": 100.0,
            "contract_liab": 0.0,
            "total_assets": 1200.0,
            "total_liab": 500.0,
            "total_hldr_eqy_exc_min_int": 700.0,
            "goodwill": 0.0,
            "st_borr": 0.0,
            "lt_borr": 0.0,
            "minority_int": 0.0,
            "inventories": 0.0,
            "fix_assets": 100.0,
            "intang_assets": 0.0,
            "employee_cost": 0.0,
        })
        cashflow.append({
            "end_date": f"{year}1231",
            "n_cashflow_act": 120.0,
            "c_pay_acq_const_fiolta": 20.0,
            "asset_disposal": 0.0,
            "interest_received": 0.0,
            "tax_paid": 10.0,
            "interest_paid": 2.0,
            "inventory_change": 0.0,
            "ar_change_cf": 0.0,
            "intangible_purchase": 0.0,
            "gain_asset_sale": 0.0,
            "impairment_cf": 0.0,
            "cash_paid_employees": 500.0,
        })
        dividends.append({
            "end_date": f"{year}1231",
            "cash_div_tax": 30.0,
            "dividends_paid": 30.0,
            "dps": 0.3,
            "base_share": 1000.0,
        })

    return {
        "ts_code": "01502.HK",
        "income": income,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "dividends": dividends,
        "records": [],
    }


def _sample_fin_data_sga_proxy():
    data = _sample_fin_data()
    for row in data["cashflow"]:
        row["cash_paid_employees"] = 0.0
    return data


def _sample_market():
    return {
        "price_rmb": 10.0,
        "price_hkd": 10.0,
        "shares_m": 100.0,
        "mc_rmb": 1000.0,
        "mc_hkd": 1000.0,
        "fx": 1.0,
    }


def _sample_params():
    return {
        "II": 5.5,
        "Rf": 4.0,
        "Q": 0.10,
        "O": 0.0,
        "PORTFOLIO_CAP_PCT": 5.0,
        "g_base": 2.0,
        "b_penalty": 0.25,
        "dps_latest": 0.3,
    }


def test_load_gg_override_normalizes_single_year(tmp_path):
    override_path = tmp_path / "gg_override.json"
    override_path.write_text(json.dumps({
        "source_year": 2025,
        "direct_labor_cost": 320.0,
        "admin_labor_cost": 100.0,
        "sales_labor_cost": 50.0,
        "rd_labor_cost": 20.0,
        "total_labor_cost": 490.0,
        "notes_basis": "职工薪酬附注按职能披露",
        "confidence": "high",
        "source_pages": [120, 121],
    }, ensure_ascii=False))

    override = load_gg_override(str(tmp_path))

    assert override is not None
    assert "2025" in override["years"]
    assert override["years"]["2025"]["direct_labor_cost"] == 320.0
    assert override["years"]["2025"]["rd_labor_cost"] == 20.0
    assert override["years"]["2025"]["confidence"] == "high"


def test_load_gg_override_derives_total_labor_from_components(tmp_path):
    override_path = tmp_path / "gg_override.json"
    override_path.write_text(json.dumps({
        "source_year": 2025,
        "direct_labor_cost": 320.0,
        "admin_labor_cost": 100.0,
        "sales_labor_cost": 50.0,
        "rd_labor_cost": 20.0,
        "notes_basis": "legacy file without total_labor_cost",
    }, ensure_ascii=False))

    override = load_gg_override(str(tmp_path))

    assert override is not None
    assert override["years"]["2025"]["total_labor_cost"] == 490.0


def test_normalized_aa_subtracts_maintenance_capex_shortfall():
    assert _normalized_aa_value(100.0, 10.0, 40.0) == 70.0
    assert _normalized_aa_value(20.0, 10.0, 40.0) == 0.0


def test_fcfe_exposes_raw_and_distributed_return_identities():
    result = compute_factor3(_sample_fin_data(), _sample_market(), _sample_params())
    fcfe = result["gg_fcfe"]
    assert fcfe["base_semantics"] == "distributed_fcfe_owner_return_pct"
    assert fcfe["fcfe_yield_pct"] == 10.0
    assert fcfe["distributed_fcfe_yield_pct"] == fcfe["base"] == 5.0


def test_compute_factor3_prefers_pdf_override_for_direct_labor():
    override = {
        "years": {
            "2023": {"direct_labor_cost": 300.0, "confidence": "high", "notes_basis": "note"},
            "2024": {"direct_labor_cost": 300.0, "confidence": "high", "notes_basis": "note"},
            "2025": {"direct_labor_cost": 300.0, "confidence": "high", "notes_basis": "note"},
        }
    }

    result = compute_factor3(
        _sample_fin_data(),
        _sample_market(),
        _sample_params(),
        gg_override=override,
    )

    assert result["gg_labor_source"] == "pdf_override"
    assert result["gg_labor_confidence"] == "high"
    assert result["gg_override_applied"] is True
    assert result["gg_override_years"] == ["2023", "2024", "2025"]
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["source"] == "pdf_override"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["direct_labor_cost"] == 300.0


def test_compute_factor3_derives_direct_labor_from_note_sga_and_db_total():
    override = {
        "years": {
            "2023": {"admin_labor_cost": 100.0, "sales_labor_cost": 50.0, "rd_labor_cost": 20.0, "confidence": "medium", "notes_basis": "note"},
            "2024": {"admin_labor_cost": 100.0, "sales_labor_cost": 50.0, "rd_labor_cost": 20.0, "confidence": "medium", "notes_basis": "note"},
            "2025": {"admin_labor_cost": 100.0, "sales_labor_cost": 50.0, "rd_labor_cost": 20.0, "confidence": "medium", "notes_basis": "note"},
        }
    }

    result = compute_factor3(
        _sample_fin_data(),
        _sample_market(),
        _sample_params(),
        gg_override=override,
    )

    assert result["gg_labor_source"] == "hybrid_override"
    assert result["gg_labor_confidence"] == "medium"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["source"] == "hybrid_override"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["direct_labor_cost"] == 330.0


def test_compute_factor3_uses_pdf_total_labor_when_sga_proxy_would_otherwise_drop_labor():
    override = {
        "years": {
            "2023": {"direct_labor_cost": 300.0, "total_labor_cost": 470.0, "confidence": "high", "notes_basis": "note"},
            "2024": {"direct_labor_cost": 300.0, "total_labor_cost": 470.0, "confidence": "high", "notes_basis": "note"},
            "2025": {"direct_labor_cost": 300.0, "total_labor_cost": 470.0, "confidence": "high", "notes_basis": "note"},
        }
    }

    base = compute_factor3(
        _sample_fin_data_sga_proxy(),
        _sample_market(),
        _sample_params(),
        gg_override=None,
    )
    result = compute_factor3(
        _sample_fin_data_sga_proxy(),
        _sample_market(),
        _sample_params(),
        gg_override=override,
    )

    assert result["gg_labor_source"] == "pdf_override"
    assert result["w_breakdown"]["W2_source"] == "SGA_proxy+pdf_total_labor_override"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["source"] == "pdf_override"
    assert result["w_breakdown"]["w2_override_years"]["2025"]["source"] == "pdf_total_labor_override"
    assert result["w_breakdown"]["W2_employee_avg"] == 470.0
    assert abs(result["aa_avg"]["3y"] - base["aa_avg"]["3y"]) < 1e-9
    assert abs(
        (result["w_breakdown"]["W1_supplier_avg"] + result["w_breakdown"]["W2_employee_avg"])
        - (base["w_breakdown"]["W1_supplier_avg"] + base["w_breakdown"]["W2_employee_avg"])
    ) < 1e-9


def test_compute_factor3_falls_back_to_industry_heuristic_without_override():
    result = compute_factor3(
        _sample_fin_data(),
        _sample_market(),
        _sample_params(),
    )

    assert result["gg_labor_source"] == "industry_heuristic"
    assert result["gg_labor_confidence"] == "medium"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["source"] == "industry_heuristic"
    assert result["w_breakdown"]["w1_dedup_years"]["2025"]["direct_labor_cost"] == 330.0


def test_compute_factor3_marks_total_only_report_as_capability_limit():
    result = compute_factor3(
        _sample_fin_data_sga_proxy(),
        _sample_market(),
        _sample_params(),
        labor_disclosure_summary={
            "years_with_total_only": ["2025"],
            "years_with_function_split": [],
            "years_with_no_labor_disclosure": ["2023", "2024"],
        },
    )

    assert result["gg_labor_source"] == "db_proxy"
    assert result["gg_labor_capability"] == "annual_report_total_only"
    assert result["gg_override_applied"] is False
    assert result["w_breakdown"]["annual_report_total_only_years"] == ["2025"]
