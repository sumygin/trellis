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

The browser only receives the Supabase anon key. Row-level security protects
boards, memberships, and invitations. Board edits are stored as JSONB and
synced to members through Supabase Realtime.

## Syntgrid board API

List the boards available to the authenticated user:

```text
GET https://<trellis-host>/api/boards
HTTP Authorization header: the user's Supabase access token
```

Response:

```json
{"boards":[{"id":"uuid","name":"Personal Board","role":"owner"}]}
```

Syntgrid can fetch a user's Trellis board as a compact, AI-ready JSON payload.
Prefer the board UUID returned by `/api/boards`:

```text
GET https://<trellis-host>/api/board?id=<board-uuid>
HTTP Authorization header: the user's Supabase access token
```

The `name` query parameter remains supported for compatibility, but board names
are not required to be unique. The access token must belong to the same
Supabase account that has access to the requested board. Trellis validates the
token with Supabase Auth and relies on the existing board membership policies,
so the endpoint does not expose boards to other users.

The response uses short keys to reduce prompt size:

```json
{"v":1,"b":"Personal Board","l":[{"n":"To Do","c":[{"t":"Prepare demo","due":"2026-10-31T12:00:00.000Z","k":[{"t":"Slides"},{"t":"Examples","done":true}]}]}]}
```

`t` is a title, `d` a description, `due` a due date, `done` completion state,
`links` attached links, `img` a link preview image, and `k` checklist items.
Empty optional values are omitted. Syntgrid should send the signed-in user's
Supabase access token and use the exact board name selected by the user.

Set `SYNTGRID_ORIGIN` in Vercel to the Syntgrid origin to restrict browser
requests. It must be exactly `http://localhost:3000` or
`https://syntgrid.vercel.app`; requests from other origins receive no CORS
permission. The API requires `SUPABASE_URL` and `SUPABASE_ANON_KEY`, which are
already used by the web app.

To connect from Syntgrid, open Trellis in a popup with
`?syntgridOrigin=https%3A%2F%2Fsyntgrid.vercel.app`. After the existing
Supabase session loads, Trellis sends the access token to the popup opener
with a `TRELLIS_SUPABASE_SESSION` message targeted only at that trusted
origin. Syntgrid should keep the token in memory only, use it to call the
board endpoints, and exclude it from generated prompts and persistence.
