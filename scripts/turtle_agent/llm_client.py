"""LLM API 客户端封装。

统一 Anthropic / OpenAI 调用接口，处理工具调用、流式输出、token 计数。

Usage::

    from turtle_agent.llm_client import LlmClient

    client = LlmClient(provider="anthropic")
    resp = client.chat(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[...],  # Anthropic tool schemas
    )
    if resp.has_tool_calls:
        for tc in resp.tool_calls:
            ...
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """单次工具调用。

    Args:
        id: 工具调用唯一 ID。
        name: 工具名称。
        arguments: 工具参数 dict。
    """

    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LlmResponse:
    """LLM 响应。

    Args:
        content: 文本内容（无工具调用时）。
        tool_calls: 工具调用列表。
        finish_reason: 完成原因 (stop/tool_calls/length)。
        usage: token 用量 {input, output}。
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        """是否包含工具调用。"""
        return len(self.tool_calls) > 0

    @property
    def is_text_only(self) -> bool:
        """是否为纯文本响应（无工具调用）。"""
        return self.finish_reason == "stop" and not self.tool_calls


class LlmClient:
    """LLM API 客户端。

    支持 Anthropic Messages API 和 OpenAI Chat Completions API。
    自动从环境变量读取 API key。

    Args:
        provider: LLM provider (``"anthropic"`` | ``"openai"``)。
        model: 模型 ID（默认 ``claude-sonnet-4-20250514``）。
        api_key: API key（默认从环境变量读取）。
        max_retries: 最大重试次数。
    """

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
    ) -> None:
        if provider not in ("anthropic", "openai", "deepseek", "deepseek_oa"):
            raise ValueError(f"不支持的 provider: {provider}，可选 anthropic/openai/deepseek/deepseek_oa")

        self._provider: str = provider
        self._max_retries: int = max_retries

        if provider in ("anthropic", "deepseek"):
            import anthropic

            key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
            url = base_url or os.environ.get("ANTHROPIC_BASE_URL") or None
            if not key:
                raise ValueError(
                    "需要 API key。设置 ANTHROPIC_API_KEY 环境变量或传入 api_key 参数。"
                )

            client_kwargs: dict[str, Any] = {"api_key": key}
            if url:
                client_kwargs["base_url"] = url
            elif provider == "deepseek":
                client_kwargs["base_url"] = "https://api.deepseek.com/anthropic"
            self._client: Any = anthropic.Anthropic(**client_kwargs)
            self._model: str = (
                model
                or os.environ.get("ANTHROPIC_MODEL")
                or ("deepseek-v4-pro[1m]" if provider == "deepseek" else "claude-sonnet-4-20250514")
            )
        elif provider == "deepseek_oa":
            # DeepSeek OpenAI 兼容 API，用 httpx 直调，不依赖 openai SDK
            key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
            if not key:
                raise ValueError("需要 DEEPSEEK_API_KEY")
            self._provider = "deepseek_oa"
            self._api_key = key
            self._base_url = base_url or "https://api.deepseek.com/chat/completions"
            self._model = model or "deepseek-chat"
            self._client = None  # 不用 SDK
        else:
            import openai

            key = api_key or os.environ.get("OPENAI_API_KEY") or ""
            url = base_url or os.environ.get("OPENAI_BASE_URL") or None
            if not key:
                raise ValueError(
                    "需要 OpenAI API key。"
                    "设置 OPENAI_API_KEY 环境变量或传入 api_key 参数。"
                )

            client_kwargs: dict[str, Any] = {"api_key": key}
            if url:
                client_kwargs["base_url"] = url
            self._client: Any = openai.OpenAI(**client_kwargs)
            self._model: str = model or "gpt-4o"

    @property
    def model(self) -> str:
        """当前使用的模型 ID。"""
        return self._model

    def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        max_retries: int = 2,
        replay_on_empty: bool = True,
    ) -> LlmResponse:
        """带 replay 的 chat — 来自 Dayu scene_executor 的 retry/replay 模式。

        业务错误（API 失败）→ 重发同 prompt。
        解析失败（空输出）→ 追加修复消息到上下文 → replay → 最大 1 次 replay/attempt。

        与 Dayu 的区别：同步（无 asyncio），无 Host 依赖。
        """
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                resp = self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)

                # 空输出检测 → 触发 replay
                if replay_on_empty and (not resp.content or len(resp.content.strip()) < 50):
                    if attempt < max_retries:
                        messages.append({"role": "assistant", "content": resp.content or ""})
                        messages.append({
                            "role": "user",
                            "content": "上一轮输出无法解析或内容过短，请直接基于已有上下文按要求格式输出完整结果，不要再调用工具。",
                        })
                        continue

                return resp
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"LLM 调用失败（重试{max_retries}次，含replay）: {last_error}")

    # ------------------------------------------------------------------
    # chat — 主要调用接口
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> LlmResponse:
        """发送消息到 LLM 并返回统一响应。

        Args:
            messages: 消息列表，每项含 ``role`` / ``content``。
            tools: 工具 schema 列表（OpenAI/Anthropic 格式）。
            temperature: 采样温度。
            max_tokens: 最大输出 token。

        Returns:
            ``LlmResponse`` 对象。

        Raises:
            RuntimeError: API 调用失败（重试后仍失败）。
        """
        if self._provider == "deepseek_oa":
            return self._chat_deepseek_oa(messages, tools, temperature, max_tokens)
        if self._provider in ("anthropic", "deepseek"):
            return self._chat_anthropic(messages, tools, temperature, max_tokens)
        return self._chat_openai(messages, tools, temperature, max_tokens)

    def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> LlmResponse:
        """Anthropic Messages API 调用。"""
        # 分离 system 消息
        system_parts: list[str] = []
        user_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                user_messages.append(msg)

        system_text = "\n\n".join(system_parts) if system_parts else None

        # 转换 tools 为 Anthropic 格式
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            kwargs["system"] = system_text
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.messages.create(**kwargs)
                return self._parse_anthropic_response(resp)
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Anthropic API 调用失败（重试{self._max_retries}次）: {last_error}")

    def _chat_deepseek_oa(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> LlmResponse:
        """DeepSeek OpenAI 兼容 API — httpx 直调。

        自动将 Anthropic 格式消息（tool_use/tool_result content blocks）
        转换为 OpenAI 格式（assistant tool_calls / tool role）。
        """
        import httpx

        oa_messages = _convert_messages_to_openai(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": oa_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=600.0) as client:
                    resp = client.post(self._base_url, json=payload, headers=headers)
                    if resp.status_code >= 400:
                        detail = resp.text[:1000]
                        raise RuntimeError(f"HTTP {resp.status_code}: {detail}")
                    data = resp.json()
                return self._parse_openai_response_raw(data)
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"DeepSeek API 调用失败（重试{self._max_retries}次）: {last_error}")

    def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> LlmResponse:
        """OpenAI Chat Completions API 调用。"""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                return self._parse_openai_response(resp)
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"OpenAI API 调用失败（重试{self._max_retries}次）: {last_error}")

    # ------------------------------------------------------------------
    # 响应解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_anthropic_response(resp: Any) -> LlmResponse:
        """解析 Anthropic 响应为 LlmResponse。"""
        content_text = ""
        tool_calls: list[ToolCall] = []
        finish_reason = "stop"
        usage: dict[str, int] = {}

        for block in resp.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )

        if resp.stop_reason == "tool_use":
            finish_reason = "tool_calls"

        if hasattr(resp, "usage"):
            usage = {
                "input": getattr(resp.usage, "input_tokens", 0),
                "output": getattr(resp.usage, "output_tokens", 0),
            }

        return LlmResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    @staticmethod
    def _parse_openai_response_raw(data: dict[str, Any]) -> LlmResponse:
        """解析 OpenAI 兼容 API 的原始 JSON 响应。"""
        choice = data["choices"][0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop") or "stop"

        content_text = message.get("content") or ""
        tool_calls: list[ToolCall] = []
        if message.get("tool_calls"):
            finish_reason = "tool_calls"
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = {}
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                ))

        usage: dict[str, int] = {}
        if "usage" in data:
            u = data["usage"]
            usage = {
                "input": u.get("prompt_tokens", 0),
                "output": u.get("completion_tokens", 0),
            }

        return LlmResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    @staticmethod
    def _parse_openai_response(resp: Any) -> LlmResponse:
        """解析 OpenAI 响应为 LlmResponse。"""
        choice = resp.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason or "stop"

        tool_calls: list[ToolCall] = []
        content_text = message.content or ""

        if message.tool_calls:
            finish_reason = "tool_calls"
            for tc in message.tool_calls:
                args = {}
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    pass
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage: dict[str, int] = {}
        if hasattr(resp, "usage") and resp.usage:
            usage = {
                "input": resp.usage.prompt_tokens or 0,
                "output": resp.usage.completion_tokens or 0,
            }

        return LlmResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )


# ------------------------------------------------------------------
# Anthropic → OpenAI 消息格式转换
# ------------------------------------------------------------------


def _convert_messages_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 Anthropic content blocks 转换为 OpenAI tool_calls/tool role 格式。"""
    result: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            result.append(msg)
            continue

        if isinstance(content, str):
            result.append(msg)
            continue

        if isinstance(content, list):
            text_parts = []
            tool_calls = []
            tool_results = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                        },
                    })
                elif btype == "tool_result":
                    tc = block.get("content", "")
                    if isinstance(tc, (list, dict)):
                        tc = json.dumps(tc, ensure_ascii=False)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(tc),
                    })

            if tool_calls:
                am = {"role": "assistant"}
                if text_parts:
                    am["content"] = "\n".join(text_parts)
                am["tool_calls"] = tool_calls
                result.append(am)

            result.extend(tool_results)

            if not tool_calls and not tool_results and text_parts:
                result.append({"role": role, "content": "\n".join(text_parts)})
            continue

        result.append(msg)

    return result
