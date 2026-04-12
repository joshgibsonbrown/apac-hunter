# APAC Hunter

A private intelligence tool that monitors financial filings, stock exchanges, and regulatory data to identify ultra-high-net-worth individuals at the moment they experience a significant wealth event (IPO, insider sale, lock-up expiry, M&A, ownership restructuring), then automatically generates strategic relationship briefs.

Built for internal use. All output is strictly confidential.

---

## What it does

1. **Scans** data sources across APAC and Europe: SGX, HKEX, ACRA, SEC EDGAR, Companies House, Euronext, news feeds, IPO pipelines, and secondary market intelligence.
2. **Filters** 200+ raw items down to high-signal candidates using keyword heuristics (no API cost).
3. **Classifies** candidates using Claude (Sonnet) to identify genuine wealth trigger events tied to named individuals.
4. **Researches** each individual via web search (SerpApi) and synthesises a background dossier.
5. **Generates** a structured strategic brief using Claude (Opus), covering individual profile, event significance, access pathways, and suggested outreach framing.
6. **Tracks** insider selling acceleration, lock-up expiry calendars, and ownership changes (SC 13D/G) as continuous background signals.

---

## Architecture

```
app.py                          Flask web app (auth, routes, scan job management)
apac_hunter/
  database.py                   Supabase client + all DB functions (briefs, jobs, events)
  scanner/
    __init__.py                 Public API: run_scan(), get_last_scan_stats()
    _run.py                     Orchestration: fetch → enrich → classify → brief
    _sources.py                 Source fetching (all scrapers)
    _edgar.py                   EDGAR enrichment (insider tracking, lock-up calendar)
  scrapers/                     One module per data source
  intelligence/
    schemas.py                  Pydantic models for all LLM outputs
    classifier.py               Batch AI classification of trigger events
    brief_generator.py          Strategic brief generation
    researcher.py               Web research + dossier synthesis
    normaliser.py               Name cleaning
    pre_filter.py               Fast heuristic pre-filter gate
    lockup_tracker.py           IPO lock-up calendar
    insider_tracker.py          Form 4 parsing + acceleration detection
    analysis_engine.py          Deterministic template analysis
  regions/
    apac.py                     APAC region config (sources, queries, tickers)
    europe.py                   Europe region config
  templates/                    Jinja2 HTML templates
tests/
  test_schemas.py               Pydantic schema + parse_llm_json tests
  test_scan_pipeline.py         Pipeline logic tests (no API calls)
  test_job_tracking.py          Scan job DB function tests (mocked)
```

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd apac-hunter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env` with your credentials (see required variables below). **Never commit `.env`.**

### 3. Run Supabase migrations

Open the Supabase SQL Editor and run all statements in `SCHEMA_MIGRATIONS.md` in order. They are all idempotent (`IF NOT EXISTS`).

### 4. Run locally

```bash
python app.py
```

App starts on `http://localhost:5000`. Log in with your `DASHBOARD_PASSWORD`.

---

## Environment variables

All required. The app will refuse to start if any are missing.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DASHBOARD_PASSWORD` | Login password for the web dashboard |
| `ANTHROPIC_API_KEY` | Anthropic API key (used for classification, research, brief generation) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |

Optional:

| Variable | Description |
|---|---|
| `SERPAPI_KEY` | SerpApi key for web research (research quality degrades without it) |
| `RESEND_API_KEY` | Resend API key for email notifications |
| `COMPANIES_HOUSE_API_KEY` | UK Companies House API key (free at developer.company-information.service.gov.uk) |

---

## Running scans

From the dashboard, select regions (APAC / Europe), scan mode, and lookback window, then click **Run Scan**.

- **Quick scan** (~5 min): SGX, EDGAR, news, IPO pipeline, Companies House, Euronext
- **Deep scan** (~15 min): All sources including secondary markets, PE deals, private companies, RSS feeds, ACRA

Scans run as background jobs tracked in the `scan_jobs` Supabase table. Progress is polled live in the UI.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Tests cover schema validation, pipeline logic, and DB function contracts. They do not require external API credentials.

---

## Deployment

The app is configured for Heroku (see `Procfile` and `runtime.txt`). Set all environment variables as Heroku config vars.

```bash
heroku config:set SECRET_KEY=... DASHBOARD_PASSWORD=... ANTHROPIC_API_KEY=...
git push heroku main
```

---

## Security notes

- The `.env` file is gitignored. Never commit it.
- The app fails at startup if any required secret is missing — there are no insecure defaults.
- All routes require session authentication.
- LLM outputs are validated through Pydantic schemas before persistence; malformed responses are logged and discarded rather than stored.
