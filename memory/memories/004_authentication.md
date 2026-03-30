# Authentication — email/password sessions replacing token auth
Tags: authentication login flask session werkzeug users password
Date: 2026-03-30

## Decision

Replaced single shared Bearer token (flask-httpauth) with traditional
email + password login backed by a `users` DB table and Flask sessions.

## Why

Five named staff members needed individual accounts:
gabby@nbnesigns.com, toby@nbnesigns.com, sanna@nbnesigns.com,
ivan@nbnesigns.com, ben@nbnesigns.com — all initially on `!49Monkswood`.

A shared token gave no per-user identity and was awkward to share securely.

## Implementation

`models.py` — `users` table:
```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    password_hash TEXT NOT NULL,
    active        INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
)
```

`User` model methods:
- `User.authenticate(email, password)` — checks werkzeug password hash, returns user dict or None
- `User.get(email)` — fetch by email
- `User.set_password(email, password)` — update hash
- `User.create(email, name, password)` — new user

Seeding: `_seed_users()` runs on `init_db()` — inserts DEFAULT_USERS from config if table is empty.

`app.py` auth flow:
- `before_request` checks `session['user_email']` — redirects to `/login` if missing
- `GET /login` — shows email+password form
- `POST /login` — calls `User.authenticate`, sets session, redirects to `/`
- `GET /logout` — clears session, redirects to `/login`

Public paths (no auth): `/health`, `/favicon.ico`, `/login`, `/static/`, `/images/`

## Bug fixed at launch

`LOGIN_HTML` is a Python string template. The CSS contains `{font-family: ...}` which
Python's `.format()` method tried to interpret as format placeholders, causing `KeyError: 'font-family'`.
Fixed by using `__ERROR__` as the placeholder and `.replace()` instead of `.format()`.

## Removed

- `flask-httpauth` package — removed from requirements.txt
- `APP_TOKEN` env var — removed from docker-compose.yml and .env.example
- Cookie-based token auth — replaced entirely
