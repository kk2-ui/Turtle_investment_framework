#!/usr/bin/env python3
"""Bind every training run to one complete EnterpriseUnderwritingEpisode.

This is a thin execution contract over the existing underwriting read model.
It does not store facts, settle outcomes, score fields, freeze methods, or
create investment authority.  Teaching, blind replay, and prospective work
only determine source visibility and the Episode sample identity; the sole
primary training product is the complete Episode itself.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.enterprise_underwriting_episode import (
        EPISODE_SCHEMA,
        compile_underwriting_projections,
        validate_enterprise_underwriting_episode,
        validate_underwriting_projection_bundle,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from enterprise_underwriting_episode import (
        EPISODE_SCHEMA,
        compile_underwriting_projections,
        validate_enterprise_underwriting_episode,
        validate_underwriting_projection_bundle,
    )


CONTRACT_SCHEMA = "enterprise-underwriting-training-contract.v1"
CONTRACT_VALIDATION_SCHEMA = "enterprise-underwriting-training-contract-validation.v1"
EPISODE_VALIDATION_SCHEMA = "enterprise-underwriting-training-episode-validation.v1"
DOWNSTREAM_BUNDLE_SCHEMA = "enterprise-underwriting-training-downstream-bundle.v1"
RUN_RECEIPT_SCHEMA = "enterprise-underwriting-training-run-receipt.v1"

TRACK_BINDINGS = {
    "WORKED_CASE": {
        "sample_identity": "WORKED_CASE",
        "outcome_access": "RESULT_KNOWN",
    },
    "BLIND_REPLAY": {
        "sample_identity": "BLIND_REPLAY",
        "outcome_access": "SEALED",
    },
    "PROSPECTIVE": {
        "sample_identity": "PROSPECTIVE_EPISODE",
        "outcome_access": "NOT_YET_RELEASED",
    },
}

# ``TRAINING_MEMORY`` is deliberately distinct from issuer evidence.  A Blind
# Replay may use a lesson learned from an earlier, separately settled case to
# change its questions or evidence order, even though the lesson was written
# after the target's historical cutoff.  It can never support a target-company
# fact, so the Episode binding below keeps it out of evidence_trace and
# existing_object_refs.
SOURCE_TIME_ROLES = {"PRE_CUTOFF", "RESULT_KNOWN", "TRAINING_MEMORY"}
FEEDBACK_HORIZONS = {
    "EARLY_SIGNAL",
    "OPERATING_ADAPTATION",
    "NORMALIZATION_AND_CASH",
    "LONG_TERM_PERMANENT_LOSS",
}
EPISODE_CLAIMS = {
    "INDUSTRY_AND_SITUATION",
    "BUSINESS_POSITION_AND_ADAPTATION",
    "SURVIVAL_AND_FINANCING",
    "NORMAL_EARNINGS",
    "OWNER_CASH",
    "PERMANENT_LOSS",
    "VALUE_ROUTE",
}

ROOT_FIELDS = {
    "schema_version",
    "contract_id",
    "training_track",
    "company_id",
    "company_name",
    "cutoff_at",
    "sample_identity",
    "outcome_access",
    "allowed_sources",
    "feedback_clocks",
    "primary_training_product",
    "authority",
}
SOURCE_FIELDS = {"source_id", "source_ref", "available_at", "time_role"}
CLOCK_FIELDS = {
    "clock_id",
    "horizon",
    "opens_at",
    "episode_claims",
    "discriminating_observation",
}
PRODUCT_FIELDS = {"object_type", "schema_version", "completion_basis"}
PRIMARY_PRODUCT = {
    "object_type": "EnterpriseUnderwritingEpisode",
    "schema_version": EPISODE_SCHEMA,
    "completion_basis": "COMPLETE_EPISODE_VALIDATION_ONLY",
}
TRAINING_AUTHORITY = "RESEARCH_TRAINING_ONLY_NO_PRICE_VALUATION_OR_INVESTMENT_AUTHORITY"

_ROOT = Path(__file__).resolve().parents[1]
_PRICE_RESULT_KEYS = {
    "price",
    "market_price",
    "share_price",
    "entry_price",
    "buyband",
    "buy_band",
    "expected_return",
    "realized_return",
    "valuation_result",
}
_BLIND_RESULT_KEYS = {
    "outcome_result",
    "outcome_results",
    "observed_result",
    "result_value",
    "settlement",
    "settled_value",
    "post_outcome_review",
}
_LEGACY_COMPLETION_KEYS = {
    "axes",
    "outcome_cells",
    "material_treatment_snapshot",
    "field_completion",
    "gate_states",
    "receipt_completion",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _canonical_ref(value: Any) -> str:
    return str(value or "").split("#", 1)[0].strip()


def _source_ref_resolvable(value: Any) -> bool:
    reference = _canonical_ref(value)
    if not reference or "://" in reference:
        return False
    return (_ROOT / reference).is_file() or reference.startswith(
        ("SRC:", "OBS:", "DOC:", "CALC:", "canonical:")
    )


def _result(schema_version: str, findings: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": schema_version,
        "state": "REVIEWABLE" if not unique else "INVALID",
        "findings": unique,
    }


def _forbidden_paths(value: Any, forbidden: set[str], path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in forbidden:
                findings.append(child)
            else:
                findings.extend(_forbidden_paths(item, forbidden, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, forbidden, f"{path}[{index}]"))
    return findings


def build_training_contract(
    *,
    contract_id: str,
    training_track: str,
    company_id: str,
    company_name: str,
    cutoff_at: str,
    allowed_sources: list[dict[str, Any]],
    feedback_clocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the minimal task envelope without adding another training object."""

    track = str(training_track or "").upper()
    binding = TRACK_BINDINGS.get(track, {})
    return {
        "schema_version": CONTRACT_SCHEMA,
        "contract_id": contract_id,
        "training_track": track,
        "company_id": company_id,
        "company_name": company_name,
        "cutoff_at": cutoff_at,
        "sample_identity": binding.get("sample_identity"),
        "outcome_access": binding.get("outcome_access"),
        "allowed_sources": deepcopy(allowed_sources),
        "feedback_clocks": deepcopy(feedback_clocks),
        "primary_training_product": deepcopy(PRIMARY_PRODUCT),
        "authority": TRAINING_AUTHORITY,
    }


def validate_training_contract(contract: Any) -> dict[str, Any]:
    """Validate identity, source visibility, and multi-clock feedback binding."""

    findings: list[str] = []
    value = _mapping(contract)
    if not value:
        return _result(CONTRACT_VALIDATION_SCHEMA, ["contract.must_be_object"])
    unexpected = sorted(set(value) - ROOT_FIELDS)
    if unexpected:
        findings.append("contract.unexpected_fields:" + ",".join(unexpected))
    if value.get("schema_version") != CONTRACT_SCHEMA:
        findings.append("contract.schema_version_invalid")
    for field in ("contract_id", "company_id", "company_name"):
        if not _text(value.get(field)):
            findings.append(f"contract.{field}_missing")

    cutoff = _instant(value.get("cutoff_at"))
    if cutoff is None:
        findings.append("contract.cutoff_at_invalid")

    track = str(value.get("training_track") or "").upper()
    binding = TRACK_BINDINGS.get(track)
    if binding is None:
        findings.append("contract.training_track_invalid")
    else:
        if value.get("sample_identity") != binding["sample_identity"]:
            findings.append("contract.sample_identity_not_bound_to_track")
        if value.get("outcome_access") != binding["outcome_access"]:
            findings.append("contract.outcome_access_not_bound_to_track")
    if track == "BLIND_REPLAY" and value.get("outcome_access") != "SEALED":
        findings.append("contract.blind_replay_requires_sealed_outcome")

    sources = value.get("allowed_sources")
    if not isinstance(sources, list) or not sources:
        findings.append("contract.allowed_sources_missing")
        sources = []
    source_ids: set[str] = set()
    source_refs: set[str] = set()
    for index, raw in enumerate(sources):
        path = f"contract.allowed_sources[{index}]"
        source = _mapping(raw)
        if not source:
            findings.append(path + ".must_be_object")
            continue
        extra = sorted(set(source) - SOURCE_FIELDS)
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        source_id = source.get("source_id")
        source_ref = _canonical_ref(source.get("source_ref"))
        if not _text(source_id) or source_id in source_ids:
            findings.append(path + ".source_id_missing_or_duplicate")
        else:
            source_ids.add(str(source_id))
        if not source_ref or source_ref in source_refs:
            findings.append(path + ".source_ref_missing_or_duplicate")
        else:
            source_refs.add(source_ref)
            if not _source_ref_resolvable(source_ref):
                findings.append(path + ".source_ref_not_resolvable")
        available = _instant(source.get("available_at"))
        if available is None:
            findings.append(path + ".available_at_invalid")
        time_role = source.get("time_role")
        if time_role not in SOURCE_TIME_ROLES:
            findings.append(path + ".time_role_invalid")
        if track in {"BLIND_REPLAY", "PROSPECTIVE"}:
            if time_role == "RESULT_KNOWN":
                findings.append(path + ".result_known_source_forbidden")
            if (
                time_role == "PRE_CUTOFF"
                and cutoff is not None
                and available is not None
                and available > cutoff
            ):
                findings.append(path + ".available_after_cutoff")

    clocks = value.get("feedback_clocks")
    if not isinstance(clocks, list) or len(clocks) < 2:
        findings.append("contract.feedback_clocks_requires_multiple_items")
        clocks = []
    clock_ids: set[str] = set()
    horizons: set[str] = set()
    for index, raw in enumerate(clocks):
        path = f"contract.feedback_clocks[{index}]"
        clock = _mapping(raw)
        if not clock:
            findings.append(path + ".must_be_object")
            continue
        extra = sorted(set(clock) - CLOCK_FIELDS)
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        clock_id = clock.get("clock_id")
        if not _text(clock_id) or clock_id in clock_ids:
            findings.append(path + ".clock_id_missing_or_duplicate")
        else:
            clock_ids.add(str(clock_id))
        horizon = clock.get("horizon")
        if horizon not in FEEDBACK_HORIZONS:
            findings.append(path + ".horizon_invalid")
        else:
            horizons.add(str(horizon))
        opens = _instant(clock.get("opens_at"))
        if opens is None:
            findings.append(path + ".opens_at_invalid")
        elif cutoff is not None and opens <= cutoff:
            findings.append(path + ".opens_at_must_follow_cutoff")
        claims = clock.get("episode_claims")
        if not isinstance(claims, list) or not claims:
            findings.append(path + ".episode_claims_missing")
        elif len(claims) != len(set(claims)) or not set(claims) <= EPISODE_CLAIMS:
            findings.append(path + ".episode_claims_invalid")
        if not _text(clock.get("discriminating_observation")):
            findings.append(path + ".discriminating_observation_missing")
    if len(clocks) >= 2 and len(horizons) < 2:
        findings.append("contract.feedback_clocks_must_use_distinct_horizons")

    product = _mapping(value.get("primary_training_product"))
    if set(product) != PRODUCT_FIELDS or product != PRIMARY_PRODUCT:
        findings.append("contract.primary_training_product_must_be_complete_episode_only")
    if value.get("authority") != TRAINING_AUTHORITY:
        findings.append("contract.authority_invalid")
    return _result(CONTRACT_VALIDATION_SCHEMA, findings)


def validate_training_episode(contract: Any, episode: Any) -> dict[str, Any]:
    """Validate one Episode against the task without rewarding local artifacts."""

    findings: list[str] = []
    contract_result = validate_training_contract(contract)
    findings.extend("contract:" + item for item in contract_result["findings"])
    contract_value = _mapping(contract)
    episode_value = _mapping(episode)

    episode_result = validate_enterprise_underwriting_episode(episode_value)
    findings.extend("episode:" + item for item in episode_result["findings"])
    if episode_value:
        for field in ("company_id", "company_name", "cutoff_at", "sample_identity"):
            if episode_value.get(field) != contract_value.get(field):
                findings.append("binding." + field + "_mismatch")

        allowed_sources = [
            _mapping(item)
            for item in _items(contract_value.get("allowed_sources"))
            if isinstance(item, dict)
        ]
        allowed = {_canonical_ref(item.get("source_ref")) for item in allowed_sources}
        training_memory = {
            _canonical_ref(item.get("source_ref"))
            for item in allowed_sources
            if item.get("time_role") == "TRAINING_MEMORY"
        }
        for index, item in enumerate(_items(episode_value.get("evidence_trace"))):
            reference = _canonical_ref(_mapping(item).get("source_ref"))
            if reference not in allowed:
                findings.append(f"binding.evidence_trace[{index}].source_not_allowed")
            elif reference in training_memory:
                findings.append(f"binding.evidence_trace[{index}].training_memory_not_company_evidence")
        for index, item in enumerate(_items(episode_value.get("existing_object_refs"))):
            reference = _canonical_ref(_mapping(item).get("ref"))
            if reference not in allowed:
                findings.append(f"binding.existing_object_refs[{index}].source_not_allowed")
            elif reference in training_memory:
                findings.append(f"binding.existing_object_refs[{index}].training_memory_not_company_evidence")

        findings.extend(
            "episode.price_or_return_forbidden:" + path
            for path in _forbidden_paths(episode_value, _PRICE_RESULT_KEYS)
        )
        findings.extend(
            "episode.legacy_completion_forbidden:" + path
            for path in _forbidden_paths(episode_value, _LEGACY_COMPLETION_KEYS)
        )
        if contract_value.get("training_track") in {"BLIND_REPLAY", "PROSPECTIVE"}:
            findings.extend(
                "episode.preoutcome_result_forbidden:" + path
                for path in _forbidden_paths(episode_value, _BLIND_RESULT_KEYS)
            )
    return _result(EPISODE_VALIDATION_SCHEMA, findings)


def compile_price_free_downstream_bundle(contract: Any, episode: Any) -> dict[str, Any]:
    """Compile existing price-free projections after the sole product validates."""

    validation = validate_training_episode(contract, episode)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("training_episode_invalid:" + ",".join(validation["findings"]))
    projections = compile_underwriting_projections(episode)
    projection_validation = validate_underwriting_projection_bundle(episode, projections)
    if projection_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "underwriting_projection_invalid:" + ",".join(projection_validation["findings"])
        )
    value = _mapping(episode)
    thesis = _mapping(value.get("underwriting_thesis"))
    return {
        "schema_version": DOWNSTREAM_BUNDLE_SCHEMA,
        "contract_id": _mapping(contract).get("contract_id"),
        "company_id": value.get("company_id"),
        "cutoff_at": value.get("cutoff_at"),
        "sample_identity": value.get("sample_identity"),
        "primary_training_product": {
            "object_type": "EnterpriseUnderwritingEpisode",
            "episode_id": value.get("episode_id"),
            "underwriting_thesis_id": thesis.get("thesis_id"),
        },
        "authority": "PRICE_FREE_RESEARCH_CANDIDATES_ONLY",
        "projections": projections,
        "boundary": {
            "contains_outcome_results": False,
            "contains_price_or_valuation_results": False,
            "grants_investment_authority": False,
        },
    }


def _source_materials(contract: dict[str, Any]) -> list[dict[str, str]]:
    """Read only the source files named by the already validated contract."""
    materials: list[dict[str, str]] = []
    for item in _items(contract.get("allowed_sources")):
        source = _mapping(item)
        reference = _canonical_ref(source.get("source_ref"))
        path = Path(reference).expanduser()
        if not path.is_absolute():
            path = _ROOT / path
        if not path.is_file():
            raise ValueError(
                "training source is not a readable local artifact; prepare a source-package "
                "text artifact before running the Agent: " + reference
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "training source must be a UTF-8 research artifact: " + reference
            ) from exc
        materials.append({
            "source_id": str(source.get("source_id") or ""),
            "source_ref": reference,
            "content": content,
        })
    return materials


def build_training_agent_messages(
    contract: Any,
    *,
    source_materials: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build the one complete-Episode task consumed by the training Agent."""
    validation = validate_training_contract(contract)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("training_contract_invalid:" + ",".join(validation["findings"]))
    value = _mapping(contract)
    source_blocks = []
    source_roles = {
        _canonical_ref(item.get("source_ref")): str(item.get("time_role") or "")
        for item in _items(value.get("allowed_sources"))
        if isinstance(item, dict)
    }
    for item in source_materials:
        source_ref = str(item.get("source_ref") or "")
        source_blocks.append(
            "\n".join([
                "<source>",
                "source_id=" + str(item.get("source_id") or ""),
                "source_ref=" + source_ref,
                "time_role=" + source_roles.get(_canonical_ref(source_ref), ""),
                str(item.get("content") or ""),
                "</source>",
            ])
        )
    system = """You are Turtle's enterprise-underwriting training synthesizer.
Your only product is one complete EnterpriseUnderwritingEpisode JSON object.
Connect industry future and profit-pool transmission, company position and adaptation,
survival and financing, normalized economics, owner cash, permanent-loss paths, value
route, strongest rival, and reversal observations into one best-current judgment.
Evidence discipline is a constraint, not the product: localize an unknown and continue
the rest of the company. Do not emit axes, outcome cells, receipts, gates, scores,
market price, valuation results, expected return, BuyBand, or investment action.
When capital spending matters, keep three distinct economic questions: operating cash
less economic maintenance capital (normal owner cash), operating cash less all
long-lived-asset spending (current capital-allocation and financing pressure), and the
subsequent return on growth capital. Missing growth-return evidence or total spending
must never be renamed as maintenance capital or used to invent a negative owner-cash
point estimate; give a conditional treatment and continue the company judgment.
Capital intensity is economic, not a fixed-asset label: for a channel, service, retail,
or acquisition-led company, identify material working-capital, lease, logistics, people,
integration, or customer-acquisition commitments alongside long-lived assets. Do not call
a company cash-light merely because capex is low, and do not force a capital-spending
problem where those commitments are immaterial.
Use only the supplied sources. Every evidence_trace.source_ref and existing_object_ref.ref
must exactly match a supplied source_ref. Return JSON only, with schema_version
enterprise-underwriting-episode.v2. The underwriting_thesis must include
economic_directions.normal_earnings, owner_cash, and permanent_loss, each chosen from
IMPROVES, DETERIORATES, MIXED, UNKNOWN, or NONE. Only primary valuation model roles are
mandatory; corroborative and stress roles may be empty or omitted when economically
inapplicable. A source labelled TRAINING_MEMORY is prior curriculum guidance only: use it
to change questions, evidence order, rival checks, or conditional treatment, but never
as a target-company fact and never cite it in evidence_trace or existing_object_refs."""
    user = "\n".join([
        "Create the complete pre-outcome Episode for this frozen training contract:",
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        "\nAllowed source material:",
        "\n\n".join(source_blocks),
        "\nReturn the JSON object now.",
    ])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_agent_episode(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return deepcopy(raw)
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("training Agent did not return an Episode JSON object")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("training Agent Episode must be a JSON object")
    return payload


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_training_agent(
    contract: Any,
    *,
    output_dir: str | Path,
    episode_generator: Callable[[list[dict[str, str]]], Any],
    source_materials: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate, validate, and persist the sole training product.

    A caller cannot complete this function by handing in a prewritten Episode;
    it must supply an Agent/runtime generator, which is invoked after the source
    contract has been validated.  Local artifacts are written only after the
    returned complete Episode passes the same binding validator used by replay.
    """
    contract_value = _mapping(contract)
    contract_validation = validate_training_contract(contract_value)
    if contract_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "training_contract_invalid:" + ",".join(contract_validation["findings"])
        )
    materials = source_materials if source_materials is not None else _source_materials(contract_value)
    allowed_refs = {
        _canonical_ref(item.get("source_ref"))
        for item in _items(contract_value.get("allowed_sources"))
        if isinstance(item, dict)
    }
    observed_refs = {
        _canonical_ref(item.get("source_ref"))
        for item in materials if isinstance(item, dict)
    }
    if observed_refs != allowed_refs:
        raise ValueError("training Agent source materials must exactly match the contract allowlist")
    messages = build_training_agent_messages(
        contract_value,
        source_materials=materials,
    )
    episode = _parse_agent_episode(episode_generator(messages))
    episode_validation = validate_training_episode(contract_value, episode)
    if episode_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "training_agent_episode_invalid:" + ",".join(episode_validation["findings"])
        )
    bundle = compile_price_free_downstream_bundle(contract_value, episode)
    output = Path(output_dir).expanduser().resolve()
    episode_path = output / "enterprise_underwriting_episode.json"
    bundle_path = output / "enterprise_underwriting_downstream_bundle.json"
    _atomic_json(episode_path, episode)
    _atomic_json(bundle_path, bundle)
    return {
        "schema_version": RUN_RECEIPT_SCHEMA,
        "state": "TRAINING_EPISODE_COMPLETED",
        "contract_id": contract_value.get("contract_id"),
        "episode_id": episode.get("episode_id"),
        "underwriting_thesis_id": _mapping(episode.get("underwriting_thesis")).get("thesis_id"),
        "episode_path": str(episode_path),
        "downstream_bundle_path": str(bundle_path),
        "completion_basis": "AGENT_GENERATED_COMPLETE_EPISODE_VALIDATED",
        "authority": TRAINING_AUTHORITY,
    }


def _runtime_episode_generator(
    *, provider: str, model: str,
) -> Callable[[list[dict[str, str]]], str]:
    try:
        from scripts.turtle_agent.llm_client import LlmClient
    except ModuleNotFoundError:  # pragma: no cover - direct script fallback
        from turtle_agent.llm_client import LlmClient
    client = LlmClient(provider=provider, model=model or None)

    def generate(messages: list[dict[str, str]]) -> str:
        response = client.chat_with_retry(
            messages,
            temperature=0.2,
            max_tokens=16384,
            max_retries=1,
        )
        return response.content

    return generate


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_contract = sub.add_parser("validate-contract")
    validate_contract.add_argument("contract", type=Path)
    for name in ("validate-episode", "compile-bundle"):
        command = sub.add_parser(name)
        command.add_argument("contract", type=Path)
        command.add_argument("episode", type=Path)
    run = sub.add_parser("run")
    run.add_argument("contract", type=Path)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument(
        "--provider", choices=["anthropic", "openai", "deepseek", "deepseek_oa"],
        default="anthropic",
    )
    run.add_argument("--model", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        contract = _read_json(args.contract)
        if args.command == "validate-contract":
            result = validate_training_contract(contract)
        elif args.command == "run":
            result = run_training_agent(
                contract,
                output_dir=args.output_dir,
                episode_generator=_runtime_episode_generator(
                    provider=args.provider,
                    model=args.model,
                ),
            )
        else:
            episode = _read_json(args.episode)
            result = (
                validate_training_episode(contract, episode)
                if args.command == "validate-episode"
                else compile_price_free_downstream_bundle(contract, episode)
            )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        result = {
            "schema_version": "enterprise-underwriting-training-cli-error.v1",
            "state": "INVALID",
            "findings": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("state", "REVIEWABLE") != "INVALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
