# Render — Project Protocol

**Render** is NBNE's internal sign product generator and marketplace publisher.
It takes blank sign templates, generates AI content, renders product images,
and publishes listings to Amazon, Etsy, and eBay.

---

## What this project is

- **URL**: https://render.nbnesigns.co.uk
- **Repo**: https://github.com/NBNEORIGIN/render
- **Local**: `D:\render`
- **Server**: 178.104.1.152 — `/opt/nbne/render/`

## Stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3.0 + Gunicorn (1 worker — in-memory job state) |
| Database | PostgreSQL 16 (production) / SQLite (local dev) |
| Rendering | Playwright headless Chromium → PNG |
| Image processing | Pillow (MAX_IMAGE_PIXELS = 100_000_000) |
| AI content | Anthropic Claude (claude-opus-4-6 for content) |
| Lifestyle images | OpenAI DALL-E |
| Auth | Flask sessions — email + password |
| Image hosting | Own server — nginx serves `/images/` directly |
| SSL | Let's Encrypt via certbot |

## Users

| Email | Name |
|---|---|
| gabby@nbnesigns.com | Gabby |
| toby@nbnesigns.com | Toby |
| sanna@nbnesigns.com | Sanna |
| ivan@nbnesigns.com | Ivan |
| ben@nbnesigns.com | Ben |

Default password: `!49Monkswood` (users can change via `/api/users/password`)

## Architecture

```
nginx (443)
  ├── /images/*  → /opt/nbne/render/images/  (served directly, cached 30d)
  └── /*         → gunicorn :8025 → Flask

Flask app (app.py)
  ├── auth       → models.User (werkzeug hashed passwords)
  ├── products   → models.Product
  ├── blanks     → models.Blank (DB-driven, seeded from config.BLANK_SEEDS)
  ├── jobs       → jobs.py (in-memory queue, Playwright rendering)
  ├── content    → content_generator.py (Anthropic API)
  ├── images     → image_generator.py (Playwright + Pillow)
  └── storage    → local_storage.py (saves to IMAGES_DIR)
```

## Blanks system

Blanks are physical sign blanks (shape, dimensions, print area bounds).
They are stored in the `blanks` DB table, seeded once from `config.BLANK_SEEDS`.

**To add a new blank:**
1. Add entry to `BLANK_SEEDS` in `config.py`
2. Drop the existing `blanks` table on the server so `init_db()` re-seeds it,
   OR POST to `/api/blanks` with the blank data
3. Add SVG templates: `assets/{color}_{slug}_landscape.svg` (and `_portrait.svg` if `has_portrait=True`)

Blank fields:
- `slug` — unique identifier (e.g. `dracula`, `baby_jesus`)
- `width_mm`, `height_mm` — physical dimensions
- `is_circular` — bool
- `display` — human display string (e.g. `"11 x 9.5 cm"`)
- `amazon_code` — size code (XS/S/M/L/XL)
- `sign_bounds` — `(x, y, w, h)` in px — printable area on the blank template
- `peel_bounds` — `(x, y, w, h)` or `null` — peel-and-stick tab area
- `has_portrait` — bool — whether a portrait orientation template exists

## Deployment

```
Server: 178.104.1.152 (in-house Ubuntu)
App dir: /opt/nbne/render/app/    (git repo)
Env file: /opt/nbne/render/.env
Images:   /opt/nbne/render/images/  (bind-mounted to /images in container)
Override: /opt/nbne/render/docker-compose.override.yml
```

### Rebuild and restart

```bash
ssh root@178.104.1.152
cd /opt/nbne/render/app && git pull
docker compose -p render \
  -f docker-compose.yml \
  -f /opt/nbne/render/docker-compose.override.yml \
  --env-file /opt/nbne/render/.env \
  up -d --build
```

### First-time server setup

Run `deploy.sh` from the repo root. It handles:
- Directory creation
- git clone
- .env generation (prompts for secrets)
- certbot SSL
- nginx config
- docker compose up

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL or SQLite URL |
| `DB_PASSWORD` | Postgres password |
| `SECRET_KEY` | Flask session signing key |
| `ANTHROPIC_API_KEY` | Claude API for content generation |
| `OPENAI_API_KEY` | DALL-E for lifestyle images + embeddings |
| `EBAY_CLIENT_ID/SECRET` | eBay publishing |
| `EBAY_RU_NAME` | eBay redirect URI name |
| `PUBLIC_BASE_URL` | Public URL used in marketplace image links |
| `IMAGES_DIR` | Where to write generated images (default: `/images`) |
| `SMTP_HOST/PORT/USER/PASSWORD` | Outbound mail for bug reports |

## Memory system

Project decisions, bug fixes, and session summaries are stored in `memory/memories/*.md`.
The memory system provides hybrid BM25 + cosine similarity search across these files.

```bash
# Search project memory
cd memory && python search.py "how does authentication work"

# Add a new memory
python ingest.py

# Rebuild the vector index
python store.py --rebuild
```

Memories are committed to git. The SQLite vector DB (`memory/render_memory.db`) is
gitignored and rebuilt locally on first search.

## Bug reports

Users click "🐛 Report a Bug" in the top-right of the app.
Reports are emailed to `toby@nbnesigns.com` and `gabby@nbnesigns.com` via IONOS SMTP.

## Key decisions log

See `memory/memories/` for full decision history with reasoning.

| Decision | Chosen | Reason |
|---|---|---|
| Image hosting | Own server + nginx | Removed Cloudflare R2 dependency, faster for Amazon/Etsy/eBay |
| Auth | Email + password sessions | Replaces single shared token; 5 named users |
| Blanks | DB-driven (seeded from config) | Extensible without code changes |
| Workers | 1 Gunicorn worker | Job state is in-memory — multi-worker loses jobs |
| Deployment | Own Ubuntu + Docker | Not Render.com, not Hetzner |
| HTML | Extracted to templates/ | Reduced app.py from 4,598 → 1,796 lines |
