"""Engine selection for the voice agent.

Default is $0-safe: with no ANTHROPIC_API_KEY set, the offline mock
engine runs and no API calls are made. Set a key (or KEDS_LLM_MODE=real)
to route through the real Claude engine.
"""
import os
import sqlite3


def engine_mode() -> str:
    """'real' or 'mock'."""
    forced = os.environ.get("KEDS_LLM_MODE", "auto").lower()
    if forced in ("real", "mock"):
        return forced
    return "real" if os.environ.get("ANTHROPIC_API_KEY") else "mock"


def run_turn(conn: sqlite3.Connection, caller_phone: str, history: list[dict], user_message: str) -> dict:
    if engine_mode() == "real":
        try:
            from app.agent import llm
            return llm.run_turn(conn, caller_phone, history, user_message)
        except Exception as exc:
            # Never hard-fail the call: fall back to mock and surface why.
            from app.agent import mock
            result = mock.run_turn(conn, caller_phone, history, user_message)
            result["engine"] = f"mock (fell back: {type(exc).__name__})"
            return result
    from app.agent import mock
    return mock.run_turn(conn, caller_phone, history, user_message)
