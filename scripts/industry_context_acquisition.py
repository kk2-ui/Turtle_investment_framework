#!/usr/bin/env python3
"""Archive pre-registered official industry-context pages as raw PIT sources.

This is deliberately narrower than the Phase 10 company-disclosure collector.
It records only government context pages whose identity, availability date and
allowed use were fixed before download.  A successful archive is raw-source
completion, not a company fact or a substitute for licensed competitive data.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from scripts.phase10_acquisition import _is_date_precision, _package_relative_path, _resolve_package_path, _timestamp
except ModuleNotFoundError:  # pragma: no cover - CLI execution from scripts/
    from phase10_acquisition import _is_date_precision, _package_relative_path, _resolve_package_path, _timestamp


CATALOG_SCHEMA_VERSION = "official-industry-context-catalog.v1"
PACKAGE_SCHEMA_VERSION = "official-industry-context-source-package.v1"
OBSERVATION_SCHEMA_VERSION = "official-industry-context-observation-ledger.v1"
OFFICIAL_CONTEXT_SOURCE_TYPE = "OFFICIAL_INDUSTRY_CONTEXT"
CONTEXT_ONLY = "CONTEXT_ONLY"
ALLOWED_REPRESENTATIONS = {"ORIGINAL_HTML", "ORIGINAL_PDF", "ORIGINAL_DATA_EXPORT"}
ALLOWED_DRIVER_TYPES = {"demand", "supply", "competition", "regulation"}
CATALOG_SOURCE_FIELDS = (
    "source_id", "source_version", "source_type", "official", "title", "source_url",
    "official_host", "published_at", "data_as_of", "content_representation", "package_path",
    "use_policy", "coverage_ids", "permitted_inference", "prohibited_inference",
)


def _failure(code: str, source_id: str | None = None) -> str:
    return f"{source_id}:{code}" if source_id else code


def validate_official_context_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Validate identity, PIT availability and non-company-use boundaries."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(catalog, dict):
        return {"state": "INVALID", "invalid_findings": ["catalog_not_object"], "incomplete_findings": []}
    if catalog.get("schema_version") != CATALOG_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    cutoff_at = _timestamp(catalog.get("cutoff_at"))
    if cutoff_at is None:
        invalid.append("cutoff_at_invalid")
    if not str(catalog.get("industry_id") or "").strip():
        invalid.append("industry_id_missing")
    sources = catalog.get("sources")
    if not isinstance(sources, list) or not sources:
        invalid.append("sources_missing")
        sources = []
    seen_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            invalid.append("source_not_object")
            continue
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            invalid.append("source_id_missing")
            continue
        if source_id in seen_ids:
            invalid.append(_failure("duplicate_source_id", source_id))
        seen_ids.add(source_id)
        for field in (
            "source_version", "title", "official_host", "data_as_of",
            "published_at", "package_path", "permitted_inference",
        ):
            if not str(source.get(field) or "").strip():
                incomplete.append(_failure(f"{field}_missing", source_id))
        if source.get("source_type") != OFFICIAL_CONTEXT_SOURCE_TYPE:
            invalid.append(_failure("source_type_invalid", source_id))
        if source.get("official") is not True:
            invalid.append(_failure("official_required", source_id))
        if source.get("use_policy") != CONTEXT_ONLY:
            invalid.append(_failure("context_only_required", source_id))
        if source.get("content_representation") not in ALLOWED_REPRESENTATIONS:
            invalid.append(_failure("content_representation_invalid", source_id))
        url = str(source.get("source_url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            invalid.append(_failure("source_url_invalid", source_id))
        elif parsed.hostname != str(source.get("official_host") or "").strip():
            invalid.append(_failure("official_host_mismatch", source_id))
        if _package_relative_path(source.get("package_path")) is None:
            invalid.append(_failure("package_path_invalid", source_id))
        published_at = _timestamp(source.get("published_at"))
        data_as_of = _timestamp(source.get("data_as_of"))
        if published_at is None:
            invalid.append(_failure("published_at_invalid", source_id))
        if data_as_of is None:
            invalid.append(_failure("data_as_of_invalid", source_id))
        if cutoff_at is not None and published_at is not None:
            if published_at > cutoff_at:
                invalid.append(_failure("published_after_cutoff", source_id))
            elif published_at.date() == cutoff_at.date() and _is_date_precision(source.get("published_at")):
                invalid.append(_failure("published_time_unknown_at_cutoff", source_id))
        if cutoff_at is not None and data_as_of is not None and data_as_of > cutoff_at:
            invalid.append(_failure("data_as_of_after_cutoff", source_id))
        if not isinstance(source.get("coverage_ids"), list) or not source["coverage_ids"]:
            incomplete.append(_failure("coverage_ids_missing", source_id))
        if not isinstance(source.get("prohibited_inference"), list) or not source["prohibited_inference"]:
            incomplete.append(_failure("prohibited_inference_missing", source_id))
    return {
        "state": "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
    }


def validate_official_context_source_package(source_package: dict[str, Any]) -> dict[str, Any]:
    """Recheck the materialized package identity before observations can use it."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(source_package, dict):
        return {
            "state": "INVALID",
            "invalid_findings": ["source_package_not_object"],
            "incomplete_findings": [],
        }
    if source_package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        invalid.append("source_package_schema_version_invalid")
    if source_package.get("status") != "RAW_COMPLETE_PENDING_OBSERVATION_REVIEW":
        invalid.append("source_package_status_invalid")
    if source_package.get("use_policy") != CONTEXT_ONLY:
        invalid.append("source_package_context_only_required")

    sources = source_package.get("sources")
    if not isinstance(sources, list) or not sources:
        invalid.append("source_package_sources_missing")
        sources = []
    catalog_projection = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "industry_id": source_package.get("industry_id"),
        "cutoff_at": source_package.get("cutoff_at"),
        "sources": [
            {field: source.get(field) for field in CATALOG_SOURCE_FIELDS}
            for source in sources
            if isinstance(source, dict)
        ],
    }
    catalog_result = validate_official_context_catalog(catalog_projection)
    invalid.extend("source_package:" + item for item in catalog_result["invalid_findings"])
    incomplete.extend("source_package:" + item for item in catalog_result["incomplete_findings"])

    materialized_count = 0
    failed_count = 0
    for source in sources:
        if not isinstance(source, dict):
            invalid.append("source_package:source_not_object")
            continue
        source_id = str(source.get("source_id") or "").strip() or None
        status = source.get("materialization_status")
        if status in {"MATERIALIZED", "ALREADY_MATERIALIZED"}:
            materialized_count += 1
        elif status == "FAILED":
            failed_count += 1
        else:
            invalid.append(_failure("materialization_status_invalid", source_id))
    expected_counts = {
        "source_count": len(sources),
        "materialized_count": materialized_count,
        "failed_count": failed_count,
    }
    for field, expected in expected_counts.items():
        if source_package.get(field) != expected:
            invalid.append(f"source_package_{field}_mismatch")
    if failed_count:
        invalid.append("source_package_contains_failed_source")
    return {
        "state": "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE",
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
    }


def _download_original(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": "TurtleResearch/1.0", "Accept": "*/*"})
    with urlopen(request, timeout=60) as response:
        return response.read(), response.geturl()


def materialize_official_context_package(
    catalog: dict[str, Any],
    package_root: str | Path,
    *,
    downloader: Callable[[str], tuple[bytes, str]] = _download_original,
) -> dict[str, Any]:
    """Save each raw official response without elevating it to a company fact."""
    validation = validate_official_context_catalog(catalog)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("official context catalog is not reviewable: " + ",".join([
            *validation["invalid_findings"], *validation["incomplete_findings"],
        ]))
    root = Path(package_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for source in catalog["sources"]:
        record = {
            key: source[key]
            for key in CATALOG_SOURCE_FIELDS
        }
        destination = _resolve_package_path(root, source["package_path"], field="source.package_path")
        if destination.is_file() and destination.stat().st_size > 0:
            record["materialization_status"] = "ALREADY_MATERIALIZED"
            records.append(record)
            continue
        try:
            body, final_url = downloader(source["source_url"])
            final_host = urlparse(final_url).hostname
            if final_host != source["official_host"]:
                raise ValueError("redirected_to_non_official_host")
            if not body:
                raise ValueError("empty_response")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError("destination_exists_but_not_materialized")
            destination.write_bytes(body)
            record["materialization_status"] = "MATERIALIZED"
            record["local_path"] = source["package_path"]
        except Exception as exc:  # retained in manifest; never silently substitute a current page
            record["materialization_status"] = "FAILED"
            record["error"] = str(exc)
        records.append(record)
    failed = sum(item["materialization_status"] == "FAILED" for item in records)
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "status": "RAW_COMPLETE_PENDING_OBSERVATION_REVIEW" if not failed else "RAW_INCOMPLETE",
        "industry_id": catalog["industry_id"],
        "cutoff_at": catalog["cutoff_at"],
        "use_policy": CONTEXT_ONLY,
        "source_count": len(records),
        "materialized_count": sum(item["materialization_status"] in {"MATERIALIZED", "ALREADY_MATERIALIZED"} for item in records),
        "failed_count": failed,
        "sources": records,
    }


def validate_official_context_observation_ledger(
    ledger: dict[str, Any],
    source_package: dict[str, Any],
    *,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    """Admit only locator-backed, context-only observations from raw sources."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(ledger, dict):
        return {"state": "INVALID", "invalid_findings": ["observation_ledger_not_object"], "incomplete_findings": []}
    if ledger.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        invalid.append("observation_schema_version_invalid")
    if ledger.get("use_policy") != CONTEXT_ONLY:
        invalid.append("observation_context_only_required")
    for field in ("ledger_id", "industry_id", "source_package_ref"):
        if not str(ledger.get(field) or "").strip():
            invalid.append(f"{field}_missing")
    ledger_cutoff = _timestamp(ledger.get("cutoff_at"))
    if ledger_cutoff is None:
        invalid.append("cutoff_at_invalid")
    package_validation = validate_official_context_source_package(source_package)
    if package_validation["state"] != "REVIEWABLE":
        invalid.append("raw_source_package_not_complete")
        invalid.extend(package_validation["invalid_findings"])
        incomplete.extend(package_validation["incomplete_findings"])
        available_sources: dict[str, dict[str, Any]] = {}
    else:
        if source_package.get("industry_id") != ledger.get("industry_id"):
            invalid.append("source_package_industry_mismatch")
        if source_package.get("cutoff_at") != ledger.get("cutoff_at"):
            invalid.append("source_package_cutoff_mismatch")
        available_sources = {
            str(source.get("source_id") or ""): source
            for source in source_package.get("sources") or []
            if source.get("materialization_status") in {"MATERIALIZED", "ALREADY_MATERIALIZED"}
        }
        if package_root is not None:
            root = Path(package_root).expanduser().resolve()
            for source_id, source in available_sources.items():
                try:
                    raw_path = _resolve_package_path(
                        root,
                        source.get("package_path"),
                        field="source.package_path",
                    )
                except ValueError:
                    invalid.append(_failure("raw_source_path_invalid", source_id))
                    continue
                if not raw_path.is_file() or raw_path.stat().st_size <= 0:
                    invalid.append(_failure("raw_source_file_missing", source_id))
    observations = ledger.get("observations")
    if not isinstance(observations, list) or not observations:
        invalid.append("observations_missing")
        observations = []
    seen_ids: set[str] = set()
    for observation in observations:
        if not isinstance(observation, dict):
            invalid.append("observation_not_object")
            continue
        observation_id = str(observation.get("observation_id") or "").strip()
        if not observation_id:
            invalid.append("observation_id_missing")
            continue
        if observation_id in seen_ids:
            invalid.append(_failure("duplicate_observation_id", observation_id))
        seen_ids.add(observation_id)
        if observation.get("use_policy") != CONTEXT_ONLY:
            invalid.append(_failure("context_only_required", observation_id))
        if observation.get("driver_type") not in ALLOWED_DRIVER_TYPES:
            invalid.append(_failure("driver_type_invalid", observation_id))
        for field in (
            "metric_definition", "period", "value", "statement",
            "economic_interpretation", "profit_pool_effect", "permitted_inference",
        ):
            if field not in observation or observation.get(field) in (None, "", [], {}):
                incomplete.append(_failure(f"{field}_missing", observation_id))
        if not isinstance(observation.get("prohibited_inference"), list) or not observation["prohibited_inference"]:
            incomplete.append(_failure("prohibited_inference_missing", observation_id))
        locators = observation.get("source_locators")
        if not isinstance(locators, list) or not locators:
            incomplete.append(_failure("source_locators_missing", observation_id))
            continue
        for locator in locators:
            if not isinstance(locator, dict):
                invalid.append(_failure("source_locator_not_object", observation_id))
                continue
            source_id = str(locator.get("source_id") or "").strip()
            if source_id not in available_sources:
                invalid.append(_failure("source_not_materialized", observation_id))
            if not str(locator.get("locator") or "").strip():
                incomplete.append(_failure("locator_missing", observation_id))
    return {
        "state": "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE_CONTEXT_ONLY",
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "materialize", "validate-observations"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--source-package", type=Path)
    args = parser.parse_args()
    catalog = json.loads(args.input.read_text(encoding="utf-8"))
    if args.command == "validate":
        result = validate_official_context_catalog(catalog)
        _write(args.output, result)
        print(json.dumps({"written": str(args.output), "state": result["state"]}, ensure_ascii=False))
        return 0 if result["state"] == "REVIEWABLE" else 1
    if args.command == "validate-observations":
        if args.source_package is None:
            parser.error("--source-package is required for validate-observations")
        source_package = json.loads(args.source_package.read_text(encoding="utf-8"))
        result = validate_official_context_observation_ledger(
            catalog,
            source_package,
            package_root=args.source_package.parent,
        )
        _write(args.output, result)
        print(json.dumps({"written": str(args.output), "state": result["state"]}, ensure_ascii=False))
        return 0 if result["state"] == "REVIEWABLE_CONTEXT_ONLY" else 1
    if args.package_root is None:
        parser.error("--package-root is required for materialize")
    payload = materialize_official_context_package(catalog, args.package_root)
    _write(args.output, payload)
    print(json.dumps({"written": str(args.output), "status": payload["status"], "materialized_count": payload["materialized_count"], "failed_count": payload["failed_count"]}, ensure_ascii=False))
    return 0 if payload["status"] == "RAW_COMPLETE_PENDING_OBSERVATION_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
