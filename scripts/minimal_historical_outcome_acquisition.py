#!/usr/bin/env python3
"""Custodian-only CNINFO metadata enumeration for minimal episode outcomes.

This adapter has a deliberately narrow job: after controller-recorded outcome
access, enumerate one bounded CNINFO announcement window and identify whether
exactly one direct annual-report PDF can carry the frozen measurement field.
It never receives a prediction, price, CJO, pairing, report, or learning
object.  PDF reader state belongs to the custodian callback and is not written
to the inventory receipt; the later runner remains responsible for the exact
numeric/quote check on the one inventory-approved page.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
import sqlite3
from typing import Any, Callable

try:
    from scripts import minimal_historical_episode as episode
    from scripts import minimal_historical_episode_control_plane as control
    from scripts import phase10_acquisition as phase10
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as episode
    import minimal_historical_episode_control_plane as control
    import phase10_acquisition as phase10


OUTCOME_SOURCE_ACQUISITION_SCHEMA_VERSION = "turtle-minimal-historical-episode-outcome-source-acquisition.v1"
PageLocator = Callable[[dict[str, Any], dict[str, Any]], str | None]
CNInfoRequest = Callable[[dict[str, str]], dict[str, Any]]
_REVISION_TITLE = re.compile(r"修订|更正|更新", re.IGNORECASE)
_DIRECT_ANNUAL_REPORT_TITLE = re.compile(
    r"^20\d{2}年年度报告(?:（原始版）|\(原始版\))?$",
)


def _connect(database: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    return conn


def _context(database: str, *, outcome_access_authorization_id: str) -> dict[str, Any]:
    conn = _connect(database)
    try:
        return control.resolve_authorized_outcome_access(
            conn, authorization_id=outcome_access_authorization_id,
        )
    finally:
        conn.close()


def _date(value: str, *, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def _is_direct_original_annual_report(title: Any) -> bool:
    """Keep a full original annual report distinct from its summary/abstract.

    CNINFO's general normalizer deliberately groups titles containing
    ``年度报告`` under the same broad annual-report period.  That is useful for
    discovery, but a frozen field may only be read from the full statutory
    report; an annual-report summary is not a substitute.  This is a narrow
    title identity rule, not an inference about the contents of either PDF.
    """
    compact = re.sub(r"\s+", "", str(title or ""))
    return bool(_DIRECT_ANNUAL_REPORT_TITLE.fullmatch(compact))


def _base_candidate(
    context: dict[str, Any], *, inventory_receipt_id: str, status: str,
) -> dict[str, Any]:
    if not isinstance(inventory_receipt_id, str) or not inventory_receipt_id.strip():
        raise ValueError("inventory_receipt_id is required")
    return {
        "schema_version": episode.OUTCOME_SOURCE_INVENTORY_SCHEMA_VERSION,
        "inventory_receipt_id": inventory_receipt_id,
        "measurement_contract_ref": deepcopy(context["measurement_contract_ref"]),
        "custodian_id": context["custodian_id"],
        # The controller replaces this placeholder with its own clock at the
        # moment it appends the receipt.  The adapter must not self-time a
        # custody event.
        "inventoried_at": "",
        "status": status,
        "object_class": "MINIMAL_HISTORICAL_OUTCOME_SOURCE_INVENTORY_RECEIPT",
        "claim_class": "CUSTODIAN_VALUE_FREE_SOURCE_READINESS",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _mismatch(
    context: dict[str, Any], *, inventory_receipt_id: str, rule: str, detail: str,
) -> dict[str, Any]:
    candidate = _base_candidate(context, inventory_receipt_id=inventory_receipt_id, status="MEASUREMENT_MISMATCH")
    candidate.update({"mismatch_rule": rule, "mismatch_detail": detail})
    return candidate


def acquire_cninfo_outcome_source_candidate(
    database: str,
    *,
    outcome_access_authorization_id: str,
    inventory_receipt_id: str,
    field_locator: PageLocator | None = None,
    request: CNInfoRequest | None = None,
) -> dict[str, Any]:
    """Return a value-free FIELD_READY or MEASUREMENT_MISMATCH candidate.

    ``field_locator`` is a custodian-local callback.  If it opens a PDF or a
    page-marked reader, it may return only the one page locator; page text,
    exact quote, and numeric value remain temporary and are not accepted by
    this adapter.
    """
    # Resolve persistent authorization before touching the official metadata
    # enumerator.  The entire query route is then read from the stored v2
    # Measurement Contract; this API intentionally has no caller route
    # parameters that could drift after the prediction freeze.
    context = _context(database, outcome_access_authorization_id=outcome_access_authorization_id)
    contract = context["measurement_contract"]
    try:
        route = episode.outcome_acquisition_route_from_measurement_contract(contract)
    except ValueError as exc:
        raise control.MinimalHistoricalEpisodeError(
            "outcome_acquisition_route_v2_required",
            "custodian metadata enumeration requires the stored Measurement Contract v2 route",
        ) from exc
    company_code = route["security_code"]
    org_id = route["organization_id"]
    start, end = _date(route["begin_date"], name="stored route begin_date"), _date(
        route["end_date"], name="stored route end_date",
    )
    try:
        acquisition = phase10.fetch_cninfo_announcement_records(
            company_code=company_code,
            org_id=org_id,
            begin_date=start.isoformat(),
            end_date=end.isoformat(),
            page_size=route["page_size"],
            tab_name=route["tab_name"],
            request=request,
        )
        normalized = [
            phase10.normalize_cninfo_announcement_record(record, company_code=company_code)
            for record in acquisition["records"]
        ]
    except (phase10.CNInfoAnnouncementQueryError, phase10.CNInfoAnnouncementExportError, ValueError):
        return _mismatch(
            context,
            inventory_receipt_id=inventory_receipt_id,
            rule="CNINFO_METADATA_ENUMERATION_INVALID",
            detail="the bounded official CNINFO metadata enumeration could not prove a contract-bound candidate",
        )

    outcome_period_end = contract["outcome_period_end"]
    annual_period_candidates = [
        source for source in normalized
        if source.get("source_type") == route["announcement_category"]
        and source.get("data_as_of") == outcome_period_end
    ]
    # The general Phase10 normalizer intentionally preserves the supplied
    # announcement row as an original disclosure record.  A minimal outcome
    # contract cannot infer that a later corrected/revised annual-report title
    # is the version to settle, even when it is the only row in a bounded
    # response.  This narrow adapter therefore records a mismatch rather than
    # choosing a revision or silently preferring an earlier title.
    if any(_REVISION_TITLE.search(str(source.get("title") or "")) for source in annual_period_candidates):
        return _mismatch(
            context,
            inventory_receipt_id=inventory_receipt_id,
            rule="ANNUAL_REPORT_REVISION_OR_CORRECTION_UNRESOLVED",
            detail="the bounded official metadata enumeration includes a revised, corrected, or updated annual report title",
        )
    candidates = [
        source for source in annual_period_candidates
        if _is_direct_original_annual_report(source.get("title"))
    ]
    if len(candidates) != 1:
        return _mismatch(
            context,
            inventory_receipt_id=inventory_receipt_id,
            rule="NO_UNIQUE_DIRECT_ANNUAL_REPORT",
            detail="the bounded official metadata enumeration did not identify one direct annual report for the frozen outcome period",
        )
    selected = candidates[0]
    if not episode._is_static_cninfo_finalpage_url(selected.get("url")):
        return _mismatch(
            context,
            inventory_receipt_id=inventory_receipt_id,
            rule="ANNUAL_REPORT_NOT_STATIC_FINALPAGE",
            detail="the uniquely identified annual report does not provide an exact static CNINFO finalpage PDF URL",
        )
    locator = field_locator(deepcopy(selected), deepcopy(contract)) if field_locator is not None else None
    if not isinstance(locator, str) or not locator.strip():
        return _mismatch(
            context,
            inventory_receipt_id=inventory_receipt_id,
            rule="DIRECT_FIELD_PAGE_LOCATOR_UNAVAILABLE",
            detail="the unique annual report has no custodian-declared direct PDF page locator for the frozen field",
        )
    source = {
        "source_id": selected["source_id"],
        "source_url": selected["url"],
        "source_type": episode.OFFICIAL_STATIC_FILING,
        "source_available_at": selected["published_at"],
        "source_available_precision": "DATE_ONLY",
        "issuer_id": contract["issuer_id"],
        "metric_id": contract["metric_id"],
        "measurement_period_end": contract["outcome_period_end"],
        "responsibility_boundary": contract["responsibility_boundary"],
        "unit": contract["unit"],
        "field_ref": locator.strip(),
    }
    candidate = _base_candidate(context, inventory_receipt_id=inventory_receipt_id, status="FIELD_READY")
    candidate["source"] = source
    return candidate
