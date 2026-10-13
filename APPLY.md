# KEDS — how to apply

1. Copy everything in this folder over your project folder (overwrite when asked).
   `app/agent/*` and `public/*` are not touched — I never saw them.
2. Delete `launch.json` (editor config; a hardcoded Windows path).
3. Run the tests:  `pip install -r requirements-dev.txt` then `python -m pytest`
4. Check `app/agent/service.py` for the default model ID (the old README claimed
   `claude-opus-4-8`; I could not verify it) and replace it with an ID from Anthropic's model list.

## What changed
- `app/routes/pending_reports.py` — route was shadowing the library function, so POST /api/pending-reports crashed. Imported with an alias.
- `app/lib/matching.py` — customers who declined SMS were still notified when an outage was confirmed. Now filtered on `consent_to_sms = 1`.
- `app/lib/timeutil.py` — clock was read twice per timestamp; now once.
- `app/lib/cleanup.py` — background loop no longer dies on one exception; DB work runs off the event loop.
- `app/main.py` — static dir is resolved from the file location (no more crash when started from another directory); clean shutdown of the cleanup task.
- `README.md` — removed hardcoded local path and the unverifiable model names; added a Tests section.
- `.gitignore`, `requirements-dev.txt`, `.github/workflows/ci.yml`, `tests/` (19 tests).
