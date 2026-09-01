import pandas as pd

from tushare_collector import TushareClient


def test_hk_fallback_cashflow_infers_proxy_marker_from_legacy_payload(tmp_path, monkeypatch):
    client = TushareClient("dummy-token")
    client._store["_output_dir"] = str(tmp_path)
    monkeypatch.setattr(client, "_load_hk_report_fallback", lambda ts_code: {
        "cashflow": [
            {
                "ts_code": "02669.HK",
                "end_date": "20251231",
                "c_pay_to_staff": 4597.62,
                "_employee_benefit_total": 4597.62,
            },
            {
                "ts_code": "02669.HK",
                "end_date": "20241231",
                "c_pay_to_staff": None,
                "_employee_benefit_total": None,
            },
        ]
    })

    df = client._get_hk_report_fallback_df("02669.HK", "cashflow")

    assert "_c_pay_to_staff_is_proxy" in df.columns
    latest = df.loc[df["end_date"] == "20251231"].iloc[0]
    prior = df.loc[df["end_date"] == "20241231"].iloc[0]
    assert latest["_c_pay_to_staff_is_proxy"] == 1.0
    assert prior["_c_pay_to_staff_is_proxy"] == 0.0


def test_hk_w2_ignores_employee_cost_proxy_and_falls_back_to_sga():
    client = TushareClient("dummy-token")
    client._store["income"] = pd.DataFrame([
        {
            "end_date": "20251231",
            "oper_cost": 13848.85 * 1_000_000,
            "sell_exp": 0.0,
            "admin_exp": 458.54 * 1_000_000,
            "rd_exp": 0.0,
            "finance_exp": 8.12 * 1_000_000,
            "income_tax": 490.61 * 1_000_000,
            "revenue": 16296.99 * 1_000_000,
        },
        {
            "end_date": "20241231",
            "oper_cost": 12868.88 * 1_000_000,
            "sell_exp": 0.0,
            "admin_exp": 475.67 * 1_000_000,
            "rd_exp": 0.0,
            "finance_exp": 9.32 * 1_000_000,
            "income_tax": 535.87 * 1_000_000,
            "revenue": 15422.78 * 1_000_000,
        },
    ])
    client._store["balance_sheet"] = pd.DataFrame([
        {
            "end_date": "20251231",
            "acct_payable": 2866.23 * 1_000_000,
            "defer_tax_assets": 122.79 * 1_000_000,
            "defer_tax_liab": 11.22 * 1_000_000,
        },
        {
            "end_date": "20241231",
            "acct_payable": 2688.12 * 1_000_000,
            "defer_tax_assets": 62.91 * 1_000_000,
            "defer_tax_liab": 24.35 * 1_000_000,
        },
    ])
    client._store["cashflow"] = pd.DataFrame([
        {
            "end_date": "20251231",
            "c_pay_to_staff": 4597.62 * 1_000_000,
            "_c_pay_to_staff_is_proxy": 1.0,
        }
    ])

    text = client._compute_factor3_step4()

    assert text is not None
    assert "458.54" in text
    assert "4,597.62" not in text
    assert "† W2" in text
