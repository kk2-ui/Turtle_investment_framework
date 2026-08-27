from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.turtle_agent import run as run_module
from scripts.financial_driver_bridge import (
    evaluate_output_financial_driver_bridge,
    initialize_financial_driver_bridge_policy,
    persist_financial_driver_bridge,
)
from scripts.thesis_test_gate import (
    evaluate_output_thesis_test,
    initialize_thesis_test_policy,
    thesis_test_fingerprint,
)
from tests.test_financial_driver_bridge import _payload as _valid_bridge_payload
from tests.test_financial_driver_bridge import _prepare as _prepare_bridge_dependencies
from tests.test_stage14_thesis_test_gate import _no_probability_company_judgment_payload
from turtle_agent.agent_loop import AgentConfig, TurtleAgent
from turtle_agent.llm_client import LlmResponse, ToolCall
from turtle_agent.tool_registry import ToolRegistry


class ProductionLlm:
    model = "test-pit-production"

    def __init__(self) -> None:
        self.task_type = ""
        self.schemas: list[set[str]] = []
        self.messages: list[list[dict[str, object]]] = []
        self.responses = [LlmResponse(tool_calls=[ToolCall(
            id="assemble", name="pit_assemble_report", arguments={"company_name": "Test issuer"},
        )])]

    def set_runtime_task(self, task_type: str) -> None:
        self.task_type = task_type

    def chat(self, messages: list[dict[str, object]], **kwargs: object) -> LlmResponse:
        self.messages.append(messages)
        self.schemas.append({item["function"]["name"] for item in kwargs["tools"]})
        return self.responses.pop(0)


class BoundCjoLlm(ProductionLlm):
    def __init__(self) -> None:
        super().__init__()
        self.responses = [
            LlmResponse(tool_calls=[ToolCall(
                id="contract", name="pit_read_report_contract_pack", arguments={},
            )]),
            LlmResponse(tool_calls=[ToolCall(
                id="handoff", name="pit_read_judgment_generation_handoff",
                arguments={"view": "JUDGMENT_SYNTHESIS"},
            )]),
            LlmResponse(tool_calls=[ToolCall(
                id="assemble", name="pit_assemble_report", arguments={"company_name": "ignored"},
            )]),
        ]


class BoundNormalCjoLlm(BoundCjoLlm):
    def __init__(self) -> None:
        super().__init__()
        self.responses = [
            LlmResponse(tool_calls=[ToolCall(
                id="contract", name="read_report_contract_pack", arguments={},
            )]),
            LlmResponse(tool_calls=[ToolCall(
                id="handoff", name="read_judgment_generation_handoff",
                arguments={"view": "JUDGMENT_SYNTHESIS"},
            )]),
            LlmResponse(tool_calls=[ToolCall(
                id="assemble", name="assemble_report", arguments={"company_name": "ignored"},
            )]),
        ]


def test_pit_production_agent_uses_only_bound_tools_and_ends_at_assembly() -> None:
    tools = ToolRegistry()
    allowed = TurtleAgent._pit_production_allowed_tools()
    for name in sorted(allowed):
        if name == "pit_assemble_report":
            tools.register(name, lambda company_name="": {"path": "output/pit-report.md"})
        else:
            tools.register(name, lambda: {"ok": True})
    llm = ProductionLlm()

    report_path = TurtleAgent(
        llm=llm,
        tools=tools,
        config=AgentConfig(
            code="600340.SH",
            pit_production_mode=True,
            pit_case_id="HBTCASE:600340:20200427",
            pit_experiment_id="HBT:600340:20200427",
            pit_cutoff_at="2020-04-27T18:00:00+08:00",
        ),
    ).analyze()

    assert report_path == "output/pit-report.md"
    assert llm.task_type == "pit_production_freeze"
    assert llm.schemas == [allowed]
    assert "判断优先宪法" in str(llm.messages[0][0]["content"])
    assert "未披露与非决定性 proxy 不是经营冲突或负面证据" in str(llm.messages[0][0]["content"])


def test_pit_production_registry_discovers_exactly_the_bound_toolset() -> None:
    tools = ToolRegistry()
    tools.auto_discover("turtle_agent.tools.pit_read_tools")
    tools.auto_discover("turtle_agent.tools.pit_production_write_tools")

    assert set(tools.list_tools()) == TurtleAgent._pit_production_allowed_tools()


def test_bound_frozen_cjo_uses_compact_prompt_and_exact_tool_trace(tmp_path: Path) -> None:
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "canonical_judgment_refs": {"frozen_cjo_ref": "canonical/frozen_cjo.json"},
    }), encoding="utf-8")
    tools = ToolRegistry()
    called: list[str] = []
    full = TurtleAgent._pit_production_allowed_tools("COMPANY_JUDGMENT_ONLY")
    for name in sorted(full):
        def handler(_name: str = name, **kwargs: object) -> dict[str, object]:
            called.append(_name)
            if _name == "pit_assemble_report":
                return {"path": "output/company-judgment-research.md"}
            if _name == "pit_read_judgment_generation_handoff":
                return {"readiness": {"state": "READY"}}
            return {"ok": True}
        tools.register(name, handler)
    llm = BoundCjoLlm()

    result = TurtleAgent(
        llm=llm,
        tools=tools,
        config=AgentConfig(
            code="600340.SH", output_dir=str(tmp_path),
            analysis_purpose="COMPANY_JUDGMENT_ONLY",
            pit_production_mode=True,
            pit_case_id="HBTCASE:600340:20200427",
            pit_experiment_id="HBT:600340:20200427",
            pit_cutoff_at="2020-04-27T18:00:00+08:00",
        ),
    ).analyze()

    compact = {
        "pit_read_report_contract_pack",
        "pit_read_judgment_generation_handoff",
        "pit_assemble_report",
    }
    assert result == "output/company-judgment-research.md"
    assert llm.schemas == [compact, compact, compact]
    assert called == [
        "pit_read_report_contract_pack",
        "pit_read_judgment_generation_handoff",
        "pit_assemble_report",
    ]
    prompt = str(llm.messages[0][0]["content"])
    assert "只允许依次调用" in prompt
    assert "15章" not in prompt
    assert "compute_ddm" not in prompt
    assert "估值模型" not in prompt


def test_normal_bound_frozen_cjo_prompt_never_builds_full_report_context(tmp_path: Path) -> None:
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "canonical_judgment_refs": {"frozen_cjo_ref": "canonical/frozen_cjo.json"},
    }), encoding="utf-8")
    tools = ToolRegistry()
    compact = {
        "read_report_contract_pack",
        "read_judgment_generation_handoff",
        "assemble_report",
    }
    for name in sorted(compact):
        tools.register(name, lambda **kwargs: {"ok": True})
    agent = TurtleAgent(
        llm=None, tools=tools,
        config=AgentConfig(
            code="600340.SH", output_dir=str(tmp_path),
            analysis_purpose="COMPANY_JUDGMENT_ONLY",
        ),
    )

    prompt = agent._build_system_prompt()
    offered = {
        item["function"]["name"] for item in agent._tool_schemas_for_stage()
    }

    assert offered == compact
    assert "只能依次调用" in prompt
    for forbidden in ("15章", "compute_ddm", "reader coverage", "模板合约", "估值模型"):
        assert forbidden not in prompt


def test_normal_bound_frozen_cjo_actual_prompt_and_trace_are_compact(tmp_path: Path) -> None:
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "canonical_judgment_refs": {"frozen_cjo_ref": "canonical/frozen_cjo.json"},
    }), encoding="utf-8")
    tools = ToolRegistry()
    called: list[str] = []
    compact = {
        "read_report_contract_pack",
        "read_judgment_generation_handoff",
        "assemble_report",
    }
    for name in sorted(compact):
        def handler(_name: str = name, **kwargs: object) -> dict[str, object]:
            called.append(_name)
            if _name == "assemble_report":
                return {"path": "output/company-judgment-research.md"}
            if _name == "read_judgment_generation_handoff":
                return {"readiness": {"state": "READY"}}
            return {"ok": True}
        tools.register(name, handler)
    llm = BoundNormalCjoLlm()

    result = TurtleAgent(
        llm=llm, tools=tools,
        config=AgentConfig(
            code="600340.SH", output_dir=str(tmp_path),
            analysis_purpose="COMPANY_JUDGMENT_ONLY", publish_downstream=False,
        ),
    ).analyze()

    assert result == "output/company-judgment-research.md"
    assert llm.schemas == [compact, compact, compact]
    assert called == [
        "read_report_contract_pack", "read_judgment_generation_handoff", "assemble_report",
    ]
    system = str(llm.messages[0][0]["content"])
    user = str(llm.messages[0][1]["content"])
    assert "只能依次调用" in system
    assert "读取 report contract，再读取当前 JUDGMENT_SYNTHESIS" in user
    for forbidden in ("15章", "compute_ddm", "reader coverage", "模板合约", "估值模型"):
        assert forbidden not in system + user


PIT_ARGS = {
    "pit_source_manifest": "source-manifest.json",
    "pit_package_root": "source-package",
    "pit_case_id": "HBTCASE:600340:20200427",
    "pit_experiment_id": "HBT:600340:20200427",
    "pit_production_freeze": True,
}


def _company_judgment_snapshot(tmp_path: Path, code: str = "600340.SH") -> Path:
    predecessor = tmp_path / "company-judgment"
    predecessor.mkdir()
    thesis = {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "freeze": {"frozen": True},
        "central_path": {"path_id": "CJO:path.core", "statement": "经营中心路径"},
        "forward_judgments": [{"judgment_id": "FJ:CJO:operating"}],
        "mechanism_chains": [{"chain_id": "MC:CJO:operating"}],
    }
    thesis_path = predecessor / "thesis_test.json"
    thesis_path.write_text(json.dumps(thesis), encoding="utf-8")
    digest = hashlib.sha256(thesis_path.read_bytes()).hexdigest()
    (predecessor / "analysis_contract.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "ts_code": code,
    }), encoding="utf-8")
    snapshot = predecessor / "publication_snapshot.json"
    snapshot.write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "report_id": code,
        "data_as_of": "2020-04-27", "v3_enforced": True,
        "completion_status": "COMPLETE", "snapshot_fingerprint": "cjo-freeze",
        "ledger_sha256": {"thesis_test": digest},
    }), encoding="utf-8")
    return snapshot


def _cjo_report(*, central_path: bool = True) -> str:
    central = "[central-path: path.core] " if central_path else ""
    return "\n\n".join([
        "## Ch0 公司判断\n" + central,
        "## Ch9 风险\n[thesis-test: test.core] [threshold: th.reduce] [threshold: th.exit]",
        "## Ch13 监测\n[threshold: th.buy]",
        "## Ch14 结论\n" + central + "[thesis-test: test.core]",
    ])


def _complete_company_judgment_snapshot(tmp_path: Path, code: str = "600340.SH") -> Path:
    predecessor = tmp_path / "complete-company-judgment"
    predecessor.mkdir()
    _prepare_bridge_dependencies(predecessor)
    thesis = _no_probability_company_judgment_payload(
        predecessor, selection_status="SELECTION_ADMITTED",
    )
    thesis["report_id"] = code
    thesis["as_of"] = "2026-08-02"
    thesis["freeze"]["fingerprint"] = thesis_test_fingerprint(thesis)
    thesis_path = predecessor / "thesis_test.json"
    thesis_path.write_text(json.dumps(thesis, ensure_ascii=False), encoding="utf-8")
    report_text = _cjo_report()
    report_path = predecessor / "reports" / "cjo.md"
    report_path.parent.mkdir()
    report_path.write_text(report_text, encoding="utf-8")
    (predecessor / "analysis_contract.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "ts_code": code,
        "company_id": code, "data_as_of": "2026-08-02",
    }), encoding="utf-8")
    initialize_thesis_test_policy(
        predecessor, run_id="cjo-run", enforced=True, monitoring_required=True,
        forward_judgment_required=True, rival_hypothesis_pair_required=True,
    )
    thesis_validation = evaluate_output_thesis_test(
        predecessor, report_text=report_text, persist=True,
    )
    assert thesis_validation["state"] == "DECISION_READY"
    bridge = _valid_bridge_payload(predecessor, analysis_purpose="COMPANY_JUDGMENT_ONLY")
    bridge["report_id"] = code
    bridge["as_of"] = "2026-08-02"
    judgment_by_driver = {
        "FDBDRV:demand": "fj.retention",
        "FDBDRV:margin": "fj.retention",
        "FDBDRV:cash": "fj.owner_cash",
        "FDBDRV:allocation": "fj.value",
    }
    for driver in bridge["drivers"]:
        driver.pop("model_bindings", None)
        driver["monitoring_contract"]["forward_judgment_ids"] = [
            judgment_by_driver[driver["driver_id"]]
        ]
    for event in bridge["allocation_events"]:
        judgment_id = "fj.value"
        realization = event["realization_contract"]
        realization["forward_judgment_ids"] = [judgment_id]
        realization["early_signal"]["forward_judgment_ids"] = [judgment_id]
        realization["terminal_outcome"]["forward_judgment_ids"] = [judgment_id]
    initialize_financial_driver_bridge_policy(predecessor, run_id="cjo-run", enforced=True)
    bridge_result = persist_financial_driver_bridge(predecessor, bridge)
    assert bridge_result["validation"]["state"] == "REVIEWABLE"
    bridge_validation = evaluate_output_financial_driver_bridge(predecessor, persist=True)
    assert bridge_validation["state"] == "REVIEWABLE"
    bridge_path = predecessor / "financial_driver_bridge.json"
    snapshot = predecessor / "publication_snapshot.json"
    snapshot.write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "report_id": code,
        "data_as_of": "2026-08-02", "v3_enforced": True,
        "completion_status": "COMPLETE", "snapshot_fingerprint": "complete-cjo-freeze",
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "ledger_sha256": {
            "thesis_test": hashlib.sha256(thesis_path.read_bytes()).hexdigest(),
            "financial_driver_bridge": hashlib.sha256(bridge_path.read_bytes()).hexdigest(),
        },
        "gate_states": {
            "thesis_test": "DECISION_READY",
            "financial_driver_bridge": "REVIEWABLE",
        },
    }), encoding="utf-8")
    return snapshot


def test_investment_pit_predecessor_requires_same_cutoff_frozen_cjo(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="company-judgment-snapshot"):
        run_module._load_company_judgment_predecessor(
            "", company_code="600340.SH", cutoff_at="2020-04-27T18:00:00+08:00",
        )
    snapshot = _company_judgment_snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="predecessor_thesis_schema_invalid"):
        run_module._load_company_judgment_predecessor(
            str(snapshot), company_code="600340.SH", cutoff_at="2020-04-27T18:00:00+08:00",
        )
    with pytest.raises(RuntimeError, match="predecessor_cutoff_mismatch"):
        run_module._load_company_judgment_predecessor(
            str(snapshot), company_code="600340.SH", cutoff_at="2020-04-28T18:00:00+08:00",
        )


def test_complete_company_judgment_predecessor_carries_the_full_g1j_identity(tmp_path: Path) -> None:
    predecessor = run_module._load_company_judgment_predecessor(
        str(_complete_company_judgment_snapshot(tmp_path)),
        company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
    )

    assert predecessor["identity"] == {"status": "G1J_COMPLETE", "missing_components": []}
    assert predecessor["source"]["thesis_freeze_fingerprint"]
    assert predecessor["source"]["financial_driver_bridge_validation_state"] == "REVIEWABLE"
    assert predecessor["rival_hypothesis_pairs"][0]["pair_id"] == "RHP:retention-vs-erosion"
    assert predecessor["analogy_transfer_cards"][0]["card_id"] == "ATC:retention-vs-erosion"
    assert predecessor["selection_admission"]["status"] == "SELECTION_ADMITTED"
    assert predecessor["financial_driver_bridge"]["drivers"][0]["driver_id"] == "FDBDRV:demand"


def test_declared_company_judgment_bridge_hash_mismatch_is_not_downgraded(tmp_path: Path) -> None:
    snapshot = _complete_company_judgment_snapshot(tmp_path)
    bridge_path = snapshot.parent / "financial_driver_bridge.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge["drivers"][0]["statement"] = "冻结后被改写"
    bridge_path.write_text(json.dumps(bridge, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="predecessor_financial_driver_bridge_hash_mismatch"):
        run_module._load_company_judgment_predecessor(
            str(snapshot), company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
        )


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ({"report_id": "000651.SZ"}, "predecessor_financial_driver_bridge_report_id_mismatch"),
        ({"as_of": "2026-08-03"}, "predecessor_financial_driver_bridge_cutoff_mismatch"),
    ],
)
def test_complete_predecessor_rejects_bridge_company_or_cutoff_mismatch(
    tmp_path: Path, mutation: dict[str, str], finding: str,
) -> None:
    snapshot = _complete_company_judgment_snapshot(tmp_path)
    bridge_path = snapshot.parent / "financial_driver_bridge.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge.update(mutation)
    bridge_path.write_text(json.dumps(bridge, ensure_ascii=False), encoding="utf-8")
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    snapshot_payload["ledger_sha256"]["financial_driver_bridge"] = hashlib.sha256(
        bridge_path.read_bytes()
    ).hexdigest()
    snapshot.write_text(json.dumps(snapshot_payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match=finding):
        run_module._load_company_judgment_predecessor(
            str(snapshot), company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
        )


def test_complete_predecessor_rejects_legacy_generic_policy_state(tmp_path: Path) -> None:
    snapshot = _complete_company_judgment_snapshot(tmp_path)
    policy_path = snapshot.parent / "thesis_test_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["schema_version"] = "thesis-test-policy.v1"
    policy.pop("forward_judgment_required")
    policy.pop("rival_hypothesis_pair_required")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(RuntimeError, match="predecessor_thesis_policy_not_current_g1j"):
        run_module._load_company_judgment_predecessor(
            str(snapshot), company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
        )


def test_investment_initialization_rejects_injected_legacy_predecessor(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="company_judgment_predecessor_not_g1j_complete"):
        run_module._initialize_pit_production_output(
            output_dir=str(tmp_path / "investment"), code="600340.SH", run_id="run",
            cutoff_at="2020-04-27T18:00:00+08:00", analysis_purpose="INVESTMENT_DECISION",
            company_judgment_predecessor={
                "schema_version": "company-judgment-predecessor.v2",
                "identity": {"status": "LEGACY_PARTIAL", "missing_components": ["financial_driver_bridge"]},
            },
        )


def test_complete_no_primary_cjo_is_valid_but_not_investment_ready(tmp_path: Path) -> None:
    snapshot = _complete_company_judgment_snapshot(tmp_path)
    root = snapshot.parent
    thesis_path = root / "thesis_test.json"
    thesis = _no_probability_company_judgment_payload(root, selection_status="NO_PRIMARY")
    thesis["report_id"] = "600340.SH"
    thesis["as_of"] = "2026-08-02"
    thesis["freeze"]["fingerprint"] = thesis_test_fingerprint(thesis)
    thesis_path.write_text(json.dumps(thesis, ensure_ascii=False), encoding="utf-8")
    no_primary_report = _cjo_report(central_path=False)
    report_path = root / "reports" / "cjo.md"
    report_path.write_text(no_primary_report, encoding="utf-8")
    validation = evaluate_output_thesis_test(
        root, report_text=no_primary_report, persist=True,
    )
    assert validation["state"] == "DECISION_READY"
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    snapshot_payload["ledger_sha256"]["thesis_test"] = hashlib.sha256(thesis_path.read_bytes()).hexdigest()
    snapshot_payload["report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    snapshot.write_text(json.dumps(snapshot_payload), encoding="utf-8")

    predecessor = run_module._load_company_judgment_predecessor(
        str(snapshot), company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
    )
    assert predecessor["identity"]["status"] == "G1J_COMPLETE"
    assert predecessor["central_path"] == {}
    assert predecessor["selection_admission"]["status"] == "NO_PRIMARY"
    with pytest.raises(RuntimeError, match="company_judgment_predecessor_not_investment_ready_selection"):
        run_module._initialize_pit_production_output(
            output_dir=str(tmp_path / "investment"), code="600340.SH", run_id="run",
            cutoff_at="2026-08-02T18:00:00+08:00", analysis_purpose="INVESTMENT_DECISION",
            company_judgment_predecessor=predecessor,
        )


def test_investment_pit_initialization_freezes_company_judgment_lineage(tmp_path: Path) -> None:
    snapshot = _complete_company_judgment_snapshot(tmp_path)
    predecessor = run_module._load_company_judgment_predecessor(
        str(snapshot), company_code="600340.SH", cutoff_at="2026-08-02T18:00:00+08:00",
    )
    output = tmp_path / "investment"
    run_module._initialize_pit_production_output(
        output_dir=str(output), code="600340.SH", run_id="run", cutoff_at="2026-08-02T18:00:00+08:00",
        analysis_purpose="INVESTMENT_DECISION", company_judgment_predecessor=predecessor,
    )

    contract = json.loads((output / "analysis_contract.json").read_text(encoding="utf-8"))
    policy = json.loads((output / "thesis_test_policy.json").read_text(encoding="utf-8"))
    frozen_predecessor = json.loads((output / "company_judgment_predecessor.json").read_text(encoding="utf-8"))
    assert contract["company_judgment_predecessor"]["central_path_id"] == "path.core"
    assert contract["company_judgment_predecessor"]["completeness_status"] == "G1J_COMPLETE"
    assert contract["company_judgment_predecessor"]["rival_hypothesis_pair_ids"] == ["RHP:retention-vs-erosion"]
    assert contract["company_judgment_predecessor"]["analogy_transfer_card_ids"] == ["ATC:retention-vs-erosion"]
    assert contract["company_judgment_predecessor"]["selection_admission_status"] == "SELECTION_ADMITTED"
    assert contract["company_judgment_predecessor"]["financial_driver_bridge_sha256"]
    assert policy["company_judgment_lineage_required"] is True
    assert frozen_predecessor["source"]["snapshot_fingerprint"] == "complete-cjo-freeze"


@pytest.mark.parametrize(
    "blocked_kwargs",
    [
        {"validation_only": True},
        {"dry_run": True},
        {"unified": True},
        {"qualitative_only": True},
        {"data_source": "600340.SH"},
        {"price_source": "600340.SH"},
        {"source_deepening": False},
    ],
)
def test_pit_production_freeze_rejects_validation_and_ordinary_modes(
    tmp_path: Path, blocked_kwargs: dict[str, object],
) -> None:
    with pytest.raises(RuntimeError, match="PIT运行禁止普通报告"):
        run_module.run_full_pipeline(
            "600340.SH",
            output_dir=str(tmp_path / "output"),
            **PIT_ARGS,
            **blocked_kwargs,
        )


@pytest.mark.parametrize(
    ("acceptance_status", "should_publish"),
    [
        ("READY_FOR_BLIND_REVIEW", True),
        ("REVISION_REQUIRED", False),
    ],
)
def test_pit_production_freeze_uses_one_run_id_and_only_publishes_after_ready_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acceptance_status: str, should_publish: bool,
) -> None:
    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(json.dumps({"company_code": "600340.SH"}), encoding="utf-8")
    package_root = tmp_path / "source-package"
    package_root.mkdir()
    output = tmp_path / "output"
    cjo_snapshot = _complete_company_judgment_snapshot(tmp_path)
    observed: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, manifest: dict, package: str, **kwargs: object) -> None:
            observed["runner_manifest"] = manifest
            observed["runner_package"] = package
            observed["runner_kwargs"] = kwargs
            self.state = "REVIEWABLE"
            self.invalid_findings: list[str] = []
            self.incomplete_findings: list[str] = []
            self.run_id = str(kwargs["run_id"])
            self.cutoff_at = "2026-08-02T18:00:00+08:00"

    class FakeRuntimeManifest:
        def __init__(self, path: Path) -> None:
            self.path = path
            self.artifacts: list[tuple[str, str]] = []
            self.finalized: tuple[str, dict] | None = None

        def add_artifact(self, path: str, kind: str) -> None:
            self.artifacts.append((path, kind))

        def record_step(self, *args: object, **kwargs: object) -> None:
            return None

        def add_error(self, *args: object, **kwargs: object) -> None:
            return None

        def finalize(self, status: str, *, publication: dict) -> None:
            self.finalized = (status, publication)

    class FakeRuntime:
        def __init__(self, **kwargs: object) -> None:
            observed["runtime_kwargs"] = kwargs
            self.manifest = FakeRuntimeManifest(Path(str(kwargs["output_dir"])) / "run_manifest.json")
            observed["runtime"] = self

    def fake_production_freeze(**kwargs: object) -> str:
        observed["production_kwargs"] = kwargs
        report_path = Path(str(kwargs["output_dir"])) / "report.md"
        report_path.write_text("# PIT production report\n", encoding="utf-8")
        return str(report_path)

    def unexpected_normal_phase(*args: object, **kwargs: object) -> dict:
        raise AssertionError("normal report phase must not execute in PIT production mode")

    import scripts.phase10_pit_runner as pit_runner_module
    import scripts.real_report_acceptance as real_report_acceptance
    import scripts.runtime_governance as runtime_governance

    monkeypatch.setattr(pit_runner_module, "PITSourcePackage", FakeRunner)
    monkeypatch.setattr(runtime_governance, "RuntimeController", FakeRuntime)
    monkeypatch.setattr(run_module, "_run_pit_production_freeze", fake_production_freeze)
    monkeypatch.setattr(
        run_module,
        "_validate_pit_production_completion",
        lambda **kwargs: {
            "completion_status": "COMPLETE",
            "report_path": str(kwargs["report_path"]),
            "publication_snapshot_path": str(Path(str(kwargs["output_dir"])) / "publication_snapshot.json"),
            "pit_attestation_path": str(Path(str(kwargs["output_dir"])) / "pit_runner_attestation.json"),
        },
    )
    monkeypatch.setattr(
        real_report_acceptance,
        "evaluate_phase10_production_freeze_acceptance",
        lambda **kwargs: {"samples": [{"machine_status": acceptance_status}]},
    )
    monkeypatch.setattr(run_module, "_run_phase", unexpected_normal_phase)

    if should_publish:
        report_path = run_module.run_full_pipeline(
            "600340.SH",
            output_dir=str(output),
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package_root),
            pit_case_id="HBTCASE:600340:20200427",
            pit_experiment_id="HBT:600340:20200427",
            pit_production_freeze=True,
            company_judgment_snapshot=str(cjo_snapshot),
        )
    else:
        with pytest.raises(RuntimeError, match="not ready at the independent Phase 10 acceptance gate"):
            run_module.run_full_pipeline(
                "600340.SH",
                output_dir=str(output),
                pit_source_manifest=str(manifest_path),
                pit_package_root=str(package_root),
                pit_case_id="HBTCASE:600340:20200427",
                pit_experiment_id="HBT:600340:20200427",
                pit_production_freeze=True,
                company_judgment_snapshot=str(cjo_snapshot),
            )
        report_path = str(output / "report.md")

    runner_kwargs = observed["runner_kwargs"]
    runtime_kwargs = observed["runtime_kwargs"]
    production_kwargs = observed["production_kwargs"]
    assert isinstance(runner_kwargs, dict)
    assert isinstance(runtime_kwargs, dict)
    assert isinstance(production_kwargs, dict)
    run_id = runner_kwargs["run_id"]
    assert run_id == runtime_kwargs["run_id"]
    assert production_kwargs["pit_runner"].run_id == run_id
    assert production_kwargs["runtime"] is observed["runtime"]
    assert (
        production_kwargs["company_judgment_predecessor"]["source"]["snapshot_fingerprint"]
        == "complete-cjo-freeze"
    )
    assert report_path == str(output / "report.md")
    runtime = observed["runtime"]
    assert isinstance(runtime, FakeRuntime)
    assert runtime.manifest.artifacts[0] == (report_path, "pit_production_report")
    assert runtime.manifest.finalized == (
        ("COMPLETED", {"status": "PUBLISHED", "validation_only": False})
        if should_publish else ("BLOCKED", {"status": "NOT_PUBLISHED", "validation_only": False})
    )
