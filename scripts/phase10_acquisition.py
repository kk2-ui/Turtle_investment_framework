#!/usr/bin/env python3
"""Point-in-time source acquisition primitives for the Phase 10 first case.

The module is deliberately an offline boundary layer.  A caller may feed it
the records returned by an SSE announcement export or an already downloaded
source catalog; it never uses the current web page as a proxy for a historical
vintage.  Every discovered announcement is retained, including rejected
records, so later review can distinguish an incomplete enumeration from an
empty selection.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


MANIFEST_SCHEMA_VERSION = "phase10-source-manifest.v1"
DEFAULT_COMPANY_CODE = "600340.SH"
DEFAULT_CUTOFF_AT = "2020-04-27T18:00:00+08:00"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

ADMITTED = "ADMITTED"
REJECTION_REASONS = {
    "FUTURE_PUBLISHED_AT",
    "FUTURE_DATA_AS_OF",
    "FUTURE_REVISION",
    "CURRENT_RESTATED_ONLY",
    "SUPERSEDED_BEFORE_CUTOFF",
    "MISSING_IDENTITY",
    "DUPLICATE_SOURCE_ID",
    "MISSING_ANNOUNCEMENT_TITLE",
    "MISSING_ANNOUNCEMENT_DATE",
}


def _timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp, treating date-only values as local midnight."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), time.min)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def _copy_record(record: dict[str, Any], **updates: Any) -> dict[str, Any]:
    result = deepcopy(record)
    result.update(updates)
    return result


def _source_identity_ok(source: dict[str, Any]) -> bool:
    required = ("source_id", "source_version", "source_type", "published_at", "data_as_of", "revision_policy")
    return all(str(source.get(field) or "").strip() for field in required)


def _reject(source: dict[str, Any], reason: str) -> dict[str, Any]:
    return _copy_record(source, admissible=False, admission_status=f"REJECTED_{reason}")


def _admit_one(source: dict[str, Any], cutoff: datetime) -> dict[str, Any]:
    if str(source.get("admission_status") or "").startswith("REJECTED_"):
        return _copy_record(source, admissible=False)
    if not _source_identity_ok(source):
        return _reject(source, "MISSING_IDENTITY")
    published = _timestamp(source["published_at"])
    data_as_of = _timestamp(source["data_as_of"])
    revision_at = _timestamp(source.get("revision_published_at")) if source.get("revision_published_at") else None
    if published is None:
        return _reject(source, "MISSING_IDENTITY")
    if published > cutoff:
        return _reject(source, "FUTURE_PUBLISHED_AT")
    if data_as_of is None:
        return _reject(source, "MISSING_IDENTITY")
    if data_as_of > cutoff:
        return _reject(source, "FUTURE_DATA_AS_OF")
    if revision_at and revision_at > cutoff:
        return _reject(source, "FUTURE_REVISION")
    if source.get("revision_policy") == "CURRENT_RESTATED_ONLY":
        return _reject(source, "CURRENT_RESTATED_ONLY")
    return _copy_record(source, admissible=True, admission_status=ADMITTED)


def _supersession_group(source: dict[str, Any]) -> str | None:
    group = source.get("version_group") or source.get("revision_group")
    if group:
        return str(group)
    # A revision may explicitly identify the source it replaces.  Both records
    # are placed in the same group without requiring a naming convention.
    supersedes = source.get("supersedes")
    if isinstance(supersedes, list) and supersedes:
        return str(supersedes[0])
    return None


def admit_source_manifest(
    sources: Iterable[dict[str, Any]],
    *,
    cutoff_at: str = DEFAULT_CUTOFF_AT,
    company_code: str = DEFAULT_COMPANY_CODE,
) -> dict[str, Any]:
    """Admit a source catalog at a precise cutoff, retaining every decision.

    The newest admissible version in a declared ``version_group`` wins.  An
    older version is explicitly retained as ``REJECTED_SUPERSEDED...`` rather
    than silently dropped.  This is what makes the 2017 original annual report
    fail in favor of its 2018-04-21 revision.
    """
    cutoff = _timestamp(cutoff_at)
    if cutoff is None:
        raise ValueError(f"invalid cutoff_at: {cutoff_at!r}")
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for raw in sources:
        source = deepcopy(raw)
        source_id = str(source.get("source_id") or "")
        if source_id and source_id in seen:
            duplicate_ids.add(source_id)
        if source_id:
            seen.add(source_id)
        decision = _admit_one(source, cutoff)
        if source_id in duplicate_ids:
            decision = _reject(decision, "DUPLICATE_SOURCE_ID")
        decisions.append(decision)

    # Apply version replacement only among records that passed the temporal
    # fence.  A revision published after cutoff cannot replace the vintage.
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, decision in enumerate(decisions):
        if decision.get("admissible") is True:
            group = _supersession_group(decision)
            if group:
                groups.setdefault(group, []).append((index, decision))
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda item: (_timestamp(item[1].get("published_at")) or datetime.min.replace(tzinfo=timezone.utc), item[0]))
        for index, _decision in members[:-1]:
            decisions[index] = _reject(decisions[index], "SUPERSEDED_BEFORE_CUTOFF")

    admitted = [item for item in decisions if item.get("admissible") is True]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "company_code": company_code,
        "cutoff_at": cutoff.isoformat(),
        "cutoff_timezone": "Asia/Shanghai",
        "sources": decisions,
        "admitted_source_ids": [str(item["source_id"]) for item in admitted],
        "rejected_source_ids": [str(item.get("source_id") or "") for item in decisions if item.get("admissible") is not True],
        "admitted_count": len(admitted),
        "rejected_count": len(decisions) - len(admitted),
    }


def enumerate_sse_announcements(
    records: Iterable[dict[str, Any]],
    *,
    cutoff_at: str = DEFAULT_CUTOFF_AT,
    period_start: str = "2018-01-01",
) -> dict[str, Any]:
    """Preserve a full SSE announcement inventory before source selection.

    ``records`` is expected to be the complete result of an SSE page/export for
    the requested period.  The function does not silently discard a future or
    malformed row: each row becomes a source decision and remains reviewable.
    """
    materialized = [deepcopy(item) for item in records]
    normalized: list[dict[str, Any]] = []
    for item in materialized:
        title = str(item.get("title") or item.get("announcement_title") or "").strip()
        published_value = item.get("published_at") or item.get("announcement_date")
        published = _timestamp(published_value)
        source = _copy_record(
            item,
            source_id=item.get("source_id") or f"SSE:600340:ANN:{published_value}:{title}",
            source_version=item.get("source_version") or "sse-announcement-original",
            source_type=item.get("source_type") or "EXCHANGE_ANNOUNCEMENT",
            revision_policy=item.get("revision_policy") or "ORIGINAL_VINTAGE",
            published_at=published_value,
            data_as_of=item.get("data_as_of") or (published.date().isoformat() if published else ""),
            title=title,
        )
        if not title:
            normalized.append(_reject(source, "MISSING_ANNOUNCEMENT_TITLE"))
        elif published is None:
            normalized.append(_reject(source, "MISSING_ANNOUNCEMENT_DATE"))
        else:
            normalized.append(source)
    normalized.sort(key=lambda item: (_timestamp(item.get("published_at")) or datetime.max.replace(tzinfo=timezone.utc), str(item.get("title") or "")))
    manifest = admit_source_manifest(normalized, cutoff_at=cutoff_at)
    manifest.update({
        "inventory_kind": "SSE_ANNOUNCEMENT_FULL_ENUMERATION",
        "period_start": period_start,
        "period_end": _timestamp(cutoff_at).date().isoformat() if _timestamp(cutoff_at) else cutoff_at[:10],
        "enumeration_complete": True,
        "inventory_count": len(normalized),
        "inventory": manifest.pop("sources"),
    })
    # The generic manifest still exposes selected source records via `sources`;
    # keeping `inventory` as the authoritative full list avoids losing rejects.
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["admitted_source_ids"] = [str(item["source_id"]) for item in manifest["sources"]]
    manifest["rejected_source_ids"] = [str(item.get("source_id") or "") for item in manifest["inventory"] if item.get("admissible") is not True]
    manifest["admitted_count"] = len(manifest["sources"])
    manifest["rejected_count"] = len(manifest["inventory"]) - len(manifest["sources"])
    return manifest


def validate_source_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a persisted manifest without contacting the network."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    cutoff = _timestamp(manifest.get("cutoff_at"))
    if cutoff is None:
        invalid.append("cutoff_at_invalid")
        cutoff = _timestamp(DEFAULT_CUTOFF_AT)
    inventory = manifest.get("inventory") if isinstance(manifest.get("inventory"), list) else manifest.get("sources")
    if not isinstance(inventory, list) or not inventory:
        incomplete.append("inventory_missing")
        inventory = []
    if manifest.get("enumeration_complete") is not True:
        incomplete.append("sse_enumeration_incomplete")
    ids: set[str] = set()
    for index, source in enumerate(inventory):
        if not isinstance(source, dict):
            invalid.append(f"inventory[{index}]:not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            invalid.append(f"inventory[{index}]:source_id_missing")
        elif source_id in ids:
            invalid.append(f"inventory[{index}]:duplicate_source_id:{source_id}")
        ids.add(source_id)
        published = _timestamp(source.get("published_at"))
        data_as_of = _timestamp(source.get("data_as_of"))
        if source.get("admissible") is True:
            if published is None or data_as_of is None:
                invalid.append(f"inventory[{index}]:admitted_missing_time_identity")
            elif published > cutoff:
                invalid.append(f"inventory[{index}]:admitted_future_published_at")
            elif data_as_of > cutoff:
                invalid.append(f"inventory[{index}]:admitted_future_data_as_of")
        elif not str(source.get("admission_status") or "").startswith("REJECTED_"):
            incomplete.append(f"inventory[{index}]:rejection_reason_missing")
    admitted_ids = [str(item.get("source_id")) for item in inventory if isinstance(item, dict) and item.get("admissible") is True]
    if manifest.get("admitted_source_ids") != admitted_ids:
        invalid.append("admitted_source_ids_mismatch")
    expected_count = len(admitted_ids)
    if manifest.get("admitted_count") != expected_count:
        invalid.append("admitted_count_mismatch")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def build_600340_source_manifest() -> dict[str, Any]:
    """Build the offline catalog of known pre-cutoff primary documents.

    This is a catalog, not a claim that PDFs have been downloaded.  The SSE
    announcement inventory is intentionally empty/incomplete until a complete
    export is supplied to :func:`enumerate_sse_announcements`.
    """
    documents = [
        {
            "source_id": "SSE:600340:AR2019:ORIGINAL",
            "source_version": "annual-report-2019-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2019 年年度报告",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2020-04-25/600340_20200425_22.pdf",
            "published_at": "2020-04-25",
            "data_as_of": "2019-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2018:ORIGINAL",
            "source_version": "annual-report-2018-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2018 年年度报告",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2019-04-20/600340_2018_n.pdf",
            "published_at": "2019-04-20",
            "data_as_of": "2018-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:ORIGINAL",
            "source_version": "annual-report-2017-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2017 年年度报告（原始版）",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-03-30/600340_2017_n.pdf",
            "published_at": "2018-03-30",
            "data_as_of": "2017-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "version_group": "SSE:600340:AR2017",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:REVISED",
            "source_version": "annual-report-2017-revised-2018-04-21",
            "source_type": "ANNUAL_REPORT",
            "title": "2017 年年度报告（修订版）",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-21/600340_2017_nB.pdf",
            "published_at": "2018-04-21",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "version_group": "SSE:600340:AR2017",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:INQUIRY_LETTER",
            "source_version": "annual-report-inquiry-letter-2018-04-14",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "关于对华夏幸福基业股份有限公司2017年年度报告的事后审核问询函",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-14/600340_20180414_1.pdf",
            "published_at": "2018-04-14",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:INQUIRY_REPLY",
            "source_version": "annual-report-inquiry-reply-2018-04-21",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "2017 年报问询回复",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-21/600340_20180421_9.pdf",
            "published_at": "2018-04-21",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "admissible": True,
        },
    ]
    manifest = admit_source_manifest(documents, company_code=DEFAULT_COMPANY_CODE)
    manifest["inventory_kind"] = "KNOWN_PRIMARY_DOCUMENT_CATALOG"
    manifest["enumeration_complete"] = False
    manifest["inventory"] = manifest.pop("sources")
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["acquisition_status"] = "CATALOG_ONLY_NO_NETWORK_FETCH"
    manifest["announcement_inventory"] = {
        "inventory_kind": "SSE_ANNOUNCEMENT_FULL_ENUMERATION",
        "period_start": "2018-01-01",
        "period_end": "2020-04-27",
        "enumeration_complete": False,
        "records": [],
    }
    return manifest


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catalog", "validate", "enumerate"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "catalog":
        payload = build_600340_source_manifest()
    else:
        if args.input is None:
            parser.error("--input is required for validate/enumerate")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.command == "validate":
            result = validate_source_manifest(payload)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["state"] == "REVIEWABLE" else 1
        records = payload.get("records") if isinstance(payload, dict) else payload
        payload = enumerate_sse_announcements(records or [])
    _write(args.output, payload)
    print(json.dumps({"written": str(args.output), "admitted_count": payload.get("admitted_count", 0)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
