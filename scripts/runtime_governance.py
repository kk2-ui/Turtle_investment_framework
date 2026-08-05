#!/usr/bin/env python3
"""Fail-closed runtime governance for Turtle's automatic research pipeline.

The module deliberately stores fingerprints and operational metadata only.  It
never persists prompts, responses, request headers, API keys, or environment
values.  User-approved local secret files remain the secret source; this layer
only prevents those values from escaping into generated artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


CONFIG_SCHEMA_VERSION = "runtime-governance.v1"
MANIFEST_SCHEMA_VERSION = "run-manifest.v1"
CACHE_SCHEMA_VERSION = "runtime-cache-entry.v1"
RETENTION_SCHEMA_VERSION = "runtime-retention-plan.v1"
TERMINAL_STATUSES = {"PAUSED", "INCOMPLETE", "FAILED", "BLOCKED", "COMPLETED"}


class RuntimeGovernanceError(RuntimeError):
    """Base class for observable, categorized runtime failures."""

    category = "runtime_error"


class BudgetExhausted(RuntimeGovernanceError):
    category = "budget_exhausted"


class ModelTierViolation(RuntimeGovernanceError):
    category = "model_tier_violation"


class CriticalTruncation(RuntimeGovernanceError):
    category = "critical_truncation"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, prefix=path.name + "."
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _secret_values() -> list[str]:
    values: list[str] = []
    for name, value in os.environ.items():
        if re.search(r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|AUTH)", name, re.IGNORECASE):
            text = str(value or "")
            if len(text) >= 6:
                values.append(text)
    return sorted(set(values), key=len, reverse=True)


_REDACTION_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\]}]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[\"']?)[^\s\"',;\]}]+"),
    re.compile(r"(?i)([?&](?:api[_-]?key|token|secret)=)[^&\s]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def redact_text(value: Any, *, extra_secrets: list[str] | None = None) -> str:
    """Return safe text without revealing discovered secret values."""
    text = str(value or "")
    for secret in [*_secret_values(), *(extra_secrets or [])]:
        if secret:
            text = text.replace(secret, "<redacted>")
    for pattern in _REDACTION_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda match: match.group(1) + "<redacted>", text)
        else:
            text = pattern.sub("<redacted>", text)
    return text


def redact_sensitive(value: Any) -> Any:
    """Recursively redact values and remove intrinsically unsafe fields."""
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(?:api[_-]?key|authorization|password|secret)", str(key), re.IGNORECASE):
                safe[str(key)] = "<redacted>"
            else:
                safe[str(key)] = redact_sensitive(item)
        return safe
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def load_runtime_config(path: str | Path | None = None) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[1]
    config_path = Path(path) if path else repo / "config" / "runtime_governance.v1.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise RuntimeGovernanceError("runtime governance config schema mismatch")
    return payload


def classify_error(exc: BaseException) -> dict[str, Any]:
    """Classify without persisting provider response bodies or credentials."""
    text = redact_text(exc).lower()
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status == 429:
            category = "rate_limit"
        elif status >= 500:
            category = "server_error"
        elif status in {401, 403}:
            category = "authentication"
        else:
            category = "client_error"
    elif "429" in text or "rate limit" in text or "too many requests" in text:
        category = "rate_limit"
    elif "timeout" in text or "timed out" in text:
        category = "timeout"
    elif any(token in text for token in (
        "connection", "dns", "network", "temporarily unavailable",
        "nodename nor servname", "name or service not known", "failed to resolve",
    )):
        category = "connection"
    elif any(token in text for token in ("500", "502", "503", "504", "server error")):
        category = "server_error"
    elif "context" in text and any(token in text for token in ("window", "length", "too long")):
        category = "context_window"
    else:
        category = getattr(exc, "category", "unknown")
    return {"category": category, "message": redact_text(exc)[:500]}


def _code_version(repo: Path) -> str:
    try:
        value = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    except (OSError, subprocess.SubprocessError):
        pass
    files = [
        repo / "scripts" / "runtime_governance.py",
        repo / "scripts" / "turtle_agent" / "llm_client.py",
        repo / "scripts" / "turtle_agent" / "agent_loop.py",
        repo / "scripts" / "turtle_agent" / "run.py",
    ]
    return fingerprint({path.name: _file_hash(path) for path in files if path.is_file()})


def collect_input_fingerprints(output_dir: str | Path, template_path: str | Path = "") -> dict[str, str]:
    output = Path(output_dir)
    repo = Path(__file__).resolve().parents[1]
    candidates = {
        "analysis_contract": output / "analysis_contract.json",
        "compute_bundle": output / "compute_bundle.json",
        "document_manifest": output / "document_manifest.json",
        "report_context": output / "report_context.json",
        "runtime_config": repo / "config" / "runtime_governance.v1.json",
    }
    if template_path:
        template = Path(template_path)
        if not template.is_absolute():
            template = repo / template
        candidates["template"] = template
    return {name: _file_hash(path) for name, path in candidates.items() if path.is_file()}


@dataclass(frozen=True)
class CacheScope:
    company_code: str
    period: str
    task_type: str
    model: str
    prompt_version: str
    code_version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "company_code": self.company_code,
            "period": self.period,
            "task_type": self.task_type,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "code_version": self.code_version,
        }


class ContentAddressedCache:
    """Exact-match JSON cache with identity scope, TTL, integrity and locking."""

    def __init__(self, root: str | Path, max_entry_bytes: int = 8 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.max_entry_bytes = int(max_entry_bytes)

    @staticmethod
    def key(scope: CacheScope, request_fingerprint: str) -> str:
        return fingerprint({"scope": scope.to_dict(), "request_fingerprint": request_fingerprint})

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, scope: CacheScope, request_fingerprint: str) -> tuple[dict[str, Any] | None, str]:
        key = self.key(scope, request_fingerprint)
        path = self._path(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, "miss"
        except (OSError, json.JSONDecodeError):
            return None, "corrupt"
        expected_scope = scope.to_dict()
        if entry.get("schema_version") != CACHE_SCHEMA_VERSION or entry.get("cache_key") != key:
            return None, "invalid"
        if entry.get("scope") != expected_scope:
            return None, "scope_mismatch"
        try:
            expires = datetime.fromisoformat(str(entry["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            return None, "invalid"
        if expires <= datetime.now(timezone.utc):
            return None, "expired"
        payload = entry.get("payload")
        if entry.get("payload_hash") != fingerprint(payload):
            return None, "corrupt"
        return payload if isinstance(payload, dict) else None, "hit"

    def put(
        self, scope: CacheScope, request_fingerprint: str, payload: dict[str, Any], ttl_seconds: int
    ) -> bool:
        safe_payload = redact_sensitive(payload)
        if len(_canonical(safe_payload).encode("utf-8")) > self.max_entry_bytes:
            return False
        key = self.key(scope, request_fingerprint)
        created = datetime.now(timezone.utc).replace(microsecond=0)
        entry = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": key,
            "scope": scope.to_dict(),
            "created_at": created.isoformat(),
            "expires_at": (created + timedelta(seconds=max(0, int(ttl_seconds)))).isoformat(),
            "payload_hash": fingerprint(safe_payload),
            "payload": safe_payload,
        }
        _atomic_json(self._path(key), entry)
        return True


class RunManifest:
    """Atomic, replay-oriented manifest.  A failed run cannot become successful."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        company_code: str,
        period: str,
        mode: str,
        config: dict[str, Any],
        input_fingerprints: dict[str, str],
        latest_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.latest_path = Path(latest_path) if latest_path else None
        repo = Path(__file__).resolve().parents[1]
        self.data: dict[str, Any] = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "run_id": run_id,
            "status": "RUNNING",
            "identity": {"company_code": company_code, "period": period, "mode": mode},
            "versions": {
                "code": _code_version(repo),
                "config": fingerprint(config),
                "prompt": str(config.get("prompt_version") or ""),
            },
            "input_fingerprints": dict(sorted(input_fingerprints.items())),
            "started_at": _now(),
            "completed_at": None,
            "steps": [],
            "llm_calls": [],
            "usage": {
                "calls": 0, "input_tokens": 0, "output_tokens": 0,
                "cached_input_tokens": 0, "uncached_input_tokens": 0,
                "llm_duration_sec": 0.0, "retry_attempts": 0, "estimated_cost_usd": None,
            },
            "cache": {"hits": 0, "misses": 0, "writes": 0, "invalid": 0},
            "warnings": [],
            "errors": [],
            "artifacts": [],
            "publication": {"status": "NOT_ATTEMPTED"},
            "manifest_fingerprint": "",
        }
        self.write()

    def _fingerprint(self) -> str:
        payload = deepcopy(self.data)
        payload.pop("manifest_fingerprint", None)
        return fingerprint(payload)

    def write(self) -> None:
        self.data = redact_sensitive(self.data)
        self.data["manifest_fingerprint"] = self._fingerprint()
        _atomic_json(self.path, self.data)
        if self.latest_path and self.latest_path != self.path:
            _atomic_json(self.latest_path, self.data)

    def record_step(self, name: str, status: str, **fields: Any) -> None:
        self.data["steps"].append({"name": name, "status": status, "recorded_at": _now(), **redact_sensitive(fields)})
        self.write()

    def record_call(self, payload: dict[str, Any]) -> None:
        safe = redact_sensitive(payload)
        self.data["llm_calls"].append(safe)
        if not safe.get("cache_hit"):
            self.data["usage"]["calls"] += 1
            self.data["usage"]["llm_duration_sec"] = round(
                float(self.data["usage"].get("llm_duration_sec", 0.0))
                + float(safe.get("duration_sec", 0.0) or 0.0), 3
            )
            if int(safe.get("attempt", 1) or 1) > 1:
                self.data["usage"]["retry_attempts"] += 1
        if safe.get("outcome") == "success" and not safe.get("cache_hit"):
            usage = safe.get("usage") or {}
            self.data["usage"]["input_tokens"] += int(usage.get("input", 0) or 0)
            self.data["usage"]["output_tokens"] += int(usage.get("output", 0) or 0)
            cached = int(usage.get("cache_hit_input", 0) or 0)
            uncached = int(usage.get("cache_miss_input", 0) or 0)
            if not cached and not uncached:
                uncached = int(usage.get("input", 0) or 0)
            self.data["usage"]["cached_input_tokens"] += cached
            self.data["usage"]["uncached_input_tokens"] += uncached
            call_cost = safe.get("estimated_cost_usd")
            if call_cost is not None:
                current = self.data["usage"].get("estimated_cost_usd")
                self.data["usage"]["estimated_cost_usd"] = round(float(current or 0.0) + float(call_cost), 8)
        self.write()

    def cache_event(self, outcome: str) -> None:
        field = "hits" if outcome == "hit" else "misses" if outcome == "miss" else "writes" if outcome == "write" else "invalid"
        self.data["cache"][field] += 1
        self.write()

    def add_warning(self, code: str) -> None:
        if code not in self.data["warnings"]:
            self.data["warnings"].append(redact_text(code))
            self.write()

    def add_error(self, category: str, message: str) -> None:
        self.data["errors"].append({"category": category, "message": redact_text(message)[:500], "at": _now()})
        self.write()

    def add_artifact(self, path: str | Path, role: str) -> None:
        target = Path(path)
        item = {"path": str(target), "role": role, "exists": target.exists()}
        if target.is_file():
            item.update({"sha256": _file_hash(target), "size_bytes": target.stat().st_size})
        self.data["artifacts"].append(item)
        self.write()

    def finalize(self, status: str, *, publication: dict[str, Any] | None = None) -> None:
        normalized = status.upper()
        if normalized not in TERMINAL_STATUSES:
            raise RuntimeGovernanceError(f"invalid terminal status: {normalized}")
        if normalized == "COMPLETED" and self.data.get("errors"):
            raise RuntimeGovernanceError("manifest with recorded errors cannot be marked COMPLETED")
        self.data["status"] = normalized
        self.data["completed_at"] = _now()
        if publication is not None:
            self.data["publication"] = redact_sensitive(publication)
        self.write()


class RuntimeController:
    """Model route, budget, rate limit, exact cache and manifest coordinator."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        run_id: str,
        company_code: str,
        period: str,
        mode: str,
        template_path: str = "",
        config_path: str | Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.config = load_runtime_config(config_path)
        self.task_type = "report_synthesis"
        self.company_code = company_code
        self.period = period or "UNSPECIFIED"
        cache_cfg = self.config["cache"]
        self.cache = ContentAddressedCache(
            self.output_dir / str(cache_cfg["directory_name"]), int(cache_cfg["max_entry_bytes"])
        )
        self.manifest = RunManifest(
            self.output_dir / "run_manifests" / f"{run_id}.json",
            run_id=run_id,
            company_code=company_code,
            period=self.period,
            mode=mode,
            config=self.config,
            input_fingerprints=collect_input_fingerprints(self.output_dir, template_path),
            latest_path=self.output_dir / "run_manifest.json",
        )
        self._last_call_at = 0.0
        self._started_monotonic = time.monotonic()

    def set_task(self, task_type: str) -> None:
        if task_type not in self.config["task_profiles"]:
            raise RuntimeGovernanceError(f"unknown task type: {task_type}")
        self.task_type = task_type

    def refresh_input_fingerprints(self, template_path: str = "") -> None:
        """Capture deterministic inputs created during prepare phases."""
        self.manifest.data["input_fingerprints"] = collect_input_fingerprints(
            self.output_dir, template_path
        )
        self.manifest.write()

    def profile(self) -> dict[str, Any]:
        return self.config["task_profiles"][self.task_type]

    def validate_route(self, model: str) -> dict[str, Any]:
        profile = self.profile()
        actual = self.config["model_tiers"].get(model, "economy")
        required = profile["minimum_tier"]
        ranks = self.config["tier_rank"]
        if profile["critical"] and ranks.get(actual, 0) < ranks.get(required, 0):
            self.manifest.add_error("model_tier_violation", f"{self.task_type}:{model}:{actual}<{required}")
            raise ModelTierViolation(
                f"关键任务 {self.task_type} 要求 {required}，模型 {model} 仅登记为 {actual}；禁止静默降级"
            )
        return {"task_type": self.task_type, "critical": bool(profile["critical"]), "tier": actual, "minimum_tier": required}

    def prepare_call(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
        temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        route = self.validate_route(model)
        request_hash = fingerprint({
            "messages": messages, "tools": tools or [], "temperature": temperature, "max_tokens": max_tokens
        })
        budget = self.config["budget"]
        usage = self.manifest.data["usage"]
        estimated_input = max(1, len(_canonical(messages)) // 4)
        max_wall_minutes = float((self.config.get("execution_guard") or {}).get("max_wall_minutes", 0))
        if max_wall_minutes > 0 and time.monotonic() - self._started_monotonic >= max_wall_minutes * 60:
            self.manifest.add_error("budget_exhausted", "wall time budget exhausted")
            raise BudgetExhausted("真实运行已达到最长墙钟时间；保留断点并停止继续消耗")
        if int(usage["calls"]) >= int(budget["max_calls"]):
            self.manifest.add_error("budget_exhausted", "call budget exhausted")
            raise BudgetExhausted("LLM 调用预算耗尽；运行暂停，不降低关键任务模型")
        remaining_input = int(budget["max_input_tokens"]) - int(usage["input_tokens"])
        remaining_output = int(budget["max_output_tokens"]) - int(usage["output_tokens"])
        remaining_uncached = int(budget.get("max_uncached_input_tokens", budget["max_input_tokens"])) - int(
            usage.get("uncached_input_tokens", 0)
        )
        warning_fraction = float(budget.get("warning_fraction", 0.8))
        if (
            int(usage["calls"]) >= int(budget["max_calls"]) * warning_fraction
            or int(usage["input_tokens"]) >= int(budget["max_input_tokens"]) * warning_fraction
            or int(usage["output_tokens"]) >= int(budget["max_output_tokens"]) * warning_fraction
        ):
            self.manifest.add_warning("runtime_budget_warning_threshold_reached")
        allowed_max_tokens = int(max_tokens)
        if estimated_input > remaining_input or estimated_input > remaining_uncached or allowed_max_tokens > remaining_output:
            if route["critical"]:
                self.manifest.add_error("budget_exhausted", f"critical task budget insufficient:{self.task_type}")
                raise BudgetExhausted("关键研究预算不足；运行暂停，不自动换低能力模型或截短推理")
            allowed_max_tokens = min(allowed_max_tokens, max(0, remaining_output))
            if estimated_input > remaining_input or allowed_max_tokens < 512:
                self.manifest.add_error("budget_exhausted", f"noncritical task budget insufficient:{self.task_type}")
                raise BudgetExhausted("非关键任务预算不足；运行暂停")
            self.manifest.add_warning(f"scope_reduced_by_budget:{self.task_type}")
        scope = CacheScope(
            company_code=self.company_code,
            period=self.period,
            task_type=self.task_type,
            model=model,
            prompt_version=str(self.config["prompt_version"]),
            code_version=str(self.manifest.data["versions"]["code"]),
        )
        cached = None
        cache_status = "disabled"
        if self.config["cache"]["enabled"]:
            cached, cache_status = self.cache.get(scope, request_hash)
            self.manifest.cache_event(cache_status if cache_status in {"hit", "miss"} else "invalid")
        return {
            "route": route, "request_fingerprint": request_hash, "scope": scope,
            "cached": cached, "cache_status": cache_status, "max_tokens": allowed_max_tokens,
            "estimated_input_tokens": estimated_input,
        }

    def retry_policy(self) -> dict[str, Any]:
        return self.config["retry"]

    def wait_for_rate_limit(self) -> None:
        # A small inter-call floor prevents accidental tight loops without hiding provider 429s.
        minimum = float((self.config.get("rate_limit") or {}).get("minimum_interval_seconds", 0.1))
        elapsed = time.monotonic() - self._last_call_at
        if self._last_call_at and elapsed < minimum:
            time.sleep(minimum - elapsed)
        self._last_call_at = time.monotonic()

    def record_call(self, payload: dict[str, Any]) -> None:
        enriched = dict(payload)
        if enriched.get("outcome") == "success" and not enriched.get("cache_hit"):
            model = str(enriched.get("model") or "")
            rates = (self.config.get("pricing_usd_per_million_tokens") or {}).get(model)
            usage = enriched.get("usage") if isinstance(enriched.get("usage"), dict) else {}
            if isinstance(rates, dict):
                enriched["estimated_cost_usd"] = round(
                    (int(usage.get("input", 0) or 0) * float(rates.get("input", 0.0))
                     + int(usage.get("output", 0) or 0) * float(rates.get("output", 0.0))) / 1_000_000,
                    8,
                )
            else:
                enriched["estimated_cost_usd"] = None
                self.manifest.add_warning(f"pricing_unconfigured:{model}")
        self.manifest.record_call(enriched)

    def cache_response(self, prepared: dict[str, Any], payload: dict[str, Any]) -> None:
        if not self.config["cache"]["enabled"]:
            return
        ttl = int(self.profile()["cache_ttl_seconds"])
        if ttl > 0 and self.cache.put(prepared["scope"], prepared["request_fingerprint"], payload, ttl):
            self.manifest.cache_event("write")


PROTECTED_ARTIFACT_NAMES = {
    "analysis_contract.json", "compute_bundle.json", "document_manifest.json", "fact_observations.json",
    "report_context.json", "decision_ledger.json", "decision_manifest.json", "claim_evidence_ledger.json",
    "valuation_model_ledger.json", "thesis_test_ledger.json", "insight_ledger.json",
    "decisive_question_plan.json", "decisive_question_findings.json", "publication_snapshot.json",
    "monitoring_plan.json", "run_manifest.json", "completion_report.json",
}


def build_retention_plan(root: str | Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Produce an auditable preview.  Nothing is removed by this function."""
    base = Path(root).resolve()
    current = now or datetime.now(timezone.utc)
    config = load_runtime_config()["retention"]
    candidates: list[dict[str, Any]] = []
    protected: list[str] = []
    for path in base.rglob("*"):
        if not path.is_file() or ".runtime_trash" in path.parts:
            continue
        relative = str(path.relative_to(base))
        if path.name in PROTECTED_ARTIFACT_NAMES or path.suffix.lower() in {".pdf"} or "publication_snapshot" in path.name:
            protected.append(relative)
            continue
        age_days = max(0.0, (current.timestamp() - path.stat().st_mtime) / 86400)
        reason = ""
        if ".runtime_cache" in path.parts and age_days >= int(config["cache_days"]):
            reason = "expired_runtime_cache"
        elif path.name in {"_diagnostics.json"} and age_days >= int(config["diagnostic_days"]):
            reason = "stale_diagnostics"
        elif path.suffix in {".tmp", ".partial"} and age_days >= 1:
            reason = "stale_partial"
        if reason:
            candidates.append({"path": relative, "reason": reason, "size_bytes": path.stat().st_size})
    core = {
        "schema_version": RETENTION_SCHEMA_VERSION,
        "root": str(base),
        "generated_at": current.replace(microsecond=0).isoformat(),
        "mode": "PREVIEW",
        "candidates": sorted(candidates, key=lambda item: item["path"]),
        "protected_count": len(protected),
        "candidate_bytes": sum(int(item["size_bytes"]) for item in candidates),
    }
    core["plan_fingerprint"] = fingerprint({key: value for key, value in core.items() if key != "generated_at"})
    return core


def apply_retention_plan(plan: dict[str, Any], *, confirm_fingerprint: str) -> dict[str, Any]:
    """Move previewed files to recoverable trash after exact confirmation."""
    if plan.get("schema_version") != RETENTION_SCHEMA_VERSION:
        raise RuntimeGovernanceError("retention plan schema mismatch")
    if str(plan.get("plan_fingerprint")) != str(confirm_fingerprint):
        raise RuntimeGovernanceError("retention confirmation fingerprint mismatch")
    base = Path(str(plan["root"])).resolve()
    trash = base / load_runtime_config()["retention"]["trash_directory_name"] / datetime.now().strftime("%Y%m%d_%H%M%S")
    moved: list[dict[str, Any]] = []
    for item in plan.get("candidates") or []:
        source = (base / str(item["path"])).resolve()
        if base not in source.parents or not source.is_file() or source.name in PROTECTED_ARTIFACT_NAMES:
            continue
        target = trash / source.relative_to(base)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moved.append({"from": str(source.relative_to(base)), "to": str(target.relative_to(base))})
    return {"status": "MOVED_TO_RECOVERABLE_TRASH", "trash": str(trash), "moved": moved}


def validate_run_manifest(payload: dict[str, Any], *, verify_artifacts: bool = True) -> dict[str, Any]:
    invalid: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version", "run_id", "status", "identity", "versions", "input_fingerprints",
        "steps", "llm_calls", "usage", "cache", "artifacts", "publication", "manifest_fingerprint",
    }
    missing = sorted(required - set(payload))
    if missing:
        invalid.extend("missing:" + field for field in missing)
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    core = deepcopy(payload)
    recorded = str(core.pop("manifest_fingerprint", ""))
    if recorded != fingerprint(core):
        invalid.append("manifest_fingerprint_mismatch")
    if payload.get("status") == "COMPLETED" and payload.get("errors"):
        invalid.append("completed_manifest_contains_errors")
    if verify_artifacts:
        for index, item in enumerate(payload.get("artifacts") or []):
            if not isinstance(item, dict) or not item.get("path"):
                invalid.append(f"artifact[{index}]:identity_invalid")
                continue
            path = Path(str(item["path"]))
            if not path.is_file():
                warnings.append(f"artifact[{index}]:missing:{path.name}")
            elif item.get("sha256") and _file_hash(path) != item.get("sha256"):
                invalid.append(f"artifact[{index}]:hash_mismatch:{path.name}")
    return {
        "status": "INVALID" if invalid else "PASS_WITH_WARNINGS" if warnings else "PASS",
        "invalid_findings": invalid,
        "warnings": warnings,
        "run_id": payload.get("run_id"),
        "run_status": payload.get("status"),
    }


def recovery_advice(output_dir: str | Path) -> dict[str, Any]:
    """Return deterministic recovery state; never auto-publish or auto-delete."""
    output = Path(output_dir).resolve()
    manifest_path = output / "run_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "NO_MANIFEST", "action": "rerun_validation_only", "output_dir": str(output)}
    validation = validate_run_manifest(manifest, verify_artifacts=False)
    if validation["status"] == "INVALID":
        return {"status": "MANIFEST_INVALID", "action": "manual_audit_before_resume", "validation": validation}
    status = str(manifest.get("status") or "")
    execution_path = output / "judgment_research_execution.json"
    completion_path = output / "completion_report.json"
    execution = {}
    completion = {}
    try:
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if status == "COMPLETED":
        action = "no_resume_needed"
    elif execution.get("state") in {"ACTIVE", "INCOMPLETE"}:
        action = "resume_judgment_queue_validation_only"
    elif completion.get("status") in {"BLOCKED", "INCOMPLETE", "INVALID"}:
        action = "resume_repair_only_validation_only"
    else:
        action = "rerun_validation_only_from_last_verified_inputs"
    return {
        "status": status,
        "action": action,
        "run_id": manifest.get("run_id"),
        "output_dir": str(output),
        "publication_allowed": False,
    }


def audit_local_secret_boundaries(
    repo_root: str | Path, approved_files: tuple[str, ...] = ("analyze.sh", ".env")
) -> dict[str, Any]:
    """Audit boundaries without returning secret values or their hashes."""
    repo = Path(repo_root).resolve()
    ignore_text = (repo / ".gitignore").read_text(encoding="utf-8") if (repo / ".gitignore").is_file() else ""
    approved: list[dict[str, Any]] = []
    secret_values: list[tuple[str, str]] = []
    assignment = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
    for relative in approved_files:
        path = repo / relative
        labels: list[str] = []
        if path.is_file():
            file_text = path.read_text(encoding="utf-8", errors="ignore")
            for line in file_text.splitlines():
                match = assignment.match(line)
                if not match or not re.search(r"(?:KEY|TOKEN|SECRET|PASSWORD)", match.group(1), re.IGNORECASE):
                    continue
                labels.append(match.group(1))
                raw = match.group(2).strip()
                values = re.findall(r"[\"']([^\"']{6,})[\"']", raw)
                if not values:
                    values = [raw.strip("\"'")]
                for candidate in values:
                    if len(candidate) >= 6 and "$" not in candidate:
                        secret_values.append((f"{relative}:{match.group(1)}", candidate))
            for match in re.finditer(
                r"(?ms)^\s*([A-Za-z_][A-Za-z0-9_]*(?:KEYS?|TOKENS?|SECRETS?|PASSWORDS?))\s*=\s*\((.*?)\)",
                file_text,
            ):
                label = match.group(1)
                labels.append(label)
                for candidate in re.findall(r"[\"']([^\"']{6,})[\"']", match.group(2)):
                    if "$" not in candidate:
                        secret_values.append((f"{relative}:{label}", candidate))
        approved.append({
            "path": relative, "exists": path.is_file(), "ignored": _ignore_rule_covers(relative, ignore_text),
            "secret_labels": sorted(set(labels)),
        })
    leaks: list[dict[str, str]] = []
    scan_suffixes = {
        ".json", ".jsonl", ".log", ".md", ".html", ".txt", ".yaml", ".yml",
        ".py", ".sh", ".toml", ".cfg", ".ini",
    }
    excluded_parts = {".git", ".venv", "node_modules", ".runtime_trash"}
    approved_paths = {(repo / name).resolve() for name in approved_files}
    if secret_values:
        for path in repo.rglob("*"):
            if not path.is_file() or path.resolve() in approved_paths or any(part in excluded_parts for part in path.parts):
                continue
            if path.suffix.lower() not in scan_suffixes or path.stat().st_size > 16 * 1024 * 1024:
                continue
            data = path.read_text(encoding="utf-8", errors="ignore")
            for label, secret in secret_values:
                if secret in data:
                    leaks.append({"path": str(path.relative_to(repo)), "secret_label": label})
    return {
        "status": "PASS" if all(item["ignored"] for item in approved) and not leaks else "INVALID",
        "approved_local_secret_files": approved,
        "leaks": leaks,
        "secret_values_returned": False,
    }


def _ignore_rule_covers(relative: str, ignore_text: str) -> bool:
    rules = {line.strip().lstrip("/") for line in ignore_text.splitlines() if line.strip() and not line.startswith("#")}
    return relative in rules or (relative.startswith(".env") and ".env.*" in rules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Turtle runtime governance utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    retention = sub.add_parser("retention-preview")
    retention.add_argument("root")
    retention.add_argument("--output", default="")
    retention_apply = sub.add_parser("retention-apply")
    retention_apply.add_argument("plan")
    retention_apply.add_argument("--confirm-fingerprint", required=True)
    secret = sub.add_parser("secret-audit")
    secret.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    verify = sub.add_parser("verify-manifest")
    verify.add_argument("manifest")
    recovery = sub.add_parser("recovery-advice")
    recovery.add_argument("output_dir")
    args = parser.parse_args(argv)
    if args.command == "retention-preview":
        payload = build_retention_plan(args.root)
        if args.output:
            _atomic_json(Path(args.output), payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "retention-apply":
        payload = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        print(json.dumps(apply_retention_plan(payload, confirm_fingerprint=args.confirm_fingerprint), ensure_ascii=False, indent=2))
    elif args.command == "secret-audit":
        print(json.dumps(audit_local_secret_boundaries(args.root), ensure_ascii=False, indent=2))
    elif args.command == "verify-manifest":
        payload = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        result = validate_run_manifest(payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] != "INVALID" else 2
    else:
        print(json.dumps(recovery_advice(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
