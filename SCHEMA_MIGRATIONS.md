# Schema Migrations

Run these SQL statements in Supabase SQL Editor **before** running a scan with new features.

---

## Phase 4: Multi-Region

```sql
ALTER TABLE trigger_events ADD COLUMN IF NOT EXISTS region text DEFAULT 'apac';
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS region text DEFAULT 'apac';
```

---

## Phase 5: Lock-Up Expiry Calendar

```sql
CREATE TABLE IF NOT EXISTS lockup_calendar (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company text NOT NULL,
    ticker text DEFAULT '',
    ipo_date text,
    lockup_days integer,
    lockup_expiry_date text,
    region text DEFAULT 'apac',
    source_url text DEFAULT '',
    status text DEFAULT 'unknown',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lockup_expiry ON lockup_calendar (lockup_expiry_date);
CREATE INDEX IF NOT EXISTS idx_lockup_status ON lockup_calendar (status);
```

---

## Phase 6: Insider Transactions

```sql
CREATE TABLE IF NOT EXISTS insider_transactions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    individual_name text NOT NULL,
    company text DEFAULT '',
    ticker text DEFAULT '',
    transaction_date text,
    transaction_code text DEFAULT '',
    shares real DEFAULT 0,
    price_per_share real DEFAULT 0,
    total_value real DEFAULT 0,
    shares_remaining real DEFAULT 0,
    filing_url text DEFAULT '',
    region text DEFAULT 'apac',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_insider_name ON insider_transactions (individual_name);
CREATE INDEX IF NOT EXISTS idx_insider_date ON insider_transactions (transaction_date);
CREATE INDEX IF NOT EXISTS idx_insider_code ON insider_transactions (transaction_code);
CREATE INDEX IF NOT EXISTS idx_insider_ticker ON insider_transactions (ticker);
```

---

## Phase 6b: Ownership Changes (SC 13D/G tracking)

```sql
CREATE TABLE IF NOT EXISTS ownership_changes (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    individual_name text DEFAULT '',
    company text DEFAULT '',
    ticker text DEFAULT '',
    filing_type text DEFAULT '',
    filing_date text,
    ownership_pct real DEFAULT 0,
    previous_pct real DEFAULT 0,
    change_direction text DEFAULT 'unknown',
    filing_url text DEFAULT '',
    region text DEFAULT 'apac',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ownership_company ON ownership_changes (company);
CREATE INDEX IF NOT EXISTS idx_ownership_date ON ownership_changes (filing_date);
CREATE INDEX IF NOT EXISTS idx_ownership_name ON ownership_changes (individual_name);
```

---

---

## Hardening: Persistent Scan Jobs

```sql
CREATE TABLE IF NOT EXISTS scan_jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status          text NOT NULL DEFAULT 'pending',   -- pending | running | complete | failed
    progress        integer NOT NULL DEFAULT 0,
    status_message  text,
    started_at      timestamptz,
    finished_at     timestamptz,
    error           text,
    params          jsonb,           -- {days_back, regions, scan_mode}
    items_fetched   integer,
    items_after_filter integer,
    triggers_found  integer,
    briefs_generated integer,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_created_at ON scan_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_jobs_status     ON scan_jobs (status);
```

---

## Workflow + Q&A Layer

```sql
-- Workflow triage status for each brief
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS workflow_status text DEFAULT 'New';

-- Network signal: high-profile individuals factually connected to the subject
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS network_signal text;

-- Source context for grounded Q&A (raw filing content + research facts as JSONB)
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS source_context jsonb;
```

---

---

## Brief Reliability + Explainability Layer

```sql
-- Structured client development relevance bullets (LLM-generated at brief time)
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS why_this_matters jsonb;

-- Evidence-quality confidence level (computed heuristic, separate from classifier confidence)
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS confidence_level text DEFAULT 'Low';
```

---

*Run all statements above in one go if setting up from scratch. Statements use `IF NOT EXISTS` so they are safe to re-run.*
