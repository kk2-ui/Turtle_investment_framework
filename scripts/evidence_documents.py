#!/usr/bin/env python3
"""Build deterministic identities for cached official evidence documents.

The manifest deliberately separates an original filing (normally PDF) from
its page-marked Markdown derivative.  A derivative is a locator aid, not an
independent source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "document-manifest.v1"
POLICY_VERSION = "official-evidence-policy.v1"
_FILING_RE = re.compile(
    r"^(?:(?P<file_code>[A-Za-z0-9.]+)_)?(?P<year>20\d{2})_(?P<kind>年报|中报)(?:[^/]*)\.(?P<ext>pdf|md)$",
    re.IGNORECASE,
)

_REGISTERED_DOC_TYPES = {
    "quarterly_report",
    "company_announcement",
    "company_circular",
    "exchange_announcement",
    "official_statistics",
    "other_official",
    "licensed_industry_data",
}
_REGISTERED_AUTHORITIES_BY_DOC_TYPE = {
    "quarterly_report": "company_filing",
    "company_announcement": "company_filing",
    "company_circular": "company_filing",
    "exchange_announcement": "company_filing",
    "official_statistics": "official_statistics",
    "other_official": "other_official",
    "licensed_industry_data": "industry_data",
}
_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
    ".htm": "text/html",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, prefix=path.name + "."
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def normalize_security_identity(code: str, output_dir: str | Path) -> tuple[str, str, str]:
    """Return canonical ``(code, market, issuer)`` without external lookups."""
    raw = str(code or "").strip().upper()
    base, dot, suffix = raw.partition(".")
    base = base or Path(output_dir).name.split("_", 1)[0].upper()
    if dot:
        market = {"HK": "HK", "SZ": "CN-SZ", "SH": "CN-SH", "BJ": "CN-BJ", "US": "US", "DE": "DE"}.get(suffix, suffix)
    elif base.isdigit() and len(base) == 5:
        market = "HK"
    elif base.startswith(("0", "2", "3")):
        market = "CN-SZ"
    elif base.startswith(("6", "9")):
        market = "CN-SH"
    else:
        market = "UNKNOWN"
    dirname = Path(output_dir).name
    issuer = dirname.split("_", 1)[1] if "_" in dirname else base
    issuer = re.sub(r"_(?:phase|stage|try).*$", "", issuer, flags=re.IGNORECASE).strip() or base
    return base, market, issuer


def _filing_parts(path: Path) -> dict[str, Any] | None:
    match = _FILING_RE.match(path.name)
    if not match:
        return None
    year = int(match.group("year"))
    kind = match.group("kind")
    annual = kind == "年报"
    return {
        "year": year,
        "kind": kind,
        "doc_type": "annual_report" if annual else "interim_report",
        "fiscal_period": f"FY{year}" if annual else f"H1-{year}",
        "period_end": f"{year}-12-31" if annual else f"{year}-06-30",
        "authority": "audited_filing" if annual else "company_filing",
        "mime_type": "application/pdf" if path.suffix.lower() == ".pdf" else "text/markdown",
    }


def _registered_document_parts(path: Path, source_record: dict[str, Any]) -> dict[str, Any] | None:
    """Read an explicitly registered non-annual official document.

    Generic files are never inferred from their filename.  Their sidecar must
    state the economic document identity needed by PIT evidence: document
    type, authority, covered period, and publication date.  This lets an
    announcement, circular, regulatory instrument, tender record, or official
    dataset enter the same evidence manifest without pretending it is an
    annual report.
    """
    doc_type = source_record.get("doc_type")
    if doc_type is None:
        return None
    if doc_type not in _REGISTERED_DOC_TYPES:
        raise ValueError(f"registered_document_type_invalid:{path.name}:{doc_type}")
    authority = source_record.get("authority")
    if authority != _REGISTERED_AUTHORITIES_BY_DOC_TYPE[doc_type]:
        raise ValueError(f"registered_document_authority_invalid:{path.name}:{authority}")
    fiscal_period = str(source_record.get("fiscal_period") or "").strip()
    period_end = str(source_record.get("period_end") or "").strip()
    published_at = str(source_record.get("published_at") or "").strip()
    if not fiscal_period:
        raise ValueError(f"registered_document_fiscal_period_missing:{path.name}")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", period_end):
            raise ValueError
        datetime.fromisoformat(period_end).date()
    except ValueError:
        raise ValueError(f"registered_document_period_end_invalid:{path.name}")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T[^ ]+)?", published_at):
            raise ValueError
        datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"registered_document_published_at_invalid:{path.name}")
    mime_type = str(source_record.get("mime_type") or _MIME_TYPES.get(path.suffix.lower()) or "").strip()
    if not mime_type:
        raise ValueError(f"registered_document_mime_type_missing:{path.name}")
    return {
        "doc_type": doc_type,
        "fiscal_period": fiscal_period,
        "period_end": period_end,
        "published_at": published_at,
        "authority": authority,
        "mime_type": mime_type,
        "language": str(source_record.get("language") or "zh").strip(),
        "derived_text_path": source_record.get("derived_text_path"),
    }


def _copy_optional_source_fields(document: dict[str, Any], source_record: dict[str, Any]) -> None:
    for field in ("source_id", "source_version", "revision_policy", "source_role_provenance"):
        if source_record.get(field) not in (None, "", {}):
            document[field] = deepcopy(source_record[field])


def _manifest_core(payload: dict[str, Any]) -> dict[str, Any]:
    core = deepcopy(payload)
    core.pop("generated_at", None)
    core.pop("manifest_hash", None)
    core.pop("validation", None)
    return core


def validate_document_manifest(payload: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    documents = payload.get("documents")
    if not isinstance(documents, list):
        invalid.append("documents_not_array")
        documents = []
    seen: set[str] = set()
    latest_annual = False
    for index, doc in enumerate(documents):
        prefix = f"documents[{index}]"
        if not isinstance(doc, dict):
            invalid.append(prefix + ":not_object")
            continue
        doc_id = str(doc.get("doc_id") or "")
        if not doc_id.startswith("DOC:"):
            invalid.append(prefix + ":doc_id_invalid")
        elif doc_id in seen:
            invalid.append("duplicate_doc_id:" + doc_id)
        seen.add(doc_id)
        digest = str(doc.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            invalid.append(f"{doc_id or prefix}:sha256_invalid")
        local_path = str(doc.get("local_path") or "")
        if output_dir is not None and local_path:
            resolved = Path(output_dir) / local_path
            if not resolved.is_file():
                invalid.append(f"{doc_id or prefix}:local_file_missing:{local_path}")
            elif _sha256_bytes(resolved) != digest:
                invalid.append(f"{doc_id or prefix}:content_hash_mismatch")
        if doc.get("doc_type") == "annual_report" and doc.get("authority") == "audited_filing":
            latest_annual = True
        if not doc.get("source_url"):
            warnings.append(f"{doc_id or prefix}:source_url_unrecorded")
        derived = doc.get("derived_text_path")
        if derived and output_dir is not None and not (Path(output_dir) / str(derived)).is_file():
            warnings.append(f"{doc_id or prefix}:derived_text_missing:{derived}")
    expected_hash = _payload_hash(_manifest_core(payload))
    if payload.get("manifest_hash") != expected_hash:
        invalid.append("manifest_hash_mismatch")
    if not documents:
        incomplete.append("official_document_missing")
    elif not latest_annual:
        incomplete.append("audited_annual_report_missing")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "state": state,
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
        "warnings": list(dict.fromkeys(warnings)),
        "document_count": len(documents),
    }


def build_document_manifest(
    output_dir: str | Path,
    code: str,
    *,
    source_urls: dict[str, str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    canonical_code, market, issuer = normalize_security_identity(code, output)
    urls = source_urls or {}
    try:
        source_registry = json.loads((output / "document_sources.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        source_registry = {}
    source_records = source_registry.get("documents") if isinstance(source_registry, dict) else {}
    if not isinstance(source_records, dict):
        source_records = {}
    pdfs: list[tuple[Path, dict[str, Any]]] = []
    markdown_by_key: dict[tuple[int, str], Path] = {}
    for path in sorted(output.iterdir()) if output.is_dir() else []:
        if not path.is_file():
            continue
        parts = _filing_parts(path)
        if not parts:
            continue
        key = (int(parts["year"]), str(parts["kind"]))
        if path.suffix.lower() == ".pdf":
            pdfs.append((path, parts))
        elif path.suffix.lower() == ".md":
            markdown_by_key[key] = path
    latest_period = max((parts["period_end"] for _, parts in pdfs), default="unknown")
    report_id = f"REPORT:{market}:{canonical_code}:{latest_period}"
    documents: list[dict[str, Any]] = []
    original_keys: set[tuple[int, str]] = set()
    for path, parts in pdfs:
        key = (int(parts["year"]), str(parts["kind"]))
        original_keys.add(key)
        digest = _sha256_bytes(path)
        doc_id = f"DOC:{market}:{canonical_code}:{parts['doc_type']}:{parts['period_end']}:{digest[:12]}"
        derivative = markdown_by_key.get(key)
        source_record = source_records.get(path.name) if isinstance(source_records.get(path.name), dict) else {}
        document = {
            "doc_id": doc_id,
            "report_id": report_id,
            "issuer": issuer,
            "code": canonical_code,
            "market": market,
            "doc_type": parts["doc_type"],
            "fiscal_period": parts["fiscal_period"],
            "period_end": parts["period_end"],
            "published_at": source_record.get("published_at"),
            "authority": parts["authority"],
            "source_url": urls.get(path.name) or source_record.get("source_url"),
            "local_path": path.name,
            "derived_text_path": derivative.name if derivative else None,
            "sha256": digest,
            "mime_type": "application/pdf",
            "language": "zh",
            "acquisition_status": "DOWNLOADED" if source_record else "CACHED",
        }
        _copy_optional_source_fields(document, source_record)
        documents.append(document)
    for key, path in sorted(markdown_by_key.items()):
        if key in original_keys:
            continue
        parts = _filing_parts(path)
        assert parts is not None
        digest = _sha256_bytes(path)
        doc_type = parts["doc_type"] + "_text"
        doc_id = f"DOC:{market}:{canonical_code}:{doc_type}:{parts['period_end']}:{digest[:12]}"
        documents.append({
            "doc_id": doc_id,
            "report_id": report_id,
            "issuer": issuer,
            "code": canonical_code,
            "market": market,
            "doc_type": doc_type,
            "fiscal_period": parts["fiscal_period"],
            "period_end": parts["period_end"],
            "published_at": None,
            "authority": "derived",
            "source_url": None,
            "local_path": path.name,
            "derived_text_path": path.name,
            "sha256": digest,
            "mime_type": "text/markdown",
            "language": "zh",
            "acquisition_status": "DERIVED_ONLY",
        })

    filing_names = {path.name for path, _ in pdfs}.union(path.name for path in markdown_by_key.values())
    for filename, raw_record in sorted(source_records.items()):
        if filename in filing_names or not isinstance(raw_record, dict):
            continue
        path = output / filename
        if raw_record.get("doc_type") is None:
            continue
        if not path.is_file():
            raise ValueError(f"registered_document_file_missing:{filename}")
        parts = _registered_document_parts(path, raw_record)
        assert parts is not None
        source_url = urls.get(filename) or raw_record.get("source_url")
        if not str(source_url or "").strip():
            raise ValueError(f"registered_document_source_url_missing:{filename}")
        derivative = parts.get("derived_text_path")
        if derivative is not None and not (output / str(derivative)).is_file():
            raise ValueError(f"registered_document_derived_text_missing:{filename}:{derivative}")
        digest = _sha256_bytes(path)
        doc_id = (
            f"DOC:{market}:{canonical_code}:{parts['doc_type']}:"
            f"{parts['period_end']}:{digest[:12]}"
        )
        document = {
            "doc_id": doc_id,
            "report_id": report_id,
            "issuer": issuer,
            "code": canonical_code,
            "market": market,
            "doc_type": parts["doc_type"],
            "fiscal_period": parts["fiscal_period"],
            "period_end": parts["period_end"],
            "published_at": parts["published_at"],
            "authority": parts["authority"],
            "source_url": source_url,
            "local_path": filename,
            "derived_text_path": derivative,
            "sha256": digest,
            "mime_type": parts["mime_type"],
            "language": parts["language"],
            "acquisition_status": "DOWNLOADED",
        }
        _copy_optional_source_fields(document, raw_record)
        documents.append(document)
    documents.sort(key=lambda item: (item["period_end"], item["doc_type"], item["doc_id"]))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "issuer": issuer,
        "code": canonical_code,
        "market": market,
        "generated_at": _now(),
        "documents": documents,
    }
    payload["manifest_hash"] = _payload_hash(_manifest_core(payload))
    payload["validation"] = validate_document_manifest(payload, output)
    if persist:
        _atomic_write_json(output / "document_manifest.json", payload)
    return payload


def initialize_official_evidence_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        "created_at": _now(),
    }
    _atomic_write_json(Path(output_dir) / "official_evidence_policy.json", payload)
    return payload


def _parse_source_urls(items: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        filename, separator, url = str(item).partition("=")
        if not separator or not filename.strip() or not url.strip():
            raise ValueError("--source-url 必须使用 filename=url")
        result[filename.strip()] = url.strip()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="建立官方文件身份与哈希manifest")
    parser.add_argument("--code", required=True)
    parser.add_argument("--output-dir", "--output", required=True)
    parser.add_argument("--source-url", action="append", default=[], help="filename=url，可重复")
    args = parser.parse_args()
    payload = build_document_manifest(
        args.output_dir, args.code, source_urls=_parse_source_urls(args.source_url), persist=True
    )
    print(json.dumps({
        "path": str(Path(args.output_dir) / "document_manifest.json"),
        "state": payload["validation"]["state"],
        "documents": len(payload["documents"]),
        "manifest_hash": payload["manifest_hash"],
    }, ensure_ascii=False))
    return 0 if payload["validation"]["state"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
