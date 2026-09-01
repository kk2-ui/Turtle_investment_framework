"""Targeted tests for the offline cutoff official-fact locator validator."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.cutoff_official_fact_register import main, validate_fact_register


def _register() -> dict:
    observations = []
    for source_id, period in (("AR2015", "FY2015"), ("AR2016", "FY2016")):
        for field, page, unit in (("revenue", 18, "CNY million"), ("volume", 21, "tonnes")):
            observations.append({
                "source_id": source_id,
                "pdf_page": page,
                "table_or_section": "Management discussion / operating data",
                "field": field,
                "period": period,
                "responsibility_boundary": "consolidated continuing operations",
                "unit": unit,
            })
    return {
        "schema_version": "turtle-cutoff-official-fact-register.v1",
        "cutoff_at": "2018-04-30T23:59:59+08:00",
        "sources": [
            {
                "source_id": "AR2015",
                "static_url": "https://disclosure.example.gov/finalpage/annual-2015.pdf",
                "available_at": "2016-04-28",
                "declared_pages": 100,
            },
            {
                "source_id": "AR2016",
                "static_url": "https://disclosure.example.gov/finalpage/annual-2016.PDF",
                "available_at": "2017-03-10T08:00:00+08:00",
                "declared_pages": 110,
            },
        ],
        "observations": observations,
        "required_series": [
            {
                "series_id": "revenue_history",
                "fields": ["revenue"],
                "periods": ["FY2015", "FY2016"],
                "responsibility_boundary": "consolidated continuing operations",
                "unit": "CNY million",
            },
            {
                "series_id": "volume_history",
                "fields": ["volume"],
                "periods": ["FY2015", "FY2016"],
            },
        ],
    }


def test_valid_register_binds_every_fact_to_a_pre_cutoff_static_pdf_page() -> None:
    result = validate_fact_register(_register())

    assert result == {"valid": True, "findings": [], "source_count": 2, "observation_count": 4}


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (lambda item: item["sources"][0].update(static_url="http://example.gov/a.pdf"),
         "register.sources[0].static_url_must_be_static_https_pdf"),
        (lambda item: item["sources"][0].update(static_url="https://example.gov/download?id=1"),
         "register.sources[0].static_url_must_be_static_https_pdf"),
        (lambda item: item["sources"][0].update(static_url="https://example.gov/a.pdf?token=changing"),
         "register.sources[0].static_url_must_be_static_https_pdf"),
        (lambda item: item["sources"][0].update(available_at="2018-04-30T23:59:59+08:00"),
         "register.sources[0].available_at_not_before_cutoff"),
        (lambda item: item["sources"][0].update(declared_pages=True),
         "register.sources[0].declared_pages_must_be_positive_integer"),
    ],
)
def test_source_contract_rejects_nonstatic_or_non_pre_cutoff_sources(mutation, finding: str) -> None:
    register = _register()
    mutation(register)

    result = validate_fact_register(register)

    assert result["valid"] is False
    assert finding in result["findings"]


@pytest.mark.parametrize("field", [
    "source_id", "table_or_section", "field", "period", "responsibility_boundary", "unit",
])
def test_every_observation_requires_source_and_measurement_boundary_fields(field: str) -> None:
    register = _register()
    register["observations"][0][field] = ""

    result = validate_fact_register(register)

    assert result["valid"] is False
    assert f"register.observations[0].{field}_required" in result["findings"]


def test_observation_rejects_unknown_source_nonpositive_and_out_of_range_pages() -> None:
    register = _register()
    register["observations"][0]["source_id"] = "UNKNOWN"
    register["observations"][1]["pdf_page"] = 0
    register["observations"][2]["pdf_page"] = 111

    result = validate_fact_register(register)

    assert result["valid"] is False
    assert "register.observations[0].source_id_unknown:UNKNOWN" in result["findings"]
    assert "register.observations[1].pdf_page_must_be_positive_integer" in result["findings"]
    assert "register.observations[2].pdf_page_exceeds_source_declared_pages:111>110" in result["findings"]


def test_required_series_reports_each_missing_field_period_pair_with_boundary_matching() -> None:
    register = _register()
    register["observations"] = [
        observation for observation in register["observations"]
        if not (observation["field"] == "revenue" and observation["period"] == "FY2016")
    ]
    wrong_boundary = deepcopy(register["observations"][0])
    wrong_boundary["period"] = "FY2016"
    wrong_boundary["responsibility_boundary"] = "parent only"
    register["observations"].append(wrong_boundary)

    result = validate_fact_register(register)

    assert result["valid"] is False
    assert (
        "register.required_series[0].missing_observation:revenue_history:revenue:FY2016"
        in result["findings"]
    )


def test_cli_emits_json_and_returns_validation_status(tmp_path, capsys) -> None:
    path = tmp_path / "register.json"
    path.write_text(json.dumps(_register()), encoding="utf-8")
    assert main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    register = _register()
    register["observations"][0]["pdf_page"] = 101
    path.write_text(json.dumps(register), encoding="utf-8")
    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False


def test_v2_canonical_register_requires_a_stable_fact_id_and_exact_value() -> None:
    register = _register()
    register["schema_version"] = "turtle-cutoff-official-fact-register.v2"
    for index, observation in enumerate(register["observations"]):
        observation["fact_id"] = f"OBS:OFFICIAL:{index}"
        observation["value"] = float(index)

    assert validate_fact_register(register)["valid"] is True

    register["observations"][0].pop("fact_id")
    register["observations"][1]["fact_id"] = "OBS:OFFICIAL:2"
    register["observations"][2]["value"] = {"not": "a disclosed scalar"}
    findings = validate_fact_register(register)["findings"]

    assert "register.observations[0].fact_id_required" in findings
    assert "register.observations[2].fact_id_duplicate:OBS:OFFICIAL:2" in findings
    assert "register.observations[2].value_required" in findings
