from __future__ import annotations

import json
import sqlite3

from scripts import enterprise_judgment_round10_appliance_v2_control as control
from scripts import enterprise_judgment_round10_external_review as review


def _terminal_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    control.freeze_preoutcome_batch(conn)
    rows = conn.execute(
        """SELECT measurement_contract_id, measurement_contract_version, company_id, metric_id
           FROM minimal_historical_measurement_contracts
           ORDER BY company_id, metric_id"""
    ).fetchall()
    for index, (contract_id, version, company_id, metric_id) in enumerate(rows):
        mismatch = company_id == "CN:002508"
        inventory_status = "MEASUREMENT_MISMATCH" if mismatch else "FIELD_READY"
        conn.execute(
            """INSERT INTO minimal_historical_outcome_source_inventory
               (inventory_receipt_id, measurement_contract_id, measurement_contract_version, custodian_id, status, payload_json, inventoried_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"INV:{index}", contract_id, version, "ROLE:ROUND10:TEST_CUSTODIAN", inventory_status,
             json.dumps({"status": inventory_status}), f"2026-08-27T00:00:{index:02d}+00:00"),
        )
        if not mismatch:
            conn.execute(
                """INSERT INTO minimal_historical_observations
                   (observation_id, measurement_contract_id, measurement_contract_version, custodian_id, payload_json, observed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (f"OBS:{index}", contract_id, version, "ROLE:ROUND10:TEST_CUSTODIAN", "{}", f"2026-08-27T00:01:{index:02d}+00:00"),
            )
            conn.execute(
                """INSERT INTO minimal_historical_settlements
                   (settlement_id, measurement_contract_id, measurement_contract_version, payload_json, settled_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (f"SET:{index}", contract_id, version, json.dumps({"status": "MATCH"}), f"2026-08-27T00:02:{index:02d}+00:00"),
            )
    conn.commit()
    return conn


def test_external_review_accepts_exact_nine_field_terminal_lifecycle_without_values() -> None:
    conn = _terminal_database()
    try:
        bundle = review.review_database(conn)
    finally:
        conn.close()
    assert bundle["terminal"]["valid"], bundle["terminal"]["findings"]
    assert bundle["terminal"]["mechanically_settled_field_count"] == 6
    assert bundle["terminal"]["measurement_mismatch_field_count"] == 3
    assert [row["terminal_state"] for row in bundle["terminal"]["company_summaries"]] == [
        "MECHANICALLY_SETTLED", "MEASUREMENT_MISMATCH", "MECHANICALLY_SETTLED",
    ]
    assert bundle["review"]["review_status"] == "NO_MATERIAL_UTILITY"
    assert bundle["review"]["accepted_treatment_delta_ids"] == []
    assert bundle["candidate"]["treatment_delta_ledger"][0]["method_advantage_count"] == 1
    assert bundle["completion"]["completion_status"] == "ROUND10_COMPLETE_NO_METHOD_TRANSFER"


def test_external_review_rejects_a_missing_settlement_as_nonterminal() -> None:
    conn = _terminal_database()
    try:
        contract_id = conn.execute(
            """SELECT measurement_contract_id FROM minimal_historical_measurement_contracts
               WHERE company_id = 'CN:002035' ORDER BY metric_id LIMIT 1"""
        ).fetchone()[0]
        conn.execute("DELETE FROM minimal_historical_settlements WHERE measurement_contract_id = ?", (contract_id,))
        conn.commit()
        terminal = review.inspect_terminal_batch(conn)
    finally:
        conn.close()
    assert not terminal["valid"]
    assert "round10_review_terminal_state_invalid:CN:002035" in terminal["findings"]
    assert "round10_review_contains_nonterminal_field" in terminal["findings"]


def test_external_bundle_keeps_rights_closed_and_uses_existing_round10_validator() -> None:
    conn = _terminal_database()
    try:
        bundle = review.review_database(conn)
    finally:
        conn.close()
    result = review.validate_external_review_bundle(bundle)
    assert result["valid"], result["findings"]
    assert bundle["review"]["rights"]["method_transfer"] == "NOT_AUTHORIZED"
    assert bundle["completion"]["rights"]["investment"] == "NOT_AUTHORIZED"
