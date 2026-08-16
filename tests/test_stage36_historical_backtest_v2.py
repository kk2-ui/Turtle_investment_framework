from __future__ import annotations

from copy import deepcopy

from scripts.historical_backtest import (
    CASE_SCHEMA_VERSION_V2,
    SETTLEMENT_SCHEMA_VERSION_V2,
    validate_case,
    validate_settlement,
)
from tests.test_stage36_historical_backtest_pilot import _case, _settlement


def _v2_case() -> dict:
    case = deepcopy(_case())
    case["schema_version"] = CASE_SCHEMA_VERSION_V2
    for claim in case["calibration_ledger"]["claims"]:
        outcome = claim["observable_outcome"]
        start = outcome.pop("period_start")
        end = outcome.pop("period_end")
        outcome["measurement_period"] = {
            "kind": "REPORTING_PERIOD",
            "start": start,
            "end": end,
        }
        outcome["observation_window"] = {
            "opens_after": "2021-08-31T18:00:00+08:00",
            "closes_at": "2022-08-31T18:00:00+08:00",
        }
    return case


def _v2_settlement() -> dict:
    settlement = deepcopy(_settlement())
    settlement["schema_version"] = SETTLEMENT_SCHEMA_VERSION_V2
    for source in settlement["actual_sources"]:
        source["content_access"] = "BODY_READ"
    for observation in settlement["actual_outcomes"]["operating_observations"]:
        start = observation.pop("period_start")
        end = observation.pop("period_end")
        observation["measurement_period"] = {
            "kind": "REPORTING_PERIOD",
            "start": start,
            "end": end,
        }
    return settlement


def test_v2_accepts_reporting_period_separate_from_post_freeze_window() -> None:
    case = _v2_case()
    settlement = _v2_settlement()

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"


def test_v2_rejects_metadata_only_or_window_outside_operating_observations() -> None:
    case = _v2_case()
    metadata_only = _v2_settlement()
    metadata_only["actual_sources"][0]["content_access"] = "METADATA_ONLY"
    result = validate_settlement(metadata_only, case=case)
    assert "actual_outcomes.operating_observations[0]:source_body_not_read:AR:00506:2021" in result["invalid_findings"]

    window_outside = _v2_settlement()
    case["calibration_ledger"]["claims"][0]["observable_outcome"]["observation_window"]["closes_at"] = "2022-03-24T18:00:00+08:00"
    result = validate_settlement(window_outside, case=case)
    assert "actual_outcomes.operating_observations[0]:source_published_after_observation_window:AR:00506:2021" in result["invalid_findings"]


def test_v2_event_window_requires_an_in_window_event_period_but_not_report_period_end() -> None:
    case = _v2_case()
    outcome = case["calibration_ledger"]["claims"][0]["observable_outcome"]
    outcome["measurement_period"] = {
        "kind": "EVENT_WINDOW",
        "start": "2022-03-25",
        "end": "2022-03-25",
    }
    outcome["allowed_source_types"] = ["ANNUAL_REPORT"]
    settlement = _v2_settlement()
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation["measurement_period"] = deepcopy(outcome["measurement_period"])
    observation["event_period"] = {"start": "2022-03-25", "end": "2022-03-25"}
    settlement["actual_sources"][0].update({
        "source_type": "ANNUAL_REPORT",
        "data_as_of": "2021-12-31",
    })

    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    outside_event_period = deepcopy(settlement)
    outside_event_period["actual_outcomes"]["operating_observations"][0]["event_period"] = {
        "start": "2022-03-24", "end": "2022-03-25",
    }
    result = validate_settlement(outside_event_period, case=case)
    assert "actual_outcomes.operating_observations[0].event_period:starts_before_frozen_measurement_period" in result["invalid_findings"]
