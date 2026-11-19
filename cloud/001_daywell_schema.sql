-- Money Theory cloud foundation. Legacy daywell_* table names are retained for compatibility.
-- Each row belongs to one Supabase Auth user, enforced by Postgres RLS.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists public.daywell_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '' check (length(display_name) <= 100),
  privacy_accepted_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists public.daywell_records (
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('transactions','budgets','habits','checks','tasks','journal','goals','bills')),
  id text not null check (length(id) between 1 and 100),
  body jsonb not null check (jsonb_typeof(body) = 'object'),
  updated_at timestamptz not null default now(),
  primary key (user_id, kind, id)
);

create table if not exists public.daywell_meta (
  user_id uuid not null references auth.users(id) on delete cascade,
  key text not null check (length(key) between 1 and 300),
  value jsonb not null,
  primary key (user_id, key)
);

create table if not exists public.daywell_payments (
  user_id uuid not null references auth.users(id) on delete cascade,
  key text not null check (length(key) between 1 and 300),
  body jsonb not null check (jsonb_typeof(body) = 'object'),
  primary key (user_id, key)
);

-- Administrator roles and access events live outside the exposed API schema.
create table if not exists private.daywell_admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  granted_at timestamptz not null default now()
);
create table if not exists private.daywell_admin_access (
  id bigint generated always as identity primary key,
  actor_id uuid not null references auth.users(id),
  target_id uuid not null references auth.users(id),
  purpose text not null check (length(purpose) between 1 and 200),
  accessed_at timestamptz not null default now()
);

-- Do not rely on dashboard defaults: remove broad access first.
revoke all on public.daywell_profiles, public.daywell_records,
  public.daywell_meta, public.daywell_payments from anon, authenticated;
grant select, insert, update, delete on public.daywell_profiles,
  public.daywell_records, public.daywell_meta,
  public.daywell_payments to authenticated;

alter table public.daywell_profiles enable row level security;
alter table public.daywell_records enable row level security;
alter table public.daywell_meta enable row level security;
alter table public.daywell_payments enable row level security;
alter table private.daywell_admins enable row level security;
alter table private.daywell_admin_access enable row level security;

create policy "profiles_owner" on public.daywell_profiles
  for all to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "records_owner" on public.daywell_records
  for all to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "meta_owner" on public.daywell_meta
  for all to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "payments_owner" on public.daywell_payments
  for all to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- There are intentionally no direct client policies on the private tables.
-- Cloud admin reads will go through an audited Python service after MFA.
