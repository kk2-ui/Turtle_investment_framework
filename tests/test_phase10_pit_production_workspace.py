from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_report_context import build_verified_context
from scripts.evidence_facts import build_fact_observations, verify_fact_from_quote
from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_pit_production import PITProductionWorkspace
from scripts.phase10_pit_runner import PITRunnerError, PITSourcePackage
from turtle_agent.tools.pit_read_tools import clear_pit_runner, configure_pit_runner, pit_read_source


SOURCE_ID = "SSE:600340:AR2019:ORIGINAL"
FUTURE_SOURCE_ID = "SSE:600340:ANN:FUTURE"


def _manifest() -> dict:
    manifest = enumerate_sse_announcements(
        [
            {
                "source_id": SOURCE_ID,
                "source_version": "annual-report-2019-original",
                "source_type": "ANNUAL_REPORT",
                "title": "2019 annual report",
                "published_at": "2020-04-25T18:00:00+08:00",
                "data_as_of": "2019-12-31",
                "revision_policy": "ORIGINAL_VINTAGE",
            },
            {
                "source_id": FUTURE_SOURCE_ID,
                "source_version": "future-v1",
                "source_type": "EXCHANGE_ANNOUNCEMENT",
                "title": "future announcement",
                "published_at": "2020-04-28T18:00:00+08:00",
                "data_as_of": "2020-04-28",
                "revision_policy": "ORIGINAL_VINTAGE",
            },
        ],
        cutoff_at="2020-04-27T18:00:00+08:00",
        period_start="2019-01-01",
    )
    for source in [*manifest["inventory"], *manifest["sources"]]:
        if source["source_id"] == SOURCE_ID:
            source.update(
                {
                    "package_path": "annual/2019.pdf",
                    "content_representation": "PDF_PAGE_MARKDOWN",
                    "reader_text_path": "annual/2019.pages.md",
                    "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
                    "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
                    "reader_text_page_count": 1,
                }
            )
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    return manifest


@pytest.fixture()
def runner(tmp_path: Path) -> PITSourcePackage:
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual" / "2019.pdf").write_bytes(b"%PDF-original")
    (package / "annual" / "2019.pages.md").write_text(
        "# SSE:600340:AR2019:ORIGINAL\n\n"
        "- source_id: SSE:600340:AR2019:ORIGINAL\n"
        "- source_version: annual-report-2019-original\n"
        "- content_representation: PDF_PAGE_MARKDOWN\n\n"
        "## \u7b2c 1 \u9875\n\nhistorical annual report revenue 100\n",
        encoding="utf-8",
    )
    source_runner = PITSourcePackage(
        _manifest(),
        package,
        case_id="HBTCASE:600340:20200427",
        experiment_id="HBT:600340:20200427",
        run_id="pit-production-workspace-test",
    )
    assert source_runner.state == "REVIEWABLE"
    return source_runner


def _projected_path(output: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else output / path


def test_workspace_requires_runner_allow_read_before_projecting_source(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner,
        output,
        company_code="600340.SH",
        run_id="pit-production-workspace-test",
    )

    with pytest.raises(RuntimeError, match="source.*read.*before projection"):
        workspace.project_read_source(SOURCE_ID)

    assert workspace.document_sources() == []
    assert not (output / "pit_sources").exists()


def test_workspace_projects_only_read_source_as_links_with_registered_identity(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner,
        output,
        company_code="600340.SH",
        run_id="pit-production-workspace-test",
    )
    runner.read_source(SOURCE_ID)

    projected = workspace.project_read_source(SOURCE_ID)

    assert projected["source_id"] == SOURCE_ID
    assert projected["source_version"] == "annual-report-2019-original"
    assert projected["published_at"] == "2020-04-25T18:00:00+08:00"
    assert projected["data_as_of"] == "2019-12-31"
    assert projected["revision_policy"] == "ORIGINAL_VINTAGE"
    assert projected["source_type"] == "ANNUAL_REPORT"
    assert projected["package_path"] == "annual/2019.pdf"
    assert projected["reader_text_path"] == "annual/2019.pages.md"
    local_path = _projected_path(output, projected["local_path"])
    derived_text_path = _projected_path(output, projected["derived_text_path"])
    assert local_path.is_relative_to(output / "pit_sources")
    assert derived_text_path.is_relative_to(output / "pit_sources")
    assert local_path.suffix == ".pdf"
    assert derived_text_path.suffix == ".md"
    assert local_path.is_symlink()
    assert derived_text_path.is_symlink()
    assert local_path.resolve() == runner.package_root / "annual" / "2019.pdf"
    assert derived_text_path.resolve() == runner.package_root / "annual" / "2019.pages.md"
    assert workspace.document_sources() == [projected]


def test_workspace_writes_existing_v3_document_manifest_only_for_projected_source(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner,
        output,
        company_code="600340.SH",
        run_id="pit-production-workspace-test",
    )
    runner.read_source(SOURCE_ID)
    workspace.project_read_source(SOURCE_ID)

    manifest = workspace.write_document_manifest()

    assert manifest["validation"]["state"] == "REVIEWABLE"
    assert manifest["code"] == "600340"
    assert manifest["market"] == "CN-SH"
    assert len(manifest["documents"]) == 1
    document = manifest["documents"][0]
    assert document["source_id"] == SOURCE_ID
    assert document["source_version"] == "annual-report-2019-original"
    assert document["local_path"].startswith("pit_sources/")
    assert document["derived_text_path"].startswith("pit_sources/")
    assert (output / "document_manifest.json").is_file()

    facts = build_fact_observations(output, manifest, persist=True)
    assert facts["validation"]["state"] == "INCOMPLETE"
    verified = verify_fact_from_quote(
        output,
        doc_id=document["doc_id"],
        page=1,
        fact_name="revenue",
        domain="income_statement",
        raw_value=100,
        normalized_value=100,
        unit="CNY",
        basis="consolidated",
        quote="revenue 100",
        currency="CNY",
    )
    facts = build_fact_observations(output, manifest, persist=True)
    context = build_verified_context(output, manifest, facts, persist=True)

    assert verified["verified"] is True
    assert verified["validation"]["state"] == "REVIEWABLE"
    assert context["validation"]["state"] == "REVIEWABLE"


def test_pit_read_tool_projects_source_only_after_its_allow_read(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner,
        output,
        company_code="600340.SH",
        run_id="pit-production-workspace-test",
    )
    configure_pit_runner(runner, production_workspace=workspace)
    try:
        result = pit_read_source(SOURCE_ID)
    finally:
        clear_pit_runner()

    assert result["ok"] is True
    assert result["production_projection"]["source_id"] == SOURCE_ID
    assert [item["source_id"] for item in workspace.document_sources()] == [SOURCE_ID]


def test_workspace_never_projects_framework_or_future_source(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner,
        output,
        company_code="600340.SH",
        run_id="pit-production-workspace-test",
    )
    runner.read_framework("framework/policy.md")
    with pytest.raises(PITRunnerError, match="source_not_allowlisted"):
        runner.read_source(FUTURE_SOURCE_ID)

    with pytest.raises(RuntimeError, match="source.*read.*before projection"):
        workspace.project_read_source(FUTURE_SOURCE_ID)
    with pytest.raises(RuntimeError, match="source.*read.*before projection"):
        workspace.project_read_source("framework/policy.md")

    assert workspace.document_sources() == []
    assert not (output / "pit_sources").exists()
