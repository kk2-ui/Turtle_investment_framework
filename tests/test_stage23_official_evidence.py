from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.build_report_context import (
    build_official_evidence_bundle,
    build_verified_context,
    evaluate_output_official_evidence,
)
from scripts.claim_evidence import (
    build_claim_evidence_ledger,
    persist_claim_evidence_ledger,
    validate_claim_evidence_ledger,
)
from scripts.claim_evidence_migration import migrate_claim_evidence, promote_migration_candidate
from scripts.computation_evidence import (
    _unit_for, build_calculation_observations, validate_calculation_observations,
)
from scripts.evidence_documents import (
    _manifest_core,
    _payload_hash,
    build_document_manifest,
    initialize_official_evidence_policy,
    validate_document_manifest,
)
from scripts.evidence_facts import (
    build_fact_observations,
    make_observation_id,
    validate_fact_observations,
    verify_fact_from_quote,
)
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.read_tools import (
    read_evidence_context, read_section, read_structured_ledger_contract, search_report,
)
from scripts.report_completion import evaluate_report_completion


def _filing_dir(tmp_path: Path) -> Path:
    output = tmp_path / "01502_测试公司"
    output.mkdir()
    (output / "01502_2025_年报.pdf").write_bytes(b"%PDF-1.4\nfixture official filing\n")
    (output / "2025_年报.md").write_text(
        "\n".join([
            "# FY2025 年报全文",
            "",
            "## 第 1 页",
            "",
            "公司資料",
            "致同（香港）會計師事務所有限公司",
            "",
            "## 第 30 页",
            "",
            "管理層討論與分析",
            "截至2025年末，整體毛利率約為14.19%。",
            "在管建築面積約50.62百萬平方米。",
            "商務物業 199,804 22.60 179,639 20.51 20,165 2.09",
            "非商務物業 83,996 8.08 76,671 9.57 7,325 (1.49)",
            "多元經營 (60) (0.08) (3,752) (5.05) 3,692 4.97",
            "本公司擁有人應佔利潤約為人民幣107.35百萬元。",
            "於2025年度，本集團商譽減值虧損約為人民幣18.83百萬元。",
            "派息比例相當於約為50.45%。",
            "受限制銀行存款 69,080 80,906",
            "現金及現金等價物 1,509,025 1,458,578",
            "— 同系附屬公司的定期存款（附訷37） 117,166 99,730",
            "存於一間同系附屬公司的款項 373,771 380,826",
            "最高每日存款結\n餘約為人民幣373.77百萬元。",
            "獲取的最高利息為人民\n幣4.43百萬元。",
            "金融街集團（我們的控股股東及本公司的關連人）。",
            "",
            "## 第 160 页",
            "",
            "公司財務狀況報表",
            "現金及現金等價物 1,033,070 917,246",
            "到期日超過三個月的銀行存款 117,166 99,730",
            "受限制銀行存款 34,538 42,767",
            "",
            "## 第 75 页",
            "",
            "獨立核數師報告",
            "我們認為財務報表真實而中肯地反映本集團狀況。",
        ]),
        encoding="utf-8",
    )
    (output / "pdf_sections_2025.json").write_text(json.dumps({
        "financials": {"营业收入": 100.0, "资产总计": 200.0}
    }, ensure_ascii=False), encoding="utf-8")
    return output


def test_manifest_identity_and_hash_are_deterministic(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    first = build_document_manifest(output, "01502.HK", persist=False)
    second = build_document_manifest(output, "01502.HK", persist=False)

    assert first["manifest_hash"] == second["manifest_hash"]
    assert first["documents"][0]["doc_id"] == second["documents"][0]["doc_id"]
    assert first["documents"][0]["doc_id"].startswith("DOC:HK:01502:annual_report:2025-12-31:")
    assert first["documents"][0]["derived_text_path"] == "2025_年报.md"
    assert first["validation"]["state"] == "REVIEWABLE"


def test_manifest_detects_content_hash_tampering(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    manifest = build_document_manifest(output, "01502.HK", persist=False)
    (output / "01502_2025_年报.pdf").write_bytes(b"changed")

    validation = validate_document_manifest(manifest, output)

    assert validation["state"] == "INVALID"
    assert any("content_hash_mismatch" in item for item in validation["invalid_findings"])


def test_manifest_consumes_download_provenance_sidecar(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            "01502_2025_年报.pdf": {
                "source_url": "https://www1.hkexnews.hk/fixture.pdf",
                "published_at": "2026-03-20",
                "provider": "hkexnews",
            }
        },
    }), encoding="utf-8")

    manifest = build_document_manifest(output, "01502.HK", persist=False)
    document = manifest["documents"][0]

    assert document["source_url"] == "https://www1.hkexnews.hk/fixture.pdf"
    assert document["published_at"] == "2026-03-20"
    assert document["acquisition_status"] == "DOWNLOADED"
    assert not manifest["validation"]["warnings"]


def test_manifest_ingests_registered_announcement_with_temporal_identity(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    announcement_name = "01502_2026-03-28_cash_upstream_announcement.pdf"
    announcement_text = "01502_2026-03-28_cash_upstream_announcement.md"
    (output / announcement_name).write_bytes(b"%PDF-1.4\nfixture exchange announcement\n")
    (output / announcement_text).write_text(
        "# 公告\n\n## 第 2 页\n\n附属公司已于2026年3月15日向母公司上游现金人民币278.417百万元。\n",
        encoding="utf-8",
    )
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            "01502_2025_年报.pdf": {
                "source_url": "https://www1.hkexnews.hk/annual.pdf",
                "published_at": "2026-03-20",
                "provider": "hkexnews",
            },
            announcement_name: {
                "source_url": "https://www1.hkexnews.hk/cash-upstream.pdf",
                "published_at": "2026-03-28",
                "provider": "hkexnews",
                "doc_type": "exchange_announcement",
                "authority": "company_filing",
                "fiscal_period": "POST-FY2025",
                "period_end": "2025-12-31",
                "derived_text_path": announcement_text,
                "source_id": "HKEX:01502:20260328:CASH_UPSTREAM",
                "source_version": "ORIGINAL",
                "verification_mode": "PAGE_QUOTE",
            },
        },
    }), encoding="utf-8")

    manifest = build_document_manifest(output, "01502.HK", persist=True)
    announcement = next(
        item for item in manifest["documents"]
        if item["doc_type"] == "exchange_announcement"
    )

    assert manifest["validation"]["state"] == "REVIEWABLE"
    assert announcement["period_end"] == "2025-12-31"
    assert announcement["published_at"] == "2026-03-28"
    assert announcement["derived_text_path"] == announcement_text
    assert announcement["source_id"] == "HKEX:01502:20260328:CASH_UPSTREAM"
    verified = verify_fact_from_quote(
        output,
        doc_id=announcement["doc_id"],
        page=2,
        fact_name="subsidiary_cash_upstream_rmb_m",
        domain="cash_accessibility",
        raw_value=278.417,
        normalized_value=278.417,
        unit="RMB_m",
        currency="RMB",
        basis="parent_company_receipt",
        quote="附属公司已于2026年3月15日向母公司上游现金人民币278.417百万元。",
        temporal_role="EVENT",
        event_date="2026-03-15",
        observed_at="2026-03-28",
    )
    assert verified["verified"] is True
    assert verified["observation"]["as_of"] == "2026-03-15"
    assert verified["observation"]["event_date"] == "2026-03-15"
    assert verified["observation"]["observed_at"] == "2026-03-28"

    missing_clock = verify_fact_from_quote(
        output,
        doc_id=announcement["doc_id"],
        page=2,
        fact_name="subsidiary_cash_upstream_rmb_m",
        domain="cash_accessibility",
        raw_value=278.417,
        normalized_value=278.417,
        unit="RMB_m",
        currency="RMB",
        basis="parent_company_receipt",
        quote="附属公司已于2026年3月15日向母公司上游现金人民币278.417百万元。",
    )
    assert missing_clock == {
        "verified": False,
        "error": "registered_event_document_temporal_role_required",
    }


def test_registered_non_filing_document_requires_publication_date(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    filename = "01502_tender_record.pdf"
    (output / filename).write_bytes(b"%PDF-1.4\nfixture tender record\n")
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            filename: {
                "source_url": "https://official.example/tender.pdf",
                "doc_type": "other_official",
                "authority": "other_official",
                "fiscal_period": "EVENT-2025",
                "period_end": "2025-11-01",
                "verification_mode": "PAGE_QUOTE",
            }
        },
    }), encoding="utf-8")

    import pytest
    with pytest.raises(ValueError, match="registered_document_published_at_invalid"):
        build_document_manifest(output, "01502.HK", persist=False)


def test_registered_document_authority_must_match_document_type(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    filename = "01502_official_statistics.json"
    (output / filename).write_text('{"series": []}', encoding="utf-8")
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            filename: {
                "source_url": "https://official.example/statistics.json",
                "published_at": "2025-11-02",
                "doc_type": "official_statistics",
                "authority": "company_filing",
                "fiscal_period": "2025-M10",
                "period_end": "2025-10-31",
                "verification_mode": "STRUCTURED_DATA",
            }
        },
    }), encoding="utf-8")

    import pytest
    with pytest.raises(ValueError, match="registered_document_authority_invalid"):
        build_document_manifest(output, "01502.HK", persist=False)


def _registered_announcement_manifest(tmp_path: Path) -> tuple[Path, dict]:
    output = _filing_dir(tmp_path)
    filename = "01502_2026-03-28_announcement.pdf"
    derivative = "01502_2026-03-28_announcement.md"
    (output / filename).write_bytes(b"%PDF-1.4\nfixture announcement\n")
    (output / derivative).write_text(
        "# 公告\n\n## 第 1 页\n\n本公告披露一项已完成事项。\n",
        encoding="utf-8",
    )
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            filename: {
                "source_url": "https://www1.hkexnews.hk/announcement.pdf",
                "published_at": "2026-03-28",
                "doc_type": "exchange_announcement",
                "authority": "company_filing",
                "fiscal_period": "POST-FY2025",
                "period_end": "2025-12-31",
                "derived_text_path": derivative,
                "verification_mode": "PAGE_QUOTE",
            }
        },
    }), encoding="utf-8")
    return output, build_document_manifest(output, "01502.HK", persist=False)


def test_manifest_validator_rechecks_registered_identity_after_tampering(tmp_path: Path) -> None:
    output, manifest = _registered_announcement_manifest(tmp_path)
    announcement = next(
        item for item in manifest["documents"]
        if item["doc_type"] == "exchange_announcement"
    )

    for field, bad_value, finding in (
        ("authority", "other_official", "authority_incompatible_with_registered_doc_type"),
        ("published_at", None, "published_at_invalid"),
        ("source_url", None, "source_url_invalid"),
    ):
        tampered = deepcopy(manifest)
        target = next(item for item in tampered["documents"] if item["doc_id"] == announcement["doc_id"])
        target[field] = bad_value
        tampered["manifest_hash"] = _payload_hash(_manifest_core(tampered))
        validation = validate_document_manifest(tampered, output)
        assert validation["state"] == "INVALID"
        assert any(finding in item for item in validation["invalid_findings"])


def test_registered_page_quote_document_without_page_marked_text_is_incomplete(tmp_path: Path) -> None:
    output, manifest = _registered_announcement_manifest(tmp_path)
    announcement = next(
        item for item in manifest["documents"]
        if item["doc_type"] == "exchange_announcement"
    )
    (output / announcement["derived_text_path"]).write_text(
        "# 公告\n\n没有页码定位。\n", encoding="utf-8"
    )
    validation = validate_document_manifest(manifest, output)

    assert validation["state"] == "INCOMPLETE"
    assert any("page_markers_missing" in item for item in validation["incomplete_findings"])

    no_derivative = deepcopy(manifest)
    target = next(item for item in no_derivative["documents"] if item["doc_id"] == announcement["doc_id"])
    target["derived_text_path"] = None
    no_derivative["manifest_hash"] = _payload_hash(_manifest_core(no_derivative))
    validation = validate_document_manifest(no_derivative, output)
    assert validation["state"] == "INCOMPLETE"
    assert any("page_marked_derivative_missing" in item for item in validation["incomplete_findings"])


def test_quote_verifier_rejects_nonreviewable_manifest_and_structured_data(tmp_path: Path) -> None:
    output, manifest = _registered_announcement_manifest(tmp_path)
    announcement = next(
        item for item in manifest["documents"]
        if item["doc_type"] == "exchange_announcement"
    )
    tampered = deepcopy(manifest)
    target = next(item for item in tampered["documents"] if item["doc_id"] == announcement["doc_id"])
    target["authority"] = "other_official"
    tampered["manifest_hash"] = _payload_hash(_manifest_core(tampered))
    (output / "document_manifest.json").write_text(
        json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rejected = verify_fact_from_quote(
        output, doc_id=announcement["doc_id"], page=1, fact_name="event",
        domain="cash_accessibility", raw_value="完成", normalized_value="完成",
        unit="text", basis="event", quote="本公告披露一项已完成事项。",
    )
    assert rejected == {"verified": False, "error": "document_manifest_not_reviewable"}

    data_file = "01502_official_statistics.json"
    (output / data_file).write_text('{"value": 12}', encoding="utf-8")
    (output / "document_sources.json").write_text(json.dumps({
        "schema_version": "document-sources.v1",
        "documents": {
            data_file: {
                "source_url": "https://official.example/statistics.json",
                "published_at": "2026-03-20",
                "doc_type": "official_statistics",
                "authority": "official_statistics",
                "fiscal_period": "FY2025",
                "period_end": "2025-12-31",
                "verification_mode": "STRUCTURED_DATA",
            }
        },
    }), encoding="utf-8")
    structured_manifest = build_document_manifest(output, "01502.HK", persist=True)
    structured = next(
        item for item in structured_manifest["documents"]
        if item["doc_type"] == "official_statistics"
    )
    rejected = verify_fact_from_quote(
        output, doc_id=structured["doc_id"], page=1, fact_name="statistic",
        domain="industry", raw_value=12, normalized_value=12,
        unit="count", basis="official_statistics", quote='{"value": 12}',
    )
    assert rejected == {
        "verified": False,
        "error": "structured_document_requires_deterministic_data_verifier",
    }


def test_only_page_located_source_facts_are_verified(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    manifest = build_document_manifest(output, "01502.HK", persist=False)
    facts = build_fact_observations(output, manifest, persist=False)
    verified = [item for item in facts["observations"] if item["status"] == "VERIFIED"]
    candidates = [item for item in facts["observations"] if item["status"] == "CANDIDATE"]

    assert {item["fact_name"] for item in verified} >= {
        "auditor_name", "overall_gross_margin_pct", "managed_area_m_sqm",
        "business_property_gross_margin_pct",
        "non_business_property_gross_margin_pct", "goodwill_impairment_rmb_m",
        "diversified_operations_gross_margin_pct", "net_profit_parent_rmb_m",
        "dividend_payout_ratio_pct", "restricted_bank_deposits_rmb_m",
        "cash_and_cash_equivalents_rmb_m", "related_party_term_deposits_rmb_m",
        "company_only_cash_and_cash_equivalents_rmb_m",
        "company_only_term_deposits_rmb_m",
        "company_only_restricted_bank_deposits_rmb_m",
        "amounts_placed_with_fellow_subsidiary_rmb_m",
        "finance_company_max_daily_deposit_rmb_m",
        "finance_company_interest_income_rmb_m",
        "controlling_shareholder_identity",
    }
    assert all(item["locator"]["page"] and item["raw_text"] for item in verified)
    assert {item["fact_name"] for item in candidates} == {"revenue", "total_assets"}
    assert all(item["unit"] == "source_native_unresolved" for item in candidates)
    by_name = {item["fact_name"]: item for item in verified}
    assert by_name["restricted_bank_deposits_rmb_m"]["normalized_value"] == 69.08
    assert by_name["amounts_placed_with_fellow_subsidiary_rmb_m"]["normalized_value"] == 373.771
    assert by_name["diversified_operations_gross_margin_pct"]["normalized_value"] == -0.08
    assert by_name["net_profit_parent_rmb_m"]["normalized_value"] == 107.35
    assert by_name["controlling_shareholder_identity"]["normalized_value"] == "金融街集團"


def test_verified_quote_is_rechecked_at_exact_page(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    manifest = build_document_manifest(output, "01502.HK", persist=False)
    facts = build_fact_observations(output, manifest, persist=False)
    tampered = deepcopy(facts)
    item = next(value for value in tampered["observations"] if value["status"] == "VERIFIED")
    item["raw_text"] = "不存在的原文"
    item["observation_id"] = make_observation_id(item)
    # Recompute hash so the locator/quote check, rather than the envelope hash,
    # is what makes the payload invalid.
    from scripts.evidence_facts import _observation_core, _payload_hash
    tampered["observation_hash"] = _payload_hash(_observation_core(tampered))

    validation = validate_fact_observations(tampered, manifest, output)

    assert validation["state"] == "INVALID"
    assert any("quote_not_at_locator" in finding for finding in validation["invalid_findings"])


def test_exact_quote_tool_can_verify_new_fact_and_reject_wrong_value(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    manifest = build_document_manifest(output, "01502.HK", persist=True)
    build_fact_observations(output, manifest, persist=True)
    doc_id = manifest["documents"][0]["doc_id"]

    success = verify_fact_from_quote(
        output,
        doc_id=doc_id,
        page=30,
        fact_name="gross_margin_pct_manual",
        domain="operations",
        raw_value=14.19,
        normalized_value=14.19,
        unit="pct",
        basis="consolidated",
        quote="截至2025年末，整體毛利率約為14.19%。",
    )
    failure = verify_fact_from_quote(
        output,
        doc_id=doc_id,
        page=30,
        fact_name="invented_value",
        domain="operations",
        raw_value=99.0,
        normalized_value=99.0,
        unit="pct",
        basis="consolidated",
        quote="截至2025年末，整體毛利率約為14.19%。",
    )

    assert success["verified"] is True
    assert success["observation"]["observation_id"].startswith("OBS:")
    assert failure == {"verified": False, "error": "raw_value_not_in_quote"}


def test_context_exposes_verified_facts_but_not_candidates(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    bundle = build_official_evidence_bundle(output, "01502.HK", persist=True)
    context = bundle["context"]
    visible = [item for values in context["domains"].values() for item in values]

    assert context["validation"]["state"] == "REVIEWABLE"
    assert visible and all(item["status"] == "VERIFIED" for item in visible)
    assert not any(item["fact_name"] == "revenue" for item in visible)
    first_fingerprint = context["meta"]["context_fingerprint"]
    rebuilt = build_verified_context(output, bundle["manifest"], bundle["facts"], persist=False)
    assert rebuilt["meta"]["context_fingerprint"] == first_fingerprint


def test_claim_migration_atomizes_verified_numbers_without_touching_canonical(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    build_official_evidence_bundle(output, "01502.HK", persist=True)
    ledger = {
        "schema_version": "claim-evidence-ledger.v1",
        "report_id": "01502.HK",
        "revision": 1,
        "lifecycle": "decision_ready",
        "change_reason": "legacy fixture",
        "claims": [{
            "claim_id": "C001",
            "claim": "segment margins diverged",
            "chapters": [0],
            "raw_facts": [{
                "evidence_id": "E001", "source_id": "01502_2025_年报.pdf",
                "source_group_id": "annual_report", "fact": "22.60% and 8.08%",
                "authority": "audited_filing", "claim_distance": "raw_data",
                "published_at": "2026-03-20", "data_as_of": "2025-12-31",
                "direct_support": True, "support_type": "supports", "basis_match": "exact",
                "conflict_of_interest": "issuer",
            }, {
                "evidence_id": "E002", "source_id": "compute_gg",
                "source_group_id": "tool", "fact": "GG=8.08%",
                "authority": "company_filing", "claim_distance": "direct_statement",
                "published_at": "2026-03-20", "data_as_of": "2025-12-31",
                "direct_support": True, "support_type": "supports", "basis_match": "exact",
                "conflict_of_interest": "calculation",
            }],
            "reasoning_steps": ["compare"], "alternative_explanations": ["mix"],
            "applicability_conditions": ["same basis"],
            "confidence": {"kind": "analyst_subjective", "value": 0.7, "basis": "filing"},
            "decision_impact": {"valuation": "lower", "position": "hold", "action": "review"},
            "decision_entry_ids": [],
        }],
        "freeze": {"frozen": False, "fingerprint": "", "frozen_at": None},
    }
    canonical_path = output / "claim_evidence.json"
    canonical_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    before = canonical_path.read_bytes()

    result = migrate_claim_evidence(output, persist=True)

    assert canonical_path.read_bytes() == before
    rows = result["candidate"]["claims"][0]["raw_facts"]
    direct = [item for item in rows if item.get("direct_support")]
    assert {item["fact"].split("(", 1)[0] for item in direct} == {
        "business_property_gross_margin_pct", "non_business_property_gross_margin_pct",
    }
    assert all(item.get("observation_id", "").startswith("OBS:") for item in direct)
    assert next(item for item in rows if item["evidence_id"] == "E002")["support_type"] == "context"
    assert (output / "claim_evidence_migration_report.json").is_file()
    contract = read_structured_ledger_contract(str(output), "claim")
    migration = contract["deterministic_migration"]
    assert migration["canonical_ledger_unchanged"] is True
    assert migration["candidate_claims"][0]["claim_id"] == "C001"
    assert "never reconstruct" in migration["instruction"]


def test_read_tools_return_document_and_candidate_identity(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    build_official_evidence_bundle(output, "01502.HK", persist=True)

    section = read_section(str(output), 2025, "MDA", max_chars=1000)
    searched = search_report(str(output), "毛利率", 2025)
    context = read_evidence_context(str(output), "operations")

    assert section["document_id"].startswith("DOC:")
    assert section["verification_eligible"] is True
    assert searched["document_id"] == section["document_id"]
    assert searched["hits"][0]["status"] == "CANDIDATE"
    assert searched["hits"][0]["page"] == 30
    assert context["citable"] is True
    assert all(item["status"] == "VERIFIED" for item in context["facts"])


def test_new_policy_fails_closed_and_legacy_output_skips(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    assert evaluate_output_official_evidence(legacy, persist=False)["state"] == "SKIP"

    output = _filing_dir(tmp_path)
    initialize_official_evidence_policy(output, run_id="run", enforced=True)
    missing = evaluate_output_official_evidence(output, persist=False)
    assert missing["state"] == "INCOMPLETE"
    build_official_evidence_bundle(output, "01502.HK", persist=True)
    assert evaluate_output_official_evidence(output, persist=False)["state"] == "REVIEWABLE"


def test_completion_contract_contains_official_evidence_gate(tmp_path: Path) -> None:
    output = tmp_path / "new_run"
    output.mkdir()
    initialize_official_evidence_policy(output, run_id="run", enforced=True)

    completion = evaluate_report_completion("draft", str(output))

    assert completion.status == "INCOMPLETE"
    assert completion.validators["official_evidence"]["state"] == "INCOMPLETE"
    assert any("Official evidence: INCOMPLETE" in item for item in completion.blocking_findings)


def _claim(source_id: str, observation_id: str | None) -> dict:
    evidence = {
        "evidence_id": "ev.margin",
        "source_id": source_id,
        "source_group_id": "issuer-fy2025",
        "fact": "FY2025整体毛利率为14.19%。",
        "authority": "audited_filing",
        "claim_distance": "raw_data",
        "published_at": "2026-03-20",
        "data_as_of": "2025-12-31",
        "direct_support": True,
        "support_type": "supports",
        "basis_match": "exact",
        "conflict_of_interest": "公司披露，数字经审计",
        "cross_checked_by": [],
    }
    if observation_id:
        evidence["observation_id"] = observation_id
    return {
        "claim_id": "claim.margin",
        "claim": "毛利率处于低位。",
        "chapters": [0],
        "raw_facts": [evidence],
        "reasoning_steps": ["毛利率约束利润弹性。"],
        "alternative_explanations": ["业务组合变化可能压低表观毛利率。"],
        "applicability_conditions": ["统计口径保持一致。"],
        "confidence": {"kind": "analyst_subjective", "value": 0.7, "basis": "已审计披露"},
        "decision_impact": {"valuation": "压低基准估值", "position": "不提高仓位", "action": "持续跟踪"},
        "decision_entry_ids": ["valuation.v_final@test"],
    }


def test_direct_support_requires_verified_observation_on_new_runs(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    bundle = build_official_evidence_bundle(output, "01502.HK", persist=True, run_id="run", enforced=True)
    observation = next(item for item in bundle["facts"]["observations"] if item["fact_name"] == "overall_gross_margin_pct")
    (output / "decision_ledger.json").write_text(json.dumps({
        "entries": [{"entry_id": "valuation.v_final@test"}]
    }), encoding="utf-8")
    report = "## Ch0 测试\n毛利率处于低位。[claim: claim.margin]"

    missing = build_claim_evidence_ledger(output, [_claim(observation["doc_id"], None)], change_reason="test", freeze=False)
    linked = build_claim_evidence_ledger(output, [_claim(observation["doc_id"], observation["observation_id"])], change_reason="test", freeze=False)
    missing_result = validate_claim_evidence_ledger(missing, report_text=report, output_dir=output)
    linked_result = validate_claim_evidence_ledger(linked, report_text=report, output_dir=output)

    assert any("verified_evidence_identity_required" in item for item in missing_result["invalid_findings"])
    assert not any("observation" in item for item in linked_result["invalid_findings"])


def test_verified_calculation_identity_supports_only_its_exact_atomic_value(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    (output / "compute_bundle.json").write_text(json.dumps({
        "factor2": {"M": 0.5, "M_source": "fixture", "np_avg_3y": 10.0, "r_np": 6.0},
        "factor3": {
            "aa": {"FY2025": 8.0}, "aa_avg": {"3y": 8.0, "5y": 8.0, "all": 8.0},
            "receipt_ratios": {}, "true_revenue": {}, "gg": {"base": 6.2, "pessimistic": 5.0, "optimistic": 7.0},
            "g_adj": 1.0, "mcapex_split_used": 0.5, "rejection": {},
            "net_cash": 20.0, "net_cash_pct_mc": 25.0,
        },
        "params": {"II": 5.5, "Rf": 4.0, "Q": 0.1},
        "market": {"mc_rmb": 100.0, "shares_m": 10.0},
    }), encoding="utf-8")
    build_official_evidence_bundle(output, "01502.HK", persist=True, run_id="run", enforced=True)
    calculations = build_calculation_observations(output, persist=True)
    gg = next(item for item in calculations["calculations"] if item["tool"] == "compute_gg" and item["metric_path"] == "gg_base")
    assert gg["unit"] == "pct_or_pct_point"
    (output / "decision_ledger.json").write_text(json.dumps({
        "entries": [{"entry_id": "valuation.v_final@test"}]
    }), encoding="utf-8")
    claim = _claim("compute_gg", None)
    evidence = claim["raw_facts"][0]
    evidence.update({
        "calculation_id": gg["calculation_id"], "fact": "GG=6.2%",
        "authority": "verified_calculation", "claim_distance": "direct_statement",
        "source_group_id": "derived:compute_gg", "conflict_of_interest": "deterministic calculation",
    })
    payload = build_claim_evidence_ledger(output, [claim], change_reason="calculation fixture", freeze=False)
    report = "## Ch0 测试\n毛利率处于低位。[claim: claim.margin]"

    valid = validate_claim_evidence_ledger(payload, report_text=report, output_dir=output)
    assert not valid["invalid_findings"]
    payload["claims"][0]["raw_facts"][0]["fact"] = "GG=6.3%"
    invalid = validate_claim_evidence_ledger(payload, report_text=report, output_dir=output)
    assert any("calculation_numeric_support_mismatch" in item for item in invalid["invalid_findings"])

    tampered = deepcopy(calculations)
    tampered["calculations"][0]["value"] = 999
    assert validate_calculation_observations(tampered, output)["state"] == "INVALID"
    legacy_claim = _claim("compute_gg", None)
    legacy_claim["raw_facts"][0].update({"fact": "GG=6.2%", "source_group_id": "legacy-tool"})
    legacy = build_claim_evidence_ledger(output, [legacy_claim], change_reason="legacy compute", freeze=False)
    (output / "claim_evidence.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "chapters").mkdir()
    (output / "chapters" / "_ch00.md").write_text(
        "## Ch0 测试\n毛利率处于低位。[claim: claim.margin]", encoding="utf-8"
    )
    migrated = migrate_claim_evidence(output, persist=True)
    calc_rows = [
        item for item in migrated["candidate"]["claims"][0]["raw_facts"]
        if item.get("calculation_id")
    ]
    assert len(calc_rows) == 1
    assert calc_rows[0]["calculation_id"] == gg["calculation_id"]
    assert calc_rows[0]["authority"] == "verified_calculation"
    assert migrated["report"]["candidate_validation"]["state"] == "REVIEWABLE"
    promotion = promote_migration_candidate(output)
    assert promotion["promoted"] is True
    canonical = json.loads((output / "claim_evidence.json").read_text(encoding="utf-8"))
    assert canonical["freeze"]["frozen"] is True
    assert canonical["claims"][0]["claim"] == legacy_claim["claim"]

    # Unified evidence preflight performs the same migration automatically for
    # legacy direct rows, but only when the candidate is fully reviewable.
    (output / "claim_evidence.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")
    automatic = build_official_evidence_bundle(
        output, "01502.HK", persist=True, run_id="run-2", enforced=True
    )
    assert automatic["claim_migration"]["promotion"]["promoted"] is True
    auto_canonical = json.loads((output / "claim_evidence.json").read_text(encoding="utf-8"))
    assert auto_canonical["lifecycle"] == "decision_ready"


def test_calculation_units_do_not_label_capex_amounts_as_percentages() -> None:
    result = {"gg_normalized": {"maintenance_capex": 102.19, "base": 6.2}}
    assert _unit_for("gg_normalized.maintenance_capex", result) == "source_native"
    assert _unit_for("gg_normalized.base", result) == "pct_or_pct_point"


def test_verified_observation_cannot_be_borrowed_for_unrelated_numbers(tmp_path: Path) -> None:
    output = _filing_dir(tmp_path)
    bundle = build_official_evidence_bundle(
        output, "01502.HK", persist=True, run_id="run", enforced=True
    )
    observation = next(
        item for item in bundle["facts"]["observations"]
        if item["fact_name"] == "overall_gross_margin_pct"
    )
    (output / "decision_ledger.json").write_text(json.dumps({
        "entries": [{"entry_id": "valuation.v_final@test"}]
    }), encoding="utf-8")
    claim = _claim(observation["doc_id"], observation["observation_id"])
    claim["raw_facts"][0]["fact"] = "FY2025商务毛利率22.60%，非商务毛利率8.08%。"
    payload = build_claim_evidence_ledger(
        output, [claim], change_reason="adversarial mismatch", freeze=False
    )

    result = validate_claim_evidence_ledger(
        payload,
        report_text="## Ch0 测试\n毛利率处于低位。[claim: claim.margin]",
        output_dir=output,
    )

    assert any(
        "observation_numeric_support_mismatch" in item
        for item in result["invalid_findings"]
    )

    rejected = persist_claim_evidence_ledger(
        output, payload,
        report_text="## Ch0 测试\n毛利率处于低位。[claim: claim.margin]",
    )
    assert rejected["written"] is False
    assert (output / "claim_evidence_last_rejected.json").is_file()
    saved = json.loads(
        (output / "claim_evidence_last_rejected_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(
        "observation_numeric_support_mismatch" in item
        for item in saved["invalid_findings"]
    )


def test_evidence_tools_are_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.read_tools")
    registry.auto_discover("turtle_agent.tools.write_tools")

    assert "read_evidence_context" in registry.list_tools()
    assert "verify_official_fact" in registry.list_tools()


def test_phase01_schemas_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("document_manifest.schema.json", "fact_observations.schema.json", "report_context.schema.json"):
        payload = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert payload["$schema"].endswith("2020-12/schema")
