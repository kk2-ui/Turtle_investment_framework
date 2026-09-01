from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.industry_context_acquisition import (
    CATALOG_SCHEMA_VERSION,
    materialize_official_context_package,
)
from scripts.industry_evidence_source_binding import (
    build_industry_evidence_source_binding,
    validate_industry_evidence_source_binding,
)
from scripts.industry_experience_acquisition import build_industry_evidence_acquisition_receipt
from scripts.industry_evidence_report_admission import (
    build_industry_evidence_report_admission,
    validate_industry_evidence_report_admission,
)
from scripts.phase10_acquisition import (
    acquire_source_package,
    enumerate_official_web_releases,
)
from scripts.turtle_agent.tools import read_tools, write_tools
from tests import test_enterprise_judgment_core as episode_fixture


def _plan() -> dict:
    return {
        "schema_version": "industry-evidence-acquisition-plan.v1",
        "plan_id": "IEAP:CN:TEST:2026-08-03T18:00:00+08:00",
        "company_identity": {
            "company_id": "CN:TEST",
            "company_name": "Test Company",
            "cutoff_at": "2026-08-03T18:00:00+08:00",
            "industry_ids": ["INDUSTRY:CN:TEST"],
        },
        "source_context_ref": "industry_underwriting_context.json",
        "context_id": "IUC:CN:TEST:2026-08-03T18:00:00+08:00",
        "plan_status": "READY",
        "use_policy": {
            "mode": "PRE_UNDERWRITING_EXTERNAL_EVIDENCE_AGENDA",
            "non_blocking": True,
            "can_support": [
                "EXTERNAL_INDUSTRY_SOURCE_SELECTION",
                "COMPANY_TRANSMISSION_TEST_SELECTION",
                "INDUSTRY_FUTURE_THESIS_EVIDENCE_CANDIDATES",
            ],
            "cannot_establish": [
                "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE", "OWNER_CASH_VALUE",
                "VALUATION_PARAMETER", "INVESTMENT_ACTION",
            ],
            "boundary": "Questions and source roles only.",
        },
        "tasks": [{
            "task_id": "IEAT:CN:TEST:DEMAND:1",
            "role": "DEMAND",
            "decisive_question": "What is the demand direction?",
            "company_transmission_to_verify": "Verify target company exposure with primary disclosure.",
            "measurement_boundary": "Industry demand is not company volume.",
            "required_source_roles": [
                "OFFICIAL_STATISTICS", "INDUSTRY_ASSOCIATION", "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
            ],
            "evidence_uses": ["INDUSTRY_FUTURE_THESIS", "COMPANY_TRANSMISSION_TEST"],
            "stop_rule": "Stop after a matched series or public unavailability.",
            "context_evidence_refs": ["INDCTX:TEST:DEMAND"],
        }],
        "warnings": [],
    }


def _receipt(plan: dict, *, source_role: str, source_kind: str, source_ref: str, source_url: str, published_at: str) -> dict:
    task = plan["tasks"][0]
    return build_industry_evidence_acquisition_receipt(plan, [{
        "task_id": task["task_id"],
        "outcome": "VERIFIED",
        "research_summary": "Matched the archived source to the demand question.",
        "attempted_source_roles": [source_role],
        "stop_reason": "COMPLETED",
        "observations": [{
            "observation_id": "IEAO:CN:TEST:DEMAND:1",
            "source_role": source_role,
            "source_kind": source_kind,
            "source_ref": source_ref,
            "source_url": source_url,
            "publisher": "Test official publisher",
            "published_at": published_at,
            "available_at": published_at,
            "period": "FY2025",
            "locator": "Table 1",
            "metric": "Demand direction",
            "unit": "%",
            "responsibility_boundary": task["measurement_boundary"],
            "statement": "The archived source records the requested industry demand observation.",
            "company_transmission": task["company_transmission_to_verify"],
            "relation": "SUPPORTS",
            "evidence_use": "INDUSTRY_FUTURE_THESIS",
        }],
    }])


def _context_catalog() -> dict:
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "industry_id": "INDUSTRY:CN:TEST",
        "cutoff_at": "2026-08-03T18:00:00+08:00",
        "sources": [{
            "source_id": "INDDOC:TEST:DEMAND:2025",
            "source_version": "2026-01-19-original",
            "source_type": "OFFICIAL_INDUSTRY_CONTEXT",
            "official": True,
            "title": "Test official statistic",
            "source_url": "https://www.stats.gov.cn/test/202601/demand.html",
            "official_host": "www.stats.gov.cn",
            "published_at": "2026-01-19T10:00:00+08:00",
            "data_as_of": "2025-12-31",
            "content_representation": "ORIGINAL_HTML",
            "package_path": "raw/demand.html",
            "use_policy": "CONTEXT_ONLY",
            "coverage_ids": ["INDCTX:TEST:DEMAND"],
            "permitted_inference": "Industry demand background.",
            "prohibited_inference": ["Company volume"],
        }],
    }


def _write_context_package(root: Path) -> tuple[dict, dict]:
    package_root = root / "context_raw"
    package = materialize_official_context_package(
        _context_catalog(), package_root,
        downloader=lambda url: (b"<html>frozen official statistic</html>", url),
    )
    (root / "context_package.json").write_text(json.dumps(package), encoding="utf-8")
    return package, {
        "package_id": "PKG:CONTEXT:TEST",
        "kind": "OFFICIAL_CONTEXT_SOURCE_PACKAGE",
        "package_ref": "context_package.json",
        "package_root_ref": "context_raw",
    }


def _bindings(receipt: dict, *, package_id: str, package_source_id: str) -> list[dict]:
    observation = receipt["task_receipts"][0]["observations"][0]
    return [{
        "observation_id": observation["observation_id"],
        "task_id": receipt["task_receipts"][0]["task_id"],
        "source_ref": observation["source_ref"],
        "package_id": package_id,
        "package_source_id": package_source_id,
    }]


def _episode_for_report_admission(receipt: dict) -> dict:
    episode = episode_fixture._underwriting_episode()
    observation = receipt["task_receipts"][0]["observations"][0]
    episode["evidence_trace"].extend([
        {
            "evidence_id": "IEA:" + observation["observation_id"],
            "source_ref": observation["source_ref"],
            "locator": observation["locator"],
            "scope": "External industry observation; target-company transmission remains separately tested.",
            "used_for": "Industry future thesis and company transmission test only.",
        },
        {
            "evidence_id": "EVIDENCE:TARGET:DEMAND_TRANSMISSION",
            "source_ref": "DOC:TARGET:TEST:PRE_CUTOFF",
            "locator": "p. 12",
            "scope": "Target-company primary disclosure on customer exposure.",
            "used_for": "Tests the company transmission of the external industry observation.",
        },
    ])
    episode["existing_object_refs"].append({
        "kind": "TARGET_COMPANY_PRIMARY_SOURCE_PACKAGE",
        "ref": "DOC:TARGET:TEST:PRE_CUTOFF",
        "role": "The sole primary source package used to test target-company transmission.",
    })
    return episode


def test_context_observation_must_bind_to_a_materialized_source_package(tmp_path: Path) -> None:
    plan = _plan()
    _package, descriptor = _write_context_package(tmp_path)
    receipt = _receipt(
        plan,
        source_role="OFFICIAL_STATISTICS",
        source_kind="GOVERNMENT_STATISTIC",
        source_ref="SRC:INDDOC:TEST:DEMAND:2025",
        source_url="https://www.stats.gov.cn/test/202601/demand.html",
        published_at="2026-01-19T10:00:00+08:00",
    )

    binding = build_industry_evidence_source_binding(
        plan, receipt,
        plan_ref="industry_evidence_acquisition_plan.json",
        receipt_ref="industry_evidence_acquisition_receipt.json",
        source_packages=[descriptor],
        observation_source_bindings=_bindings(
            receipt, package_id=descriptor["package_id"], package_source_id="INDDOC:TEST:DEMAND:2025",
        ),
        artifact_root=tmp_path,
    )

    assert validate_industry_evidence_source_binding(
        binding, plan, receipt, artifact_root=tmp_path,
    )["state"] == "REVIEWABLE"
    assert binding["use_policy"]["company_transmission_still_required"] is True


def test_binding_rejects_unmaterialized_or_mismatched_source_identity(tmp_path: Path) -> None:
    plan = _plan()
    _package, descriptor = _write_context_package(tmp_path)
    receipt = _receipt(
        plan,
        source_role="OFFICIAL_STATISTICS",
        source_kind="GOVERNMENT_STATISTIC",
        source_ref="SRC:INDDOC:TEST:DEMAND:2025",
        source_url="https://www.stats.gov.cn/test/202601/demand.html",
        published_at="2026-01-19T10:00:00+08:00",
    )
    binding = build_industry_evidence_source_binding(
        plan, receipt,
        plan_ref="industry_evidence_acquisition_plan.json",
        receipt_ref="industry_evidence_acquisition_receipt.json",
        source_packages=[descriptor],
        observation_source_bindings=_bindings(
            receipt, package_id=descriptor["package_id"], package_source_id="INDDOC:TEST:DEMAND:2025",
        ),
        artifact_root=tmp_path,
    )

    bad_url = deepcopy(binding)
    bad_url["observation_source_bindings"][0]["package_source_id"] = "UNKNOWN"
    assert any("package_source_not_materialized" in finding for finding in validate_industry_evidence_source_binding(
        bad_url, plan, receipt, artifact_root=tmp_path,
    )["findings"])

    raw = tmp_path / "context_raw/raw/demand.html"
    raw.unlink()
    result = validate_industry_evidence_source_binding(binding, plan, receipt, artifact_root=tmp_path)
    assert result["state"] == "INVALID"
    assert any("raw_source_missing" in finding for finding in result["findings"])


def test_phase10_issuer_package_can_supply_a_customer_role_without_current_page_substitution(tmp_path: Path) -> None:
    plan = _plan()
    source_url = "https://investor.example.com/news/customer-demand.html"
    manifest = enumerate_official_web_releases([{
        "release_id": "CUSTOMER_DEMAND",
        "title": "Customer releases demand update",
        "url": source_url,
        "published_at": "2026-07-29T16:00:00-07:00",
        "data_as_of": "2026-06-28",
        "publisher_name": "Customer Corporation",
        "official_publisher_domain": "investor.example.com",
        "language": "en",
        "source_role_provenance": {
            "schema_version": "phase10-source-role-provenance.v1",
            "publisher_entity": {
                "entity_id": "ENTITY:CUSTOMER", "legal_name": "Customer Corporation",
                "entity_kind": "OPERATING_ENTITY",
            },
            "subject_entity": {
                "entity_id": "ENTITY:TARGET", "legal_name": "Test Company",
                "entity_kind": "OPERATING_ENTITY",
            },
            "relative_role": "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
            "scope": {
                "scope_id": "SCOPE:CUSTOMER:CN:2026", "product_or_service": "customer demand",
                "geography": "China mainland", "period_start": "2026-01-01", "period_end": "2026-12-31",
            },
            "role_basis": {
                "source_id": "IR:CUSTOMER.US:CUSTOMER_DEMAND", "locator": "Demand update",
                "basis_kind": "PUBLISHER_PRIMARY_DISCLOSURE",
            },
        },
    }], company_code="CUSTOMER.US", cutoff_at="2026-08-03T18:00:00+08:00")
    package_root = tmp_path / "customer_raw"
    package = acquire_source_package(
        manifest, package_root,
        downloader=lambda _url: b"<html><body>frozen demand update</body></html>",
    )
    (tmp_path / "customer_package.json").write_text(json.dumps(package), encoding="utf-8")
    source = package["sources"][0]
    descriptor = {
        "package_id": "PKG:CUSTOMER:TEST",
        "kind": "PHASE10_SOURCE_PACKAGE",
        "package_ref": "customer_package.json",
        "package_root_ref": "customer_raw",
    }
    receipt = _receipt(
        plan,
        source_role="SUPPLIER_OR_CUSTOMER_DISCLOSURE",
        source_kind="CUSTOMER_DISCLOSURE",
        source_ref="SRC:IR:CUSTOMER:DEMAND:2026M7",
        source_url=source_url,
        published_at="2026-07-29T23:00:00+00:00",
    )

    binding = build_industry_evidence_source_binding(
        plan, receipt,
        plan_ref="industry_evidence_acquisition_plan.json",
        receipt_ref="industry_evidence_acquisition_receipt.json",
        source_packages=[descriptor],
        observation_source_bindings=_bindings(
            receipt, package_id=descriptor["package_id"], package_source_id=source["source_id"],
        ),
        artifact_root=tmp_path,
    )

    assert validate_industry_evidence_source_binding(
        binding, plan, receipt, artifact_root=tmp_path,
    )["state"] == "REVIEWABLE"
    assert (package_root / source["reader_text_path"]).is_file()

    wrong_role = deepcopy(binding)
    receipt["task_receipts"][0]["observations"][0]["source_role"] = "OFFICIAL_STATISTICS"
    receipt["task_receipts"][0]["observations"][0]["source_kind"] = "GOVERNMENT_STATISTIC"
    # The receipt itself now rejects this role because the task-to-source role
    # and the frozen Phase10 provenance no longer agree.
    assert validate_industry_evidence_source_binding(
        wrong_role, plan, receipt, artifact_root=tmp_path,
    )["state"] == "INVALID"


def test_report_read_interface_marks_a_receipt_unbound_until_the_local_source_package_is_registered(tmp_path: Path) -> None:
    plan = _plan()
    _package, descriptor = _write_context_package(tmp_path)
    receipt = _receipt(
        plan,
        source_role="OFFICIAL_STATISTICS",
        source_kind="GOVERNMENT_STATISTIC",
        source_ref="SRC:INDDOC:TEST:DEMAND:2025",
        source_url="https://www.stats.gov.cn/test/202601/demand.html",
        published_at="2026-01-19T10:00:00+08:00",
    )
    (tmp_path / "industry_evidence_acquisition_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "industry_evidence_acquisition_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    unbound = read_tools.read_industry_evidence_acquisition(str(tmp_path))
    assert unbound["ok"] is True
    assert unbound["source_binding"]["state"] == "NOT_RECORDED"
    assert len(unbound["accepted_observations"]) == 1

    written = write_tools.write_industry_evidence_source_binding(
        str(tmp_path),
        source_packages=[descriptor],
        observation_source_bindings=_bindings(
            receipt, package_id=descriptor["package_id"], package_source_id="INDDOC:TEST:DEMAND:2025",
        ),
    )
    assert written["ok"] is True
    bound = read_tools.read_industry_evidence_acquisition(str(tmp_path))
    assert bound["source_binding"]["state"] == "READY_FOR_COMPANY_TRANSMISSION_PAIR"
    assert "target-company primary evidence" in bound["source_binding"]["report_use"]


def test_report_admission_requires_a_separate_target_company_primary_trace(tmp_path: Path) -> None:
    plan = _plan()
    _package, descriptor = _write_context_package(tmp_path)
    receipt = _receipt(
        plan,
        source_role="OFFICIAL_STATISTICS",
        source_kind="GOVERNMENT_STATISTIC",
        source_ref="SRC:INDDOC:TEST:DEMAND:2025",
        source_url="https://www.stats.gov.cn/test/202601/demand.html",
        published_at="2026-01-19T10:00:00+08:00",
    )
    binding = build_industry_evidence_source_binding(
        plan, receipt,
        plan_ref="industry_evidence_acquisition_plan.json",
        receipt_ref="industry_evidence_acquisition_receipt.json",
        source_packages=[descriptor],
        observation_source_bindings=_bindings(
            receipt, package_id=descriptor["package_id"], package_source_id="INDDOC:TEST:DEMAND:2025",
        ),
        artifact_root=tmp_path,
    )
    episode = _episode_for_report_admission(receipt)
    pair = {
        "observation_id": "IEAO:CN:TEST:DEMAND:1",
        "industry_evidence_id": "IEA:IEAO:CN:TEST:DEMAND:1",
        "target_company_evidence_id": "EVIDENCE:TARGET:DEMAND_TRANSMISSION",
        "target_company_source_ref": "DOC:TARGET:TEST:PRE_CUTOFF",
        "transmission_status": "SUPPORTED",
    }
    admission = build_industry_evidence_report_admission(
        binding, plan, receipt, episode,
        binding_ref="industry_evidence_source_binding.json",
        episode_ref="episode.json",
        paired_observations=[pair],
        artifact_root=tmp_path,
    )
    assert validate_industry_evidence_report_admission(
        admission, binding, plan, receipt, episode, artifact_root=tmp_path,
    )["state"] == "REVIEWABLE"

    wrong_primary = deepcopy(admission)
    wrong_primary["paired_observations"][0]["target_company_source_ref"] = "SRC:INDDOC:TEST:DEMAND:2025"
    result = validate_industry_evidence_report_admission(
        wrong_primary, binding, plan, receipt, episode, artifact_root=tmp_path,
    )
    assert result["state"] == "INVALID"
    assert any("target_company_primary_source_not_declared" in finding for finding in result["findings"])


def test_reader_exposes_only_episode_paired_industry_observations_to_report_consumers(tmp_path: Path) -> None:
    plan = _plan()
    _package, descriptor = _write_context_package(tmp_path)
    receipt = _receipt(
        plan,
        source_role="OFFICIAL_STATISTICS",
        source_kind="GOVERNMENT_STATISTIC",
        source_ref="SRC:INDDOC:TEST:DEMAND:2025",
        source_url="https://www.stats.gov.cn/test/202601/demand.html",
        published_at="2026-01-19T10:00:00+08:00",
    )
    (tmp_path / "industry_evidence_acquisition_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "industry_evidence_acquisition_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert write_tools.write_industry_evidence_source_binding(
        str(tmp_path), [descriptor], _bindings(
            receipt, package_id=descriptor["package_id"], package_source_id="INDDOC:TEST:DEMAND:2025",
        ),
    )["ok"] is True
    episode = _episode_for_report_admission(receipt)
    (tmp_path / "episode.json").write_text(json.dumps(episode), encoding="utf-8")
    pair = {
        "observation_id": "IEAO:CN:TEST:DEMAND:1",
        "industry_evidence_id": "IEA:IEAO:CN:TEST:DEMAND:1",
        "target_company_evidence_id": "EVIDENCE:TARGET:DEMAND_TRANSMISSION",
        "target_company_source_ref": "DOC:TARGET:TEST:PRE_CUTOFF",
        "transmission_status": "SUPPORTED",
    }
    assert write_tools.write_industry_evidence_report_admission(
        str(tmp_path), episode_ref="episode.json", paired_observations=[pair],
    )["ok"] is True
    payload = read_tools.read_industry_evidence_acquisition(str(tmp_path))
    assert payload["report_admission"]["state"] == "READY"
    assert payload["report_admission"]["report_admitted_observations"] == [{
        "observation_id": "IEAO:CN:TEST:DEMAND:1",
        "industry_evidence_id": "IEA:IEAO:CN:TEST:DEMAND:1",
        "target_company_evidence_id": "EVIDENCE:TARGET:DEMAND_TRANSMISSION",
        "transmission_status": "SUPPORTED",
        "source_role": "OFFICIAL_STATISTICS",
        "metric": "Demand direction",
        "evidence_use": "INDUSTRY_FUTURE_THESIS",
    }]
