from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.industry_context_acquisition import (
    CATALOG_SCHEMA_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    materialize_official_context_package,
    validate_official_context_catalog,
    validate_official_context_observation_ledger,
    validate_official_context_source_package,
)


def _catalog(**source_updates: object) -> dict:
    source = {
        "source_id": "INDDOC:NBS:TEST:2025",
        "source_version": "2026-01-19-original",
        "source_type": "OFFICIAL_INDUSTRY_CONTEXT",
        "official": True,
        "title": "国家统计局测试发布物",
        "source_url": "https://www.stats.gov.cn/test/202601/example.html",
        "official_host": "www.stats.gov.cn",
        "published_at": "2026-01-19T10:00:00+08:00",
        "data_as_of": "2025-12-31",
        "content_representation": "ORIGINAL_HTML",
        "package_path": "nbs/test-2025.html",
        "use_policy": "CONTEXT_ONLY",
        "coverage_ids": ["INDCTX:NBS:TEST"],
        "permitted_inference": "行业环境背景。",
        "prohibited_inference": ["公司份额", "公司现金流"],
    }
    source.update(source_updates)
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "industry_id": "INDUSTRY:CN:TEST",
        "cutoff_at": "2026-08-03T18:00:00+08:00",
        "sources": [source],
    }


def test_materialize_preserves_raw_response_and_context_only_boundary(tmp_path) -> None:
    catalog = _catalog()

    payload = materialize_official_context_package(
        catalog,
        tmp_path,
        downloader=lambda url: (b"<html>official original</html>", url),
    )

    assert payload["status"] == "RAW_COMPLETE_PENDING_OBSERVATION_REVIEW"
    assert payload["use_policy"] == "CONTEXT_ONLY"
    assert payload["sources"][0]["materialization_status"] == "MATERIALIZED"
    assert (tmp_path / "nbs/test-2025.html").read_bytes() == b"<html>official original</html>"
    assert validate_official_context_source_package(payload)["state"] == "REVIEWABLE"


def test_source_package_rechecks_catalog_cutoff_identity(tmp_path) -> None:
    package = materialize_official_context_package(
        _catalog(), tmp_path, downloader=lambda url: (b"official original", url),
    )
    package["sources"][0]["published_at"] = "2026-09-01T10:00:00+08:00"

    result = validate_official_context_source_package(package)

    assert result["state"] == "INVALID"
    assert "source_package:INDDOC:NBS:TEST:2025:published_after_cutoff" in result["invalid_findings"]


def test_rejects_same_day_date_only_publication_at_cutoff() -> None:
    catalog = _catalog(published_at="2026-08-03")
    validation = validate_official_context_catalog(catalog)
    assert validation["state"] == "INVALID"
    assert "INDDOC:NBS:TEST:2025:published_time_unknown_at_cutoff" in validation["invalid_findings"]


def test_rejects_non_official_host_and_does_not_fetch(tmp_path) -> None:
    catalog = _catalog(official_host="mirror.example.com")
    called = False

    def downloader(url: str) -> tuple[bytes, str]:
        nonlocal called
        called = True
        return b"unexpected", url

    with pytest.raises(ValueError, match="official_host_mismatch"):
        materialize_official_context_package(catalog, tmp_path, downloader=downloader)
    assert not called


def test_existing_raw_source_is_not_overwritten(tmp_path) -> None:
    catalog = _catalog()
    destination = tmp_path / "nbs/test-2025.html"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"first frozen response")
    payload = materialize_official_context_package(
        catalog,
        tmp_path,
        downloader=lambda url: (_ for _ in ()).throw(AssertionError("must not download again")),
    )
    assert payload["sources"][0]["materialization_status"] == "ALREADY_MATERIALIZED"
    assert destination.read_bytes() == b"first frozen response"


def test_observation_ledger_requires_materialized_locator_and_context_only(tmp_path) -> None:
    catalog = _catalog()
    source_package = materialize_official_context_package(
        catalog, tmp_path, downloader=lambda url: (b"official original", url),
    )
    ledger = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "ledger_id": "INDOBS:CN:TEST:V1",
        "industry_id": "INDUSTRY:CN:TEST",
        "cutoff_at": "2026-08-03T18:00:00+08:00",
        "source_package_ref": "source-package.json",
        "use_policy": "CONTEXT_ONLY",
        "observations": [{
            "observation_id": "INDCTX:NBS:TEST",
            "use_policy": "CONTEXT_ONLY",
            "driver_type": "demand",
            "metric_definition": "全国行业环境指标。",
            "period": {"end": "2025-12-31"},
            "value": {"yoy_pct": 1.0},
            "statement": "全国行业环境指标同比增长 1%。",
            "economic_interpretation": "需求小幅增长。",
            "profit_pool_effect": "DEMAND_SLIGHTLY_EXPANDS",
            "source_locators": [{"source_id": "INDDOC:NBS:TEST:2025", "locator": "HTML paragraph test"}],
            "permitted_inference": "背景。",
            "prohibited_inference": ["格力份额"],
        }],
    }
    assert validate_official_context_observation_ledger(
        ledger,
        source_package,
        package_root=tmp_path,
    )["state"] == "REVIEWABLE_CONTEXT_ONLY"
    invalid = deepcopy(ledger)
    invalid["observations"][0]["source_locators"][0]["source_id"] = "MISSING"
    assert "INDCTX:NBS:TEST:source_not_materialized" in validate_official_context_observation_ledger(
        invalid,
        source_package,
        package_root=tmp_path,
    )["invalid_findings"]


def test_observation_ledger_rejects_missing_raw_file_and_industry_mismatch(tmp_path) -> None:
    catalog = _catalog()
    source_package = materialize_official_context_package(
        catalog, tmp_path, downloader=lambda url: (b"official original", url),
    )
    raw_path = tmp_path / "nbs/test-2025.html"
    raw_path.unlink()
    ledger = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "ledger_id": "INDOBS:CN:TEST:V1",
        "industry_id": "INDUSTRY:CN:OTHER",
        "cutoff_at": "2026-08-03T18:00:00+08:00",
        "source_package_ref": "source-package.json",
        "use_policy": "CONTEXT_ONLY",
        "observations": [{
            "observation_id": "INDCTX:NBS:TEST",
            "use_policy": "CONTEXT_ONLY",
            "driver_type": "demand",
            "metric_definition": "全国行业环境指标。",
            "period": {"end": "2025-12-31"},
            "value": {"yoy_pct": 1.0},
            "statement": "全国行业环境指标同比增长 1%。",
            "economic_interpretation": "需求小幅增长。",
            "profit_pool_effect": "DEMAND_SLIGHTLY_EXPANDS",
            "source_locators": [{"source_id": "INDDOC:NBS:TEST:2025", "locator": "HTML paragraph test"}],
            "permitted_inference": "背景。",
            "prohibited_inference": ["公司份额"],
        }],
    }
    result = validate_official_context_observation_ledger(
        ledger,
        source_package,
        package_root=tmp_path,
    )
    assert result["state"] == "INVALID"
    assert "source_package_industry_mismatch" in result["invalid_findings"]
    assert "INDDOC:NBS:TEST:2025:raw_source_file_missing" in result["invalid_findings"]


def test_observation_ledger_rejects_wrong_yi_yuan_to_rmb_bn_conversion(tmp_path) -> None:
    catalog = _catalog()
    source_package = materialize_official_context_package(
        catalog, tmp_path, downloader=lambda url: (b"official original", url),
    )
    ledger = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "ledger_id": "INDOBS:CN:TEST:UNIT:V1",
        "industry_id": "INDUSTRY:CN:TEST",
        "cutoff_at": "2026-08-03T18:00:00+08:00",
        "source_package_ref": "source-package.json",
        "use_policy": "CONTEXT_ONLY",
        "observations": [{
            "observation_id": "INDCTX:NBS:TEST:UNIT",
            "use_policy": "CONTEXT_ONLY",
            "driver_type": "demand",
            "metric_definition": "Official retail observation.",
            "period": {"end": "2025-12-31"},
            "value": "RMB796.5bn",
            "quantity_provenance": [{
                "native_value": 7965,
                "native_unit": "RMB_100M",
                "normalized_value": 796.5,
                "normalized_unit": "RMB_BN",
                "native_locator": "Official table row",
            }],
            "statement": "Official retail observation.",
            "economic_interpretation": "Demand context only.",
            "profit_pool_effect": "CONTEXT_ONLY",
            "source_locators": [{"source_id": "INDDOC:NBS:TEST:2025", "locator": "Official table row"}],
            "permitted_inference": "Context only.",
            "prohibited_inference": ["Company demand"],
        }],
    }
    assert validate_official_context_observation_ledger(
        ledger, source_package, package_root=tmp_path,
    )["state"] == "REVIEWABLE_CONTEXT_ONLY"
    ledger["observations"][0]["quantity_provenance"][0]["normalized_value"] = 79.65
    result = validate_official_context_observation_ledger(
        ledger, source_package, package_root=tmp_path,
    )
    assert result["state"] == "INVALID"
    assert "INDCTX:NBS:TEST:UNIT:quantity_provenance[0]_conversion_mismatch" in result["invalid_findings"]
