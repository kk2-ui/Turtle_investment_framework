from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

from scripts.outcome_acquisition import (
    OUTCOME_EXTRACTION_SCHEMA_VERSION,
    OUTCOME_PACKAGE_SCHEMA_VERSION,
    acquire_outcome_package,
    read_outcome_package,
    validate_outcome_extraction,
    validate_outcome_package,
    validate_settlement_outcome_acquisition,
)
from scripts.historical_backtest import validate_settlement
from tests.test_stage36_historical_backtest_v2 import (
    _company_judgment_case,
    _company_judgment_early_settlement,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def test_outcome_extraction_rejects_a_number_not_present_in_the_read_source() -> None:
    # A changed value without a changed source quote cannot enter a settlement.
    case = _company_judgment_case()
    case["calibration_ledger"]["claims"][0]["observable_outcome"]["publisher_domains"] = ["issuer.example.com"]
    settlement = _company_judgment_early_settlement()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT, prefix="p34-outcome-") as directory:
        root = Path(directory)
        (root / "raw").mkdir()
        (root / "reader").mkdir()
        (root / "raw" / "fy2021.html").write_text("<html><body>ordinary-share owner cash per share was 0.18 HKD/share. Revenue per share was 0.30 HKD/share.</body></html>", encoding="utf-8")
        (root / "reader" / "fy2021.md").write_text("# FY2021 annual report\n\nordinary-share owner cash per share was 0.18 HKD/share. Revenue per share was 0.30 HKD/share.\n", encoding="utf-8")
        source = {
            "source_id": "AR:00506:2021",
            "source_type": "ANNUAL_REPORT",
            "official": True,
            "published_at": "2022-03-25T10:00:00+08:00",
            "source_version": "annual-report-original-2021",
            "data_as_of": "2021-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "official_publisher_domain": "issuer.example.com",
            "package_path": "raw/fy2021.html",
            "reader_text_path": "reader/fy2021.md",
        }
        manifest = {
            "schema_version": OUTCOME_PACKAGE_SCHEMA_VERSION,
            "outcome_package_id": "OUTPKG:TEST:FY2021",
            "case_id": case["case_id"],
            "freeze_id": case["report_freeze"]["freeze_id"],
            "frozen_cutoff": case["simulation_cutoff"],
            "enumeration": {
                "status": "COMPLETE",
                "query_identity": "issuer annual-report archive FY2021 through 2022-08-31",
                "source_ids": [source["source_id"]],
            },
            "inventory": [source],
            "selected_source_ids": [source["source_id"]],
            "source_package_status": "COMPLETE",
        }
        assert validate_outcome_package(
            manifest, root, case=case, settlement_as_of=settlement["settlement_as_of"],
        )["state"] == "REVIEWABLE"
        attestation = read_outcome_package(
            manifest, root, case=case, settlement_as_of=settlement["settlement_as_of"],
        )
        assert attestation["state"] == "REVIEWABLE"
        observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
        observation.update({
            "reported_file_scope": "FY2021 annual report",
            "reported_label": "ordinary-share owner cash per share",
            "reported_locator": "cash conversion table",
            "reported_text": "ordinary-share owner cash per share was 0.18 HKD/share.",
            "reported_value_text": "0.18 HKD/share",
        })
        extraction = {
            "schema_version": OUTCOME_EXTRACTION_SCHEMA_VERSION,
            "outcome_package_id": manifest["outcome_package_id"],
            "case_id": case["case_id"],
            "freeze_id": case["report_freeze"]["freeze_id"],
            "settlement_as_of": settlement["settlement_as_of"],
            "observations": [observation],
        }
        assert validate_outcome_extraction(
            extraction, manifest=manifest, package_root=root, read_attestation=attestation,
            case=case, settlement_as_of=settlement["settlement_as_of"],
        )["state"] == "REVIEWABLE"
        tampered = deepcopy(extraction)
        tampered["observations"][0]["value"] = 0.30
        result = validate_outcome_extraction(
            tampered, manifest=manifest, package_root=root, read_attestation=attestation,
            case=case, settlement_as_of=settlement["settlement_as_of"],
        )
        assert "observations[0]:value_does_not_match_reported_value_text" in result["invalid_findings"]
        wrong_row = deepcopy(extraction)
        wrong_row["observations"][0].update({
            "value": 0.30,
            "reported_text": "Revenue per share was 0.30 HKD/share.",
            "reported_value_text": "0.30 HKD/share",
        })
        result = validate_outcome_extraction(
            wrong_row, manifest=manifest, package_root=root, read_attestation=attestation,
            case=case, settlement_as_of=settlement["settlement_as_of"],
        )
        assert "observations[0]:reported_label_not_found_in_reported_text" in result["invalid_findings"]
        wrong_domain = deepcopy(manifest)
        wrong_domain["inventory"][0]["official_publisher_domain"] = "proxy.example.com"
        result = validate_outcome_extraction(
            extraction, manifest=wrong_domain, package_root=root, read_attestation=attestation,
            case=case, settlement_as_of=settlement["settlement_as_of"],
        )
        assert "observations[0]:publisher_domain_does_not_match_frozen_contract:AR:00506:2021" in result["invalid_findings"]


def test_outcome_acquirer_retains_unselected_inventory_but_materializes_selected_web_release() -> None:
    case = _company_judgment_case()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT, prefix="p34-acquire-") as directory:
        root = Path(directory)
        selected = {
            "source_id": "IR:00506:FY2021", "source_type": "OTHER_OFFICIAL", "official": True,
            "published_at": "2022-03-25T10:00:00+08:00", "source_version": "issuer-release-fy2021",
            "data_as_of": "2021-12-31", "revision_policy": "ORIGINAL_VINTAGE",
            "acquisition_kind": "OFFICIAL_WEB_RELEASE", "content_format": "HTML",
            "url": "https://issuer.example.com/fy2021", "release_id": "FY2021",
            "publisher_name": "Issuer", "official_publisher_domain": "issuer.example.com",
        }
        unselected = {
            "source_id": "IR:00506:FY2021:TRANSCRIPT", "source_type": "OTHER_OFFICIAL", "official": True,
            "published_at": "2022-03-25T11:00:00+08:00", "source_version": "issuer-transcript-fy2021",
            "data_as_of": "2021-12-31", "revision_policy": "ORIGINAL_VINTAGE",
        }
        manifest = {
            "schema_version": OUTCOME_PACKAGE_SCHEMA_VERSION, "outcome_package_id": "OUTPKG:TEST:ACQUIRE",
            "case_id": case["case_id"], "freeze_id": case["report_freeze"]["freeze_id"],
            "frozen_cutoff": case["simulation_cutoff"],
            "enumeration": {"status": "COMPLETE", "query_identity": "issuer archive export", "source_ids": [selected["source_id"], unselected["source_id"]]},
            "inventory": [selected, unselected], "selected_source_ids": [selected["source_id"]], "source_package_status": "INCOMPLETE",
        }
        acquired = acquire_outcome_package(
            manifest, root, downloader=lambda _: b"<html><body>FY2021 annual release</body></html>",
        )
        assert acquired["source_package_status"] == "COMPLETE"
        by_id = {item["source_id"]: item for item in acquired["inventory"]}
        assert by_id[selected["source_id"]]["package_acquisition_status"] == "ADMITTED_PACKAGE"
        assert "package_path" not in by_id[unselected["source_id"]]
        assert validate_outcome_package(
            acquired, root, case=case, settlement_as_of="2022-08-31T18:00:00+08:00",
        )["state"] == "REVIEWABLE"


def test_settlement_binding_rejects_a_hand_edited_actual_value() -> None:
    # This is an integration test because the validator deliberately reads the
    # outcome artifacts rather than trusting a field copied into settlement.
    case = _company_judgment_case()
    settlement = _company_judgment_early_settlement()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT, prefix="p34-binding-") as directory:
        root = Path(directory)
        (root / "raw").mkdir()
        (root / "reader").mkdir()
        (root / "raw" / "fy2021.html").write_text("<html>ordinary-share owner cash per share: 0.18 HKD/share. Transactions only: metric definition changed.</html>", encoding="utf-8")
        (root / "reader" / "fy2021.md").write_text("ordinary-share owner cash per share: 0.18 HKD/share. Transactions only: metric definition changed.", encoding="utf-8")
        source = {
            "source_id": "AR:00506:2021", "source_type": "ANNUAL_REPORT", "official": True,
            "published_at": "2022-03-25T10:00:00+08:00", "source_version": "annual-report-original-2021",
            "data_as_of": "2021-12-31", "revision_policy": "ORIGINAL_VINTAGE",
            "package_path": "raw/fy2021.html", "reader_text_path": "reader/fy2021.md",
        }
        manifest = {
            "schema_version": OUTCOME_PACKAGE_SCHEMA_VERSION, "outcome_package_id": "OUTPKG:TEST:BOUND",
            "case_id": case["case_id"], "freeze_id": case["report_freeze"]["freeze_id"],
            "frozen_cutoff": case["simulation_cutoff"],
            "enumeration": {"status": "COMPLETE", "query_identity": "issuer archive", "source_ids": [source["source_id"]]},
            "inventory": [source], "selected_source_ids": [source["source_id"]], "source_package_status": "COMPLETE",
        }
        attestation = read_outcome_package(manifest, root, case=case, settlement_as_of=settlement["settlement_as_of"])
        observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
        observation.update({
            "reported_file_scope": "FY2021 annual report", "reported_label": "ordinary-share owner cash per share",
            "reported_locator": "cash conversion table", "reported_text": "ordinary-share owner cash per share: 0.18 HKD/share",
            "reported_value_text": "0.18 HKD/share",
        })
        extraction = {
            "schema_version": OUTCOME_EXTRACTION_SCHEMA_VERSION, "outcome_package_id": manifest["outcome_package_id"],
            "case_id": case["case_id"], "freeze_id": case["report_freeze"]["freeze_id"],
            "settlement_as_of": settlement["settlement_as_of"], "observations": [observation],
        }
        for name, payload in (("manifest.json", manifest), ("attestation.json", attestation), ("extraction.json", extraction)):
            (root / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        settlement["actual_sources"][0].update({
            "published_at": source["published_at"], "revision_policy": source["revision_policy"],
        })
        settlement["actual_outcomes"]["operating_observations"][0] = {
            key: value for key, value in observation.items() if key not in {"reported_text", "reported_value_text"}
        }
        binding = {
            "package_root": _relative(root), "manifest_path": _relative(root / "manifest.json"),
            "read_attestation_path": _relative(root / "attestation.json"), "extraction_path": _relative(root / "extraction.json"),
        }
        invalid, incomplete = validate_settlement_outcome_acquisition(binding, settlement=settlement, case=case)
        assert not invalid and not incomplete
        settlement["actual_outcomes"]["operating_observations"][0]["value"] = 0.30
        invalid, incomplete = validate_settlement_outcome_acquisition(binding, settlement=settlement, case=case)
        assert not incomplete
        assert "outcome_acquisition:settlement_observation_payload_mismatch:HBTOBS:owner-cash:FY2021" in invalid

        # A changed definition is still a real, read outcome.  It must close
        # the claim as NOT_CALCULABLE rather than push a made-up replacement
        # number through the comparable-observation route.
        non_diagnostic = deepcopy(extraction)
        non_diagnostic["observations"] = []
        non_diagnostic["non_diagnostic_resolutions"] = [{
            "claim_id": "HBTCLM:owner-cash", "resolution": "MEASUREMENT_MISMATCH",
            "source_ids": [source["source_id"]], "reported_label": "Transactions only",
            "reported_locator": "results table", "reported_text": "Transactions only: metric definition changed.",
        }]
        (root / "extraction.json").write_text(json.dumps(non_diagnostic, ensure_ascii=False), encoding="utf-8")
        mismatch = _company_judgment_early_settlement()
        mismatch["actual_sources"][0].update({
            "published_at": source["published_at"], "revision_policy": source["revision_policy"],
        })
        mismatch["actual_outcomes"]["operating_observations"] = []
        mismatch["model_forecast_error"]["metrics"] = []
        mismatch["model_forecast_error"]["claim_settlements"][0].update({
            "status": "NOT_CALCULABLE", "observation_ids": [],
        })
        invalid, incomplete = validate_settlement_outcome_acquisition(binding, settlement=mismatch, case=case)
        assert not invalid and not incomplete
        mismatch["model_forecast_error"]["claim_settlements"][0]["status"] = "CALCULATED"
        invalid, incomplete = validate_settlement_outcome_acquisition(binding, settlement=mismatch, case=case)
        assert not incomplete
        assert "outcome_acquisition:non_diagnostic_resolution_requires_not_calculable_claim:HBTCLM:owner-cash" in invalid


def test_production_company_judgment_pair_requires_an_outcome_acquisition_binding() -> None:
    # The full case is deliberately a test fixture, so other production
    # findings are expected.  This verifies that a pair cannot evade the new
    # result-input gate merely because its eventual verdict is derived.
    case = _company_judgment_case()
    case["calibration_ledger"]["rival_hypothesis_pairs"] = [{"pair_id": "RHP:fixture"}]
    result = validate_settlement(
        _company_judgment_early_settlement(), case=case, allow_test_fixtures=False,
    )
    assert "outcome_acquisition_missing" in result["incomplete_findings"]
