"""Accounts/cash service — deposit, withdraw, and cash management.

Port of Android CashRepository semantics against portfolio.db cash + cash_flow tables.
All mutations are atomic (single SQLite transaction).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from niangao.db import get_db, _DB_PATH


class AccountsError(RuntimeError):
    """Raised when an account/cash operation cannot complete."""


@dataclass
class CashResult:
    account_id: int
    currency: str
    previous_amount: float
    delta: float
    new_amount: float


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ensure_cash_row(db, currency: str, account_id: int) -> None:
    row = db.execute(
        "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
        (currency, account_id),
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO cash (currency, account_id, amount, last_updated) VALUES (?, ?, 0, ?)",
            (currency, account_id, _now_ms()),
        )


def _record_cash_flow(
    db, account_id: int, currency: str, delta: float, delta_cny: float, note: str,
) -> None:
    db.execute(
        """INSERT INTO cash_flow (account_id, currency, delta_amount, delta_cny, note, flow_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (account_id, currency, delta, delta_cny, note, _now_ms()),
    )


# ── Public API ───────────────────────────────────────────────────────

def get_balance(
    currency: str = "CNY",
    account_id: int = 1,
    db_path: str = _DB_PATH,
) -> float:
    """Read current cash balance for a currency/account pair."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
            (currency, account_id),
        ).fetchone()
        return row[0] if row else 0.0
    finally:
        db.close()


def list_balances(
    account_id: int | None = None,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """List all cash balances, optionally filtered by account."""
    db = get_db(db_path)
    try:
        if account_id is not None:
            rows = db.execute(
                "SELECT * FROM cash WHERE account_id = ? ORDER BY currency", (account_id,),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM cash ORDER BY account_id, currency").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def list_accounts(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """List all accounts."""
    db = get_db(db_path)
    try:
        return [dict(r) for r in db.execute("SELECT * FROM account ORDER BY id").fetchall()]
    finally:
        db.close()


def deposit(
    *,
    amount: float,
    currency: str = "CNY",
    account_id: int = 1,
    note: str = "",
    db_path: str = _DB_PATH,
) -> CashResult:
    """Deposit (add) cash to an account. Atomic.

    Args:
        amount: Positive amount to add (in the currency unit, not necessarily CNY)
        currency: Currency code (CNY, HKD, USD)
        account_id: Target account ID
        note: Description for cash_flow record
        db_path: Override DB path

    Raises:
        AccountsError: If amount <= 0.
    """
    if amount <= 0:
        raise AccountsError(f"Deposit amount must be > 0, got {amount}")

    db = get_db(db_path)
    try:
        _ensure_cash_row(db, currency, account_id)
        prev = db.execute(
            "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
            (currency, account_id),
        ).fetchone()[0]

        db.execute(
            "UPDATE cash SET amount = amount + ?, last_updated = ? WHERE currency = ? AND account_id = ?",
            (amount, _now_ms(), currency, account_id),
        )
        # For deposit in native currency, delta_cny = delta_amount (simplified;
        # a full implementation would use exchange rates)
        _record_cash_flow(
            db, account_id, currency, amount, amount,
            note or f"存入 {amount} {currency}",
        )
        db.commit()
        return CashResult(
            account_id=account_id, currency=currency,
            previous_amount=prev, delta=amount, new_amount=prev + amount,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def withdraw(
    *,
    amount: float,
    currency: str = "CNY",
    account_id: int = 1,
    note: str = "",
    allow_overdraft: bool = False,
    db_path: str = _DB_PATH,
) -> CashResult:
    """Withdraw (subtract) cash from an account. Atomic.

    Args:
        amount: Positive amount to withdraw
        currency: Currency code
        account_id: Account ID
        note: Description
        allow_overdraft: If False (default), raises AccountsError on insufficient funds
        db_path: Override DB path

    Raises:
        AccountsError: If amount <= 0 or insufficient funds.
    """
    if amount <= 0:
        raise AccountsError(f"Withdraw amount must be > 0, got {amount}")

    db = get_db(db_path)
    try:
        _ensure_cash_row(db, currency, account_id)
        prev = db.execute(
            "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
            (currency, account_id),
        ).fetchone()[0]

        if not allow_overdraft and prev < amount:
            raise AccountsError(
                f"Insufficient funds: {currency} balance {prev:.2f}, "
                f"trying to withdraw {amount:.2f}"
            )

        db.execute(
            "UPDATE cash SET amount = amount - ?, last_updated = ? WHERE currency = ? AND account_id = ?",
            (amount, _now_ms(), currency, account_id),
        )
        _record_cash_flow(
            db, account_id, currency, -amount, -amount,
            note or f"取出 {amount} {currency}",
        )
        db.commit()
        return CashResult(
            account_id=account_id, currency=currency,
            previous_amount=prev, delta=-amount, new_amount=prev - amount,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def transfer(
    *,
    from_account_id: int,
    to_account_id: int,
    amount: float,
    currency: str = "CNY",
    note: str = "",
    db_path: str = _DB_PATH,
) -> tuple[CashResult, CashResult]:
    """Transfer cash between two accounts. Atomic (both sides succeed or roll back).

    Returns (from_result, to_result).
    """
    if amount <= 0:
        raise AccountsError(f"Transfer amount must be > 0, got {amount}")
    if from_account_id == to_account_id:
        raise AccountsError("Source and destination accounts must differ")

    db = get_db(db_path)
    try:
        # Ensure both cash rows exist
        _ensure_cash_row(db, currency, from_account_id)
        _ensure_cash_row(db, currency, to_account_id)

        from_prev = db.execute(
            "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
            (currency, from_account_id),
        ).fetchone()[0]
        if from_prev < amount:
            raise AccountsError(
                f"Insufficient funds: account {from_account_id} {currency} "
                f"balance {from_prev:.2f}, need {amount:.2f}"
            )

        to_prev = db.execute(
            "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
            (currency, to_account_id),
        ).fetchone()[0]

        now = _now_ms()
        db.execute(
            "UPDATE cash SET amount = amount - ?, last_updated = ? WHERE currency = ? AND account_id = ?",
            (amount, now, currency, from_account_id),
        )
        db.execute(
            "UPDATE cash SET amount = amount + ?, last_updated = ? WHERE currency = ? AND account_id = ?",
            (amount, now, currency, to_account_id),
        )

        transfer_note = note or f"转账 {amount} {currency} 账户{from_account_id}→{to_account_id}"
        _record_cash_flow(db, from_account_id, currency, -amount, -amount, transfer_note)
        _record_cash_flow(db, to_account_id, currency, amount, amount, transfer_note)

        db.commit()
        return (
            CashResult(account_id=from_account_id, currency=currency,
                       previous_amount=from_prev, delta=-amount,
                       new_amount=from_prev - amount),
            CashResult(account_id=to_account_id, currency=currency,
                       previous_amount=to_prev, delta=amount,
                       new_amount=to_prev + amount),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_cash_flow_history(
    account_id: int | None = None,
    limit: int = 100,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """Return recent cash flow entries, newest first."""
    db = get_db(db_path)
    try:
        if account_id is not None:
            rows = db.execute(
                "SELECT * FROM cash_flow WHERE account_id = ? ORDER BY flow_at DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM cash_flow ORDER BY flow_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
