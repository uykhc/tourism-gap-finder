-- JSON inputs that the API combines with the AI report for one region page.
create table if not exists public.region_analysis_artifacts (
  region_id text not null references public.regions(region_id) on delete restrict,
  artifact_type text not null check (artifact_type in (
    'peer_candidates', 'relative_supply', 'datalab_navigation'
  )),
  payload jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (region_id, artifact_type)
);

alter table public.region_analysis_artifacts enable row level security;
