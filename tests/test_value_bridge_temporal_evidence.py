from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.evidence_facts import (
    _observation_core,
    _payload_hash,
    make_observation_id,
    validate_fact_observations,
    verify_fact_from_quote,
)
from scripts.valuation_model_gate import (
    _bridge_numeric_leaves,
    _bridge_operand_context,
    _bridge_path_nodes,
    _validate_value_bridge_fact_bindings,
)
from scripts.valuation_value_bridges import compile_valuation_value_bridges
from tests.test_valuation_value_bridges import _cash_input


POSITION_DATE = "2025-12-31"
CUTOFF_DATE = "2026-08-11"
EVENT_DATE = "2026-05-28"
EVENT_OBSERVED_AT = "2026-06-01"
ROOT = Path(__file__).resolve().parents[1]


def _document(doc_id: str, period_end: str, published_at: str) -> dict:
    return {
        "doc_id": doc_id,
        "period_end": period_end,
        "published_at": published_at,
    }


def _temporal_cash_fixture() -> tuple[dict, dict, dict]:
    cash = deepcopy(_cash_input())
    cash["cutoff_at"] = CUTOFF_DATE
    cash["position_as_of"] = POSITION_DATE
    for period in cash["realization_periods"]:
        year = period["period_id"]
        period["period_start"] = f"{year}-01-01"
        period["period_end"] = f"{year}-12-31"

    bridge_input = {
        "schema_version": "valuation-value-bridges-input.v1",
        "cash_accessibility": {
            "model_input": cash,
            "valuation_context": {
                "company_id": "TEST.HK",
                "operating_model_id": "EPV:TEST",
                "position_as_of": POSITION_DATE,
                "ordinary_share_claim_scope": "Listed ordinary common shares",
                "valuation_currency": "RMB",
                "fx_source_per_valuation_currency": 1,
                "shares": 100,
                "source_fact_ids": [],
            },
        },
    }
    documents = {
        "DOC:FY2023": _document("DOC:FY2023", "2023-12-31", "2024-03-31"),
        "DOC:FY2024": _document("DOC:FY2024", "2024-12-31", "2025-03-31"),
        "DOC:FY2025": _document("DOC:FY2025", POSITION_DATE, "2026-03-31"),
        # The announcement retains the balance-sheet reference period while
        # the exact-quote observation owns its later realized-event clock.
        "DOC:EVENT": _document("DOC:EVENT", POSITION_DATE, EVENT_OBSERVED_AT),
    }

    observations: list[dict] = []
    bindings: list[dict[str, str]] = []
    numeric_leaves = _bridge_numeric_leaves(bridge_input)
    for index, (path, value) in enumerate(sorted(numeric_leaves.items())):
        evidence_id = f"OBS:TEMPORAL:{index:03d}"
        nodes = _bridge_path_nodes(bridge_input, path)
        owner = next(
            node for node in reversed(nodes)
            if isinstance(node.get("source_fact_ids"), list)
        )
        owner["source_fact_ids"].append(evidence_id)
        cash["verified_facts"].append(
            {"fact_id": evidence_id, "status": "VERIFIED"}
        )
        context = _bridge_operand_context(bridge_input, path)
        role = context["temporal_role"]
        if role == "HISTORICAL_PERIOD":
            as_of = context["period_end"]
            doc_id = "DOC:FY" + as_of[:4]
            measurement_context = {
                "period_start": context["period_start"],
                "period_end": context["period_end"],
            }
            temporal_fields = {}
        elif role == "EVENT":
            as_of = EVENT_DATE
            doc_id = "DOC:EVENT"
            measurement_context = {}
            temporal_fields = {
                "event_date": EVENT_DATE,
                "observed_at": EVENT_OBSERVED_AT,
            }
        else:
            as_of = POSITION_DATE
            doc_id = "DOC:FY2025"
            measurement_context = {}
            temporal_fields = {}
        observations.append(
            {
                "observation_id": evidence_id,
                "fact_name": path,
                "normalized_value": value,
                "unit": context["unit"],
                "currency": context["currency"] or None,
                "as_of": as_of,
                "temporal_role": role,
                "measurement_context": measurement_context,
                "doc_id": doc_id,
                "status": "VERIFIED",
                **temporal_fields,
            }
        )
        bindings.append({"path": path, "evidence_id": evidence_id})
    bridge_input["canonical_fact_bindings"] = bindings
    fact_registry = {
        "report_id": "",
        "observations": observations,
    }
    manifest = {"documents": list(documents.values())}
    return bridge_input, fact_registry, manifest


def _validate(output: Path, bridge_input: dict) -> tuple[list[str], list[str]]:
    payload = {"value_bridge_models": compile_valuation_value_bridges(bridge_input)}
    invalid: list[str] = []
    incomplete: list[str] = []
    _validate_value_bridge_fact_bindings(
        payload,
        output,
        required=True,
        invalid=invalid,
        incomplete=incomplete,
    )
    return invalid, incomplete


def _write_registries(output: Path, facts: dict, manifest: dict) -> None:
    (output / "fact_observations.json").write_text(
        json.dumps(facts), encoding="utf-8"
    )
    (output / "document_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (output / "calculation_observations.json").write_text(
        json.dumps({"calculations": []}), encoding="utf-8"
    )


def _complete_observation(
    *,
    fact_name: str,
    as_of: str,
    doc_id: str,
    temporal_role: str | None = None,
    measurement_context: dict | None = None,
    event_date: str | None = None,
    observed_at: str | None = None,
) -> dict:
    observation = {
        "observation_id": "",
        "fact_name": fact_name,
        "domain": "financial",
        "raw_value": 10,
        "normalized_value": 10,
        "unit": "RMB_m",
        "currency": "RMB",
        "basis": "fixture",
        "as_of": as_of,
        "doc_id": doc_id,
        "locator": {
            "page": 1,
            "section": "financial",
            "table": None,
            "row": None,
            "column": None,
            "char": None,
        },
        "raw_text": "fixture value 10",
        "extraction_method": "exact_quote_programmatic_verification",
        "status": "VERIFIED",
        "confidence": 0.98,
        "conflict_ids": [],
    }
    if temporal_role is not None:
        observation["temporal_role"] = temporal_role
    if measurement_context is not None:
        observation["measurement_context"] = measurement_context
    if event_date is not None:
        observation["event_date"] = event_date
    if observed_at is not None:
        observation["observed_at"] = observed_at
    observation["observation_id"] = make_observation_id(observation)
    return observation


def _fact_temporal_payload() -> tuple[dict, dict]:
    manifest_hash = "a" * 64
    manifest = {
        "manifest_hash": manifest_hash,
        "documents": [
            {
                "doc_id": "DOC:ANNUAL",
                "period_end": "2025-12-31",
                "published_at": "2026-03-31",
                "authority": "audited_filing",
            },
            {
                "doc_id": "DOC:EVENT",
                "period_end": "2025-12-31",
                "published_at": EVENT_OBSERVED_AT,
                "authority": "company_filing",
            },
        ],
    }
    observations = [
        _complete_observation(
            fact_name="legacy_position",
            as_of="2025-12-31",
            doc_id="DOC:ANNUAL",
        ),
        _complete_observation(
            fact_name="historical_distribution",
            as_of="2024-12-31",
            doc_id="DOC:ANNUAL",
            temporal_role="HISTORICAL_PERIOD",
            measurement_context={
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
            },
        ),
        _complete_observation(
            fact_name="post_position_collection",
            as_of=EVENT_DATE,
            doc_id="DOC:EVENT",
            temporal_role="EVENT",
            event_date=EVENT_DATE,
            observed_at=EVENT_OBSERVED_AT,
        ),
    ]
    payload = {
        "schema_version": "fact-observations.v1",
        "report_id": "REPORT:TEST",
        "manifest_hash": manifest_hash,
        "observations": observations,
    }
    payload["observation_hash"] = _payload_hash(_observation_core(payload))
    return payload, manifest


def test_fact_validator_accepts_legacy_period_and_explicit_event_clocks() -> None:
    payload, manifest = _fact_temporal_payload()
    payload["validation"] = validate_fact_observations(payload, manifest)

    assert payload["validation"]["state"] == "REVIEWABLE"


def test_fact_schema_accepts_legacy_period_and_explicit_event_clocks() -> None:
    schema = json.loads(
        (ROOT / "schemas/fact_observations.schema.json").read_text(encoding="utf-8")
    )

    observation_schema = schema["$defs"]["observation"]
    assert observation_schema["properties"]["temporal_role"]["enum"] == [
        "POSITION_AS_OF",
        "HISTORICAL_PERIOD",
        "EVENT",
    ]
    assert observation_schema["properties"]["event_date"]["type"] == "string"
    assert observation_schema["properties"]["observed_at"]["type"] == "string"
    assert len(observation_schema["allOf"]) == 2


def test_event_fact_requires_its_own_observation_clock_and_document_publication() -> None:
    payload, manifest = _fact_temporal_payload()
    event = payload["observations"][-1]
    event.pop("observed_at")
    event["observation_id"] = make_observation_id(event)
    payload["observation_hash"] = _payload_hash(_observation_core(payload))

    validation = validate_fact_observations(payload, manifest)

    assert validation["state"] == "INVALID"
    assert any(
        "event_observed_at_missing_or_invalid" in finding
        for finding in validation["invalid_findings"]
    )


def test_exact_quote_event_uses_event_clock_instead_of_document_period_end(
    tmp_path: Path,
) -> None:
    source = tmp_path / "announcement.pages.md"
    source.write_text(
        "## 第 1 页\n\n期末后已收回关联方款项人民币20百万元。\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "document-manifest.v1",
        "report_id": "REPORT:TEST",
        "manifest_hash": "b" * 64,
        "documents": [
            {
                "doc_id": "DOC:EVENT",
                "period_end": POSITION_DATE,
                "published_at": EVENT_OBSERVED_AT,
                "authority": "company_filing",
                "derived_text_path": source.name,
            }
        ],
    }
    (tmp_path / "document_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    result = verify_fact_from_quote(
        tmp_path,
        doc_id="DOC:EVENT",
        page=1,
        fact_name="related_party_collection_after_position",
        domain="financial",
        raw_value=20,
        normalized_value=20,
        unit="RMB_m",
        basis="cash_received_after_balance_sheet_date",
        quote="期末后已收回关联方款项人民币20百万元。",
        currency="RMB",
        temporal_role="EVENT",
        event_date=EVENT_DATE,
        observed_at=EVENT_OBSERVED_AT,
    )

    assert result["verified"] is True
    observation = result["observation"]
    assert observation["as_of"] == observation["event_date"] == EVENT_DATE
    assert observation["as_of"] != manifest["documents"][0]["period_end"]


def test_three_historical_annual_periods_and_one_post_position_event_share_one_cash_model(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    _write_registries(tmp_path, facts, manifest)

    invalid, incomplete = _validate(tmp_path, bridge_input)

    assert invalid == []
    assert incomplete == []
    announcement = next(
        item for item in manifest["documents"] if item["doc_id"] == "DOC:EVENT"
    )
    event_observation = next(
        item for item in facts["observations"] if item["temporal_role"] == "EVENT"
    )
    assert announcement["period_end"] == POSITION_DATE
    assert POSITION_DATE < announcement["published_at"] <= CUTOFF_DATE
    assert event_observation["as_of"] == event_observation["event_date"] == EVENT_DATE
    assert event_observation["observed_at"] == announcement["published_at"]
    model = compile_valuation_value_bridges(bridge_input)["result"]["cash_accessibility"]
    assert [
        (period["period_start"], period["period_end"])
        for period in model["existing_excess_cash_realization"]["history"]
    ] == [
        ("2023-01-01", "2023-12-31"),
        ("2024-01-01", "2024-12-31"),
        ("2025-01-01", "2025-12-31"),
    ]
    assert model["related_party_receivable_realization"][
        "post_position_collections"
    ] == 20


def test_cash_realization_history_cannot_omit_its_model_period_bounds(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    first_period = bridge_input["cash_accessibility"]["model_input"][
        "realization_periods"
    ][0]
    first_period.pop("period_start")
    first_period.pop("period_end")
    _write_registries(tmp_path, facts, manifest)

    invalid, _ = _validate(tmp_path, bridge_input)

    assert "value_bridge_cash_realization_period_bounds_missing:0" in invalid


def test_same_post_position_announcement_moved_after_cutoff_is_blocked(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    event_document = next(
        item for item in manifest["documents"] if item["doc_id"] == "DOC:EVENT"
    )
    event_document["published_at"] = "2026-08-12"
    event_observation = next(
        item for item in facts["observations"] if item["temporal_role"] == "EVENT"
    )
    event_observation["observed_at"] = "2026-08-12"
    _write_registries(tmp_path, facts, manifest)

    invalid, incomplete = _validate(tmp_path, bridge_input)

    assert incomplete == []
    assert any("published_at_after_cutoff" in finding for finding in invalid)
    assert any("observed_at_after_cutoff" in finding for finding in invalid)


def test_historical_fact_cannot_be_relabelled_as_the_current_position_date(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    historical = next(
        item
        for item in facts["observations"]
        if item["temporal_role"] == "HISTORICAL_PERIOD"
        and item["as_of"] == "2023-12-31"
    )
    historical["as_of"] = POSITION_DATE
    _write_registries(tmp_path, facts, manifest)

    invalid, _ = _validate(tmp_path, bridge_input)

    assert any("as_of_mismatch" in finding for finding in invalid)


def test_post_position_collection_cannot_masquerade_as_a_balance_sheet_stock(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    event = next(
        item for item in facts["observations"] if item["temporal_role"] == "EVENT"
    )
    event["temporal_role"] = "POSITION_AS_OF"
    event["as_of"] = POSITION_DATE
    event.pop("event_date")
    event.pop("observed_at")
    _write_registries(tmp_path, facts, manifest)

    invalid, _ = _validate(tmp_path, bridge_input)

    assert any("temporal_role_mismatch" in finding for finding in invalid)
