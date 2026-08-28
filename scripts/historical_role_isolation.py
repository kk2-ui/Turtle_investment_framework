#!/usr/bin/env python3
"""Role-scoped blindness for historical enterprise-judgment training.

The presence of an outcome file somewhere in the repository is not itself an
exposure.  A role is contaminated only when its recorded input includes
post-cutoff outcome content (or outcome-derived content) for the same episode.

This module deliberately does not try to sandbox a collaborator's machine or
claim which files an Agent actually read.  It validates declared inputs and
builds the smallest selector/forecaster packets.  The coordinator must execute
a no-parent-context Agent separately and record that execution.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.historical_judgment_first_draft import forecaster_contract
except ModuleNotFoundError:  # Direct `python scripts/historical_role_isolation.py` execution.
    from historical_judgment_first_draft import forecaster_contract


SCHEMA_VERSION = "historical-role-isolation.v1"
METHOD_PACK_SCHEMA_VERSION = "historical-frozen-training-method-pack.v1"
HOLDOUT_PAIR_PACKET_SCHEMA_VERSION = "historical-holdout-pair-packet.v1"
DANGEROUS_EXPOSURES = {
    "BODY_READ",
    "DERIVED_CONTENT_READ",
    "PRICE_READ",
    "RETURN_READ",
}
ALLOWED_EXPOSURES = DANGEROUS_EXPOSURES | {"METADATA_ONLY"}
REQUIRED_ROLES = ("selector_id", "forecaster_id", "custodian_id", "reviewer_id")
SELECTOR_CANDIDATE_FIELDS = {
    "company_id",
    "cutoff_at",
    "business_model_archetype",
    "preoutcome_source_count",
    "outcome_existence_confirmed",
}
SELECTION_POLICIES = {"BUSINESS_MODEL_HETEROGENEITY_THEN_CUTOFF_SOURCE_READINESS"}
METHOD_PACK_FIELDS = {
    "schema_version",
    "method_pack_id",
    "method_version",
    "state",
    "frozen_at",
    "rules",
    "authority",
    "permissions",
}
METHOD_RULE_FIELDS = {
    "rule_id",
    "status",
    "scope",
    "trigger",
    "required_behavior",
    "prohibited_inference",
    "disconfirming_observation",
}
METHOD_PERMISSION_FIELDS = {
    "method_validation",
    "transfer_validation",
    "cjo",
    "formal_valuation",
    "buy_band",
    "report",
    "investment_action",
}


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_method_pack(method_pack: dict[str, Any]) -> list[str]:
    """Validate the generalized method memory supplied to an enhanced holdout arm.

    The closed shape is intentional: a holdout receives portable research
    behavior, not company examples, outcome summaries, or raw training files.
    """

    findings: list[str] = []
    if not isinstance(method_pack, dict):
        return ["method_pack.must_be_object"]
    unexpected = sorted(set(method_pack) - METHOD_PACK_FIELDS)
    if unexpected:
        findings.append("method_pack.unapproved_fields:" + ",".join(unexpected))
    if method_pack.get("schema_version") != METHOD_PACK_SCHEMA_VERSION:
        findings.append("method_pack.schema_version_invalid")
    for field in ("method_pack_id", "method_version"):
        if not _nonempty_text(method_pack.get(field)):
            findings.append(f"method_pack.{field}_missing")
    if method_pack.get("state") != "FROZEN_FOR_HOLDOUT_EVALUATION":
        findings.append("method_pack.state_must_be_frozen_for_holdout")
    try:
        _parse_time(method_pack["frozen_at"])
    except (AttributeError, KeyError, TypeError, ValueError):
        findings.append("method_pack.frozen_at_invalid")
    if method_pack.get("authority") != "RESEARCH_METHOD_ONLY":
        findings.append("method_pack.authority_invalid")

    rules = method_pack.get("rules")
    if not isinstance(rules, list) or not rules:
        findings.append("method_pack.rules_missing")
        rules = []
    seen_rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        prefix = f"method_pack.rules[{index}]"
        if not isinstance(rule, dict):
            findings.append(prefix + ".must_be_object")
            continue
        extra = sorted(set(rule) - METHOD_RULE_FIELDS)
        if extra:
            findings.append(prefix + ".unapproved_fields:" + ",".join(extra))
        for field in METHOD_RULE_FIELDS:
            if not _nonempty_text(rule.get(field)):
                findings.append(f"{prefix}.{field}_missing")
        rule_id = rule.get("rule_id")
        if rule_id in seen_rule_ids:
            findings.append(prefix + ".rule_id_duplicate")
        elif _nonempty_text(rule_id):
            seen_rule_ids.add(str(rule_id))
        if rule.get("status") != "CANDIDATE_BEHAVIOR_NOT_VALIDATED":
            findings.append(prefix + ".status_invalid")

    permissions = method_pack.get("permissions")
    if not isinstance(permissions, dict):
        findings.append("method_pack.permissions_must_be_object")
    else:
        extra = sorted(set(permissions) - METHOD_PERMISSION_FIELDS)
        missing = sorted(METHOD_PERMISSION_FIELDS - set(permissions))
        if extra:
            findings.append("method_pack.permissions_unapproved_fields:" + ",".join(extra))
        if missing:
            findings.append("method_pack.permissions_missing:" + ",".join(missing))
        if any(permissions.get(field) != "NONE" for field in METHOD_PERMISSION_FIELDS):
            findings.append("method_pack.permissions_must_all_be_none")
    return findings


def _pdf_has_extractable_text(path: Path) -> bool:
    """Reject a damaged/textless annual-report materialization before Agent use."""

    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "5", str(path), "-"],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _exposures_for_role(manifest: dict[str, Any], role_id: str) -> list[dict[str, Any]]:
    return [
        exposure
        for exposure in manifest.get("exposure_ledger", [])
        if exposure.get("role_id") == role_id
        and exposure.get("company_id") == manifest.get("company_id")
    ]


def role_is_contaminated(manifest: dict[str, Any], role_key: str) -> bool:
    """Return whether a role actually received outcome-bearing content.

    Metadata-only knowledge that a later filing exists is intentionally not an
    exposure.  Neither is the presence of unrelated files elsewhere on disk.
    """

    role_id = manifest.get("roles", {}).get(role_key)
    if not role_id:
        return True
    try:
        cutoff = _parse_time(manifest["cutoff_at"])
    except (KeyError, TypeError, ValueError):
        return True
    for exposure in _exposures_for_role(manifest, role_id):
        try:
            available_at = _parse_time(exposure["source_available_at"])
        except (KeyError, TypeError, ValueError):
            return True
        if exposure.get("access") in DANGEROUS_EXPOSURES and available_at > cutoff:
            return True
    return False


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        findings.append("role_isolation.schema_version_invalid")

    for key in ("episode_id", "company_id", "cutoff_at", "roles"):
        if not manifest.get(key):
            findings.append(f"role_isolation.{key}_missing")

    roles = manifest.get("roles", {})
    role_ids = [roles.get(key) for key in REQUIRED_ROLES]
    if any(not role_id for role_id in role_ids):
        findings.append("role_isolation.required_role_missing")
    elif len(set(role_ids)) != len(role_ids):
        findings.append("role_isolation.roles_must_be_distinct")

    try:
        cutoff = _parse_time(manifest["cutoff_at"])
    except (KeyError, TypeError, ValueError):
        findings.append("role_isolation.cutoff_at_invalid")
        cutoff = None

    exposures = manifest.get("exposure_ledger")
    if not isinstance(exposures, list):
        findings.append("role_isolation.exposure_ledger_must_be_list")
        exposures = []
    for index, exposure in enumerate(exposures):
        prefix = f"role_isolation.exposure_ledger[{index}]"
        for field in ("role_id", "company_id", "access", "source_available_at"):
            if not exposure.get(field):
                findings.append(f"{prefix}.{field}_missing")
        if exposure.get("access") not in ALLOWED_EXPOSURES:
            findings.append(f"{prefix}.access_invalid")
        try:
            _parse_time(exposure["source_available_at"])
        except (KeyError, TypeError, ValueError):
            findings.append(f"{prefix}.source_available_at_invalid")

    sources = manifest.get("preoutcome_sources")
    if not isinstance(sources, list) or not sources:
        findings.append("role_isolation.preoutcome_sources_missing")
    else:
        seen_ids: set[str] = set()
        seen_names: set[str] = set()
        for index, source in enumerate(sources):
            prefix = f"role_isolation.preoutcome_sources[{index}]"
            source_id = source.get("source_id")
            source_path = source.get("path")
            packet_name = source.get("packet_name")
            if not source_id or source_id in seen_ids:
                findings.append(f"{prefix}.source_id_missing_or_duplicate")
            else:
                seen_ids.add(source_id)
            if not packet_name or packet_name in seen_names or Path(packet_name).name != packet_name:
                findings.append(f"{prefix}.packet_name_invalid_or_duplicate")
            else:
                seen_names.add(packet_name)
            if not source_path or not Path(source_path).is_file():
                findings.append(f"{prefix}.path_not_readable")
            elif Path(source_path).suffix.lower() == ".pdf" and not _pdf_has_extractable_text(
                Path(source_path)
            ):
                findings.append(f"{prefix}.pdf_text_not_extractable")
            try:
                available_at = _parse_time(source["available_at"])
                if cutoff is not None and available_at > cutoff:
                    findings.append(f"{prefix}.available_after_cutoff")
            except (KeyError, TypeError, ValueError):
                findings.append(f"{prefix}.available_at_invalid")
            if source.get("time_role") != "PRE_CUTOFF":
                findings.append(f"{prefix}.time_role_must_be_pre_cutoff")

    outcome = manifest.get("sealed_outcome")
    if not isinstance(outcome, dict):
        findings.append("role_isolation.sealed_outcome_missing")
    else:
        if outcome.get("body_access") != "CUSTODIAN_ONLY_AFTER_FREEZE":
            findings.append("role_isolation.outcome_body_access_invalid")
        if outcome.get("forecaster_visibility") != "EXISTENCE_METADATA_ONLY":
            findings.append("role_isolation.outcome_forecaster_visibility_invalid")
        if "path" in outcome or "url" in outcome or "value" in outcome:
            findings.append("role_isolation.outcome_locator_or_value_exposed")

    if role_is_contaminated(manifest, "selector_id"):
        findings.append("role_isolation.selector_outcome_contaminated")
    if role_is_contaminated(manifest, "forecaster_id"):
        findings.append("role_isolation.forecaster_outcome_contaminated")
    return findings


def validate_selector_universe(universe: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if universe.get("schema_version") != "historical-selector-universe.v1":
        findings.append("selector_universe.schema_version_invalid")
    if not universe.get("selector_id"):
        findings.append("selector_universe.selector_id_missing")
    selection_policy = universe.get("selection_policy")
    if selection_policy not in SELECTION_POLICIES:
        findings.append("selector_universe.selection_policy_invalid")
    candidates = universe.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        findings.append("selector_universe.candidates_missing")
        return findings
    seen: set[tuple[str, str]] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"selector_universe.candidates[{index}]"
        for field in (
            "company_id",
            "cutoff_at",
            "business_model_archetype",
            "preoutcome_source_count",
            "outcome_existence_confirmed",
        ):
            if candidate.get(field) is None:
                findings.append(f"{prefix}.{field}_missing")
        extra_fields = set(candidate) - SELECTOR_CANDIDATE_FIELDS
        if extra_fields:
            findings.append(f"{prefix}.unapproved_fields:{','.join(sorted(extra_fields))}")
        company_id = candidate.get("company_id")
        cutoff_at = candidate.get("cutoff_at")
        episode_key = (company_id, cutoff_at)
        if not company_id or not cutoff_at or episode_key in seen:
            findings.append(f"{prefix}.company_cutoff_missing_or_duplicate")
        else:
            seen.add(episode_key)
        if candidate.get("preoutcome_source_count", 0) < 2:
            findings.append(f"{prefix}.insufficient_preoutcome_sources")
    return findings


def build_selector_packet(universe: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    findings = validate_selector_universe(universe)
    if findings:
        raise ValueError(";".join(findings))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("role_isolation.output_directory_must_be_empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = {
        "schema_version": "historical-selector-packet.v1",
        "selector_id": universe["selector_id"],
        "selection_policy": universe["selection_policy"],
        "candidates": universe["candidates"],
        "instructions": [
            "Use only this candidate metadata; do not search outcomes, prices, returns, or the parent workspace.",
            "Freeze the complete roster and order before any forecaster or custodian starts.",
            "Do not rank by expected result direction, expected utility, or writing convenience.",
        ],
    }
    (output_dir / "SELECTOR_PACKET.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return packet


def _materialize_forecaster_packet(
    manifest: dict[str, Any],
    output_dir: Path,
    *,
    evaluation_arm: str,
    forecaster_id: str,
    method_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("role_isolation.output_directory_must_be_empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_sources: list[dict[str, Any]] = []
    for source in manifest["preoutcome_sources"]:
        destination = output_dir / source["packet_name"]
        shutil.copy2(source["path"], destination)
        safe_sources.append(
            {
                "source_id": source["source_id"],
                "packet_name": source["packet_name"],
                "available_at": source["available_at"],
                "time_role": "PRE_CUTOFF",
            }
        )

    method_input: dict[str, Any] = {"state": "NONE"}
    instructions = [
        "Use only files listed in source_budget.",
        "Do not search the parent workspace, prices, returns, or post-cutoff materials.",
        "Follow judgment_first_contract and return the best-current enterprise judgment before designing outcome cells.",
        "Localize unknowns without turning them into deterioration or refusing the company.",
    ]
    if method_pack is not None:
        method_path = output_dir / "FROZEN_METHOD_PACK.json"
        method_path.write_text(
            json.dumps(method_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        method_input = {
            "state": "FROZEN_GENERALIZED_METHOD_SUPPLIED",
            "packet_name": method_path.name,
            "method_pack_id": method_pack["method_pack_id"],
            "method_version": method_pack["method_version"],
        }
        instructions.append(
            "Apply FROZEN_METHOD_PACK.json only as generalized research behavior; it is not company evidence or an answer key."
        )
    elif evaluation_arm == "FAIR_BASELINE":
        instructions.append(
            "Use ordinary judgment-first research without any candidate training-method pack."
        )

    packet = {
        "schema_version": "historical-forecaster-packet.v1",
        "episode_id": manifest["episode_id"],
        "company_id": manifest["company_id"],
        "cutoff_at": manifest["cutoff_at"],
        "forecaster_id": forecaster_id,
        "evaluation_arm": evaluation_arm,
        "source_budget": safe_sources,
        "method_input": method_input,
        "outcome_state": "SEALED_NOT_IN_PACKET",
        "instructions": instructions,
        "judgment_first_contract": forecaster_contract(),
    }
    (output_dir / "FORECASTER_PACKET.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return packet


def build_forecaster_packet(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Materialize only cutoff-safe inputs for a fresh single-arm forecaster.

    The packet manifest intentionally omits the outcome locator, exposure
    ledger, other role identities, and any derived result.
    """

    findings = validate_manifest(manifest)
    if findings:
        raise ValueError(";".join(findings))
    return _materialize_forecaster_packet(
        manifest,
        output_dir,
        evaluation_arm="BLIND_SINGLE_ARM",
        forecaster_id=manifest["roles"]["forecaster_id"],
    )


def build_holdout_pair_packets(
    manifest: dict[str, Any], method_pack_path: Path, output_dir: Path,
) -> dict[str, Any]:
    """Build fair baseline/enhanced packets with one deliberate difference.

    Both fresh roles receive the same cutoff-safe company sources and the same
    judgment-first contract.  Only the enhanced arm receives the frozen,
    generalized method pack.  The target outcome remains absent from both.
    """

    findings = validate_manifest(manifest)
    pair_roles = manifest.get("holdout_pair_roles")
    if not isinstance(pair_roles, dict):
        findings.append("role_isolation.holdout_pair_roles_missing")
        pair_roles = {}
    baseline_id = pair_roles.get("baseline_forecaster_id")
    enhanced_id = pair_roles.get("enhanced_forecaster_id")
    if not _nonempty_text(baseline_id):
        findings.append("role_isolation.baseline_forecaster_id_missing")
    if not _nonempty_text(enhanced_id):
        findings.append("role_isolation.enhanced_forecaster_id_missing")
    other_roles = set(manifest.get("roles", {}).values())
    if baseline_id == enhanced_id or baseline_id in other_roles or enhanced_id in other_roles:
        findings.append("role_isolation.holdout_pair_roles_must_be_distinct")
    try:
        cutoff = _parse_time(manifest["cutoff_at"])
    except (AttributeError, KeyError, TypeError, ValueError):
        cutoff = None
    for arm, role_id in (("baseline", baseline_id), ("enhanced", enhanced_id)):
        if not _nonempty_text(role_id):
            continue
        for exposure in _exposures_for_role(manifest, str(role_id)):
            try:
                available_at = _parse_time(exposure["source_available_at"])
            except (AttributeError, KeyError, TypeError, ValueError):
                findings.append(f"role_isolation.{arm}_forecaster_exposure_invalid")
                continue
            if (
                cutoff is not None
                and exposure.get("access") in DANGEROUS_EXPOSURES
                and available_at > cutoff
            ):
                findings.append(f"role_isolation.{arm}_forecaster_outcome_contaminated")
    try:
        method_pack = json.loads(method_pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        findings.append("role_isolation.method_pack_unreadable")
        method_pack = {}
    findings.extend(validate_method_pack(method_pack))
    if findings:
        raise ValueError(";".join(findings))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("role_isolation.output_directory_must_be_empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline = _materialize_forecaster_packet(
        manifest,
        output_dir / "baseline",
        evaluation_arm="FAIR_BASELINE",
        forecaster_id=str(baseline_id),
    )
    enhanced = _materialize_forecaster_packet(
        manifest,
        output_dir / "enhanced",
        evaluation_arm="FROZEN_METHOD_ENHANCED",
        forecaster_id=str(enhanced_id),
        method_pack=method_pack,
    )
    pair = {
        "schema_version": HOLDOUT_PAIR_PACKET_SCHEMA_VERSION,
        "episode_id": manifest["episode_id"],
        "company_id": manifest["company_id"],
        "cutoff_at": manifest["cutoff_at"],
        "method_pack_id": method_pack["method_pack_id"],
        "method_version": method_pack["method_version"],
        "shared_source_budget": baseline["source_budget"],
        "arms": {
            "baseline": {
                "packet_dir": "baseline",
                "forecaster_id": baseline["forecaster_id"],
                "method_input": baseline["method_input"],
            },
            "enhanced": {
                "packet_dir": "enhanced",
                "forecaster_id": enhanced["forecaster_id"],
                "method_input": enhanced["method_input"],
            },
        },
        "fairness_contract": [
            "Both arms use the same company, cutoff, source budget, judgment-first contract, and outcome seal.",
            "Only the enhanced arm receives the frozen generalized method pack.",
            "Compare frozen material investment treatments, not prose length, field count, or confidence tone.",
        ],
        "outcome_state": "SEALED_NOT_IN_PACKET",
        "authority": "NONE",
    }
    (output_dir / "HOLDOUT_PAIR_PACKET.json").write_text(
        json.dumps(pair, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return pair


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("manifest", type=Path)
    build_parser = subparsers.add_parser("build-forecaster-packet")
    build_parser.add_argument("manifest", type=Path)
    build_parser.add_argument("output_dir", type=Path)
    holdout_parser = subparsers.add_parser("build-holdout-pair")
    holdout_parser.add_argument("manifest", type=Path)
    holdout_parser.add_argument("method_pack", type=Path)
    holdout_parser.add_argument("output_dir", type=Path)
    selector_parser = subparsers.add_parser("build-selector-packet")
    selector_parser.add_argument("manifest", type=Path)
    selector_parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.command == "validate":
        findings = validate_manifest(manifest)
        print(json.dumps({"valid": not findings, "findings": findings}, ensure_ascii=False))
        return 0 if not findings else 1
    if args.command == "build-selector-packet":
        packet = build_selector_packet(manifest, args.output_dir)
        print(json.dumps({"built": True, "candidate_count": len(packet["candidates"])}, ensure_ascii=False))
        return 0
    if args.command == "build-holdout-pair":
        packet = build_holdout_pair_packets(manifest, args.method_pack, args.output_dir)
        print(json.dumps({
            "built": True,
            "episode_id": packet["episode_id"],
            "method_pack_id": packet["method_pack_id"],
        }, ensure_ascii=False))
        return 0
    packet = build_forecaster_packet(manifest, args.output_dir)
    print(json.dumps({"built": True, "source_count": len(packet["source_budget"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
