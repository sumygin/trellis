# Trellis

Trellis is a lightweight collaborative kanban board.

## Local development

```bash
python3 app.py
```

Without Supabase environment variables, the app uses `data.json` exactly as before.

## Supabase + Vercel

1. Create a Supabase project and run [`supabase/schema.sql`](./supabase/schema.sql) in the SQL editor.
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` as Vercel environment variables.
3. Import this repository into Vercel. The included [`vercel.json`](./vercel.json) serves the app and its config function.
4. Add the deployed URL to Supabase Authentication > URL Configuration.

The browser only receives the Supabase anon key. Row-level security protects boards, memberships, and invitations. Board edits are stored as JSONB and synced to members through Supabase Realtime.
