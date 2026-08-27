import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from compute_bundle import (  # noqa: E402
    _normalized_aa_value,
    compute_factor2,
    compute_factor3,
    compute_factor4,
    load_gg_override,
    load_zone_j_params,
)


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


def test_missing_data_discount_does_not_reduce_gg_point_estimate():
    fin_data = _sample_fin_data()
    for row in fin_data["cashflow"]:
        row["cash_paid_employees"] = 10.0
    params = _sample_params()
    params["_g_coef"] = 1.0

    result = compute_factor3(fin_data, _sample_market(), params)

    assert result["data_discount_used"] == 0.0
    assert result["gg_discounted"] == result["gg"]


def test_missing_normalization_coefficient_does_not_erase_observed_conservative_gg():
    fin_data = _sample_fin_data()
    for row in fin_data["cashflow"]:
        row["cash_paid_employees"] = 10.0
    params = _sample_params()
    assert "_g_coef" not in params

    result = compute_factor3(fin_data, _sample_market(), params)

    assert result["gg_raw"]["aa_based"] == 5.35
    assert result["gg"]["base"] == 5.3
    assert result.get("gg_unavailable") is not True
    assert "gg_normalized" not in result


def test_observed_economic_discount_still_reduces_gg_point_estimate():
    fin_data = _sample_fin_data()
    for row in fin_data["cashflow"]:
        row["cash_paid_employees"] = 10.0
    params = _sample_params()
    params["_g_coef"] = 1.0
    params["total_discount_pct"] = {
        "value": 8,
        "rationale": "observed related-party cash extraction",
        "evidence_ref": ["audit.json:related_party_cash"],
        "confidence": "high",
    }

    result = compute_factor3(fin_data, _sample_market(), params)

    assert result["data_discount_used"] == 8.0
    assert result["gg_discounted"] == {
        key: round(value * 0.92, 1) for key, value in result["gg"].items()
    }


def test_zone_j_loader_ignores_legacy_missing_disclosure_discount(tmp_path):
    (tmp_path / "data_discount.json").write_text(
        json.dumps({"total_discount_pct": 15}), encoding="utf-8"
    )

    assert "total_discount_pct" not in load_zone_j_params(str(tmp_path))


def test_zone_j_loader_accepts_marked_observed_economic_discount(tmp_path):
    (tmp_path / "data_discount.json").write_text(
        json.dumps(
            {
                "discount_basis": "observed_economic_carrier_v1",
                "total_discount_pct": 8,
            }
        ),
        encoding="utf-8",
    )

    assert load_zone_j_params(str(tmp_path))["total_discount_pct"] == 8


def test_zone_j_loader_ignores_legacy_governance_discount(tmp_path):
    (tmp_path / "governance_tension.json").write_text(
        json.dumps({"governance_discount": 5}), encoding="utf-8"
    )

    assert "governance_discount" not in load_zone_j_params(str(tmp_path))


def test_zone_j_loader_requires_observed_carrier_for_governance_discount(tmp_path):
    (tmp_path / "governance_tension.json").write_text(
        json.dumps(
            {
                "discount_basis": "observed_economic_carrier_v1",
                "governance_discount": {"additional_discount_pct": 5},
            }
        ),
        encoding="utf-8",
    )

    assert "governance_discount" not in load_zone_j_params(str(tmp_path))


def test_zone_j_loader_accepts_observed_governance_cash_carrier(tmp_path):
    (tmp_path / "governance_tension.json").write_text(
        json.dumps(
            {
                "discount_basis": "observed_economic_carrier_v1",
                "governance_discount": {
                    "additional_discount_pct": 5,
                    "economic_carrier": {
                        "status": "OBSERVED",
                        "responsibility_unit": "listed parent",
                        "amount_or_range": "RMB 500m",
                        "period": "FY2023-FY2024",
                        "cash_transmission": "cash advanced to controller affiliate remains unavailable",
                        "evidence_ref": ["governance.json:related_party_advance"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_zone_j_params(str(tmp_path))["governance_discount"] == 5


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


def test_compute_factor3_missing_market_cap_keeps_operating_work_and_withholds_gg():
    market = _sample_market()
    market.update({"price_rmb": None, "price_hkd": None, "mc_rmb": 0, "mc_hkd": 0})

    result = compute_factor3(_sample_fin_data(), market, _sample_params())

    assert result["aa_avg"]["3y"] is not None
    assert result["gg"] == {"pessimistic": None, "base": None, "optimistic": None}
    assert result["gg_unavailable"] is True
    assert result["rejection"]["market_cap"] == "unresolved"


def test_compute_factor3_observed_zero_aa_is_negative_gg_not_missing_data():
    result = compute_factor3(_sample_fin_data(), _sample_market(), _sample_params())

    assert result["aa_avg"]["3y"] == 0.0
    assert result["gg_raw"]["aa_based"] == 0.0
    assert result["gg"]["base"] == 0.0
    assert result.get("gg_unavailable") is not True


def test_observed_zero_gg_full_factor_chain_resolves_to_avoid():
    fin_data = _sample_fin_data()
    market = _sample_market()
    params = _sample_params()
    factor2 = compute_factor2(fin_data, market, params)
    params["_g_coef"] = factor2["oe_maintenance_G"]["coefficient"]
    factor3 = compute_factor3(
        fin_data, market, params,
        factor2.get("M"), factor2.get("r_np"), factor2.get("r_np_penetration"),
    )

    factor4 = compute_factor4(factor3, market, params)

    assert factor3["gg"]["base"] == 0.0
    assert factor4["valuation_status"] == "RESOLVED"
    assert factor4["verdict"]["final"] == "AVOID"


def test_factor2_observed_zero_profit_and_owner_earnings_are_not_missing():
    fin_data = _sample_fin_data()
    for row in fin_data["income"]:
        row["n_income_attr_p"] = 0.0
        row["depr_fa_coga_dpba"] = 20.0
    for row in fin_data["cashflow"]:
        row["c_pay_acq_const_fiolta"] = 20.0

    result = compute_factor2(fin_data, _sample_market(), _sample_params())

    assert result["np_avg_3y"] == 0.0
    assert result["oe_avg_3y"] == 0.0
    assert result["r_np"] == 0.0
    assert result["r_oe"] == 0.0
    assert result["r_np_penetration"] == 0.0
    assert result["r_oe_penetration"] == 0.0


def test_factor2_missing_profit_field_is_not_relabelled_as_observed_zero():
    fin_data = _sample_fin_data()
    fin_data["income"][-1]["n_income_attr_p"] = None

    result = compute_factor2(fin_data, _sample_market(), _sample_params())

    assert result["np_avg_3y"] is None
    assert result["r_np"] is None
    assert result["r_np_penetration"] is None


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
