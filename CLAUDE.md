# CLAUDE.md — Render
# North By North East Print & Sign Ltd
# Read this file fully before doing anything else.

---

## What Render Is

Render is NBNE's internal tool for designing aluminium sign products and publishing them
to marketplaces (Amazon, eBay, Etsy) and the NBNE website shop.

It is a **Flask 3.0 web application** running on Hetzner (178.104.1.152, port 8025)
behind nginx at **https://render.nbnesigns.co.uk**.

The primary day-to-day users are **Gabby** and **Sanna**. Toby is the owner/admin.

---

## Who You Are Helping

You are assisting **Gabby Bassett** (gabby@nbnesigns.com), NBNE's product designer.
She is not a developer. Speak plainly. Explain what you are about to do before you do it.
When something will change the live site, say so clearly and ask her to confirm first.

---

## The Codebase

**GitHub:** https://github.com/NBNEORIGIN/render
**Production:** https://render.nbnesigns.co.uk
**Server:** Hetzner 178.104.1.152, Docker container `render-app-1`, port 8025

### Key files

| File | Purpose |
|---|---|
| `app.py` | All Flask routes — the main application |
| `models.py` | Database models (Product, User, Blank, etc.) |
| `config.py` | Environment config, API keys, blank seed data |
| `templates/index.html` | The entire front-end UI (one large HTML+JS file) |
| `image_generator.py` | Playwright-based sign image renderer |
| `etsy_api.py` | Etsy API client |
| `etsy_variation_push.py` | Etsy grouped variation listing publisher |
| `ebay_api.py` | eBay Inventory API client |
| `amazon_api.py` | Amazon SP-API Listings Items client |
| `jobs.py` | Background job queue for image generation |

---

## Database

**Engine:** PostgreSQL (shared Deek/Cairn DB on Hetzner server)
**Container:** `deploy-deek-db-1` (on the `deploy_default` Docker network)
**Database name:** `cairn`
**All tables are prefixed `render_`**

Key tables:
- `render_products` — individual sign SKUs (M-numbers)
- `render_users` — staff logins
- `render_blanks` — sign substrate sizes (dracula, saville, dick, barzan, baby_jesus)
- `render_catalogue_listing` — product families for marketplace grouping
- `render_etsy_listing_group` — Etsy variation listing groups
- `render_ean_pool` — GS1 EAN codes

The `DATABASE_URL` lives in `/opt/nbne/render/.env` on the server.
**Never connect to the database directly. All DB access goes through the Python models.**

---

## Staff Logins

All staff use default password: `!49Monkswood`
Each person only sees their own products on the Products tab.
The QA tab shows all products from all staff (shared review).

| Email | Name |
|---|---|
| gabby@nbnesigns.com | Gabby |
| sanna@nbnesigns.com | Sanna |
| ivan@nbnesigns.com | Ivan |
| jo@nbnesigns.com | Jo |
| ben@nbnesigns.com | Ben |
| nyo@nbnesigns.com | Nyo |
| toby@nbnesigns.com | Toby |

Password changes: use the "Change Password" button in the app header.

---

## Product Sizes (Blanks)

| Slug | Display size | Notes |
|---|---|---|
| dracula | 9.5 × 9.5 cm | Circular |
| saville | 11 × 9.5 cm | |
| dick | 14 × 9 cm | Has portrait orientation option |
| barzan | 19 × 14 cm | |
| baby_jesus | 29 × 19 cm | Has portrait option + peel strip |

Products come in three colours: **silver**, **gold**, **white**.
A full "family" = 1 description × 5 sizes × 3 colours = 15 SKUs.

---

## Marketplace Publishing

### Etsy
- Uses OAuth 2.0 PKCE. Tokens stored in `/opt/nbne/render/etsy_tokens.json` on the server.
- Re-auth: visit https://render.nbnesigns.co.uk/etsy/oauth/connect
- Variation groups: one Etsy listing per product family (all sizes + colours in one listing)
- **Key gotcha:** Etsy callback URL is NOT on the main Edit App page — it is in a hidden
  submenu in the Etsy developer portal. Registered URL:
  `https://render.nbnesigns.co.uk/etsy/oauth/callback`

### eBay
- Uses OAuth 2.0 (standard). Tokens in `/opt/nbne/render/ebay_tokens.json`.
- Re-auth: visit https://render.nbnesigns.co.uk/ebay/oauth/connect
- Policy IDs (configured): fulfillment=253767317013, return=255261922013, payment=186497146013
- **Key gotcha:** `EBAY_ENVIRONMENT` env var must be lowercase (`production` not `PRODUCTION`).
- **Key gotcha:** All `/sell/account/v1/*` requests need `X-EBAY-C-MARKETPLACE-ID: EBAY_GB` header.

### Amazon
- SP-API Listings Items API. Product type: `signage` (lowercase).
- Routes: `/api/amazon/listings/preflight/<id>` and `/api/amazon/listings/publish/<id>`

---

## Deploying Changes to Production

**Changes go through this process:**
1. Edit the file locally
2. `git add <file> && git commit -m "fix(scope): description"`
3. `git push origin main`
4. SSH to the server and hot-patch (no rebuild needed for Python/HTML changes):

```bash
ssh root@178.104.1.152
cd /opt/nbne/render/app && git pull origin main
docker cp app.py render-app-1:/app/app.py
docker cp templates/index.html render-app-1:/app/templates/index.html
# Reload the gunicorn master so the new files take effect.
# NOTE: `docker top` lists the `/bin/sh -c gunicorn ...` wrapper process first.
# Match on `python.*gunicorn app:app` to target the real master — HUP'ing the
# shell wrapper does nothing, workers keep serving the cached templates, and
# the deploy silently fails.
kill -HUP $(docker top render-app-1 | awk '/python.*gunicorn app:app/ {print $2; exit}')
curl http://localhost:8025/health   # should return {"status":"ok"}
```

**Full rebuild** (only needed when Python dependencies change):
```bash
cd /opt/nbne/render/app
docker compose \
  --env-file /opt/nbne/render/.env \
  -f docker-compose.yml \
  -f /opt/nbne/render/docker-compose.override.yml \
  -p render up -d --build
```
Always include both `--env-file` and the override `-f` flags, or the container
will lose its database connection and OAuth tokens on restart.

---

## Known Issues & Recent History

### Fixed — do not re-introduce
- **EBAY_ENVIRONMENT uppercase bug** — fixed with `.lower()` in `ebay_auth.py`
- **Bug report SMTP failure** — switched to Postmark REST API (token hardcoded in `app.py`)
- **Container losing OAuth tokens on rebuild** — fixed with Docker volume mounts in override file
- **DATABASE_URL stale hostname** — was `deploy-cairn-db-1`, now correctly `deploy-deek-db-1`
  after the Cairn→Deek rename. If you see `Name or service not known` DB errors, check `.env` first.
- **QA tab orphaned products** — 15 NULL-owner legacy products deleted 2026-04-24. QA cards now
  have a delete button so products can be removed directly from QA if needed.

### Open issues (current priorities)
1. **eBay 400 error on publish** — `GET /sell/account/v1/return_policy` returns 400.
   Likely causes: expired OAuth token, or stale policy IDs in `ebay_policies.json`.
   Fix path: check https://render.nbnesigns.co.uk/ebay/oauth/status → re-auth if expired →
   if token is valid, run `python ebay_setup_policies.py` on the server to refresh policy IDs.

2. **Etsy `listings_d` scope missing** — the reconcile/delete path requires this scope.
   Fix: re-auth at https://render.nbnesigns.co.uk/etsy/oauth/connect to get a fresh token
   that includes `listings_d`.

---

## Hard Rules

1. **Never commit secrets or `.env` files.** The `.env` lives only on the server at `/opt/nbne/render/.env`.
2. **Never connect to the database directly** from outside the app — always use the
   Python model classes (`Product.get()`, `User.all()`, etc.).
3. **One change per commit.** Use the format `fix(scope): description` or `feat(scope): description`.
4. **Always verify on the live URL** after deploying — there is no local dev environment.
5. **If unsure about a change that affects the live site, ask first.**

---

## Useful URLs

| Purpose | URL |
|---|---|
| Live app | https://render.nbnesigns.co.uk |
| Health check | https://render.nbnesigns.co.uk/health |
| Etsy OAuth status | https://render.nbnesigns.co.uk/etsy/oauth/status |
| Etsy re-auth | https://render.nbnesigns.co.uk/etsy/oauth/connect |
| eBay OAuth status | https://render.nbnesigns.co.uk/ebay/oauth/status |
| eBay re-auth | https://render.nbnesigns.co.uk/ebay/oauth/connect |
| GitHub repo | https://github.com/NBNEORIGIN/render |
