from __future__ import annotations

import json

import pytest

from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_pit_runner import PITRunnerError, PITSourcePackage


def _manifest(*, package_path: str = "annual/2019.txt") -> dict:
    manifest = enumerate_sse_announcements([
        {
            "source_id": "SSE:600340:AR2019:ORIGINAL",
            "source_version": "annual-report-2019-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2019 年年度报告",
            "published_at": "2020-04-25",
            "data_as_of": "2019-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
        {
            "source_id": "SSE:600340:ANN:FUTURE",
            "source_version": "future-v1",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "后续公告",
            "published_at": "2020-04-28",
            "data_as_of": "2020-04-28",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
    ], cutoff_at="2020-04-27T18:00:00+08:00", period_start="2019-01-01")
    for source in manifest["inventory"]:
        if source["source_id"] == "SSE:600340:AR2019:ORIGINAL":
            source["package_path"] = package_path
    for source in manifest["sources"]:
        source["package_path"] = package_path
    manifest["framework_allowlist"] = [{"path": "framework/policy.md", "role": "framework"}]
    return manifest


def test_runner_reads_only_admitted_source_and_framework_and_audits_identity(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual/2019.txt").write_text("historical report", encoding="utf-8")

    runner = PITSourcePackage(
        _manifest(), package,
        case_id="HBTCASE:600340",
        experiment_id="HBT:600340",
        run_id="pit-run:600340",
        manifest_path="config/source-package.json",
    )
    assert runner.state == "REVIEWABLE"
    assert runner.read_source("SSE:600340:AR2019:ORIGINAL") == b"historical report"
    assert runner.read_framework("framework/policy.md").startswith(b"# Phase 10 PIT Writer Policy")

    audit = runner.attestation()
    assert audit["schema_version"] == "phase10-pit-runner-attestation.v1"
    assert audit["assurance_level"] == "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS"
    assert audit["source_allowlist"][0]["source_version"] == "annual-report-2019-original"
    assert [event["kind"] for event in audit["read_audit"]] == ["SOURCE", "FRAMEWORK"]
    assert all(event["allowed"] for event in audit["read_audit"])
    assert all(event["phase"] == "FREEZE" and event["run_id"] == "pit-run:600340" for event in audit["read_audit"])
    assert audit["forbidden_success_count"] == 0


def test_runner_rejects_future_and_unregistered_reads_without_exposing_files(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "annual").mkdir()
    (package / "annual/2019.txt").write_text("historical report", encoding="utf-8")
    future = package / "future-settlement.json"
    future.write_text(json.dumps({"future_return": 3}), encoding="utf-8")
    runner = PITSourcePackage(_manifest(), package)

    with pytest.raises(PITRunnerError, match="source_not_allowlisted"):
        runner.read_source("SSE:600340:ANN:FUTURE")
    with pytest.raises(PITRunnerError, match="source_not_allowlisted"):
        runner.read_source("future-settlement")

    denied = [event for event in runner.attestation()["read_audit"] if not event["allowed"]]
    assert len(denied) == 2
    assert denied[0]["admission_status"] == "REJECTED"
    assert future.read_text(encoding="utf-8").startswith("{")


def test_runner_marks_missing_package_path_incomplete_and_current_restated_invalid(tmp_path) -> None:
    manifest = _manifest()
    for source in manifest["inventory"]:
        source.pop("package_path", None)
    for source in manifest["sources"]:
        source.pop("package_path", None)
    runner = PITSourcePackage(manifest, tmp_path)
    assert runner.state == "INCOMPLETE"
    assert "source:SSE:600340:AR2019:ORIGINAL:package_path_missing" in runner.incomplete_findings

    invalid_manifest = _manifest()
    for source in invalid_manifest["inventory"]:
        if source["source_id"] == "SSE:600340:AR2019:ORIGINAL":
            source["revision_policy"] = "CURRENT_RESTATED_ONLY"
    for source in invalid_manifest["sources"]:
        if source["source_id"] == "SSE:600340:AR2019:ORIGINAL":
            source["revision_policy"] = "CURRENT_RESTATED_ONLY"
    invalid_runner = PITSourcePackage(invalid_manifest, tmp_path)
    assert invalid_runner.state == "INVALID"
    assert any("admission_decision_mismatch" in finding for finding in invalid_runner.invalid_findings)


def test_runner_rejects_path_traversal_in_registered_source(tmp_path) -> None:
    manifest = _manifest(package_path="../future/settlement.json")
    runner = PITSourcePackage(manifest, tmp_path)
    assert runner.state == "INVALID"
    assert "source:SSE:600340:AR2019:ORIGINAL:package_path_invalid" in runner.invalid_findings


def test_runner_rejects_untrusted_framework_root(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual/2019.txt").write_text("historical report", encoding="utf-8")
    untrusted_framework = tmp_path / "ordinary-output"
    untrusted_framework.mkdir()
    (untrusted_framework / "future-settlement.md").write_text("future outcome", encoding="utf-8")

    with pytest.raises(ValueError, match="framework root 必须使用仓库内受控静态目录"):
        PITSourcePackage(_manifest(), package, framework_root=untrusted_framework)


def test_runner_requires_registered_page_text_for_pdf_and_audits_representation(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual/2019.pdf").write_bytes(b"%PDF-not-read-directly")
    manifest = _manifest(package_path="annual/2019.pdf")
    missing_reader = PITSourcePackage(manifest, package)
    assert missing_reader.state == "INCOMPLETE"
    assert "source:SSE:600340:AR2019:ORIGINAL:reader_text_path_missing" in missing_reader.incomplete_findings

    for source in [*manifest["inventory"], *manifest["sources"]]:
        if source["source_id"] == "SSE:600340:AR2019:ORIGINAL":
            source.update({
                "content_representation": "PDF_PAGE_MARKDOWN",
                "reader_text_path": "annual/2019.pages.md",
                "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
                "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
                "reader_text_page_count": 1,
            })
    (package / "annual/2019.pages.md").write_text(
        "# SSE:600340:AR2019:ORIGINAL\n\n## 第 1 页\n\n历史年报正文\n",
        encoding="utf-8",
    )
    runner = PITSourcePackage(manifest, package)
    assert runner.state == "REVIEWABLE"
    assert "## 第 1 页" in runner.read_source("SSE:600340:AR2019:ORIGINAL").decode("utf-8")
    allowed = runner.attestation()["read_audit"][-1]
    assert allowed["path"] == "annual/2019.pages.md"
    assert allowed["representation"] == "PDF_PAGE_MARKDOWN"
