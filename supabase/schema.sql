create table if not exists public.boards (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  background text not null default '',
  data jsonb not null default '{"lists":[]}'::jsonb,
  owner_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.board_members (
  board_id uuid not null references public.boards(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'editor', 'commenter', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (board_id, user_id)
);

create table if not exists public.board_invitations (
  id uuid primary key default gen_random_uuid(),
  board_id uuid not null references public.boards(id) on delete cascade,
  email text not null,
  role text not null check (role in ('editor', 'commenter', 'viewer')),
  invited_by uuid not null references auth.users(id) on delete cascade,
  accepted_at timestamptz,
  created_at timestamptz not null default now()
);

insert into storage.buckets (id, name, public)
values ('board-backgrounds', 'board-backgrounds', true)
on conflict (id) do update set public = true;

alter table public.boards enable row level security;
alter table public.board_members enable row level security;
alter table public.board_invitations enable row level security;

create or replace function public.is_board_member(target_board_id uuid, target_user_id uuid default auth.uid())
returns boolean language sql security definer stable set search_path = public as $$
  select exists (select 1 from public.board_members where board_id = target_board_id and user_id = target_user_id);
$$;
create or replace function public.is_board_owner(target_board_id uuid, target_user_id uuid default auth.uid())
returns boolean language sql security definer stable set search_path = public as $$
  select exists (select 1 from public.board_members where board_id = target_board_id and user_id = target_user_id and role = 'owner');
$$;

drop policy if exists "members can read boards" on public.boards;
drop policy if exists "owners can create boards" on public.boards;
drop policy if exists "editors can update boards" on public.boards;
drop policy if exists "members can read memberships" on public.board_members;
drop policy if exists "owners can manage memberships" on public.board_members;
drop policy if exists "members can insert memberships" on public.board_members;
drop policy if exists "owners can update memberships" on public.board_members;
drop policy if exists "owners can delete memberships" on public.board_members;
drop policy if exists "owners can create invitations" on public.board_invitations;
drop policy if exists "users can read their invitations" on public.board_invitations;

create policy "members can read boards" on public.boards for select using (
  public.is_board_member(id) or exists (
    select 1 from public.board_invitations i
    where i.board_id = id and lower(i.email) = lower(auth.jwt() ->> 'email') and i.accepted_at is null
  )
);
create policy "owners can create boards" on public.boards for insert with check (owner_id = auth.uid());
create policy "editors can update boards" on public.boards for update using (
  exists (select 1 from public.board_members m where m.board_id = id and m.user_id = auth.uid() and m.role in ('owner', 'editor'))
);
create policy "members can read memberships" on public.board_members for select using (
  user_id = auth.uid() or public.is_board_member(board_id)
);
create policy "members can insert memberships" on public.board_members for insert with check (
  user_id = auth.uid() and (
    public.is_board_owner(board_id)
    or exists (select 1 from public.boards b where b.id = board_id and b.owner_id = auth.uid())
  )
);
create policy "owners can update memberships" on public.board_members for update using (
  public.is_board_owner(board_id)
) with check (
  public.is_board_owner(board_id)
);
create policy "owners can delete memberships" on public.board_members for delete using (
  public.is_board_owner(board_id)
);
create policy "owners can create invitations" on public.board_invitations for insert with check (
  exists (select 1 from public.board_members m where m.board_id = board_id and m.user_id = auth.uid() and m.role = 'owner')
);
create policy "users can read their invitations" on public.board_invitations for select using (
  lower(email) = lower(auth.jwt() ->> 'email')
  or invited_by = auth.uid()
);

drop policy if exists "authenticated users can upload board backgrounds" on storage.objects;
drop policy if exists "public can read board backgrounds" on storage.objects;
create policy "authenticated users can upload board backgrounds" on storage.objects
  for insert to authenticated with check (bucket_id = 'board-backgrounds' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "public can read board backgrounds" on storage.objects
  for select using (bucket_id = 'board-backgrounds');

create or replace function public.create_board(
  board_name text,
  board_background text default '',
  board_data jsonb default '{"lists":[]}'::jsonb
)
returns public.boards
language plpgsql
security definer
set search_path = public
as $$
declare
  created_board public.boards;
begin
  if auth.uid() is null then
    raise exception 'You must be signed in to create a board';
  end if;

  insert into public.boards (name, background, data, owner_id)
  values (board_name, board_background, board_data, auth.uid())
  returning * into created_board;

  insert into public.board_members (board_id, user_id, role)
  values (created_board.id, auth.uid(), 'owner');

  return created_board;
end;
$$;
grant execute on function public.create_board(text, text, jsonb) to authenticated;

create or replace function public.accept_board_invitation(invitation_id uuid)
returns void language plpgsql security definer set search_path = public as $$
declare invitation public.board_invitations;
begin
  select * into invitation from public.board_invitations
  where id = invitation_id and lower(email) = lower(auth.jwt() ->> 'email')
    and accepted_at is null;
  if invitation.id is null then raise exception 'Invitation not found or already accepted'; end if;
  insert into public.board_members(board_id, user_id, role)
    values (invitation.board_id, auth.uid(), invitation.role)
    on conflict (board_id, user_id) do update set role = excluded.role;
  update public.board_invitations set accepted_at = now() where id = invitation.id;
end;
$$;
