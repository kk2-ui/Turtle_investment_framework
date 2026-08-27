#!/usr/bin/env python3
"""Independent, value-free review for the Round 10 appliance batch.

The reviewer consumes only the frozen Round 10 batch contract and lifecycle
records from its isolated Minimal-Historical-Episode database.  It never reads
an observed number, an outcome direction, a price, or a prediction.  This is
deliberately a review adapter, not another acquisition or settlement engine.
"""

from __future__ import annotations

from copy import deepcopy
import json
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_round10_appliance_v2 as round10
    from scripts import enterprise_judgment_round10_appliance_v2_control as round10_control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_round10_appliance_v2 as round10
    import enterprise_judgment_round10_appliance_v2_control as round10_control


REVIEWER_ID = "ROLE:ROUND10:EXTERNAL_METHOD_REVIEWER"
REVIEW_CANDIDATE_ID = "R10:EXTERNAL-REVIEW-CANDIDATE:CN_APPLIANCE:20180930:V2"
REVIEW_ID = "R10:EXTERNAL-METHOD-REVIEW:CN_APPLIANCE:20180930:V2"
COMPLETION_RECEIPT_ID = "R10:BATCH-COMPLETION:CN_APPLIANCE:20180930:V2"
METRICS = (
    "ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB",
    "ISSUER_CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
    "ISSUER_CONSOLIDATED_TOTAL_ASSETS_RMB",
)
SETTLEMENT_TERMINAL_STATUSES = {"MATCH", "MISS"}


class Round10ExternalReviewError(ValueError):
    """The persisted custody lifecycle is not a closed Round 10 review input."""


def _json(payload: str) -> dict[str, Any]:
    try:
        result = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise Round10ExternalReviewError("round10_review_payload_not_json") from exc
    if not isinstance(result, dict):
        raise Round10ExternalReviewError("round10_review_payload_must_be_object")
    return result


def _expected_company_ids() -> list[str]:
    return [row["company_id"] for row in round10.ROSTER]


def _field_records(conn: sqlite3.Connection) -> list[dict[str, str | int | None]]:
    """Read lifecycle state only, intentionally discarding values and labels."""
    contracts = conn.execute(
        """
        SELECT measurement_contract_id, measurement_contract_version, company_id, metric_id
        FROM minimal_historical_measurement_contracts
        WHERE company_id IN (?, ?, ?)
        ORDER BY CASE company_id WHEN ? THEN 1 WHEN ? THEN 2 WHEN ? THEN 3 ELSE 99 END,
                 CASE metric_id
                   WHEN ? THEN 1
                   WHEN ? THEN 2
                   WHEN ? THEN 3
                   ELSE 99
                 END
        """,
        (*_expected_company_ids(), *_expected_company_ids(), *METRICS),
    ).fetchall()
    records: list[dict[str, str | int | None]] = []
    for contract_id, version, company_id, metric_id in contracts:
        inventories = conn.execute(
            """
            SELECT status FROM minimal_historical_outcome_source_inventory
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?
            ORDER BY inventoried_at
            """,
            (contract_id, version),
        ).fetchall()
        observation_count = int(conn.execute(
            """
            SELECT COUNT(*) FROM minimal_historical_observations
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?
            """,
            (contract_id, version),
        ).fetchone()[0])
        settlements = conn.execute(
            """
            SELECT payload_json FROM minimal_historical_settlements
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?
            ORDER BY settled_at
            """,
            (contract_id, version),
        ).fetchall()
        inventory_status = inventories[0][0] if len(inventories) == 1 else None
        settlement_status = _json(settlements[0][0]).get("status") if len(settlements) == 1 else None
        if inventory_status == "FIELD_READY" and observation_count == 1 and settlement_status in SETTLEMENT_TERMINAL_STATUSES:
            terminal_state = "MECHANICALLY_SETTLED"
        elif inventory_status == "MEASUREMENT_MISMATCH" and observation_count == 0 and not settlements:
            terminal_state = "MEASUREMENT_MISMATCH"
        else:
            terminal_state = "NONTERMINAL_OR_INCONSISTENT"
        records.append({
            "company_id": company_id,
            "metric_id": metric_id,
            "inventory_status": inventory_status,
            "observation_count": observation_count,
            "settlement_count": len(settlements),
            # This is a lifecycle terminality class, never a value or direction.
            "terminal_state": terminal_state,
        })
    return records


def inspect_terminal_batch(conn: sqlite3.Connection) -> dict[str, Any]:
    """Validate the exact three-company, nine-field persisted custody result."""
    records = _field_records(conn)
    findings: list[str] = []
    expected_ids = _expected_company_ids()
    expected_pairs = [(company_id, metric_id) for company_id in expected_ids for metric_id in METRICS]
    actual_pairs = [(str(row["company_id"]), str(row["metric_id"])) for row in records]
    if actual_pairs != expected_pairs:
        findings.append("round10_review_requires_exact_predeclared_nine_field_roster")
    by_company: list[dict[str, Any]] = []
    expected_terminal_states = {
        "CN:002035": "MECHANICALLY_SETTLED",
        "CN:002508": "MEASUREMENT_MISMATCH",
        "CN:002677": "MECHANICALLY_SETTLED",
    }
    for company_id in expected_ids:
        rows = [row for row in records if row["company_id"] == company_id]
        states = {row["terminal_state"] for row in rows}
        terminal_state = next(iter(states)) if len(states) == 1 else "MIXED_OR_NONTERMINAL"
        if len(rows) != len(METRICS) or terminal_state != expected_terminal_states[company_id]:
            findings.append(f"round10_review_terminal_state_invalid:{company_id}")
        by_company.append({
            "company_id": company_id,
            "mechanically_settled_field_count": sum(row["terminal_state"] == "MECHANICALLY_SETTLED" for row in rows),
            "measurement_mismatch_field_count": sum(row["terminal_state"] == "MEASUREMENT_MISMATCH" for row in rows),
            "terminal_state": terminal_state,
        })
    if any(row["terminal_state"] == "NONTERMINAL_OR_INCONSISTENT" for row in records):
        findings.append("round10_review_contains_nonterminal_field")
    return {
        "schema_version": "enterprise-judgment-round10-terminal-lifecycle-review.v1",
        "batch_ref": "R10:BATCH:CN_APPLIANCE:20180930:V2",
        "field_records": records,
        "company_summaries": by_company,
        "mechanically_settled_field_count": sum(row["terminal_state"] == "MECHANICALLY_SETTLED" for row in records),
        "measurement_mismatch_field_count": sum(row["terminal_state"] == "MEASUREMENT_MISMATCH" for row in records),
        "valid": not findings,
        "findings": findings,
        "rights": deepcopy(round10.RIGHTS),
    }


def build_external_review_candidate(terminal: dict[str, Any]) -> dict[str, Any]:
    """Create a value-free candidate from terminality, not outcome direction."""
    if not terminal.get("valid"):
        raise Round10ExternalReviewError("round10_review_requires_valid_terminal_batch")
    delta = round10.build_method_epoch()["treatment_deltas"][0]
    applications: list[str] = []
    comparisons: list[dict[str, Any]] = []
    for summary in terminal["company_summaries"]:
        company_id = summary["company_id"]
        baseline = "CONTINUE_OPERATING_UNDERWRITING" if summary["mechanically_settled_field_count"] >= 2 else "NOT_DIAGNOSTIC"
        enhanced = "REQUIRE_OWNER_CASH_AND_BOUNDARY_EVIDENCE" if baseline == "CONTINUE_OPERATING_UNDERWRITING" else "NOT_DIAGNOSTIC"
        if baseline != enhanced:
            applications.append(company_id)
        comparisons.append({
            "company_id": company_id,
            "baseline_treatment": baseline,
            "enhanced_treatment": enhanced,
            "treatment_delta_application_id": f"R10:APPLICATION:{company_id.split(':', 1)[1]}:ISSUER_CASH_BOUNDARY" if baseline != enhanced else None,
            "treatment_delta_ref": delta["treatment_delta_id"] if baseline != enhanced else None,
            "candidate_basis": "Field terminality can create a review candidate only; it does not disclose or infer a result direction.",
        })
    return {
        "schema_version": "enterprise-judgment-round10-external-review-candidate.v1",
        "review_candidate_id": REVIEW_CANDIDATE_ID,
        "batch_ref": terminal["batch_ref"],
        "comparisons": comparisons,
        "treatment_delta_ledger": [{
            "treatment_delta_id": delta["treatment_delta_id"],
            "application_company_ids": applications,
            "method_advantage_count": 1 if applications else 0,
            "status": "ONE_BATCH_LEVEL_REVIEW_CANDIDATE_ONLY",
        }],
        "automatic_status": "INDEPENDENT_REVIEW_REQUIRED",
        "automatic_completion": False,
        "object_class": "ROUND10_EXTERNAL_METHOD_REVIEW_CANDIDATE",
        "claim_class": "VALUE_FREE_TERMINALITY_ONLY",
        "allowed_outputs": ["EXTERNAL_REVIEW_ONLY", "RESEARCH_AGENDA"],
        "rights": deepcopy(round10.RIGHTS),
    }


def build_external_review(*, terminal: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the independent conclusion without manufacturing a method win."""
    if not terminal.get("valid"):
        raise Round10ExternalReviewError("round10_external_review_requires_valid_terminal_batch")
    review = {
        "schema_version": "enterprise-judgment-round10-external-method-review.v1",
        "review_id": REVIEW_ID,
        "review_candidate_ref": candidate["review_candidate_id"],
        "reviewer_id": REVIEWER_ID,
        "review_status": "NO_MATERIAL_UTILITY",
        "accepted_treatment_delta_ids": [],
        "utility_basis": None,
        "reasoning": {
            "decision": "The enhanced rule did not demonstrate a material investment-treatment change and did not prove that it avoided a baseline directional error.",
            "permitted_basis_assessment": {
                "material_treatment_change": "NOT_ESTABLISHED: baseline already prohibits promoting issuer revenue or cash into customer response, action effect, unit economics or ordinary-share owner cash.",
                "prevented_directional_error": "NOT_ESTABLISHED: the frozen and settled fields are issuer-boundary financial lines, not an action, customer, unit-economic or owner-cash test.",
            },
            "not_counted_as_utility": ["MORE_EXPLANATION", "MORE_DIMENSIONS", "MORE_UNKNOWN", "MORE_COVERAGE"],
            "root_causes": [
                {
                    "classification": "MODEL",
                    "economic_impact": "The batch cannot establish that the eight-dimension method changes an investor's conclusion; it can only preserve a sensible evidence boundary.",
                    "missing_facts": "No frozen outcome field separately measures customer response, unit economics, ordinary-share owner cash, or the effect of an implemented action.",
                    "prohibited_assumption": "Do not infer any of those facts from issuer-level revenue, cash flow or total assets.",
                    "remediation": "Freeze the next unseen episode with at least one independently settleable field for the material boundary or mechanism that could alter the baseline treatment.",
                    "acceptance_criterion": "The predeclared enhanced rule must alter a material treatment or prevent a predeclared baseline directional error using those fields.",
                },
                {
                    "classification": "ACQUISITION_MODULE",
                    "economic_impact": "The CN:002508 fields cannot inform either method in this batch, but they do not invalidate settled fields for the other two companies.",
                    "missing_facts": "An `ORIGINAL_ONLY` FY2019 annual-report version family could not be uniquely resolved for the three contracted lines.",
                    "prohibited_assumption": "Do not substitute a revised or alternate annual report merely to complete the company.",
                    "remediation": "Improve original-version enumeration or choose a later unseen episode whose authorized version family is resolvable before freezing it.",
                    "acceptance_criterion": "A uniquely identified original official annual report maps to the same issuer, period, unit and listed-consolidated boundary.",
                },
            ],
        },
        "rights": deepcopy(round10.RIGHTS),
        "allowed_outputs": ["RESEARCH_AGENDA"],
    }
    generic = round10.validate_external_review(review, candidate=candidate)
    if not generic["valid"]:
        raise Round10ExternalReviewError("round10_generic_review_validator_rejected:" + ";".join(generic["findings"]))
    return review


def build_completion_receipt(*, terminal: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if not terminal.get("valid") or review.get("review_status") != "NO_MATERIAL_UTILITY":
        raise Round10ExternalReviewError("round10_completion_requires_valid_no_material_review")
    return {
        "schema_version": "enterprise-judgment-round10-batch-completion.v1",
        "completion_receipt_id": COMPLETION_RECEIPT_ID,
        "batch_ref": terminal["batch_ref"],
        "review_ref": review["review_id"],
        "completion_status": "ROUND10_COMPLETE_NO_METHOD_TRANSFER",
        "field_outcome_summary": terminal["company_summaries"],
        "mechanically_settled_field_count": terminal["mechanically_settled_field_count"],
        "measurement_mismatch_field_count": terminal["measurement_mismatch_field_count"],
        "method_utility_status": review["review_status"],
        "method_transfer": "NOT_AUTHORIZED",
        "next_unseen_sample_requirement": "Use independently settleable evidence for a material mechanism or boundary, not only issuer-level financial context.",
        "allowed_outputs": ["RESEARCH_AGENDA"],
        "rights": deepcopy(round10.RIGHTS),
    }


def validate_external_review_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    terminal = bundle.get("terminal")
    candidate = bundle.get("candidate")
    review = bundle.get("review")
    completion = bundle.get("completion")
    findings: list[str] = []
    if not isinstance(terminal, dict) or not terminal.get("valid"):
        findings.append("round10_external_bundle_terminal_input_invalid")
    if not isinstance(candidate, dict) or candidate.get("review_candidate_id") != REVIEW_CANDIDATE_ID:
        findings.append("round10_external_bundle_candidate_invalid")
    if not isinstance(review, dict) or review.get("review_status") != "NO_MATERIAL_UTILITY":
        findings.append("round10_external_bundle_review_must_remain_no_material_utility")
    elif isinstance(candidate, dict):
        generic = round10.validate_external_review(review, candidate=candidate)
        findings.extend("round10_external_bundle_generic:" + item for item in generic["findings"])
    if not isinstance(completion, dict) or completion.get("completion_status") != "ROUND10_COMPLETE_NO_METHOD_TRANSFER":
        findings.append("round10_external_bundle_completion_invalid")
    if isinstance(review, dict) and review.get("rights") != round10.RIGHTS:
        findings.append("round10_external_bundle_rights_must_remain_closed")
    return {"valid": not findings, "findings": findings}


def review_database(conn: sqlite3.Connection) -> dict[str, Any]:
    terminal = inspect_terminal_batch(conn)
    candidate = build_external_review_candidate(terminal)
    review = build_external_review(terminal=terminal, candidate=candidate)
    completion = build_completion_receipt(terminal=terminal, review=review)
    bundle = {"terminal": terminal, "candidate": candidate, "review": review, "completion": completion}
    result = validate_external_review_bundle(bundle)
    if not result["valid"]:
        raise Round10ExternalReviewError("round10_external_review_bundle_invalid:" + ";".join(result["findings"]))
    return bundle
