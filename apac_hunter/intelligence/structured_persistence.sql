create table if not exists structured_fact_records (
  id uuid primary key default gen_random_uuid(),
  trigger_event_id uuid null,
  individual_name text null,
  company text null,
  source_type text not null,
  event_type text null,
  event_date date null,
  schema_version text not null,
  packet jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists structured_fact_records_trigger_event_idx
  on structured_fact_records(trigger_event_id);

create index if not exists structured_fact_records_individual_idx
  on structured_fact_records(individual_name);
