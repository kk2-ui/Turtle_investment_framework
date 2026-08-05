import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from boundary_validator import ZONE_J_SCHEMAS, validate_file  # noqa: E402
from zone_j_agent import _validate_param_wrapper  # noqa: E402


def test_boundary_validator_accepts_wrapped_moat_params_without_moat_rating():
    data = {
        "moat_evidence": [
            {
                "type": "brand",
                "evidence": "brand strength",
                "quote": "quoted evidence",
                "durability": "5年以上",
            }
        ],
        "b_penalty_final": {
            "value": 0.2,
            "rationale": "low-quality segment exists",
            "evidence_ref": ["segments.json:1"],
            "confidence": "medium",
        },
        "g_base": {
            "value": 2.0,
            "rationale": "mature business",
            "evidence_ref": ["mda.json:2"],
            "confidence": "medium",
        },
        "g_scenarios": {"pessimistic": 1.0, "base": 2.0, "optimistic": 3.0},
        "value_trap_signals": ["margin compression"],
    }

    errors = validate_file(data, ZONE_J_SCHEMAS["moat_assessment.json"], "moat_assessment.json")

    assert errors == []


def test_boundary_validator_accepts_wrapped_data_discount_param():
    data = {
        "discount_factors": [
            {"factor": "data gap", "discount_pct": 10, "rationale": "missing note facts"}
        ],
        "total_discount_pct": {
            "value": 15,
            "rationale": "combined effect",
            "evidence_ref": ["audit.json:1"],
            "confidence": "low",
        },
        "confidence_by_section": {
            "factor2": "medium",
            "factor3_aa": "low",
            "factor3_gg": "low",
            "factor4_ddm": "medium",
        },
    }

    errors = validate_file(data, ZONE_J_SCHEMAS["data_discount.json"], "data_discount.json")

    assert errors == []


def test_zone_j_agent_wrapper_validation_requires_evidence_ref_and_confidence():
    data = {
        "total_discount_pct": {
            "value": 15,
            "rationale": "combined effect",
            "evidence_ref": ["audit.json:1"],
            "confidence": "low",
        }
    }

    assert _validate_param_wrapper(data, "total_discount_pct") == []


def test_zone_j_agent_wrapper_validation_accepts_legacy_numeric():
    data = {"total_discount_pct": 15}

    assert _validate_param_wrapper(data, "total_discount_pct") == []
