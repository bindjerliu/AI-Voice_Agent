# AI Voice Agent-Prototype

A design prototype for an AI voice agent system for an electricity distribution company.
It deflects high-volume, repetitive call-center queries and implements a **pending-outage notification
loop**: when a customer calls about an outage nobody has confirmed yet,
the system stores their number and area, then notifies them by SMS
once a technician confirms the outage.

This is a bootcamp prototype, not a production system. Everywhere a
real integration would exist (billing/CRM, SCADA/OMS, SMS
gateway, telephony/STT/TTS), this project uses mock or simulated data
instead. Those points are called out below.

## Status

Built as **two separate front-end apps over one shared backend API**:

1. **Customer AI voice agent** (`/`) — an LLM-driven chat that stands in
   for the real telephony + STT + LLM + TTS pipeline. The caller types
   (STT would transcribe speech); the agent understands intent, calls
   systems (mock) via tool use, and replies in Standard Albanian
   (TTS would speak it). Runs on the real Claude API when a key is set,
   otherwise on an offline rule-based fallback (see *LLM engine* below).
2. **Technician & dispatch console** (`/technician/`) — technicians
   report/confirm outages; the dispatch dashboard clusters outages and
   pending reports by area. This is the ops-facing app.

Still no real telephony/STT/TTS — that's the flagged validation risk
(see the language note below).

## Stack

- **Python 3.11 + FastAPI + Uvicorn** — chosen over Node.js because
  this machine already had Python and not Node; FastAPI also gives
  free interactive API docs at `/docs`.
- **SQLite** (Python's builtin `sqlite3`) instead of Postgres — zero
  setup, one inspectable file (`data/keds.db`). Production → Postgres
  behind real billing/CRM/OMS systems.
- **Anthropic Claude** (`anthropic` SDK) for the voice agent's language
  understanding + tool calling, with an offline mock fallback.
- No auth, no message broker, no real SMS provider — all simulated.

## LLM engine — real Claude vs. offline mock (cost note)

The voice agent has two interchangeable engines behind the same
`/api/agent/chat` endpoint. They call the **same tools** and drive the
**same pending-outage loop** — only the language understanding differs.

| Engine | When it runs | Cost |
|---|---|---|
| **mock** (rule-based, offline) | Default — whenever `ANTHROPIC_API_KEY` is not set | $0, no network calls |
| **Claude** (real LLM) | When `ANTHROPIC_API_KEY` is set (or `COMPANY_LLM_MODE=real`) | Pay-per-use on your Anthropic account |

**By default this project costs nothing to run** — the mock engine
handles the whole demo offline. To switch on the real Claude agent:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # from console.anthropic.com
# optional: pick a cheaper/faster model for a demo (ID from the model list)
$env:KEDS_LLM_MODEL = "<model-id>"
```

- The default model is set in `app/agent/service.py`; override it with `COMPANY_LLM_MODEL`.
  Use a model ID from the [Anthropic model list](https://docs.claude.com/en/docs/about-claude/models)
  — an invalid ID makes the real engine fail and the app falls back to mock.
- The engine badge in the customer app shows which engine is live.
- If a real call fails (bad key, network), it falls back to mock rather
  than dropping the call, and the badge says so.

## How to run it

```powershell
cd <project folder>
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

(If the venv doesn't exist yet: `py -3.11 -m venv .venv` then
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.)

Then open the two apps:
- **`http://127.0.0.1:8000/`** — customer AI voice agent (chat). Pick a
  caller ID, then type e.g. *"Sa kam për të paguar?"* or *"Nuk kam
  rrymë në Prizren"*. The tool-call trace shows what it did.
- **`http://127.0.0.1:8000/technician/`** — technician console (report/
  confirm outages) + **`/technician/dashboard.html`** dispatch dashboard.
- **`http://127.0.0.1:8000/docs`** — interactive API docs.

The database file is created and seeded automatically on first run
(`data/keds.db`, mock customers across 6 areas — delete the file to
reset to a clean seed).

A background task expires unmatched pending reports every 60 seconds
once their `expires_at` (default: 24h after creation) has passed. For
demoing, `POST /api/pending-reports` accepts a `ttl_hours` override
(e.g. `0.001`) so you can see expiry without waiting a day, and
`POST /api/admin/run-cleanup` triggers the sweep immediately.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

The suite uses a throw-away SQLite file per test and covers the pending-outage
matching loop (including SMS consent, expiry and one-notification-only), the
REST routes, timestamp formatting and the background cleanup loop. It does not
call the LLM, so it needs no API key.

## Demoing the core loop

**Via the UI** (recommended for a mentor demo):
1. Open the **voice agent** (`/`), pick a caller ID whose area has no
   known outage, and type *"Nuk kam rrymë"* (I have no power). The
   agent looks up the caller's area, sees no confirmed outage, files a
   pending report, and says it'll SMS them once confirmed. The
   tool-call trace shows all three tool calls.
2. Open the **technician console** (`/technician/`) in another tab and
   confirm an outage in that same area → response shows
   `pending_reports_notified: 1`, and the server console logs a
   `[SMS SIMULATED] ...` line to the caller.
3. Open the **dispatch dashboard** (`/technician/dashboard.html`) → the
   area shows the confirmed outage, the matched count, and the full
   audit trail at the bottom.
4. Back in the **voice agent**, start a new call from a *different*
   caller in that area and ask *"A ka ndërprerje?"* — the agent now
   reports the outage is confirmed, with cause and ETA.
5. To see the **unreported-outage clustering** signal: run step 1 for
   two different callers in the same area *without* confirming an
   outage — the dashboard highlights that area with a red
   "⚠ raportime pa ndërprerje të konfirmuar" warning.

**Via `/docs`** (raw API): drive the same loop with `POST
/api/agent/chat`, `POST /api/outages`, `GET /api/pending-reports?area=`,
`GET /api/audit-log`.

Valid area names (fixed list, so area-matching is exact and
deterministic): see `GET /api/areas`, or `app/lib/constants.py`.

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/agent/chat` | Voice agent turn — runs the Claude (or mock) tool-use loop; returns reply + tool trace + engine |
| `GET /api/agent/engine` | Which engine is live (`real` / `mock`) |
| `GET /api/customers` | List customers (used by the voice agent's caller-ID picker) |
| `GET /api/customers/lookup?phone=` or `?account=` | Read-only customer lookup |
| `GET /api/customers/{id}/balance` | Read-only balance lookup |
| `GET /api/outages?area=` | Outage status by area |
| `POST /api/outages` | Technician creates/confirms an outage → triggers matching |
| `PATCH /api/outages/{id}` | Technician updates status/cause/eta → triggers matching on confirm |
| `POST /api/pending-reports` | Customer's "nobody knows yet" report → stored, or matched immediately if already known |
| `GET /api/pending-reports?area=` | List pending/matched/expired reports |
| `GET /api/audit-log` | Who accessed/changed what, when |
| `POST /api/admin/run-cleanup` | Manually trigger expiry sweep (demo convenience) |
| `GET /api/areas` | Fixed list of valid areas/feeders |

## Mapping to real electric distribution company architecture

| This prototype | Production equivalent |
|---|---|
| SQLite `customers` table | Company's real billing/CRM system (customer master data + balance ledger) |
| SQLite `outages` table, technician `POST/PATCH /api/outages` | Company's SCADA/OMS (outage management system) and dispatcher workflow — outage status would flow from the grid, not manual entry |
| `pending_reports` table + matching logic | A lightweight intake queue the OMS integration subscribes to; consent/opt-in tracking would be a real compliance requirement, not a boolean |
| `[SMS SIMULATED]` log line | Real SMS gateway (e.g. Twilio, or the company's existing bulk-SMS vendor) |
| `audit_log` table | Real audit trail / compliance log, likely shipped to a SIEM |
| Voice agent chat (`/`) — typed text in, Claude/mock + tools, text reply | Real telephony (caller ID) + STT (speech→text) + this same LLM+tools layer + TTS (text→speech) |
| Agent tool executors (`app/agent/tools.py`) hitting SQLite | Same tool contract, but calling the company's real billing API / OMS |
| Fixed `AREAS` list | KEDS's GIS / network topology data (which feeder serves which street) |
| No auth on any endpoint | Real deployment needs authN/authZ — the technician/dispatch app especially must not be publicly writable |

## Language note: Standard Albanian vs. Gheg (validation risk)

Kosovo's official written/professional language is **Standard
Albanian** (Tosk-based). Everyday spoken Albanian in Kosovo is
colloquial **Gheg**. This creates an asymmetry that matters for the
real voice pipeline (not yet built here):

- **Agent output (TTS)** can safely target Standard Albanian — that's
  how a formal utility company is expected to sound, and it's a
  solved, low-risk choice.
- **Agent input (STT)** is the harder problem: real callers will speak
  colloquial Gheg, not Standard Albanian, and general-purpose STT
  models are trained primarily on Standard Albanian text/audio. This
  is a known validation risk that would need real caller-audio testing
  before launch — accuracy on Gheg speech (vocabulary, phonology, and
  grammar differences from Tosk-based Standard Albanian) cannot be
  assumed from Standard Albanian benchmarks.

No STT/TTS/telephony integration is implemented in this prototype —
this is a design note for the eventual real pipeline, flagged early
because it's the kind of risk that's cheap to note now and expensive
to discover during a pilot.

## Known limitations (by design, for a prototype)

- Customers who decline SMS (`consent_to_sms = false`) are stored but never notified;
  real deployments need proper opt-in/opt-out tracking (see the mapping table above).

- No auth on any endpoint — the technician/dispatch app would need real
  login in production, and the agent endpoint would sit behind the
  telephony gateway, not be publicly callable.
- The voice agent keeps only prior **text** turns as conversation
  history (not the intermediate tool_use/tool_result blocks) — fine for
  short, self-contained call turns, but a longer multi-step dialogue
  would want the full message history preserved server-side.
- Dashboard clustering threshold (≥2 unmatched pending reports, no
  confirmed outage) is a fixed constant in `dashboard.html`, not
  configurable — fine for a demo, would need tuning against real call
  volume in production.
- No real STT/TTS/telephony — see the language note above.
