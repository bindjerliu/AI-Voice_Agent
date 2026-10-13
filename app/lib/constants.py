"""Shared constants: KEDS operating areas (feeders/zones).

In production these would come from KEDS's GIS / network topology system
(which feeder serves which street). Here it's a fixed list so the
prototype's matching logic (pending report area == outage area) is
deterministic and demoable.
"""

AREAS = [
    "Prishtinë - Qendër",
    "Prishtinë - Lakrishtë",
    "Prizren - Qendër",
    "Pejë - Kala",
    "Gjilan - Qendër",
    "Ferizaj - Stacion",
]

OUTAGE_STATUSES = ["reported", "confirmed", "in_progress", "restored"]
