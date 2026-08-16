"""Point-in-time read tools bound to a :class:`PITSourcePackage`.

These tools are deliberately separate from ``read_tools``.  They do not
accept an output directory or filesystem path: the caller can name only an
admitted ``source_id`` or an explicitly registered framework-relative path.
The runner owns cutoff validation and records both successful and denied
reads in its audit.
"""

from __future__ import annotations

import base64
from typing import Any

from scripts.phase10_pit_runner import PITRunnerError, PITSourcePackage


_RUNNER: PITSourcePackage | None = None


def configure_pit_runner(runner: PITSourcePackage | None) -> None:
    """Bind the read tools to one runner for the lifetime of one run."""
    global _RUNNER
    _RUNNER = runner


def clear_pit_runner() -> None:
    """Drop the process-local binding between runs and tests."""
    configure_pit_runner(None)


def _not_configured() -> dict[str, Any]:
    return {"ok": False, "error": "pit_runner_not_configured"}


def _text_payload(raw: bytes, *, identity: dict[str, Any], max_chars: int, start_char: int) -> dict[str, Any]:
    """Return UTF-8 text when possible, preserving binary sources as base64."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        safe_limit = max(500, min(int(max_chars or 30000), 100000))
        encoded = base64.b64encode(raw).decode("ascii")
        safe_start = max(0, int(start_char or 0))
        chunk = encoded[safe_start:safe_start + safe_limit]
        next_cursor = safe_start + len(chunk)
        return {
            "ok": True,
            **identity,
            "encoding": "base64",
            "content": chunk,
            "char_count": len(chunk),
            "original_char_count": len(encoded),
            "start_char": safe_start,
            "end_char": next_cursor,
            "truncated": next_cursor < len(encoded),
            "next_cursor": next_cursor if next_cursor < len(encoded) else None,
        }
    safe_start = max(0, int(start_char or 0))
    safe_limit = max(500, min(int(max_chars or 30000), 100000))
    content = text[safe_start:safe_start + safe_limit]
    next_cursor = safe_start + len(content)
    return {
        "ok": True,
        **identity,
        "encoding": "utf-8",
        "content": content,
        "char_count": len(content),
        "original_char_count": len(text),
        "start_char": safe_start,
        "end_char": next_cursor,
        "truncated": next_cursor < len(text),
        "next_cursor": next_cursor if next_cursor < len(text) else None,
    }


def _source_identity(source_id: str) -> dict[str, Any]:
    if _RUNNER is None:
        return {"source_id": source_id}
    for item in _RUNNER.attestation().get("source_allowlist", []):
        if isinstance(item, dict) and item.get("source_id") == source_id:
            return {
                "source_id": source_id,
                "source_version": item.get("source_version"),
                "published_at": item.get("published_at"),
                "data_as_of": item.get("data_as_of"),
                "admission_status": item.get("admission_status"),
            }
    return {"source_id": source_id, "admission_status": "REJECTED"}


def pit_list_sources() -> dict[str, Any]:
    """List the admitted source identities without reading file contents."""
    if _RUNNER is None:
        return _not_configured()
    attestation = _RUNNER.attestation()
    return {
        "ok": _RUNNER.state == "REVIEWABLE",
        "state": _RUNNER.state,
        "cutoff_at": attestation.get("cutoff_at"),
        "company_code": attestation.get("company_code"),
        "sources": attestation.get("source_allowlist", []),
        "invalid_findings": _RUNNER.invalid_findings,
        "incomplete_findings": _RUNNER.incomplete_findings,
    }


def pit_read_source(
    source_id: str = "",
    max_chars: int = 30000,
    start_char: int = 0,
) -> dict[str, Any]:
    """Read an admitted source by identity; no path or URL is accepted."""
    if _RUNNER is None:
        return _not_configured()
    identity = _source_identity(str(source_id or "").strip())
    try:
        raw = _RUNNER.read_source(str(source_id or "").strip())
    except (PITRunnerError, OSError, ValueError) as exc:
        return {"ok": False, **identity, "error": str(exc)}
    return _text_payload(raw, identity=identity, max_chars=max_chars, start_char=start_char)


def pit_read_framework(
    path: str = "",
    max_chars: int = 30000,
    start_char: int = 0,
) -> dict[str, Any]:
    """Read an explicitly allowlisted framework-relative path."""
    if _RUNNER is None:
        return _not_configured()
    relative = str(path or "").strip()
    try:
        raw = _RUNNER.read_framework(relative)
    except (PITRunnerError, OSError, ValueError) as exc:
        return {"ok": False, "path": relative, "error": str(exc)}
    return _text_payload(raw, identity={"path": relative, "kind": "FRAMEWORK"}, max_chars=max_chars, start_char=start_char)


pit_list_sources._tool_meta = {
    "name": "pit_list_sources",
    "description": "列出当前PIT冻结时点已准入来源身份；不读取任意文件",
    "parameters": {},
}  # type: ignore[attr-defined]
pit_read_source._tool_meta = {
    "name": "pit_read_source",
    "description": "按已准入source_id读取冻结历史来源；禁止路径、URL和未注册来源",
    "parameters": {
        "source_id": {"type": "string", "description": "已准入来源身份"},
        "max_chars": {"type": "integer", "description": "UTF-8文本最大字符数", "optional": True},
        "start_char": {"type": "integer", "description": "续读起始位置", "optional": True},
    },
}  # type: ignore[attr-defined]
pit_read_framework._tool_meta = {
    "name": "pit_read_framework",
    "description": "按已注册相对路径读取PIT框架文件；禁止任意路径和当前输出",
    "parameters": {
        "path": {"type": "string", "description": "framework allowlist中的相对路径"},
        "max_chars": {"type": "integer", "description": "UTF-8文本最大字符数", "optional": True},
        "start_char": {"type": "integer", "description": "续读起始位置", "optional": True},
    },
}  # type: ignore[attr-defined]
