from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.runtime_governance import (
    BudgetExhausted,
    CacheScope,
    ContentAddressedCache,
    CriticalTruncation,
    ModelTierViolation,
    RunManifest,
    RuntimeController,
    apply_retention_plan,
    audit_local_secret_boundaries,
    build_retention_plan,
    fingerprint,
    load_runtime_config,
    recovery_advice,
    redact_sensitive,
    validate_run_manifest,
    classify_error,
)
from scripts.turtle_agent.llm_client import LlmClient, LlmResponse


def _controller(tmp_path: Path, *, code: str = "01502.HK", period: str = "FY2025") -> RuntimeController:
    return RuntimeController(
        output_dir=tmp_path,
        run_id="RUN-TEST",
        company_code=code,
        period=period,
        mode="unified",
    )


def _fake_client(controller: RuntimeController, responses: list[object]) -> LlmClient:
    client = object.__new__(LlmClient)
    client._provider = "deepseek_oa"
    client._model = "deepseek-v4-pro"
    client._max_retries = 2
    client._timeout_seconds = 10
    client._runtime_controller = controller

    def call(*args, **kwargs):
        value = responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    client._chat_once = call  # type: ignore[method-assign]
    return client


def test_governance_config_declares_critical_routes_and_no_secret_values() -> None:
    config = load_runtime_config()
    assert config["schema_version"] == "runtime-governance.v1"
    assert config["task_profiles"]["deep_research"]["critical"] is True
    assert config["task_profiles"]["report_synthesis"]["minimum_tier"] == "frontier"
    assert not any("api_key" in key.lower() for key in config)


def test_critical_route_rejects_silent_model_downgrade(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.set_task("report_synthesis")
    with pytest.raises(ModelTierViolation):
        controller.validate_route("deepseek-chat")
    assert controller.manifest.data["errors"][0]["category"] == "model_tier_violation"


def test_macos_dns_resolution_failure_is_classified_as_connection() -> None:
    result = classify_error(OSError(8, "nodename nor servname provided, or not known"))
    assert result["category"] == "connection"


def test_critical_budget_pauses_instead_of_reducing_model_or_output(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.config["budget"]["max_output_tokens"] = 100
    with pytest.raises(BudgetExhausted):
        controller.prepare_call(
            model="deepseek-v4-pro", messages=[{"role": "user", "content": "research"}],
            tools=None, temperature=0.2, max_tokens=1000,
        )
    assert controller.manifest.data["errors"][-1]["category"] == "budget_exhausted"


def test_cache_is_exact_scoped_by_company_period_model_prompt_and_code(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path)
    base = CacheScope("01502.HK", "FY2025", "deep_research", "deepseek-v4-pro", "p1", "c1")
    assert cache.put(base, "request", {"content": "result"}, 3600)
    assert cache.get(base, "request")[0] == {"content": "result"}
    other_company = CacheScope("000651.SZ", "FY2025", "deep_research", "deepseek-v4-pro", "p1", "c1")
    other_period = CacheScope("01502.HK", "FY2024", "deep_research", "deepseek-v4-pro", "p1", "c1")
    assert cache.get(other_company, "request")[0] is None
    assert cache.get(other_period, "request")[0] is None


def test_cache_rejects_expiry_and_payload_corruption(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path)
    scope = CacheScope("01502.HK", "FY2025", "deep_research", "deepseek-v4-pro", "p1", "c1")
    assert cache.put(scope, "request", {"content": "result"}, 0)
    assert cache.get(scope, "request")[1] == "expired"
    assert cache.put(scope, "request2", {"content": "result"}, 3600)
    path = cache._path(cache.key(scope, "request2"))
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["payload"]["content"] = "tampered"
    path.write_text(json.dumps(entry), encoding="utf-8")
    assert cache.get(scope, "request2")[1] == "corrupt"


def test_llm_retry_is_categorized_and_manifested(monkeypatch, tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    response = LlmResponse(content="complete result", usage={"input": 12, "output": 4})
    client = _fake_client(controller, [TimeoutError("timed out"), response])
    monkeypatch.setattr("scripts.turtle_agent.llm_client.time.sleep", lambda _: None)
    result = client.chat([{"role": "user", "content": "x"}], max_tokens=100)
    assert result.content == "complete result"
    calls = controller.manifest.data["llm_calls"]
    assert [item["outcome"] for item in calls] == ["error", "success"]
    assert calls[0]["error_category"] == "timeout"
    assert controller.manifest.data["usage"]["calls"] == 2


def test_critical_truncation_fails_closed_and_is_not_cached(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    client = _fake_client(controller, [
        LlmResponse(content="partial", finish_reason="max_tokens", usage={"input": 5, "output": 100})
    ])
    with pytest.raises(CriticalTruncation):
        client.chat([{"role": "user", "content": "x"}], max_tokens=100)
    assert controller.manifest.data["cache"]["writes"] == 0
    assert any("critical_truncation_rejected" in item for item in controller.manifest.data["warnings"])


def test_exact_llm_cache_replays_without_second_provider_call(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    response = LlmResponse(content="stable", usage={"input": 8, "output": 2}, provider="fake")
    client = _fake_client(controller, [response])
    messages = [{"role": "user", "content": "same"}]
    assert client.chat(messages, max_tokens=100).content == "stable"
    assert client.chat(messages, max_tokens=100).content == "stable"
    assert controller.manifest.data["cache"]["hits"] == 1
    assert controller.manifest.data["usage"]["calls"] == 1


def test_manifest_cannot_turn_recorded_failure_into_success(tmp_path: Path) -> None:
    manifest = RunManifest(
        tmp_path / "manifest.json", run_id="r", company_code="c", period="p", mode="m",
        config=load_runtime_config(), input_fingerprints={"x": "a" * 64},
    )
    manifest.add_error("server_error", "failed")
    with pytest.raises(RuntimeError):
        manifest.finalize("COMPLETED")
    manifest.finalize("FAILED")
    saved = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    expected = dict(saved)
    recorded = expected.pop("manifest_fingerprint")
    assert recorded == fingerprint(expected)


def test_redaction_and_secret_boundary_audit_never_return_secret_value(tmp_path: Path) -> None:
    secret = "sk-super-private-value"
    (tmp_path / ".gitignore").write_text(".env\nanalyze.sh\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    (tmp_path / "analyze.sh").write_text("DEEPSEEK_KEYS=(\"local-array-kept\")\n", encoding="utf-8")
    (tmp_path / "run.log").write_text(f"Authorization: Bearer {secret}\n", encoding="utf-8")
    result = audit_local_secret_boundaries(tmp_path)
    serialized = json.dumps(result)
    assert result["status"] == "INVALID"
    assert result["leaks"] == [{"path": "run.log", "secret_label": ".env:ANTHROPIC_API_KEY"}]
    assert secret not in serialized
    assert secret not in json.dumps(redact_sensitive({"error": f"Bearer {secret}"}))


def test_retention_is_preview_first_and_moves_only_confirmed_candidates(tmp_path: Path) -> None:
    protected = tmp_path / "publication_snapshot.json"
    protected.write_text("{}", encoding="utf-8")
    stale = tmp_path / ".runtime_cache" / "aa" / "old.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
    import os
    os.utime(stale, (old, old))
    plan = build_retention_plan(tmp_path)
    assert protected.exists() and stale.exists()
    assert [item["path"] for item in plan["candidates"]] == [".runtime_cache/aa/old.json"]
    with pytest.raises(RuntimeError):
        apply_retention_plan(plan, confirm_fingerprint="wrong")
    applied = apply_retention_plan(plan, confirm_fingerprint=plan["plan_fingerprint"])
    assert protected.exists() and not stale.exists()
    assert Path(applied["trash"]).joinpath(".runtime_cache/aa/old.json").exists()


def test_dry_run_pipeline_cannot_overwrite_formal_outputs_or_publish(tmp_path: Path) -> None:
    from scripts.turtle_agent.run import run_full_pipeline

    reports = tmp_path / "reports"
    reports.mkdir()
    latest = reports / "最新_分析报告_v13.md"
    snapshot = tmp_path / "publication_snapshot.json"
    latest.write_text("existing formal report", encoding="utf-8")
    snapshot.write_text('{"snapshot": "existing"}', encoding="utf-8")

    report = run_full_pipeline(
        "01502.HK", output_dir=str(tmp_path), skip_prepare=True, dry_run=True,
        unified=True,
    )
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert Path(report).is_file()
    assert Path(report).name == "01502.HK_V12_DRY_RUN.md"
    assert latest.read_text(encoding="utf-8") == "existing formal report"
    assert snapshot.read_text(encoding="utf-8") == '{"snapshot": "existing"}'
    assert not (reports / "2025_年报_分析报告_v13.md").exists()
    assert manifest["status"] == "COMPLETED"
    assert manifest["publication"] == {
        "status": "NOT_PUBLISHED",
        "artifact_class": "DRY_RUN",
        "validation_only": False,
    }
    assert (tmp_path / "run_manifests" / f"{manifest['run_id']}.json").is_file()
    assert validate_run_manifest(manifest)["status"] == "PASS"
    assert recovery_advice(tmp_path)["action"] == "no_resume_needed"


def test_prompt_only_pipeline_cannot_overwrite_formal_outputs_or_publish(
    tmp_path: Path, monkeypatch,
) -> None:
    from scripts.turtle_agent.run import run_full_pipeline

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reports = tmp_path / "reports"
    reports.mkdir()
    latest = reports / "最新_分析报告_v13.md"
    snapshot = tmp_path / "publication_snapshot.json"
    latest.write_text("existing formal report", encoding="utf-8")
    snapshot.write_text('{"snapshot": "existing"}', encoding="utf-8")
    (tmp_path / "analysis_contract.json").write_text(
        json.dumps({"ts_code": "01502.HK", "company_name": "测试公司"}),
        encoding="utf-8",
    )
    (tmp_path / "compute_bundle.json").write_text("{}", encoding="utf-8")

    artifact = run_full_pipeline(
        "01502.HK", output_dir=str(tmp_path), skip_prepare=True,
    )

    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert Path(artifact).name == "_v11_system_prompt.md"
    assert latest.read_text(encoding="utf-8") == "existing formal report"
    assert snapshot.read_text(encoding="utf-8") == '{"snapshot": "existing"}'
    assert not (tmp_path / "analysis_contract.latest.json").exists()
    assert not (tmp_path / "compute_bundle.latest.json").exists()
    assert sorted(path.name for path in reports.iterdir()) == [latest.name]
    assert manifest["status"] == "COMPLETED"
    assert manifest["publication"] == {
        "status": "NOT_PUBLISHED",
        "artifact_class": "PROMPT_PACKAGE",
        "validation_only": False,
    }


def test_validation_only_is_a_draft_and_only_report_class_can_publish() -> None:
    from scripts.turtle_agent.run import (
        ArtifactClass,
        _publication_manifest,
        _resolve_artifact_class,
    )

    artifact_class = _resolve_artifact_class(
        dry_run=False, validation_only=True, llm_available=True,
    )
    assert artifact_class is ArtifactClass.DRAFT
    assert _publication_manifest(
        artifact_class, runtime_status="COMPLETED", validation_only=True,
    ) == {
        "status": "NOT_PUBLISHED",
        "artifact_class": "DRAFT",
        "validation_only": True,
    }
    assert _publication_manifest(
        ArtifactClass.REPORT, runtime_status="COMPLETED", validation_only=False,
    )["status"] == "PUBLISHED"
