from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.evidence_facts import (
    _observation_core,
    _payload_hash,
    make_observation_id,
    validate_fact_observations,
    verify_fact_from_quote,
)
from scripts.evidence_documents import build_document_manifest
from scripts.valuation_model_gate import (
    _bridge_numeric_leaves,
    _bridge_operand_context,
    _bridge_path_nodes,
    _validate_value_bridge_fact_bindings,
)
from scripts.valuation_value_bridges import compile_valuation_value_bridges
from tests.test_cash_accessibility_model import _bind_to_canonical_official_facts
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
        period["opening_position_as_of"] = f"{year}-01-01"
        for event in period["extraordinary_events"]:
            event["observed_at"] = f"{int(year) + 1}-03-31"
    _bind_to_canonical_official_facts(cash)

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
            as_of = context.get("event_date") or EVENT_DATE
            observed_at = context.get("observed_at") or EVENT_OBSERVED_AT
            doc_id = (
                "DOC:FY" + as_of[:4]
                if context.get("event_date")
                else "DOC:EVENT"
            )
            measurement_context = {}
            temporal_fields = {
                "event_date": as_of,
                "observed_at": observed_at,
            }
        else:
            as_of = context["as_of"]
            if ".realization_periods[" in path:
                period_index = int(
                    path.split("realization_periods[", 1)[1].split("]", 1)[0]
                )
                doc_id = "DOC:FY" + cash["realization_periods"][period_index]["period_id"]
            else:
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
    observations.append(
        {
            "observation_id": "F:CONTINUITY",
            "fact_name": "cash_realization_mechanism_continuity",
            "normalized_value": True,
            "unit": "boolean",
            "currency": None,
            "as_of": POSITION_DATE,
            "temporal_role": "POSITION_AS_OF",
            "measurement_context": {},
            "doc_id": "DOC:FY2025",
            "status": "VERIFIED",
        }
    )
    outer_by_path = {item["path"]: item["evidence_id"] for item in bindings}
    cash_register = cash["official_fact_register"]
    for observation in observations:
        if not observation["observation_id"].startswith("OBS:TEMPORAL:"):
            continue
        path = observation["fact_name"]
        cash_register["observations"].append({
            "fact_id": observation["observation_id"],
            "source_id": "TEST-OFFICIAL-CASH",
            "pdf_page": 7,
            "table_or_section": "Temporal cash source table",
            "field": path,
            "period": "FY2025",
            "responsibility_boundary": (
                "Listed ordinary common shares" if path.endswith(".shares")
                else "listed consolidated issuer"
            ),
            "unit": observation["unit"],
            "value": observation["normalized_value"],
        })
    cash_register["observations"].append({
        "fact_id": "F:CONTINUITY",
        "source_id": "TEST-OFFICIAL-CASH",
        "pdf_page": 7,
        "table_or_section": "Temporal cash source table",
        "field": "cash_realization_mechanism_continuity",
        "period": "FY2025",
        "responsibility_boundary": "listed consolidated issuer",
        "unit": "boolean",
        "value": True,
    })
    for binding in cash["canonical_fact_bindings"]:
        path = binding["path"]
        if "realization_applicability." in path or ".prospective_applicability." in path:
            binding["fact_id"] = "F:CONTINUITY"
            continue
        outer_path = "cash_accessibility.model_input." + path
        if outer_path in outer_by_path:
            binding["fact_id"] = outer_by_path[outer_path]
    for applicability in cash["realization_applicability"].values():
        for key, value in applicability["source_fact_bindings"].items():
            if key in applicability and isinstance(applicability[key], bool):
                applicability["source_fact_bindings"][key] = "F:CONTINUITY"
    cash["verified_facts"].append({"fact_id": "F:CONTINUITY", "status": "VERIFIED"})
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


def _replace_cash_binding(
    bridge_input: dict, *, path: str, evidence_id: str
) -> float:
    binding = next(
        item for item in bridge_input["canonical_fact_bindings"]
        if item["path"] == path
    )
    binding["evidence_id"] = evidence_id
    owner = next(
        node for node in reversed(_bridge_path_nodes(bridge_input, path))
        if isinstance(node.get("source_fact_ids"), list)
    )
    owner["source_fact_ids"].append(evidence_id)
    cash = bridge_input["cash_accessibility"]["model_input"]
    cash["verified_facts"].append({"fact_id": evidence_id, "status": "VERIFIED"})
    return _bridge_numeric_leaves(bridge_input)[path]


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
            fact_name="opening_position_disclosed_later",
            as_of="2025-01-01",
            doc_id="DOC:ANNUAL",
            temporal_role="POSITION_AS_OF",
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
    opening = next(
        item for item in payload["observations"]
        if item["fact_name"] == "opening_position_disclosed_later"
    )
    assert opening["as_of"] != manifest["documents"][0]["period_end"]


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
    annual = tmp_path / "TEST_2025_年报.pdf"
    annual.write_bytes(b"%PDF-1.4\nfixture audited annual report\n")
    announcement = tmp_path / "TEST_2026-06-01_collection_announcement.pdf"
    announcement.write_bytes(b"%PDF-1.4\nfixture exchange announcement\n")
    source = tmp_path / "announcement.pages.md"
    source.write_text(
        "## 第 1 页\n\n2026年5月28日期末后已收回关联方款项人民币20百万元。\n",
        encoding="utf-8",
    )
    (tmp_path / "document_sources.json").write_text(
        json.dumps(
            {
                "schema_version": "document-sources.v1",
                "documents": {
                    announcement.name: {
                        "source_url": "https://www1.hkexnews.hk/fixture-event.pdf",
                        "published_at": EVENT_OBSERVED_AT,
                        "doc_type": "exchange_announcement",
                        "authority": "company_filing",
                        "fiscal_period": "POST-FY2025",
                        "period_end": POSITION_DATE,
                        "derived_text_path": source.name,
                        "verification_mode": "PAGE_QUOTE",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = build_document_manifest(tmp_path, "TEST.HK", persist=True)
    event_document = next(
        item
        for item in manifest["documents"]
        if item["doc_type"] == "exchange_announcement"
    )
    assert manifest["validation"]["state"] == "REVIEWABLE"

    result = verify_fact_from_quote(
        tmp_path,
        doc_id=event_document["doc_id"],
        page=1,
        fact_name="related_party_collection_after_position",
        domain="financial",
        raw_value=20,
        normalized_value=20,
        unit="RMB_m",
        basis="cash_received_after_balance_sheet_date",
        quote="2026年5月28日期末后已收回关联方款项人民币20百万元。",
        currency="RMB",
        temporal_role="EVENT",
        event_date=EVENT_DATE,
        observed_at=EVENT_OBSERVED_AT,
    )

    assert result["verified"] is True
    observation = result["observation"]
    assert observation["as_of"] == observation["event_date"] == EVENT_DATE
    assert observation["as_of"] != event_document["period_end"]


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
        item for item in facts["observations"]
        if item["fact_name"].endswith(".post_position_collections")
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
    assert model["existing_excess_cash_realization"]["realization_rate_range"] == {
        "low": pytest.approx(0.1),
        "base": pytest.approx(0.2),
        "high": pytest.approx(0.3),
    }
    assert model["future_retained_cash_realization"]["realization_rate_range"] == {
        "low": pytest.approx(0.2),
        "base": pytest.approx(0.4),
        "high": pytest.approx(0.6),
    }
    assert model["existing_excess_cash_realization"]["adopted_value"] == pytest.approx(7)
    assert model["future_retained_cash_realization"]["adopted_value"] == pytest.approx(16)


def test_cash_model_schema_exposes_each_realization_clock() -> None:
    schema = json.loads(
        (ROOT / "schemas/cash_accessibility_model.schema.json").read_text(
            encoding="utf-8"
        )
    )

    period = schema["$defs"]["realizationPeriod"]
    event = schema["$defs"]["extraordinaryEvent"]
    assert {
        "period_start", "period_end", "opening_position_as_of"
    }.issubset(period["required"])
    assert {"event_date", "observed_at"}.issubset(event["required"])


@pytest.mark.parametrize(
    ("path_fragment", "expected_role", "wrong_role"),
    [
        (".opening_existing_excess_cash", "POSITION_AS_OF", "HISTORICAL_PERIOD"),
        (".retained_cash_generated", "HISTORICAL_PERIOD", "POSITION_AS_OF"),
        (".ordinary_dividend", "HISTORICAL_PERIOD", "POSITION_AS_OF"),
        (".extraordinary_events[0].amount", "EVENT", "HISTORICAL_PERIOD"),
    ],
)
def test_cash_realization_fact_roles_cannot_be_swapped(
    tmp_path: Path,
    path_fragment: str,
    expected_role: str,
    wrong_role: str,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    binding = next(
        item for item in bridge_input["canonical_fact_bindings"]
        if path_fragment in item["path"]
    )
    observation = next(
        item for item in facts["observations"]
        if item["observation_id"] == binding["evidence_id"]
    )
    assert observation["temporal_role"] == expected_role
    observation["temporal_role"] = wrong_role
    _write_registries(tmp_path, facts, manifest)

    invalid, _ = _validate(tmp_path, bridge_input)

    assert any("temporal_role_mismatch" in finding for finding in invalid)


def test_fake_calculation_cannot_bind_a_cash_temporal_operand(tmp_path: Path) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    path = next(
        item["path"] for item in bridge_input["canonical_fact_bindings"]
        if item["path"].endswith(".opening_existing_excess_cash")
    )
    _replace_cash_binding(bridge_input, path=path, evidence_id="CALC:FAKE:CASH")
    _write_registries(tmp_path, facts, manifest)

    with pytest.raises(ValueError, match="fact_id_not_canonical_official_observation"):
        compile_valuation_value_bridges(bridge_input)


def test_renamed_non_calc_registry_row_cannot_bind_cash_temporal_operand(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    path = next(
        item["path"] for item in bridge_input["canonical_fact_bindings"]
        if item["path"].endswith(".opening_existing_excess_cash")
    )
    calculation_id = "DERIVED:CASH:RENAMED"
    value = _replace_cash_binding(
        bridge_input, path=path, evidence_id=calculation_id
    )
    _write_registries(tmp_path, facts, manifest)
    (tmp_path / "calculation_observations.json").write_text(
        json.dumps(
            {
                "calculations": [{
                    "calculation_id": calculation_id,
                    "tool": "compute_gg",
                    "metric_path": "synthetic.renamed_cash",
                    "value": value,
                    "unit": "million",
                    "status": "VERIFIED",
                }]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fact_id_not_canonical_official_observation"):
        compile_valuation_value_bridges(bridge_input)


def test_non_observation_identifier_cannot_bind_cash_temporal_operand(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    path = next(
        item["path"] for item in bridge_input["canonical_fact_bindings"]
        if item["path"].endswith(".retained_cash_generated")
    )
    _replace_cash_binding(
        bridge_input, path=path, evidence_id="DERIVED:CASH:UNREGISTERED"
    )
    _write_registries(tmp_path, facts, manifest)

    with pytest.raises(ValueError, match="fact_id_not_canonical_official_observation"):
        compile_valuation_value_bridges(bridge_input)


def test_verified_calculation_without_temporal_lineage_cannot_bind_cash_operand(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    path = next(
        item["path"] for item in bridge_input["canonical_fact_bindings"]
        if item["path"].endswith(".retained_cash_generated")
    )
    calculation_id = "CALC:VERIFIED:NO-TEMPORAL-LINEAGE"
    value = _replace_cash_binding(
        bridge_input, path=path, evidence_id=calculation_id
    )
    _write_registries(tmp_path, facts, manifest)
    (tmp_path / "calculation_observations.json").write_text(
        json.dumps(
            {
                "calculations": [{
                    "calculation_id": calculation_id,
                    "tool": "compute_gg",
                    "metric_path": "synthetic.cash",
                    "value": value,
                    "unit": "million",
                    "status": "VERIFIED",
                }]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fact_id_not_canonical_official_observation"):
        compile_valuation_value_bridges(bridge_input)


def test_old_observation_derived_calculation_cannot_relabel_cash_time(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    path = next(
        item["path"] for item in bridge_input["canonical_fact_bindings"]
        if ".extraordinary_events[0].amount" in item["path"]
    )
    calculation_id = "CALC:DERIVED:OLD-OBSERVATION"
    value = _replace_cash_binding(
        bridge_input, path=path, evidence_id=calculation_id
    )
    _write_registries(tmp_path, facts, manifest)
    (tmp_path / "calculation_observations.json").write_text(
        json.dumps(
            {
                "calculations": [{
                    "calculation_id": calculation_id,
                    "tool": "compute_gg",
                    "metric_path": "synthetic.cash_from_old_observation",
                    "value": value,
                    "unit": "million",
                    "status": "VERIFIED",
                    "input_observation_ids": ["OBS:OLD:2022"],
                    "input_temporal_context": {"as_of": "2022-12-31"},
                }]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fact_id_not_canonical_official_observation"):
        compile_valuation_value_bridges(bridge_input)


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

    with pytest.raises(ValueError, match="period_bounds_missing"):
        compile_valuation_value_bridges(bridge_input)


def test_same_post_position_announcement_moved_after_cutoff_is_blocked(
    tmp_path: Path,
) -> None:
    bridge_input, facts, manifest = _temporal_cash_fixture()
    event_document = next(
        item for item in manifest["documents"] if item["doc_id"] == "DOC:EVENT"
    )
    event_document["published_at"] = "2026-08-12"
    event_observation = next(
        item for item in facts["observations"]
        if item["fact_name"].endswith(".post_position_collections")
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
        item for item in facts["observations"]
        if item["fact_name"].endswith(".post_position_collections")
    )
    event["temporal_role"] = "POSITION_AS_OF"
    event["as_of"] = POSITION_DATE
    event.pop("event_date")
    event.pop("observed_at")
    _write_registries(tmp_path, facts, manifest)

    invalid, _ = _validate(tmp_path, bridge_input)

    assert any("temporal_role_mismatch" in finding for finding in invalid)
