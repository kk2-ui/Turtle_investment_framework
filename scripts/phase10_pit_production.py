#!/usr/bin/env python3
"""Source-bound workspace for a production point-in-time report.

The normal report validators expect report-local document paths.  A PIT source
package is intentionally outside that output directory and is readable only
through :class:`PITSourcePackage`.  This adapter creates a small, link-only
projection *after* a source has been read through that boundary.  It neither
copies the historical package nor makes an unread source available to a writer.
"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.evidence_documents import (
    _atomic_write_json,
    _manifest_core,
    _payload_hash,
    _sha256_bytes,
    validate_document_manifest,
)
from scripts.phase10_pit_runner import PITSourcePackage


PIT_SOURCE_PROVENANCE_PROJECTION_SCHEMA_VERSION = "phase10-pit-source-provenance-projection.v1"


class PITProductionWorkspaceError(RuntimeError):
    """Raised when a report workspace would exceed the PIT read boundary."""


@dataclass(frozen=True)
class PITProjectedSource:
    """One report-local view of an already-read PIT source."""

    source_id: str
    source_version: str
    published_at: str
    data_as_of: str
    revision_policy: str
    source_type: str
    title: str
    package_path: str
    reader_text_path: str
    local_path: str
    derived_text_path: str
    source_role_provenance: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source_id": self.source_id,
            "source_version": self.source_version,
            "published_at": self.published_at,
            "data_as_of": self.data_as_of,
            "revision_policy": self.revision_policy,
            "source_type": self.source_type,
            "title": self.title,
            "package_path": self.package_path,
            "reader_text_path": self.reader_text_path,
            "local_path": self.local_path,
            "derived_text_path": self.derived_text_path,
        }
        if self.source_role_provenance is not None:
            result["source_role_provenance"] = deepcopy(self.source_role_provenance)
        return result


class PITProductionWorkspace:
    """Link-only output projection bounded by one runner's ALLOW audit."""

    def __init__(
        self,
        runner: PITSourcePackage,
        output_dir: str | Path,
        *,
        company_code: str,
        run_id: str,
    ) -> None:
        self.runner = runner
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.company_code = str(company_code or "").strip()
        self.run_id = str(run_id or "").strip()
        if not self.company_code or not self.run_id:
            raise PITProductionWorkspaceError("PIT production workspace requires company_code and run_id")
        self._projected: dict[str, PITProjectedSource] = {}

    def _registration(self, source_id: str) -> dict[str, Any]:
        for item in self.runner.attestation().get("source_allowlist", []):
            if isinstance(item, dict) and item.get("source_id") == source_id:
                return item
        raise PITProductionWorkspaceError("PIT source is not allowlisted: " + source_id)

    def _manifest_source(self, source_id: str) -> dict[str, Any]:
        for item in self.runner.manifest.get("sources") or []:
            if isinstance(item, dict) and item.get("source_id") == source_id:
                return item
        return {}

    def _allowed_reads(self) -> set[str]:
        return {
            str(event.get("source_id") or "")
            for event in self.runner.attestation().get("read_audit", [])
            if event.get("allowed") is True and event.get("kind") == "SOURCE"
        }

    def _source_file(self, relative_path: str, *, source_id: str) -> Path:
        target = (self.runner.package_root / relative_path).resolve()
        if target != self.runner.package_root and self.runner.package_root not in target.parents:
            raise PITProductionWorkspaceError("PIT source path is outside package: " + source_id)
        if not target.is_file():
            raise PITProductionWorkspaceError("PIT source file missing: " + source_id)
        return target

    @staticmethod
    def _slug(source_id: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", source_id).strip("._")
        return slug or "source"

    @staticmethod
    def _link(path: Path, target: Path) -> None:
        if path.exists() or path.is_symlink():
            if path.is_symlink() and path.resolve() == target:
                return
            raise PITProductionWorkspaceError("PIT projection path already exists: " + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(target, path.parent)
        path.symlink_to(relative_target)

    def project_read_source(self, source_id: str) -> dict[str, Any]:
        """Project an admitted source only after the runner logged an ALLOW read."""
        source_id = str(source_id or "").strip()
        if not source_id:
            raise PITProductionWorkspaceError("PIT source_id is required")
        if source_id in self._projected:
            return self._projected[source_id].to_dict()
        if source_id not in self._allowed_reads():
            raise PITProductionWorkspaceError("PIT source must be read before projection: " + source_id)

        registration = self._registration(source_id)
        source = self._manifest_source(source_id)
        package_path = str(registration.get("package_path") or "")
        reader_text_path = str(registration.get("reader_text_path") or "")
        # A versioned industry export is directly readable data.  Other
        # source types must supply a registered reader representation; that
        # includes first-party web releases, whose page-marked reader copy is
        # created by the acquisition module rather than from a live browser.
        if (
            not reader_text_path
            and str(source.get("source_type") or "").upper() == "LICENSED_INDUSTRY_DATA"
        ):
            reader_text_path = package_path
        if not package_path or not reader_text_path:
            raise PITProductionWorkspaceError("PIT source lacks original or reader path: " + source_id)
        original = self._source_file(package_path, source_id=source_id)
        reader = self._source_file(reader_text_path, source_id=source_id)
        folder = Path("pit_sources") / self._slug(source_id)
        local_path = folder / ("original" + original.suffix.lower())
        derived_text_path = folder / ("pages" + reader.suffix.lower())
        self._link(self.output_dir / local_path, original)
        self._link(self.output_dir / derived_text_path, reader)
        projected = PITProjectedSource(
            source_id=source_id,
            source_version=str(registration.get("source_version") or ""),
            published_at=str(registration.get("published_at") or ""),
            data_as_of=str(registration.get("data_as_of") or ""),
            revision_policy=str(source.get("revision_policy") or ""),
            source_type=str(source.get("source_type") or ""),
            title=str(source.get("title") or ""),
            package_path=package_path,
            reader_text_path=reader_text_path,
            local_path=local_path.as_posix(),
            derived_text_path=derived_text_path.as_posix(),
            source_role_provenance=(
                deepcopy(source["source_role_provenance"])
                if isinstance(source.get("source_role_provenance"), dict) else None
            ),
        )
        self._projected[source_id] = projected
        return projected.to_dict()

    def document_sources(self) -> list[dict[str, Any]]:
        """Return the already-projected source map in stable source-id order."""
        return [self._projected[key].to_dict() for key in sorted(self._projected)]

    def write_document_manifest(self) -> dict[str, Any]:
        """Create the existing V3 document contract from projected PIT sources.

        The document validator already requires a content identity for formal
        report acceptance.  This method deliberately invokes that existing
        contract only for sources the runner has recorded as read; it never
        walks the source package or adds a second provenance scheme.
        """
        if not self._projected:
            raise PITProductionWorkspaceError("PIT document manifest requires at least one projected source")
        code, market = self._security_identity()
        documents: list[dict[str, Any]] = []
        source_provenance: list[dict[str, Any]] = []
        for projected in self.document_sources():
            doc_type, authority = self._document_class(projected["source_type"])
            original = self.output_dir / projected["local_path"]
            if not original.is_file():
                raise PITProductionWorkspaceError("PIT projected original is missing: " + projected["source_id"])
            digest = _sha256_bytes(original)
            period_end = projected["data_as_of"]
            document = {
                "doc_id": f"DOC:{market}:{code}:{doc_type}:{period_end}:{digest[:12]}",
                "report_id": "",
                "issuer": code,
                "code": code,
                "market": market,
                "doc_type": doc_type,
                "fiscal_period": self._fiscal_period(period_end, doc_type),
                "period_end": period_end,
                "published_at": projected["published_at"],
                "authority": authority,
                "source_url": self._source_url(projected["source_id"]),
                "local_path": projected["local_path"],
                "derived_text_path": projected["derived_text_path"],
                "sha256": digest,
                "mime_type": (
                    "application/pdf" if original.suffix.lower() == ".pdf"
                    else "text/csv" if original.suffix.lower() == ".csv"
                    else "text/html" if original.suffix.lower() in {".html", ".htm"}
                    else "text/markdown"
                ),
                "language": str(self._manifest_source(projected["source_id"]).get("language") or "zh"),
                "acquisition_status": "PIT_LINKED_AFTER_ALLOW_READ",
                "source_id": projected["source_id"],
                "source_version": projected["source_version"],
                "revision_policy": projected["revision_policy"],
            }
            role_provenance = projected.get("source_role_provenance")
            if isinstance(role_provenance, dict):
                # This is a structural copy of acquisition metadata.  Neither
                # the document title, URL nor legal-name display text is used
                # to infer a publisher role later.
                document["source_role_provenance"] = deepcopy(role_provenance)
            documents.append(document)
            source_provenance.append({
                "source_id": projected["source_id"],
                "source_version": projected["source_version"],
                "revision_policy": projected["revision_policy"],
                "source_type": projected["source_type"],
                "admission_status": "ADMITTED",
                "source_role_provenance": deepcopy(role_provenance) if isinstance(role_provenance, dict) else None,
            })
        documents.sort(key=lambda item: (str(item["period_end"]), str(item["doc_id"])))
        report_id = f"REPORT:{market}:{code}:{documents[-1]['period_end']}"
        for document in documents:
            document["report_id"] = report_id
        payload: dict[str, Any] = {
            "schema_version": "document-manifest.v1",
            "report_id": report_id,
            "issuer": code,
            "code": code,
            "market": market,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "documents": documents,
        }
        payload["manifest_hash"] = _payload_hash(_manifest_core(payload))
        payload["validation"] = validate_document_manifest(payload, self.output_dir)
        _atomic_write_json(self.output_dir / "document_manifest.json", payload)
        # The P29 gate cannot safely reconstruct a publisher role from a DOC
        # alone.  Keep a narrow, read-only projection of the actual admitted
        # source identities beside the documents so it can reject a hand-edited
        # DOC role contract.  It contains no source content and only sources
        # already ALLOW-read by this runner.
        _atomic_write_json(self.output_dir / "pit_source_provenance.json", {
            "schema_version": PIT_SOURCE_PROVENANCE_PROJECTION_SCHEMA_VERSION,
            "run_id": self.run_id,
            "company_code": self.company_code,
            "sources": sorted(source_provenance, key=lambda item: str(item["source_id"])),
        })
        return payload

    def _security_identity(self) -> tuple[str, str]:
        raw = self.company_code.upper()
        code, _, suffix = raw.partition(".")
        market = {"SH": "CN-SH", "SZ": "CN-SZ", "BJ": "CN-BJ", "HK": "HK"}.get(suffix, "UNKNOWN")
        return code, market

    @staticmethod
    def _document_class(source_type: str) -> tuple[str, str]:
        classes = {
            "ANNUAL_REPORT": ("annual_report", "audited_filing"),
            "INTERIM_REPORT": ("interim_report", "company_filing"),
            "QUARTERLY_REPORT": ("quarterly_report", "company_filing"),
            "LICENSED_INDUSTRY_DATA": ("licensed_industry_data", "industry_data"),
            "OTHER_OFFICIAL": ("other_official", "other_official"),
        }
        return classes.get(str(source_type or "").upper(), ("exchange_announcement", "company_filing"))

    @staticmethod
    def _fiscal_period(period_end: str, doc_type: str) -> str:
        if doc_type == "annual_report" and re.fullmatch(r"20\d{2}-12-31", period_end):
            return "FY" + period_end[:4]
        if doc_type == "interim_report" and re.fullmatch(r"20\d{2}-06-30", period_end):
            return "H1-" + period_end[:4]
        return period_end

    def _source_url(self, source_id: str) -> str | None:
        source = self._manifest_source(source_id)
        for field in ("source_url", "url", "pdf_url"):
            value = str(source.get(field) or "").strip()
            if value:
                return value
        return None
