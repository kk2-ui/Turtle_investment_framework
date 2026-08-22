from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.outcome_acquisition import (
    OUTCOME_EXTRACTION_SCHEMA_VERSION,
    OUTCOME_PACKAGE_SCHEMA_VERSION,
    assess_live_forward_acquisition_due,
    build_live_forward_due_inbox,
    read_outcome_package,
    validate_live_forward_outcome_contract,
    validate_outcome_extraction,
    validate_outcome_package,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = (
    {
        "contract": REPO_ROOT / "docs/development/research/experiments/R-05_prospective_operating_feedback/08_outcome_acquisition_contract.json",
        "claim_id": "R05-S1",
        "source_id": "IR:SBUX.US:FY2027Q1_RESULTS",
        "published_at": "2027-02-01T08:00:00-08:00",
        "domain": "investor.starbucks.com",
        "quote": "North America Change in Transactions was 4.5%.",
        "value_text": "4.5%",
    },
    {
        "contract": REPO_ROOT / "docs/development/research/experiments/R-06_prospective_retail_feedback/08_outcome_acquisition_contract.json",
        "claim_id": "R06-S1",
        "source_id": "IR:WMT.US:FY2027Q4_RESULTS",
        "published_at": "2027-02-20T08:00:00-08:00",
        "domain": "corporate.walmart.com",
        "quote": "Walmart U.S. Transactions were 1.5%.",
        "value_text": "1.5%",
    },
)


def _contract_case(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _exercise(contract_case: dict, fixture: dict) -> tuple[dict, dict, dict, dict, Path]:
    claim = next(item for item in contract_case["calibration_ledger"]["claims"] if item["claim_id"] == fixture["claim_id"])
    outcome = claim["observable_outcome"]
    target = outcome["metric_reconstruction_contract"]["source_targets"][0]
    directory = tempfile.TemporaryDirectory(dir=REPO_ROOT, prefix="live-forward-outcome-")
    root = Path(directory.name)
    # Keep the context alive by attaching it to the returned manifest; callers
    # close it after the assertion.  This is a synthetic reader only, not a
    # result-period source and does not alter either experiment's freeze.
    root.joinpath("raw").mkdir()
    root.joinpath("reader").mkdir()
    quote = f"{target['reported_period_anchor']} | Comparative period | {fixture['quote']}"
    root.joinpath("raw", "result.html").write_text("<html>" + quote + "</html>", encoding="utf-8")
    root.joinpath("reader", "result.md").write_text(quote, encoding="utf-8")
    source = {
        "source_id": fixture["source_id"], "source_type": "OTHER_OFFICIAL", "official": True,
        "published_at": fixture["published_at"], "source_version": "synthetic-live-contract-v1",
        "data_as_of": outcome["measurement_period"]["label"], "revision_policy": "ORIGINAL_VINTAGE",
        "official_publisher_domain": fixture["domain"], "package_path": "raw/result.html",
        "reader_text_path": "reader/result.md", "candidate_claim_ids": [fixture["claim_id"]],
    }
    manifest = {
        "schema_version": OUTCOME_PACKAGE_SCHEMA_VERSION,
        "outcome_package_id": "OUTPKG:" + fixture["claim_id"],
        "case_id": contract_case["case_id"], "freeze_id": contract_case["report_freeze"]["freeze_id"],
        "frozen_cutoff": contract_case["simulation_cutoff"],
        "enumeration": {"status": "COMPLETE", "query_identity": "synthetic dry-run official results archive", "source_ids": [fixture["source_id"]]},
        "inventory": [source], "selected_source_ids": [fixture["source_id"]], "source_package_status": "COMPLETE",
        "_temporary_directory": directory,
    }
    attestation = read_outcome_package(
        manifest, root, case=contract_case, settlement_as_of=outcome["observation_window"]["closes_at"],
    )
    extraction = {
        "schema_version": OUTCOME_EXTRACTION_SCHEMA_VERSION, "outcome_package_id": manifest["outcome_package_id"],
        "case_id": contract_case["case_id"], "freeze_id": contract_case["report_freeze"]["freeze_id"],
        "settlement_as_of": outcome["observation_window"]["closes_at"],
        "observations": [{
            "observation_id": "HBTOBS:" + fixture["claim_id"], "claim_id": fixture["claim_id"],
            "metric": outcome["metric"], "value": float(fixture["value_text"].rstrip("%")), "unit": outcome["unit"],
            "measurement_basis": outcome["measurement_basis"], "measurement_period": outcome["measurement_period"],
            "source_ids": [fixture["source_id"]], "comparability_status": "COMPARABLE",
            "reported_file_scope": target["file_scope"], "reported_label": target["reported_label"],
            "reported_locator": target["reported_locator"], "reported_text": quote,
            "reported_value_text": fixture["value_text"],
            "reported_period_text": target["reported_period_anchor"],
        }],
    }
    return manifest, attestation, extraction, outcome, root


def test_r05_r06_frozen_outcome_contracts_accept_only_their_own_source_metric_and_window() -> None:
    for fixture in EXPERIMENTS:
        case = _contract_case(fixture["contract"])
        manifest, attestation, extraction, outcome, root = _exercise(case, fixture)
        directory = manifest.pop("_temporary_directory")
        try:
            assert validate_outcome_package(
                manifest, root, case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )["state"] == "REVIEWABLE"
            assert attestation["state"] == "REVIEWABLE"
            assert validate_outcome_extraction(
                extraction, manifest=manifest, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )["state"] == "REVIEWABLE"

            # Both labels and values can appear in a comparison table.  The
            # extraction may not reinterpret the comparison column as the
            # frozen target period.
            wrong_period = json.loads(json.dumps(extraction))
            wrong_period["observations"][0]["reported_period_text"] = "Comparative period"
            result = validate_outcome_extraction(
                wrong_period, manifest=manifest, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )
            assert "observations[0]:reported_period_anchor_not_found_in_reported_period_text" in result["invalid_findings"]

            proxy = json.loads(json.dumps(extraction))
            proxy["observations"][0]["reported_label"] = "Comparable sales"
            result = validate_outcome_extraction(
                proxy, manifest=manifest, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )
            assert "observations[0]:reported_disclosure_does_not_match_frozen_metric_contract" in result["invalid_findings"]

            late = json.loads(json.dumps(manifest))
            late["inventory"][0]["published_at"] = "2030-01-01T08:00:00-08:00"
            result = validate_outcome_extraction(
                extraction, manifest=late, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )
            assert "observations[0]:source_published_after_frozen_window:" + fixture["source_id"] in result["invalid_findings"]

            # A later eligible-looking release cannot replace the frozen
            # initial-disclosure policy merely because it contains the same KPI.
            later = json.loads(json.dumps(manifest))
            revision = json.loads(json.dumps(later["inventory"][0]))
            revision["source_id"] += ":REVISION"
            revision["source_version"] += ":revision"
            revision["published_at"] = "2027-03-01T08:00:00-08:00" if fixture["claim_id"] == "R05-S1" else "2027-03-20T08:00:00-08:00"
            later["inventory"].append(revision)
            later["enumeration"]["source_ids"].append(revision["source_id"])
            proxy = json.loads(json.dumps(extraction))
            proxy["observations"][0]["source_ids"] = [revision["source_id"]]
            result = validate_outcome_extraction(
                proxy, manifest=later, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )
            assert "observations[0]:does_not_use_initial_enumerated_disclosure" in result["invalid_findings"]

            # The inventory can include an early archive item that names this
            # claim but is outside the frozen issuer domain.  It must not
            # redefine what "initial" means for the eligible result set.
            unrelated = json.loads(json.dumps(manifest))
            archive_item = json.loads(json.dumps(unrelated["inventory"][0]))
            archive_item["source_id"] += ":ARCHIVE"
            archive_item["published_at"] = (
                "2027-01-15T08:00:00-08:00" if fixture["claim_id"] == "R05-S1"
                else "2027-02-10T08:00:00-08:00"
            )
            archive_item["official_publisher_domain"] = "archive.example.invalid"
            unrelated["inventory"].append(archive_item)
            unrelated["enumeration"]["source_ids"].append(archive_item["source_id"])
            result = validate_outcome_extraction(
                extraction, manifest=unrelated, package_root=root, read_attestation=attestation,
                case=case, settlement_as_of=outcome["observation_window"]["closes_at"],
            )
            assert result["state"] == "REVIEWABLE"
        finally:
            directory.cleanup()


def test_live_forward_execution_contract_rejects_an_outcome_or_investment_field() -> None:
    case = _contract_case(EXPERIMENTS[0]["contract"])
    assert validate_live_forward_outcome_contract(case)["state"] == "REVIEWABLE"
    case["actual_value"] = 4.5
    result = validate_live_forward_outcome_contract(case)
    assert "post_freeze_execution_contract_carries_prohibited_outcome_or_investment_field" in result["invalid_findings"]
    missing_anchor = _contract_case(EXPERIMENTS[0]["contract"])
    del missing_anchor["calibration_ledger"]["claims"][0]["observable_outcome"]["metric_reconstruction_contract"]["source_targets"][0]["reported_period_anchor"]
    result = validate_live_forward_outcome_contract(missing_anchor)
    assert "calibration_ledger.claims[0].observable_outcome.metric_reconstruction_contract.source_targets[0]:reported_period_anchor_missing" in result["incomplete_findings"]


def test_selection_admitted_contract_can_schedule_non_pair_operating_clocks() -> None:
    case = _contract_case(EXPERIMENTS[0]["contract"])
    pair = case["mechanism_signal_pair"]
    pair["selection_status"] = "SELECTION_ADMITTED"
    pair["selection_evidence_locator"] = "00_episode.md:42"
    pair["baseline_rule"] = "hold the same disclosed operating metric flat"
    case["calibration_ledger"]["claims"][0]["operating_clock"] = "CUSTOMER_COMPETITOR_RESPONSE"
    case["calibration_ledger"]["claims"][1]["operating_clock"] = "UNIT_ECONOMICS"
    for claim_id, clock in (
        ("R05-DECISION-CLOCK", "DECISION_IMPLEMENTATION"),
        ("R05-CASH-CLOCK", "WORKING_CAPITAL_CASH"),
        ("R05-CAPITAL-CLOCK", "CAPITAL_RETURN"),
    ):
        supplemental = json.loads(json.dumps(case["calibration_ledger"]["claims"][0]))
        supplemental["claim_id"] = claim_id
        supplemental["operating_clock"] = clock
        case["calibration_ledger"]["claims"].append(supplemental)
    assert validate_live_forward_outcome_contract(case)["state"] == "REVIEWABLE"

    missing = json.loads(json.dumps(case))
    del missing["mechanism_signal_pair"]["baseline_rule"]
    result = validate_live_forward_outcome_contract(missing)
    assert "mechanism_signal_pair:baseline_rule_missing" in result["incomplete_findings"]


def test_live_forward_execution_status_turns_frozen_windows_into_acquisition_actions() -> None:
    for fixture in EXPERIMENTS:
        case = _contract_case(fixture["contract"])
        before = assess_live_forward_acquisition_due(case, as_of="2026-08-21T12:00:00+08:00")
        assert before["state"] == "REVIEWABLE"
        assert before["execution_state"] == "NOT_YET_DUE"
        assert {item["action"] for item in before["claim_actions"]} == {"NOT_YET_DUE"}

        active = assess_live_forward_acquisition_due(case, as_of="2027-02-15T12:00:00-08:00")
        assert active["state"] == "REVIEWABLE"
        assert active["execution_state"] == "DUE_FOR_ACQUISITION"
        assert active["claim_actions"][0]["action"] == "DUE_FOR_ACQUISITION"
        assert active["claim_actions"][0]["required_next_step"] == "enumerate_and_acquire_frozen_result_sources"
        assert active["claim_actions"][1]["action"] == "NOT_YET_DUE"

        overdue = assess_live_forward_acquisition_due(case, as_of="2027-10-01T12:00:00-07:00")
        assert overdue["state"] == "REVIEWABLE"
        assert overdue["execution_state"] == "OVERDUE_FOR_ACQUISITION"
        assert {item["action"] for item in overdue["claim_actions"]} == {"OVERDUE_FOR_ACQUISITION"}


def test_due_inbox_scans_all_contracts_and_surfaces_only_actionable_claims(tmp_path) -> None:
    for index, fixture in enumerate(EXPERIMENTS):
        destination = tmp_path / f"R-{index + 5}" / "08_outcome_acquisition_contract.json"
        destination.parent.mkdir(parents=True)
        destination.write_text(fixture["contract"].read_text(encoding="utf-8"), encoding="utf-8")

    inbox = build_live_forward_due_inbox(tmp_path, as_of="2026-08-21T12:00:00+08:00")
    assert inbox["state"] == "REVIEWABLE"
    assert inbox["actionable"] == []
    assert len(inbox["scheduled"]) == 2

    due = build_live_forward_due_inbox(tmp_path, as_of="2027-02-15T12:00:00-08:00")
    assert due["state"] == "REVIEWABLE"
    assert [(item["case_id"], item["claim"]["claim_id"], item["claim"]["action"]) for item in due["actionable"]] == [
        ("R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821", "R05-S1", "DUE_FOR_ACQUISITION"),
        ("R-06:WMT:US_TRANSACTION_DURABILITY:20260821", "R06-S1", "DUE_FOR_ACQUISITION"),
    ]

    broken = tmp_path / "broken" / "08_outcome_acquisition_contract.json"
    broken.parent.mkdir()
    broken.write_text("{not json", encoding="utf-8")
    incomplete = build_live_forward_due_inbox(tmp_path, as_of="2027-02-15T12:00:00-08:00")
    assert incomplete["state"] == "INCOMPLETE"
    assert incomplete["contract_issues"] == [{
        "contract_path": "broken/08_outcome_acquisition_contract.json",
        "state": "INVALID", "findings": ["contract_unreadable"],
    }]
