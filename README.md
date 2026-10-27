# Trellis

Trellis is a lightweight collaborative kanban board.

## Local development

```bash
python3 app.py
```

Without Supabase environment variables, the app uses `data.json` exactly as before.

## Supabase + Vercel

1. Create a Supabase project and run [`supabase/schema.sql`](./supabase/schema.sql) in the SQL editor.
   If you already ran an older version, run the current file again; it replaces the affected policies and creates the `board-backgrounds` Storage bucket.
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` as Vercel environment variables.
3. Import this repository into Vercel. The included [`vercel.json`](./vercel.json) serves the app and its config function.
4. Add the deployed URL to Supabase Authentication > URL Configuration.

### Google sign-in

To enable the **Continue with Google** button:

1. In Google Cloud Console, create or select a project.
2. Open **APIs & Services > OAuth consent screen** and configure the app.
3. Open **APIs & Services > Credentials > Create credentials > OAuth client ID**.
4. Choose **Web application**.
5. In Supabase, open **Authentication > Providers > Google** and copy the displayed callback URL.
6. Add that callback URL to the Google OAuth client's **Authorized redirect URIs**.
7. Copy the Google client ID and client secret into Supabase's Google provider settings.
8. Enable the Google provider and save.

The callback URL normally looks like:

```text
https://<project-ref>.supabase.co/auth/v1/callback
```

In Supabase **Authentication > URL Configuration**, also add the deployed Vercel URL to the allowed redirect URLs. The app sends users back to the current site after Google sign-in.

The browser only receives the Supabase anon key. Row-level security protects boards, memberships, and invitations. Board edits are stored as JSONB and synced to members through Supabase Realtime.
