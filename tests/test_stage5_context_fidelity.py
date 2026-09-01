from __future__ import annotations

import json
from pathlib import Path

from scripts.turtle_agent.agent_loop import (
    AgentConfig,
    TurtleAgent,
    _chapter_memory,
    _compact_template_index,
)
from scripts.turtle_agent.llm_client import LlmResponse, ToolCall
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.write_tools import _ensure_canonical_chapter_heading
from scripts.turtle_agent.tools.read_tools import read_section


class _DummyLlm:
    model = "dummy"


def test_compact_template_keeps_map_not_full_contract() -> None:
    template = """# report
## 投资要点概览
very long overview contract
## 公司做的是什么生意
very long business contract
"""

    compact = _compact_template_index(template)

    assert "Ch0" in compact and "Ch1" in compact
    assert "read_report_contract_pack" in compact
    assert "very long overview contract" not in compact


def test_chapter_memory_preserves_numeric_thesis_and_causal_reasoning() -> None:
    content = """## Ch3 商业模式机制、护城河与关键约束

### 结论要点

- 毛利率69.96%，因此楼宇网络仍有定价权。[source: segments.json]
- 客户集中度上升意味着议价风险需要跟踪。

### 详细情况

普通背景句不重要。
OCF达到72.09亿元，但治理折价导致估值不能机械上调。
"""

    memory = _chapter_memory(content, 3)

    assert "69.96%" in memory
    assert "客户集中度" in memory
    assert "72.09" in memory
    assert "治理折价" in memory


def test_write_requires_contract_when_real_contract_tool_is_registered(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register("read_report_contract_pack", lambda **kwargs: {"ok": True}, parameters={})
    registry.register(
        "write_chapter",
        lambda **kwargs: calls.append(kwargs) or {"chapter_index": kwargs["chapter_index"]},
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(_DummyLlm(), registry, AgentConfig(output_dir=str(tmp_path)))  # type: ignore[arg-type]

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="write",
        name="write_chapter",
        arguments={"chapter_index": 2, "content": "正文"},
    )]))

    assert calls == []
    result = json.loads(agent._messages[-1]["content"][0]["content"])
    assert result["value"]["contract_required"] is True


def test_duplicate_data_results_keep_only_latest_copy(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register("compute_gg", lambda **kwargs: {"payload": "数据" * 1000}, parameters={})
    agent = TurtleAgent(_DummyLlm(), registry, AgentConfig(output_dir=str(tmp_path)))  # type: ignore[arg-type]

    for call_id in ("one", "two"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id,
            name="compute_gg",
            arguments={},
        )]))

    first = agent._messages[1]["content"][0]["content"]
    second = agent._messages[3]["content"][0]["content"]
    assert "旧的重复工具结果已压缩" in first
    assert len(second) > 1000
    assert agent.run_metrics()["duplicate_result_chars_compacted"] > 1000


def test_failed_chapter_keeps_full_body_for_same_author_rewrite(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: {
            "chapter_index": kwargs["chapter_index"],
            "char_count": len(kwargs["content"]),
            "depth": {"status": "FAIL", "failures": ["substantive_chars"]},
            "audit": {"passed": False, "verdict": "regenerate"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(_DummyLlm(), registry, AgentConfig(output_dir=str(tmp_path)))  # type: ignore[arg-type]
    draft = "尚未通过但包含重要事实与推理。" * 200

    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="failed",
        name="write_chapter",
        arguments={"chapter_index": 6, "content": draft},
    )]))

    assert agent._messages[0]["content"][0]["input"]["content"] == draft
    assert agent.run_metrics()["context_chars_compacted"] == 0


def test_contract_pack_loads_all_targets_in_one_tool_call() -> None:
    registry = ToolRegistry()
    registry.auto_discover("scripts.turtle_agent.tools.read_tools")
    result = registry.execute("read_report_contract_pack", {
        "chapter_indexes": [1, 11, 14],
        "template_path": "templates/report_template_v12.md",
    })

    assert result["ok"] is True
    pack = result["value"]
    assert pack["ok"] is True
    assert set(pack["chapters"]) == {"1", "11", "14"}
    assert all(item["char_count"] > 1000 for item in pack["chapters"].values())


def test_passed_chapter_is_frozen_against_unneeded_rewrite(tmp_path: Path) -> None:
    calls: list[dict] = []
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: calls.append(kwargs) or {
            "chapter_index": kwargs["chapter_index"],
            "char_count": len(kwargs["content"]),
            "depth": {"status": "PASS", "failures": []},
            "audit": {"passed": True, "verdict": "pass"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(_DummyLlm(), registry, AgentConfig(output_dir=str(tmp_path)))  # type: ignore[arg-type]
    for call_id in ("first", "redundant"):
        agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
            id=call_id,
            name="write_chapter",
            arguments={"chapter_index": 3, "content": "完整章节" * 1000},
        )]))

    assert len(calls) == 1
    result = json.loads(agent._messages[-1]["content"][0]["content"])
    assert result["value"]["already_passed_this_pass"] is True


def test_chapter_heading_identity_is_deterministic() -> None:
    assert _ensure_canonical_chapter_heading("## 综合决策\n\n正文", 14).startswith("## Ch14 综合决策")
    assert _ensure_canonical_chapter_heading("正文没有标题", 0).startswith("## Ch0 投资要点概览")


def test_read_section_uses_real_markdown_heading_not_toc(tmp_path: Path) -> None:
    report = """# FY2025

## 第 3 页

目录
第三节 管理层讨论与分析........9

## 第 10 页

第三节 管理层讨论与分析
这里是真实经营回顾与渠道变化。

## 第 11 页

研发投入与竞争优势。
"""
    (tmp_path / "2025_年报.md").write_text(report, encoding="utf-8")

    result = read_section(str(tmp_path), 2025, "MDA", max_chars=5000)

    assert result["source_type"] == "annual_markdown"
    assert result["page_range"][0] == 10
    assert "真实经营回顾" in result["text"]
    assert "目录" not in result["text"]
