"""Read-only customer lookups.

Production equivalent: these would call KEDS's real billing/CRM system
(customer master data + balance ledger) instead of a local SQLite
table. The IVR/agent would never write to that system directly -
lookups only.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.lib.audit import log

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _customer_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "area": row["area"],
        "meter_number": row["meter_number"],
        "balance": row["balance"],
    }


@router.get("")
def list_customers(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM customers ORDER BY area, name").fetchall()
    return [_customer_to_dict(r) for r in rows]


@router.get("/lookup")
def lookup_customer(
    phone: str | None = Query(default=None),
    account: int | None = Query(default=None, description="customer id"),
    conn: sqlite3.Connection = Depends(get_db),
):
    if not phone and not account:
        raise HTTPException(status_code=400, detail="Provide phone or account")

    if account is not None:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (account,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()

    log(conn, actor="ivr", action="customer_lookup", details={"phone": phone, "account": account, "found": row is not None})

    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _customer_to_dict(row)


@router.get("/{customer_id}/balance")
def get_balance(customer_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT id, name, balance FROM customers WHERE id = ?", (customer_id,)).fetchone()
    log(conn, actor="ivr", action="balance_lookup", details={"customer_id": customer_id, "found": row is not None})
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"id": row["id"], "name": row["name"], "balance": row["balance"]}
