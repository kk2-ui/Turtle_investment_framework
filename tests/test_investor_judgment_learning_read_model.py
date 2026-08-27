from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.investor_judgment_learning_read_model import (
    build_learning_read_model,
    validate_learning_read_model,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1_MANIFEST.json"
STATUS_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1.json"


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _read_model(manifest: dict | None = None) -> dict:
    return build_learning_read_model(
        manifest or _manifest(),
        repo_root=ROOT,
        manifest_ref=str(MANIFEST_PATH.relative_to(ROOT)),
    )


def _round(read_model: dict, round_id: str) -> dict:
    return next(item for item in read_model["evidence_inventory"] if item["round_id"] == round_id)


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_keys(child))
        return result
    return set()


def test_current_status_stops_at_l1_without_hiding_real_company_findings() -> None:
    read_model = _read_model()

    assert validate_learning_read_model(read_model) == {"valid": True, "findings": []}
    assert read_model["current_ceiling"]["strict_validation_level"] == "L1"
    assert read_model["current_ceiling"]["next_unmet_level"] == "L2"
    assert read_model["evidence_counts"]["recorded_company_cutoff_settlements"] == 5
    assert all(item["strict_level_ceiling"] == "L1" for item in read_model["evidence_inventory"])
    level4 = next(item for item in read_model["validation_ladder"] if item["level"] == "L4")
    assert level4["status"].startswith("NOT_ESTABLISHED")


def test_round5_local_material_change_remains_visible_without_transfer_claim() -> None:
    round5 = _round(_read_model(), "ROUND5")

    assert round5["company_finding"]["status"] == "ACCEPTED_LOCAL_FINDING"
    assert "Do not credit Furun" in round5["company_finding"]["statement"]
    assert round5["method_utility"]["status"] == "NOT_EVALUATED"
    assert round5["transfer_evidence"]["status"] == "NOT_EVALUATED"


def test_round8_no_advantage_is_valid_negative_evidence_not_method_success() -> None:
    round8 = _round(_read_model(), "ROUND8")

    assert round8["method_utility"]["status"] == "NO_ADVANTAGE_PROVED"
    assert round8["transfer_evidence"]["status"] == "NOT_ESTABLISHED"
    assert "POSITIVE" not in round8["method_utility"]["status"]
    assert "Enhanced method" not in round8["company_finding"]["statement"]
    assert "parcel volume" in round8["company_finding"]["statement"]


def test_round9_invalidation_cannot_become_method_or_transfer_evidence() -> None:
    round9 = _round(_read_model(), "ROUND9")

    assert round9["pipeline_proof"]["status"] == "ACCEPTED"
    assert round9["company_finding"]["status"] == "ACCEPTED_OUTCOME_FINDING"
    assert round9["method_utility"]["status"] == "INVALIDATED"
    assert round9["transfer_evidence"]["status"] == "INVALIDATED"
    assert "METHOD_FEEDBACK_COMPLETED" in round9["invalidated_evidence"]["prohibited_claims"]
    assert "method comparison" not in round9["company_finding"]["statement"]
    assert "Ordinary-share owner cash remains UNKNOWN" in round9["company_finding"]["statement"]


def test_unknown_mixed_and_measurement_mismatch_stay_in_the_denominator() -> None:
    denominator = _read_model()["preserved_denominator"]
    measurement = denominator["measurement_cells"]["status_counts"]
    diagnostic = denominator["diagnostic_findings"]["status_counts"]

    assert measurement["UNKNOWN"] > 0
    assert measurement["MEASUREMENT_MISMATCH"] > 0
    assert diagnostic["MIXED"] > 0
    assert diagnostic["NOT_DIAGNOSTIC"] > 0


def test_missing_independent_review_prevents_method_and_transfer_elevation() -> None:
    manifest = deepcopy(_manifest())
    round6 = next(item for item in manifest["entries"] if item["round_id"] == "ROUND6")
    round6["independent_review_artifact"] = ""

    projected = _round(_read_model(manifest), "ROUND6")

    assert projected["independent_review_present"] is False
    assert projected["method_utility"]["status"] == "UNREVIEWED"
    assert projected["transfer_evidence"]["status"] == "UNREVIEWED"

    round8 = next(item for item in manifest["entries"] if item["round_id"] == "ROUND8")
    round8["independent_review_artifact"] = ""
    read_model = _read_model(manifest)
    projected = _round(read_model, "ROUND8")
    assert validate_learning_read_model(read_model) == {"valid": True, "findings": []}
    assert projected["company_finding"]["status"] == "UNREVIEWED"
    assert projected["method_utility"]["status"] == "UNREVIEWED"


def test_all_downstream_rights_remain_closed_and_no_total_judgment_ranking_exists() -> None:
    read_model = _read_model()

    assert set(read_model["rights"].values()) == {"NOT_AUTHORIZED"}
    assert all(set(item["rights"].values()) == {"NOT_AUTHORIZED"} for item in read_model["evidence_inventory"])
    assert not ({"score", "judgment_score", "total_score", "rank"} & _keys(read_model))
    assert read_model["aggregation_policy"] == "COUNTS_AND_EVIDENCE_CLASSES_ONLY_NO_TOTAL_RANKING"


def test_checked_in_status_is_the_deterministic_projection() -> None:
    expected = json.loads(STATUS_PATH.read_text(encoding="utf-8"))

    assert expected == _read_model()


def test_schema_declares_closed_rights_and_l1_ceiling() -> None:
    schema = json.loads(
        (ROOT / "schemas/investor_judgment_learning_read_model.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["current_ceiling"]["properties"]["strict_validation_level"]["const"] == "L1"
    assert schema["$defs"]["closedRights"]["properties"]["investment"]["const"] == "NOT_AUTHORIZED"
