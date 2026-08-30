from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.valuation_archetypes import (
    load_valuation_archetype,
    resolve_valuation_archetype,
    validate_valuation_archetype,
    validate_valuation_archetype_registry,
)


ROOT = Path(__file__).resolve().parents[1]
CARD_PATH = ROOT / "knowledge" / "valuation_archetypes" / "property_service.v1.json"
SCHEMA_PATH = ROOT / "schemas" / "valuation_archetype.schema.json"
PROPERTY_SERVICE_COMPONENT_TYPES = {
    "CUSTOMER_RELATIONSHIP",
    "REGIONAL_OPERATING_ORGANIZATION",
    "CUSTOMER_ACQUISITION_CHANNEL",
    "FULFILLMENT_OR_PROJECT_TRACK_RECORD",
    "PROJECT_STARTUP_WORKING_CAPITAL",
    "OTHER_FUNCTIONAL_ASSET",
}


def _card() -> dict:
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def test_property_service_card_is_a_valid_non_parameterized_template() -> None:
    card = _card()
    validation = validate_valuation_archetype(card)

    assert validation == {
        "schema_version": "valuation-archetype-validation.v1",
        "state": "VALID",
        "status": "PASS",
        "findings": [],
    }
    assert card["card_id"] == "VALUATION_ARCHETYPE:property_service:v1"
    assert "label" not in card
    assert "route" not in card
    assert {item["component_type"] for item in card["components"]} == PROPERTY_SERVICE_COMPONENT_TYPES
    assert {item["presence_requirement"] for item in card["components"]} == {"REQUIRED"}
    assert all(item["required_evidence_roles"] for item in card["components"])
    assert all("allowed_exclusion_destinations" in item for item in card["components"])
    exclusions = {
        item["component_type"]: item["allowed_exclusion_destinations"]
        for item in card["components"]
    }
    assert exclusions["CUSTOMER_RELATIONSHIP"] == []
    assert exclusions["CUSTOMER_ACQUISITION_CHANNEL"] == ["OTHER_REPLACEMENT_COMPONENT"]
    assert exclusions["PROJECT_STARTUP_WORKING_CAPITAL"] == [
        "BALANCE_SHEET_WORKING_CAPITAL",
        "EPV_MAINTENANCE_NEED",
    ]
    assert all(item["allowed_calculation_methods"] for item in card["components"])
    assert all(item["double_count_owner"] for item in card["components"])


def test_schema_accepts_the_card_shape() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator(schema).validate(_card())


def test_registry_resolves_only_an_exact_versioned_card() -> None:
    registry = validate_valuation_archetype_registry()
    loaded = load_valuation_archetype("property_service", "v1")
    resolved = resolve_valuation_archetype("property_service", "v1")

    assert registry["state"] == "VALID"
    assert loaded["card_id"] == "VALUATION_ARCHETYPE:property_service:v1"
    assert resolved["state"] == "RESOLVED"
    assert resolved["archetype_id"] == "property_service"
    assert resolved["version"] == "v1"
    assert resolved["status"] == "ACTIVE"
    assert resolved["required_component_specs"] == loaded["components"]
    assert "company_id" not in resolved
    assert "route" not in resolved


def test_component_types_are_generic_to_the_card_not_hardcoded_to_property_services() -> None:
    card = _card()
    card["archetype_id"] = "mature_manufacturing"
    card["version"] = "v2"
    card["card_id"] = "VALUATION_ARCHETYPE:mature_manufacturing:v2"
    card["components"] = [card["components"][0]]
    card["components"][0]["component_type"] = "PROCESS_QUALIFICATION"
    card["components"][0]["double_count_owner"] = "CUSTOMER_CERTIFICATION_COMPONENT"

    assert validate_valuation_archetype(card)["state"] == "VALID"


@pytest.mark.parametrize(
    ("mutate", "expected_finding"),
    [
        (
            lambda card: card["components"][0].update({"default_haircut": 0.5}),
            "$.components[0].default_haircut:numeric_value_forbidden",
        ),
        (
            lambda card: card["components"][0].update({"requirement": "Recognize 50% of the rebuild."}),
            "$.components[0].requirement:percentage_or_multiple_text_forbidden",
        ),
        (
            lambda card: card.update({"valuation_multiple": "company default"}),
            "$:forbidden_parameter_field:valuation_multiple",
        ),
    ],
)
def test_validator_rejects_numeric_or_parameterized_content(mutate, expected_finding: str) -> None:
    card = deepcopy(_card())
    mutate(card)

    findings = validate_valuation_archetype(card)["findings"]

    assert expected_finding in findings


def test_validator_requires_structured_presence_requirement() -> None:
    card = deepcopy(_card())
    card["components"][0].pop("presence_requirement")

    findings = validate_valuation_archetype(card)["findings"]

    assert "components[0]:presence_requirement_invalid" in findings
