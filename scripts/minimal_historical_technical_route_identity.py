#!/usr/bin/env python3
"""Resolve a value-free CNINFO code-to-orgId technical route identity.

This adapter deliberately separates a current exchange routing lookup from
company evidence. It never returns an issuer name, title, announcement, PDF,
body, price, or outcome. The resulting receipt can be frozen only before a
Measurement Contract v2 and only against the matching Decision Contract.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

try:
    from scripts import minimal_historical_episode as episode
    from scripts.downloaders.cninfo import CninfoDownloader
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as episode
    from downloaders.cninfo import CninfoDownloader


RouteResolver = Callable[[str], Mapping[str, Any]]


def resolve_cninfo_stock_map_code_to_org_id(
    security_code: str, *, downloader: CninfoDownloader | None = None,
) -> dict[str, str]:
    """Project the downloader's stock-map response to the only allowed fields."""
    code = str(security_code or "").strip()
    resolved = (downloader or CninfoDownloader()).resolve_company(code)
    organization_id = str(resolved.get("org_id") or "").strip()
    if not organization_id:
        raise ValueError("CNINFO stock-map resolver returned no organization id")
    # Do not return the downloader's company name, market label, or any other
    # stock-map field. This is technical routing provenance only.
    return {"security_code": code, "organization_id": organization_id}


def _mismatch(*, rule: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "turtle-minimal-historical-episode-technical-route-resolution.v1",
        "status": "MEASUREMENT_MISMATCH",
        "mismatch_rule": rule,
        "mismatch_detail": detail,
        "object_class": "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY_RESOLUTION",
        "claim_class": "TECHNICAL_ROUTE_IDENTITY_ONLY",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def resolve_technical_route_identity(
    *,
    technical_route_identity_id: str,
    technical_route_identity_version: int,
    decision_contract: dict[str, Any],
    observed_at: str,
    resolver: RouteResolver = resolve_cninfo_stock_map_code_to_org_id,
) -> dict[str, Any]:
    """Return a ready receipt or a value-free resolver mismatch.

    ``resolver`` may receive only the Decision Contract's six-digit code and
    must return exactly ``security_code`` plus ``organization_id``. Extra
    response fields are rejected, not silently discarded, so titles, names,
    disclosure metadata, and outcome material cannot cross this boundary.
    """
    decision_result = episode.validate_decision_contract(decision_contract)
    if not decision_result["valid"]:
        return _mismatch(
            rule="DECISION_CONTRACT_INVALID",
            detail="a valid frozen decision contract is required for technical route identity",
        )
    decision = decision_result["decision_contract"]
    company_id = decision["company_id"]
    if not company_id.startswith("CN:"):
        return _mismatch(
            rule="TECHNICAL_ROUTE_COMPANY_ID_UNSUPPORTED",
            detail="technical CNINFO route identity requires a CN six-digit company identity",
        )
    security_code = company_id.removeprefix("CN:")
    try:
        response = resolver(security_code)
    except Exception:
        return _mismatch(
            rule="CNINFO_TECHNICAL_ROUTE_RESOLVER_UNAVAILABLE",
            detail="the official code-to-organization routing resolver could not return the expected mapping",
        )
    if not isinstance(response, Mapping) or set(response) != {"security_code", "organization_id"}:
        return _mismatch(
            rule="CNINFO_TECHNICAL_ROUTE_RESOLVER_RESPONSE_INVALID",
            detail="the routing resolver must return only the expected code-to-organization mapping",
        )
    returned_code = str(response.get("security_code") or "").strip()
    organization_id = str(response.get("organization_id") or "").strip()
    if returned_code != security_code or not organization_id:
        return _mismatch(
            rule="CNINFO_TECHNICAL_ROUTE_IDENTITY_MISMATCH",
            detail="the resolver response does not bind the expected security code to one organization id",
        )
    receipt = {
        "schema_version": episode.TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION,
        "technical_route_identity_id": technical_route_identity_id,
        "technical_route_identity_version": technical_route_identity_version,
        "decision_contract_ref": {
            "decision_contract_id": decision["decision_contract_id"],
            "decision_contract_version": decision["decision_contract_version"],
        },
        "company_id": company_id,
        "issuer_id": decision["issuer_id"],
        "security_code": security_code,
        "organization_id": organization_id,
        "resolver_endpoint": episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT,
        "resolver_version": episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION,
        "observed_at": observed_at,
        "object_class": "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY",
        "claim_class": "TECHNICAL_ROUTE_IDENTITY",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }
    validation = episode.validate_technical_route_identity(receipt, decision_contract=decision)
    if not validation["valid"]:
        return _mismatch(
            rule="CNINFO_TECHNICAL_ROUTE_IDENTITY_INVALID",
            detail="the resolver output cannot form a closed technical route identity receipt",
        )
    return {"status": "TECHNICAL_ROUTE_IDENTITY_READY", "technical_route_identity": deepcopy(receipt)}
