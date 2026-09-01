import json
from pathlib import Path

from scripts.turtle_agent.tools.read_tools import (
    get_global_benchmarks,
    get_peer_comparison,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _industry_payload(*, eligibility: dict | None = None, source: str = "zone_d") -> dict:
    return {
        "_source": source,
        "meta": {"industry_l2": "示例行业", "fiscal_year": 2024, "total_industry_peers": 8},
        "target_metrics": {"gross_margin": 30.0, "pe": 15.0},
        "comparison_eligibility": eligibility or {
            "status": "CANDIDATE_UNVERIFIED",
            "selection_basis": "same broad industry label",
            "responsibility_boundary_basis": None,
            "lifecycle_basis": None,
            "accounting_definition_basis": "same DB field name only",
            "period_basis": "FY2024",
        },
        "comparable_peers": [{"ts_code": "000002.SZ", "name": "候选同行", "pe": 10.0}],
        "percentiles": {
            "gross_margin": {
                "label": "毛利率", "value": 30.0, "industry_median": 20.0,
                "percentile": 80.0, "peer_count": 8,
            },
        },
        "signals": [{"type": "STRENGTH", "detail": "毛利率行业前20%"}],
    }


def test_unverified_nonempty_peer_pool_is_candidate_only_without_percentiles(tmp_path: Path) -> None:
    _write(tmp_path / "industry_context.json", _industry_payload())

    result = get_peer_comparison(str(tmp_path))

    assert result["peer_comparison_status"] == "CANDIDATE_UNVERIFIED"
    assert result["comparable_peers"] == []
    assert result["percentiles"] == {}
    assert result["signals"] == []
    assert result["candidate_peers"][0]["name"] == "候选同行"
    assert "不得生成表、Pxx" in result["usage_hint"]


def test_stub_peer_pool_cannot_become_verified_even_with_claimed_eligibility(tmp_path: Path) -> None:
    verified = {
        "status": "VERIFIED",
        "responsibility_boundary_basis": "listed consolidated issuers",
        "lifecycle_basis": "mature operators",
        "accounting_definition_basis": "same parent profit and PE definition",
        "period_basis": "FY2024",
    }
    _write(
        tmp_path / "industry_context.json",
        _industry_payload(eligibility=verified, source="stub (script failed)"),
    )

    result = get_peer_comparison(str(tmp_path))

    assert result["peer_comparison_status"] == "CANDIDATE_UNVERIFIED"
    assert result["comparable_peers"] == []


def test_verified_same_definition_peer_pool_remains_usable(tmp_path: Path) -> None:
    verified = {
        "status": "VERIFIED",
        "responsibility_boundary_basis": "listed consolidated issuers",
        "lifecycle_basis": "mature operators with no material perimeter transition",
        "accounting_definition_basis": "same parent-profit PE and gross-margin definition",
        "period_basis": "FY2024 audited annual reports",
    }
    _write(tmp_path / "industry_context.json", _industry_payload(eligibility=verified))

    result = get_peer_comparison(str(tmp_path))

    assert result["peer_comparison_status"] == "VERIFIED"
    assert result["comparable_peers"][0]["name"] == "候选同行"
    assert result["percentiles"]["gross_margin"]["percentile"] == 80.0
    assert result["candidate_peers"] == []


def test_global_benchmark_names_are_discovery_candidates_not_verified_comparables(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "analysis_contract.json", {
        "industry_classification": {"peer_group": "饮料", "l2": "软饮料"},
    })

    result = get_global_benchmarks(str(tmp_path))

    assert result["matched"] is False
    assert result["usage_status"] == "CANDIDATE_ONLY"
    assert result["match_status"] in {"CURATED_CANDIDATES_UNVERIFIED", "DISCOVERY_ONLY"}
    assert "只有补齐责任边界、生命周期、会计定义、时期和一手来源后才可使用" in result["note"]
