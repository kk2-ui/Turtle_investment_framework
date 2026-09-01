from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.report_autonomy_bridge import (
    compile_component_reader_bridge,
    validate_component_reader_anchors,
    validate_component_reader_bridge,
)
from scripts.report_completion import _evaluate_component_reader_bridge
from scripts.turtle_agent.tools.write_tools import (
    write_enterprise_underwriting_component_reader_bridge,
)
from scripts.turtle_agent.tools.read_tools import read_report_contract_pack
from scripts.judgment_generation_handoff import build_judgment_generation_handoff
from scripts.turtle_agent import run as run_module
from tests.test_enterprise_underwriting_episode import _episode_with_derivation
from tests.test_turtle_agent_pit_production_mode import (
    _episode_bound_current_company_artifacts,
)


def test_component_reader_bridge_is_exact_episode_derivation_without_control_ids() -> None:
    episode = _episode_with_derivation()
    bridge = compile_component_reader_bridge(
        episode, episode_ref="enterprise_underwriting_episode.json",
    )

    assert validate_component_reader_bridge(
        bridge, episode, episode_ref="enterprise_underwriting_episode.json",
    )["state"] == "REVIEWABLE"
    serialized = str(bridge)
    assert "NEB:CORE" not in serialized
    assert "DOMESTIC_CORE_NORMAL_EARNINGS" not in serialized
    assert bridge["component_anchors"]
    assert {item["heading"] for item in bridge["economic_section_anchors"]} == {
        "正常盈利组件桥", "关键敏感性与翻转条件",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bridge: bridge["component_anchors"].pop(),
        lambda bridge: bridge["economic_section_anchors"].pop(),
        lambda bridge: bridge["identity"].update(company_id="CN:OTHER"),
    ],
)
def test_component_reader_bridge_rejects_omission_or_rewrite(mutate) -> None:
    episode = _episode_with_derivation()
    bridge = compile_component_reader_bridge(
        episode, episode_ref="enterprise_underwriting_episode.json",
    )
    mutate(bridge)

    validation = validate_component_reader_bridge(
        bridge, episode, episode_ref="enterprise_underwriting_episode.json",
    )

    assert validation["state"] == "INVALID"
    assert "not_exact_episode_derivation" in validation["findings"]


def test_component_reader_anchor_validator_requires_existing_writer_to_retain_every_anchor() -> None:
    episode = _episode_with_derivation()
    bridge = compile_component_reader_bridge(
        episode, episode_ref="enterprise_underwriting_episode.json",
    )
    text = "\n\n".join(
        item["text"]
        for field in ("component_anchors", "economic_section_anchors")
        for item in bridge[field]
    )

    assert validate_component_reader_anchors(
        bridge, technical_text=text, reader_text=text,
    )["state"] == "PASS"
    assert validate_component_reader_anchors(
        bridge, technical_text=text, reader_text=text.replace(bridge["component_anchors"][0]["text"], ""),
    )["state"] == "BLOCKED"


def test_completion_contract_blocks_a_bound_bridge_when_existing_writer_omits_an_anchor(tmp_path) -> None:
    episode = _episode_with_derivation()
    episode_path = tmp_path / "episode.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    bridge = compile_component_reader_bridge(episode, episode_ref=str(episode_path))
    bridge_path = tmp_path / "component_bridge.json"
    bridge_path.write_text(json.dumps(bridge, ensure_ascii=False), encoding="utf-8")
    text = "\n\n".join(
        item["text"]
        for field in ("component_anchors", "economic_section_anchors")
        for item in bridge[field]
    )
    refs = {
        "enterprise_underwriting_component_reader_bridge_ref": str(bridge_path),
        "company_id": episode["company_id"],
        "cutoff_at": episode["cutoff_at"],
    }

    assert _evaluate_component_reader_bridge(
        output_dir=str(tmp_path), refs=refs, technical_text=text, reader_text=text,
    )["state"] == "DECISION_READY"
    assert _evaluate_component_reader_bridge(
        output_dir=str(tmp_path), refs=refs, technical_text=text,
        reader_text=text.replace(bridge["economic_section_anchors"][0]["text"], ""),
    )["state"] == "INVALID"


def test_writer_tool_binds_only_same_company_same_cutoff_episode_to_report_contract(tmp_path) -> None:
    episode = _episode_with_derivation()
    episode_path = tmp_path / "episode.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "company_id": episode["company_id"],
        "data_as_of": episode["cutoff_at"],
        "analysis_purpose": "INVESTMENT_DECISION",
    }), encoding="utf-8")

    result = write_enterprise_underwriting_component_reader_bridge(
        str(tmp_path), str(episode_path),
    )

    assert result["ok"] is True
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    assert contract["canonical_judgment_refs"] == {
        "enterprise_underwriting_component_reader_bridge_ref": (
            "enterprise_underwriting_component_reader_bridge.json"
        ),
    }


def test_first_contract_pack_delivers_a_successfully_bound_component_bridge(tmp_path) -> None:
    episode = _episode_with_derivation()
    episode_path = tmp_path / "episode.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "company_id": episode["company_id"],
        "data_as_of": episode["cutoff_at"],
        "analysis_purpose": "INVESTMENT_DECISION",
    }), encoding="utf-8")

    assert write_enterprise_underwriting_component_reader_bridge(
        str(tmp_path), "episode.json",
    )["ok"] is True

    contract_pack = read_report_contract_pack(str(tmp_path))

    assert contract_pack["ok"] is True
    bridge = contract_pack["judgment_generation_handoff"][
        "writer_underwriting_handoff"
    ]["enterprise_underwriting_component_reader_bridge"]
    assert bridge["state"] == "READY"
    assert bridge["bridge"]["identity"]["episode_id"] == episode["episode_id"]


def test_component_bridge_must_match_the_frozen_cjo_and_admission_episode_identity(tmp_path) -> None:
    frozen_path, admission_path, frozen_bundle = _episode_bound_current_company_artifacts(
        tmp_path,
    )
    projection = frozen_bundle["frozen_cjo"]["underwriting_thesis_projection"]
    episode = _episode_with_derivation()
    episode["company_id"] = projection["company_id"]
    episode["cutoff_at"] = projection["cutoff_at"]
    episode["episode_id"] = projection["episode_id"]
    episode["underwriting_thesis"]["thesis_id"] = projection["underwriting_thesis_id"]
    episode_path = tmp_path / "same-episode.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "analysis_contract.json").write_text(json.dumps({
        "company_id": episode["company_id"],
        "data_as_of": episode["cutoff_at"],
        "analysis_purpose": "INVESTMENT_DECISION",
        "canonical_judgment_refs": {
            "frozen_cjo_ref": str(frozen_path),
            "current_company_cjo_admission_ref": str(admission_path),
        },
    }), encoding="utf-8")

    assert write_enterprise_underwriting_component_reader_bridge(
        str(tmp_path), episode_path.name,
    )["ok"] is True

    different_episode = deepcopy(episode)
    different_episode["episode_id"] = "EUE:COMPANY:SYNTHETIC:20260802:OTHER:V1"
    different_episode["underwriting_thesis"]["thesis_id"] = (
        "UWT:COMPANY:SYNTHETIC:20260802:OTHER:V1"
    )
    different_path = tmp_path / "different-episode.json"
    different_path.write_text(
        json.dumps(different_episode, ensure_ascii=False), encoding="utf-8",
    )

    rejected = write_enterprise_underwriting_component_reader_bridge(
        str(tmp_path), different_path.name,
    )

    assert rejected["ok"] is False
    assert "bridge_frozen_cjo_episode_id_mismatch" in rejected["error"]

    unbound_bridge = compile_component_reader_bridge(
        different_episode, episode_ref=str(different_path),
    )
    unbound_bridge_path = tmp_path / "manually-bound-different-episode.json"
    unbound_bridge_path.write_text(
        json.dumps(unbound_bridge, ensure_ascii=False), encoding="utf-8",
    )
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["canonical_judgment_refs"]["enterprise_underwriting_component_reader_bridge_ref"] = (
        str(unbound_bridge_path)
    )
    (tmp_path / "analysis_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8",
    )
    handoff = build_judgment_generation_handoff(tmp_path, "JUDGMENT_SYNTHESIS")
    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        "component_reader_bridge_cjo_binding:bridge_frozen_cjo_episode_id_mismatch"
        == finding
        for finding in handoff["readiness"]["invalid_findings"]
    )
    text = "\n".join(
        item["text"]
        for field in ("component_anchors", "economic_section_anchors")
        for item in unbound_bridge[field]
    )
    completion = _evaluate_component_reader_bridge(
        output_dir=str(tmp_path),
        refs={
            **contract["canonical_judgment_refs"],
            "company_id": episode["company_id"],
            "cutoff_at": episode["cutoff_at"],
        },
        technical_text=text,
        reader_text=text,
    )
    assert completion["state"] == "INVALID"
    assert (
        "component_reader_bridge_cjo_binding:bridge_frozen_cjo_episode_id_mismatch"
        in completion["findings"]
    )


def test_episode_bound_production_initialization_writes_bridge_before_writer_reads(tmp_path) -> None:
    episode = _episode_with_derivation()
    episode_path = tmp_path / "episode.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "production"
    run_module._initialize_pit_production_output(
        output_dir=str(output),
        code=episode["company_id"],
        run_id="RUN:COMPONENT-BRIDGE",
        cutoff_at=episode["cutoff_at"],
        analysis_purpose="INVESTMENT_DECISION",
        canonical_judgment_binding={
            "company_id": episode["company_id"],
            "frozen_cjo_path": "frozen_cjo.json",
            "current_company_cjo_admission_path": "current_company_admission.json",
            "enterprise_underwriting_episode_path": str(episode_path),
        },
    )

    contract = json.loads((output / "analysis_contract.json").read_text(encoding="utf-8"))
    bridge_ref = contract["canonical_judgment_refs"][
        "enterprise_underwriting_component_reader_bridge_ref"
    ]
    bridge = json.loads((output / bridge_ref).read_text(encoding="utf-8"))
    assert bridge["identity"]["episode_id"] == episode["episode_id"]
