from __future__ import annotations

from scripts import minimal_historical_episode_runner as runner


def test_rmb_revenue_quote_accepts_a_consolidated_statement_note_column() -> None:
    runner._verify_quote_value(
        {
            "exact_quote": "其中：营业收入  六、33  123.45  100.00",
            "numeric_value": 123.45,
            "unit": "RMB",
        },
        source={
            "metric_id": "ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB",
            "responsibility_boundary": "LISTED_CONSOLIDATED_ISSUER",
            "field_ref": "Synthetic consolidated income statement, PDF p. 72, 营业收入.",
        },
    )
