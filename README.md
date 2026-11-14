# Trellis

A lightweight, real-time collaborative Kanban board with dual-mode persistence and a token-optimised API for LLM scheduling pipelines.

## Overview

`Trellis` is a collaborative task-management workspace built for low-overhead state synchronisation and direct interoperability with **syntgrid**. It operates seamlessly in both a zero-dependency local mode (backed by a flat `data.json` store) and a multi-user cloud mode powered by **Supabase Realtime**, `JSONB` document storage, and strict Row-Level Security (RLS).

## Key Features

- **Real-Time Collaborative Sync:** Board mutations are persisted as PostgreSQL `JSONB` documents and broadcast instantaneously to active board members via Supabase Realtime channels.
- **Dual-Mode Storage Engine:** Automatically falls back to local `data.json` file persistence when run offline via `python3 app.py`, allowing instant local use without external database dependencies.
- **Fine-Grained Access Control:** Enforces database-level Row-Level Security (RLS) across boards, member roles, invitations, and custom background storage buckets while exposing only the public anonymous key to the client.
- **Rich Card Primitives:** Supports nested checklists, due dates, descriptions, attached URLs with automated link-preview images, and custom board backgrounds.
- **Native `syntgrid` Bridge:** Built-in cross-origin session handoff and a token-minified REST API designed specifically to feed board state into LLM context windows with minimal token overhead.

## Architecture & Security Model

1. **Client-Safe Authentication:** Supports Google OAuth and Supabase Auth. The browser only ever receives the public anon key; all read/write permissions for boards, memberships, and invites are enforced directly by PostgreSQL RLS policies.
2. **Cross-Origin Popup Handoff:** When opened from a trusted `syntgrid` origin (`?syntgridOrigin=...`), Trellis validates the active session and dispatches the user's access token to the opener window via a strictly target-scoped `TRELLIS_SUPABASE_SESSION` `postMessage` event.
3. **Token-Minified Serialization:** To reduce LLM latency and prompt token consumption when scheduling tasks in `syntgrid`, Trellis strips empty optional fields and serialises board hierarchies using single-character keys.

## `syntgrid` Board API

All endpoints validate the caller's `Authorization` bearer token against Supabase Auth and inherit the user's RLS board membership permissions.

Licesnse: MIT
