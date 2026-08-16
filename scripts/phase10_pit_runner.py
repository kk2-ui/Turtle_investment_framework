#!/usr/bin/env python3
"""Read-only point-in-time source-package runner for Phase 10.

The acquisition module decides *which* disclosures are admissible.  This
module is the smaller execution boundary that decides *what a writer may
read*: only an admitted ``source_id`` whose registered package path is under
the package root, plus explicitly registered framework files.  It does not
fetch URLs and it does not expose arbitrary filesystem reads.

The attestation emitted here is a declared-process/read-audit artifact.  It
is intentionally not a deployment signature or a model-memory guarantee.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.phase10_acquisition import validate_source_manifest


PIT_ATTESTATION_SCHEMA_VERSION = "phase10-pit-runner-attestation.v1"
PIT_RUNNER_VERSION = "phase10-pit-runner.v1"
ADMITTED = "ADMITTED"
PIT_STATIC_FRAMEWORK_ROOT = Path(__file__).resolve().parents[1] / "config" / "phase10_pit_framework"


class PITRunnerError(RuntimeError):
    """Raised when a requested read is outside the registered PIT boundary."""


def _timestamp(value: Any) -> datetime | None:
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
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _relative_path(value: Any) -> str | None:
    """Normalize a registered path without accepting absolute paths."""
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.startswith("/"):
        return None
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix()


def _path_field(source: dict[str, Any]) -> str | None:
    # ``package_path`` is canonical.  The aliases make it possible to adopt
    # acquisition exports that already use ``path`` or ``artifact_path``.
    for field in ("package_path", "path", "local_path", "artifact_path"):
        value = _relative_path(source.get(field))
        if value:
            return value
    return None


def _manifest_sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    selected = manifest.get("sources")
    if isinstance(selected, list):
        return [item for item in selected if isinstance(item, dict)]
    inventory = manifest.get("inventory")
    if isinstance(inventory, list):
        return [item for item in inventory if isinstance(item, dict) and item.get("admissible") is True]
    return []


def _framework_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = manifest.get("framework_allowlist")
    if entries is None and isinstance(manifest.get("source_package"), dict):
        entries = manifest["source_package"].get("framework_allowlist")
    if not isinstance(entries, list):
        return []
    result: list[dict[str, Any]] = []
    for item in entries:
        if isinstance(item, str):
            path = _relative_path(item)
            if path:
                result.append({"path": path})
        elif isinstance(item, dict):
            path = _relative_path(item.get("path") or item.get("package_path"))
            if path:
                result.append({**item, "path": path})
    return result


@dataclass(frozen=True)
class SourceRegistration:
    source_id: str
    source_version: str
    published_at: str
    data_as_of: str
    package_path: str


class PITReadAudit:
    """Deterministic read audit; no content or secret values are recorded."""

    def __init__(self, *, cutoff_at: str, run_id: str | None = None) -> None:
        self.cutoff_at = cutoff_at
        self.run_id = run_id
        self._events: list[dict[str, Any]] = []

    def record(
        self,
        *,
        allowed: bool,
        kind: str,
        path: str,
        source_id: str | None = None,
        source_version: str | None = None,
        published_at: str | None = None,
        data_as_of: str | None = None,
        reason: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "read_ordinal": len(self._events) + 1,
            "allowed": bool(allowed),
            "decision": "ALLOW" if allowed else "DENY",
            "kind": kind,
            "path": path,
            "cutoff_at": self.cutoff_at,
            "phase": "FREEZE",
            "admission_status": ADMITTED if allowed else "REJECTED",
        }
        if source_id is not None:
            event["source_id"] = source_id
        if self.run_id:
            event["run_id"] = self.run_id
        if source_version is not None:
            event["source_version"] = source_version
        if published_at is not None:
            event["published_at"] = published_at
        if data_as_of is not None:
            event["data_as_of"] = data_as_of
        if reason:
            event["reason"] = reason
        self._events.append(event)

    @property
    def events(self) -> list[dict[str, Any]]:
        return deepcopy(self._events)


class PITSourcePackage:
    """Validated, read-only view over one registered historical source package."""

    def __init__(
        self,
        manifest: dict[str, Any],
        package_root: str | Path,
        *,
        framework_root: str | Path | None = None,
        require_complete_manifest: bool = True,
        case_id: str | None = None,
        experiment_id: str | None = None,
        run_id: str | None = None,
        manifest_path: str | None = None,
    ) -> None:
        self.manifest = deepcopy(manifest)
        self.case_id = case_id
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.manifest_path = manifest_path
        self.package_root = Path(package_root).expanduser().resolve()
        static_framework_root = PIT_STATIC_FRAMEWORK_ROOT.resolve()
        if framework_root and Path(framework_root).expanduser().resolve() != static_framework_root:
            raise ValueError("PIT framework root 必须使用仓库内受控静态目录")
        self._framework_root = static_framework_root
        self.framework_root_class = "REPOSITORY_STATIC"
        self.validation = validate_source_manifest(self.manifest)
        self.cutoff_at = str(self.manifest.get("cutoff_at") or "")
        cutoff = _timestamp(self.cutoff_at)
        self._invalid: list[str] = list(self.validation.get("invalid_findings", []))
        self._incomplete: list[str] = list(self.validation.get("incomplete_findings", []))
        if not self.package_root.is_dir():
            self._incomplete.append("package_root_missing")
        if not self._framework_root.is_dir():
            self._incomplete.append("framework_root_missing")
        if cutoff is None:
            self._invalid.append("cutoff_at_invalid")
        if require_complete_manifest and self.validation.get("state") != "REVIEWABLE":
            # A package cannot silently upgrade an acquisition manifest that
            # still has an incomplete announcement inventory.
            self._incomplete.append("source_manifest_not_reviewable")
        self._registrations: dict[str, SourceRegistration] = {}
        registered_paths: dict[str, str] = {}
        for source in _manifest_sources(self.manifest):
            source_id = str(source.get("source_id") or "").strip()
            if source.get("admissible") is not True or not source_id:
                continue
            path = _path_field(source)
            if not path:
                supplied_path = any(source.get(field) not in (None, "") for field in ("package_path", "path", "local_path", "artifact_path"))
                finding = "package_path_invalid" if supplied_path else "package_path_missing"
                target = self._invalid if supplied_path else self._incomplete
                target.append(f"source:{source_id}:{finding}")
                continue
            if source_id in self._registrations:
                self._invalid.append(f"source:{source_id}:duplicate_registration")
                continue
            self._registrations[source_id] = SourceRegistration(
                source_id=source_id,
                source_version=str(source.get("source_version") or ""),
                published_at=str(source.get("published_at") or ""),
                data_as_of=str(source.get("data_as_of") or ""),
                package_path=path,
            )
            previous_source = registered_paths.get(path)
            if previous_source is not None and previous_source != source_id:
                self._invalid.append(f"source:{source_id}:package_path_reused:{path}")
            registered_paths[path] = source_id
            try:
                package_file = self._resolve_under(self.package_root, path, reason_prefix=f"source:{source_id}")
            except PITRunnerError as exc:
                self._invalid.append(str(exc))
            else:
                if not package_file.is_file():
                    self._incomplete.append(f"source:{source_id}:package_file_missing")
        self._framework: dict[str, dict[str, Any]] = {
            str(item["path"]): item for item in _framework_entries(self.manifest)
        }
        self.audit = PITReadAudit(cutoff_at=self.cutoff_at, run_id=self.run_id)

    @property
    def state(self) -> str:
        if self._invalid:
            return "INVALID"
        if self._incomplete:
            return "INCOMPLETE"
        return "REVIEWABLE"

    @property
    def invalid_findings(self) -> list[str]:
        return list(self._invalid)

    @property
    def incomplete_findings(self) -> list[str]:
        return list(self._incomplete)

    @property
    def admitted_source_ids(self) -> list[str]:
        return list(self._registrations)

    @property
    def framework_root(self) -> Path:
        """Expose the static framework location without a mutable setter."""
        return self._framework_root

    def _resolve_under(self, root: Path, relative: str, *, reason_prefix: str) -> Path:
        normalized = _relative_path(relative)
        if not normalized:
            raise PITRunnerError(f"{reason_prefix}:path_not_relative")
        resolved = (root / normalized).resolve()
        if resolved != root and root not in resolved.parents:
            raise PITRunnerError(f"{reason_prefix}:path_outside_root")
        return resolved

    def _deny(self, *, kind: str, path: str, reason: str, source: SourceRegistration | None = None) -> None:
        self.audit.record(
            allowed=False,
            kind=kind,
            path=path,
            source_id=source.source_id if source else None,
            source_version=source.source_version if source else None,
            published_at=source.published_at if source else None,
            data_as_of=source.data_as_of if source else None,
            reason=reason,
        )
        raise PITRunnerError(reason)

    def read_source(self, source_id: str) -> bytes:
        """Read one admitted source; all other IDs are denied and audited."""
        if self.state != "REVIEWABLE":
            self._deny(kind="SOURCE", path="", reason=f"runner_not_reviewable:{self.state}")
        key = str(source_id or "").strip()
        source = self._registrations.get(key)
        if source is None:
            self._deny(kind="SOURCE", path="", reason=f"source_not_allowlisted:{key}")
        assert source is not None
        cutoff = _timestamp(self.cutoff_at)
        published = _timestamp(source.published_at)
        if cutoff is None or published is None or published > cutoff:
            self._deny(kind="SOURCE", path=source.package_path, reason=f"source_after_cutoff:{key}", source=source)
        try:
            path = self._resolve_under(self.package_root, source.package_path, reason_prefix=f"source:{key}")
        except PITRunnerError as exc:
            self._deny(kind="SOURCE", path=source.package_path, reason=str(exc), source=source)
        assert path is not None
        if not path.is_file():
            self._deny(kind="SOURCE", path=source.package_path, reason=f"source_file_missing:{key}", source=source)
        try:
            content = path.read_bytes()
        except OSError as exc:
            self._deny(kind="SOURCE", path=source.package_path, reason=f"source_read_failed:{key}:{exc.__class__.__name__}", source=source)
        self.audit.record(
            allowed=True,
            kind="SOURCE",
            path=source.package_path,
            source_id=source.source_id,
            source_version=source.source_version,
            published_at=source.published_at,
            data_as_of=source.data_as_of,
        )
        return content

    def read_framework(self, relative_path: str) -> bytes:
        """Read a framework artifact explicitly registered by relative path."""
        if self.state != "REVIEWABLE":
            self._deny(kind="FRAMEWORK", path=str(relative_path), reason=f"runner_not_reviewable:{self.state}")
        normalized = _relative_path(relative_path)
        if normalized is None or normalized not in self._framework:
            self._deny(kind="FRAMEWORK", path=str(relative_path), reason=f"framework_not_allowlisted:{relative_path}")
        assert normalized is not None
        try:
            path = self._resolve_under(self._framework_root, normalized, reason_prefix="framework")
        except PITRunnerError as exc:
            self._deny(kind="FRAMEWORK", path=normalized, reason=str(exc))
        assert path is not None
        if not path.is_file():
            self._deny(kind="FRAMEWORK", path=normalized, reason="framework_file_missing")
        try:
            content = path.read_bytes()
        except OSError as exc:
            self._deny(kind="FRAMEWORK", path=normalized, reason=f"framework_read_failed:{exc.__class__.__name__}")
        self.audit.record(allowed=True, kind="FRAMEWORK", path=normalized)
        return content

    def attestation(self) -> dict[str, Any]:
        """Return a serializable read-boundary attestation."""
        return {
            "schema_version": PIT_ATTESTATION_SCHEMA_VERSION,
            "runner": "phase10_pit_runner",
            "runner_version": PIT_RUNNER_VERSION,
            "assurance_level": "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS",
            "case_id": self.case_id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "manifest_path": self.manifest_path,
            "source_manifest_schema_version": self.manifest.get("schema_version"),
            "company_code": self.manifest.get("company_code"),
            "cutoff_at": self.cutoff_at,
            "package_root": str(self.package_root),
            "framework_root": str(self.framework_root),
            "framework_root_class": self.framework_root_class,
            "allowed_source_ids": self.admitted_source_ids,
            "source_allowlist": [
                {
                    "source_id": registration.source_id,
                    "source_version": registration.source_version,
                    "published_at": registration.published_at,
                    "data_as_of": registration.data_as_of,
                    "package_path": registration.package_path,
                    "admission_status": ADMITTED,
                }
                for registration in self._registrations.values()
            ],
            "framework_allowlist": sorted(self._framework),
            "state": self.state,
            "invalid_findings": self.invalid_findings,
            "incomplete_findings": self.incomplete_findings,
            "read_audit": self.audit.events,
            "read_count": len(self.audit.events),
            "forbidden_success_count": sum(
                1 for event in self.audit.events
                if event.get("allowed") is True and event.get("kind") not in {"SOURCE", "FRAMEWORK"}
            ),
            "future_read_rejections": sum(
                1 for event in self.audit.events if not event["allowed"] and "cutoff" in str(event.get("reason", ""))
            ),
            "forbidden_read_rejections": sum(1 for event in self.audit.events if not event["allowed"]),
        }


# Names used by callers that prefer function-style construction.
SourcePackageRunner = PITSourcePackage


def validate_source_package(
    manifest: dict[str, Any],
    package_root: str | Path,
    *,
    framework_root: str | Path | None = None,
    require_complete_manifest: bool = True,
    case_id: str | None = None,
    experiment_id: str | None = None,
    run_id: str | None = None,
    manifest_path: str | None = None,
) -> dict[str, Any]:
    runner = PITSourcePackage(
        manifest,
        package_root,
        framework_root=framework_root,
        require_complete_manifest=require_complete_manifest,
        case_id=case_id,
        experiment_id=experiment_id,
        run_id=run_id,
        manifest_path=manifest_path,
    )
    return runner.attestation()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--framework-root", type=Path)
    parser.add_argument("--attestation", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--experiment-id")
    parser.add_argument("--run-id")
    args = parser.parse_args(list(argv) if argv is not None else None)
    static_framework_root = PIT_STATIC_FRAMEWORK_ROOT.resolve()
    if args.framework_root and args.framework_root.expanduser().resolve() != static_framework_root:
        parser.error("--framework-root 只能使用仓库内受控的 P10 PIT framework 目录")
    runner = PITSourcePackage(
        _load_json(args.manifest),
        args.package_root,
        case_id=args.case_id,
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        manifest_path=str(args.manifest.resolve()),
    )
    payload = runner.attestation()
    if args.attestation:
        args.attestation.parent.mkdir(parents=True, exist_ok=True)
        args.attestation.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if runner.state == "REVIEWABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
