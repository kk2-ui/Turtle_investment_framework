#!/usr/bin/env python3
"""Admission control for a current-company Frozen CJO.

This module is deliberately a *consumer* of the canonical Enterprise
Judgment Core.  It does not add fields to the Core candidate or Frozen CJO,
and it does not infer a company conclusion.  Its sole job is to decide whether
one fully specified current-company package may use the directional PRIMARY
downstream lane.

The returned admission receipt is intentionally separate from the Core object:
the generic Core continues to represent an append-only enterprise judgment,
while this gate records the additional current-company evidence, driver, and
two-sided-thesis prerequisites.  A non-directional CJO can therefore be
independently reviewed and frozen without accidentally becoming a directional
Overlay input or a publication/investment authorization.  It may still be
presented read-only as an explicit ``NO_PRIMARY`` or ``MIXED`` conclusion.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_core as core
    from scripts import financial_driver_bridge as financial_bridge
    from scripts import thesis_test_gate as thesis_gate
except ImportError:  # pragma: no cover - direct script import fallback
    import enterprise_judgment_core as core
    import financial_driver_bridge as financial_bridge
    import thesis_test_gate as thesis_gate


SCHEMA_VERSION = "current-company-cjo-admission.v1"
REVIEW_BINDING_VERSION = "current-company-cjo-admission-review.v1"
FROZEN_RECEIPT_VERSION = "current-company-cjo-admission-receipt.v1"
ANALYSIS_PURPOSE = "COMPANY_JUDGMENT_ONLY"
PRIMARY_ADMITTED = "PRIMARY_ADMITTED"
REVIEWED_NOT_PRIMARY = "REVIEWED_NOT_PRIMARY"
REJECTED = "REJECTED"


class CurrentCompanyCjoAdmissionError(ValueError):
    """Raised when a current-company CJO cannot enter the requested lane."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if _text(item)]


def _exact_id_list(value: Any, *, path: str, findings: list[str]) -> list[str]:
    if not isinstance(value, list) or not value or any(not _text(item) for item in value):
        _add(findings, path + "_missing_or_invalid")
        return []
    items = list(value)
    if len(items) != len(set(items)):
        _add(findings, path + "_duplicate")
    return items


def _date_from_cutoff(cutoff_at: Any) -> str:
    return str(cutoff_at or "")[:10]


def _contract_identity_findings(
    contract: dict[str, Any], *, candidate: dict[str, Any], model: dict[str, Any],
    ledger: dict[str, Any], source_package: dict[str, Any], findings: list[str],
) -> None:
    allowed = {
        "schema_version", "admission_id", "analysis_purpose", "company_id", "report_id",
        "cutoff_at", "method_version", "source_package_id", "primary_binding",
    }
    for field in sorted(set(contract) - allowed):
        _add(findings, "admission_contract." + field + "_unsupported")
    if contract.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "admission_contract.schema_version_invalid")
    if contract.get("analysis_purpose") != ANALYSIS_PURPOSE:
        _add(findings, "admission_contract.analysis_purpose_invalid")
    for field in (
        "admission_id", "company_id", "report_id", "cutoff_at", "method_version", "source_package_id",
    ):
        if not _text(contract.get(field)):
            _add(findings, "admission_contract." + field + "_missing")
    for field in ("company_id", "cutoff_at", "method_version"):
        expected = candidate.get(field)
        if contract.get(field) != expected:
            _add(findings, "admission_contract." + field + "_candidate_mismatch")
        if model.get(field) != expected:
            _add(findings, "enterprise_system_model." + field + "_candidate_mismatch")
        if source_package.get(field) != expected:
            _add(findings, "source_package." + field + "_candidate_mismatch")
    if ledger.get("company_id") != candidate.get("company_id"):
        _add(findings, "management_decision_ledger.company_id_candidate_mismatch")
    if contract.get("source_package_id") != source_package.get("source_package_id"):
        _add(findings, "admission_contract.source_package_id_input_mismatch")
    if contract.get("source_package_id") != _mapping(candidate.get("source_package")).get("source_package_id"):
        _add(findings, "admission_contract.source_package_id_candidate_mismatch")


def _validation_context(value: str | Path | None) -> Path | None:
    return Path(value) if value is not None else None


def _bridge_index(bridge: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    drivers = {
        str(item.get("driver_id")): item
        for item in map(_mapping, _items(bridge.get("drivers")))
        if _text(item.get("driver_id"))
    }
    events = {
        str(item.get("event_id")): item
        for item in map(_mapping, _items(bridge.get("allocation_events")))
        if _text(item.get("event_id"))
    }
    return drivers, events


def _binding_consumption(candidate: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, bool]:
    transmissions = {
        str(item.get("transmission_id")): item
        for item in map(
            _mapping,
            _items(_mapping(candidate.get("enterprise_system_ref")).get("financial_transmissions")),
        )
        if _text(item.get("transmission_id"))
    }
    bindings = _items(_mapping(contract.get("primary_binding")).get("forward_judgment_bindings"))
    consumes_cash_or_loss = any(
        _mapping(transmissions.get(transmission_id)).get("layer") in {"OWNER_CASH", "PERMANENT_LOSS"}
        for raw in bindings
        for transmission_id in _ids(_mapping(raw).get("cjo_transmission_ids"))
    )
    consumes_allocation = any(
        _ids(_mapping(raw).get("allocation_event_ids")) for raw in bindings
    )
    return consumes_cash_or_loss, consumes_allocation


def _monitoring_binds(contract: Any, thesis_fj_id: str) -> bool:
    item = _mapping(contract)
    return (
        _text(item.get("contract_id"))
        and str(item.get("contract_id")).startswith("FDBMON:")
        and thesis_fj_id in _ids(item.get("forward_judgment_ids"))
    )


def _realization_binds(realization: Any, thesis_fj_id: str) -> bool:
    item = _mapping(realization)
    return (
        _text(item.get("contract_id"))
        and str(item.get("contract_id")).startswith("FDBREAL:")
        and thesis_fj_id in _ids(item.get("forward_judgment_ids"))
        and _monitoring_binds(item.get("early_signal"), thesis_fj_id)
        and _monitoring_binds(item.get("terminal_outcome"), thesis_fj_id)
    )


def _thesis_indexes(thesis: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    judgments = {
        str(item.get("judgment_id")): item
        for item in map(_mapping, _items(thesis.get("forward_judgments")))
        if _text(item.get("judgment_id"))
    }
    pairs = {
        str(item.get("pair_id")): item
        for item in map(_mapping, _items(thesis.get("rival_hypothesis_pairs")))
        if _text(item.get("pair_id"))
    }
    return judgments, pairs


def _selected_pair_side(pair: dict[str, Any], thesis: dict[str, Any]) -> str:
    selected = _mapping(thesis.get("central_path")).get("selected_scenario_id")
    chains = {
        str(item.get("chain_id")): item
        for item in map(_mapping, _items(thesis.get("mechanism_chains")))
        if _text(item.get("chain_id"))
    }
    if _mapping(chains.get(str(pair.get("primary_mechanism_chain_id")))).get("scenario_id") == selected:
        return "PRIMARY"
    if _mapping(chains.get(str(pair.get("rival_mechanism_chain_id")))).get("scenario_id") == selected:
        return "RIVAL"
    return ""


def _primary_binding_findings(
    *, candidate: dict[str, Any], contract: dict[str, Any], financial_driver_bridge: dict[str, Any],
    thesis_test_ledger: dict[str, Any], findings: list[str],
) -> None:
    binding = contract.get("primary_binding")
    if not isinstance(binding, dict):
        _add(findings, "admission_contract.primary_binding_missing")
        return
    allowed = {
        "rival_hypothesis_pair_id", "selected_scenario_id", "central_trace_ids", "forward_judgment_bindings",
    }
    for field in sorted(set(binding) - allowed):
        _add(findings, "admission_contract.primary_binding." + field + "_unsupported")
    for field in ("rival_hypothesis_pair_id", "selected_scenario_id"):
        if not _text(binding.get(field)):
            _add(findings, "admission_contract.primary_binding." + field + "_missing")
    central_trace_ids = _exact_id_list(
        binding.get("central_trace_ids"),
        path="admission_contract.primary_binding.central_trace_ids",
        findings=findings,
    )
    candidate_central_trace_ids = _ids(_mapping(candidate.get("central_path")).get("trace_ids"))
    if set(central_trace_ids) != set(candidate_central_trace_ids):
        _add(findings, "admission_contract.primary_binding.central_trace_ids_must_exactly_match_cjo")

    thesis_central = _mapping(thesis_test_ledger.get("central_path"))
    if binding.get("selected_scenario_id") != thesis_central.get("selected_scenario_id"):
        _add(findings, "admission_contract.primary_binding.selected_scenario_cjo_thesis_mismatch")
    if _date_from_cutoff(candidate.get("cutoff_at")) != str(thesis_central.get("as_of") or "")[:10]:
        _add(findings, "thesis_test.central_path_as_of_cutoff_mismatch")
    thesis_judgments, thesis_pairs = _thesis_indexes(thesis_test_ledger)
    pair = thesis_pairs.get(str(binding.get("rival_hypothesis_pair_id")))
    if pair is None:
        _add(findings, "admission_contract.primary_binding.rival_hypothesis_pair_unknown")
    elif not _selected_pair_side(pair, thesis_test_ledger):
        _add(findings, "admission_contract.primary_binding.selected_scenario_not_in_rival_pair")
    selection = _mapping(thesis_test_ledger.get("selection_admission"))
    if selection.get("status") != "SELECTION_ADMITTED":
        _add(findings, "thesis_test.selection_admission_not_admitted")
    if selection.get("rival_hypothesis_pair_id") != binding.get("rival_hypothesis_pair_id"):
        _add(findings, "thesis_test.selection_admission_rival_pair_mismatch")
    if binding.get("selected_scenario_id") not in _ids(selection.get("candidate_scenario_ids")):
        _add(findings, "thesis_test.selection_admission_selected_scenario_not_registered")

    raw_bindings = binding.get("forward_judgment_bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        _add(findings, "admission_contract.primary_binding.forward_judgment_bindings_missing")
        return
    cjo_judgments = {
        str(item.get("judgment_id")): item
        for item in map(_mapping, _items(candidate.get("forward_judgments")))
        if _text(item.get("judgment_id"))
    }
    variables = {
        str(item.get("variable_id")): item
        for item in map(_mapping, _items(candidate.get("key_operating_drivers")))
        if _text(item.get("variable_id"))
    }
    transmissions = {
        str(item.get("transmission_id")): item
        for item in map(_mapping, _items(_mapping(candidate.get("enterprise_system_ref")).get("financial_transmissions")))
        if _text(item.get("transmission_id"))
    }
    drivers, events = _bridge_index(financial_driver_bridge)
    seen_cjo: set[str] = set()
    seen_thesis: set[str] = set()
    for index, raw in enumerate(raw_bindings):
        path = f"admission_contract.primary_binding.forward_judgment_bindings[{index}]"
        item = _mapping(raw)
        allowed_binding = {
            "cjo_forward_judgment_id", "thesis_forward_judgment_id", "financial_driver_ids",
            "allocation_event_ids", "cjo_variable_ids", "cjo_transmission_ids", "material_to_primary",
            "selected_side", "thesis_mechanism_chain_ids", "cjo_trace_ids", "cjo_direction",
        }
        for field in sorted(set(item) - allowed_binding):
            _add(findings, path + "." + field + "_unsupported")
        cjo_id = item.get("cjo_forward_judgment_id")
        thesis_id = item.get("thesis_forward_judgment_id")
        if not _text(cjo_id) or cjo_id not in cjo_judgments or cjo_id in seen_cjo:
            _add(findings, path + ".cjo_forward_judgment_id_unknown_or_duplicate")
        else:
            seen_cjo.add(cjo_id)
        if not _text(thesis_id) or thesis_id not in thesis_judgments or thesis_id in seen_thesis:
            _add(findings, path + ".thesis_forward_judgment_id_unknown_or_duplicate")
        else:
            seen_thesis.add(thesis_id)
        if item.get("material_to_primary") is not True:
            _add(findings, path + ".material_to_primary_required")
        cjo_judgment = _mapping(cjo_judgments.get(str(cjo_id)))
        if cjo_judgment.get("status") == "UNKNOWN" or cjo_judgment.get("evidence_state") in {
            "UNKNOWN", "MODEL_UNCERTAIN", "EVIDENCE_INELIGIBLE",
        }:
            _add(findings, path + ".cjo_forward_judgment_unknown_or_uncertain")
        thesis_judgment = _mapping(thesis_judgments.get(str(thesis_id)))
        if thesis_judgment.get("status") == "UNKNOWN" or thesis_judgment.get("evidence_state") == "UNKNOWN":
            _add(findings, path + ".thesis_forward_judgment_unknown")
        if thesis_judgment.get("rival_hypothesis_pair_id") != binding.get("rival_hypothesis_pair_id"):
            _add(findings, path + ".thesis_forward_judgment_rival_pair_mismatch")
        selected_side = _selected_pair_side(pair, thesis_test_ledger) if pair is not None else ""
        if item.get("selected_side") != selected_side:
            _add(findings, path + ".selected_side_must_match_selected_scenario")
        chain_ids = _exact_id_list(
            item.get("thesis_mechanism_chain_ids"),
            path=path + ".thesis_mechanism_chain_ids",
            findings=findings,
        )
        if set(chain_ids) != set(_ids(thesis_judgment.get("mechanism_chain_ids"))):
            _add(findings, path + ".thesis_mechanism_chain_ids_must_exactly_match_forward_judgment")
        chains = {
            str(chain.get("chain_id")): chain
            for chain in map(_mapping, _items(thesis_test_ledger.get("mechanism_chains")))
            if _text(chain.get("chain_id"))
        }
        if any(_mapping(chains.get(chain_id)).get("scenario_id") != binding.get("selected_scenario_id") for chain_id in chain_ids):
            _add(findings, path + ".thesis_mechanism_chain_not_on_selected_scenario")
        cjo_trace_ids = _exact_id_list(item.get("cjo_trace_ids"), path=path + ".cjo_trace_ids", findings=findings)
        cjo_trace_index = {
            str(trace.get("trace_id")): trace
            for trace in map(_mapping, _items(candidate.get("traceability")))
            if _text(trace.get("trace_id"))
        }
        if any(trace_id not in cjo_trace_index for trace_id in cjo_trace_ids):
            _add(findings, path + ".cjo_trace_id_unknown")
        if not set(cjo_trace_ids) <= set(candidate_central_trace_ids):
            _add(findings, path + ".cjo_trace_ids_must_be_central")
        if item.get("cjo_direction") != cjo_judgment.get("direction"):
            _add(findings, path + ".cjo_direction_must_match_forward_judgment")
        driver_ids = _exact_id_list(item.get("financial_driver_ids"), path=path + ".financial_driver_ids", findings=findings)
        variable_ids = _exact_id_list(item.get("cjo_variable_ids"), path=path + ".cjo_variable_ids", findings=findings)
        transmission_ids = _exact_id_list(item.get("cjo_transmission_ids"), path=path + ".cjo_transmission_ids", findings=findings)
        for variable_id in variable_ids:
            if variable_id not in variables:
                _add(findings, path + ".cjo_variable_id_unknown:" + variable_id)
        for transmission_id in transmission_ids:
            if transmission_id not in transmissions:
                _add(findings, path + ".cjo_transmission_id_unknown:" + transmission_id)
        has_cash_or_loss = any(
            _mapping(transmissions.get(transmission_id)).get("layer") in {"OWNER_CASH", "PERMANENT_LOSS"}
            for transmission_id in transmission_ids
        )
        cash_driver_seen = False
        for driver_id in driver_ids:
            driver = _mapping(drivers.get(driver_id))
            if not driver:
                _add(findings, path + ".financial_driver_id_unknown:" + driver_id)
                continue
            if driver.get("status") != "OBSERVED" or not _ids(driver.get("observation_ids")):
                _add(findings, path + ".material_financial_driver_not_observed:" + driver_id)
            if not _monitoring_binds(driver.get("monitoring_contract"), str(thesis_id)):
                _add(findings, path + ".financial_driver_monitoring_not_bound:" + driver_id)
            if driver.get("layer") == "CASH_CONVERSION":
                cash_driver_seen = True
                if _mapping(driver.get("cash_normalization_contract")).get("state") != "NORMALIZED":
                    _add(findings, path + ".owner_cash_requires_normalized_cash_driver:" + driver_id)
        if has_cash_or_loss and not cash_driver_seen:
            _add(findings, path + ".owner_cash_or_loss_requires_cash_conversion_driver")
        event_ids = item.get("allocation_event_ids")
        if not isinstance(event_ids, list) or any(not _text(event_id) for event_id in event_ids):
            _add(findings, path + ".allocation_event_ids_invalid")
            event_ids = []
        if has_cash_or_loss and not event_ids:
            _add(findings, path + ".owner_cash_or_loss_requires_allocation_event")
        for event_id in event_ids:
            event = _mapping(events.get(str(event_id)))
            if not event:
                _add(findings, path + ".allocation_event_id_unknown:" + str(event_id))
                continue
            if event.get("classification") == "UNRESOLVED" or not _ids(event.get("observation_ids")):
                _add(findings, path + ".material_allocation_event_not_resolved:" + str(event_id))
            if not _realization_binds(event.get("realization_contract"), str(thesis_id)):
                _add(findings, path + ".allocation_event_realization_not_bound:" + str(event_id))
    if pair is not None:
        selected_side = _selected_pair_side(pair, thesis_test_ledger)
        for item in map(_mapping, _items(pair.get("critical_assumptions"))):
            if item.get("mechanism_side") == selected_side and item.get("status") == "UNKNOWN":
                _add(findings, "thesis_test.selected_critical_assumption_unknown")
        for item in map(_mapping, _items(pair.get("causal_trace"))):
            if item.get("mechanism_side") == selected_side and item.get("status") == "UNKNOWN":
                _add(findings, "thesis_test.selected_causal_trace_unknown")


def _underwriting_primary_binding_findings(
    *, candidate: dict[str, Any], contract: dict[str, Any], source_package: dict[str, Any],
    findings: list[str],
) -> None:
    """Admit a current-company primary from the complete Episode, not E3 selection.

    Comparative selection remains available to claims that actually depend on
    it.  A whole-company underwriting conclusion instead binds the already
    validated, price-free Episode carried by the CJO to current-company source
    evidence and the CJO's central traces.
    """
    projection = _mapping(candidate.get("underwriting_thesis_projection"))
    binding = _mapping(contract.get("primary_binding"))
    allowed = {
        "binding_kind", "episode_id", "underwriting_thesis_id", "central_trace_ids",
    }
    for field in sorted(set(binding) - allowed):
        _add(findings, "admission_contract.primary_binding." + field + "_unsupported")
    if binding.get("binding_kind") != "ENTERPRISE_UNDERWRITING_EPISODE":
        _add(findings, "admission_contract.primary_binding.binding_kind_invalid")
    for field in ("episode_id", "underwriting_thesis_id"):
        if binding.get(field) != projection.get(field):
            _add(findings, "admission_contract.primary_binding." + field + "_mismatch")
    if projection.get("sample_identity") == "WORKED_CASE":
        _add(findings, "worked_case_underwriting_cannot_enter_current_company_primary")
    central_trace_ids = _exact_id_list(
        binding.get("central_trace_ids"),
        path="admission_contract.primary_binding.central_trace_ids",
        findings=findings,
    )
    if set(central_trace_ids) != set(_ids(_mapping(candidate.get("central_path")).get("trace_ids"))):
        _add(findings, "admission_contract.primary_binding.central_trace_ids_must_exactly_match_cjo")
    package_sources = {
        str(item.get("source_ref") or "")
        for item in _items(source_package.get("sources")) if isinstance(item, dict)
    }
    projection_sources = {
        str(item.get("source_ref") or "")
        for item in _items(projection.get("evidence_trace")) if isinstance(item, dict)
    }
    if not projection_sources:
        _add(findings, "underwriting_thesis_projection.evidence_trace_missing")
    for source_ref in sorted(projection_sources - package_sources):
        _add(findings, "underwriting_thesis_projection.source_not_in_package:" + source_ref)


def _admission_receipt(
    *, contract: dict[str, Any], candidate: dict[str, Any], status: str, findings: list[str],
) -> dict[str, Any]:
    primary = status == PRIMARY_ADMITTED
    return {
        "schema_version": SCHEMA_VERSION,
        "admission_id": contract.get("admission_id"),
        "status": status,
        "subject": {
            "candidate_id": candidate.get("candidate_id"),
            "company_id": candidate.get("company_id"),
            "report_id": contract.get("report_id"),
            "cutoff_at": candidate.get("cutoff_at"),
            "method_version": candidate.get("method_version"),
            "source_package_id": _mapping(candidate.get("source_package")).get("source_package_id"),
            "resolution": candidate.get("resolution"),
        },
        "primary_binding": deepcopy(contract.get("primary_binding")) if primary else None,
        "findings": list(findings),
        "authority": {
            "primary_cjo_admitted": primary,
            "overlay_read_allowed": primary,
            # A report may accurately present an abstention or mixed outcome;
            # this is read authority only and never a release privilege.
            "report_read_allowed": True,
            "publication_authorization": False,
            "investment_authorization": False,
        },
    }


def build_current_company_cjo_review_binding(
    *, candidate: Any, admission: Any, independent_review: Any,
) -> dict[str, Any]:
    """Build the exact non-Core review binding for one compiled admission.

    Core's generic review deliberately has a broader purpose.  This small
    companion object records what the independent reviewer actually reviewed
    for the current-company PRIMARY lane without changing Core's schema.
    """
    candidate_value = _mapping(candidate)
    admission_value = _mapping(admission)
    review_value = _mapping(independent_review)
    return {
        "schema_version": REVIEW_BINDING_VERSION,
        "review_id": review_value.get("review_id"),
        "reviewer_id": review_value.get("reviewer_id"),
        "reviewed_at": review_value.get("reviewed_at"),
        "candidate_id": candidate_value.get("candidate_id"),
        "compiled_at": candidate_value.get("compiled_at"),
        "admission_id": admission_value.get("admission_id"),
        "source_package_id": _mapping(candidate_value.get("source_package")).get("source_package_id"),
        "primary_binding": deepcopy(admission_value.get("primary_binding")),
    }


def _validate_review_binding(
    *, candidate: dict[str, Any], admission: dict[str, Any], independent_review: Any,
    admission_review: Any,
) -> list[str]:
    value = _mapping(admission_review)
    review = _mapping(independent_review)
    findings: list[str] = []
    allowed = {
        "schema_version", "review_id", "reviewer_id", "reviewed_at", "candidate_id", "compiled_at",
        "admission_id", "source_package_id", "primary_binding",
    }
    for field in sorted(set(value) - allowed):
        _add(findings, "current_company_admission_review." + field + "_unsupported")
    if value.get("schema_version") != REVIEW_BINDING_VERSION:
        _add(findings, "current_company_admission_review.schema_version_invalid")
    expected = {
        "review_id": review.get("review_id"),
        "reviewer_id": review.get("reviewer_id"),
        "reviewed_at": review.get("reviewed_at"),
        "candidate_id": candidate.get("candidate_id"),
        "compiled_at": candidate.get("compiled_at"),
        "admission_id": admission.get("admission_id"),
        "source_package_id": _mapping(candidate.get("source_package")).get("source_package_id"),
    }
    for field, required in expected.items():
        if value.get(field) != required:
            _add(findings, "current_company_admission_review." + field + "_mismatch")
    if value.get("primary_binding") != admission.get("primary_binding"):
        _add(findings, "current_company_admission_review.primary_binding_mismatch")
    return findings


def _frozen_admission_receipt(
    *, frozen_cjo: dict[str, Any], admission: dict[str, Any], admission_review: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": FROZEN_RECEIPT_VERSION,
        "admission_id": admission.get("admission_id"),
        "status": admission.get("status"),
        "cjo_ref": {
            field: frozen_cjo.get(field)
            for field in ("cjo_id", "company_id", "cutoff_at", "method_version", "resolution")
        },
        "candidate_binding": {
            "candidate_id": admission_review.get("candidate_id"),
            "compiled_at": admission_review.get("compiled_at"),
            "source_package_id": admission_review.get("source_package_id"),
            "primary_binding": deepcopy(admission_review.get("primary_binding")),
        },
        "independent_review_binding": {
            field: admission_review.get(field)
            for field in ("review_id", "reviewer_id", "reviewed_at")
        },
        "authority": deepcopy(admission.get("authority")),
    }


def validate_frozen_current_company_cjo_admission(
    *, frozen_cjo: Any, admission_receipt: Any, require_overlay: bool = False,
) -> dict[str, Any]:
    """Validate the immutable current-company downstream admission artifact."""
    cjo = _mapping(frozen_cjo)
    receipt = _mapping(admission_receipt)
    findings: list[str] = []
    if core.validate_frozen_cjo(cjo)["state"] != "VALID":
        _add(findings, "frozen_cjo_invalid")
    allowed = {
        "schema_version", "admission_id", "status", "cjo_ref", "candidate_binding",
        "independent_review_binding", "authority",
    }
    for field in sorted(set(receipt) - allowed):
        _add(findings, "current_company_admission_receipt." + field + "_unsupported")
    if receipt.get("schema_version") != FROZEN_RECEIPT_VERSION:
        _add(findings, "current_company_admission_receipt.schema_version_invalid")
    if not _text(receipt.get("admission_id")):
        _add(findings, "current_company_admission_receipt.admission_id_missing")
    expected_ref = {field: cjo.get(field) for field in ("cjo_id", "company_id", "cutoff_at", "method_version", "resolution")}
    if _mapping(receipt.get("cjo_ref")) != expected_ref:
        _add(findings, "current_company_admission_receipt.cjo_ref_mismatch")
    authority = _mapping(receipt.get("authority"))
    if receipt.get("status") == PRIMARY_ADMITTED:
        if authority.get("primary_cjo_admitted") is not True:
            _add(findings, "current_company_admission_receipt.primary_authority_missing")
        if cjo.get("resolution") != "PRIMARY":
            _add(findings, "current_company_admission_receipt.primary_status_resolution_mismatch")
    elif receipt.get("status") != REVIEWED_NOT_PRIMARY:
        _add(findings, "current_company_admission_receipt.status_invalid")
    if authority.get("report_read_allowed") is not True:
        _add(findings, "current_company_admission_receipt.report_read_not_allowed")
    if authority.get("publication_authorization") is not False or authority.get("investment_authorization") is not False:
        _add(findings, "current_company_admission_receipt.prohibited_authority")
    if require_overlay and (
        receipt.get("status") != PRIMARY_ADMITTED or authority.get("overlay_read_allowed") is not True
    ):
        _add(findings, "current_company_admission_receipt.overlay_not_admitted")
    review = _mapping(receipt.get("independent_review_binding"))
    core_review = _mapping(cjo.get("independent_review_receipt"))
    for field in ("review_id", "reviewer_id", "reviewed_at"):
        if review.get(field) != core_review.get(field):
            _add(findings, "current_company_admission_receipt.independent_review_" + field + "_mismatch")
    candidate = _mapping(receipt.get("candidate_binding"))
    if candidate.get("candidate_id") != core_review.get("candidate_id"):
        _add(findings, "current_company_admission_receipt.candidate_id_mismatch")
    if candidate.get("compiled_at") != cjo.get("compiled_at"):
        _add(findings, "current_company_admission_receipt.compiled_at_mismatch")
    if candidate.get("source_package_id") != _mapping(cjo.get("source_package")).get("source_package_id"):
        _add(findings, "current_company_admission_receipt.source_package_id_mismatch")
    if receipt.get("status") == PRIMARY_ADMITTED and not isinstance(candidate.get("primary_binding"), dict):
        _add(findings, "current_company_admission_receipt.primary_binding_missing")
    return {"state": "VALID" if not findings else "INVALID", "findings": findings}


def validate_current_company_cjo_admission(
    *, candidate: Any, model: Any, ledger: Any, source_package: Any, admission_contract: Any,
    financial_driver_bridge: Any | None = None, thesis_test_ledger: Any | None = None,
    validation_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate an already compiled CJO against the current-company gate.

    ``validation_dir`` is optional read-only context for the existing validators
    (for example, VERIFIED observation and thesis evidence ledgers).  The gate
    neither writes to it nor treats report prose as a prerequisite.
    """
    candidate_value = _mapping(candidate)
    model_value = _mapping(model)
    ledger_value = _mapping(ledger)
    source_value = _mapping(source_package)
    contract = _mapping(admission_contract)
    bridge = _mapping(financial_driver_bridge)
    thesis = _mapping(thesis_test_ledger)
    findings: list[str] = []
    core_validation = core.validate_cjo_candidate(candidate_value)
    for finding in core_validation["findings"]:
        _add(findings, "candidate:" + finding)
    _contract_identity_findings(
        contract, candidate=candidate_value, model=model_value, ledger=ledger_value,
        source_package=source_value, findings=findings,
    )
    resolution = candidate_value.get("resolution")
    if resolution not in {"PRIMARY", "NO_PRIMARY", "MIXED", "UNKNOWN"}:
        _add(findings, "candidate.resolution_invalid")
    if findings:
        status = REJECTED
        return {
            "state": status, "status": status, "findings": findings,
            "core_validation": core_validation,
            "admission": _admission_receipt(contract=contract, candidate=candidate_value, status=status, findings=findings),
        }
    if resolution != "PRIMARY":
        # A reviewed abstention or mixed state remains useful as a canonical
        # research record, but it cannot borrow the directional downstream lane.
        status = REVIEWED_NOT_PRIMARY
        return {
            "state": status, "status": status, "findings": [],
            "core_validation": core_validation,
            "admission": _admission_receipt(contract=contract, candidate=candidate_value, status=status, findings=[]),
        }

    if isinstance(candidate_value.get("underwriting_thesis_projection"), dict):
        _underwriting_primary_binding_findings(
            candidate=candidate_value,
            contract=contract,
            source_package=source_value,
            findings=findings,
        )
        status = PRIMARY_ADMITTED if not findings else REJECTED
        return {
            "state": status,
            "status": status,
            "findings": findings,
            "core_validation": core_validation,
            "financial_driver_bridge_validation": {
                "state": "NOT_REQUIRED_EPISODE_BOUND",
                "invalid_findings": [],
                "incomplete_findings": [],
            },
            "thesis_test_validation": {
                "state": "NOT_REQUIRED_EPISODE_BOUND",
                "invalid_findings": [],
                "incomplete_findings": [],
            },
            "admission": _admission_receipt(
                contract=contract,
                candidate=candidate_value,
                status=status,
                findings=findings,
            ),
        }

    if not bridge:
        _add(findings, "financial_driver_bridge_missing")
        bridge_validation: dict[str, Any] = {"state": "MISSING", "invalid_findings": [], "incomplete_findings": []}
    else:
        consumes_cash_or_loss, consumes_allocation = _binding_consumption(candidate_value, contract)
        bridge_validation = financial_bridge.validate_financial_driver_bridge(
            bridge,
            output_dir=_validation_context(validation_dir),
            require_allocation_commitment_trace=consumes_allocation,
            require_cash_normalization_contract=consumes_cash_or_loss,
        )
        if bridge_validation.get("state") != "REVIEWABLE":
            _add(findings, "financial_driver_bridge_not_reviewable:" + str(bridge_validation.get("state")))
        if bridge.get("analysis_purpose") != ANALYSIS_PURPOSE:
            _add(findings, "financial_driver_bridge.analysis_purpose_invalid")
        if bridge.get("report_id") != contract.get("report_id"):
            _add(findings, "financial_driver_bridge.report_id_contract_mismatch")
        if bridge.get("as_of") != _date_from_cutoff(candidate_value.get("cutoff_at")):
            _add(findings, "financial_driver_bridge.as_of_cutoff_mismatch")
    if not thesis:
        _add(findings, "thesis_test_ledger_missing")
        thesis_validation: dict[str, Any] = {"state": "MISSING", "invalid_findings": [], "incomplete_findings": []}
    else:
        thesis_validation = thesis_gate.validate_thesis_test_ledger(
            thesis,
            output_dir=_validation_context(validation_dir),
            report_text="",
            enforced=False,
            monitoring_required=True,
            forward_judgment_required=True,
            rival_hypothesis_pair_required=True,
        )
        if thesis_validation.get("state") not in {"DECISION_READY", "MONITORING"}:
            _add(findings, "thesis_test_ledger_not_ready:" + str(thesis_validation.get("state")))
        if thesis.get("analysis_purpose") != ANALYSIS_PURPOSE:
            _add(findings, "thesis_test.analysis_purpose_invalid")
        if thesis.get("report_id") != contract.get("report_id"):
            _add(findings, "thesis_test.report_id_contract_mismatch")
    if bridge and thesis:
        _primary_binding_findings(
            candidate=candidate_value, contract=contract, financial_driver_bridge=bridge,
            thesis_test_ledger=thesis, findings=findings,
        )
    status = PRIMARY_ADMITTED if not findings else REJECTED
    return {
        "state": status,
        "status": status,
        "findings": findings,
        "core_validation": core_validation,
        "financial_driver_bridge_validation": bridge_validation,
        "thesis_test_validation": thesis_validation,
        "admission": _admission_receipt(contract=contract, candidate=candidate_value, status=status, findings=findings),
    }


def compile_current_company_cjo_candidate(
    *, model: Any, ledger: Any, source_package: Any, judgment_input: Any, admission_contract: Any,
    financial_driver_bridge: Any | None = None, thesis_test_ledger: Any | None = None,
    underwriting_episode: Any | None = None,
    validation_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compile Core's candidate and attach a separately auditable admission receipt."""
    candidate = core.compile_cjo_candidate(
        model=model,
        ledger=ledger,
        source_package=source_package,
        judgment_input=judgment_input,
        underwriting_episode=underwriting_episode,
    )
    validation = validate_current_company_cjo_admission(
        candidate=candidate,
        model=model,
        ledger=ledger,
        source_package=source_package,
        admission_contract=admission_contract,
        financial_driver_bridge=financial_driver_bridge,
        thesis_test_ledger=thesis_test_ledger,
        validation_dir=validation_dir,
    )
    if validation["state"] == REJECTED:
        raise CurrentCompanyCjoAdmissionError(
            "current_company_cjo_admission_rejected:" + ",".join(validation["findings"])
        )
    return {"candidate": candidate, "admission": validation["admission"]}


def freeze_admitted_current_company_cjo(
    *, model: Any, ledger: Any, source_package: Any, judgment_input: Any, admission_contract: Any,
    financial_driver_bridge: Any | None = None, thesis_test_ledger: Any | None = None,
    underwriting_episode: Any | None = None,
    independent_review: Any, admission_review: Any, validation_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Recompile and revalidate all inputs before independently freezing a CJO.

    Callers cannot hand a previously admitted candidate to this function.  The
    full source/model/ledger/thesis package is re-run so a changed driver,
    binding, or identity cannot be smuggled between admission and freeze.
    """
    compiled = compile_current_company_cjo_candidate(
        model=model,
        ledger=ledger,
        source_package=source_package,
        judgment_input=judgment_input,
        admission_contract=admission_contract,
        financial_driver_bridge=financial_driver_bridge,
        thesis_test_ledger=thesis_test_ledger,
        underwriting_episode=underwriting_episode,
        validation_dir=validation_dir,
    )
    review_findings = _validate_review_binding(
        candidate=compiled["candidate"], admission=compiled["admission"],
        independent_review=independent_review, admission_review=admission_review,
    )
    if review_findings:
        raise CurrentCompanyCjoAdmissionError(
            "current_company_cjo_admission_review_rejected:" + ",".join(review_findings)
        )
    frozen = core.freeze_cjo(
        candidate=compiled["candidate"],
        independent_review=independent_review,
    )
    frozen_receipt = _frozen_admission_receipt(
        frozen_cjo=frozen,
        admission=compiled["admission"],
        admission_review=_mapping(admission_review),
    )
    receipt_validation = validate_frozen_current_company_cjo_admission(
        frozen_cjo=frozen, admission_receipt=frozen_receipt,
    )
    if receipt_validation["state"] != "VALID":
        raise CurrentCompanyCjoAdmissionError(
            "current_company_cjo_admission_receipt_invalid:" + ",".join(receipt_validation["findings"])
        )
    return {"frozen_cjo": frozen, "admission": frozen_receipt}
