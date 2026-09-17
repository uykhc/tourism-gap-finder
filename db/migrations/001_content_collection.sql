-- 전국 카카오 관광 콘텐츠 수집 결과
-- Supabase SQL Editor에 이미 적용한 스키마를 Git으로도 관리한다.

create extension if not exists pgcrypto;

create table if not exists public.regions (
  region_id text primary key,
  area_code text not null,
  sigungu_code text not null,
  province_name text not null,
  region_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (area_code, sigungu_code)
);

create table if not exists public.content_collection_runs (
  run_id uuid primary key default gen_random_uuid(),
  collected_at timestamptz not null default now(),
  taxonomy_version text not null,
  collector_version text not null,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  region_count integer not null default 0 check (region_count >= 0),
  note text,
  created_at timestamptz not null default now()
);

create table if not exists public.region_content_counts (
  run_id uuid not null references public.content_collection_runs(run_id) on delete cascade,
  region_id text not null references public.regions(region_id) on delete restrict,
  content_type text not null check (content_type in (
    '체험관광', '숙박', '쇼핑', '레저스포츠', '문화관광', '음식'
  )),
  place_count integer not null check (place_count >= 0),
  is_complete boolean not null,
  truncated_tile_count integer not null default 0 check (truncated_tile_count >= 0),
  collected_at timestamptz not null default now(),
  primary key (run_id, region_id, content_type)
);

create index if not exists idx_region_content_counts_region_collected
  on public.region_content_counts (region_id, collected_at desc);
create index if not exists idx_region_content_counts_run
  on public.region_content_counts (run_id);
create index if not exists idx_regions_name
  on public.regions (province_name, region_name);

alter table public.regions enable row level security;
alter table public.content_collection_runs enable row level security;
alter table public.region_content_counts enable row level security;
