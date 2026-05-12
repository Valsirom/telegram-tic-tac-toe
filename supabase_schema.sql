create table if not exists public.user_stats (
  user_id text primary key,
  stats jsonb not null default '{
    "bot": {
      "games": 0,
      "wins": 0,
      "losses": 0,
      "draws": 0
    },
    "pvp": {
      "games": 0,
      "wins": 0,
      "losses": 0,
      "draws": 0
    }
  }'::jsonb,
  updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_stats_set_updated_at on public.user_stats;

create trigger user_stats_set_updated_at
before update on public.user_stats
for each row
execute function public.set_updated_at();

alter table public.user_stats enable row level security;
