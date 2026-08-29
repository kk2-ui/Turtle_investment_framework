from __future__ import annotations

import json
from pathlib import Path

from scripts.real_report_acceptance import (
    CJO_REQUIRED_MACHINE_GATES,
    REQUIRED_MACHINE_GATES,
    REVIEW_DIMENSIONS,
    _hash,
    _blind_packet_text,
    _report_bundle_hash,
    evaluate_acceptance,
    find_report,
    find_technical_report,
    validate_independent_review,
)
from scripts.prepare_acceptance_candidate import seed_candidate
from scripts.approve_gold_contract import approve_preview, build_approval_preview


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _config(path: Path, output: Path) -> Path:
    payload = {
        "schema_version": "real-report-acceptance-config.v1",
        "phase": "08",
        "frozen_at": "2026-08-03",
        "policy": {
            "minimum_independent_reviews": 2,
            "human_approval_required": True,
            "automatic_ceiling": "READY_FOR_BLIND_REVIEW",
            "no_compensating_score": True,
            "control_sample_hidden_until_rules_frozen": True,
            "forward_judgment_contract_required": True,
        },
        "samples": [{
            "sample_id": "sample", "company_code": "000001.SZ", "archetype": "test",
            "role": "candidate", "output_dir": str(output), "report_period": "FY2025",
            "rules_visible": True,
        }],
    }
    _write_json(path, payload)
    return path


def _report(output: Path) -> Path:
    path = output / "reports" / "最新年报_分析报告_v13.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 公司分析\n\n## 结论\n\n事实、机制、估值和动作。\n", encoding="utf-8")
    return path


def _pass_gates(output: Path) -> None:
    for gate, (filename, accepted) in REQUIRED_MACHINE_GATES.items():
        state = sorted(accepted)[0]
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        payload = {key: state}
        if gate == "thesis_test":
            payload["forward_judgment_state"] = "DECISION_READY"
        _write_json(output / filename, payload)
    _write_json(output / "research_execution.json", {
        "enforced": True,
        "chapters": {
            "2": {"enforced": True, "tool_counts": {"read_section": 2, "web_search": 2, "web_fetch": 1}, "fiscal_years": [2024, 2025], "sections": ["MDA", "SEG"]}
        },
    })
    _write_json(output / "judgment_review_validation.json", {"state": "REVIEWED", "ceiling_verdict": "COMPETENT"})
    _write_json(output / "judgment_review.json", {"ceiling_verdict": "COMPETENT", "fragile_leaps": [], "dimension_assessments": {}})


def _pass_cjo_gates(output: Path) -> None:
    _write_json(output / "analysis_contract.json", {"analysis_purpose": "COMPANY_JUDGMENT_ONLY"})
    for gate, (filename, accepted) in CJO_REQUIRED_MACHINE_GATES.items():
        state = sorted(accepted)[0]
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        payload = {key: state}
        if gate == "thesis_test":
            payload.update({"forward_judgment_state": "DECISION_READY", "analysis_purpose": "COMPANY_JUDGMENT_ONLY"})
        if gate == "financial_driver_bridge":
            payload["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
        _write_json(output / filename, payload)
    _write_json(output / "research_execution.json", {
        "enforced": True,
        "chapters": {
            "2": {"enforced": True, "tool_counts": {"read_section": 2, "web_search": 2, "web_fetch": 1}, "fiscal_years": [2024, 2025], "sections": ["MDA", "SEG"]}
        },
    })
    _write_json(output / "judgment_review.json", {"ceiling_verdict": "COMPETENT", "fragile_leaps": [], "dimension_assessments": {}})


def _review(
    reviewer: str, verdict: str = "INSIGHTFUL", variant_id: str = "variant",
    packet_sha256: str = "0" * 64, *, context_id: str | None = None,
    provider: str = "openai", model: str = "review-model",
) -> dict:
    return {
        "schema_version": "independent-report-review.v2",
        "sample_id": "sample",
        "variant_id": variant_id,
        "reviewer_id": reviewer,
        "reviewer_provenance": {
            "actor_type": "model", "provider": provider, "model": model,
            "context_id": context_id or f"context-{reviewer}",
            "reviewed_packet_sha256": packet_sha256,
        },
        "independence": {
            "did_not_generate_candidate": True,
            "variant_label_blinded": True,
            "no_prior_review_seen": True,
            "reviewer_context_isolated": True,
            "generator_identity_disjoint": True,
        },
        "dimensions": {
            name: {"state": "STRONG", "basis": "该判断直接对应报告中的原始证据、竞争解释、现金流影响、估值变化与最终动作传导关系。", "report_locations": ["Ch12"]}
            for name in REVIEW_DIMENSIONS
        },
        "ceiling_verdict": verdict,
        "fatal_findings": [],
        "reviewer_limits": ["未取得管理层非公开资料"],
        "submitted_at": "2026-08-03T00:00:00+00:00",
    }


def _variant_and_packet(output: Path) -> tuple[str, str]:
    report = find_report(output)
    assert report is not None
    technical = find_technical_report(report)
    report_sha256 = _report_bundle_hash(report, technical)
    variant_id = report_sha256[:16]
    packet = _blind_packet_text({
        "report_path": str(report), "technical_report_path": str(technical) if technical else None,
        "variant_id": variant_id,
    })
    import hashlib
    return variant_id, hashlib.sha256(packet.encode("utf-8")).hexdigest()


def test_missing_report_is_not_assessable_and_never_auto_passes(tmp_path: Path) -> None:
    output = tmp_path / "missing"
    config = _config(tmp_path / "config.json", output)
    result = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)
    assert result["samples"][0]["machine_status"] == "NOT_ASSESSABLE"
    assert result["summary"]["benchmark_approved_count"] == 0


def test_validation_only_draft_is_an_acceptance_object_not_a_published_report(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    draft = output / "reports" / "drafts" / "000001_分析报告_v13_draft.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("# 验证候选", encoding="utf-8")

    assert find_report(output) == draft
    config = _config(tmp_path / "config.json", output)
    sample = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)["samples"][0]
    assert sample["machine_status"] == "TECHNICALLY_BLOCKED"


def test_newer_complete_dual_layer_draft_supersedes_stale_formal_and_binds_variant(
    tmp_path: Path,
) -> None:
    output = tmp_path / "candidate"
    formal = _report(output)
    draft = output / "reports" / "drafts" / "000001_分析报告_v13_draft.md"
    technical = output / "reports" / "drafts" / "000001_分析报告_v13_technical_draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("# 当前验证备忘录", encoding="utf-8")
    technical.write_text("# 当前技术附录\n\n## Ch0\n证据", encoding="utf-8")
    _pass_gates(output)
    _write_json(output / "run_manifest.json", {
        "status": "COMPLETED",
        "publication": {
            "status": "VALIDATED_NOT_PUBLISHED", "validation_only": True,
        },
    })
    formal.write_text("# 后写入但仍是旧正式稿", encoding="utf-8")
    assert formal.is_file()
    assert find_report(output) == draft
    assert find_technical_report(draft) == technical

    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    first = evaluate_acceptance(config, acceptance_root=acceptance, persist=True)
    sample = first["samples"][0]
    first_variant = sample["variant_id"]
    assert sample["technical_report_path"] == str(technical)
    packet = acceptance / "blind_packets" / f"{first_variant}.md"
    packet_text = packet.read_text(encoding="utf-8")
    assert "当前验证备忘录" in packet_text and "当前技术附录" in packet_text
    template = json.loads(
        (acceptance / "blind_packets" / f"{first_variant}.review_template.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["review_contract"]["dimension_state_allowed_values"] == [
        "MIXED", "NOT_ASSESSABLE", "STRONG", "WEAK",
    ]
    assert template["review_contract"]["ceiling_verdict_allowed_values"] == [
        "COMPETENT", "FRAGILE", "INSIGHTFUL", "NOT_ASSESSABLE",
    ]
    assert "PASS/FAIL" in template["review_contract"]["instruction"]
    assert "industry-future thesis" in template["review_contract"]["instruction"]
    assert "trend inventory is WEAK" in template["review_contract"]["instruction"]

    technical.write_text("# 当前技术附录\n\n## Ch0\n证据已变化", encoding="utf-8")
    second = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)
    assert second["samples"][0]["variant_id"] != first_variant


def test_validated_draft_identity_survives_later_rule_upgrade_block(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    formal = _report(output)
    draft = output / "reports" / "drafts" / "000001_分析报告_v13_draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("# 已评审验证候选", encoding="utf-8")
    formal.write_text("# 更旧的正式稿", encoding="utf-8")
    _write_json(output / "completion_report.json", {"status": "INVALID"})
    _write_json(output / "run_manifest.json", {
        "status": "COMPLETED",
        "publication": {"status": "VALIDATED_NOT_PUBLISHED", "validation_only": True},
    })
    assert find_report(output) == draft


def test_legacy_report_without_current_ledgers_is_technically_blocked(tmp_path: Path) -> None:
    output = tmp_path / "legacy"
    _report(output)
    config = _config(tmp_path / "config.json", output)
    result = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)
    sample = result["samples"][0]
    assert sample["machine_status"] == "TECHNICALLY_BLOCKED"
    assert "decision_ledger:MISSING" in sample["hard_gates"]["blocking"]


def test_machine_complete_report_stops_at_blind_review(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output)
    _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    result = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)
    sample = result["samples"][0]
    assert sample["hard_gates"]["passed"] is True
    assert sample["machine_status"] == "READY_FOR_BLIND_REVIEW"
    assert sample["research_execution"]["two_fiscal_years_observed"] is True


def test_company_judgment_acceptance_requires_operating_gates_not_valuation_or_decision(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output)
    _pass_cjo_gates(output)
    config = _config(tmp_path / "config.json", output)

    sample = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)["samples"][0]

    assert sample["machine_status"] == "READY_FOR_BLIND_REVIEW"
    assert sample["hard_gates"]["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert "financial_driver_bridge" in sample["hard_gates"]["gates"]
    assert "official_evidence" in sample["hard_gates"]["gates"]
    assert "decision_ledger" not in sample["hard_gates"]["gates"]
    assert "valuation_model" not in sample["hard_gates"]["gates"]


def test_company_judgment_acceptance_rejects_investment_purpose_thesis(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output)
    _pass_cjo_gates(output)
    thesis = json.loads((output / "thesis_test_validation.json").read_text(encoding="utf-8"))
    thesis["analysis_purpose"] = "INVESTMENT_DECISION"
    _write_json(output / "thesis_test_validation.json", thesis)
    config = _config(tmp_path / "config.json", output)

    sample = evaluate_acceptance(config, acceptance_root=tmp_path / "acceptance", persist=False)["samples"][0]

    assert sample["machine_status"] == "TECHNICALLY_BLOCKED"
    assert "thesis_test:analysis_purpose:INVESTMENT_DECISION" in sample["hard_gates"]["blocking"]


def test_new_gold_candidate_requires_forward_judgment_contract(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output)
    _pass_gates(output)
    thesis_validation = json.loads((output / "thesis_test_validation.json").read_text(encoding="utf-8"))
    thesis_validation.pop("forward_judgment_state")
    _write_json(output / "thesis_test_validation.json", thesis_validation)

    config = _config(tmp_path / "config.json", output)
    sample = evaluate_acceptance(
        config, acceptance_root=tmp_path / "acceptance", persist=False,
    )["samples"][0]

    assert sample["machine_status"] == "TECHNICALLY_BLOCKED"
    assert "forward_judgment_contract:MISSING" in sample["hard_gates"]["blocking"]


def test_two_independent_reviews_create_candidate_but_not_approval(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    variant_id, packet_sha = _variant_and_packet(output)
    _write_json(acceptance / "reviews" / "sample" / "r1.json", _review("reviewer-1", variant_id=variant_id, packet_sha256=packet_sha))
    _write_json(acceptance / "reviews" / "sample" / "r2.json", _review("reviewer-2", "COMPETENT", variant_id, packet_sha))
    result = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)
    assert result["samples"][0]["machine_status"] == "BENCHMARK_CANDIDATE"
    assert result["summary"]["benchmark_approved_count"] == 0


def test_two_valid_fragile_reviews_require_revision_instead_of_more_votes(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    variant_id, packet_sha = _variant_and_packet(output)
    for idx in (1, 2):
        review = _review(
            f"reviewer-{idx}", verdict="FRAGILE", variant_id=variant_id,
            packet_sha256=packet_sha,
        )
        review["fatal_findings"] = [f"fatal finding {idx}"]
        _write_json(acceptance / "reviews" / "sample" / f"r{idx}.json", review)
    sample = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)["samples"][0]
    assert sample["machine_status"] == "REVISION_REQUIRED"
    assert sample["independent_review_outcome"]["revision_required"] is True
    assert sample["independent_review_outcome"]["fatal_finding_count"] == 2


def test_duplicate_reviewer_does_not_satisfy_independence(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    variant_id, packet_sha = _variant_and_packet(output)
    _write_json(acceptance / "reviews" / "sample" / "r1.json", _review("same", variant_id=variant_id, packet_sha256=packet_sha, context_id="context-1"))
    _write_json(acceptance / "reviews" / "sample" / "r2.json", _review("same", variant_id=variant_id, packet_sha256=packet_sha, context_id="context-2"))
    result = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)
    assert result["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"


def test_human_approved_fingerprinted_gold_contract_is_required(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    variant_id, packet_sha = _variant_and_packet(output)
    report_sha256 = _report_bundle_hash(find_report(output), None)  # type: ignore[arg-type]
    _write_json(acceptance / "reviews" / "sample" / "r1.json", _review("reviewer-1", variant_id=variant_id, packet_sha256=packet_sha))
    _write_json(acceptance / "reviews" / "sample" / "r2.json", _review("reviewer-2", "COMPETENT", variant_id, packet_sha))
    gold = {
        "schema_version": "gold-report-contract.v1", "sample_id": "sample",
        "variant_id": variant_id, "report_sha256": report_sha256,
        "company_code": "000001.SZ", "report_period": "FY2025", "information_cutoff": "2026-04-30",
        "decisive_questions": [{"id": "Q1"}], "competitive_explanations": [{"id": "ALT1"}],
        "required_evidence_ids": ["E1"], "valuation_roles": [{"model": "EPV"}],
        "decision_invariants": [{"metric": "valuation.v_final"}], "known_failure_modes": [],
        "review_ids": ["reviewer-1", "reviewer-2"],
        "human_approval": {"approved": True, "approved_by": "human", "approved_at": "2026-08-03"},
    }
    gold["fingerprint"] = _hash(gold)
    _write_json(acceptance / "gold_contracts" / "sample.json", gold)
    result = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)
    assert result["samples"][0]["machine_status"] == "BENCHMARK_APPROVED"


def test_independent_review_rejects_non_blind_or_thin_review() -> None:
    review = _review("reviewer")
    review["independence"]["variant_label_blinded"] = False
    review["dimensions"]["causal_depth"]["basis"] = "太短"
    validation = validate_independent_review(review, "sample")
    assert validation["status"] == "INVALID"
    assert "independence:variant_label_blinded" in validation["invalid_findings"]


def test_review_is_bound_to_exact_blind_packet_and_disjoint_from_generator() -> None:
    review = _review(
        "reviewer", packet_sha256="a" * 64,
        provider="deepseek_oa", model="deepseek-v4-pro",
    )
    validation = validate_independent_review(
        review, "sample", expected_packet_sha256="b" * 64,
        known_generator_identities={"deepseek_oa:deepseek-v4-pro"},
    )
    assert validation["status"] == "INVALID"
    assert "reviewed_packet_sha256_mismatch" in validation["invalid_findings"]
    assert "reviewer_generator_identity_overlap" in validation["invalid_findings"]


def test_review_rejects_structured_fatal_finding_when_schema_requires_strings() -> None:
    review = _review("reviewer")
    review["fatal_findings"] = [{"finding": "不能用结构对象绕过字符串契约"}]
    validation = validate_independent_review(review, "sample")
    assert validation["status"] == "INVALID"
    assert "fatal_findings_item_invalid" in validation["invalid_findings"]


def test_distinct_reviewer_names_cannot_reuse_same_review_context(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    variant_id, packet_sha = _variant_and_packet(output)
    _write_json(
        acceptance / "reviews" / "sample" / "r1.json",
        _review("reviewer-1", variant_id=variant_id, packet_sha256=packet_sha, context_id="shared-context"),
    )
    _write_json(
        acceptance / "reviews" / "sample" / "r2.json",
        _review("reviewer-2", variant_id=variant_id, packet_sha256=packet_sha, context_id="shared-context"),
    )
    sample = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)["samples"][0]
    assert sample["machine_status"] == "READY_FOR_BLIND_REVIEW"
    assert sample["independent_reviews"][1]["duplicate_reviewer"] is True


def test_persisted_blind_packet_hides_candidate_path_and_version_metadata(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    report = _report(output); _pass_gates(output)
    report.write_text("> 生成版本 run_id=secret-path\n\n正文\n", encoding="utf-8")
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    result = evaluate_acceptance(config, acceptance_root=acceptance, persist=True)
    variant = result["samples"][0]["variant_id"]
    packet = (acceptance / "blind_packets" / f"{variant}.md").read_text(encoding="utf-8")
    assert str(output) not in packet
    assert "run_id=secret-path" not in packet
    assert "正文" in packet


def test_blocked_candidate_never_gets_blind_review_packet(tmp_path: Path) -> None:
    output = tmp_path / "blocked"
    _report(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    evaluate_acceptance(config, acceptance_root=acceptance, persist=True)
    index = json.loads((acceptance / "blind_packets" / "blind_packet_index.json").read_text(encoding="utf-8"))
    assert index["packets"] == []
    assert list((acceptance / "blind_packets").glob("*.review_template.json")) == []


def test_review_for_prior_report_variant_is_invalidated(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    _write_json(
        acceptance / "reviews" / "sample" / "stale.json",
        _review("reviewer", variant_id="old-report-hash"),
    )
    sample = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)["samples"][0]
    assert sample["independent_reviews"][0]["validation"]["status"] == "INVALID"
    assert "variant_id_mismatch" in sample["independent_reviews"][0]["validation"]["invalid_findings"]


def test_held_out_control_result_is_not_evaluated_before_rules_freeze(tmp_path: Path) -> None:
    visible = tmp_path / "visible"; control = tmp_path / "control"
    _report(visible); _report(control)
    config_path = _config(tmp_path / "config.json", visible)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["policy"]["rules_frozen"] = False
    config["samples"].append({
        "sample_id": "control", "company_code": "000002.SZ", "archetype": "control",
        "role": "held_out_control", "output_dir": str(control), "report_period": "FY2025",
        "rules_visible": False,
    })
    _write_json(config_path, config)
    result = evaluate_acceptance(config_path, acceptance_root=tmp_path / "acceptance", persist=False)
    assert [item["sample_id"] for item in result["samples"]] == ["sample"]
    assert result["summary"]["held_out_count"] == 1


def test_gold_contract_cannot_reuse_reviews_from_old_variant(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    _report(output); _pass_gates(output)
    config = _config(tmp_path / "config.json", output)
    acceptance = tmp_path / "acceptance"
    _write_json(acceptance / "reviews" / "sample" / "r1.json", _review("reviewer-1", variant_id="stale"))
    _write_json(acceptance / "reviews" / "sample" / "r2.json", _review("reviewer-2", variant_id="stale"))
    result = evaluate_acceptance(config, acceptance_root=acceptance, persist=False)
    assert result["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"


def test_gold_approval_requires_current_candidate_and_exact_preview_fingerprint() -> None:
    reviews = [
        {
            "reviewer_id": reviewer,
            "duplicate_reviewer": False,
            "fatal_findings": [],
            "validation": {"status": "VALID"},
        }
        for reviewer in ("reviewer-1", "reviewer-2")
    ]
    acceptance = {"samples": [{
        "sample_id": "sample", "machine_status": "BENCHMARK_CANDIDATE",
        "variant_id": "a" * 16, "report_sha256": "b" * 64,
        "independent_reviews": reviews,
    }]}
    draft = {
        "company_code": "000001.SZ", "report_period": "FY2025",
        "information_cutoff": "2026-04-30",
        "decisive_questions": [{"id": "Q1"}],
        "competitive_explanations": [{"id": "ALT1"}],
        "required_evidence_ids": ["E1"], "valuation_roles": [{"model": "EPV"}],
        "decision_invariants": [{"metric": "valuation.v_final"}],
        "known_failure_modes": [],
    }
    preview = build_approval_preview(acceptance, draft, "sample")
    import pytest
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        approve_preview(preview, confirm_fingerprint="wrong", approved_by="human")
    contract = approve_preview(
        preview, confirm_fingerprint=preview["approval_fingerprint"], approved_by="human"
    )
    assert contract["human_approval"]["approved"] is True
    assert contract["variant_id"] == "a" * 16
    assert contract["review_ids"] == ["reviewer-1", "reviewer-2"]


def test_gold_approval_rejects_machine_blocked_candidate() -> None:
    import pytest
    with pytest.raises(ValueError, match="BENCHMARK_CANDIDATE"):
        build_approval_preview(
            {"samples": [{"sample_id": "sample", "machine_status": "TECHNICALLY_BLOCKED"}]},
            {}, "sample",
        )


def test_candidate_seed_copies_inputs_but_never_prior_conclusions(tmp_path: Path) -> None:
    source = tmp_path / "source"; source.mkdir()
    _write_json(source / "analysis_contract.json", {"ts_code": "000001.SZ"})
    _write_json(source / "compute_bundle.json", {"factor3": {}})
    (source / "2025_年报.md").write_text("filing", encoding="utf-8")
    (source / "completion_report.json").write_text("{}", encoding="utf-8")
    (source / "decision_ledger.json").write_text("{}", encoding="utf-8")
    (source / "reports").mkdir()
    (source / "reports" / "最新年报_分析报告_v13.md").write_text("old conclusion", encoding="utf-8")
    target = tmp_path / "target"
    manifest = seed_candidate(source, target)
    names = {item["name"] for item in manifest["files"]}
    assert {"analysis_contract.json", "compute_bundle.json", "2025_年报.md"}.issubset(names)
    assert not (target / "completion_report.json").exists()
    assert not (target / "decision_ledger.json").exists()
    assert not (target / "reports").exists()


def test_candidate_seed_refuses_to_overwrite_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "source"; source.mkdir()
    _write_json(source / "analysis_contract.json", {})
    _write_json(source / "compute_bundle.json", {})
    target = tmp_path / "target"; target.mkdir()
    (target / "user.txt").write_text("keep", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="never overwritten"):
        seed_candidate(source, target)
    assert (target / "user.txt").read_text(encoding="utf-8") == "keep"
