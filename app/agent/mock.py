"""Offline rule-based voice agent (no LLM, no API calls, no cost).

Used automatically when no ANTHROPIC_API_KEY is configured. It keys off
keywords, calls the SAME tool executors as the real engine, and returns
canned Standard Albanian replies. It is not conversational — it stands
in so the pending-outage loop is fully demoable with zero setup and
zero spend. Swap in the real Claude engine by setting an API key.
"""
import sqlite3

from app.agent import tools
from app.lib.constants import AREAS

_BALANCE_WORDS = ("bilanc", "borxh", "pagu", "fatur", "balance")
_OUTAGE_WORDS = ("rrym", "energ", "ndërprer", "nderprer", "drit", "outage", "power", "s'kam", "skam")


def _match_area(text: str) -> str | None:
    t = text.lower()
    # Exact canonical match first.
    for area in AREAS:
        if area.lower() in t:
            return area
    if "lakrisht" in t:
        return "Prishtinë - Lakrishtë"
    if "prizren" in t:
        return "Prizren - Qendër"
    if "pej" in t or "kala" in t:
        return "Pejë - Kala"
    if "gjilan" in t:
        return "Gjilan - Qendër"
    if "ferizaj" in t or "stacion" in t:
        return "Ferizaj - Stacion"
    if "prishtin" in t or "qend" in t:
        return "Prishtinë - Qendër"
    return None


def run_turn(conn: sqlite3.Connection, caller_phone: str, history: list[dict], user_message: str) -> dict:
    text = user_message.lower()
    trace: list[dict] = []

    def call(name, tool_input):
        result = tools.run_tool(conn, name, tool_input)
        trace.append({"tool": name, "input": tool_input, "result": result})
        return result

    def done(reply):
        return {"reply": reply, "trace": trace, "engine": "mock"}

    # Balance intent.
    if any(w in text for w in _BALANCE_WORDS):
        cust = call("get_customer", {"phone": caller_phone})
        if not cust["found"]:
            return done("Më falni, nuk gjeta një llogari me këtë numër telefoni.")
        bal = cust["balance_eur"]
        if bal < 0:
            return done(f"Përshëndetje {cust['name']}. Ju keni një borxh prej "
                        f"{abs(bal):.2f} € në llogarinë tuaj.")
        return done(f"Përshëndetje {cust['name']}. Bilanci juaj është {bal:.2f} € në favorin tuaj.")

    # Outage intent.
    if any(w in text for w in _OUTAGE_WORDS):
        area = _match_area(text)
        if area is None:
            cust = call("get_customer", {"phone": caller_phone})
            area = cust["area"] if cust["found"] else None
        if area is None:
            return done("Në cilën zonë ndodheni, ju lutem? Për shembull: " + ", ".join(AREAS[:3]) + ".")

        status = call("get_area_outage_status", {"area": area})
        if status.get("active"):
            eta = status.get("eta") or "ende e paverifikuar"
            return done(f"Po, ka një ndërprerje të konfirmuar në zonën {area}. "
                        f"Shkaku: {status.get('cause') or 'në verifikim'}. Koha e pritur: {eta}.")

        report = call("file_outage_report", {"phone": caller_phone, "area": area, "consent_to_sms": True})
        if report.get("immediate_match"):
            return done(f"Ndërprerja në zonën {area} sapo u konfirmua — do të merrni një SMS menjëherë.")
        return done(f"Nuk kemi ende një ndërprerje të konfirmuar në zonën {area}. E ruajtëm numrin tuaj "
                    f"dhe do t'ju dërgojmë një SMS sapo një teknik ta konfirmojë ndërprerjen.")

    # Fallback / greeting.
    return done("Përshëndetje, jam Alba, asistentja automatike e KEDS-it. Mund t'ju ndihmoj me "
                "bilancin e llogarisë ose me një ndërprerje energjie. Si mund t'ju shërbej?")
