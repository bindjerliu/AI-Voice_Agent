"""Tools the voice agent can call.

These are the agent's "hands": each maps to a mock KEDS backend
operation (customer lookup, outage status, filing a report). Both the
real Claude loop and the offline mock engine call the same executors
here, so behaviour is identical regardless of engine.

In production these executors would call KEDS's real billing API and
OMS instead of the local SQLite tables.
"""
import json
import sqlite3

from app.lib.constants import AREAS
from app.lib.matching import get_active_outage
from app.lib.reports import create_pending_report

# Tool schemas passed to the Claude Messages API (tool use).
TOOL_SCHEMAS = [
    {
        "name": "get_customer",
        "description": (
            "Look up a KEDS customer's account by phone number. Returns their name, "
            "service area/feeder, account balance in EUR (negative = amount owed), and "
            "meter number. Use the caller's own phone number unless they give another."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Phone number in +383... format"}
            },
            "required": ["phone"],
        },
    },
    {
        "name": "get_area_outage_status",
        "description": (
            "Check whether there is a known/confirmed power outage in a service area. "
            "Returns whether an outage is currently confirmed or in progress, its cause "
            "and estimated restoration time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {"type": "string", "description": f"One of the exact service areas: {AREAS}"}
            },
            "required": ["area"],
        },
    },
    {
        "name": "file_outage_report",
        "description": (
            "File a customer's report of a power outage that is NOT yet confirmed by KEDS. "
            "Stores their number so they get an SMS once a technician confirms an outage in "
            "that area. If an outage is already confirmed there, it matches immediately. "
            "Only call this after get_area_outage_status shows no active outage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Caller's phone number"},
                "area": {"type": "string", "description": f"One of the exact service areas: {AREAS}"},
                "consent_to_sms": {
                    "type": "boolean",
                    "description": "Whether the customer consents to receive an SMS notification",
                },
            },
            "required": ["phone", "area"],
        },
    },
]


def get_customer(conn: sqlite3.Connection, phone: str) -> dict:
    row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
    if row is None:
        return {"found": False, "phone": phone}
    return {
        "found": True,
        "id": row["id"],
        "name": row["name"],
        "area": row["area"],
        "balance_eur": row["balance"],
        "meter_number": row["meter_number"],
    }


def get_area_outage_status(conn: sqlite3.Connection, area: str) -> dict:
    if area not in AREAS:
        return {"valid_area": False, "area": area, "valid_areas": AREAS}
    outage = get_active_outage(conn, area)
    if outage is None:
        return {"valid_area": True, "area": area, "active": False}
    return {
        "valid_area": True,
        "area": area,
        "active": True,
        "status": outage["status"],
        "cause": outage["cause"],
        "eta": outage["eta"],
    }


def file_outage_report(conn: sqlite3.Connection, phone: str, area: str, consent_to_sms: bool = True) -> dict:
    if area not in AREAS:
        return {"valid_area": False, "area": area, "valid_areas": AREAS}
    report, matched_outage = create_pending_report(conn, phone, area, consent_to_sms)
    return {
        "valid_area": True,
        "area": area,
        "report_id": report["id"],
        "immediate_match": matched_outage is not None,
        "expires_at": report["expires_at"],
        "cause": matched_outage["cause"] if matched_outage else None,
        "eta": matched_outage["eta"] if matched_outage else None,
    }


_EXECUTORS = {
    "get_customer": lambda conn, i: get_customer(conn, i["phone"]),
    "get_area_outage_status": lambda conn, i: get_area_outage_status(conn, i["area"]),
    "file_outage_report": lambda conn, i: file_outage_report(
        conn, i["phone"], i["area"], i.get("consent_to_sms", True)
    ),
}


def run_tool(conn: sqlite3.Connection, name: str, tool_input: dict) -> dict:
    """Dispatch a tool call by name. Returns a JSON-serialisable dict."""
    executor = _EXECUTORS.get(name)
    if executor is None:
        return {"error": f"unknown tool {name}"}
    try:
        return executor(conn, tool_input)
    except Exception as exc:  # surface tool errors back to the model rather than 500
        return {"error": str(exc)}


def result_to_content(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)
