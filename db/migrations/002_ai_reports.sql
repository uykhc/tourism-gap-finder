-- Current generated AI report per municipality.  The report is served from
-- Supabase rather than a deployment-local JSON file.

create table if not exists public.ai_reports (
  region_id text primary key references public.regions(region_id) on delete restrict,
  report_payload jsonb not null,
  generator jsonb not null,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.ai_reports enable row level security;
