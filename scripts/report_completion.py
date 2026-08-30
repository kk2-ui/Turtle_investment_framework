from __future__ import annotations

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any

try:
    from scripts.chapter_depth import analyze_chapter_depth, detect_data_richness
except ModuleNotFoundError:
    from chapter_depth import analyze_chapter_depth, detect_data_richness  # type: ignore[no-redef]


@dataclass
class CompletionResult:
    status: str
    blocking_findings: list[str]
    warning_findings: list[str]
    chapter_results: list[dict[str, Any]]
    validators: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_audit_ledger(output_dir: str) -> dict[str, Any]:
    path = os.path.join(output_dir, 'chapter_audit_ledger.json')
    if not os.path.exists(path):
        return {'chapters': {}}
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def evaluate_pending_valuation_decision_revision(output_dir: str) -> dict[str, Any]:
    """Validate a non-canonical valuation hypothesis against current state.

    A valuation-layer action is not a user approval surface.  It remains an
    internal synthesis input until thesis, insight, chapters and the full
    completion contract are coherent.  Legacy pending-approval proposals are
    interpreted under the same rule instead of asking the user to approve an
    incomplete report.
    """
    path = Path(output_dir, 'valuation_decision_revision_proposal.json')
    try:
        proposal = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'state': 'NONE', 'status': 'SKIP', 'findings': []}
    state = str(proposal.get('state') or '')
    legacy_pending = (
        state == 'READY_FOR_DECISION_REVISION'
        and proposal.get('approval_status') == 'PENDING'
    )
    internal_synthesis = (
        state == 'INTERNAL_SYNTHESIS_REQUIRED'
        and proposal.get('approval_status') == 'NOT_REQUESTED_AT_VALUATION_STAGE'
    )
    if not (legacy_pending or internal_synthesis):
        return {'state': 'NONE', 'status': 'SKIP', 'findings': []}
    try:
        from scripts.decision_ledger import ledger_fingerprint
        from scripts.valuation_model_gate import valuation_fingerprint
    except ModuleNotFoundError:
        from decision_ledger import ledger_fingerprint
        from valuation_model_gate import valuation_fingerprint
    findings: list[str] = []
    candidate = proposal.get('candidate')
    if not isinstance(candidate, dict) or (
        valuation_fingerprint(candidate) != proposal.get('candidate_fingerprint')
    ):
        findings.append('candidate_fingerprint_mismatch')
    # A valuation proposal is an internal hypothesis, not a permanent approval
    # ticket.  Once full-report synthesis has propagated the same valuation,
    # action, position and chosen value into the canonical files, the old
    # ledger fingerprint is expected to differ and the proposal is resolved.
    # Treating that intentional propagation as staleness would force a user to
    # approve an already coherent final report one intermediate step at a time.
    try:
        canonical_valuation = json.loads(
            Path(output_dir, 'valuation_model.json').read_text(encoding='utf-8')
        )
        canonical_manifest = json.loads(
            Path(output_dir, 'decision_manifest.json').read_text(encoding='utf-8')
        )
        canonical_ledger = json.loads(
            Path(output_dir, 'decision_ledger.json').read_text(encoding='utf-8')
        )
    except (OSError, json.JSONDecodeError):
        canonical_valuation = {}; canonical_manifest = {}; canonical_ledger = {}
    proposed = proposal.get('proposed_synthesis') or {}
    canonical_synthesis = canonical_valuation.get('synthesis') or {}
    entries = {
        str(item.get('entry_id')): item
        for item in canonical_ledger.get('entries') or []
        if isinstance(item, dict)
    }
    chosen_entry = entries.get(str(proposed.get('decision_entry_id') or 'D006')) or {}
    action = str(proposed.get('action') or '').lower()
    manifest_actions = {
        str(canonical_manifest.get('quantitative_decision') or '').lower(),
        str(canonical_manifest.get('unified_decision') or '').lower(),
    }
    def same_optional_number(left: Any, right: Any) -> bool:
        if left is None or right is None:
            return left is None and right is None
        try:
            return abs(float(left) - float(right)) <= 1e-9
        except (TypeError, ValueError):
            return False

    position_matches = same_optional_number(
        canonical_manifest.get('position_pct'), proposed.get('position_pct')
    )
    value_matches = same_optional_number(
        chosen_entry.get('value'), proposed.get('chosen_value_per_share')
    )
    valuation_metadata = {
        'revision', 'lifecycle', 'change_reason', 'generated_at', 'freeze',
    }
    semantic_keys = (
        set(candidate) | set(canonical_valuation)
        if isinstance(candidate, dict) else set()
    ) - valuation_metadata
    valuation_semantics_match = bool(semantic_keys) and all(
        canonical_valuation.get(key) == candidate.get(key) for key in semantic_keys
    )
    if (
        isinstance(candidate, dict)
        and not findings
        and valuation_semantics_match
        and canonical_synthesis == proposed
        and action in manifest_actions
        and position_matches
        and value_matches
    ):
        return {
            'state': 'RESOLVED', 'status': 'PASS', 'findings': [],
            'path': str(path),
            'resolution': 'propagated_after_full_report_synthesis',
            'candidate_fingerprint': proposal.get('candidate_fingerprint'),
        }
    try:
        ledger = canonical_ledger or json.loads(Path(output_dir, 'decision_ledger.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        ledger = {}
    if not ledger or ledger_fingerprint(ledger) != proposal.get('current_decision_ledger_fingerprint'):
        findings.append('current_decision_ledger_changed')
    structural = proposal.get('structural_validation') or {}
    report_text = '\n\n'.join(
        chapter.read_text(encoding='utf-8')
        for chapter in sorted(Path(output_dir, 'chapters').glob('_ch*.md'))
    )
    try:
        from scripts.valuation_model_gate import validate_valuation_model_ledger
        from scripts.decision_reliability import validate_decision_reliability
    except ModuleNotFoundError:
        from valuation_model_gate import validate_valuation_model_ledger
        from decision_reliability import validate_decision_reliability
    if isinstance(candidate, dict):
        structural = validate_valuation_model_ledger(
            candidate, output_dir=output_dir, report_text=report_text, enforced=True
        )
    allowed = {
        'synthesis_manifest_action_mismatch',
        'synthesis_manifest_position_mismatch',
        'synthesis_v_final_mismatch',
    }
    structural_invalid = set(structural.get('invalid_findings') or [])
    if (
        not structural_invalid
        or not structural_invalid.issubset(allowed)
        or structural.get('incomplete_findings')
    ):
        findings.append('proposal_structural_scope_invalid')
    reliability = (
        validate_decision_reliability(
            output_dir, report_text=report_text, enforced=True,
            valuation_override=candidate,
        ) if isinstance(candidate, dict) else {}
    )
    if reliability.get('state') not in {'DECISION_READY', 'MONITORING'}:
        findings.append('proposal_decision_reliability_not_ready')
    if findings:
        return {'state': 'INVALID', 'status': 'FAIL', 'findings': findings, 'path': str(path)}
    return {
        'state': 'INCOMPLETE', 'status': 'FULL_REPORT_SYNTHESIS_REQUIRED',
        'findings': ['valuation_hypothesis_requires_full_report_synthesis'],
        'path': str(path),
        'candidate_fingerprint': proposal.get('candidate_fingerprint'),
        'proposed_synthesis': proposal.get('proposed_synthesis') or {},
        'required_revisions': proposal.get('required_revisions') or [],
    }


def has_valid_internal_valuation_hypothesis(output_dir: str) -> bool:
    """Whether downstream synthesis may consume a non-final valuation.

    This advances research context only.  It does not make the candidate
    canonical, publishable, approved or executable.
    """
    result = evaluate_pending_valuation_decision_revision(output_dir)
    return (
        result.get('state') == 'INCOMPLETE'
        and result.get('status') == 'FULL_REPORT_SYNTHESIS_REQUIRED'
        and result.get('findings') == [
            'valuation_hypothesis_requires_full_report_synthesis'
        ]
    )


def _expected_v13_chapters() -> list[int]:
    return list(range(15))


def _chapter_path(output_dir: str, idx: int) -> str:
    chapters_dir = os.path.join(output_dir, 'chapters')
    candidate = os.path.join(chapters_dir, f'_ch{idx:02d}.md')
    if os.path.exists(candidate):
        return candidate
    return os.path.join(output_dir, f'_ch{idx:02d}.md')


def _title_from_text(text: str) -> str:
    for line in text.splitlines():
        if line.startswith('## '):
            return line[3:].strip()
    return ''


def _analysis_purpose(output_dir: str) -> str:
    """Resolve the frozen report purpose before choosing completion gates."""
    try:
        contract = json.loads(Path(output_dir, "analysis_contract.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "INVESTMENT_DECISION"
    purpose = str(contract.get("analysis_purpose") or "INVESTMENT_DECISION")
    return purpose if purpose in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"} else "INVALID"


def _bound_frozen_cjo_ref(output_dir: str) -> str:
    try:
        contract = json.loads(
            Path(output_dir, "analysis_contract.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return ""
    refs = contract.get("canonical_judgment_refs")
    if not isinstance(refs, dict):
        return ""
    return str(refs.get("frozen_cjo_ref") or "").strip()


def _episode_bound_investment_refs(output_dir: str) -> dict[str, Any]:
    """Return the formal Episode predecessor binding, including partial binds.

    Once either canonical current-company reference is declared, completion
    must validate that route and must not silently fall back to the legacy
    bridge/thesis predecessor.
    """
    try:
        contract = json.loads(
            Path(output_dir, "analysis_contract.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    refs = contract.get("canonical_judgment_refs")
    if contract.get("analysis_purpose") != "INVESTMENT_DECISION" or not isinstance(refs, dict):
        return {}
    frozen_ref = str(refs.get("frozen_cjo_ref") or "").strip()
    admission_ref = str(refs.get("current_company_cjo_admission_ref") or "").strip()
    if not frozen_ref and not admission_ref:
        return {}
    return {
        "frozen_cjo_ref": frozen_ref,
        "current_company_cjo_admission_ref": admission_ref,
        "company_id": str(
            contract.get("company_id")
            or contract.get("ts_code")
            or contract.get("code")
            or ""
        ),
        "cutoff_at": str(
            contract.get("data_as_of")
            or contract.get("analysis_date")
            or ""
        ),
    }


def _completion_company_identity_matches(canonical: Any, runtime: Any) -> bool:
    left = str(canonical or "").strip().upper()
    right = str(runtime or "").strip().upper()
    if left == right:
        return True
    if ":" not in left or "." not in right:
        return False
    market, security = left.split(":", 1)
    runtime_security, exchange = right.split(".", 1)
    runtime_market = {"SH": "CN", "SZ": "CN", "BJ": "CN", "HK": "HK"}.get(exchange)
    return bool(runtime_market == market and runtime_security == security)


def _evaluate_episode_bound_investment_predecessor(
    output_dir: str, refs: dict[str, Any],
) -> dict[str, Any]:
    """Validate the Frozen Episode/CJO admission that replaces legacy G1J."""
    output = Path(output_dir)
    findings: list[str] = []

    def resolve(ref: Any) -> Path | None:
        text = str(ref or "").strip()
        if not text:
            return None
        path = Path(text).expanduser()
        return path.resolve() if path.is_absolute() else (output / path).resolve()

    frozen_path = resolve(refs.get("frozen_cjo_ref"))
    admission_path = resolve(refs.get("current_company_cjo_admission_ref"))
    if frozen_path is None:
        findings.append("frozen_cjo_ref_missing")
    if admission_path is None:
        findings.append("current_company_cjo_admission_ref_missing")
    try:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path else {}
    except (OSError, json.JSONDecodeError):
        frozen = {}
        findings.append("frozen_cjo_unreadable")
    try:
        admission = json.loads(admission_path.read_text(encoding="utf-8")) if admission_path else {}
    except (OSError, json.JSONDecodeError):
        admission = {}
        findings.append("current_company_cjo_admission_unreadable")

    try:
        from scripts.enterprise_judgment_core import validate_frozen_cjo
        from scripts.current_company_cjo_admission import (
            validate_frozen_current_company_cjo_admission,
        )
    except ModuleNotFoundError:
        from enterprise_judgment_core import validate_frozen_cjo
        from current_company_cjo_admission import (
            validate_frozen_current_company_cjo_admission,
        )

    frozen_validation = validate_frozen_cjo(frozen)
    admission_validation = validate_frozen_current_company_cjo_admission(
        frozen_cjo=frozen,
        admission_receipt=admission,
        require_overlay=True,
    )
    if frozen_validation.get("state") != "VALID":
        findings.extend(
            "frozen_cjo_invalid:" + str(item)
            for item in frozen_validation.get("findings") or []
        )
    if admission_validation.get("state") != "VALID":
        findings.extend(
            "current_company_cjo_admission_invalid:" + str(item)
            for item in admission_validation.get("findings") or []
        )
    projection = (
        frozen.get("underwriting_thesis_projection")
        if isinstance(frozen.get("underwriting_thesis_projection"), dict) else {}
    )
    if projection.get("sample_identity") not in {"BLIND_REPLAY", "PROSPECTIVE_EPISODE"}:
        findings.append("current_investment_requires_blind_or_prospective_episode")
    binding = (
        admission.get("candidate_binding", {}).get("primary_binding", {})
        if isinstance(admission.get("candidate_binding"), dict) else {}
    )
    if (
        binding.get("binding_kind") != "ENTERPRISE_UNDERWRITING_EPISODE"
        or binding.get("episode_id") != projection.get("episode_id")
        or binding.get("underwriting_thesis_id") != projection.get("underwriting_thesis_id")
    ):
        findings.append("current_company_admission_episode_binding_mismatch")
    if not _completion_company_identity_matches(frozen.get("company_id"), refs.get("company_id")):
        findings.append("frozen_cjo_company_id_contract_mismatch")
    if str(frozen.get("cutoff_at") or "")[:10] != str(refs.get("cutoff_at") or "")[:10]:
        findings.append("frozen_cjo_cutoff_contract_mismatch")

    return {
        "state": "DECISION_READY" if not findings else "INVALID",
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
        "episode_id": str(projection.get("episode_id") or ""),
        "underwriting_thesis_id": str(projection.get("underwriting_thesis_id") or ""),
        "sample_identity": str(projection.get("sample_identity") or ""),
        "frozen_cjo_validation": frozen_validation,
        "current_company_cjo_admission_validation": admission_validation,
    }


def _evaluate_bound_frozen_cjo_completion(
    report_text: str, output_dir: str, frozen_ref: str,
) -> CompletionResult:
    """Complete the exact deterministic Frozen-CJO reader route.

    This route has no free chapters.  Its completion truth is the validated
    canonical object, the current read receipt and the exact deterministic
    renderer output.
    """
    output = Path(output_dir)
    path = Path(frozen_ref).expanduser()
    frozen_path = path.resolve() if path.is_absolute() else (output / path).resolve()
    try:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        frozen = {}
    try:
        from scripts.enterprise_judgment_core import validate_frozen_cjo
        from scripts.judgment_handoff_receipts import validate_judgment_handoff_read_receipt
        from scripts.turtle_agent.tools.write_tools import (
            _cjo_report_output_validation,
            _render_bound_frozen_cjo_research_artifact,
        )
    except ModuleNotFoundError:
        from enterprise_judgment_core import validate_frozen_cjo
        from judgment_handoff_receipts import validate_judgment_handoff_read_receipt
        from turtle_agent.tools.write_tools import (
            _cjo_report_output_validation,
            _render_bound_frozen_cjo_research_artifact,
        )

    frozen_validation = validate_frozen_cjo(frozen)
    receipt = validate_judgment_handoff_read_receipt(output)
    deterministic_output = _cjo_report_output_validation(report_text)
    findings: list[str] = []
    if frozen_validation.get("state") != "VALID":
        findings.extend(
            "Frozen CJO: " + str(item)
            for item in frozen_validation.get("findings") or []
        )
    try:
        expected_report = _render_bound_frozen_cjo_research_artifact(frozen)
    except RuntimeError as exc:
        expected_report = ""
        findings.append(str(exc))
    if expected_report and report_text != expected_report:
        findings.append("Deterministic CJO output does not equal canonical renderer")
    if receipt.get("state") != "READY":
        findings.extend(
            "Judgment handoff receipt: " + str(item)
            for item in receipt.get("findings") or [receipt.get("state")]
        )
    if deterministic_output.get("status") != "PASS":
        findings.extend(
            "CJO output: " + str(item)
            for item in deterministic_output.get("blocking_findings") or []
        )

    status = "COMPLETE" if not findings else "BLOCKED"
    validators = {
        "analysis_purpose": {"state": "COMPANY_JUDGMENT_ONLY"},
        "bound_frozen_cjo": frozen_validation,
        "judgment_handoff_read_receipt": receipt,
        "deterministic_cjo_output": deterministic_output,
        "deterministic_renderer": {
            "status": "PASS" if expected_report and report_text == expected_report else "FAIL",
        },
        "structure": {"status": "SKIP", "reason": "bound_frozen_cjo_has_no_free_chapters"},
        "depth": {"status": "SKIP", "reason": "bound_frozen_cjo_has_no_free_chapters"},
        "audit": {"status": "SKIP", "reason": "bound_frozen_cjo_has_no_free_chapters"},
        "reader_coverage": {"status": "SKIP", "reason": "deterministic_frozen_cjo_field_projection"},
        "absolute_quality": {"status": "SKIP", "reason": "bound_frozen_cjo_has_no_free_chapters"},
    }
    result = CompletionResult(
        status=status,
        blocking_findings=findings,
        warning_findings=[],
        chapter_results=[],
        validators=validators,
    )
    (output / "completion_report.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def evaluate_report_completion(
    report_text: str,
    output_dir: str,
    *,
    reader_report_text: str | None = None,
) -> CompletionResult:
    ledger = _load_audit_ledger(output_dir)
    analysis_purpose = _analysis_purpose(output_dir)
    company_judgment_only = analysis_purpose == "COMPANY_JUDGMENT_ONLY"
    episode_investment_refs = _episode_bound_investment_refs(output_dir)
    episode_bound_investment = bool(episode_investment_refs)
    episode_predecessor = (
        _evaluate_episode_bound_investment_predecessor(
            output_dir, episode_investment_refs,
        )
        if episode_bound_investment else {
            "state": "SKIP", "status": "SKIP",
            "findings": [], "reason": "legacy_predecessor_path",
        }
    )
    frozen_ref = _bound_frozen_cjo_ref(output_dir) if company_judgment_only else ""
    if frozen_ref:
        return _evaluate_bound_frozen_cjo_completion(
            report_text, output_dir, frozen_ref,
        )
    blocking: list[str] = []
    warnings: list[str] = []
    chapter_results: list[dict[str, Any]] = []
    chapter_texts: dict[int, str] = {}
    if episode_bound_investment and episode_predecessor.get("state") != "DECISION_READY":
        blocking.append(
            "Enterprise underwriting predecessor: INVALID: "
            + " | ".join(str(item) for item in episode_predecessor.get("findings") or [])
        )
    chapters = ledger.get('chapters', {}) if isinstance(ledger, dict) else {}
    data_rich = detect_data_richness(output_dir)
    for idx in _expected_v13_chapters():
        path = _chapter_path(output_dir, idx)
        exists = os.path.exists(path)
        text = ''
        if exists:
            text = Path(path).read_text(encoding='utf-8')
        chapter_texts[idx] = text
        nonempty = sum(1 for line in text.splitlines() if line.strip())
        title = _title_from_text(text)
        ledger_entry = chapters.get(str(idx), {}) if isinstance(chapters, dict) else {}
        final_audit = ledger_entry.get('final') if isinstance(ledger_entry, dict) else None
        depth = analyze_chapter_depth(text, idx, data_rich=data_rich)
        chapter_blockers: list[str] = []
        if not exists:
            chapter_blockers.append('missing_file')
        if exists and not title:
            chapter_blockers.append('missing_h2_title')
        if depth['status'] == 'FAIL':
            chapter_blockers.append('short_depth:' + ','.join(depth['failures']))
        if not final_audit:
            chapter_blockers.append('missing_audit_record')
        elif not final_audit.get('passed', False):
            chapter_blockers.append('audit_failed')
        if chapter_blockers:
            blocking.append(f'Ch{idx}: ' + '; '.join(chapter_blockers))
        chapter_results.append({
            'index': idx,
            'path': path,
            'exists': exists,
            'title': title,
            'nonempty_lines': nonempty,
            'depth': depth,
            'audit': final_audit,
            'blocking_rules': chapter_blockers,
        })

    # Chapter depth and structured ledgers can all pass while a remediation
    # accidentally replaces the reader narrative with a technical summary.
    # The semantic reader gate is enforced for current archetype-aware runs;
    # legacy directories without that context remain auditable by the older
    # contracts and are not silently reclassified here.
    try:
        from scripts.reader_coverage import evaluate_reader_coverage
    except ModuleNotFoundError:
        from reader_coverage import evaluate_reader_coverage
    # Archetype routing is the activation marker.  An insight-policy file can
    # exist in legacy/unit-test outputs without the current reader contract.
    reader_enforced = os.path.exists(
        os.path.join(output_dir, 'company_archetype.json')
    )
    reader_coverage = evaluate_reader_coverage(
        reader_report_text if reader_report_text is not None else report_text,
        output_dir,
        enforced=reader_enforced,
        persist=reader_enforced,
    )
    if reader_coverage.get('status') == 'BLOCKED':
        blocking.append(
            'Reader coverage: ' + ' | '.join(
                str(item) for item in reader_coverage.get('blocking_findings', [])[:12]
            )
        )

    decision_status = 'SKIP' if company_judgment_only else 'PASS'
    manifest_path = os.path.join(output_dir, 'decision_manifest.json')
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    if not company_judgment_only:
        required_decision_fields = {
            'qualitative_decision', 'quantitative_decision', 'unified_decision',
            'display_label', 'decision_family', 'position_pct',
        }
        missing_decision_fields = sorted(required_decision_fields - set(manifest)) if isinstance(manifest, dict) else sorted(required_decision_fields)
        if missing_decision_fields:
            decision_status = 'FAIL'
            blocking.append('Decision: manifest_missing_fields:' + ','.join(missing_decision_fields))
        else:
            label = str(manifest.get('display_label') or '').strip()
            if not label or label not in chapter_texts.get(0, '') or label not in chapter_texts.get(14, ''):
                decision_status = 'FAIL'
                blocking.append(f'Decision: Ch0/Ch14/manifest mismatch ({label or "empty"})')

    # Phase 01 official-evidence platform. Legacy directories without its
    # policy remain SKIP; new unified runs must preserve document/fact identity.
    try:
        from scripts.build_report_context import evaluate_output_official_evidence
    except ModuleNotFoundError:
        from build_report_context import evaluate_output_official_evidence
    try:
        official_evidence = evaluate_output_official_evidence(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        official_evidence = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [], 'warnings': [],
        }
    official_evidence_state = str(official_evidence.get('state') or 'INVALID')
    if official_evidence_state == 'INVALID':
        blocking.append('Official evidence: INVALID: ' + ' | '.join(str(item) for item in official_evidence.get('invalid_findings', [])[:12]))
    elif official_evidence_state == 'INCOMPLETE':
        blocking.append('Official evidence: INCOMPLETE: ' + ' | '.join(str(item) for item in official_evidence.get('incomplete_findings', [])[:12]))
    elif official_evidence_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Official evidence: INVALID: unknown state ' + official_evidence_state)

    # A financial-driver bridge is opt-in for legacy outputs, but once a new
    # run enables it, a report cannot complete while cash conversion or capital
    # allocation remains unbound from the valuation and decision ledgers.
    if episode_bound_investment:
        financial_driver_bridge = {
            'state': 'SKIP', 'status': 'SKIP',
            'invalid_findings': [], 'incomplete_findings': [], 'warnings': [],
            'reason': 'enterprise_underwriting_episode_is_price_free_company_story',
        }
    else:
        try:
            from scripts.financial_driver_bridge import evaluate_output_financial_driver_bridge
        except ModuleNotFoundError:
            from financial_driver_bridge import evaluate_output_financial_driver_bridge
        try:
            financial_driver_bridge = evaluate_output_financial_driver_bridge(output_dir, persist=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            financial_driver_bridge = {
                'state': 'INVALID', 'status': 'FAIL',
                'invalid_findings': ['validator_error:' + str(exc)],
                'incomplete_findings': [], 'warnings': [],
            }
    financial_driver_bridge_state = str(financial_driver_bridge.get('state') or 'INVALID')
    if financial_driver_bridge_state == 'INVALID':
        blocking.append('Financial driver bridge: INVALID: ' + ' | '.join(str(item) for item in financial_driver_bridge.get('invalid_findings', [])[:12]))
    elif financial_driver_bridge_state == 'INCOMPLETE':
        blocking.append('Financial driver bridge: INCOMPLETE: ' + ' | '.join(str(item) for item in financial_driver_bridge.get('incomplete_findings', [])[:12]))
    elif financial_driver_bridge_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Financial driver bridge: INVALID: unknown state ' + financial_driver_bridge_state)

    try:
        from scripts.valuation_routing import evaluate_output_valuation_route
    except ModuleNotFoundError:
        from valuation_routing import evaluate_output_valuation_route
    try:
        valuation_route = evaluate_output_valuation_route(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        valuation_route = {'state': 'INVALID', 'status': 'FAIL', 'invalid_findings': ['validator_error:' + str(exc)], 'incomplete_findings': [], 'warnings': []}
    valuation_route_state = str(valuation_route.get('state') or 'INVALID')
    if not company_judgment_only and valuation_route_state == 'INVALID':
        blocking.append('Valuation route: INVALID: ' + ' | '.join(str(item) for item in valuation_route.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and valuation_route_state == 'INCOMPLETE':
        blocking.append('Valuation route: INCOMPLETE: ' + ' | '.join(str(item) for item in valuation_route.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and valuation_route_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Valuation route: INVALID: unknown state ' + valuation_route_state)

    try:
        from scripts.decisive_question import evaluate_output_decisive_questions
    except ModuleNotFoundError:
        from decisive_question import evaluate_output_decisive_questions
    try:
        decisive_questions = evaluate_output_decisive_questions(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        decisive_questions = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [], 'warnings': [],
        }
    decisive_questions_state = str(decisive_questions.get('state') or 'INVALID')
    if not company_judgment_only and decisive_questions_state == 'INVALID':
        blocking.append('Decisive questions: INVALID: ' + ' | '.join(str(item) for item in decisive_questions.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and decisive_questions_state == 'INCOMPLETE':
        blocking.append('Decisive questions: INCOMPLETE: ' + ' | '.join(str(item) for item in decisive_questions.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and decisive_questions_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Decisive questions: INVALID: unknown state ' + decisive_questions_state)

    try:
        from scripts.base_rate_case_library import evaluate_output_base_rate
    except ModuleNotFoundError:
        from base_rate_case_library import evaluate_output_base_rate
    try:
        base_rate = evaluate_output_base_rate(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        base_rate = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [], 'warnings': [],
        }
    base_rate_state = str(base_rate.get('state') or 'INVALID')
    if not company_judgment_only and base_rate_state == 'INVALID':
        blocking.append('Base rate: INVALID: ' + ' | '.join(str(item) for item in base_rate.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and base_rate_state == 'INCOMPLETE':
        blocking.append('Base rate: INCOMPLETE: ' + ' | '.join(str(item) for item in base_rate.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and base_rate_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Base rate: INVALID: unknown state ' + base_rate_state)
    if not company_judgment_only:
        for finding in base_rate.get('warnings') or []:
            warnings.append('Base rate: ' + str(finding))

    # A current-price refresh is a dependency change, not a cosmetic edit.
    # When a refresh candidate exists, completion stays blocked until all
    # market-cap/return/action dependents have been rebuilt and reviewed.
    try:
        from scripts.market_refresh import evaluate_output_market_refresh
    except ModuleNotFoundError:
        from market_refresh import evaluate_output_market_refresh
    try:
        market_refresh = evaluate_output_market_refresh(output_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        market_refresh = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [],
        }
    market_refresh_state = str(market_refresh.get('state') or 'INVALID')
    if not company_judgment_only and market_refresh_state == 'INVALID':
        blocking.append('Market refresh: INVALID: ' + ' | '.join(str(item) for item in market_refresh.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and market_refresh_state == 'RECOMPUTE_REQUIRED':
        blocking.append('Market refresh: RECOMPUTE_REQUIRED: ' + ' | '.join(str(item) for item in market_refresh.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and market_refresh_state not in {'SKIP', 'CURRENT'}:
        blocking.append('Market refresh: INVALID: unknown state ' + market_refresh_state)

    # V3 decision ledger.  Old directories without a policy/ledger are SKIP;
    # new unified runs bind enforcement to their run_id before report writing.
    try:
        from scripts.decision_ledger import evaluate_output_decision_ledger
    except ModuleNotFoundError:
        from decision_ledger import evaluate_output_decision_ledger
    try:
        decision_ledger = evaluate_output_decision_ledger(
            output_dir, report_text=report_text, persist=True
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        decision_ledger = {
            'state': 'INVALID',
            'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [],
        }
    decision_ledger_state = str(decision_ledger.get('state') or 'INVALID')
    if not company_judgment_only and decision_ledger_state == 'INVALID':
        findings = decision_ledger.get('invalid_findings', [])
        blocking.append('Decision ledger: INVALID: ' + ' | '.join(str(item) for item in findings[:12]))
    elif not company_judgment_only and decision_ledger_state == 'INCOMPLETE':
        findings = decision_ledger.get('incomplete_findings', [])
        blocking.append('Decision ledger: INCOMPLETE: ' + ' | '.join(str(item) for item in findings[:12]))
    elif not company_judgment_only and decision_ledger_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Decision ledger: INVALID: unknown state ' + decision_ledger_state)

    # Phase 04 decision compiler: a valid ledger is necessary but insufficient.
    # The protected output must still match its exact sources, and no second set
    # of unbound critical values may survive in explanatory prose.
    try:
        from scripts.decision_compiler import evaluate_output_decision_compiler
    except ModuleNotFoundError:
        from decision_compiler import evaluate_output_decision_compiler
    try:
        decision_compiler = evaluate_output_decision_compiler(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        decision_compiler = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [],
        }
    decision_compiler_state = str(decision_compiler.get('state') or 'INVALID')
    if not company_judgment_only and decision_compiler_state == 'INVALID':
        blocking.append('Decision compiler: INVALID: ' + ' | '.join(str(item) for item in decision_compiler.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and decision_compiler_state == 'INCOMPLETE':
        blocking.append('Decision compiler: INCOMPLETE: ' + ' | '.join(str(item) for item in decision_compiler.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and decision_compiler_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Decision compiler: INVALID: unknown state ' + decision_compiler_state)

    # V3 major-claim evidence graph.  Like the decision ledger, enforcement is
    # bound only to new unified runs; legacy output directories remain SKIP.
    try:
        from scripts.claim_evidence import evaluate_output_claim_evidence
    except ModuleNotFoundError:
        from claim_evidence import evaluate_output_claim_evidence
    try:
        claim_evidence = evaluate_output_claim_evidence(
            output_dir, report_text=report_text, persist=True
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        claim_evidence = {
            'state': 'INVALID',
            'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [],
        }
    claim_evidence_state = str(claim_evidence.get('state') or 'INVALID')
    if claim_evidence_state == 'INVALID':
        findings = claim_evidence.get('invalid_findings', [])
        blocking.append('Claim evidence: INVALID: ' + ' | '.join(str(item) for item in findings[:12]))
    elif claim_evidence_state == 'INCOMPLETE':
        findings = claim_evidence.get('incomplete_findings', [])
        blocking.append('Claim evidence: INCOMPLETE: ' + ' | '.join(str(item) for item in findings[:12]))
    elif claim_evidence_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Claim evidence: INVALID: unknown state ' + claim_evidence_state)

    try:
        from scripts.valuation_model_gate import evaluate_output_valuation_model
    except ModuleNotFoundError:
        from valuation_model_gate import evaluate_output_valuation_model
    try:
        valuation_model = evaluate_output_valuation_model(output_dir, report_text=report_text, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        valuation_model = {'state': 'INVALID', 'status': 'FAIL', 'invalid_findings': ['validator_error:' + str(exc)], 'incomplete_findings': []}
    valuation_model_state = str(valuation_model.get('state') or 'INVALID')
    if not company_judgment_only and valuation_model_state == 'INVALID':
        blocking.append('Valuation model: INVALID: ' + ' | '.join(str(item) for item in valuation_model.get('invalid_findings', [])[:12]))
    elif not company_judgment_only and valuation_model_state == 'INCOMPLETE':
        blocking.append('Valuation model: INCOMPLETE: ' + ' | '.join(str(item) for item in valuation_model.get('incomplete_findings', [])[:12]))
    elif not company_judgment_only and valuation_model_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Valuation model: INVALID: unknown state ' + valuation_model_state)

    # Phase-08 decision reliability is deliberately separate from structural
    # valuation validity: a syntactically complete model must still reconcile
    # cash access, parameter calibration, model comparability, arithmetic and
    # action logic before it can be published.
    try:
        from scripts.decision_reliability import evaluate_output_decision_reliability
    except ModuleNotFoundError:
        from decision_reliability import evaluate_output_decision_reliability
    try:
        decision_reliability = evaluate_output_decision_reliability(
            output_dir, report_text=report_text, persist=True
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        decision_reliability = {
            'state': 'INVALID', 'status': 'FAIL',
            'invalid_findings': ['validator_error:' + str(exc)],
            'incomplete_findings': [],
        }
    decision_reliability_state = str(decision_reliability.get('state') or 'INVALID')
    if not company_judgment_only and decision_reliability_state == 'INVALID':
        blocking.append(
            'Decision reliability: INVALID: ' + ' | '.join(
                str(item) for item in decision_reliability.get('invalid_findings', [])[:12]
            )
        )
    elif not company_judgment_only and decision_reliability_state == 'INCOMPLETE':
        blocking.append(
            'Decision reliability: INCOMPLETE: ' + ' | '.join(
                str(item) for item in decision_reliability.get('incomplete_findings', [])[:12]
            )
        )
    elif not company_judgment_only and decision_reliability_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Decision reliability: INVALID: unknown state ' + decision_reliability_state)

    decision_revision = (
        {'state': 'SKIP', 'status': 'SKIP', 'findings': []}
        if company_judgment_only else evaluate_pending_valuation_decision_revision(output_dir)
    )
    decision_revision_state = str(decision_revision.get('state') or 'NONE')
    if decision_revision_state == 'INCOMPLETE':
        # Replace the canonical reliability failure with the more precise
        # transactional state.  The candidate itself passed reliability; it
        # is withheld solely because its action/position/value differs from
        # the currently approved decision ledger.
        blocking = [
            item for item in blocking
            if not item.startswith('Decision reliability:')
            and not item.startswith('Valuation model:')
        ]
        valuation_model = {
            'state': 'INCOMPLETE', 'status': 'FULL_REPORT_SYNTHESIS_REQUIRED',
            'invalid_findings': [],
            'incomplete_findings': ['valuation_hypothesis_requires_full_report_synthesis'],
            'candidate_fingerprint': decision_revision.get('candidate_fingerprint'),
        }
        valuation_model_state = 'INCOMPLETE'
        decision_reliability = {
            'state': 'INCOMPLETE', 'status': 'FULL_REPORT_SYNTHESIS_REQUIRED',
            'invalid_findings': [],
            'incomplete_findings': ['valuation_hypothesis_requires_full_report_synthesis'],
            'candidate_fingerprint': decision_revision.get('candidate_fingerprint'),
        }
        decision_reliability_state = 'INCOMPLETE'
        blocking.append(
            'Decision synthesis: INCOMPLETE: valuation_hypothesis_requires_full_report_synthesis'
        )
    elif decision_revision_state == 'INVALID':
        blocking.append(
            'Decision revision: INVALID: '
            + ' | '.join(str(item) for item in decision_revision.get('findings', [])[:12])
        )

    if episode_bound_investment:
        thesis_test = {
            'state': 'SKIP', 'status': 'SKIP',
            'invalid_findings': [], 'incomplete_findings': [],
            'reason': 'frozen_episode_and_current_company_admission_own_thesis',
        }
    else:
        try:
            from scripts.thesis_test_gate import evaluate_output_thesis_test
        except ModuleNotFoundError:
            from thesis_test_gate import evaluate_output_thesis_test
        try:
            thesis_test = evaluate_output_thesis_test(output_dir, report_text=report_text, persist=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            thesis_test = {'state': 'INVALID', 'status': 'FAIL', 'invalid_findings': ['validator_error:' + str(exc)], 'incomplete_findings': []}
    thesis_test_state = str(thesis_test.get('state') or 'INVALID')
    if thesis_test_state == 'INVALID':
        blocking.append('Thesis test: INVALID: ' + ' | '.join(str(item) for item in thesis_test.get('invalid_findings', [])[:12]))
    elif thesis_test_state == 'INCOMPLETE':
        blocking.append('Thesis test: INCOMPLETE: ' + ' | '.join(str(item) for item in thesis_test.get('incomplete_findings', [])[:12]))
    elif thesis_test_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Thesis test: INVALID: unknown state ' + thesis_test_state)

    try:
        from scripts.insight_ledger import evaluate_output_insight
    except ModuleNotFoundError:
        from insight_ledger import evaluate_output_insight
    try:
        insight = evaluate_output_insight(output_dir, report_text=report_text, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        insight = {'state': 'INVALID', 'status': 'FAIL', 'invalid_findings': ['validator_error:' + str(exc)], 'incomplete_findings': []}
    insight_state = str(insight.get('state') or 'INVALID')
    if insight_state == 'INVALID':
        blocking.append('Insight ledger: INVALID: ' + ' | '.join(str(item) for item in insight.get('invalid_findings', [])[:12]))
    elif insight_state == 'INCOMPLETE':
        blocking.append('Insight ledger: INCOMPLETE: ' + ' | '.join(str(item) for item in insight.get('incomplete_findings', [])[:12]))
    elif insight_state not in {'SKIP', 'REVIEWABLE', 'DECISION_READY', 'MONITORING'}:
        blocking.append('Insight ledger: INVALID: unknown state ' + insight_state)

    # Independent ceiling review is deliberately diagnostic-only. Missing or
    # weak judgment must remain visible, but can neither pass nor fail V3 gates.
    try:
        from scripts.judgment_review import evaluate_output_judgment_review
    except ModuleNotFoundError:
        from judgment_review import evaluate_output_judgment_review
    try:
        judgment_review = evaluate_output_judgment_review(output_dir, persist=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        judgment_review = {'state': 'INVALID', 'status': 'FAIL', 'ceiling_verdict': 'NOT_ASSESSABLE', 'invalid_findings': ['validator_error:' + str(exc)]}
    try:
        from scripts.judgment_research_router import evaluate_output_judgment_research_plan
    except ModuleNotFoundError:
        from judgment_research_router import evaluate_output_judgment_research_plan
    try:
        judgment_research_plan = evaluate_output_judgment_research_plan(output_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        judgment_research_plan = {'state': 'INVALID', 'status': 'FAIL', 'blocking': False, 'invalid_findings': ['validator_error:' + str(exc)]}
    try:
        from scripts.judgment_research_execution import evaluate_judgment_research_execution
    except ModuleNotFoundError:
        from judgment_research_execution import evaluate_judgment_research_execution
    try:
        judgment_research_execution = evaluate_judgment_research_execution(output_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        judgment_research_execution = {'state': 'VIOLATION', 'status': 'FAIL', 'blocking': True, 'violations': ['validator_error:' + str(exc)]}
    if judgment_research_execution.get('state') == 'VIOLATION':
        blocking.append('Judgment research execution: ' + ' | '.join(str(item) for item in judgment_research_execution.get('violations', [])[:12]))
    elif judgment_research_execution.get('state') == 'ACTIVE':
        blocking.append('Judgment research execution: active task not completed: ' + str(judgment_research_execution.get('active_task_id')))
    elif judgment_research_execution.get('state') == 'PENDING':
        warnings.append(
            'Judgment research pending: '
            f"{judgment_research_execution.get('completed_tasks', 0)}/"
            f"{judgment_research_execution.get('task_count', 0)} queued tasks completed"
        )
    try:
        from scripts.judgment_research_synthesis import evaluate_judgment_research_synthesis
    except ModuleNotFoundError:
        from judgment_research_synthesis import evaluate_judgment_research_synthesis
    try:
        judgment_research_synthesis = evaluate_judgment_research_synthesis(output_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        judgment_research_synthesis = {
            'state': 'INVALID', 'status': 'FAIL', 'blocking': True,
            'findings': ['validator_error:' + str(exc)],
        }
    try:
        with open(os.path.join(output_dir, 'judgment_research_execution.json'), encoding='utf-8') as handle:
            raw_judgment_execution = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raw_judgment_execution = {}
    synthesis_required = bool(
        (judgment_research_plan.get('execution_policy') or {}).get('independent_synthesis_context')
        or any(
            isinstance(entry, dict) and bool(entry.get('finding'))
            for entry in (raw_judgment_execution.get('tasks') or {}).values()
        )
    )
    synthesis_state = str(judgment_research_synthesis.get('state') or 'NOT_STARTED')
    if synthesis_state == 'INVALID':
        blocking.append(
            'Judgment research synthesis: '
            + ' | '.join(str(item) for item in judgment_research_synthesis.get('findings', [])[:12])
        )
    elif synthesis_required and judgment_research_execution.get('state') == 'COMPLETE' and synthesis_state != 'REVIEWED':
        blocking.append('Judgment research synthesis: independent review not completed: ' + synthesis_state)

    # Optional historical-reference regression.  It is only a regression fuse,
    # never an absolute quality judge: old reports may themselves be mediocre.
    try:
        from scripts.legacy_reference_regression import evaluate_from_config
    except ModuleNotFoundError:
        from legacy_reference_regression import evaluate_from_config
    try:
        legacy_reference = evaluate_from_config(output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        legacy_reference = {'status': 'ERROR', 'reason': str(exc)}
    legacy_status = legacy_reference.get('status', 'SKIP')
    if legacy_status == 'FAIL':
        failures = legacy_reference.get('core_fact_failures', [])
        blocking.append('Legacy core facts: unexplained loss/change: ' + ' | '.join(str(item) for item in failures[:12]))
    elif legacy_status == 'WARN':
        warned = legacy_reference.get('warning_chapters', [])
        warnings.append('Legacy reference regression: relative drift in ' + ','.join(f'Ch{idx}' for idx in warned))
    elif legacy_status == 'ERROR':
        warnings.append('Legacy reference regression: evaluator error: ' + str(legacy_reference.get('reason', 'unknown')))

    # The hard contract is independent of the soft quality radar. Only
    # objectively auditable failures block publication; semantic weakness is
    # surfaced as a grade/WARN for repair prioritisation.
    try:
        from scripts.absolute_quality_scorecard import evaluate_absolute_quality
    except ModuleNotFoundError:
        from absolute_quality_scorecard import evaluate_absolute_quality
    try:
        absolute_quality = evaluate_absolute_quality(output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        absolute_quality = {'status': 'ERROR', 'reason': str(exc)}
    absolute_status = absolute_quality.get('status', 'ERROR')
    if absolute_status == 'FAIL':
        failed = absolute_quality.get('failed_chapters', [])
        blocking.append('Quality hard contract: failure in ' + ','.join(f'Ch{idx}' for idx in failed))
    elif absolute_status == 'ERROR':
        warnings.append('Quality evaluator: error: ' + str(absolute_quality.get('reason', 'unknown')))

    # V3 canonical report card is deliberately non-compensating.  The hard
    # lifecycle comes from the four structured gates above; expression is a
    # separate efficiency diagnostic and can never offset or create a hard
    # investment-quality result.
    try:
        from scripts.v3_quality_report import evaluate_v3_quality
    except ModuleNotFoundError:
        from v3_quality_report import evaluate_v3_quality
    try:
        v3_quality = evaluate_v3_quality(
            output_dir,
            report_text,
            gate_results={
                'official_evidence': official_evidence,
                'financial_driver_bridge': financial_driver_bridge,
                'valuation_route': valuation_route,
                'decisive_questions': decisive_questions,
                'base_rate': base_rate,
                'market_refresh': market_refresh,
                'decision': decision_ledger,
                'decision_compiler': decision_compiler,
                'claim_evidence': claim_evidence,
                'valuation': valuation_model,
                'decision_reliability': decision_reliability,
                'thesis_test': thesis_test,
                'insight': insight,
            },
            judgment_review=judgment_review,
            persist=True,
        )
        if v3_quality.get('expression', {}).get('status') == 'WARN':
            findings = v3_quality.get('expression', {}).get('findings') or []
            warnings.append('Expression efficiency: ' + ', '.join(findings))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        v3_quality = {'status': 'ERROR', 'reason': str(exc)}
        warnings.append('V3 quality report: evaluator error: ' + str(exc))

    active_states = {
        official_evidence_state, financial_driver_bridge_state, claim_evidence_state,
        thesis_test_state, insight_state,
    }
    if episode_bound_investment:
        active_states.add(str(episode_predecessor.get('state') or 'INVALID'))
    if not company_judgment_only:
        active_states.update({
            valuation_route_state, decisive_questions_state, base_rate_state,
            market_refresh_state, decision_ledger_state, decision_compiler_state,
            valuation_model_state, decision_reliability_state, decision_revision_state,
        })
    if analysis_purpose == 'INVALID' or 'INVALID' in active_states:
        status = 'INVALID'
    elif 'INCOMPLETE' in active_states or (
        not company_judgment_only and market_refresh_state == 'RECOMPUTE_REQUIRED'
    ):
        status = 'INCOMPLETE'
    else:
        status = 'COMPLETE' if not blocking else 'BLOCKED'
    validators = {
        'structure': {'status': 'PASS' if not any('missing_file' in b or 'missing_h2_title' in b for b in blocking) else 'FAIL'},
        'depth': {'status': 'PASS' if not any('short_depth:' in b for b in blocking) else 'FAIL'},
        'audit': {'status': 'PASS' if not any('audit_' in b or 'missing_audit_record' in b for b in blocking) else 'FAIL'},
        'analysis_purpose': {'state': analysis_purpose},
        'enterprise_underwriting_predecessor': episode_predecessor,
        'gg_derivation': {
            'status': 'SKIP',
            'reason': 'structured_valuation_model_and_decision_reliability_own_derivation',
        },
        'reader_coverage': reader_coverage,
        'decision_manifest': {'status': decision_status, 'path': manifest_path},
        'official_evidence': official_evidence,
        'financial_driver_bridge': financial_driver_bridge,
        'valuation_route': valuation_route,
        'decisive_questions': decisive_questions,
        'base_rate': base_rate,
        'market_refresh': market_refresh,
        'decision_ledger': decision_ledger,
        'decision_compiler': decision_compiler,
        'claim_evidence': claim_evidence,
        'valuation_model': valuation_model,
        'decision_reliability': decision_reliability,
        'valuation_decision_revision': decision_revision,
        'thesis_test': thesis_test,
        'insight': insight,
        'judgment_review': judgment_review,
        'judgment_research_plan': judgment_research_plan,
        'judgment_research_execution': judgment_research_execution,
        'judgment_research_synthesis': judgment_research_synthesis,
        'legacy_reference_regression': legacy_reference,
        'absolute_quality': absolute_quality,
        'v3_quality': v3_quality,
    }
    result = CompletionResult(
        status=status,
        blocking_findings=blocking,
        warning_findings=warnings,
        chapter_results=chapter_results,
        validators=validators,
    )
    out = os.path.join(output_dir, 'completion_report.json')
    Path(out).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    return result
