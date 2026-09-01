from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_report_context import build_verified_context
from scripts.evidence_facts import build_fact_observations, verify_fact_from_quote
from scripts.phase10_acquisition import (
    acquire_source_package,
    enumerate_independent_industry_sources,
    enumerate_official_web_releases,
    enumerate_sse_announcements,
)
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


def test_workspace_copies_source_role_provenance_to_document_and_pit_projection(
    runner: PITSourcePackage, tmp_path: Path,
) -> None:
    role_provenance = {
        "schema_version": "phase10-source-role-provenance.v1",
        "publisher_entity": {
            "entity_id": "ENTITY:COMPETITOR", "legal_name": "Competitor legal name",
            "entity_kind": "OPERATING_ENTITY",
        },
        "subject_entity": {
            "entity_id": "ENTITY:TARGET", "legal_name": "Target legal name",
            "entity_kind": "OPERATING_ENTITY",
        },
        "relative_role": "COMPETITOR_DISCLOSURE",
        "scope": {
            "scope_id": "SCOPE:CN:AC:2020", "product_or_service": "room air conditioner",
            "geography": "China mainland", "period_start": "2020-01-01", "period_end": "2020-12-31",
        },
        "role_basis": {
            "source_id": SOURCE_ID, "locator": "p. 1", "basis_kind": "PUBLISHER_PRIMARY_DISCLOSURE",
        },
    }
    for source in runner.manifest["sources"]:
        if source["source_id"] == SOURCE_ID:
            source["source_role_provenance"] = role_provenance
    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner, output, company_code="600340.SH", run_id="pit-production-workspace-test",
    )
    runner.read_source(SOURCE_ID)
    workspace.project_read_source(SOURCE_ID)
    document = workspace.write_document_manifest()["documents"][0]
    projection = json.loads((output / "pit_source_provenance.json").read_text(encoding="utf-8"))

    assert document["source_role_provenance"] == role_provenance
    assert projection["schema_version"] == "phase10-pit-source-provenance-projection.v1"
    assert projection["sources"] == [{
        "source_id": SOURCE_ID, "source_version": "annual-report-2019-original",
        "revision_policy": "ORIGINAL_VINTAGE", "source_type": "ANNUAL_REPORT",
        "admission_status": "ADMITTED", "source_role_provenance": role_provenance,
    }]


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


def test_workspace_projects_a_read_licensed_export_without_mislabeling_it_as_official(tmp_path: Path) -> None:
    source_id = "AVC:000651:AC:2025Q4:ORIGINAL"
    source_version = "avc-room-ac-retail-2025q4-original"
    source = {
        "source_id": source_id,
        "source_version": source_version,
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "title": "中国家用空调零售跟踪历史版本",
        "published_at": "2026-01-20T10:00:00+08:00",
        "data_as_of": "2025-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
        "package_path": "industry/avc-room-ac-2025q4.csv",
        "content_representation": "LICENSED_DATA_EXPORT",
        "industry_data_contract": {
            "schema_version": "phase10-independent-industry-data.v2",
            "provider_id": "AVC",
            "dataset_id": "room-air-conditioner-retail-tracker",
            "release": {
                "release_id": "AVC-AC-2025Q4-ORIGINAL",
                "version_id": source_version,
                "published_at": "2026-01-20T10:00:00+08:00",
                "data_as_of": "2025-12-31",
                "revision_status": "ORIGINAL_HISTORICAL",
                "revision_id": "ORIGINAL",
                "revision_published_at": None,
            },
            "query_identity": {"query_id": "AVC-QUERY-ROOM-AC-CN-2025Q4", "parameters": {"period": "2025Q4"}},
            "measurement_profile": {
                "methodology_disclosure": "PROVIDER_METHOD_DOCUMENTED",
                "methodology_locator": {"statement": "供应商说明了零售面板覆盖与口径。", "locator": "README.md#methodology"},
                "error_status": "UNQUANTIFIED",
                "permitted_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
                "known_limitations": [{
                    "statement": "零售面板不等于公司会计收入，覆盖和品牌映射可能变化。",
                    "conservative_treatment": "只用于同一供应商、同一映射下的相对变化；不与其他来源平均。",
                }],
                "disagreement_treatment": "DO_NOT_AVERAGE_REOPEN_MECHANISM",
            },
            "metric": {
                "metric_id": "domestic_room_ac_retail_value_share", "unit": "%",
                "semantic": "RETAIL_SELL_OUT",
                "provider_definition": {"statement": "按零售 sell-out 口径。", "locator": "README.md#metric"},
                "shipment_sell_in_status": "NOT_APPLICABLE",
            },
            "scope": {
                "geography": "中国大陆", "product_mapping": {"mapping_id": "product", "definition": "家用空调"},
                "channel_mapping": {"mapping_id": "channel", "definition": "线上与线下零售"},
                "brand_mapping": {"mapping_id": "brand", "definition": "品牌口径"},
                "denominator": {"mapping_id": "denominator", "definition": "全部品牌"},
            },
        },
    }
    manifest = enumerate_independent_industry_sources(
        [source], company_code="000651.SZ", cutoff_at="2026-02-01T18:00:00+08:00",
    )
    package = tmp_path / "package"
    export = package / "industry" / "avc-room-ac-2025q4.csv"
    export.parent.mkdir(parents=True)
    export.write_text("brand,retail_value_share\nGREE,24.3\n", encoding="utf-8")
    runner = PITSourcePackage(manifest, package, run_id="licensed-industry-workspace-test")
    assert runner.state == "REVIEWABLE"
    runner.read_source(source_id)

    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner, output, company_code="000651.SZ", run_id="licensed-industry-workspace-test",
    )
    projected = workspace.project_read_source(source_id)
    manifest_output = workspace.write_document_manifest()
    document = manifest_output["documents"][0]

    assert projected["reader_text_path"] == source["package_path"]
    assert (output / projected["local_path"]).resolve() == export
    assert (output / projected["derived_text_path"]).resolve() == export
    assert document["doc_type"] == "licensed_industry_data"
    assert document["authority"] == "industry_data"
    assert document["mime_type"] == "text/csv"
    assert verify_fact_from_quote(
        output, doc_id=document["doc_id"], page=1, fact_name="retail_value_share",
        domain="competition", raw_value=24.3, normalized_value=24.3, unit="%",
        basis="retail_sell_out", quote="GREE,24.3",
    ) == {"verified": False, "error": "non_official_source_cannot_verify"}


def test_workspace_projects_a_frozen_official_web_release_with_other_official_authority(tmp_path: Path) -> None:
    source_id = "IR:EXAMPLE.US:FY2026Q3_RESULTS"
    manifest = enumerate_official_web_releases(
        [{
            "release_id": "FY2026Q3_RESULTS",
            "title": "Issuer reports FY2026 Q3 results",
            "url": "https://investor.example.com/news/fy2026-q3-results.html",
            "published_at": "2026-07-29T16:00:00-07:00",
            "data_as_of": "2026-06-28",
            "publisher_name": "Example Corporation",
            "official_publisher_domain": "investor.example.com",
            "language": "en",
        }],
        company_code="EXAMPLE.US", cutoff_at="2026-08-21T18:00:00+08:00",
    )
    package = tmp_path / "package"
    packaged = acquire_source_package(
        manifest,
        package,
        downloader=lambda _url: b"<html><body><p>Comparable transactions increased 4.5%.</p></body></html>",
    )
    runner = PITSourcePackage(packaged, package, run_id="official-web-workspace-test")
    assert runner.state == "REVIEWABLE"
    runner.read_source(source_id)

    output = tmp_path / "output"
    workspace = PITProductionWorkspace(
        runner, output, company_code="EXAMPLE.US", run_id="official-web-workspace-test",
    )
    projected = workspace.project_read_source(source_id)
    document = workspace.write_document_manifest()["documents"][0]

    assert projected["reader_text_path"].endswith(".pages.md")
    assert document["doc_type"] == "other_official"
    assert document["authority"] == "other_official"
    assert document["mime_type"] == "text/html"
    assert document["language"] == "en"
    assert verify_fact_from_quote(
        output, doc_id=document["doc_id"], page=1, fact_name="comparable_transactions_pct",
        domain="operations", raw_value=4.5, normalized_value=4.5, unit="%",
        basis="north_america_company_operated_comparable_stores",
        quote="Comparable transactions increased 4.5%.",
    )["verified"] is True
