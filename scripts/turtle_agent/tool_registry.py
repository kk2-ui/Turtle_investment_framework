"""工具注册与调度系统。

借鉴 Dayu 的 ``@tool`` 装饰器模式：
- 通过装饰器注册工具，自动生成 JSON Schema。
- 工具执行返回统一信封 ``{"ok": bool, "value": ...}``。

Usage::

    from turtle_agent.tool_registry import ToolRegistry, tool

    registry = ToolRegistry()

    @tool(registry, name="search_report", description="搜索年报关键词",
          parameters={"query": {"type": "string", "description": "搜索词"}})
    def search_report(query: str) -> dict:
        ...

    # 执行
    result = registry.execute("search_report", {"query": "revenue growth"})
    # → {"ok": True, "value": {...}}
"""

from __future__ import annotations

import traceback
from typing import Any, Callable


class ToolRegistry:
    """工具注册与调度中心。

    管理工具的生命周期：注册 → Schema 生成 → 执行。
    """

    def __init__(self) -> None:
        self._tools: dict[str, _ToolDescriptor] = {}

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """注册一个工具。

        Args:
            name: 工具名称（唯一标识）。
            func: 工具函数。
            description: 工具描述（注入 LLM prompt）。
            parameters: JSON Schema properties dict。

        Raises:
            ValueError: 工具名重复时抛出。
        """
        if name in self._tools:
            raise ValueError(f"工具 {name!r} 已注册")
        schema = _build_schema(name, description, parameters or {})
        self._tools[name] = _ToolDescriptor(
            name=name,
            func=func,
            description=description,
            schema=schema,
        )

    # ------------------------------------------------------------------
    # Schema 生成
    # ------------------------------------------------------------------

    def get_schemas(self) -> list[dict[str, Any]]:
        """获取所有已注册工具的 OpenAI/Anthropic tool schema 列表。

        Returns:
            工具 schema 列表，每项为 OpenAI function-calling 格式。
        """
        return [t.schema for t in self._tools.values()]

    def get_anthropic_schemas(self) -> list[dict[str, Any]]:
        """获取 Anthropic 格式的工具 schema。

        Returns:
            Anthropic tool_use 格式的 schema 列表。
        """
        result: list[dict[str, Any]] = []
        for t in self._tools.values():
            anthropic_schema = {
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": t.schema["function"]["parameters"].get(
                        "properties", {}
                    ),
                    "required": t.schema["function"]["parameters"].get(
                        "required", []
                    ),
                },
            }
            result.append(anthropic_schema)
        return result

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行工具并返回统一信封。

        所有工具调用都返回 ``{"ok": bool, "value": Any}`` 或
        ``{"ok": bool, "error": str}``，**永不抛异常**。

        Args:
            name: 工具名称。
            arguments: 工具参数字典。

        Returns:
            执行结果信封。
        """
        descriptor = self._tools.get(name)
        if descriptor is None:
            return {"ok": False, "error": f"未找到工具 {name!r}"}

        try:
            result = descriptor.func(**arguments)
            return {"ok": True, "value": result}
        except Exception as exc:
            tb = traceback.format_exc()
            return {
                "ok": False,
                "error": str(exc),
                "traceback": tb,
            }

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_tools(self) -> list[str]:
        """列出所有已注册工具名称。"""
        return sorted(self._tools.keys())

    def auto_discover(self, module_name: str) -> int:
        """扫描模块中所有被 ``@tool`` 装饰的函数并自动注册。

        Args:
            module_name: 模块导入路径（如 ``"turtle_agent.tools.read_tools"``）。

        Returns:
            新注册的工具数量。
        """
        import importlib

        mod = importlib.import_module(module_name)
        count = 0
        seen: set[str] = set()
        for attr_name in sorted(dir(mod)):
            obj = getattr(mod, attr_name)
            if not callable(obj):
                continue
            meta = getattr(obj, "_tool_meta", None)
            if meta is None:
                continue
            name = meta["name"]
            if name in self._tools or name in seen:
                continue
            seen.add(name)
            self.register(
                name=name,
                func=obj,
                description=meta.get("description", ""),
                parameters=meta.get("parameters", {}),
            )
            count += 1
        return count

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ---------------------------------------------------------------------------
# 内部类型
# ---------------------------------------------------------------------------


class _ToolDescriptor:
    """工具内部描述符。"""

    __slots__ = ("name", "func", "description", "schema")

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        schema: dict[str, Any],
    ) -> None:
        self.name = name
        self.func = func
        self.description = description
        self.schema = schema


# ---------------------------------------------------------------------------
# Schema 构建
# ---------------------------------------------------------------------------


def _build_schema(
    name: str, description: str, properties: dict[str, Any]
) -> dict[str, Any]:
    """构建 OpenAI function-calling 格式的工具 schema。

    Args:
        name: 工具名称。
        description: 工具描述。
        properties: JSON Schema properties dict。

    Returns:
        OpenAI tool schema dict。
    """
    required = [
        k for k, v in properties.items() if not v.get("optional", False)
    ]
    clean_properties = {
        k: {kk: vv for kk, vv in v.items() if kk != "optional"}
        for k, v in properties.items()
    }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": clean_properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# @tool 装饰器（便捷注册）
# ---------------------------------------------------------------------------


def tool(
    registry: ToolRegistry,
    *,
    name: str,
    description: str = "",
    parameters: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：将函数注册为工具。

    用法::

        @tool(registry, name="my_tool", description="...",
              parameters={"x": {"type": "integer", "description": "..."}})
        def my_tool(x: int) -> dict:
            ...

    Args:
        registry: ToolRegistry 实例。
        name: 工具名称。
        description: 工具描述。
        parameters: JSON Schema properties dict。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # 存储元数据到函数对象（供 auto_discover 使用）
        func._tool_meta = {  # type: ignore[attr-defined]
            "name": name,
            "description": description,
            "parameters": parameters or {},
        }
        return func

    return decorator
