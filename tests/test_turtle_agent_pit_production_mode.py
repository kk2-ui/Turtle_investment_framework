from __future__ import annotations

from turtle_agent.agent_loop import AgentConfig, TurtleAgent
from turtle_agent.llm_client import LlmResponse, ToolCall
from turtle_agent.tool_registry import ToolRegistry


class ProductionLlm:
    model = "test-pit-production"

    def __init__(self) -> None:
        self.task_type = ""
        self.schemas: list[set[str]] = []
        self.responses = [LlmResponse(tool_calls=[ToolCall(
            id="assemble", name="pit_assemble_report", arguments={"company_name": "Test issuer"},
        )])]

    def set_runtime_task(self, task_type: str) -> None:
        self.task_type = task_type

    def chat(self, messages: list[dict[str, object]], **kwargs: object) -> LlmResponse:
        self.schemas.append({item["function"]["name"] for item in kwargs["tools"]})
        return self.responses.pop(0)


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
